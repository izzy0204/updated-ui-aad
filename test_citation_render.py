"""Tests for render-time citation injection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import (
    ClinicalModelCard,
    Contact,
    ModelDevelopmentValidation,
    Performance,
    RegulatoryApprovalStatus,
    TrainingData,
)
from core.citation_render import (
    apply_render_time_citations,
    format_citation_marker,
    inject_citations_into_text,
    normalize_citation_sidecar,
    parse_text_citation_spans,
    references_url_map,
    strip_inline_citation_markers,
)
from core.dermauto_card_render import card_to_sections, format_field, render_from_card


def _minimal_card(**overrides) -> ClinicalModelCard:
    base = dict(
        model_name="TestModel",
        developer="Dev Co",
        regulatory_approval_status=RegulatoryApprovalStatus.UNKNOWN,
        version="1.0",
        last_updated="2026-01-01",
        summary="First sentence. Second sentence.",
        medical_purpose="Assist clinicians.",
        acceptable_input="Images.",
        output="Labels.",
        role_in_decision_making="Support only.",
        intended_users="Dermatologists.",
        target_patient_population="Adults.",
        known_failure_modes="May err on rare cases.",
        unsupported_clinical_scenarios="Pediatric use.",
        unsupported_use_cases="Consumer self-diagnosis.",
        required_clinician_oversight="Required.",
        model_type="CNN.",
        training_data=TrainingData(description="10k images.", dataset_url=None),
        model_development_and_validation=ModelDevelopmentValidation(description="Validated.", publication_url=None),
        performance=Performance(summary="Sensitivity was 92%.", metrics=[]),
        performance_evaluation_limitations="Small cohort.",
        contact=Contact(email=None, url=None),
    )
    base.update(overrides)
    return ClinicalModelCard(**base)


def test_one_sentence_one_citation():
    text = "Reported sensitivity was 92%."
    spans = [{"text": "Reported sensitivity was 92%.", "citationIds": ["1"]}]
    out = inject_citations_into_text(text, spans)
    assert out.endswith("[1]")
    assert "92%" in out


def test_one_sentence_multiple_citations():
    text = "Validated on two cohorts."
    spans = [{"text": "Validated on two cohorts.", "citationIds": ["1", "3"]}]
    out = inject_citations_into_text(text, spans)
    assert "[1,3]" in out


def test_repeated_citation_reuse_same_number():
    refs = {1: {"url": "https://example.com/a"}}
    sidecar = {
        "references": {"1": refs[1]},
        "field_citations": {
            "summary": [
                {"text": "Alpha.", "citationIds": ["1"]},
                {"text": "Beta.", "citationIds": ["1"]},
            ]
        },
    }
    norm = normalize_citation_sidecar(sidecar)
    assert references_url_map(norm.references)[1] == "https://example.com/a"


def test_two_sentences_different_citations():
    text = "Sentence A. Sentence B."
    spans = [
        {"text": "Sentence A.", "citationIds": ["1"]},
        {"text": "Sentence B.", "citationIds": ["2"]},
    ]
    out = inject_citations_into_text(text, spans)
    assert "Sentence A. [1]" in out
    assert "Sentence B. [2]" in out


def test_missing_sidecar_strips_markers():
    card = _minimal_card(summary="Claim with marker [9].")
    html = render_from_card(card, source_label="test", citations=None)
    assert "Citations unavailable" in html
    assert "[9]" not in html


def test_missing_reference_id_non_clickable():
    html = format_field("Supported claim [99].", refs={}, hide_citations=False)
    assert "No URL for [99]" in html or "99" in html
    assert "<a " not in html


def test_migrated_legacy_markers_via_sidecar():
    card = _minimal_card(summary="DermGPT helps clinicians.")
    sidecar = {
        "references": {
            "1": {"url": "https://derma.jmir.org/2025/1/e74040", "title": "Study"},
            "4": {"url": "https://github.com/kfenggg/dermGPT", "title": "Repo"},
        },
        "field_citations": {
            "summary": [
                {
                    "text": "DermGPT helps clinicians.",
                    "citationIds": ["1", "4"],
                }
            ],
        },
    }
    html = render_from_card(card, source_label="migrated", citations=sidecar)
    assert 'href="https://derma.jmir.org/2025/1/e74040"' in html
    assert 'href="https://github.com/kfenggg/dermGPT"' in html
    assert "[1" in html or "1</a>" in html


def test_duplicate_marker_prevention():
    text = "Already cited [1]."
    spans = [{"text": "Already cited.", "citationIds": ["1"]}]
    out = inject_citations_into_text(strip_inline_citation_markers(text), spans)
    assert out.count("[1]") == 1


def test_clickable_links_in_viewer():
    card = _minimal_card(performance=Performance(summary="Accuracy was 95%.", metrics=[]))
    sidecar = {
        "references": {"2": {"url": "https://example.org/paper", "title": "Paper"}},
        "field_citations": {
            "performance.summary": [{"text": "Accuracy was 95%.", "citationIds": ["2"]}],
        },
    }
    html = render_from_card(card, source_label="x", citations=sidecar)
    assert 'target="_blank"' in html
    assert "example.org/paper" in html


def test_html_escaping():
    card = _minimal_card(summary='Use <script>alert("x")</script> carefully.')
    sidecar = {
        "references": {"1": {"url": "https://safe.example", "title": "Safe"}},
        "field_citations": {
            "summary": [{"text": 'Use <script>alert("x")</script> carefully.', "citationIds": ["1"]}],
        },
    }
    html = render_from_card(card, source_label="x", citations=sidecar)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_citation_toggle_off():
    card = _minimal_card(summary="Visible sentence.")
    sidecar = {
        "references": {"1": {"url": "https://example.com", "title": "Src"}},
        "field_citations": {
            "summary": [{"text": "Visible sentence.", "citationIds": ["1"]}],
        },
    }
    html = render_from_card(card, source_label="x", citations=sidecar, hide_citations=True)
    assert "[1]" not in html
    assert "Visible sentence." in html


def test_legacy_fields_format_sentence_level():
    sidecar = {
        "fields": {
            "summary": [
                {"url": "https://a.example", "snippet": "source A"},
                {"url": "https://b.example", "snippet": "source B"},
            ]
        }
    }
    norm = normalize_citation_sidecar(sidecar)
    sections = {"2) Summary": {"Summary": "Line one. Line two."}}
    card = _minimal_card()
    out = apply_render_time_citations(sections, card=card, normalized=norm)
    assert "[1" in out["2) Summary"]["Summary"] or "[2" in out["2) Summary"]["Summary"]


def test_parse_legacy_inline_spans():
    raw = "First fact. [1,2] Second fact. [3]"
    clean, spans = parse_text_citation_spans(raw)
    assert "[1" not in clean
    assert len(spans) == 2
    assert spans[0]["citationIds"] == ["1", "2"]
    assert spans[1]["citationIds"] == ["3"]


def test_migration_sidecar_from_v03_references():
    from scripts.migrate_v03_to_clinical_cards import migrate_card

    md_path = REPO / "src/core/pages/preloaded_cards/v03_backup/dermgpt-20260429-173126.md"
    if not md_path.is_file():
        return
    card, bundle = migrate_card(md_path)
    cites = bundle["citations"]
    assert cites["references"]
    assert cites["field_citations"]
    assert "[1" not in card.summary
    audit = bundle["report"]["citationAudit"]
    assert audit["referenceCount"] >= 1
    html = render_from_card(card, source_label="migrated", citations=cites)
    assert "jmir.org" in html or "github.com" in html


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
            traceback.print_exc()
    raise SystemExit(1 if failed else 0)
