#!/usr/bin/env python3
"""
Run citation verification using the **upstream** SourceCheckup implementation:
  https://github.com/kevinwu23/SourceCheckup

Upstream `run.py` expects `--citation_url` or `--question` and runs the full
(question → answer → citations → parse → verify) pipeline. Model cards already
provide (statement, URL) pairs; this script only runs the same **verifier** step
as upstream (`prompts.json` → `verifier`, `utils.GPTWrapper`, `extract_contents_from_url`).

Usage:
  export OPENAI_API_KEY=...
  python run_upstream_sourcecheckup_pairs.py \\
    --pairs-dir sourcecheckup_out/pairs_ui_cards \\
    --out-dir sourcecheckup_out/results_upstream

Optional:
  python run_upstream_sourcecheckup_pairs.py --model gpt-4o-mini ...
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import sys
import time
from pathlib import Path

import pandas as pd

SOURCECHECKUP_ROOT = Path(__file__).resolve().parent / "SourceCheckup"
EVAL_ROOT = Path(__file__).resolve().parent


def load_env_file(path: Path) -> None:
    """Minimal KEY=VALUE .env loader; does not override existing os.environ."""
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


def _ensure_upstream_importable() -> None:
    if not SOURCECHECKUP_ROOT.is_dir():
        raise SystemExit(
            f"Missing upstream clone at {SOURCECHECKUP_ROOT}. "
            "Clone with: git clone https://github.com/kevinwu23/SourceCheckup.git SourceCheckup"
        )
    sys.path.insert(0, str(SOURCECHECKUP_ROOT))


def load_prompts() -> dict:
    p = SOURCECHECKUP_ROOT / "prompts.json"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def run_verifier_row(verifier, statement: str, citation_contents: str) -> tuple[str, str]:
    """
    Match upstream run.py line 79-80:
      decision_dict = json.loads(source_verifier(f"{parsed_statement}: {citation_contents}"))
      decision, reason = decision_dict.popitem()
    """
    payload = f"{statement}: {citation_contents}"
    raw = verifier(payload)
    decision_dict = json.loads(raw)
    decision, reason = decision_dict.popitem()
    return str(decision), str(reason)


def process_pairs_csv(
    pairs_csv: Path,
    out_csv: Path,
    verifier,
    extract_fn,
    sleep_s: float,
    row_timeout_s: float,
    checkpoint_every: int = 10,
) -> dict:
    df = pd.read_csv(pairs_csv)
    if not {"statement", "url"}.issubset(df.columns):
        raise ValueError(f"{pairs_csv} must have columns: statement, url")

    rows_out = []
    found_stmt: set[str] = set()

    processed: set[tuple[str, str]] = set()
    if out_csv.is_file():
        try:
            existing = pd.read_csv(out_csv)
            if {"Statement", "Citation URL", "Decision", "Reason"}.issubset(existing.columns):
                for _, r in existing.iterrows():
                    processed.add((str(r["Statement"]).strip(), str(r["Citation URL"]).strip()))
                rows_out = existing.to_dict(orient="records")
                for r in rows_out:
                    if str(r.get("Decision", "")).strip() == "found":
                        found_stmt.add(str(r.get("Statement", "")).strip())
                print(f"[INFO] {pairs_csv.name}: resuming from existing {out_csv.name} ({len(processed)} rows)")
        except Exception as e:
            print(f"[WARN] Could not load existing {out_csv.name} for resume: {e}")

    for i, row in df.iterrows():
        statement = str(row["statement"]).strip()
        url = str(row["url"]).strip()
        if not statement or not url:
            continue

        if (statement, url) in processed:
            continue

        print(f"[INFO] {pairs_csv.name} row {i + 1}/{len(df)}")
        sys.stdout.flush()

        def _work() -> tuple[str, str]:
            contents = extract_fn(url)
            if contents is None:
                return (
                    "not_found",
                    "extract_contents_from_url returned None (non-200 or empty).",
                )
            decision, reason = run_verifier_row(verifier, statement, contents)
            return decision, reason

        class _RowTimeout(Exception):
            pass

        def _alarm_handler(_signum, _frame):
            raise _RowTimeout()

        old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, float(row_timeout_s))
        try:
            decision, reason = _work()
        except _RowTimeout:
            decision, reason = "not_found", f"Timeout after {row_timeout_s}s (likely stuck fetch or API)."
        except Exception as e:
            decision, reason = "not_found", f"Row error: {e}"
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, old_handler)

        rows_out.append(
            {
                "Statement": statement,
                "Citation URL": url,
                "Decision": decision,
                "Reason": reason,
            }
        )
        if decision == "found":
            found_stmt.add(statement)

        processed.add((statement, url))

        if checkpoint_every > 0 and (len(processed) % checkpoint_every == 0):
            out_df = pd.DataFrame(rows_out)
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            out_df.to_csv(out_csv, index=False)
            sys.stdout.flush()

        time.sleep(sleep_s)

    out_df = pd.DataFrame(rows_out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_csv, index=False)

    unique_statements = out_df["Statement"].unique()
    found_statements = out_df[out_df["Decision"] == "found"]["Statement"].unique()
    summary = {
        "pairs_csv": str(pairs_csv.resolve()),
        "output_csv": str(out_csv.resolve()),
        "rows": len(out_df),
        "unique_statements": int(len(unique_statements)),
        "statements_with_at_least_one_found": int(len(found_statements)),
        "fraction_supported": float(len(found_statements) / len(unique_statements))
        if len(unique_statements)
        else 0.0,
    }
    summary_path = out_csv.with_suffix(".summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(
        f"[RESULT] {pairs_csv.name}: {len(found_statements)}/{len(unique_statements)} "
        f"unique statements supported by ≥1 citation → {out_csv.name}"
    )
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Upstream SourceCheckup verifier on (statement,url) pair CSVs.")
    ap.add_argument("--pairs-dir", type=str, default=None, help="Directory of *_pairs.csv files.")
    ap.add_argument(
        "--pairs-files",
        nargs="+",
        default=None,
        help="Explicit pairs CSV paths (overrides --pairs-dir).",
    )
    ap.add_argument("--out-dir", type=str, required=True, help="Directory for upstream-style output CSVs.")
    ap.add_argument(
        "--model",
        type=str,
        default=None,
        help="OpenAI chat model (upstream utils.GPTWrapper defaults to gpt-4-1106-preview). "
        "Recommended today: gpt-4o-mini or gpt-4o.",
    )
    ap.add_argument("--sleep", type=float, default=0.5, help="Seconds between rows (rate limiting).")
    ap.add_argument(
        "--row-timeout",
        type=float,
        default=180.0,
        help="Max seconds per row (URL fetch + OpenAI call). On timeout, marks row not_found and continues.",
    )
    args = ap.parse_args()

    load_env_file(EVAL_ROOT / ".env")

    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        raise SystemExit(
            "Set OPENAI_API_KEY (upstream SourceCheckup uses OpenAI only). "
            f"Add it to {EVAL_ROOT / '.env'} or your environment."
        )

    _ensure_upstream_importable()
    from utils import GPTWrapper, extract_contents_from_url  # noqa: E402

    prompts = load_prompts()
    model = args.model or os.getenv("SOURCECHECKUP_MODEL") or "gpt-4-1106-preview"

    verifier = GPTWrapper(
        model_name=model,
        response_format="json",
        system_prompt=prompts["verifier"],
        seed=0,
        temperature=0,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.pairs_files:
        pair_paths = [Path(p).expanduser().resolve() for p in args.pairs_files]
    elif args.pairs_dir:
        pair_paths = sorted(Path(args.pairs_dir).glob("*_pairs.csv"))
    else:
        raise SystemExit("Provide --pairs-dir or --pairs-files.")

    if not pair_paths:
        raise SystemExit("No pairs CSV files found.")

    summaries = []
    for pairs_csv in pair_paths:
        stem = pairs_csv.stem
        name = stem[: -len("_pairs")] if stem.endswith("_pairs") else stem
        out_csv = out_dir / f"{name}_upstream_sourcecheckup_results.csv"
        summary = process_pairs_csv(
            pairs_csv=pairs_csv,
            out_csv=out_csv,
            verifier=verifier,
            extract_fn=extract_contents_from_url,
            sleep_s=args.sleep,
            row_timeout_s=args.row_timeout,
        )
        summaries.append(summary)

    all_path = out_dir / "upstream_sourcecheckup_all_summaries.json"
    with open(all_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)
    print(f"[OK] Wrote {all_path}")


if __name__ == "__main__":
    main()
