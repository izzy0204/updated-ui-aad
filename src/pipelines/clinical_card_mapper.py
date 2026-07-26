"""Map agent output and legacy data to ClinicalModelCard."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.chai_schema import (
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
from core.clinical_regulatory import classify_regulatory_status
from utils.sentence_utils import count_sentences

_METRIC_RE = re.compile(
    r"(?P<name>sensitivity|specificity|auroc|auc|accuracy|false\s*negative|false\s*positive|fnr|fpr)"
    r"[^0-9]{0,20}(?P<value>\d+(?:\.\d+)?%?)",
    re.I,
)


def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return "; ".join(str(x).strip() for x in v if str(x).strip())
    return str(v).strip()


def _merge_unique(*parts: str) -> str:
    seen: set[str] = set()
    out: List[str] = []
    for p in parts:
        t = p.strip()
        if not t or t.lower() in {"not specified", "unknown", "n/a"}:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return " ".join(out)


def parse_metrics_from_text(text: str) -> List[PerformanceMetric]:
    """Parse performance metrics from free text; rejects skin-type false positives."""
    from core.migration_metrics import parse_migration_metrics

    return parse_migration_metrics(text)


def _coerce_training_data(raw: Any, flat: Dict[str, Any]) -> TrainingData:
    if isinstance(raw, dict):
        return TrainingData(
            description=_s(raw.get("description") or raw.get("datasetDescription")),
            dataset_url=_s(raw.get("dataset_url") or raw.get("datasetUrl")) or None,
        )
    return TrainingData(
        description=_merge_unique(_s(raw), _s(flat.get("development_data_characterization"))),
        dataset_url=_s(flat.get("dataset_doi_if_applicable")) or None,
    )


def _coerce_development(raw: Any, flat: Dict[str, Any]) -> ModelDevelopmentValidation:
    if isinstance(raw, dict):
        return ModelDevelopmentValidation(
            description=_s(raw.get("description")) or None,
            publication_url=_s(raw.get("publication_url") or raw.get("publicationUrl")) or None,
        )
    return ModelDevelopmentValidation(
        description=_merge_unique(
            _s(raw),
            _s(flat.get("validation_test_dataset")),
            _s(flat.get("usefulness_efficacy_validation_process_and_justification")),
        )
        or None,
        publication_url=_s(flat.get("peer_reviewed_publications")) or None,
    )


def _coerce_clinical_trial(raw: Any, flat: Dict[str, Any]) -> Optional[ClinicalTrial]:
    if isinstance(raw, dict):
        ct = ClinicalTrial(
            identifier=_s(raw.get("identifier")) or None,
            url=_s(raw.get("url")) or None,
            description=_s(raw.get("description")) or None,
        )
        if ct.identifier or ct.url or ct.description:
            return ct
        return None
    text = _s(raw or flat.get("clinical_trial_if_available"))
    return ClinicalTrial(description=text) if text else None


def _coerce_performance(raw: Any, flat: Dict[str, Any]) -> Performance:
    if isinstance(raw, dict):
        metrics: List[PerformanceMetric] = []
        for item in raw.get("metrics") or []:
            if not isinstance(item, dict):
                continue
            name = _s(item.get("name"))
            value = _s(item.get("value"))
            if name and value:
                metrics.append(
                    PerformanceMetric(
                        name=name,
                        value=value,
                        population=_s(item.get("population")) or None,
                        confidence_interval=_s(
                            item.get("confidence_interval") or item.get("confidenceInterval")
                        )
                        or None,
                    )
                )
        summary = _s(raw.get("summary")) or "Not disclosed"
        if not metrics:
            metrics = parse_metrics_from_text(summary)
        return Performance(summary=summary, metrics=metrics)
    perf_summary = _merge_unique(
        _s(raw),
        _s(flat.get("performance_summary")),
        _s(flat.get("usefulness_efficacy_result")),
        _s(flat.get("usefulness_efficacy_interpretation")),
    )
    metrics = parse_metrics_from_text(
        _s(flat.get("usefulness_efficacy_auroc_accuracy_etc"))
        + " "
        + _s(flat.get("safety_reliability_result"))
        + " "
        + _s(flat.get("fairness_equity_result"))
    )
    return Performance(summary=perf_summary or "Not disclosed", metrics=metrics)


def _coerce_contact(raw: Any, flat: Dict[str, Any]) -> Contact:
    if isinstance(raw, dict):
        return Contact(
            email=_s(raw.get("email")) or None,
            url=_s(raw.get("url")) or None,
        )
    return Contact(
        email=None,
        url=_s(raw or flat.get("inquiries_or_to_report_an_issue") or flat.get("application_url")) or None,
    )


def apply_nested_postfill(card: ClinicalModelCard, field_path: str, value: str) -> ClinicalModelCard:
    """Apply a post-fill string to a nested subfield without stringifying dataclasses."""
    if field_path == "training_data.description":
        card.training_data.description = value
    elif field_path == "training_data.dataset_url":
        card.training_data.dataset_url = value or None
    elif field_path == "model_development_and_validation.description":
        card.model_development_and_validation.description = value or None
    elif field_path == "model_development_and_validation.publication_url":
        card.model_development_and_validation.publication_url = value or None
    elif field_path == "performance.summary":
        card.performance.summary = value
    elif field_path == "contact.email":
        card.contact.email = value or None
    elif field_path == "contact.url":
        card.contact.url = value or None
    elif field_path.startswith("clinical_trial."):
        if card.clinical_trial is None:
            card.clinical_trial = ClinicalTrial()
        sub = field_path.split(".", 1)[1]
        setattr(card.clinical_trial, sub, value or None)
    return card


def _map_agent_dump_to_card(
    agent_dump: Dict[str, Any],
    *,
    user_model_name: str = "",
    user_developer_name: str = "",
    user_application_url: str = "",
    fda_records: Optional[List[Dict[str, Any]]] = None,
) -> ClinicalModelCard:
    d = agent_dump or {}
    flat = {k: d.get(k) for k in d}
    # Also accept camelCase from agent
    key_map = {
        "modelName": "model_name",
        "medicalPurpose": "medical_purpose",
        "acceptableInput": "acceptable_input",
        "roleInDecisionMaking": "role_in_decision_making",
        "intendedUsers": "intended_users",
        "targetPatientPopulation": "target_patient_population",
        "knownPerformanceLimitations": "known_performance_limitations",
        "skinTypeRepresentationEquity": "skin_type_representation_equity",
        "modelType": "model_type",
    }
    for ck, sk in key_map.items():
        if ck in d and sk not in flat:
            flat[sk] = d[ck]

    reg_text = _s(flat.get("regulatory_approval_status") or flat.get("regulatory_approval_status_if_applicable"))
    status, reg_date, reg_source, reg_conf = classify_regulatory_status(
        legacy_text=reg_text,
        fda_records=fda_records,
    )

    training_raw = d.get("training_data") if isinstance(d.get("training_data"), dict) else flat.get("training_data")
    dev_raw = d.get("model_development_and_validation") if isinstance(d.get("model_development_and_validation"), dict) else flat.get("model_development_and_validation")
    trial_raw = d.get("clinical_trial") if isinstance(d.get("clinical_trial"), dict) else flat.get("clinical_trial")
    perf_raw = d.get("performance") if isinstance(d.get("performance"), dict) else flat.get("performance")
    contact_raw = d.get("contact") if isinstance(d.get("contact"), dict) else flat.get("contact")

    card = ClinicalModelCard(
        model_name=user_model_name or _s(flat.get("model_name")),
        application_url=user_application_url or _s(flat.get("application_url")) or None,
        developer=user_developer_name or _s(flat.get("developer")),
        regulatory_approval_status=status,
        regulatory_approval_date=reg_date,
        version=_s(flat.get("version")) or "Not disclosed",
        last_updated=date.today(),
        availability=_s(flat.get("availability") or flat.get("global_availability")) or None,
        summary=_s(flat.get("summary")),
        medical_purpose=_s(flat.get("medical_purpose") or flat.get("intended_use_and_workflow")),
        acceptable_input=_merge_unique(
            _s(flat.get("acceptable_input")),
            _s(flat.get("input_data_source")),
            _s(flat.get("output_input_data_type")),
        ),
        output=_merge_unique(
            _s(flat.get("output")),
            _s(flat.get("outcomes_and_output")),
            _s(flat.get("type_and_value_of_solution_output")),
        ),
        role_in_decision_making=_s(flat.get("role_in_decision_making") or flat.get("clinical_risk_level")),
        intended_users=_merge_unique(
            _s(flat.get("intended_users") or flat.get("primary_intended_users")),
            _s(flat.get("necessary_knowledge_expertise")),
        ),
        target_patient_population=_s(
            flat.get("target_patient_population") or flat.get("targeted_patient_population")
        ),
        known_performance_limitations=_merge_unique(
            _s(flat.get("known_failure_modes") or flat.get("known_performance_limitations")),
            _s(flat.get("model_limitations")),
            _s(flat.get("unsupported_clinical_scenarios")),
            _s(flat.get("developer_supplied_warnings")),
            _s(flat.get("unsupported_use_cases")),
        ),
        skin_type_representation_equity=_s(
            flat.get("skin_type_representation_equity") or flat.get("skin_type_representation_and_equity")
        ),
        required_clinician_oversight=_merge_unique(
            _s(flat.get("required_clinician_oversight")),
            _s(flat.get("how_to_use")),
        ),
        model_type=_s(flat.get("model_type") or flat.get("ai_system_facts")),
        training_data=_coerce_training_data(
            training_raw,
            {**flat, "training_data": _s(flat.get("training_data")), "development_data_characterization": _s(flat.get("development_data_characterization"))},
        ),
        model_development_and_validation=_coerce_development(dev_raw, flat),
        clinical_trial=_coerce_clinical_trial(trial_raw, flat),
        performance=_coerce_performance(perf_raw, flat),
        performance_evaluation_limitations=_merge_unique(
            _s(flat.get("performance_evaluation_limitations")),
            _s(flat.get("fairness_equity_testing_data_description")),
            _s(flat.get("skin_tone_diversity")),
        ),
        ongoing_monitoring_plan=_s(flat.get("ongoing_monitoring_plan") or flat.get("ongoing_maintenance")) or None,
        scheduled_updates=_s(flat.get("scheduled_updates") or flat.get("ongoing_maintenance")) or None,
        contact=_coerce_contact(contact_raw, flat),
    )
    return card


def enforce_summary_length(
    card: ClinicalModelCard,
    *,
    rewrite_callback: Optional[Callable[[str], Optional[str]]] = None,
) -> Tuple[ClinicalModelCard, List[str]]:
    """Warn when summary exceeds three sentences; optional rewrite, never truncate."""
    warnings: List[str] = []
    original = card.summary or ""
    if count_sentences(original) <= 3:
        return card, warnings

    if rewrite_callback is not None:
        rewritten = rewrite_callback(original)
        if rewritten and count_sentences(rewritten) <= 3:
            card.summary = rewritten.strip()
            return card, warnings
        if rewritten and count_sentences(rewritten) > 3:
            warnings.append("summary_rewrite_still_too_long")

    warnings.append("summary_exceeds_three_sentences")
    card.summary = original
    return card, warnings
