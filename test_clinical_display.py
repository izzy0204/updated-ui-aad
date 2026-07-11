"""Tests for shared clinical display helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import ClinicalModelCard
from core.clinical_display import (
    field_value_for_display,
    iter_display_sections,
    performance_metrics_rows,
    regulatory_status_badge_md,
    terminal_card_lines,
)

FIXTURE = REPO / "tests" / "fixtures" / "clinical_card_full.json"


@pytest.mark.unit
def test_iter_display_sections_matches_fixture():
    card = ClinicalModelCard.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
    sections = list(iter_display_sections(card))
    section_titles = [s[0] for s in sections]
    assert section_titles[0] == "1) Metadata"
    assert "Clinical Trial" in [s[2] for s in sections]
    assert "[Dataset]" in field_value_for_display(card, "training_data")


@pytest.mark.unit
def test_performance_metrics_rows():
    card = ClinicalModelCard.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
    rows = performance_metrics_rows(card)
    assert len(rows) == 2
    assert rows[0]["Metric"] == "Sensitivity"
    assert rows[0]["Value"] == "94%"


@pytest.mark.unit
def test_regulatory_badge_contains_tier_color():
    card = ClinicalModelCard.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
    badge = regulatory_status_badge_md(card.regulatory_approval_status)
    assert "FDA Cleared" in badge
    assert "background-color" in badge


@pytest.mark.unit
def test_terminal_lines_cover_six_sections():
    card = ClinicalModelCard.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
    lines = terminal_card_lines(card)
    joined = "\n".join(lines)
    for marker in (
        "1) Metadata",
        "2) Summary",
        "3) Intended Use",
        "4) Risks and Limitations",
        "5) Mechanism and Development",
        "6) Governance and Monitoring",
    ):
        assert marker in joined
    assert "Performance Metrics:" in joined
