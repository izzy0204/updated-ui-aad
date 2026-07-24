#!/usr/bin/env python3
"""
Official FActScore (`factscore` package) per (statement, URL) row.

**Not the repo’s primary evaluation path.** This project intentionally uses
``custom_factscore_eval.py`` + per-card custom corpora (no ``demons.json``, no
wiki DB) because upstream FactScore’s demo bundle and default knowledge sources
were not relied on here.

This script is optional: it mirrors the paper implementation when you want to
compare against library FActScore and can maintain valid ``.cache/factscore/demos/``
(see AtomicFactGenerator) plus compatible ``openai`` versions.

For each UI card:
1. Load premade corpus JSONL at ``--premade-dir/<stem>/<stem>_corpus.jsonl``
   (same format as custom pipeline: one JSON object per line, ``title`` = URL,
   ``text`` = page body).
2. For each row in ``pairs_ui_cards/<stem>_pairs.csv``, take the **statement** as
   the generation, build a **single-document** corpus JSONL from the premade text
   for that URL, register a dedicated knowledge source, and call ``get_score``.

Use ``--fetch-missing-corpus`` to build missing ``*_corpus.jsonl`` the same way as
``run_custom_factscore_ui_cards.py`` (URL fetch + extract), then score.

Requires ``OPENAI_API_KEY`` and FactScore demo files under ``.cache/factscore/demos/``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

EVAL_ROOT = Path(__file__).resolve().parent


def load_env_file(path: Path) -> None:
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


def normalize_url(u: str) -> str:
    return u.strip().rstrip("/")


def stem_variants(stem: str) -> list[str]:
    """Match pairs filenames like ``DermGPT_updated_pairs.csv`` to ``DermGPT updated.md``."""
    seen: set[str] = set()
    out: list[str] = []
    for v in (
        stem,
        stem.replace(" ", "_"),
        stem.replace("_", " "),
    ):
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


def resolve_corpus_jsonl(premade_dir: Path, stem: str) -> tuple[Path | None, str | None]:
    """Return (path to corpus jsonl, folder stem used) if found."""
    for v in stem_variants(stem):
        p = premade_dir / v / f"{v}_corpus.jsonl"
        if p.is_file():
            return p, v
    return None, None


def slug_ks(s: str, max_len: int = 80) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", s.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:max_len] if s else "card")


def load_corpus_map(jsonl_path: Path) -> dict[str, str]:
    """URL -> text (multiple keys per URL for fuzzy lookup)."""
    m: dict[str, str] = {}
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        title = str(obj.get("title", "")).strip()
        text = str(obj.get("text", "")).strip()
        if not title or not text:
            continue
        m[title] = text
        m[normalize_url(title)] = text
    return m


def lookup_text(corpus_map: dict[str, str], url: str) -> str | None:
    u = url.strip()
    if u in corpus_map:
        return corpus_map[u]
    n = normalize_url(u)
    if n in corpus_map:
        return corpus_map[n]
    # Loose match: normalized titles in map
    for k, v in corpus_map.items():
        if not k.startswith("http"):
            continue
        if normalize_url(k) == n:
            return v
    return None


class _UrlFetchTimeout(Exception):
    pass


def _alarm_fetch(_signum, _frame):
    raise _UrlFetchTimeout()


def fetch_url_text(url: str, timeout_s: float) -> str | None:
    """Single-page fetch with hard timeout (same stack as SourceCheckup)."""
    import signal

    sys.path.insert(0, str(EVAL_ROOT / "SourceCheckup"))
    from utils import extract_contents_from_url

    old = signal.signal(signal.SIGALRM, _alarm_fetch)
    try:
        signal.setitimer(signal.ITIMER_REAL, float(timeout_s))
        out = extract_contents_from_url(url)
        return str(out).strip() if out else None
    except _UrlFetchTimeout:
        return None
    except Exception:
        return None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, old)


def ensure_premade_corpus(
    pairs_csv: Path,
    out_jsonl: Path,
    row_timeout: float,
) -> None:
    sys.path.insert(0, str(EVAL_ROOT))
    sys.path.insert(0, str(EVAL_ROOT / "SourceCheckup"))
    from run_custom_factscore_ui_cards import iter_unique_urls_from_pairs, write_corpus_jsonl
    from utils import extract_contents_from_url

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    urls = sorted(set(iter_unique_urls_from_pairs(pairs_csv)))
    write_corpus_jsonl(
        urls=list(urls),
        extract_fn=extract_contents_from_url,
        out_path=out_jsonl,
        timeout_s=row_timeout,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md-dir", type=str, default=str(EVAL_ROOT / "ui_cards"))
    ap.add_argument("--pairs-dir", type=str, default=str(EVAL_ROOT / "sourcecheckup_out" / "pairs_ui_cards"))
    ap.add_argument(
        "--premade-dir",
        type=str,
        default=str(EVAL_ROOT / "factscore_out" / "ui_cards_custom"),
        help="Directory containing per-card folders with <stem>_corpus.jsonl",
    )
    ap.add_argument(
        "--out-dir",
        type=str,
        default=str(EVAL_ROOT / "factscore_out" / "official_premade_pairs"),
        help="Output directory for JSONL results and per-card summaries",
    )
    ap.add_argument(
        "--data-dir",
        type=str,
        default=str(EVAL_ROOT / ".cache" / "factscore"),
        help="FactScore data dir (must contain demos/ with demons.json)",
    )
    ap.add_argument("--gamma", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="Max pairs total (0 = no limit)")
    ap.add_argument(
        "--fetch-missing-corpus",
        action="store_true",
        help="If <stem>_corpus.jsonl is missing, fetch URLs from pairs CSV first.",
    )
    ap.add_argument("--row-timeout", type=float, default=30.0, help="Per-URL timeout when fetching corpus")
    ap.set_defaults(fetch_url_if_missing=True)
    ap.add_argument(
        "--no-fetch-url-if-missing",
        action="store_false",
        dest="fetch_url_if_missing",
        help="Strict premade only: skip pairs whose URL is absent from corpus JSONL.",
    )
    args = ap.parse_args()

    load_env_file(EVAL_ROOT / ".env")
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        raise SystemExit("Set OPENAI_API_KEY (env or .env)")

    demo_dir = Path(args.data_dir) / "demos"
    if not (demo_dir / "demons.json").is_file():
        raise SystemExit(
            f"Missing FactScore demos at {demo_dir / 'demons.json'}. "
            "Run factscore download_data or copy demos into .cache/factscore/demos/"
        )

    md_dir = Path(args.md_dir)
    pairs_dir = Path(args.pairs_dir)
    premade_dir = Path(args.premade_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_corpus = out_dir / "_tmp_single_doc"
    tmp_corpus.mkdir(parents=True, exist_ok=True)
    db_dir = out_dir / "_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)

    from factscore.factscorer import FactScorer

    fs = FactScorer(
        model_name="retrieval+ChatGPT",
        data_dir=str(Path(args.data_dir)),
        cache_dir=str(out_dir / ".factscore_run_cache"),
        openai_key=os.environ["OPENAI_API_KEY"],
    )

    md_paths = sorted(md_dir.glob("*.md"))
    if not md_paths:
        raise SystemExit(f"No .md files in {md_dir}")

    all_rows: list[dict] = []
    seen = 0
    stem_slug = slug_ks

    for md_path in md_paths:
        stem = md_path.stem
        pairs_csv = resolve_pairs_csv(pairs_dir, stem)
        if not pairs_csv:
            tried = ", ".join(str(pairs_dir / f"{v}_pairs.csv") for v in stem_variants(stem))
            print(f"[SKIP] no pairs file for {md_path.name}; tried: {tried}")
            continue

        corpus_jsonl, folder_stem = resolve_corpus_jsonl(premade_dir, stem)

        if not corpus_jsonl or not corpus_jsonl.is_file():
            build_path = premade_dir / stem / f"{stem}_corpus.jsonl"
            if args.fetch_missing_corpus:
                print(f"[FETCH] Building missing corpus → {build_path}")
                build_path.parent.mkdir(parents=True, exist_ok=True)
                ensure_premade_corpus(pairs_csv, build_path, args.row_timeout)
                corpus_jsonl = build_path
                folder_stem = stem
            else:
                print(f"[SKIP] no premade corpus for {stem}; expected under {premade_dir}/…")
                continue

        corpus_map = load_corpus_map(corpus_jsonl)
        n_docs = sum(1 for _ in corpus_jsonl.read_text(encoding="utf-8").splitlines() if _.strip())
        print(f"[INFO] {stem}: premade corpus {corpus_jsonl} ({n_docs} docs, folder={folder_stem})")

        with open(pairs_csv, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row_idx, row in enumerate(reader):
                if args.limit and seen >= args.limit:
                    break
                statement = str(row.get("statement", "")).strip()
                url = str(row.get("url", "")).strip()
                if not statement or not url:
                    continue

                text = lookup_text(corpus_map, url)
                source = "premade"
                if not text and args.fetch_url_if_missing:
                    text = fetch_url_text(url, args.row_timeout)
                    source = "fetch_fallback"
                if not text:
                    all_rows.append(
                        {
                            "card": stem,
                            "row": row_idx,
                            "statement": statement,
                            "url": url,
                            "error": "no text for URL (not in premade corpus and fetch failed or disabled)",
                        }
                    )
                    seen += 1
                    continue

                one = tmp_corpus / f"{stem_slug(stem)}_{row_idx}.jsonl"
                one.write_text(
                    json.dumps({"title": url, "text": text}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                ks = f"u_{stem_slug(stem)}_{row_idx}"
                dbp = db_dir / f"{stem_slug(stem)}_{row_idx}.db"

                try:
                    fs.register_knowledge_source(ks, data_path=str(one.resolve()), db_path=str(dbp.resolve()))
                except AssertionError as e:
                    if "already registered" in str(e):
                        ks = f"{ks}_dup{seen}"
                        fs.register_knowledge_source(ks, data_path=str(one.resolve()), db_path=str(dbp.resolve()))
                    else:
                        raise

                try:
                    out = fs.get_score(
                        topics=[stem],
                        generations=[statement],
                        knowledge_source=ks,
                        gamma=args.gamma,
                    )
                    # numpy scalars → python
                    score = float(out["score"]) if not isinstance(out["score"], (int, float)) else float(out["score"])
                    init_score = None
                    if args.gamma and "init_score" in out:
                        init_score = float(out["init_score"])
                    all_rows.append(
                        {
                            "card": stem,
                            "row": row_idx,
                            "statement": statement,
                            "url": url,
                            "corpus_text_source": source,
                            "score": score,
                            "init_score": init_score,
                            "respond_ratio": float(out["respond_ratio"]),
                            "num_facts_per_response": float(out["num_facts_per_response"]),
                        }
                    )
                except Exception as e:
                    all_rows.append(
                        {
                            "card": stem,
                            "row": row_idx,
                            "statement": statement,
                            "url": url,
                            "error": str(e),
                        }
                    )

                seen += 1
                if seen % 20 == 0:
                    print(f"[INFO] processed {seen} pairs…")

            if args.limit and seen >= args.limit:
                break

    out_jsonl = out_dir / "official_factscore_premade_pairs.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Aggregate by card
    by_card: dict[str, list[float]] = {}
    for r in all_rows:
        if "score" in r:
            by_card.setdefault(r["card"], []).append(r["score"])

    summary = {
        "pairs_scored": len([r for r in all_rows if "score" in r]),
        "pairs_skipped_or_error": len([r for r in all_rows if "error" in r]),
        "mean_score_overall": float(np.mean([r["score"] for r in all_rows if "score" in r]))
        if any("score" in r for r in all_rows)
        else None,
        "mean_score_by_card": {k: float(np.mean(v)) for k, v in by_card.items()},
    }
    (out_dir / "official_factscore_premade_pairs_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    fs.save_cache()
    print(f"[OK] Wrote {out_jsonl} ({len(all_rows)} rows)")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
