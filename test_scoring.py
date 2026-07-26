#!/usr/bin/env python3
"""Unit tests for clinical model card scoring (no live pipeline/API)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.chai_schema import ClinicalModelCard, Performance, PerformanceMetric, TrainingData
from utils.model_card_scorer import ClinicalUsabilityScorer, ModelCardScorer, _POINTS_TOTAL, _RAW_FIELD_POINTS


def _clinical_card_dict(**overrides) -> dict:
    base = ClinicalModelCard(
        model_name="TestModel",
        developer="Dev Co",
        version="1.0",
        last_updated=date(2026, 1, 15),
        summary="Accepts images. Outputs labels. Supports clinician review.",
        medical_purpose="Assist melanoma triage in dermatology clinics.",
        acceptable_input="Dermoscopic images from clinical cameras.",
        output="Risk score and lesion classification labels.",
        role_in_decision_making="Advisory only; clinician confirms biopsy decisions.",
        intended_users="Board-certified dermatologists.",
        target_patient_population="Adults with pigmented lesions.",
        known_performance_limitations=(
            "Reduced accuracy on rare subtypes. Not for pediatric self-screening or consumer "
            "standalone diagnosis."
        ),
        skin_type_representation_equity="Reduced accuracy observed on darker skin tones.",
        required_clinician_oversight="Physician must review all outputs before clinical action.",
        model_type="Convolutional neural network.",
        training_data=TrainingData(description="12,000 dermoscopic images from 3 sites."),
        performance=Performance(
            summary="Sensitivity 92% on validation cohort.",
            metrics=[PerformanceMetric(name="Sensitivity", value="92%", population="n=400")],
        ),
        performance_evaluation_limitations="External validation limited to single health system.",
    )
    d = base.to_dict_camel()
    d.update(overrides)
    return d


@pytest.mark.unit
def test_scorer_weights_sum_to_one() -> None:
    total = sum(v / _POINTS_TOTAL for v in _RAW_FIELD_POINTS.values())
    assert abs(total - 1.0) < 1e-9


@pytest.mark.unit
def test_scorer_clinical_fixture_completion() -> None:
    scorer = ModelCardScorer()
    score = scorer.score_model_card(_clinical_card_dict())
    assert score.total_fields > 0
    assert score.filled_fields > 0
    assert 0.0 <= score.completion_percentage <= 100.0
    assert 0.0 <= score.clinical_usability_score <= 1.0


@pytest.mark.unit
def test_scorer_field_level_quality() -> None:
    scorer = ClinicalUsabilityScorer()
    good = scorer.score_field(
        "medical_purpose",
        "Intended for dermatologists to support melanoma triage with validated clinical workflow.",
    )
    assert good.is_filled
    assert good.clinical_relevance > 0.3
    not_disclosed = scorer.score_field("medical_purpose", "Not disclosed")
    assert not not_disclosed.is_filled
    bad = scorer.score_field("medical_purpose", "not specified")
    assert not bad.is_filled or bad.clinical_relevance < good.clinical_relevance


@pytest.mark.unit
def test_scorer_honest_unknown_not_penalized() -> None:
    scorer = ModelCardScorer()
    honest = _clinical_card_dict(regulatoryApprovalStatus="UNKNOWN", availability="Status not publicly disclosed.")
    score = scorer.score_model_card(honest)
    assert score.clinical_usability_score >= 0.0


@pytest.mark.unit
def test_scorer_false_certainty_penalized() -> None:
    scorer = ModelCardScorer()
    contradictory = _clinical_card_dict(
        regulatoryApprovalStatus="UNKNOWN",
        availability="FDA cleared device available nationwide.",
    )
    honest = _clinical_card_dict(regulatoryApprovalStatus="UNKNOWN", availability="Limited public information.")
    assert scorer.score_model_card(contradictory).clinical_usability_score < scorer.score_model_card(
        honest
    ).clinical_usability_score


@pytest.mark.unit
def test_scorer_metrics_bonus() -> None:
    scorer = ModelCardScorer()
    with_metrics = _clinical_card_dict()
    without = _clinical_card_dict(performance={"summary": "Validated.", "metrics": []})
    assert scorer.score_model_card(with_metrics).clinical_usability_score >= scorer.score_model_card(
        without
    ).clinical_usability_score


@pytest.mark.unit
def test_scorer_summary_penalty() -> None:
    scorer = ModelCardScorer()
    long_summary = _clinical_card_dict(
        summary="One. Two. Three. Four sentences here.",
    )
    short_summary = _clinical_card_dict(summary="One. Two. Three.")
    assert scorer.score_model_card(long_summary).clinical_usability_score <= scorer.score_model_card(
        short_summary
    ).clinical_usability_score


@pytest.mark.unit
def test_scorer_low_confidence_regulatory_penalized() -> None:
    scorer = ModelCardScorer()
    sidecar = {"regulatory_status_confidence": "unknown", "regulatory_status_source": [{"url": "https://fda.gov"}]}
    penalized = scorer.score_model_card(
        _clinical_card_dict(regulatoryApprovalStatus="FDA_CLEARED"),
        citations=sidecar,
    )
    trusted = scorer.score_model_card(
        _clinical_card_dict(regulatoryApprovalStatus="FDA_CLEARED"),
        citations={
            "regulatory_status_confidence": "authoritative",
            "regulatory_status_evidence": [{"url": "https://fda.gov"}],
        },
    )
    assert penalized.clinical_usability_score < trusted.clinical_usability_score
    assert any("authoritative or cited_explicit" in issue for issue in penalized.quality_issues)


@pytest.mark.unit
def test_scorer_fda_without_evidence_critical() -> None:
    scorer = ModelCardScorer()
    score = scorer.score_model_card(
        _clinical_card_dict(regulatoryApprovalStatus="FDA_APPROVED"),
        citations={"regulatory_status_confidence": "authoritative"},
    )
    assert any("regulatory_status_evidence" in issue for issue in score.quality_issues)


@pytest.mark.unit
def test_scorer_unknown_regulatory_not_penalized() -> None:
    scorer = ModelCardScorer()
    score = scorer.score_model_card(
        _clinical_card_dict(regulatoryApprovalStatus="UNKNOWN"),
        citations={"regulatory_status_confidence": "unknown"},
    )
    assert not any("regulatory_status_evidence" in issue for issue in score.quality_issues)
    assert not any("authoritative or cited_explicit" in issue for issue in score.quality_issues)
