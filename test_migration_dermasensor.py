"""DermaSensor migration regression tests (offline, v03_backup)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
BACKUP = REPO / "src/core/pages/preloaded_cards/v03_backup"
DERMA_MD = BACKUP / "dermasensor-20260501-192348.md"
MIGRATE_SCRIPT = REPO / "scripts/migrate_v03_to_clinical_cards.py"

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from core.chai_schema import RegulatoryApprovalStatus
from core.clinical_regulatory import classify_regulatory_status, conservative_text_to_status
from core.dermauto_card_render import card_to_sections, render_from_card
from core.migration_metrics import parse_migration_metrics
from migration_field_synthesis import _overlap_ratio, _sents, densify_citation_sidecar, validate_migrated_card
from utils.sentence_utils import count_sentences


def _load_migrate():
    spec = importlib.util.spec_from_file_location("migrate_v03", MIGRATE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def dermasensor_bundle():
    mod = _load_migrate()
    card, bundle = mod.migrate_card(DERMA_MD)
    return card, bundle


@pytest.mark.unit
def test_dermasensor_de_novo_maps_fda_cleared():
    reg_text = (
        "The DermaSensor device received De Novo classification as a Class II prescription device "
        "from the FDA on January 12, 2024."
    )
    status, approval_date, _, confidence = classify_regulatory_status(legacy_text=reg_text)
    assert status == RegulatoryApprovalStatus.FDA_CLEARED
    assert status != RegulatoryApprovalStatus.FDA_APPROVED
    assert conservative_text_to_status(reg_text) == RegulatoryApprovalStatus.FDA_CLEARED
    assert confidence in ("conservative_map", "cited_explicit", "authoritative")
    from migration_field_synthesis import parse_regulatory_approval_date

    assert parse_regulatory_approval_date(reg_text) and parse_regulatory_approval_date(reg_text).isoformat() == "2024-01-12"


@pytest.mark.unit
def test_dermasensor_migrated_regulatory_enum(dermasensor_bundle):
    card, bundle = dermasensor_bundle
    assert card.regulatory_approval_status == RegulatoryApprovalStatus.FDA_CLEARED
    assert card.regulatory_approval_date and card.regulatory_approval_date.year == 2024
    cites = bundle["citations"]
    assert cites.get("regulatory_status_display", "").lower().find("de novo") >= 0


@pytest.mark.unit
def test_regulatory_color_only_on_status_row(dermasensor_bundle):
    card, bundle = dermasensor_bundle
    html = render_from_card(card, source_label="test", citations=bundle["citations"])
    display = bundle["citations"].get("regulatory_status_display", "FDA Cleared")
    assert "Regulatory Approval Status" in html
    status_value_idx = html.index(display[:20].split("—")[0].strip())
    status_chunk = html[max(0, status_value_idx - 500) : status_value_idx + 200]
    summary_idx = html.index(card.summary[:40])
    summary_chunk = html[summary_idx : summary_idx + 400]
    assert "background-color:#d8f3dc" in status_chunk or "border-left:4px solid #2d6a4f" in status_chunk
    assert "background-color:#d8f3dc" not in summary_chunk


@pytest.mark.unit
def test_dermasensor_summary_max_three_sentences(dermasensor_bundle):
    card, _ = dermasensor_bundle
    assert count_sentences(card.summary) <= 3


@pytest.mark.unit
def test_no_duplicate_sentences_within_fields(dermasensor_bundle):
    card, _ = dermasensor_bundle
    warnings = validate_migrated_card(card, monitoring=card.ongoing_monitoring_plan)
    assert not any("duplicate_sentences_in" in w for w in warnings)


@pytest.mark.unit
def test_risk_fields_not_highly_overlapping(dermasensor_bundle):
    card, _ = dermasensor_bundle
    warnings = validate_migrated_card(card, monitoring=card.ongoing_monitoring_plan)
    assert not any("high_overlap_between_risk_fields" in w for w in warnings)


@pytest.mark.unit
def test_no_sensitivity_equals_four_metric(dermasensor_bundle):
    card, _ = dermasensor_bundle
    for metric in card.performance.metrics:
        assert not (metric.name.lower() == "sensitivity" and metric.value.strip() == "4")
    assert not any(m.value == "4" for m in card.performance.metrics)


@pytest.mark.unit
def test_fitzpatrick_iv_not_parsed_as_sensitivity():
    text = (
        "Fitzpatrick Phototype IV: 4.3% training. "
        "Less data was available for sensitivity of the device for melanoma in Fitzpatrick skin phototypes IV-VI."
    )
    metrics = parse_migration_metrics(text)
    assert not any(m.value == "4" or m.value == "4.3%" for m in metrics if m.name == "Sensitivity")


@pytest.mark.unit
def test_scheduled_updates_not_duplicate_monitoring(dermasensor_bundle):
    card, _ = dermasensor_bundle
    if card.scheduled_updates and card.ongoing_monitoring_plan:
        assert _overlap_ratio(card.scheduled_updates, card.ongoing_monitoring_plan) < 0.65
    warnings = validate_migrated_card(card, monitoring=card.ongoing_monitoring_plan)
    assert "scheduled_updates_duplicates_monitoring" not in warnings


@pytest.mark.unit
def test_metric_level_citations_present(dermasensor_bundle):
    _, bundle = dermasensor_bundle
    field_cites = bundle["citations"].get("field_citations") or {}
    metric_keys = [k for k in field_cites if k.startswith("performance.metrics[")]
    assert metric_keys, "expected per-metric citation keys"


@pytest.mark.unit
def test_dense_citation_numbering_starts_at_one(dermasensor_bundle):
    _, bundle = dermasensor_bundle
    refs = bundle["citations"].get("references") or {}
    assert refs
    keys = sorted(int(k) for k in refs.keys())
    assert keys[0] == 1
    assert keys == list(range(1, len(keys) + 1))


@pytest.mark.unit
def test_no_orphaned_display_references(dermasensor_bundle):
    _, bundle = dermasensor_bundle
    refs = set((bundle["citations"].get("references") or {}).keys())
    cited: set[str] = set()
    for spans in (bundle["citations"].get("field_citations") or {}).values():
        for span in spans:
            for cid in span.get("citationIds") or []:
                cited.add(str(cid))
    assert cited.issubset(refs)
    assert refs == cited


@pytest.mark.unit
def test_role_has_no_class_ii(dermasensor_bundle):
    card, _ = dermasensor_bundle
    assert "class ii" not in (card.role_in_decision_making or "").lower()


@pytest.mark.unit
def test_acceptable_input_excludes_output_hardware(dermasensor_bundle):
    card, _ = dermasensor_bundle
    low = (card.acceptable_input or "").lower()
    assert "battery" not in low
    assert "investigate further" not in low


@pytest.mark.unit
def test_contact_prefers_manufacturer_not_fda_dice(dermasensor_bundle):
    card, _ = dermasensor_bundle
    contact = (card.contact.url or "").lower()
    assert "dice@fda" not in contact
    assert "dermasensor" in contact or "855" in contact
