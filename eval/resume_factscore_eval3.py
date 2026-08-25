#!/usr/bin/env python3
"""Resume FactScore for missing eval-3 stems, then rebuild the summary JSON."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL_ROOT))

from run_custom_factscore_ui_cards import (  # noqa: E402
    load_env_file,
    resolve_pairs_csv,
    write_outputs_jsonl,
)
from run_factscore_eval3 import write_corpus_from_local  # noqa: E402
from run_sourcecheckup_batch_corpus import load_corpus  # noqa: E402

STEMS = [
    "DERM",
    "DermGPT",
    "Dermasensor",
    "Forus",
    "SkinVision",
    "derm-auto-eval-3",
    "dermgpt-auto-eval-3",
    "dermasensor-auto-eval-3",
    "skinvision-auto-eval-3",
    "tandem-auto-eval-3",
]


def _result_path(out_dir: Path, stem: str) -> Path:
    return out_dir / stem / f"{stem}_factscore_like_results.json"


def _summary_row(result: dict) -> dict:
    return {
        "name": result["name"],
        "total_facts": result["total_facts"],
        "supported": result["supported"],
        "partial": result["partial"],
        "unsupported": result["unsupported"],
        "score_strict": result["score_strict"],
        "score_partial_credit": result["score_partial_credit"],
    }


def write_summary(out_dir: Path) -> Path:
    rows: list[dict] = []
    for stem in STEMS:
        path = _result_path(out_dir, stem)
        if not path.is_file():
            print(f"[WARN] missing results for {stem}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append(_summary_row(data))
        print(
            f"[HAVE] {stem}: strict={data['score_strict']:.3f} "
            f"partial={data['score_partial_credit']:.3f}"
        )
    summary_path = out_dir / "factscore_like_summary_ui_cards.json"
    summary_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"[OK] Wrote {summary_path} ({len(rows)} cards)")
    return summary_path


def main() -> None:
    load_env_file(EVAL_ROOT / ".env")
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        raise SystemExit("Missing OPENAI_API_KEY")

    from custom_factscore_eval import ensure_nltk, evaluate_one
    from openai import OpenAI

    ensure_nltk()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    md_dir = EVAL_ROOT / "ui_cards_eval3"
    pairs_dir = EVAL_ROOT / "sourcecheckup_out" / "pairs_eval3_cards"
    out_dir = EVAL_ROOT / "factscore_out" / "eval3_cards"
    corpus_path = EVAL_ROOT / "sourcecheckup_corpus_eval3" / "corpus.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)

    by_url = load_corpus(corpus_path, include_walls=False)
    fs_path = EVAL_ROOT / "sourcecheckup_corpus_eval3" / "corpus_factscore.jsonl"
    if fs_path.is_file():
        for line in fs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            title = (row.get("title") or "").strip()
            text = (row.get("text") or "").strip()
            if title and text and title not in by_url:
                by_url[title] = text

    missing = [s for s in STEMS if not _result_path(out_dir, s).is_file()]
    print(f"[INFO] Missing stems ({len(missing)}): {missing}")

    for stem in missing:
        md_path = md_dir / f"{stem}.md"
        pairs_csv = resolve_pairs_csv(pairs_dir, stem)
        if not md_path.is_file():
            print(f"[SKIP] missing md {md_path}")
            continue
        if not pairs_csv:
            print(f"[SKIP] missing pairs for {stem}")
            continue

        urls = sorted(
            {
                str(r.get("url", "")).strip()
                for r in csv.DictReader(pairs_csv.open(encoding="utf-8"))
                if str(r.get("url", "")).strip()
            }
        )
        card_out = out_dir / stem
        card_out.mkdir(parents=True, exist_ok=True)
        outputs_jsonl = card_out / f"{stem}_outputs.jsonl"
        corpus_jsonl = card_out / f"{stem}_corpus.jsonl"
        write_outputs_jsonl(topic=stem, md_path=md_path, out_path=outputs_jsonl)
        stats = write_corpus_from_local(urls, by_url, corpus_jsonl)
        (card_out / f"{stem}_corpus_stats.json").write_text(
            json.dumps(stats, indent=2), encoding="utf-8"
        )
        print(
            f"[PAIR] {stem}: {stats['docs_written']}/{stats['urls_total']} corpus docs "
            f"(missing={stats['docs_missing']}, short={stats['docs_too_short']})"
        )
        if stats["docs_written"] == 0:
            print(f"[SKIP] empty corpus for {stem}")
            continue

        cwd_before = Path.cwd()
        os.chdir(card_out)
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
            print(
                f"[RESULT] {stem}: strict={result['score_strict']:.3f} "
                f"partial={result['score_partial_credit']:.3f}"
            )

    write_summary(out_dir)


if __name__ == "__main__":
    main()
