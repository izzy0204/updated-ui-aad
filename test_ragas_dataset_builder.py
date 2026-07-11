"""Offline tests for RAGAS dataset builder clinical JSON loading."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from ragas_eval.build_ragas_dataset import _clinical_field_map, load_card_flat

FIXTURE = REPO / "tests" / "fixtures" / "clinical_card_full.json"


@pytest.mark.unit
def test_clinical_field_map_from_fixture():
    from core.chai_schema import ClinicalModelCard

    card = ClinicalModelCard.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
    mapped = _clinical_field_map(card)
    assert mapped["summary"]
    assert mapped["intended_use_and_workflow"] == card.medical_purpose


@pytest.mark.unit
def test_load_card_flat_prefers_clinical_json(tmp_path: Path):
    jp = tmp_path / "card.clinical.json"
    jp.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    flat = load_card_flat(jp, REPO)
    assert flat["summary"]
    assert "intended_use_and_workflow" in flat
