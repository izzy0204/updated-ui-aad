"""Tests for the clinical-model-card-1.0 -> 2.0 migration script (offline)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
MIGRATE_SCRIPT = REPO / "scripts" / "migrate_v1_to_v2.py"

sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import SCHEMA_VERSION  # noqa: E402


def _load_migrate():
    spec = importlib.util.spec_from_file_location("migrate_v1_to_v2", MIGRATE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _v1_card_dict(**overrides) -> dict:
    base = {
        "schemaVersion": "clinical-model-card-1.0",
        "modelName": "TestModel",
        "developer": "DevCo",
        "regulatoryApprovalStatus": "UNKNOWN",
        "version": "1.0",
        "lastUpdated": "2026-01-15",
        "summary": "Assists clinicians. Outputs a risk score. Advisory only.",
        "medicalPurpose": "Assist melanoma triage.",
        "acceptableInput": "Dermoscopic images.",
        "output": "Risk score.",
        "roleInDecisionMaking": "Advisory only.",
        "intendedUsers": "Dermatologists.",
        "targetPatientPopulation": "Adults.",
        "knownFailureModes": (
            "May underperform on rare subtypes. "
            "Less data is available for darker skin tones per Fitzpatrick phototype."
        ),
        "unsupportedClinicalScenarios": "Not tested on pediatric patients.",
        "unsupportedUseCases": "Not a standalone diagnostic device.",
        "requiredClinicianOversight": "Physician confirms biopsy decision.",
        "modelType": "CNN",
        "trainingData": {"description": "10k images", "datasetUrl": None},
        "performance": {"summary": "Sensitivity 92%.", "metrics": []},
        "performanceEvaluationLimitations": "Small validation cohort.",
        "contact": {"email": "test@example.com", "url": None},
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_migrate_card_merges_unsupported_into_known_performance_limitations():
    mod = _load_migrate()
    card, report = mod.migrate_card(_v1_card_dict())
    assert card.schema_version == SCHEMA_VERSION
    assert "Not tested on pediatric patients." in card.known_performance_limitations
    assert "Not a standalone diagnostic device." in card.known_performance_limitations
    assert report["schemaVersionTo"] == SCHEMA_VERSION


@pytest.mark.unit
def test_migrate_card_extracts_equity_sentence():
    mod = _load_migrate()
    card, report = mod.migrate_card(_v1_card_dict())
    assert "darker skin tones" in card.skin_type_representation_equity.lower()
    assert "darker skin tones" not in card.known_performance_limitations.lower()
    assert report["equitySentencesExtracted"] >= 1
    assert report["lowConfidenceEquityExtraction"] is False


@pytest.mark.unit
def test_migrate_card_no_equity_content_flagged_low_confidence():
    mod = _load_migrate()
    card, report = mod.migrate_card(
        _v1_card_dict(knownFailureModes="May underperform on rare subtypes only.")
    )
    assert card.skin_type_representation_equity == ""
    assert report["lowConfidenceEquityExtraction"] is True


@pytest.mark.unit
def test_migrate_card_valid_card_has_no_validation_errors():
    mod = _load_migrate()
    card, report = mod.migrate_card(_v1_card_dict())
    assert report["validationErrors"] == []


@pytest.mark.unit
def test_backup_and_apply_round_trip(tmp_path: Path, monkeypatch):
    mod = _load_migrate()

    preloaded = tmp_path / "preloaded_cards"
    preloaded.mkdir()
    card_path = preloaded / "sample.clinical.json"
    card_path.write_text(json.dumps(_v1_card_dict()), encoding="utf-8")

    monkeypatch.setattr(mod, "PRELOADED", preloaded)
    monkeypatch.setattr(mod, "BACKUP", preloaded / "v1_backup")

    sources = mod._clinical_json_sources()
    assert len(sources) == 1

    mod._backup(sources)
    manifest_path = preloaded / "v1_backup" / "MANIFEST.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "sample.clinical.json" in manifest

    raw = json.loads(card_path.read_text(encoding="utf-8"))
    card, _report = mod.migrate_card(raw)
    card_path.write_text(card.to_json(), encoding="utf-8")

    migrated = json.loads(card_path.read_text(encoding="utf-8"))
    assert migrated["schemaVersion"] == SCHEMA_VERSION
    assert "knownFailureModes" not in migrated
    assert "knownPerformanceLimitations" in migrated

    backed_up_name = manifest["sample.clinical.json"]
    original = json.loads((preloaded / "v1_backup" / backed_up_name).read_text(encoding="utf-8"))
    assert original["schemaVersion"] == "clinical-model-card-1.0"
