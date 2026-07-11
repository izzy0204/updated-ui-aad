"""Terminal summary smoke tests (no live pipeline)."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import ClinicalModelCard
from terminal_app import print_card_summary

FIXTURE = REPO / "tests" / "fixtures" / "clinical_card_full.json"

V03_FIELDS = (
    "intended_use_and_workflow",
    "release_stage",
    "validation_test_dataset",
    "foundation_models",
    "xml_path",
    "clinical_risk_level",
)


@pytest.mark.unit
def test_terminal_summary_no_v03_fields():
    card = ClinicalModelCard.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_card_summary(card)
    out = buf.getvalue()
    for bad in V03_FIELDS:
        assert bad not in out
    assert "Medical Purpose:" in out
    assert "Regulatory Approval Status:" in out
    assert "Clinical JSON" not in out  # artifacts not printed here
