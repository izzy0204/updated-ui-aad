#!/usr/bin/env python3
"""
Run the repo's "custom FactScore-like" evaluation on all UI cards in `ui_cards/`.

For each card (one-to-one; never mixed across cards):
- Creates an outputs JSONL from that card's markdown only (`topic` + full card text).
- Builds a corpus JSONL by fetching **only** the unique citation URLs listed in the
  matching pairs file: same basename as the `.md`, e.g. `Tandem updated.md` →
  `Tandem updated_pairs.csv`. That file is the card's reference corpus.
- Runs `custom_factscore_eval.evaluate_one` so retrieval + judging use **that**
  outputs file + **that** corpus only (BM25 over the card's fetched pages).

Outputs (all under --out-dir):
- per-card: *_corpus.jsonl, *_outputs.jsonl, *_factscore_like_results.json
- summary: factscore_like_summary_ui_cards.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import signal
import sys
from pathlib import Path
from typing import Iterable


EVAL_ROOT = Path(__file__).resolve().parent


def load_env_file(path: Path) -> None:
    """Minimal KEY=VALUE .env loader; does not override existing os.environ."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def write_outputs_jsonl(topic: str, md_path: Path, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    row = {"topic": topic, "output": clean_text(md_path.read_text(encoding="utf-8"))}
    out_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def stem_variants(stem: str) -> list[str]:
    """Match extractor output like ``DermGPT_updated_pairs.csv`` to ``DermGPT updated.md``."""
    seen: set[str] = set()
    out: list[str] = []
    for v in (stem, stem.replace(" ", "_"), stem.replace("_", " ")):
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def resolve_pairs_csv(pairs_dir: Path, stem: str) -> Path | None:
    for v in stem_variants(stem):
        p = pairs_dir / f"{v}_pairs.csv"
        if p.is_file():
            return p
    return None


def iter_unique_urls_from_pairs(pairs_csv: Path) -> Iterable[str]:
    with open(pairs_csv, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = str(row.get("url", "")).strip()
            if url:
                yield url


class _UrlTimeout(Exception):
    pass


def _alarm_handler(_signum, _frame):
    raise _UrlTimeout()


def write_corpus_jsonl(urls: list[str], extract_fn, out_path: Path, timeout_s: float) -> dict:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    kept = 0
    skipped = 0
    timeouts = 0
    errors = 0

    old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    with open(out_path, "w", encoding="utf-8") as f:
        for url in urls:
            try:
                signal.setitimer(signal.ITIMER_REAL, float(timeout_s))
                text = extract_fn(url)
            except _UrlTimeout:
                timeouts += 1
                continue
            except Exception:
                errors += 1
                continue
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0.0)

            if not text:
                skipped += 1
                continue

            entry = {"title": url, "text": clean_text(str(text))}
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            kept += 1
    signal.signal(signal.SIGALRM, old_handler)

    return {
        "urls_total": len(urls),
        "docs_written": kept,
        "docs_skipped_empty": skipped,
        "docs_errors": errors,
        "docs_timeouts": timeouts,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Run custom FactScore-like eval on all ui_cards markdown.")
    ap.add_argument("--md-dir", type=str, default=str(EVAL_ROOT / "ui_cards"))
    ap.add_argument("--pairs-dir", type=str, default=str(EVAL_ROOT / "sourcecheckup_out" / "pairs_ui_cards"))
    ap.add_argument("--out-dir", type=str, default=str(EVAL_ROOT / "factscore_out" / "ui_cards_custom"))
    ap.add_argument("--row-timeout", type=float, default=60.0, help="Timeout for a single URL fetch (seconds).")
    ap.add_argument(
        "--only",
        nargs="+",
        default=None,
        metavar="STEM",
        help="Only process these stems (md basename without .md), e.g. dermgpt-20260429-173126 tandem-20260501-043225",
    )
    args = ap.parse_args()

    load_env_file(EVAL_ROOT / ".env")
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        raise SystemExit("Missing OPENAI_API_KEY (set it in .env or environment).")

    md_dir = Path(args.md_dir)
    pairs_dir = Path(args.pairs_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Import custom evaluator + robust (bot-resistant) URL fetcher
    sys.path.insert(0, str(EVAL_ROOT))
    from custom_factscore_eval import ensure_nltk, evaluate_one  # noqa: E402
    from openai import OpenAI  # noqa: E402
    from robust_fetch import fetch_url_text as extract_contents_from_url  # noqa: E402

    ensure_nltk()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    md_paths = sorted(md_dir.glob("*.md"))
    if not md_paths:
        raise SystemExit(f"No markdown cards found in {md_dir}")

    if args.only:
        want = set(args.only)
        md_paths = [p for p in md_paths if p.stem in want]
        missing = want - {p.stem for p in md_paths}
        if missing:
            raise SystemExit(f"--only stems not found under {md_dir}: {sorted(missing)}")
        if not md_paths:
            raise SystemExit("No cards matched --only.")

    all_results = []
    for md_path in md_paths:
        stem = md_path.stem
        pairs_csv = resolve_pairs_csv(pairs_dir, stem)
        if not pairs_csv:
            tried = ", ".join(str(pairs_dir / f"{v}_pairs.csv") for v in stem_variants(stem))
            print(f"[SKIP] Missing pairs CSV for {md_path.name}; tried: {tried}")
            continue

        # Create inputs for the evaluator
        card_out_dir = out_dir / stem
        card_out_dir.mkdir(parents=True, exist_ok=True)

        outputs_jsonl = card_out_dir / f"{stem}_outputs.jsonl"
        corpus_jsonl = card_out_dir / f"{stem}_corpus.jsonl"

        write_outputs_jsonl(topic=stem, md_path=md_path, out_path=outputs_jsonl)

        urls = sorted(set(iter_unique_urls_from_pairs(pairs_csv)))
        print(
            f"[PAIR] {md_path.name} → corpus from {pairs_csv.name} "
            f"({len(urls)} unique URLs) → {corpus_jsonl.name}"
        )
        corpus_stats = write_corpus_jsonl(
            urls=urls,
            extract_fn=extract_contents_from_url,
            out_path=corpus_jsonl,
            timeout_s=args.row_timeout,
        )
        (card_out_dir / f"{stem}_corpus_stats.json").write_text(
            json.dumps(corpus_stats, indent=2),
            encoding="utf-8",
        )

        # Run evaluation (writes detailed results to CWD; we'll move it into the card folder)
        cwd_before = Path.cwd()
        os.chdir(card_out_dir)
        try:
            result = evaluate_one(
                client=client,
                name=stem,
                corpus_path=str(corpus_jsonl),
                outputs_path=str(outputs_jsonl),
            )
        finally:
            os.chdir(cwd_before)

        if result:
            all_results.append(
                {
                    "name": result["name"],
                    "total_facts": result["total_facts"],
                    "supported": result["supported"],
                    "partial": result["partial"],
                    "unsupported": result["unsupported"],
                    "score_strict": result["score_strict"],
                    "score_partial_credit": result["score_partial_credit"],
                }
            )

    summary_path = out_dir / "factscore_like_summary_ui_cards.json"
    by_name: dict[str, dict] = {}
    if summary_path.is_file():
        try:
            prev = json.loads(summary_path.read_text(encoding="utf-8"))
            for row in prev:
                by_name[str(row.get("name", ""))] = row
        except Exception:
            pass
    for row in all_results:
        by_name[row["name"]] = row
    merged = sorted(by_name.values(), key=lambda r: str(r.get("name", "")))
    summary_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Wrote {summary_path} ({len(all_results)} card(s) this run, {len(merged)} total in summary)")


if __name__ == "__main__":
    main()

