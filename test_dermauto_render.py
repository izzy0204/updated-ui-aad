"""Golden HTML tests for DermAUTO clinical card rendering."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import (
    ClinicalModelCard,
    ClinicalTrial,
    Contact,
    ModelDevelopmentValidation,
    Performance,
    PerformanceMetric,
    RegulatoryApprovalStatus,
    TrainingData,
)
from core.dermauto_card_render import (
    REGULATORY_LEGEND,
    card_to_sections,
    format_clinical_trial,
    format_contact,
    format_development,
    format_training_data,
    regulatory_tooltip_html,
    render_doc_title_html,
    render_from_card,
    render_full_card_html,
)

FIXTURES = REPO / "tests" / "fixtures"


def _load_fixture_card() -> ClinicalModelCard:
    data = json.loads((FIXTURES / "clinical_card_full.json").read_text(encoding="utf-8"))
    return ClinicalModelCard.from_dict(data)


def _load_fixture_citations() -> dict:
    return json.loads((FIXTURES / "clinical_card_full.citations.json").read_text(encoding="utf-8"))


@pytest.mark.unit
def test_fixture_renders_linked_title():
    card = _load_fixture_card()
    html = render_from_card(card, source_label="fixture", citations=_load_fixture_citations())
    assert 'href="https://example.com/dermtest"' in html
    assert "DermTest Pro" in html
    assert render_doc_title_html("DermTest Pro", None) == "DermTest Pro"


@pytest.mark.unit
def test_fixture_renders_training_dataset_link():
    card = _load_fixture_card()
    html = render_from_card(card, source_label="fixture", citations=_load_fixture_citations())
    assert "Multicenter dermoscopy archive" in html
    assert 'href="https://example.com/datasets/derm-archive"' in html
    assert "Dataset" in html


@pytest.mark.unit
def test_fixture_renders_publication_link():
    card = _load_fixture_card()
    html = render_from_card(card, source_label="fixture", citations=_load_fixture_citations())
    assert "Prospective validation across three sites" in html
    assert 'href="https://example.com/pub/dermtest-validation"' in html
    assert "Publication" in html


@pytest.mark.unit
def test_fixture_renders_clinical_trial_links():
    card = _load_fixture_card()
    html = render_from_card(card, source_label="fixture", citations=_load_fixture_citations())
    assert "NCT01234567" in html
    assert 'href="https://clinicaltrials.gov/study/NCT01234567"' in html
    assert "Multicenter prospective study" in html


@pytest.mark.unit
def test_fixture_renders_contact_mailto_and_url():
    card = _load_fixture_card()
    html = render_from_card(card, source_label="fixture", citations=_load_fixture_citations())
    assert 'href="mailto:support@example.com"' in html
    assert "support@example.com" in html
    assert 'href="https://example.com/contact"' in html


@pytest.mark.unit
def test_fixture_renders_performance_metrics_table():
    card = _load_fixture_card()
    html = render_from_card(card, source_label="fixture", citations=_load_fixture_citations())
    assert "Performance Metrics" in html
    assert "<table" in html
    assert "Sensitivity" in html
    assert "94%" in html
    assert "Pivotal cohort" in html
    assert "90–97%" in html
    assert "Specificity" in html


@pytest.mark.unit
def test_empty_optional_nested_fields_omitted():
    card = ClinicalModelCard(
        model_name="Minimal",
        developer="Dev",
        regulatory_approval_status=RegulatoryApprovalStatus.UNKNOWN,
        version="1",
        last_updated="2026-01-01",
        summary="One sentence only.",
        medical_purpose="Purpose.",
        acceptable_input="Input.",
        output="Output.",
        role_in_decision_making="Support.",
        intended_users="Clinicians.",
        target_patient_population="Adults.",
        known_performance_limitations="None listed.",
        required_clinician_oversight="Required.",
        model_type="Classifier.",
        training_data=TrainingData(),
        model_development_and_validation=ModelDevelopmentValidation(),
        clinical_trial=ClinicalTrial(),
        performance=Performance(summary="Not disclosed.", metrics=[]),
        performance_evaluation_limitations="Unknown.",
        contact=Contact(),
    )
    sections = card_to_sections(card)
    assert "Clinical Trial" not in sections["5) Mechanism and Development"]
    html = render_from_card(card, source_label="minimal")
    assert "Performance Metrics" not in html
    assert format_clinical_trial(ClinicalTrial()) is None


@pytest.mark.unit
def test_regulatory_color_only_on_status_row():
    card = _load_fixture_card()
    html = render_from_card(card, source_label="fixture", citations=_load_fixture_citations())
    assert "Regulatory Approval Status" in html
    assert "FDA Cleared" in html
    status_value_idx = html.index("FDA Cleared")
    status_chunk = html[max(0, status_value_idx - 500) : status_value_idx + 100]
    summary_idx = html.index("Assists clinicians in lesion triage")
    summary_chunk = html[summary_idx : summary_idx + 400]
    assert "background-color:#d8f3dc" in status_chunk or "border-left:4px solid #2d6a4f" in status_chunk
    assert "background-color:#d8f3dc" not in summary_chunk


@pytest.mark.unit
def test_regulatory_tooltip_is_click_to_reveal_not_hover():
    """The legend must be a <details> disclosure (click to reveal), not a hover title= tooltip."""
    card = _load_fixture_card()
    html = render_from_card(card, source_label="fixture", citations=_load_fixture_citations())
    status_idx = html.index("Regulatory Approval Status")
    chunk = html[status_idx : status_idx + 3000]
    assert "<details" in chunk
    assert "<summary" in chunk
    for _tier, label in REGULATORY_LEGEND:
        assert label in chunk
    assert 'title="Not Authorized' not in chunk


@pytest.mark.unit
def test_regulatory_tooltip_html_helper_contains_full_legend():
    tooltip = regulatory_tooltip_html()
    assert tooltip.startswith("<details")
    assert "<summary" in tooltip
    assert ">?</summary>" in tooltip
    for _tier, label in REGULATORY_LEGEND:
        assert label in tooltip


@pytest.mark.unit
def test_html_escaping_in_nested_fields():
    td = TrainingData(description='Uses <script>alert("x")</script> data.', dataset_url=None)
    escaped_html = render_full_card_html(
        sections={"5) x": {"Training Data": format_training_data(td)}},
        refs={},
        doc_title="Safe",
        source_label="test",
        hide_citations=True,
        manual_linkify=True,
    )
    assert "<script>" not in escaped_html
    assert "&lt;script&gt;" in escaped_html


@pytest.mark.unit
def test_format_helpers_plain_text():
    assert "[Dataset](https://x.com)" in format_training_data(
        TrainingData(description="Desc.", dataset_url="https://x.com")
    )
    assert "[Publication](https://pub)" in format_development(
        ModelDevelopmentValidation(description="Dev.", publication_url="https://pub")
    )
    assert "mailto:support@test" in format_contact(Contact(email="support@test", url=None))
    ct = format_clinical_trial(
        ClinicalTrial(identifier="NCT1", url="https://trials.example/nct1", description="Phase 3.")
    )
    assert ct and "NCT1" in ct and "[Trial]" in ct
