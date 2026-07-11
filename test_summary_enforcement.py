"""Summary length enforcement tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import ClinicalModelCard
from pipelines.clinical_card_mapper import enforce_summary_length


def _card(summary: str) -> ClinicalModelCard:
    return ClinicalModelCard(
        model_name="T",
        developer="D",
        version="1",
        last_updated="2026-01-01",
        summary=summary,
        medical_purpose="P",
        acceptable_input="I",
        output="O",
        role_in_decision_making="R",
        intended_users="U",
        target_patient_population="T",
        known_failure_modes="K",
        unsupported_clinical_scenarios="S",
        unsupported_use_cases="U2",
        required_clinician_oversight="C",
        model_type="M",
        performance_evaluation_limitations="L",
    )


LONG = (
    "First sentence about input. Second sentence about output. "
    "Third sentence about role. Fourth sentence should trigger warning."
)


@pytest.mark.unit
def test_summary_within_limit_unchanged():
    card = _card("One. Two. Three.")
    out, warnings = enforce_summary_length(card)
    assert out.summary == "One. Two. Three."
    assert warnings == []


@pytest.mark.unit
def test_summary_rewrite_callback_used(monkeypatch):
    from pipelines.cardgen_pipeline import CardGenPipeline

    pipeline = CardGenPipeline(out_dir=REPO / ".pytest_tmp")
    assert callable(pipeline._rewrite_summary_callback)

    def fake_rewrite(_: str) -> str:
        return "Short one. Two. Three."

    monkeypatch.setattr(pipeline, "_gemini_rewrite_summary", fake_rewrite)
    pipeline._rewrite_summary_callback = pipeline._gemini_rewrite_summary
    card = _card(LONG)
    out, warnings = enforce_summary_length(card, rewrite_callback=pipeline._rewrite_summary_callback)
    assert out.summary == "Short one. Two. Three."
    assert "summary_exceeds_three_sentences" not in warnings


@pytest.mark.unit
def test_no_callback_warns_preserves_original():
    card = _card(LONG)
    out, warnings = enforce_summary_length(card)
    assert out.summary == LONG
    assert "summary_exceeds_three_sentences" in warnings


@pytest.mark.unit
def test_callback_success_replaces_summary():
    card = _card(LONG)

    def rewrite(_: str) -> str:
        return "Short one. Two. Three."

    out, warnings = enforce_summary_length(card, rewrite_callback=rewrite)
    assert out.summary == "Short one. Two. Three."
    assert "summary_exceeds_three_sentences" not in warnings


@pytest.mark.unit
def test_callback_still_too_long_keeps_original():
    card = _card(LONG)

    def rewrite(_: str) -> str:
        return LONG + " Fifth."

    out, warnings = enforce_summary_length(card, rewrite_callback=rewrite)
    assert out.summary == LONG
    assert "summary_exceeds_three_sentences" in warnings
    assert "summary_rewrite_still_too_long" in warnings


@pytest.mark.unit
def test_no_truncation_path_exists():
    card = _card(LONG)
    before = card.summary
    enforce_summary_length(card)
    assert card.summary == before
    assert len(card.summary) == len(before)
