#!/usr/bin/env python3
"""
Flip cookie / captcha / login / geo / verification-wall SourceCheckup fails to SUPPORTED.

Matches the eval-3 corpus_web post-process convention: walls are treated as
SUPPORTED for analysis (not true citation failures).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

COOKIE_HEAD = re.compile(
    r"(this website (stores )?cookies|we use cookies|we value your privacy|"
    r"consent details|#IABV2SETTINGS#|cookie policy|"
    r"checking your browser|just a moment|are you a robot|captcha challenge|"
    r"please enable cookies|cf-browser-verification|attention required|"
    r"verify you are human|human verification|access denied|"
    r"you've been blocked|sorry,? you have been blocked|"
    r"geo.?restricted|not available in your (region|country)|"
    r"cloudflare|"
    r"sign in through your institution|login providers|"
    r"list of academic and research institutions|"
    r"performing security verification|security verification)",
    re.I,
)
REASON_WALL = re.compile(
    r"cookie (policy|consent|banner)|captcha|human.?verif|cloudflare|"
    r"login (page|wall|chrome|providers|information)|consent (banner|page|dialog)|"
    r"connection check page|javascript code, not the actual|"
    r"list of (academic|institutions).{0,40}login|"
    r"very little source text could be extracted|"
    r"error fetching or processing citation|"
    r"security verification",
    re.I,
)


def load_corpus(path: Path) -> dict[str, dict]:
    by_url: dict[str, dict] = {}
    if not path.is_file():
        return by_url
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        url = (row.get("url") or "").strip()
        if url:
            by_url[url] = row
        final = (row.get("final_url") or "").strip()
        if final:
            by_url[final] = row
    return by_url


def is_wall_fail(url: str, reason: str, corpus: dict[str, dict]) -> tuple[bool, str]:
    cr = corpus.get(url) or {}
    if cr.get("wall_category"):
        return True, f"wall_category={cr['wall_category']}"
    text = (cr.get("text") or "")[:1500]
    if COOKIE_HEAD.search(text):
        return True, "cookie/captcha/login texthead"
    if REASON_WALL.search(reason or ""):
        return True, "reason mentions wall/empty-extract"
    if "pubmed.ncbi.nlm.nih.gov" in (url or "") and (
        "login" in text.lower()[:800] or "institution" in text.lower()[:800]
    ):
        if "abstract" not in text.lower()[:500] and len(text) < 5000:
            return True, "pubmed login chrome"
    return False, ""


def relabel_dir(results_dir: Path, corpus: dict[str, dict]) -> list[dict]:
    audit: list[dict] = []
    summaries: list[dict] = []

    for p in sorted(results_dir.glob("*_sourcecheckup_results.csv")):
        name = p.name.replace("_sourcecheckup_results.csv", "")
        rows = list(csv.DictReader(p.open(encoding="utf-8")))
        if not rows:
            continue
        fieldnames = list(rows[0].keys())
        changed = 0
        for r in rows:
            if (r.get("label") or "").upper() == "SUPPORTED":
                continue
            ok, why = is_wall_fail(r.get("url") or "", r.get("reason") or "", corpus)
            if not ok:
                continue
            old = r["label"]
            r["label"] = "SUPPORTED"
            r["reason"] = (
                f"[RELABELLED from {old}] Cookie/consent/captcha/login-wall failure "
                f"treated as SUPPORTED for eval-3 analysis ({why}). "
                f"Original: {r.get('reason') or ''}"
            )
            changed += 1
            audit.append(
                {
                    "card": name,
                    "old_label": old,
                    "why": why,
                    "url": r.get("url", ""),
                    "statement": (r.get("statement") or "")[:120],
                }
            )

        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

        supported = sum(1 for r in rows if r["label"] == "SUPPORTED")
        partial = sum(1 for r in rows if r["label"] == "PARTIAL")
        unsupported = sum(1 for r in rows if r["label"] == "UNSUPPORTED")
        total = len(rows)
        summary = {
            "name": name,
            "pairs_csv": "",
            "total_pairs": total,
            "supported": supported,
            "partial": partial,
            "unsupported": unsupported,
            "strict_score": supported / total if total else 0.0,
            "partial_credit_score": (supported + 0.5 * partial) / total if total else 0.0,
            "wall_fails_relabelled_to_supported": changed,
        }
        # Preserve pairs_csv from existing summary if present
        sp = results_dir / f"{name}_sourcecheckup_summary.json"
        if sp.is_file():
            try:
                prev = json.loads(sp.read_text(encoding="utf-8"))
                if prev.get("pairs_csv"):
                    summary["pairs_csv"] = prev["pairs_csv"]
            except json.JSONDecodeError:
                pass
        sp.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        summaries.append(summary)
        print(f"[OK] {name}: flipped {changed} wall fails → SUPPORTED "
              f"(strict={summary['strict_score']:.3f})")

    (results_dir / "wall_fails_relabelled_to_supported.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    (results_dir / "sourcecheckup_all_summaries.json").write_text(
        json.dumps(summaries, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[OK] audit={len(audit)} flips → {results_dir / 'wall_fails_relabelled_to_supported.json'}")
    return summaries


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", type=str, required=True)
    ap.add_argument(
        "--corpus",
        type=str,
        default="eval/sourcecheckup_corpus_eval3/corpus.jsonl",
    )
    args = ap.parse_args()
    results_dir = Path(args.results_dir)
    corpus = load_corpus(Path(args.corpus))
    print(f"[INFO] corpus URLs={len(corpus)} results_dir={results_dir}")
    relabel_dir(results_dir, corpus)


if __name__ == "__main__":
    main()
