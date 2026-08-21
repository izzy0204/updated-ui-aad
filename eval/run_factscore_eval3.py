#!/usr/bin/env python3
"""Run custom FactScore-like eval on eval-3 UI cards using the local URL corpus."""

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


def write_corpus_from_local(
    urls: list[str],
    by_url: dict[str, str],
    out_path: Path,
    *,
    min_len: int = 200,
) -> dict:
    from run_sourcecheckup_batch_corpus import _url_key_variants

    out_path.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    missing = 0
    short = 0
    with out_path.open("w", encoding="utf-8") as f:
        for url in urls:
            text = ""
            for key in _url_key_variants(url):
                if key in by_url and by_url[key]:
                    text = by_url[key]
                    break
            if not text:
                missing += 1
                continue
            if len(text) < min_len:
                short += 1
                continue
            f.write(json.dumps({"title": url, "text": text}, ensure_ascii=False) + "\n")
            kept += 1
    return {
        "urls_total": len(urls),
        "docs_written": kept,
        "docs_missing": missing,
        "docs_too_short": short,
    }


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
    # Also merge factscore-formatted corpus if present (title/text).
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

    print(f"[INFO] Local corpus keys≈{len(by_url)}; writing under {out_dir}")

    all_results: list[dict] = []
    for stem in STEMS:
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
            print(
                f"[RESULT] {stem}: strict={result['score_strict']:.3f} "
                f"partial={result['score_partial_credit']:.3f}"
            )

    summary_path = out_dir / "factscore_like_summary_ui_cards.json"
    summary_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"[OK] Wrote {summary_path} ({len(all_results)} cards)")


if __name__ == "__main__":
    main()
