#!/usr/bin/env python3
"""One-time deterministic migration: CHAI v0.3 markdown → clinical-model-card-1.0 JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import (  # noqa: E402
    SCHEMA_VERSION,
    CITATIONS_SCHEMA_VERSION,
    ClinicalModelCard,
    ClinicalTrial,
    Contact,
    ModelDevelopmentValidation,
    Performance,
    PerformanceMetric,
    TrainingData,
    validate_model_card,
)
from core.clinical_regulatory import classify_regulatory_status, conservative_text_to_status
from core.citation_render import (
    build_field_citations_from_legacy_text,
    build_references_from_md,
    strip_inline_citation_markers,
)
from core.dermauto_card_render import (
    is_v03_markdown,
    normalize_md_for_parsing,
    parse_model_card_md,
    parse_references,
)
from pipelines.clinical_card_mapper import parse_metrics_from_text, _merge_unique
from utils.sentence_utils import count_sentences

PRELOADED = REPO / "src/core/pages/preloaded_cards"
BACKUP = PRELOADED / "v03_backup"
DEFAULT_OUT = PRELOADED / "clinical_migrated"

# v0.3 display label → legacy field name
_LABEL_TO_LEGACY: Dict[str, str] = {
    "Model Name": "model_name",
    "Developer": "developer",
    "Application URL": "application_url",
    "Inquiries or to report an issue": "inquiries_or_to_report_an_issue",
    "Release Stage": "release_stage",
    "Release Date": "release_date",
    "Version": "version",
    "Regulatory Approval Status, if applicable": "regulatory_approval_status_if_applicable",
    "Global Availability": "global_availability",
    "Summary": "summary",
    "Keywords": "keywords",
    "Intended Use & Workflow": "intended_use_and_workflow",
    "Primary Intended Users": "primary_intended_users",
    "Necessary knowledge/expertise": "necessary_knowledge_expertise",
    "How to Use": "how_to_use",
    "Targeted patient population": "targeted_patient_population",
    "Patient consent or disclosure required or suggested?": "patient_consent_or_disclosure_required_or_suggested",
    "Developer-Supplied Warnings": "developer_supplied_warnings",
    "Model Limitations": "model_limitations",
    "Skin type representation & equity": "skin_type_representation_and_equity",
    "Clinical Risk Level": "clinical_risk_level",
    "AI System Facts": "ai_system_facts",
    "Model Type": "model_type",
    "Outcomes & Output": "outcomes_and_output",
    "Type & Value of Solution Output": "type_and_value_of_solution_output",
    "Input Data Source": "input_data_source",
    "Output/Input Data Type": "output_input_data_type",
    "Training Data": "training_data",
    "Dataset (DOI if applicable)": "dataset_doi_if_applicable",
    "Validation/Test Dataset": "validation_test_dataset",
    "Skin tone diversity": "skin_tone_diversity",
    "Ongoing Maintenance": "ongoing_maintenance",
    "Goal of Metric(s)": "usefulness_efficacy_goal_of_metrics",
    "Result": "usefulness_efficacy_result",
    "Interpretation": "usefulness_efficacy_interpretation",
    "AUROC/Accuracy/etc.": "usefulness_efficacy_auroc_accuracy_etc",
    "Clinical Trial, if available": "clinical_trial_if_available",
    "Peer-Reviewed Publication(s)": "peer_reviewed_publications",
}

# Clinical field → legacy v0.3 field names (for citation span extraction)
_CLINICAL_CITATION_SOURCES: Dict[str, List[str]] = {
    "model_name": ["model_name"],
    "developer": ["developer"],
    "availability": ["global_availability"],
    "summary": ["summary"],
    "medical_purpose": ["intended_use_and_workflow"],
    "acceptable_input": ["input_data_source", "output_input_data_type", "how_to_use"],
    "output": ["outcomes_and_output", "type_and_value_of_solution_output"],
    "role_in_decision_making": ["clinical_risk_level", "intended_use_and_workflow"],
    "intended_users": ["primary_intended_users", "necessary_knowledge_expertise"],
    "target_patient_population": ["targeted_patient_population"],
    "known_failure_modes": ["model_limitations", "skin_type_representation_and_equity"],
    "unsupported_clinical_scenarios": ["developer_supplied_warnings", "model_limitations"],
    "unsupported_use_cases": ["model_limitations"],
    "required_clinician_oversight": [
        "how_to_use",
        "clinical_risk_level",
        "patient_consent_or_disclosure_required_or_suggested",
    ],
    "model_type": ["model_type", "ai_system_facts"],
    "training_data.description": ["training_data", "development_data_characterization"],
    "model_development_and_validation.description": ["validation_test_dataset", "peer_reviewed_publications"],
    "clinical_trial": ["clinical_trial_if_available"],
    "performance.summary": [
        "usefulness_efficacy_result",
        "usefulness_efficacy_interpretation",
        "usefulness_efficacy_auroc_accuracy_etc",
        "safety_reliability_result",
        "safety_reliability_interpretation",
    ],
    "performance_evaluation_limitations": ["skin_tone_diversity", "fairness_equity_testing_data_description"],
    "ongoing_monitoring_plan": ["ongoing_maintenance"],
    "scheduled_updates": ["ongoing_maintenance"],
    "contact": ["inquiries_or_to_report_an_issue", "application_url"],
    "regulatory_approval_status": ["regulatory_approval_status_if_applicable"],
}


def _clean_field_text(text: str) -> str:
    return strip_inline_citation_markers(text or "")


def _strip_url_field(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = strip_inline_citation_markers(str(raw).strip())
    return cleaned or None


def _build_citation_sidecar(
    md_text: str,
    legacy: Dict[str, str],
    old_citations: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build clinical citation sidecar from v0.3 references, inline markers, and legacy JSON."""
    references = build_references_from_md(normalize_md_for_parsing(md_text))
    ref_int: Dict[int, Dict[str, Any]] = {int(k): dict(v) for k, v in references.items()}

    # Merge URLs from legacy pipeline sidecar (flat field keys)
    for key, lst in old_citations.items():
        if key.startswith("_") or key in ("schema_version", "fields", "references", "field_citations", "fieldCitations"):
            continue
        if not isinstance(lst, list):
            continue
        for item in lst:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            if not any(_url_for_item(meta) == url for meta in ref_int.values()):
                rid = max(ref_int.keys(), default=0) + 1
                ref_int[rid] = {
                    "url": url,
                    "title": str(item.get("title") or item.get("snippet") or "")[:200],
                    "source": str(item.get("type") or "web"),
                }

    field_citations: Dict[str, List[Dict[str, Any]]] = {}
    unmatched_markers: List[int] = []
    cited_ids: Set[int] = set()

    for clinical_key, legacy_keys in _CLINICAL_CITATION_SOURCES.items():
        combined = _merge_unique(*[legacy.get(k, "") for k in legacy_keys])
        if not combined.strip():
            continue
        spans, unmatched, cited = build_field_citations_from_legacy_text(combined, ref_int)
        unmatched_markers.extend(unmatched)
        cited_ids.update(cited)
        if spans:
            field_citations[clinical_key] = spans

    # Legacy fields bucket in old sidecar
    old_fields = old_citations.get("fields") if isinstance(old_citations.get("fields"), dict) else {}
    for target, legacy_fields in {
        "regulatory_approval_status": ["regulatory_approval_status_if_applicable"],
        "summary": ["summary"],
        "known_failure_modes": ["model_limitations", "skin_type_representation_and_equity"],
        "performance.summary": ["usefulness_efficacy_result", "usefulness_efficacy_auroc_accuracy_etc"],
    }.items():
        cites = _union_citations(old_citations, target, legacy_fields)
        if not cites:
            continue
        ids: List[str] = []
        for item in cites:
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            for rid, meta in ref_int.items():
                if _url_for_item(meta) == url:
                    ids.append(str(rid))
                    cited_ids.add(rid)
                    break
            else:
                rid = max(ref_int.keys(), default=0) + 1
                ref_int[rid] = {
                    "url": url,
                    "title": str(item.get("snippet") or "")[:200],
                    "source": "pipeline",
                }
                ids.append(str(rid))
                cited_ids.add(rid)
        if ids and target not in field_citations:
            field_citations[target] = [{"citationIds": ids, "sentence_level": True}]

    orphaned = sorted(set(ref_int.keys()) - cited_ids)

    sidecar: Dict[str, Any] = {
        "schema_version": CITATIONS_SCHEMA_VERSION,
        "references": {str(k): v for k, v in sorted(ref_int.items())},
        "field_citations": field_citations,
        "fields": old_fields if isinstance(old_fields, dict) else {},
        "regulatory_status_source": None,
        "regulatory_status_confidence": "unknown",
    }
    audit = {
        "unmatchedMarkers": sorted(set(unmatched_markers)),
        "orphanedReferences": orphaned,
        "referenceCount": len(ref_int),
        "fieldCitationCount": len(field_citations),
    }
    return sidecar, audit


def _url_for_item(meta: Dict[str, Any]) -> str:
    return str(meta.get("url") or "").strip()


def _parse_v03_fields(md_text: str) -> Dict[str, str]:
    sections = parse_model_card_md(normalize_md_for_parsing(md_text))
    legacy: Dict[str, str] = {}
    for _sec, fields in sections.items():
        for label, value in fields.items():
            key = _LABEL_TO_LEGACY.get(label)
            if key:
                legacy[key] = value
            # Key metrics subsections reuse labels
            if label == "Result" and "usefulness_efficacy_result" not in legacy:
                legacy["usefulness_efficacy_result"] = value
            if label == "AUROC/Accuracy/etc.":
                legacy["usefulness_efficacy_auroc_accuracy_etc"] = value
    return legacy


def _extract_timestamp(md_text: str) -> Optional[date]:
    m = re.search(r"Generated on (\d{4}-\d{2}-\d{2})", md_text)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            pass
    return None


def _load_legacy_citations(md_path: Path) -> Dict[str, Any]:
    cite_path = md_path.with_suffix(".citations.json")
    if cite_path.is_file():
        try:
            return json.loads(cite_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _union_citations(
    citations: Dict[str, Any],
    target: str,
    legacy_fields: List[str],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for lf in legacy_fields:
        for key in (lf, f"postfill.{lf}"):
            lst = citations.get(key)
            if not isinstance(lst, list):
                continue
            for item in lst:
                if not isinstance(item, dict):
                    continue
                u = str(item.get("url") or "").strip()
                if u and u not in seen:
                    seen.add(u)
                    entry = dict(item)
                    entry["legacy_fields"] = legacy_fields
                    out.append(entry)
    return out


def migrate_card(md_path: Path, fda_records: Optional[List[Dict]] = None) -> Tuple[ClinicalModelCard, Dict[str, Any]]:
    md_text = md_path.read_text(encoding="utf-8", errors="replace")
    if not is_v03_markdown(md_text):
        raise ValueError(f"Not a v0.3 card: {md_path.name}")

    legacy = _parse_v03_fields(md_text)
    old_citations = _load_legacy_citations(md_path)

    reg_cites = _union_citations(old_citations, "regulatory_approval_status", ["regulatory_approval_status_if_applicable"])
    status, reg_date, reg_source, reg_conf = classify_regulatory_status(
        legacy_text=legacy.get("regulatory_approval_status_if_applicable", ""),
        fda_records=fda_records,
        cited_snippets=reg_cites,
    )

    last_updated = _extract_timestamp(md_text) or date.today()

    perf_text = _merge_unique(
        legacy.get("usefulness_efficacy_result", ""),
        legacy.get("usefulness_efficacy_interpretation", ""),
        legacy.get("usefulness_efficacy_auroc_accuracy_etc", ""),
    )
    metrics = parse_metrics_from_text(
        legacy.get("usefulness_efficacy_auroc_accuracy_etc", "")
        + " " + legacy.get("safety_reliability_result", "")
    )

    nct_m = re.search(r"(NCT\d+)", legacy.get("clinical_trial_if_available", ""), re.I)
    trial_url_m = re.search(r"(https?://[^\s]+clinicaltrials[^\s]+)", legacy.get("clinical_trial_if_available", ""), re.I)

    card = ClinicalModelCard(
        model_name=_clean_field_text(legacy.get("model_name", "").strip()),
        application_url=_strip_url_field(legacy.get("application_url")),
        developer=_clean_field_text(legacy.get("developer", "").strip()),
        regulatory_approval_status=status,
        regulatory_approval_date=reg_date,
        version=legacy.get("version", "").strip() or "Not disclosed",
        last_updated=last_updated,
        availability=_clean_field_text(legacy.get("global_availability") or "") or None,
        summary=_clean_field_text(legacy.get("summary", "").strip()),
        medical_purpose=_clean_field_text(legacy.get("intended_use_and_workflow", "").strip()),
        acceptable_input=_clean_field_text(
            _merge_unique(
                legacy.get("input_data_source", ""),
                legacy.get("output_input_data_type", ""),
                legacy.get("how_to_use", ""),
            )
        ),
        output=_clean_field_text(
            _merge_unique(
                legacy.get("outcomes_and_output", ""),
                legacy.get("type_and_value_of_solution_output", ""),
            )
        ),
        role_in_decision_making=_clean_field_text(
            _merge_unique(
                legacy.get("clinical_risk_level", ""),
                legacy.get("intended_use_and_workflow", ""),
            )
        ),
        intended_users=_clean_field_text(
            _merge_unique(
                legacy.get("primary_intended_users", ""),
                legacy.get("necessary_knowledge_expertise", ""),
            )
        ),
        target_patient_population=_clean_field_text(legacy.get("targeted_patient_population", "").strip()),
        known_failure_modes=_clean_field_text(
            _merge_unique(
                legacy.get("model_limitations", ""),
                legacy.get("skin_type_representation_and_equity", ""),
            )
        ),
        unsupported_clinical_scenarios=_clean_field_text(
            _merge_unique(
                legacy.get("developer_supplied_warnings", ""),
                legacy.get("model_limitations", ""),
            )
        ),
        unsupported_use_cases=_clean_field_text(legacy.get("model_limitations", "").strip()),
        required_clinician_oversight=_clean_field_text(
            _merge_unique(
                legacy.get("how_to_use", ""),
                legacy.get("clinical_risk_level", ""),
                legacy.get("patient_consent_or_disclosure_required_or_suggested", ""),
            )
        ),
        model_type=_clean_field_text(_merge_unique(legacy.get("model_type", ""), legacy.get("ai_system_facts", ""))),
        training_data=TrainingData(
            description=_clean_field_text(
                _merge_unique(legacy.get("training_data", ""), legacy.get("development_data_characterization", ""))
            )
            or "Not disclosed",
            dataset_url=legacy.get("dataset_doi_if_applicable") or None,
        ),
        model_development_and_validation=ModelDevelopmentValidation(
            description=_clean_field_text(legacy.get("validation_test_dataset") or "") or None,
            publication_url=legacy.get("peer_reviewed_publications") or None,
        ),
        clinical_trial=(
            ClinicalTrial(
                identifier=nct_m.group(1) if nct_m else None,
                url=trial_url_m.group(1) if trial_url_m else None,
                description=_clean_field_text(legacy.get("clinical_trial_if_available") or "") or None,
            )
            if legacy.get("clinical_trial_if_available")
            else None
        ),
        performance=Performance(summary=_clean_field_text(perf_text) or "Not disclosed", metrics=metrics),
        performance_evaluation_limitations=_clean_field_text(
            _merge_unique(
                legacy.get("skin_tone_diversity", ""),
                legacy.get("fairness_equity_testing_data_description", ""),
            )
        )
        or "Not disclosed",
        ongoing_monitoring_plan=_clean_field_text(legacy.get("ongoing_maintenance") or "") or None,
        scheduled_updates=_clean_field_text(legacy.get("ongoing_maintenance") or "") or None,
        contact=Contact(
            email=None,
            url=_clean_field_text(
                legacy.get("inquiries_or_to_report_an_issue") or legacy.get("application_url") or ""
            )
            or None,
        ),
    )

    new_citations, citation_audit = _build_citation_sidecar(md_text, legacy, old_citations)
    new_citations["regulatory_status_source"] = reg_source
    new_citations["regulatory_status_confidence"] = reg_conf

    report = {
        "card": md_path.name,
        "schema_version": SCHEMA_VERSION,
        "mappedFields": [{"target": k, "legacyFields": v} for k, v in _CLINICAL_CITATION_SOURCES.items()],
        "synthesizedFields": [],
        "unmappedLegacyFields": [{"field": k, "action": "DROP"} for k in ("keywords", "release_stage") if legacy.get(k)],
        "citationAudit": citation_audit,
        "validationErrors": [],
        "validationWarnings": [],
    }
    vr = validate_model_card(card)
    report["validationErrors"] = vr.errors
    report["validationWarnings"] = vr.warnings
    if count_sentences(card.summary) > 3:
        report["validationWarnings"].append("summary_exceeds_three_sentences")
    if citation_audit.get("unmatchedMarkers"):
        report["validationWarnings"].append(
            f"unmatched_citation_markers:{citation_audit['unmatchedMarkers']}"
        )
    if citation_audit.get("orphanedReferences"):
        report["validationWarnings"].append(
            f"orphaned_references:{citation_audit['orphanedReferences']}"
        )

    return card, {"card": card, "citations": new_citations, "report": report}


def _content_hash(card: ClinicalModelCard) -> str:
    return hashlib.sha256(card.to_json().encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate v0.3 model cards to clinical schema v1.0")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Copy migrated artifacts to preloaded_cards/")
    parser.add_argument("--rollback", action="store_true", help="Restore from v03_backup/")
    args = parser.parse_args()

    if args.rollback:
        import shutil
        for p in BACKUP.glob("*.md"):
            shutil.copy2(p, PRELOADED / p.name)
        print("Restored from v03_backup/")
        return 0

    manifest = BACKUP / "MANIFEST.json"
    if not manifest.is_file():
        print("ERROR: v03_backup/MANIFEST.json missing. Run backup first.", file=sys.stderr)
        return 1

    out_dir: Path = args.out_dir
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    failed = 0
    for md_path in sorted(PRELOADED.glob("*.md")):
        if md_path.parent.name in ("v03_backup", "clinical_migrated"):
            continue
        if ".clinical." in md_path.name:
            continue
        try:
            card, bundle = migrate_card(md_path)
            report = bundle["report"]
            slug = md_path.stem
            if args.dry_run:
                print(f"[dry-run] {md_path.name}: errors={report['validationErrors']} warnings={report['validationWarnings']}")
            else:
                json_path = out_dir / f"{slug}.clinical.json"
                md_out = out_dir / f"{slug}.clinical.md"
                cite_path = out_dir / f"{slug}.citations.json"
                json_path.write_text(card.to_json(), encoding="utf-8")
                md_out.write_text(card.to_markdown(citations=bundle["citations"]), encoding="utf-8")
                cite_path.write_text(json.dumps(bundle["citations"], indent=2), encoding="utf-8")
                (out_dir / f"{slug}.migration_report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                print(f"Migrated {md_path.name} → {json_path.name}")
            if report["validationErrors"]:
                failed += 1
        except Exception as exc:
            print(f"ERROR {md_path.name}: {exc}", file=sys.stderr)
            failed += 1

    if args.apply and not args.dry_run:
        import shutil
        for jf in out_dir.glob("*.clinical.json"):
            shutil.copy2(jf, PRELOADED / jf.name)
        for mf in out_dir.glob("*.clinical.md"):
            shutil.copy2(mf, PRELOADED / mf.name)
        for cf in out_dir.glob("*.citations.json"):
            shutil.copy2(cf, PRELOADED / cf.name)
        print("Applied migrated cards to preloaded_cards/")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
