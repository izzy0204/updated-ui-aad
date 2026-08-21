#!/usr/bin/env python3
"""
Corpus-backed SourceCheckup batch runner.

Same judging loop as ``run_sourcecheckup_batch.py``, but source text is looked
up from a pre-fetched corpus (``eval/sourcecheckup_corpus_eval3/corpus.jsonl``)
instead of live HTTP/Selenium fetch.

Does not modify upstream SourceCheckup or ``robust_fetch``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict
from urllib.parse import quote, unquote, urlparse, urlunparse

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
sys.path.insert(0, str(EVAL_DIR))

import run_sourcecheckup_batch as sc  # noqa: E402


def _norm_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    parsed = urlparse(u)
    path = parsed.path or ""
    if path.endswith("/") and path != "/":
        path = path[:-1]
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))


def _url_key_variants(url: str) -> list[str]:
    """
    Build lookup keys so spaced paths match percent-encoded corpus URLs
    (e.g. ``PD1123_Digital Practice.pdf`` ↔ ``PD1123_Digital%20Practice.pdf``).
    """
    raw = (url or "").strip()
    if not raw:
        return []
    keys: list[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        u = (u or "").strip()
        if not u or u in seen:
            return
        seen.add(u)
        keys.append(u)

    for base in (raw, unquote(raw)):
        add(base)
        add(_norm_url(base))
        p = urlparse(base)
        path = p.path or ""
        # Encode path segments (spaces → %20) without double-encoding existing %XX.
        enc_path = quote(unquote(path), safe="/:@-._~!$&'()*+,;=")
        add(urlunparse((p.scheme, p.netloc, enc_path, p.params, p.query, "")))
        add(
            urlunparse(
                (p.scheme, p.netloc, (enc_path.rstrip("/") or ""), "", "", "")
            )
        )
        add(urlunparse((p.scheme, p.netloc, (path.rstrip("/") or ""), "", "", "")))
    return keys


def load_corpus(path: Path, *, include_walls: bool = False) -> Dict[str, str]:
    by_url: Dict[str, str] = {}
    if not path.is_file():
        raise SystemExit(f"[ERROR] Corpus not found: {path}")

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = (row.get("text") or "").strip()
        if not text:
            continue
        status = (row.get("status") or "success").lower()
        if status != "success" and not include_walls:
            continue

        keys: list[str] = []
        for key in (row.get("url"), row.get("final_url"), row.get("title")):
            if not key:
                continue
            keys.extend(_url_key_variants(str(key)))

        for key in keys:
            if not key:
                continue
            prev = by_url.get(key)
            if prev is None or len(text) > len(prev):
                by_url[key] = text
    return by_url


def make_corpus_fetcher(
    by_url: Dict[str, str],
    *,
    fallback_live: bool = False,
    min_corpus_len: int = 80,
    always_live_compare: bool = False,
):
    """
    Look up source text from the local corpus first.

    When ``fallback_live`` is True, also try ``robust_fetch`` (live HTTP /
    Selenium) if the corpus miss/short extract is under ``min_corpus_len``,
    or for every URL when ``always_live_compare`` is set. When both texts
    exist, keep the longer one.
    """

    def _corpus_hit(url: str) -> str:
        best = ""
        for key in _url_key_variants(url):
            if key in by_url:
                text = sc.clean_text(by_url[key])
                if len(text) > len(best):
                    best = text
        return best

    def fetch(url: str) -> str:
        corpus_text = _corpus_hit(url)
        if not fallback_live:
            return corpus_text

        need_live = always_live_compare or len(corpus_text) < min_corpus_len
        if not need_live:
            return corpus_text

        live_text = ""
        try:
            from robust_fetch import fetch_url_text as live_fetch

            live_text = sc.clean_text(live_fetch(url) or "")
        except Exception as exc:  # noqa: BLE001 — keep corpus result on live failure
            print(f"[WARN] live fetch failed for {url!r}: {exc}")

        if not corpus_text:
            return live_text
        if not live_text:
            return corpus_text
        return live_text if len(live_text) > len(corpus_text) else corpus_text

    return fetch


def run_batch(remaining_argv: list[str]) -> None:
    """Execute the same CLI path as run_sourcecheckup_batch.__main__."""
    import argparse as ap_mod

    parser = ap_mod.ArgumentParser(
        description="Fetch cited URLs (from corpus) and score whether each supports its statement."
    )
    parser.add_argument("--pairs-dir", type=str, default=None)
    parser.add_argument("--out-dir", type=str, default=".")
    parser.add_argument(
        "--provider", type=str, choices=("auto", "openai", "gemini"), default="auto"
    )
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--gemini-model", type=str, default=None)
    parser.add_argument("--pairs-files", nargs="+", default=None)
    parser.add_argument("--min-text-len", type=int, default=None)
    args = parser.parse_args(remaining_argv)

    sc.load_env_file(EVAL_DIR / ".env")
    sc.load_env_file(REPO_ROOT / ".env")

    openai_model = args.model or os.getenv("OPENAI_MODEL") or sc.OPENAI_MODEL
    gemini_model = args.gemini_model or os.getenv("GEMINI_MODEL") or sc.GEMINI_MODEL
    sc.OPENAI_MODEL = openai_model

    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()

    provider = args.provider
    if provider == "auto":
        if gemini_key:
            provider = "gemini"
        elif openai_key:
            provider = "openai"
        else:
            raise SystemExit("Set GEMINI_API_KEY or OPENAI_API_KEY.")

    if provider == "gemini":
        from google import genai as google_genai

        gemini_client = google_genai.Client(api_key=gemini_key)

        def judge_fn(statement: str, url: str, source_text: str) -> dict:
            return sc.judge_support_gemini(gemini_client, gemini_model, statement, url, source_text)

        print(f"[INFO] Using Gemini model={gemini_model!r} for citation judging.")
    else:
        from openai import OpenAI

        client = OpenAI(api_key=openai_key)

        def judge_fn(statement: str, url: str, source_text: str) -> dict:
            return sc.judge_support_openai(client, openai_model, statement, url, source_text)

        print(f"[INFO] Using OpenAI model={openai_model!r} for citation judging.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    min_len = args.min_text_len if args.min_text_len is not None else sc.MIN_TEXT_LEN

    if args.pairs_files:
        runs = []
        for p in args.pairs_files:
            path = Path(p).expanduser().resolve()
            if not path.is_file():
                print(f"[SKIP] Missing pairs file: {path}")
                continue
            stem = path.stem
            card_name = stem[: -len("_pairs")] if stem.endswith("_pairs") else stem
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
            name = stem[: -len("_pairs")] if stem.endswith("_pairs") else stem
            runs.append({"name": name, "pairs_csv": str(p.resolve())})
    else:
        raise SystemExit("[ERROR] Provide --pairs-dir or --pairs-files.")

    summaries = []
    for run in runs:
        summary = sc.evaluate_pairs_file(
            judge_fn=judge_fn,
            name=run["name"],
            pairs_csv=run["pairs_csv"],
            output_dir=out_dir,
            min_text_len=min_len,
        )
        if summary:
            summaries.append(summary)

    all_path = out_dir / "sourcecheckup_all_summaries.json"
    all_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"[OK] Saved {all_path}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="SourceCheckup batch using a local pre-fetched URL corpus."
    )
    ap.add_argument(
        "--corpus",
        type=str,
        default=str(EVAL_DIR / "sourcecheckup_corpus_eval3" / "corpus.jsonl"),
    )
    ap.add_argument("--include-wall-text", action="store_true")
    ap.add_argument(
        "--fallback-live-fetch",
        action="store_true",
        help="Also live-fetch URLs when corpus text is missing/short (robust_fetch).",
    )
    ap.add_argument(
        "--always-live-compare",
        action="store_true",
        help="With --fallback-live-fetch, live-fetch every URL and keep the longer of corpus vs live.",
    )
    ap.add_argument(
        "--min-corpus-len",
        type=int,
        default=80,
        help="Corpus extracts shorter than this still trigger a live fetch when --fallback-live-fetch is set.",
    )
    args, remaining = ap.parse_known_args()

    corpus_path = Path(args.corpus).expanduser()
    if not corpus_path.is_file():
        for cand in (EVAL_DIR / args.corpus, REPO_ROOT / args.corpus):
            if cand.is_file():
                corpus_path = cand
                break
    if not corpus_path.is_file():
        raise SystemExit(f"[ERROR] Corpus not found: {args.corpus}")

    by_url = load_corpus(corpus_path, include_walls=args.include_wall_text)
    print(
        f"[INFO] Loaded corpus {corpus_path} with {len(by_url)} URL keys "
        f"(include_walls={args.include_wall_text}, "
        f"fallback_live={args.fallback_live_fetch}, "
        f"always_live_compare={args.always_live_compare})."
    )

    sc.fetch_url_text = make_corpus_fetcher(  # type: ignore[assignment]
        by_url,
        fallback_live=args.fallback_live_fetch,
        min_corpus_len=args.min_corpus_len,
        always_live_compare=args.always_live_compare,
    )
    run_batch(remaining)


if __name__ == "__main__":
    main()
