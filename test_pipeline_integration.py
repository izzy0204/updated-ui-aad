"""Offline pipeline integration tests (mocked agent, no network)."""

from __future__ import annotations

import sys
from dataclasses import fields as dc_fields
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import ClinicalModelCard, Performance, TrainingData
from pipelines.cardgen_pipeline import (
    CardGenPipeline,
    _collect_empty_clinical_fields,
    _is_clinical_field_filled,
)
from pipelines.clinical_card_mapper import _map_agent_dump_to_card, apply_nested_postfill


NESTED_AGENT = {
    "model_name": "NestedModel",
    "summary": "Supports triage. Outputs risk scores. Clinician oversight required.",
    "medical_purpose": "Lesion triage support.",
    "acceptable_input": "Dermoscopic images.",
    "output": "Risk category.",
    "role_in_decision_making": "Adjunct only.",
    "intended_users": "Physicians.",
    "target_patient_population": "Adults.",
    "known_failure_modes": "Rare subtypes.",
    "unsupported_clinical_scenarios": "Pediatric screening.",
    "unsupported_use_cases": "Self-diagnosis.",
    "required_clinician_oversight": "Required.",
    "model_type": "CNN.",
    "training_data": {
        "description": "12k labeled images.",
        "dataset_url": "https://example.com/data",
    },
    "model_development_and_validation": {
        "description": "Three-site validation.",
        "publication_url": "https://example.com/pub",
    },
    "clinical_trial": {
        "identifier": "NCT999",
        "url": "https://clinicaltrials.gov/study/NCT999",
        "description": "Prospective study.",
    },
    "performance": {
        "summary": "Sensitivity 91%.",
        "metrics": [
            {
                "name": "Sensitivity",
                "value": "91%",
                "population": "n=200",
                "confidence_interval": "86-95%",
            }
        ],
    },
    "contact": {"email": "a@b.com", "url": "https://example.com/contact"},
}

FLAT_LEGACY = {
    "model_name": "FlatModel",
    "summary": "Legacy flat extraction.",
    "medical_purpose": "From intended_use_and_workflow field.",
    "intended_use_and_workflow": "Workflow prose.",
    "acceptable_input": "Images.",
    "output": "Label.",
    "role_in_decision_making": "Support.",
    "intended_users": "Clinicians.",
    "target_patient_population": "Adults.",
    "known_failure_modes": "Limits.",
    "unsupported_clinical_scenarios": "Pediatrics.",
    "unsupported_use_cases": "Consumer.",
    "required_clinician_oversight": "Yes.",
    "model_type": "MLP.",
    "training_data": "Flat training prose.",
    "validation_test_dataset": "Flat validation prose.",
    "usefulness_efficacy_result": "Sensitivity 88%.",
}


@pytest.mark.unit
def test_mock_nested_agent_round_trip_types():
    card = _map_agent_dump_to_card(NESTED_AGENT, user_model_name="NestedModel")
    assert isinstance(card.training_data, TrainingData)
    assert card.training_data.dataset_url == "https://example.com/data"
    assert isinstance(card.performance, Performance)
    assert len(card.performance.metrics) == 1
    assert card.performance.metrics[0].value == "91%"
    assert card.clinical_trial and card.clinical_trial.identifier == "NCT999"
    assert card.contact.email == "a@b.com"


@pytest.mark.unit
def test_mock_flat_legacy_agent_fallback():
    card = _map_agent_dump_to_card(FLAT_LEGACY, user_model_name="FlatModel")
    assert "Flat training prose" in card.training_data.description
    assert card.model_development_and_validation.description
    assert "88%" in card.performance.summary or card.performance.metrics


@pytest.mark.unit
def test_collect_empty_detects_nested_gaps():
    card = ClinicalModelCard(
        model_name="X",
        developer="D",
        version="1",
        last_updated="2026-01-01",
        summary="One.",
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
    empty = _collect_empty_clinical_fields(card)
    assert "training_data.description" in empty
    assert "performance.summary" in empty
    assert "contact.url" in empty


@pytest.mark.unit
def test_postfill_does_not_stringify_nested_objects():
    card = ClinicalModelCard(
        model_name="X",
        developer="D",
        version="1",
        last_updated="2026-01-01",
        summary="One.",
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
    apply_nested_postfill(card, "training_data.description", "Filled description.")
    assert isinstance(card.training_data, TrainingData)
    assert card.training_data.description == "Filled description."
    assert not isinstance(card.training_data, str)


@pytest.mark.unit
def test_is_clinical_field_filled_nested():
    card = _map_agent_dump_to_card(NESTED_AGENT, user_model_name="NestedModel")
    assert _is_clinical_field_filled(card, "training_data")
    assert _is_clinical_field_filled(card, "performance")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_generate_model_card_mocked_agent():
  async def fake_gemini(*args, **kwargs):
      return NESTED_AGENT, {"summary": [{"url": "https://example.com", "snippet": "Evidence."}]}

  with patch("pipelines.cardgen_pipeline.gemini_run_async", new=AsyncMock(side_effect=fake_gemini)):
      with patch.object(CardGenPipeline, "discover_model_sources", new=AsyncMock(return_value={"web_search": {"discovered": [], "top_urls": []}})):
          pipe = CardGenPipeline(out_dir=REPO / ".tmp_test_out", use_web_discovery=False)
          card, sources, content = await pipe.generate_model_card(
              model_name="NestedModel",
              developer_name="Dev",
              application_url="https://example.com",
              write_files=False,
              iters=1,
          )
  assert isinstance(card, ClinicalModelCard)
  assert card.training_data.description
  assert not isinstance(card.training_data, str)
