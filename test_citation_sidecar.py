"""Tests for citation sidecar span building."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import ClinicalModelCard
from core.citation_sidecar import align_snippet_to_field_text, build_sidecar_from_evidence, merge_citation_sidecars


def _card() -> ClinicalModelCard:
    return ClinicalModelCard(
        model_name="T",
        developer="D",
        version="1",
        last_updated="2026-01-01",
        summary="Validated on cohort A. Sensitivity was 92%.",
        medical_purpose="P",
        acceptable_input="I",
        output="O",
        role_in_decision_making="R",
        intended_users="U",
        target_patient_population="T",
        known_performance_limitations="K S U2",
        required_clinician_oversight="C",
        model_type="M",
        performance_evaluation_limitations="L",
    )


@pytest.mark.unit
def test_align_snippet_exact():
    assert align_snippet_to_field_text("Reported 92% sensitivity.", "92% sensitivity") == (9, 24)


@pytest.mark.unit
def test_build_sidecar_exact_span():
    card = _card()
    evidence = {
        "summary": [{"url": "https://example.com/a", "snippet": "Sensitivity was 92%."}],
    }
    sidecar = build_sidecar_from_evidence(card, evidence)
    assert sidecar["references"]["1"]["url"] == "https://example.com/a"
    spans = sidecar["field_citations"]["summary"]
    assert spans[0]["text"] == "Sensitivity was 92%."
    assert spans[0]["citationIds"] == ["1"]


@pytest.mark.unit
def test_build_sidecar_sentence_level_fallback():
    card = _card()
    evidence = {
        "summary": [{"url": "https://example.com/b", "snippet": "nonmatching snippet xyz"}],
    }
    sidecar = build_sidecar_from_evidence(card, evidence)
    spans = sidecar["field_citations"]["summary"]
    assert spans[0].get("sentence_level") is True
    assert "snippet_mismatch:summary" in sidecar["_alignment_warnings"]


@pytest.mark.unit
def test_merge_preserves_legacy_fields():
    base = {"fields": {"summary": [{"url": "https://legacy"}]}}
    built = build_sidecar_from_evidence(
        _card(),
        {"summary": [{"url": "https://example.com/a", "snippet": "Sensitivity was 92%."}]},
    )
    merged = merge_citation_sidecars(base, built)
    assert merged.get("fields")
    assert merged.get("field_citations")
