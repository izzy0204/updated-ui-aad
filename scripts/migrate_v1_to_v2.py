#!/usr/bin/env python3
"""One-time deterministic migration: clinical-model-card-1.0 JSON -> clinical-model-card-2.0 JSON.

v1.0 "Risks and Limitations" fields (known_failure_modes, unsupported_clinical_scenarios,
unsupported_use_cases) are merged into a single known_performance_limitations field.
Skin-type/equity content that v1.0 had already folded into known_failure_modes is
best-effort split back out into a new, standalone skin_type_representation_equity field
using keyword-matched sentences; this extraction is lossy and flagged per-card for
manual review in the migration report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import SCHEMA_VERSION, ClinicalModelCard, validate_model_card  # noqa: E402
from utils.sentence_utils import split_sentences  # noqa: E402

PRELOADED = REPO / "src" / "core" / "pages" / "preloaded_cards"
BACKUP = PRELOADED / "v1_backup"

OLD_SCHEMA_VERSION = "clinical-model-card-1.0"

EQUITY_KEYWORDS = (
    "skin type",
    "skin tone",
    "fitzpatrick",
    "underrepresented",
    "under-represented",
    "equity",
    "darker skin",
    "lighter skin",
    "pigment",
    "diverse population",
    "diversity",
    "melanin",
)


def _sents(text: str) -> List[str]:
    return [s.strip() for s in split_sentences(text or "") if s.strip()]


def _split_equity_sentences(text: str) -> Tuple[str, str]:
    """Best-effort split of legacy known_failure_modes into (limitations, equity)."""
    limitations: List[str] = []
    equity: List[str] = []
    for sent in _sents(text):
        low = sent.lower()
        if any(kw in low for kw in EQUITY_KEYWORDS):
            equity.append(sent)
        else:
            limitations.append(sent)
    return " ".join(limitations), " ".join(equity)


def _merge_unique(*parts: str) -> str:
    seen: set = set()
    out: List[str] = []
    for part in parts:
        t = (part or "").strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return " ".join(out)


def _content_hash(card: ClinicalModelCard) -> str:
    return hashlib.sha256(card.to_json().encode()).hexdigest()


def migrate_card(raw: Dict[str, Any]) -> Tuple[ClinicalModelCard, Dict[str, Any]]:
    """Transform a v1.0 clinical card dict into a v2.0 ClinicalModelCard + migration report."""
    known_failure_modes = str(raw.get("knownFailureModes") or "")
    unsupported_clinical_scenarios = str(raw.get("unsupportedClinicalScenarios") or "")
    unsupported_use_cases = str(raw.get("unsupportedUseCases") or "")

    limitations_remainder, equity_extracted = _split_equity_sentences(known_failure_modes)

    known_performance_limitations = _merge_unique(
        limitations_remainder,
        unsupported_clinical_scenarios,
        unsupported_use_cases,
    )

    new_raw = dict(raw)
    new_raw.pop("knownFailureModes", None)
    new_raw.pop("unsupportedClinicalScenarios", None)
    new_raw.pop("unsupportedUseCases", None)
    new_raw["knownPerformanceLimitations"] = known_performance_limitations
    new_raw["skinTypeRepresentationEquity"] = equity_extracted
    new_raw["schemaVersion"] = SCHEMA_VERSION

    card = ClinicalModelCard.from_dict(new_raw)
    result = validate_model_card(card)

    report = {
        "schemaVersionFrom": raw.get("schemaVersion", OLD_SCHEMA_VERSION),
        "schemaVersionTo": SCHEMA_VERSION,
        "equitySentencesExtracted": len(_sents(equity_extracted)),
        "lowConfidenceEquityExtraction": len(_sents(equity_extracted)) == 0,
        "validationErrors": result.errors,
        "validationWarnings": result.warnings,
    }
    return card, report


def _clinical_json_sources() -> List[Path]:
    return sorted(p for p in PRELOADED.rglob("*.clinical.json") if BACKUP not in p.parents)


def _backup(paths: List[Path]) -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, str] = {}
    for p in paths:
        dest = BACKUP / p.relative_to(PRELOADED).as_posix().replace("/", "__")
        if not dest.exists():
            shutil.copy2(p, dest)
        manifest[str(p.relative_to(PRELOADED))] = dest.name
    (BACKUP / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate clinical model cards v1.0 -> v2.0")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    parser.add_argument("--apply", action="store_true", help="Write migrated cards in place (after backup)")
    parser.add_argument("--rollback", action="store_true", help="Restore originals from v1_backup/")
    args = parser.parse_args()

    if args.rollback:
        manifest_path = BACKUP / "MANIFEST.json"
        if not manifest_path.is_file():
            print("ERROR: v1_backup/MANIFEST.json missing, nothing to roll back.", file=sys.stderr)
            return 1
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for rel_path, backup_name in manifest.items():
            shutil.copy2(BACKUP / backup_name, PRELOADED / rel_path)
        print(f"Restored {len(manifest)} file(s) from v1_backup/")
        return 0

    sources = _clinical_json_sources()
    if not sources:
        print("No *.clinical.json files found under preloaded_cards/.")
        return 0

    if args.apply and not args.dry_run:
        _backup(sources)

    failed = 0
    for json_path in sources:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        if raw.get("schemaVersion") == SCHEMA_VERSION:
            print(f"Skipping {json_path.relative_to(PRELOADED)}: already {SCHEMA_VERSION}")
            continue

        card, report = migrate_card(raw)
        content_hash = _content_hash(card)

        if args.dry_run or not args.apply:
            print(
                f"[dry-run] {json_path.relative_to(PRELOADED)}: hash={content_hash[:12]}... "
                f"errors={report['validationErrors']} warnings={report['validationWarnings']} "
                f"equity_sentences={report['equitySentencesExtracted']}"
            )
        else:
            json_path.write_text(card.to_json(), encoding="utf-8")

            md_path = json_path.with_name(json_path.name.replace(".clinical.json", ".clinical.md"))
            citations_path = json_path.with_name(json_path.name.replace(".clinical.json", ".citations.json"))
            citations = None
            if citations_path.is_file():
                try:
                    citations = json.loads(citations_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    citations = None
            if md_path.is_file():
                md_path.write_text(card.to_markdown(citations=citations), encoding="utf-8")

            report_path = json_path.with_name(json_path.name.replace(".clinical.json", ".migration_report.json"))
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Migrated {json_path.relative_to(PRELOADED)} (hash {content_hash[:12]}...)")

        if report["validationErrors"]:
            failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
