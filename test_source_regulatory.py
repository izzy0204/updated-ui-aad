#!/usr/bin/env python3
"""Tests for source-based regulatory tier assignment."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.chai_schema import ClinicalModelCard, RegulatoryApprovalStatus
from core.source_regulatory import (
    compute_regulatory_tiers_for_card,
    infer_source_type,
    regulatory_tier_for_field,
    tier_from_citation_item,
)


@pytest.mark.unit
def test_fda_url_is_green() -> None:
    assert infer_source_type("https://www.fda.gov/medical-devices") == "fda_approval"
    assert tier_from_citation_item(
        {"url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm", "snippet": ""}
    ) == "green"


@pytest.mark.unit
def test_clinicaltrials_is_orange() -> None:
    assert infer_source_type("https://clinicaltrials.gov/study/NCT123") == "clinical_trial"
    assert tier_from_citation_item(
        {"url": "https://clinicaltrials.gov/study/NCT123", "snippet": "Phase II study"}
    ) == "orange"


@pytest.mark.unit
def test_per_field_tiers_from_citations() -> None:
    card = ClinicalModelCard(
        model_name="Test",
        developer="Dev",
        version="1.0",
        regulatory_approval_status=RegulatoryApprovalStatus.FDA_CLEARED,
        summary="General overview.",
        medical_purpose="Assist clinicians.",
        acceptable_input="Images.",
        output="Labels.",
        role_in_decision_making="Advisory.",
        intended_users="Dermatologists.",
        target_patient_population="Adults.",
        known_performance_limitations="Rare errors. Not for pediatric or consumer use.",
        required_clinician_oversight="Required.",
        model_type="CNN.",
        performance_evaluation_limitations="Small cohort.",
    )
    citations = {
        "regulatory_approval_status": [
            {"url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm", "snippet": "De Novo"}
        ],
        "summary": [
            {"url": "https://example.com/product", "snippet": "Product marketing page"}
        ],
    }
    by_field, by_comp = compute_regulatory_tiers_for_card(card, citations)
    assert by_field["regulatory_approval_status"] == "green"
    assert by_field["summary"] == "gray"
    assert "1) Metadata|||Regulatory Approval Status" in by_comp
