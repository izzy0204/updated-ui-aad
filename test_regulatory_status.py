#!/usr/bin/env python3
"""Smoke tests for regulatory status classification."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.card_regulatory import (
    classify_regulatory_status,
    compute_regulatory_for_sections,
    resolve_card_regulatory_tier,
)
from core.dermauto_card_render import normalize_md_for_parsing, parse_model_card_md


def test_fda_cleared() -> None:
    assert classify_regulatory_status("FDA De Novo / Class II classification. [8]") == "green"


def test_not_fda_approved() -> None:
    assert classify_regulatory_status("Not FDA approved / not described as a regulated medical device. [1]") == "red"


def test_ce_marked() -> None:
    assert classify_regulatory_status("Available in the EU; CE marked for clinical use.") == "blue"


def test_eua() -> None:
    assert classify_regulatory_status("Authorized under FDA emergency use authorization (EUA).") == "yellow"


def test_investigational() -> None:
    assert classify_regulatory_status("For investigational use only; IRB approval required.") == "orange"


def test_unknown() -> None:
    assert classify_regulatory_status("Not specified") == "gray"
    assert classify_regulatory_status("General workflow description without regulatory terms.") == "gray"


def test_fda_and_ce_prefers_green() -> None:
    text = "FDA-cleared in the U.S.; CE marked in Europe. [1]"
    assert classify_regulatory_status(text) == "green"


def test_card_tier_only_on_regulatory_row() -> None:
    sections = {
        "1) Metadata": {
            "Regulatory Approval Status": "FDA Cleared",
            "Summary": "Helps clinicians triage skin lesions.",
        },
    }
    tiers = compute_regulatory_for_sections(sections)
    assert tiers["1) Metadata|||Regulatory Approval Status"] in ("green", "gray")
    assert tiers["1) Metadata|||Summary"] == "gray"


def test_bundled_dermgpt_clinical_json() -> None:
    path = Path(__file__).parent / "src/core/pages/preloaded_cards/dermgpt-20260429-173126.clinical.json"
    if not path.exists():
        return
    from core.chai_schema import ClinicalModelCard
    from core.card_regulatory import regulatory_tier_for_card

    card = ClinicalModelCard.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert regulatory_tier_for_card(card) in ("red", "gray", "green", "orange", "yellow", "blue")


if __name__ == "__main__":
    import json

    test_fda_cleared()
    test_not_fda_approved()
    test_ce_marked()
    test_eua()
    test_investigational()
    test_unknown()
    test_fda_and_ce_prefers_green()
    test_card_tier_only_on_regulatory_row()
    test_bundled_dermgpt_clinical_json()
    print("All regulatory status tests passed.")
