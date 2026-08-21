import os
import re
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import pandas as pd
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from robust_fetch import fetch_url_text as _robust_fetch_url_text  # noqa: E402

OPENAI_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "gemini-2.5-flash"  # gemini-2.0-flash was retired; this 404s if left stale
REQUEST_TIMEOUT = 45
MIN_TEXT_LEN = 80

JudgeFn = Callable[[str, str, str], dict]

RUNS = [
    {
        "name": "dermgpt",
        "pairs_csv": "dermgpt_pairs.csv",
    },
    {
        "name": "skin_analytics",
        "pairs_csv": "skin_analytics_pairs.csv",
    },
    {
        "name": "skinvision",
        "pairs_csv": "skinvision_pairs.csv",
    },
]

def load_env_file(path: Path) -> None:
    """
    Minimal KEY=VALUE .env loader (no python-dotenv dependency).
    Does not override variables already present in os.environ.
    """
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def fetch_url_text(url: str) -> str:
    return clean_text(_robust_fetch_url_text(url))


def _support_evaluation_prompt(statement: str, url: str, truncated_source: str) -> str:
    return f"""
You are doing citation support evaluation.

Task:
Decide whether the cited source supports the statement.

Rules:
- Use ONLY the source text provided.
- SUPPORTED: the source clearly backs the main factual claim(s) in the statement. Exact wording or formatting on the card is not required.
- PARTIAL: the source substantiates an important part of the statement, or the overall gist, even if some secondary details are missing or worded differently.
- UNSUPPORTED: the source is irrelevant, too off-topic, contradicts the statement, or provides no meaningful support for any substantive claim.
- If the statement bundles several facts, use PARTIAL when at least one substantive claim is well supported; reserve UNSUPPORTED for largely irrelevant or contradictory sources.
- If extracted text is short but clearly on-topic and aligned with a major claim, prefer PARTIAL over UNSUPPORTED.
- Do not treat minor omissions (exact dates, product codes, punctuation) as failure if the core claim is supported.

Return ONLY valid JSON in this exact format:
{{
  "label": "SUPPORTED or PARTIAL or UNSUPPORTED",
  "reason": "brief explanation"
}}

Statement:
{statement}

Citation URL:
{url}

Source text:
{truncated_source}
""".strip()


def _parse_support_json(raw: str) -> dict:
    data = json.loads(raw)
    label = str(data.get("label", "")).strip().upper()
    reason = clean_text(str(data.get("reason", "")))

    if label not in {"SUPPORTED", "PARTIAL", "UNSUPPORTED"}:
        label = "UNSUPPORTED"

    return {"label": label, "reason": reason}


def judge_support_openai(client: OpenAI, model: str, statement: str, url: str, source_text: str) -> dict:
    truncated_source = source_text[:12000]
    prompt = _support_evaluation_prompt(statement, url, truncated_source)

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You evaluate whether a cited source supports a statement."},
            {"role": "user", "content": prompt},
        ],
    )

    raw = response.choices[0].message.content
    if not raw:
        return {"label": "UNSUPPORTED", "reason": "Empty response from OpenAI."}
    return _parse_support_json(raw)


def judge_support_gemini(client: Any, model: str, statement: str, url: str, source_text: str) -> dict:
    """
    Uses the Google GenAI SDK (`google-genai`), not the deprecated `google-generativeai` package.
    Retries a few times on transient network / disconnect errors.
    """
    from google.genai import types

    truncated_source = source_text[:12000]
    prompt = _support_evaluation_prompt(statement, url, truncated_source)

    last_err: Exception | None = None
    response = None
    for attempt in range(1, 5):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
            last_err = None
            break
        except Exception as e:  # noqa: BLE001 — judge must not crash the batch
            last_err = e
            if attempt < 4:
                time.sleep(min(2 ** attempt, 12))
                continue
            return {"label": "UNSUPPORTED", "reason": f"Gemini request failed: {e}"}

    if response is None:
        return {"label": "UNSUPPORTED", "reason": f"Gemini request failed: {last_err}"}

    raw = (getattr(response, "text", None) or "").strip()
    if not raw and getattr(response, "candidates", None):
        try:
            parts = response.candidates[0].content.parts
            raw = "".join((getattr(p, "text", None) or "") for p in parts).strip()
        except (IndexError, AttributeError, KeyError):
            raw = ""

    if not raw:
        return {"label": "UNSUPPORTED", "reason": "Empty response from Gemini."}

    try:
        return _parse_support_json(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            return _parse_support_json(m.group(0))
        return {"label": "UNSUPPORTED", "reason": "Could not parse JSON from Gemini response."}


def evaluate_pairs_file(
    judge_fn: JudgeFn,
    name: str,
    pairs_csv: str,
    output_dir: Path | None = None,
    min_text_len: int | None = None,
):
    path = Path(pairs_csv)
    if not path.exists():
        print(f"[SKIP] Missing pairs file: {pairs_csv}")
        return None

    base = output_dir if output_dir is not None else Path(".")
    base.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(path)

    required_cols = {"statement", "url"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"{pairs_csv} must contain columns: statement,url")

    if df.empty:
        print(
            f"[WARN] {name}: pairs CSV has 0 rows — nothing to judge. "
            f"This usually means the markdown had no inline [n] citations on body lines."
        )

    floor = min_text_len if min_text_len is not None else MIN_TEXT_LEN

    results = []
    supported = 0
    partial = 0
    unsupported = 0

    for i, row in df.iterrows():
        statement = str(row["statement"]).strip()
        url = str(row["url"]).strip()

        if not statement or not url:
            continue

        print(f"[INFO] {name}: checking row {i+1}/{len(df)}")

        try:
            source_text = fetch_url_text(url)

            if not source_text or len(source_text) < floor:
                label = "UNSUPPORTED"
                reason = "Very little source text could be extracted from the URL."
            else:
                judgment = judge_fn(statement, url, source_text)
                label = judgment["label"]
                reason = judgment["reason"]

        except Exception as e:
            label = "UNSUPPORTED"
            reason = f"Error fetching or processing citation: {e}"

        if label == "SUPPORTED":
            supported += 1
        elif label == "PARTIAL":
            partial += 1
        else:
            unsupported += 1

        results.append({
            "statement": statement,
            "url": url,
            "label": label,
            "reason": reason,
        })

        time.sleep(0.5)

    total = len(results)
    strict_score = supported / total if total else 0.0
    partial_credit_score = (supported + 0.5 * partial) / total if total else 0.0

    out_df = pd.DataFrame(results)
    out_csv = base / f"{name}_sourcecheckup_results.csv"
    out_df.to_csv(out_csv, index=False)

    summary = {
        "name": name,
        "pairs_csv": str(Path(pairs_csv).resolve()),
        "total_pairs": total,
        "supported": supported,
        "partial": partial,
        "unsupported": unsupported,
        "strict_score": strict_score,
        "partial_credit_score": partial_credit_score,
    }

    summary_path = base / f"{name}_sourcecheckup_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[OK] Saved detailed results to {out_csv}")
    print(f"[RESULT] {name}: strict={strict_score:.3f}, partial-credit={partial_credit_score:.3f}")

    return summary


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Fetch cited URLs and score whether each supports its statement.")
    ap.add_argument(
        "--pairs-dir",
        type=str,
        default=None,
        help="Run on every *_pairs.csv in this directory (e.g. output of extract_pairs_from_cards.py --md-dir).",
    )
    ap.add_argument(
        "--out-dir",
        type=str,
        default=".",
        help="Directory for per-card *_sourcecheckup_results.csv and *_sourcecheckup_summary.json.",
    )
    ap.add_argument("--provider", type=str, choices=("auto", "openai", "gemini"), default="auto", help="LLM backend for judging (auto prefers Gemini if GEMINI_API_KEY is set).")
    ap.add_argument("--model", type=str, default=None, help="OpenAI model name (default: gpt-4o-mini).")
    ap.add_argument("--gemini-model", type=str, default=None, help=f"Gemini model id (default: {GEMINI_MODEL} or GEMINI_MODEL env).")
    ap.add_argument(
        "--pairs-files",
        nargs="+",
        default=None,
        help="Explicit *_pairs.csv files to evaluate (skips --pairs-dir glob). Names derive from filenames.",
    )
    ap.add_argument(
        "--min-text-len",
        type=int,
        default=None,
        help=f"Minimum extracted characters from a URL before judging (default: {MIN_TEXT_LEN}). Lower if many pages extract short text.",
    )
    args = ap.parse_args()

    import sys

    load_env_file(Path(__file__).resolve().parent / ".env")

    openai_model = args.model or os.getenv("OPENAI_MODEL") or OPENAI_MODEL
    gemini_model = args.gemini_model or os.getenv("GEMINI_MODEL") or GEMINI_MODEL

    sys.modules[__name__].OPENAI_MODEL = openai_model

    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()

    provider = args.provider
    if provider == "auto":
        if gemini_key:
            provider = "gemini"
        elif openai_key:
            provider = "openai"
        else:
            raise ValueError("Set GEMINI_API_KEY or OPENAI_API_KEY in .env (or your environment).")

    if provider == "gemini":
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY is required for --provider gemini (or auto when OpenAI key is absent).")

        from google import genai as google_genai

        gemini_client = google_genai.Client(api_key=gemini_key)

        def judge_fn(statement: str, url: str, source_text: str) -> dict:
            return judge_support_gemini(gemini_client, gemini_model, statement, url, source_text)

        print(f"[INFO] Using Gemini (google-genai SDK) model={gemini_model!r} for citation judging.")
    else:
        if not openai_key:
            raise ValueError("OPENAI_API_KEY is required for --provider openai.")

        client = OpenAI(api_key=openai_key)

        def judge_fn(statement: str, url: str, source_text: str) -> dict:
            return judge_support_openai(client, openai_model, statement, url, source_text)

        print(f"[INFO] Using OpenAI model={openai_model!r} for citation judging.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    min_len = args.min_text_len if args.min_text_len is not None else MIN_TEXT_LEN

    if args.pairs_files:
        runs = []
        for p in args.pairs_files:
            path = Path(p).expanduser().resolve()
            if not path.is_file():
                print(f"[SKIP] Missing pairs file: {path}")
                continue
            stem = path.stem
            if stem.endswith("_pairs"):
                card_name = stem[: -len("_pairs")]
            else:
                card_name = stem
            runs.append({"name": card_name, "pairs_csv": str(path)})
        if not runs:
            raise SystemExit("[ERROR] No valid --pairs-files entries.")
    elif args.pairs_dir:
        pairs_dir = Path(args.pairs_dir)
        pair_files = sorted(pairs_dir.glob("*_pairs.csv"))
        if not pair_files:
            raise SystemExit(f"[ERROR] No *_pairs.csv files in {pairs_dir}")
        runs = []
        for p in pair_files:
            stem = p.stem
            if stem.endswith("_pairs"):
                name = stem[: -len("_pairs")]
            else:
                name = stem
            runs.append({"name": name, "pairs_csv": str(p.resolve())})
    else:
        runs = [{"name": r["name"], "pairs_csv": r["pairs_csv"]} for r in RUNS]

    summaries = []
    for run in runs:
        summary = evaluate_pairs_file(
            judge_fn=judge_fn,
            name=run["name"],
            pairs_csv=run["pairs_csv"],
            output_dir=out_dir,
            min_text_len=min_len,
        )
        if summary:
            summaries.append(summary)

    all_path = out_dir / "sourcecheckup_all_summaries.json"
    with open(all_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)

    print(f"[OK] Saved {all_path}")