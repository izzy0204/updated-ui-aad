"""Tests for clinical model card schema v1.0."""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.chai_schema import (
    SCHEMA_VERSION,
    ClinicalModelCard,
    Performance,
    PerformanceMetric,
    RegulatoryApprovalStatus,
    TrainingData,
    validate_model_card,
)
from core.card_regulatory import tier_for_regulatory_status
from core.clinical_regulatory import conservative_text_to_status
from utils.sentence_utils import count_sentences


def test_schema_round_trip_camel_case():
    card = ClinicalModelCard(
        model_name="TestModel",
        developer="DevCo",
        version="1.0",
        last_updated=date(2026, 1, 15),
        summary="Accepts dermoscopic images. Outputs risk score. Supports clinician review.",
        medical_purpose="Assist melanoma detection.",
        acceptable_input="Dermoscopic images.",
        output="Risk score.",
        role_in_decision_making="Advisory only.",
        intended_users="Dermatologists.",
        target_patient_population="Adults.",
        known_failure_modes="Dark skin underrepresented.",
        unsupported_clinical_scenarios="Non-pigmented lesions.",
        unsupported_use_cases="Pediatric self-use.",
        required_clinician_oversight="Physician confirms biopsy decision.",
        model_type="CNN",
        training_data=TrainingData(description="10k images"),
        performance=Performance(summary="Sensitivity 92%", metrics=[PerformanceMetric(name="Sensitivity", value="92%")]),
        performance_evaluation_limitations="Small validation cohort.",
    )
    raw = card.to_dict_camel()
    assert raw["schemaVersion"] == SCHEMA_VERSION
    assert raw["modelName"] == "TestModel"
    restored = ClinicalModelCard.from_dict(raw)
    assert restored.model_name == "TestModel"
    assert restored.regulatory_approval_status == RegulatoryApprovalStatus.UNKNOWN


def test_regulatory_enum_tier_mapping():
    assert tier_for_regulatory_status(RegulatoryApprovalStatus.FDA_CLEARED) == "green"
    assert tier_for_regulatory_status(RegulatoryApprovalStatus.UNKNOWN) == "gray"


def test_conservative_regulatory_mapping():
    assert conservative_text_to_status("FDA 510(k) cleared") == RegulatoryApprovalStatus.FDA_CLEARED
    assert conservative_text_to_status("FDA-grade accuracy") == RegulatoryApprovalStatus.UNKNOWN


def test_sentence_count_abbreviations():
    text = "Trained in the U.S. Achieves 95.5% sensitivity. Used as advisory tool."
    assert count_sentences(text) == 3


def test_validate_summary_warning():
    card = ClinicalModelCard(
        model_name="M",
        developer="D",
        version="1",
        last_updated=date.today(),
        summary="One. Two. Three. Four.",
        medical_purpose="p",
        acceptable_input="i",
        output="o",
        role_in_decision_making="r",
        intended_users="u",
        target_patient_population="t",
        known_failure_modes="k",
        unsupported_clinical_scenarios="s",
        unsupported_use_cases="u",
        required_clinician_oversight="o",
        model_type="CNN",
        training_data=TrainingData(description="data"),
        performance=Performance(summary="perf"),
        performance_evaluation_limitations="lim",
        contact=__import__("core.chai_schema", fromlist=["Contact"]).Contact(url="http://example.com"),
    )
    result = validate_model_card(card)
    assert "summary_exceeds_three_sentences" in result.warnings
