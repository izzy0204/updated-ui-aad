"""
Render eval-2 manual model cards into an evaluation-ready form.

The manual eval-2 cards (`src/core/pages/preloaded_cards/<slug>-manual-eval-2.clinical.md`)
carry their citations only in a separate `.citations.json` sidecar
(`field_citations`: field -> citation ids, `references`: id -> url). The
`.clinical.md` body itself has no inline `[n]` markers and no References
section, because `ClinicalModelCard.to_markdown()` (src/core/chai_schema.py)
only understands the older `citations["fields"][field]` shape, not this
sidecar shape.

`eval/extract_pairs_from_cards.py` -- and everything downstream of it
(FactScore-style scoring, SourceCheckup) -- needs inline `[n]` markers plus a
`## References` list to build (statement, url) pairs. This script bridges
that gap: for each manual eval-2 card, it appends `[n]` markers to the bullet
line for every cited field and appends a `## References` section, then writes
the result under `eval/ui_cards_eval2/` using the naming convention the old
`eval/ui_cards/` manual cards used (Title Case, no timestamp suffix), so
`eval/readability_analysis.py`'s `infer_card_variant()` still classifies
these as "Manual" rather than "Auto".
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRELOADED_DIR = REPO_ROOT / "src" / "core" / "pages" / "preloaded_cards"
DEFAULT_OUT_DIR = REPO_ROOT / "eval" / "ui_cards_eval2"

# (sidecar slug, output filename). Output names deliberately match the old
# ui_cards/ manual-card convention (Title Case, no timestamp suffix).
MANUAL_CARDS = [
    ("dermasensor-manual-eval-2", "Dermasensor.md"),
    ("dermgpt-manual-eval-2", "DermGPT.md"),
    ("skinanalytics-manual-eval-2", "SkinAnalytics.md"),
    ("skinvision-manual-eval-2", "SkinVision.md"),
    ("tandem-manual-eval-2", "Tandem.md"),
]

# field_citations key -> exact bold bullet label emitted by
# ClinicalModelCard.to_markdown(). Nested/combined fields map both their
# dotted sidecar key and bare parent key to the one bullet that holds them.
FIELD_TO_LABEL: dict[str, str] = {
    "model_name": "Model Name",
    "developer": "Developer",
    "regulatory_approval_status": "Regulatory Approval Status",
    "regulatory_approval_date": "Regulatory Approval Date",
    "version": "Version",
    "last_updated": "Last Updated",
    "availability": "Availability",
    "summary": "Summary",
    "medical_purpose": "Medical Purpose",
    "acceptable_input": "Acceptable Input",
    "output": "Output",
    "role_in_decision_making": "Role in Decision-Making",
    "intended_users": "Intended Users",
    "target_patient_population": "Target Patient Population",
    "known_performance_limitations": "Known Performance Limitations",
    "skin_type_representation_equity": "Skin Type Representation & Equity",
    "required_clinician_oversight": "Required Clinician Oversight",
    "model_type": "Model Type",
    "training_data": "Training Data",
    "training_data.description": "Training Data",
    "model_development_and_validation": "Model Development & Validation",
    "model_development_and_validation.description": "Model Development & Validation",
    "clinical_trial": "Clinical Trial",
    "performance": "Performance",
    "performance.summary": "Performance",
    "performance_evaluation_limitations": "Limitations in Evaluating Performance",
    "ongoing_monitoring_plan": "Plans for Ongoing Monitoring",
    "scheduled_updates": "Scheduled Updates",
    "contact": "Inquiries / Report an Issue",
}


def collect_field_citation_ids(field_citations: dict) -> dict[str, list[int]]:
    """field_key -> sorted unique citation ids cited for that field."""
    ids_by_field: dict[str, set[int]] = {}
    for field_key, entries in field_citations.items():
        ids: set[int] = set()
        for entry in entries:
            for raw_id in entry.get("citationIds", []):
                try:
                    ids.add(int(raw_id))
                except (TypeError, ValueError):
                    continue
        if ids:
            ids_by_field[field_key] = ids
    return {key: sorted(value) for key, value in ids_by_field.items()}


def bullet_label_pattern(label: str) -> re.Pattern[str]:
    return re.compile(r"^(\s*-\s*\*\*" + re.escape(label) + r":\*\*.*)$", re.MULTILINE)


def render_card(slug: str, out_name: str, out_dir: Path) -> None:
    md_path = PRELOADED_DIR / f"{slug}.clinical.md"
    citations_path = PRELOADED_DIR / f"{slug}.citations.json"

    md_text = md_path.read_text(encoding="utf-8")
    citations = json.loads(citations_path.read_text(encoding="utf-8"))
    references: dict[str, dict] = citations.get("references", {})
    field_citations: dict = citations.get("field_citations", {})

    ids_by_field = collect_field_citation_ids(field_citations)

    used_ref_ids: set[int] = set()
    unresolved_fields: list[str] = []
    unlabeled_fields: list[str] = []

    for field_key, ids in ids_by_field.items():
        label = FIELD_TO_LABEL.get(field_key)
        if label is None:
            unlabeled_fields.append(field_key)
            continue

        resolvable_ids = [i for i in ids if str(i) in references]
        if not resolvable_ids:
            continue

        pattern = bullet_label_pattern(label)
        match = pattern.search(md_text)
        if not match:
            unresolved_fields.append(field_key)
            continue

        line = match.group(1)
        if all(f"[{i}]" in line for i in resolvable_ids):
            used_ref_ids.update(resolvable_ids)
            continue  # already annotated (idempotent re-run)

        marker = "".join(f"[{i}]" for i in resolvable_ids)
        new_line = f"{line} {marker}"
        md_text = md_text[: match.start(1)] + new_line + md_text[match.end(1) :]
        used_ref_ids.update(resolvable_ids)

    if unresolved_fields:
        print(f"[WARN] {slug}: no matching bullet found for fields: {unresolved_fields}")
    if unlabeled_fields:
        print(f"[WARN] {slug}: no label mapping for fields: {unlabeled_fields}")

    if used_ref_ids:
        ref_lines = [
            f"[{i}] {references[str(i)]['url']}"
            for i in sorted(used_ref_ids)
            if references.get(str(i), {}).get("url")
        ]
        # Drop any pre-existing References section from a prior run before re-appending.
        md_text = re.sub(r"\n## References\n.*\Z", "", md_text, flags=re.DOTALL)
        md_text = md_text.rstrip() + "\n\n## References\n" + "\n".join(ref_lines) + "\n"

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name
    out_path.write_text(md_text, encoding="utf-8")
    print(f"[OK] {slug} -> {out_path} ({len(used_ref_ids)} citations inlined)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    for slug, out_name in MANUAL_CARDS:
        render_card(slug, out_name, args.out_dir)


if __name__ == "__main__":
    main()
