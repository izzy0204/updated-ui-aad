"""Tests for clinical model card schema v2.0."""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.chai_schema import (
    SCHEMA_VERSION,
    ClinicalModelCard,
    ClinicalTrial,
    Contact,
    ModelDevelopmentValidation,
    Performance,
    PerformanceMetric,
    RegulatoryApprovalStatus,
    TrainingData,
    validate_model_card,
)
from core.card_regulatory import tier_for_regulatory_status
from core.clinical_regulatory import conservative_text_to_status
from core.dermauto_card_render import card_to_sections
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
        known_performance_limitations="Not for non-pigmented lesions or pediatric self-use.",
        skin_type_representation_equity="Dark skin underrepresented.",
        required_clinician_oversight="Physician confirms biopsy decision.",
        model_type="CNN",
        training_data=TrainingData(description="10k images"),
        performance=Performance(summary="Sensitivity 92%", metrics=[PerformanceMetric(name="Sensitivity", value="92%")]),
        performance_evaluation_limitations="Small validation cohort.",
    )
    raw = card.to_dict_camel()
    assert raw["schemaVersion"] == SCHEMA_VERSION
    assert SCHEMA_VERSION == "clinical-model-card-2.0"
    assert raw["modelName"] == "TestModel"
    assert raw["knownPerformanceLimitations"] == "Not for non-pigmented lesions or pediatric self-use."
    assert raw["skinTypeRepresentationEquity"] == "Dark skin underrepresented."
    assert "unsupportedClinicalScenarios" not in raw
    assert "unsupportedUseCases" not in raw
    restored = ClinicalModelCard.from_dict(raw)
    assert restored.model_name == "TestModel"
    assert restored.known_performance_limitations == card.known_performance_limitations
    assert restored.skin_type_representation_equity == card.skin_type_representation_equity
    assert restored.regulatory_approval_status == RegulatoryApprovalStatus.UNKNOWN


def test_validate_requires_known_performance_limitations_not_equity():
    card = ClinicalModelCard(
        model_name="M",
        developer="D",
        version="1",
        last_updated=date.today(),
        summary="One sentence.",
        medical_purpose="p",
        acceptable_input="i",
        output="o",
        role_in_decision_making="r",
        intended_users="u",
        target_patient_population="t",
        required_clinician_oversight="o",
        model_type="CNN",
        training_data=TrainingData(description="data"),
        performance=Performance(summary="perf"),
        performance_evaluation_limitations="lim",
    )
    result = validate_model_card(card)
    assert "missing_required:known_performance_limitations" in result.errors
    assert "missing_required:skin_type_representation_equity" not in result.errors


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
        known_performance_limitations="k s u",
        required_clinician_oversight="o",
        model_type="CNN",
        training_data=TrainingData(description="data"),
        performance=Performance(summary="perf"),
        performance_evaluation_limitations="lim",
        contact=__import__("core.chai_schema", fromlist=["Contact"]).Contact(url="http://example.com"),
    )
    result = validate_model_card(card)
    assert "summary_exceeds_three_sentences" in result.warnings


def _minimal_card(**overrides) -> ClinicalModelCard:
    base = dict(
        model_name="M",
        developer="D",
        version="1",
        last_updated=date.today(),
        summary="s",
        medical_purpose="p",
        acceptable_input="i",
        output="o",
        role_in_decision_making="r",
        intended_users="u",
        target_patient_population="t",
        known_performance_limitations="k",
        required_clinician_oversight="o",
        model_type="CNN",
        training_data=TrainingData(description="data"),
        performance=Performance(summary="perf"),
        performance_evaluation_limitations="lim",
    )
    base.update(overrides)
    return ClinicalModelCard(**base)


def test_whole_value_not_found_synonyms_normalize_to_empty():
    for placeholder in ("Not specified", "Not specified.", "N/A", "n/a", "TBD", "Unknown", "None", "not disclosed"):
        card = _minimal_card(model_type=placeholder, availability=placeholder)
        assert card.model_type == ""
        assert card.availability is None


def test_hybrid_sentence_with_real_content_is_not_touched():
    card = _minimal_card(
        version="Not specified; described as a dermatology-focused language model.",
        target_patient_population="Not specified; tool is primarily provider-facing.",
    )
    assert card.version == "Not specified; described as a dermatology-focused language model."
    assert card.target_patient_population == "Not specified; tool is primarily provider-facing."


def test_nested_field_not_found_synonyms_normalize():
    card = _minimal_card(
        training_data=TrainingData(description="Not specified.", dataset_url="N/A"),
        model_development_and_validation=ModelDevelopmentValidation(
            description="Not specified", publication_url="TBD"
        ),
        clinical_trial=ClinicalTrial(identifier="Unknown", url="N/A", description="Not disclosed"),
        performance=Performance(summary="Not specified."),
        contact=Contact(email="Not specified", url="N/A"),
    )
    assert card.training_data.description == ""
    assert card.training_data.dataset_url is None
    assert card.model_development_and_validation.description is None
    assert card.model_development_and_validation.publication_url is None
    assert card.clinical_trial.identifier is None
    assert card.clinical_trial.url is None
    assert card.clinical_trial.description is None
    assert card.performance.summary == ""
    assert card.contact.email is None
    assert card.contact.url is None


def test_empty_required_fields_render_not_disclosed_in_markdown():
    card = _minimal_card(model_type="Not specified", performance_evaluation_limitations="N/A")
    md = card.to_markdown()
    assert "**Model Type:** Not disclosed" in md
    assert "**Limitations in Evaluating Performance:** Not disclosed" in md


def test_empty_required_fields_render_not_disclosed_in_sections():
    card = _minimal_card(medical_purpose="Not specified", model_type="TBD")
    sections = card_to_sections(card)
    assert sections["3) Intended Use"]["Medical Purpose"] == "Not disclosed"
    assert sections["5) Mechanism and Development"]["Model Type"] == "Not disclosed"
