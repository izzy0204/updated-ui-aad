#!/usr/bin/env python3
"""One-off content cleanup: round-trip preloaded clinical cards through
ClinicalModelCard so 'not found' synonyms (Not specified, N/A, TBD, ...)
collapse to the canonical empty-value representation, then re-render
markdown so display is consistently 'Not disclosed'.

Idempotent: skips a file if its round-tripped JSON is byte-identical.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import ClinicalModelCard  # noqa: E402

PRELOADED = REPO / "src" / "core" / "pages" / "preloaded_cards"
BACKUP = PRELOADED / "not_disclosed_backup"
EXCLUDED_DIRS = {BACKUP, PRELOADED / "v1_backup", PRELOADED / "v03_backup"}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> int:
    apply = "--apply" in sys.argv
    sources = sorted(
        p for p in PRELOADED.rglob("*.clinical.json") if not EXCLUDED_DIRS & set(p.parents)
    )
    if not sources:
        print("No *.clinical.json files found.")
        return 0

    changed = 0
    for json_path in sources:
        raw_text = json_path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
        card = ClinicalModelCard.from_dict(raw)
        new_text = card.to_json()
        if _hash(new_text) == _hash(raw_text):
            print(f"Unchanged {json_path.relative_to(PRELOADED)}")
            continue

        changed += 1
        if not apply:
            print(f"[dry-run] Would update {json_path.relative_to(PRELOADED)}")
            continue

        BACKUP.mkdir(parents=True, exist_ok=True)
        backup_dest = BACKUP / json_path.relative_to(PRELOADED).as_posix().replace("/", "__")
        if not backup_dest.exists():
            shutil.copy2(json_path, backup_dest)

        json_path.write_text(new_text, encoding="utf-8")

        md_path = json_path.with_name(json_path.name.replace(".clinical.json", ".clinical.md"))
        if md_path.is_file():
            citations_path = json_path.with_name(json_path.name.replace(".clinical.json", ".citations.json"))
            citations = None
            if citations_path.is_file():
                try:
                    citations = json.loads(citations_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    citations = None
            md_backup = BACKUP / md_path.relative_to(PRELOADED).as_posix().replace("/", "__")
            if not md_backup.exists():
                shutil.copy2(md_path, md_backup)
            md_path.write_text(card.to_markdown(citations=citations), encoding="utf-8")

        print(f"Updated {json_path.relative_to(PRELOADED)}")

    print(f"\n{changed} file(s) {'updated' if apply else 'would be updated'} of {len(sources)} checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
