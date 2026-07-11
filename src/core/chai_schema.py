"""Clinical model card schema v1.0 — clinician-centered structure."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional, Tuple

from utils.sentence_utils import count_sentences

SCHEMA_VERSION = "clinical-model-card-1.0"
CITATIONS_SCHEMA_VERSION = "clinical-model-card-citations-1.0"


class RegulatoryApprovalStatus(str, Enum):
    NOT_AUTHORIZED_CONSUMER_TOOL = "NOT_AUTHORIZED_CONSUMER_TOOL"
    INVESTIGATIONAL_RESEARCH_USE_ONLY = "INVESTIGATIONAL_RESEARCH_USE_ONLY"
    EUA_AUTHORIZED = "EUA_AUTHORIZED"
    FDA_APPROVED = "FDA_APPROVED"
    FDA_CLEARED = "FDA_CLEARED"
    CE_MARKED = "CE_MARKED"
    UNKNOWN = "UNKNOWN"


REGULATORY_STATUS_LABELS: Dict[RegulatoryApprovalStatus, str] = {
    RegulatoryApprovalStatus.NOT_AUTHORIZED_CONSUMER_TOOL: "Not Authorized / Consumer Tool",
    RegulatoryApprovalStatus.INVESTIGATIONAL_RESEARCH_USE_ONLY: "Investigational / Research Use Only",
    RegulatoryApprovalStatus.EUA_AUTHORIZED: "EUA Authorized",
    RegulatoryApprovalStatus.FDA_APPROVED: "FDA Approved",
    RegulatoryApprovalStatus.FDA_CLEARED: "FDA Cleared",
    RegulatoryApprovalStatus.CE_MARKED: "CE Marked",
    RegulatoryApprovalStatus.UNKNOWN: "Regulatory Status Unknown",
}


@dataclass
class TrainingData:
    description: str = ""
    dataset_url: Optional[str] = None


@dataclass
class ModelDevelopmentValidation:
    description: Optional[str] = None
    publication_url: Optional[str] = None


@dataclass
class ClinicalTrial:
    identifier: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None


@dataclass
class PerformanceMetric:
    name: str = ""
    value: str = ""
    population: Optional[str] = None
    confidence_interval: Optional[str] = None


@dataclass
class Performance:
    summary: str = ""
    metrics: List[PerformanceMetric] = field(default_factory=list)


@dataclass
class Contact:
    email: Optional[str] = None
    url: Optional[str] = None


@dataclass
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_date(val: Any) -> Optional[date]:
    if val is None or val == "":
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    s = str(val).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _date_to_iso(d: Optional[date]) -> Optional[str]:
    if d is None:
        return None
    return d.isoformat()


def iter_field_placements() -> Iterator[Tuple[str, str, str]]:
    """Yield (section, field_name, display_label) in export order."""
    yield ("1) Metadata", "model_name", "Model Name")
    yield ("1) Metadata", "developer", "Developer")
    yield ("1) Metadata", "regulatory_approval_status", "Regulatory Approval Status")
    yield ("1) Metadata", "regulatory_approval_date", "Regulatory Approval Date")
    yield ("1) Metadata", "version", "Version")
    yield ("1) Metadata", "last_updated", "Last Updated")
    yield ("1) Metadata", "availability", "Availability")

    yield ("2) Summary", "summary", "Summary")

    yield ("3) Intended Use", "medical_purpose", "Medical Purpose")
    yield ("3) Intended Use", "acceptable_input", "Acceptable Input")
    yield ("3) Intended Use", "output", "Output")
    yield ("3) Intended Use", "role_in_decision_making", "Role in Decision-Making")
    yield ("3) Intended Use", "intended_users", "Intended Users")
    yield ("3) Intended Use", "target_patient_population", "Target Patient Population")

    yield ("4) Risks and Limitations", "known_failure_modes", "Known Failure Modes")
    yield ("4) Risks and Limitations", "unsupported_clinical_scenarios", "Unsupported Clinical Scenarios")
    yield ("4) Risks and Limitations", "unsupported_use_cases", "Unsupported Use Cases")
    yield ("4) Risks and Limitations", "required_clinician_oversight", "Required Clinician Oversight")

    yield ("5) Mechanism and Development", "model_type", "Model Type")
    yield ("5) Mechanism and Development", "training_data", "Training Data")
    yield ("5) Mechanism and Development", "model_development_and_validation", "Model Development & Validation")
    yield ("5) Mechanism and Development", "clinical_trial", "Clinical Trial")
    yield ("5) Mechanism and Development", "performance", "Performance")
    yield (
        "5) Mechanism and Development",
        "performance_evaluation_limitations",
        "Limitations in Evaluating Performance",
    )

    yield ("6) Governance and Monitoring", "ongoing_monitoring_plan", "Plans for Ongoing Monitoring")
    yield ("6) Governance and Monitoring", "scheduled_updates", "Scheduled Updates")
    yield ("6) Governance and Monitoring", "contact", "Inquiries / Report an Issue")


@dataclass
class ClinicalModelCard:
    """Clinician-centered model card (v1.0)."""

    model_name: str = ""
    application_url: Optional[str] = None
    developer: str = ""
    regulatory_approval_status: RegulatoryApprovalStatus = RegulatoryApprovalStatus.UNKNOWN
    regulatory_approval_date: Optional[date] = None
    version: str = ""
    last_updated: Optional[date] = None
    availability: Optional[str] = None

    summary: str = ""

    medical_purpose: str = ""
    acceptable_input: str = ""
    output: str = ""
    role_in_decision_making: str = ""
    intended_users: str = ""
    target_patient_population: str = ""

    known_failure_modes: str = ""
    unsupported_clinical_scenarios: str = ""
    unsupported_use_cases: str = ""
    required_clinician_oversight: str = ""

    model_type: str = ""
    training_data: TrainingData = field(default_factory=TrainingData)
    model_development_and_validation: ModelDevelopmentValidation = field(
        default_factory=ModelDevelopmentValidation
    )
    clinical_trial: Optional[ClinicalTrial] = None
    performance: Performance = field(default_factory=Performance)
    performance_evaluation_limitations: str = ""

    ongoing_monitoring_plan: Optional[str] = None
    scheduled_updates: Optional[str] = None
    contact: Contact = field(default_factory=Contact)

    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.regulatory_approval_status, str):
            try:
                self.regulatory_approval_status = RegulatoryApprovalStatus(self.regulatory_approval_status)
            except ValueError:
                self.regulatory_approval_status = RegulatoryApprovalStatus.UNKNOWN
        if isinstance(self.training_data, dict):
            self.training_data = TrainingData(**self.training_data)
        if isinstance(self.model_development_and_validation, dict):
            self.model_development_and_validation = ModelDevelopmentValidation(
                **self.model_development_and_validation
            )
        if isinstance(self.clinical_trial, dict):
            self.clinical_trial = ClinicalTrial(**self.clinical_trial)
        if isinstance(self.performance, dict):
            metrics = self.performance.get("metrics", [])
            self.performance = Performance(
                summary=self.performance.get("summary", ""),
                metrics=[PerformanceMetric(**m) if isinstance(m, dict) else m for m in metrics],
            )
        if isinstance(self.contact, dict):
            self.contact = Contact(**self.contact)
        if self.last_updated is None:
            self.last_updated = date.today()
        if isinstance(self.regulatory_approval_date, str):
            self.regulatory_approval_date = _parse_date(self.regulatory_approval_date)
        if isinstance(self.last_updated, str):
            parsed = _parse_date(self.last_updated)
            if parsed:
                self.last_updated = parsed

    def to_dict_camel(self) -> Dict[str, Any]:
        def _metric(m: PerformanceMetric) -> Dict[str, Any]:
            d: Dict[str, Any] = {"name": m.name, "value": m.value}
            if m.population:
                d["population"] = m.population
            if m.confidence_interval:
                d["confidenceInterval"] = m.confidence_interval
            return d

        def _trial(t: Optional[ClinicalTrial]) -> Optional[Dict[str, Any]]:
            if t is None:
                return None
            d: Dict[str, Any] = {}
            if t.identifier:
                d["identifier"] = t.identifier
            if t.url:
                d["url"] = t.url
            if t.description:
                d["description"] = t.description
            return d or None

        return {
            "schemaVersion": self.schema_version,
            "modelName": self.model_name,
            "applicationUrl": self.application_url,
            "developer": self.developer,
            "regulatoryApprovalStatus": self.regulatory_approval_status.value,
            "regulatoryApprovalDate": _date_to_iso(self.regulatory_approval_date),
            "version": self.version,
            "lastUpdated": _date_to_iso(self.last_updated),
            "availability": self.availability,
            "summary": self.summary,
            "medicalPurpose": self.medical_purpose,
            "acceptableInput": self.acceptable_input,
            "output": self.output,
            "roleInDecisionMaking": self.role_in_decision_making,
            "intendedUsers": self.intended_users,
            "targetPatientPopulation": self.target_patient_population,
            "knownFailureModes": self.known_failure_modes,
            "unsupportedClinicalScenarios": self.unsupported_clinical_scenarios,
            "unsupportedUseCases": self.unsupported_use_cases,
            "requiredClinicianOversight": self.required_clinician_oversight,
            "modelType": self.model_type,
            "trainingData": {
                "description": self.training_data.description,
                "datasetUrl": self.training_data.dataset_url,
            },
            "modelDevelopmentAndValidation": {
                "description": self.model_development_and_validation.description,
                "publicationUrl": self.model_development_and_validation.publication_url,
            },
            "clinicalTrial": _trial(self.clinical_trial),
            "performance": {
                "summary": self.performance.summary,
                "metrics": [_metric(m) for m in self.performance.metrics],
            },
            "performanceEvaluationLimitations": self.performance_evaluation_limitations,
            "ongoingMonitoringPlan": self.ongoing_monitoring_plan,
            "scheduledUpdates": self.scheduled_updates,
            "contact": {
                "email": self.contact.email,
                "url": self.contact.url,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClinicalModelCard":
        """Load from camelCase or snake_case dict."""

        def _get(*keys: str, default: Any = None) -> Any:
            for k in keys:
                if k in data:
                    return data[k]
            return default

        td = _get("trainingData", "training_data") or {}
        mdv = _get("modelDevelopmentAndValidation", "model_development_and_validation") or {}
        ct = _get("clinicalTrial", "clinical_trial")
        perf = _get("performance") or {}
        contact = _get("contact") or {}
        metrics_raw = perf.get("metrics", []) if isinstance(perf, dict) else []

        status_raw = _get("regulatoryApprovalStatus", "regulatory_approval_status", default="UNKNOWN")
        try:
            status = RegulatoryApprovalStatus(status_raw)
        except ValueError:
            status = RegulatoryApprovalStatus.UNKNOWN

        return cls(
            schema_version=_get("schemaVersion", "schema_version", default=SCHEMA_VERSION),
            model_name=_get("modelName", "model_name", default=""),
            application_url=_get("applicationUrl", "application_url"),
            developer=_get("developer", default=""),
            regulatory_approval_status=status,
            regulatory_approval_date=_parse_date(_get("regulatoryApprovalDate", "regulatory_approval_date")),
            version=_get("version", default=""),
            last_updated=_parse_date(_get("lastUpdated", "last_updated")) or date.today(),
            availability=_get("availability"),
            summary=_get("summary", default=""),
            medical_purpose=_get("medicalPurpose", "medical_purpose", default=""),
            acceptable_input=_get("acceptableInput", "acceptable_input", default=""),
            output=_get("output", default=""),
            role_in_decision_making=_get("roleInDecisionMaking", "role_in_decision_making", default=""),
            intended_users=_get("intendedUsers", "intended_users", default=""),
            target_patient_population=_get("targetPatientPopulation", "target_patient_population", default=""),
            known_failure_modes=_get("knownFailureModes", "known_failure_modes", default=""),
            unsupported_clinical_scenarios=_get(
                "unsupportedClinicalScenarios", "unsupported_clinical_scenarios", default=""
            ),
            unsupported_use_cases=_get("unsupportedUseCases", "unsupported_use_cases", default=""),
            required_clinician_oversight=_get(
                "requiredClinicianOversight", "required_clinician_oversight", default=""
            ),
            model_type=_get("modelType", "model_type", default=""),
            training_data=TrainingData(
                description=td.get("description", "") if isinstance(td, dict) else "",
                dataset_url=td.get("datasetUrl") or td.get("dataset_url") if isinstance(td, dict) else None,
            ),
            model_development_and_validation=ModelDevelopmentValidation(
                description=mdv.get("description") if isinstance(mdv, dict) else None,
                publication_url=(
                    mdv.get("publicationUrl") or mdv.get("publication_url") if isinstance(mdv, dict) else None
                ),
            ),
            clinical_trial=(
                ClinicalTrial(
                    identifier=ct.get("identifier"),
                    url=ct.get("url"),
                    description=ct.get("description"),
                )
                if isinstance(ct, dict)
                else None
            ),
            performance=Performance(
                summary=perf.get("summary", "") if isinstance(perf, dict) else "",
                metrics=[
                    PerformanceMetric(
                        name=m.get("name", ""),
                        value=m.get("value", ""),
                        population=m.get("population"),
                        confidence_interval=m.get("confidenceInterval") or m.get("confidence_interval"),
                    )
                    for m in metrics_raw
                    if isinstance(m, dict)
                ],
            ),
            performance_evaluation_limitations=_get(
                "performanceEvaluationLimitations", "performance_evaluation_limitations", default=""
            ),
            ongoing_monitoring_plan=_get("ongoingMonitoringPlan", "ongoing_monitoring_plan"),
            scheduled_updates=_get("scheduledUpdates", "scheduled_updates"),
            contact=Contact(
                email=contact.get("email") if isinstance(contact, dict) else None,
                url=contact.get("url") if isinstance(contact, dict) else None,
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict_camel(), indent=2, default=str)

    def _render_disclosed(self, val: Optional[str]) -> str:
        if val is None or not str(val).strip():
            return "Not disclosed"
        return str(val).strip()

    def _cite_suffix(self, field_name: str, citations: Optional[Dict[str, Any]], url_to_num: Dict[str, int]) -> str:
        if not citations:
            return ""
        lst = citations.get("fields", {}).get(field_name) or citations.get(field_name)
        if not isinstance(lst, list):
            return ""
        nums = sorted(
            {
                url_to_num[u]
                for item in lst
                if isinstance(item, dict)
                for u in [item.get("url", "").strip()]
                if u and u in url_to_num
            }
        )
        return f" [{','.join(map(str, nums))}]" if nums else ""

    def to_markdown(self, citations: Optional[Dict[str, Any]] = None) -> str:
        """Derive human-readable markdown from the card (viewing format)."""
        url_to_num: Dict[str, int] = {}
        ordered_urls: List[str] = []
        if citations and isinstance(citations, dict):
            fields_cites = citations.get("fields", citations)
            seen: set[str] = set()
            for _k, lst in fields_cites.items():
                if not isinstance(lst, list):
                    continue
                for it in lst:
                    if isinstance(it, dict):
                        u = (it.get("url") or "").strip()
                        if u and u not in seen:
                            seen.add(u)
                            ordered_urls.append(u)
            ordered_urls.sort()
            url_to_num = {u: i for i, u in enumerate(ordered_urls, 1)}

        def line(label: str, field_name: str, value: str) -> str:
            cite = self._cite_suffix(field_name, citations, url_to_num)
            return f"- **{label}:** {value}{cite}"

        title = self.model_name or "Unnamed Model"
        if self.application_url:
            title_md = f"[{title}]({self.application_url})"
        else:
            title_md = title

        status_label = REGULATORY_STATUS_LABELS.get(
            self.regulatory_approval_status, self.regulatory_approval_status.value
        )

        lines: List[str] = [
            "---",
            f"schema_version: {self.schema_version}",
            "---",
            "",
            f"# {title_md} — Clinical Model Card",
            "",
            "## 1) Metadata",
            line("Model Name", "model_name", self.model_name),
            line("Developer", "developer", self.developer),
            line("Regulatory Approval Status", "regulatory_approval_status", status_label),
            line(
                "Regulatory Approval Date",
                "regulatory_approval_date",
                self._render_disclosed(_date_to_iso(self.regulatory_approval_date)),
            ),
            line("Version", "version", self.version or "Not disclosed"),
            line("Last Updated", "last_updated", _date_to_iso(self.last_updated) or ""),
            line("Availability", "availability", self._render_disclosed(self.availability)),
            "",
            "## 2) Summary",
            line("Summary", "summary", self.summary),
            "",
            "## 3) Intended Use",
            line("Medical Purpose", "medical_purpose", self.medical_purpose),
            line("Acceptable Input", "acceptable_input", self.acceptable_input),
            line("Output", "output", self.output),
            line("Role in Decision-Making", "role_in_decision_making", self.role_in_decision_making),
            line("Intended Users", "intended_users", self.intended_users),
            line("Target Patient Population", "target_patient_population", self.target_patient_population),
            "",
            "## 4) Risks and Limitations",
            line("Known Failure Modes", "known_failure_modes", self.known_failure_modes),
            line("Unsupported Clinical Scenarios", "unsupported_clinical_scenarios", self.unsupported_clinical_scenarios),
            line("Unsupported Use Cases", "unsupported_use_cases", self.unsupported_use_cases),
            line("Required Clinician Oversight", "required_clinician_oversight", self.required_clinician_oversight),
            "",
            "## 5) Mechanism and Development",
            line("Model Type", "model_type", self.model_type),
        ]

        td = self.training_data.description or "Not disclosed"
        if self.training_data.dataset_url:
            td += f" [Dataset]({self.training_data.dataset_url})"
        lines.append(line("Training Data", "training_data", td))

        mdv_parts = []
        if self.model_development_and_validation.description:
            mdv_parts.append(self.model_development_and_validation.description)
        if self.model_development_and_validation.publication_url:
            mdv_parts.append(f"[Publication]({self.model_development_and_validation.publication_url})")
        lines.append(
            line(
                "Model Development & Validation",
                "model_development_and_validation",
                " ".join(mdv_parts) if mdv_parts else "Not disclosed",
            )
        )

        if self.clinical_trial:
            ct_parts = []
            if self.clinical_trial.identifier:
                ct_parts.append(self.clinical_trial.identifier)
            if self.clinical_trial.url:
                ct_parts.append(f"[ClinicalTrials.gov]({self.clinical_trial.url})")
            if self.clinical_trial.description:
                ct_parts.append(self.clinical_trial.description)
            lines.append(line("Clinical Trial", "clinical_trial", " — ".join(ct_parts)))
        else:
            lines.append(line("Clinical Trial", "clinical_trial", "Not disclosed"))

        lines.append(line("Performance", "performance", self.performance.summary or "Not disclosed"))
        for i, m in enumerate(self.performance.metrics):
            pop = f" ({m.population})" if m.population else ""
            ci = f", CI: {m.confidence_interval}" if m.confidence_interval else ""
            lines.append(
                line(
                    f"Performance — {m.name}",
                    f"performance.metrics[{i}]",
                    f"{m.value}{pop}{ci}",
                )
            )
        lines.append(
            line(
                "Limitations in Evaluating Performance",
                "performance_evaluation_limitations",
                self.performance_evaluation_limitations,
            )
        )
        lines.extend(
            [
                "",
                "## 6) Governance and Monitoring",
                line(
                    "Plans for Ongoing Monitoring",
                    "ongoing_monitoring_plan",
                    self._render_disclosed(self.ongoing_monitoring_plan),
                ),
                line(
                    "Scheduled Updates",
                    "scheduled_updates",
                    self._render_disclosed(self.scheduled_updates),
                ),
            ]
        )
        contact_parts = []
        if self.contact.email:
            contact_parts.append(self.contact.email)
        if self.contact.url:
            contact_parts.append(self.contact.url)
        lines.append(
            line(
                "Inquiries / Report an Issue",
                "contact",
                " | ".join(contact_parts) if contact_parts else "Not disclosed",
            )
        )

        if ordered_urls:
            lines.extend(["", "## References"])
            lines.extend(f"[{i}] {u}" for i, u in enumerate(ordered_urls, 1))

        return "\n".join(lines) + "\n"


def validate_model_card(card: ClinicalModelCard) -> ValidationResult:
    result = ValidationResult()
    required_strings = [
        "model_name",
        "developer",
        "version",
        "summary",
        "medical_purpose",
        "acceptable_input",
        "output",
        "role_in_decision_making",
        "intended_users",
        "target_patient_population",
        "known_failure_modes",
        "unsupported_clinical_scenarios",
        "unsupported_use_cases",
        "required_clinician_oversight",
        "model_type",
        "performance_evaluation_limitations",
    ]
    for fname in required_strings:
        val = getattr(card, fname, None)
        if not val or not str(val).strip():
            result.errors.append(f"missing_required:{fname}")

    if not card.training_data.description or not card.training_data.description.strip():
        result.errors.append("missing_required:training_data.description")
    if not card.performance.summary or not card.performance.summary.strip():
        result.errors.append("missing_required:performance.summary")

    if not card.contact.email and not card.contact.url:
        result.errors.append("missing_required:contact")

    if card.last_updated is None:
        result.errors.append("missing_required:last_updated")

    if count_sentences(card.summary) > 3:
        result.warnings.append("summary_exceeds_three_sentences")

    for i, m in enumerate(card.performance.metrics):
        if not m.name or not m.value:
            result.errors.append(f"invalid_metric:performance.metrics[{i}]")

    if card.regulatory_approval_status not in RegulatoryApprovalStatus:
        result.errors.append("invalid:regulatory_approval_status")

    return result


# Primary export type
CLINICAL_CARD_FIELD_NAMES: List[str] = [
    f.name
    for f in fields(ClinicalModelCard)
    if f.name
    not in {
        "schema_version",
        "training_data",
        "model_development_and_validation",
        "clinical_trial",
        "performance",
        "contact",
        "regulatory_approval_date",
        "last_updated",
        "application_url",
        "availability",
        "ongoing_monitoring_plan",
        "scheduled_updates",
    }
]

# Documented nested JSON shapes for agent extraction and post-fill
CLINICAL_NESTED_FIELD_SPECS: Dict[str, Dict[str, str]] = {
    "training_data": {"description": "string", "dataset_url": "string?"},
    "model_development_and_validation": {"description": "string?", "publication_url": "string?"},
    "clinical_trial": {"identifier": "string?", "url": "string?", "description": "string?"},
    "performance": {
        "summary": "string",
        "metrics": "array[{name,value,population?,confidence_interval?}]",
    },
    "contact": {"email": "string?", "url": "string?"},
}

CLINICAL_AGENT_EXTRACT_FIELDS: List[str] = CLINICAL_CARD_FIELD_NAMES + list(
    CLINICAL_NESTED_FIELD_SPECS.keys()
)
