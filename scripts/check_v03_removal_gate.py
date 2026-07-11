#!/usr/bin/env python3
"""Enforce validation gate before removing v0.3 support."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
PRELOADED = REPO / "src/core/pages/preloaded_cards"
MIGRATED = PRELOADED / "clinical_migrated"


def main() -> int:
    errors = []

    checklist = MIGRATED / "CHECKLIST.md"
    if not checklist.is_file():
        errors.append("Missing clinical_migrated/CHECKLIST.md")

    backup = PRELOADED / "v03_backup" / "MANIFEST.json"
    if not backup.is_file():
        errors.append("Missing v03_backup/MANIFEST.json")

    root_legacy_md = [
        p
        for p in PRELOADED.glob("*.md")
        if p.parent == PRELOADED and ".clinical." not in p.name
    ]
    if root_legacy_md:
        errors.append(
            f"Legacy v0.3 markdown still in preloaded_cards root: {[p.name for p in root_legacy_md]}"
        )

    clinical_jsons = list(PRELOADED.glob("*.clinical.json")) + list(MIGRATED.glob("*.clinical.json"))
    if len(clinical_jsons) < 6:
        errors.append(f"Expected >=6 clinical JSON cards, found {len(clinical_jsons)}")

    for jp in clinical_jsons:
        data = json.loads(jp.read_text(encoding="utf-8"))
        if data.get("schemaVersion") != "clinical-model-card-1.0":
            errors.append(f"Bad schemaVersion in {jp.name}")
        cite_path = jp.with_name(jp.name.replace(".clinical.json", ".citations.json"))
        if cite_path.is_file():
            cites = json.loads(cite_path.read_text(encoding="utf-8"))
            if not cites.get("references"):
                errors.append(f"Missing references in {cite_path.name}")

    import importlib.util

    def _load_test(mod_name: str):
        path = REPO / f"{mod_name}.py"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        return mod

    test_modules = [
        ("test_clinical_schema", [
            "test_schema_round_trip_camel_case",
            "test_regulatory_enum_tier_mapping",
            "test_conservative_regulatory_mapping",
            "test_sentence_count_abbreviations",
            "test_validate_summary_warning",
        ]),
        ("test_sentence_utils", [
            "test_us_abbreviation",
            "test_decimal_percent",
            "test_url_in_sentence",
            "test_three_sentences",
        ]),
        ("test_citation_render", [
            "test_one_sentence_one_citation",
            "test_clickable_links_in_viewer",
            "test_missing_sidecar_strips_markers",
            "test_migration_sidecar_from_v03_references",
        ]),
        ("test_source_regulatory", [
            "test_fda_url_is_green",
            "test_clinicaltrials_is_orange",
            "test_per_field_tiers_from_citations",
        ]),
        ("test_scoring", [
            "test_scorer_weights_sum_to_one",
            "test_scorer_clinical_fixture_completion",
            "test_scorer_field_level_quality",
            "test_scorer_low_confidence_regulatory_penalized",
            "test_scorer_fda_without_evidence_critical",
        ]),
        ("test_dermauto_render", [
            "test_fixture_renders_linked_title",
            "test_regulatory_color_only_on_status_row",
            "test_fixture_renders_performance_metrics_table",
        ]),
        ("test_summary_enforcement", [
            "test_summary_within_limit_unchanged",
            "test_callback_success_replaces_summary",
        ]),
    ]
    for mod_name, fns in test_modules:
        mod = _load_test(mod_name)
        for fn_name in fns:
            getattr(mod, fn_name)()

    tr = _load_test("test_regulatory_status")
    tr.test_fda_cleared()
    tr.test_card_tier_only_on_regulatory_row()

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO / 'src'}:{REPO / '.pytest_deps'}:{env.get('PYTHONPATH', '')}"
    pytest = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", "unit", "-q"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )
    if pytest.returncode != 0:
        errors.append("Full pytest unit suite failed")
        if pytest.stdout:
            print(pytest.stdout, file=sys.stderr)
        if pytest.stderr:
            print(pytest.stderr, file=sys.stderr)

    if errors:
        for e in errors:
            print(f"GATE FAIL: {e}", file=sys.stderr)
        return 1
    print("v0.3 removal gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
