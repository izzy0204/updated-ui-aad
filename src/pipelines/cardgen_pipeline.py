# src/pipelines/cardgen_pipeline.py
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, fields as dc_fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List

# Web discovery (DuckDuckGo) + prefetch (HTML/PDF → text)
from utils.web_search import discover_and_fetch

# Model card scoring system
from utils.model_card_scorer import ModelCardScorer, format_score_report, get_score_summary

# Publications finder (Crossref + ArXiv)
try:
    from utils.enhanced_publication_finder import EnhancedPublicationFinder
    _HAS_PUBS = True
except Exception:
    _HAS_PUBS = False
    EnhancedPublicationFinder = None  # type: ignore

# FDA/510(k) lookup (optional — skip if not present)
try:
    # expected API: async or sync find_510k_for_product(model_name, developer?) -> List[dict]
    from utils.fda_discovery import find_510k_for_product  # type: ignore
    _HAS_FDA = True
except Exception:
    _HAS_FDA = False
    find_510k_for_product = None  # type: ignore

# === CHAI schema: single source of truth ===
from core.chai_schema import CHAIModelCard

# === Gemini agent (planning/fetch/fill/validate/backfill/finalize) ===
from agents.gemini_agent.agent import run_async as gemini_run_async

# Optional: direct Gemini access for post-fill (safe no-op if absent)
try:
    import google.genai as _genai
    from google.genai import types as _genai_types
    from config.config import get_settings as _get_settings
    _HAS_GENAI = True
except Exception:
    _HAS_GENAI = False
    _genai = None  # type: ignore
    _genai_types = None  # type: ignore
    _get_settings = None  # type: ignore



# ------------------------- small helpers -------------------------

@dataclass
class PipelineOutputs:
    json_path: Optional[Path]
    md_path: Optional[Path]
    xml_path: Optional[Path]
    citations_json_path: Optional[Path]
    scoring_txt: Optional[Path] = None


def _slugify(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in s).strip("-")[:64]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ---------- Normalization + resilient fallback mapping ----------

def _norm_key(s: str) -> str:
    """
    Normalize section/key names from Gemini dumps (handles human headings, punctuation, case).
    Examples:
      "Usefulness / Efficacy: Goal" -> "usefulness.efficacy.goal"
      "resources.evaluation references" -> "resources.evaluation.references"
    """
    s = s or ""
    s = s.strip().lower()
    s = re.sub(r"[／/|]+", " ", s)          # slashes/pipes → space
    s = re.sub(r"\s+", " ", s)              # collapse spaces
    s = s.replace(" & ", " and ")
    s = s.replace(" - ", " ")
    s = s.replace("-", " ")
    s = s.replace(":", "")
    s = s.replace(",", "")
    s = s.replace("(", "").replace(")", "")
    s = s.replace("’", "'")
    s = s.strip()
    return s.replace(" ", ".")


def _flatten_with_normalization(d: dict) -> dict:
    """Flatten 1-level dict and add normalized keys; handles human headings."""
    flat = {}
    for k, v in d.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                raw = f"{k}.{k2}"
                flat[raw] = v2
                flat[_norm_key(raw)] = v2
        else:
            flat[k] = v
            flat[_norm_key(k)] = v
    return flat

# Canonical legacy agent keys (dotted paths / common aliases) → CHAI field names
_AGENT_TO_CHAI: dict[str, str] = {
    # ---------- METADATA ----------
    "metadata.name": "model_name",
    "metadata.model": "model_name",
    "name": "model_name",
    "model": "model_name",

    "metadata.developer": "developer",
    "metadata.organization": "developer",
    "metadata.publisher": "developer",
    "developer": "developer",

    "metadata.support_contact": "inquiries_or_to_report_an_issue",
    "metadata.contact": "inquiries_or_to_report_an_issue",
    "metadata.support": "inquiries_or_to_report_an_issue",
    "contact": "inquiries_or_to_report_an_issue",

    "metadata.stage": "release_stage",
    "metadata.maturity": "release_stage",
    "release.stage": "release_stage",
    "stage": "release_stage",

    "metadata.release_date": "release_date",
    "metadata.release_date_iso": "release_date",
    "metadata.date": "release_date",
    "release.date": "release_date",
    "date": "release_date",

    "metadata.version": "version",
    "metadata.version_tag": "version",
    "version": "version",

    "metadata.regulatory_status": "regulatory_approval_status_if_applicable",
    "metadata.approval_status": "regulatory_approval_status_if_applicable",

    "metadata.availability": "global_availability",
    "availability": "global_availability",

    "metadata.summary": "summary",
    "overview": "summary",
    "abstract": "summary",
    "description": "summary",
    "summary": "summary",

    "metadata.keywords": "keywords",
    "tags": "keywords",
    "keywords": "keywords",

    # ---------- USES & DIRECTIONS ----------
    "uses.purpose": "intended_use_and_workflow",
    "uses.intended_use": "intended_use_and_workflow",
    "purpose": "intended_use_and_workflow",

    "uses.primary_users": "primary_intended_users",
    "users": "primary_intended_users",

    "uses.expertise_required": "necessary_knowledge_expertise",
    "required.expertise": "necessary_knowledge_expertise",

    "uses.how_to_use": "how_to_use",
    "instructions": "how_to_use",
    "usage": "how_to_use",

    "uses.target_population": "targeted_patient_population",
    "target.population": "targeted_patient_population",

    "uses.patient_consent_required": "patient_consent_or_disclosure_required_or_suggested",
    "patient.consent": "patient_consent_or_disclosure_required_or_suggested",

    # ---------- WARNINGS ----------
    "warnings.developer_warnings": "developer_supplied_warnings",
    "developer.warnings": "developer_supplied_warnings",

    "warnings.limitations": "model_limitations",
    "limitations": "model_limitations",

    "warnings.skin_type_representation_and_equity": "skin_type_representation_and_equity",
    "skin.tone.representation": "skin_type_representation_and_equity",

    "warnings.clinical_risk_level": "clinical_risk_level",
    "risk.level": "clinical_risk_level",

    # ---------- TRUST INGREDIENTS ----------
    "trust.ai_system_facts": "ai_system_facts",

    "trust.model_type": "model_type",
    "architecture": "model_type",
    "model.architecture": "model_type",

    "trust.interaction_with_other_systems": "interaction_with_other_systems",
    "system.integration": "interaction_with_other_systems",

    "trust.outcomes_output": "outcomes_and_output",
    "outputs": "outcomes_and_output",

    "trust.type_value_output": "type_and_value_of_solution_output",
    "output.value": "type_and_value_of_solution_output",

    "trust.explainability": "explanation_for_how_an_output_is_generated",
    "explainability": "explanation_for_how_an_output_is_generated",

    "trust.foundation_models": "foundation_models_used_in_application_if_applicable",
    "foundation.models": "foundation_models_used_in_application_if_applicable",

    "trust.input_data_source": "input_data_source",
    "data.source": "input_data_source",

    "trust.output_input_data_type": "output_input_data_type",
    "data.types": "output_input_data_type",
    "modalities": "output_input_data_type",

    "trust.development_data_characterization": "development_data_characterization",

    "trust.training_data": "training_data",
    "training.dataset": "training_data",

    "trust.exclusion_criteria": "exclusion_inclusion_criteria",
    "trust.inclusion_criteria": "exclusion_inclusion_criteria",

    "trust.demographics": "demographic_representativeness",
    "demographic.representation": "demographic_representativeness",

    "trust.dataset_doi": "dataset_doi_if_applicable",
    "dataset.doi": "dataset_doi_if_applicable",

    "trust.dataset_transparency": "dataset_transparency",

    "trust.validation_test_dataset": "validation_test_dataset",
    "validation.dataset": "validation_test_dataset",
    "test.dataset": "validation_test_dataset",

    "trust.data_timeline": "timeline_of_data_collection",
    "data.collection.timeline": "timeline_of_data_collection",

    "trust.skin_tone_diversity": "skin_tone_diversity",

    "trust.did_the_data_collection_process_undergo_ethical_review": "did_the_data_collection_process_undergo_ethical_review",
    "ethical.review": "did_the_data_collection_process_undergo_ethical_review",

    "trust.ethical_review_board_oversight": "ethical_review_board_oversight",
    "ethics.board.oversight": "ethical_review_board_oversight",

    "trust.irb_approval": "irb_approval",

    "trust.relevance_of_training_data_to_intended_population": "relevance_of_training_data_to_intended_population",

    "trust.bias_mitigation_approaches": "bias_mitigation_approaches",

    "trust.ongoing_maintenance": "ongoing_maintenance",

    "trust.security_and_compliance_environment_practices_or_accreditations_if_applicable":
        "security_and_compliance_environment_practices_or_accreditations_if_applicable",

    "trust.transparency_intelligibility_and_accountability_mechanisms_if_applicable":
        "transparency_intelligibility_and_accountability_mechanisms_if_applicable",

    "trust.transparency_information": "transparency_information",

    "trust.funding_source_of_the_technical_implementation": "funding_source_of_the_technical_implementation",

    "trust.third_party_information_if_applicable": "third_party_information_if_applicable",

    # ---------- KEY METRICS: Usefulness / Efficacy ----------
    "metrics.usefulness.goal": "usefulness_efficacy_goal_of_metrics",
    "metrics.usefulness.result": "usefulness_efficacy_result",
    "metrics.usefulness.interpretation": "usefulness_efficacy_interpretation",
    "metrics.usefulness.test_type": "usefulness_efficacy_test_type",
    "metrics.usefulness.testing_data_description": "usefulness_efficacy_testing_data_description",
    "metrics.usefulness.validation_process_and_justification": "usefulness_efficacy_validation_process_and_justification",
    "metrics.usefulness.auroc_accuracy_etc": "usefulness_efficacy_auroc_accuracy_etc",

    # ---------- KEY METRICS: Fairness & Equity ----------
    "metrics.fairness.goal": "fairness_equity_goal_of_metrics",
    "metrics.fairness.result": "fairness_equity_result",
    "metrics.fairness.interpretation": "fairness_equity_interpretation",
    "metrics.fairness.test_type": "fairness_equity_test_type",
    "metrics.fairness.testing_data_description": "fairness_equity_testing_data_description",
    "metrics.fairness.validation_process_and_justification": "fairness_equity_validation_process_and_justification",

    # ---------- KEY METRICS: Safety & Reliability ----------
    "metrics.safety.goal": "safety_reliability_goal_of_metrics",
    "metrics.safety.result": "safety_reliability_result",
    "metrics.safety.interpretation": "safety_reliability_interpretation",
    "metrics.safety.test_type": "safety_reliability_test_type",
    "metrics.safety.testing_data_description": "safety_reliability_testing_data_description",
    "metrics.safety.validation_process_and_justification": "safety_reliability_validation_process_and_justification",

    # ---------- RESOURCES ----------
    "resources.evaluation_references": "evaluation_references_if_available",
    "resources.evaluation.references": "evaluation_references_if_available",

    "resources.clinical_trial": "clinical_trial_if_available",
    "clinical.trial": "clinical_trial_if_available",

    "resources.publications": "peer_reviewed_publications",
    "publications": "peer_reviewed_publications",

    "resources.reimbursement_status": "reimbursement_status_if_applicable",
    "reimbursement.status": "reimbursement_status_if_applicable",

    "resources.stakeholders_consulted": "stakeholders_consulted_during_design_of_solution",
    "stakeholders.consulted": "stakeholders_consulted_during_design_of_solution",
}

# For fields where Gemini is inconsistent, list multiple candidate keys per CHAI field.
_FALLBACKS: dict[str, list[str]] = {
    # ---------- Key Metrics: Usefulness / Efficacy ----------
    "usefulness_efficacy_goal_of_metrics": [
        "metrics.usefulness.goal", "key_metrics.usefulness.goal",
        "usefulness.efficacy.goal", "usefulness.goal", "efficacy.goal",
        "usefulness.and.efficacy.goal", "usefulness/efficacy.goal",
        "usefulness . efficacy.goal", "usefulness.efficacy.goal.of.metrics",
        "usefulness / efficacy.goal", "usefulness \\ efficacy.goal",
    ],
    "usefulness_efficacy_result": [
        "metrics.usefulness.result", "key_metrics.usefulness.result",
        "usefulness.efficacy.result", "usefulness.result", "efficacy.result",
    ],
    "usefulness_efficacy_interpretation": [
        "metrics.usefulness.interpretation", "key_metrics.usefulness.interpretation",
        "usefulness.efficacy.interpretation", "usefulness.interpretation", "efficacy.interpretation",
    ],
    "usefulness_efficacy_test_type": [
        "metrics.usefulness.test_type", "key_metrics.usefulness.test_type",
        "usefulness.efficacy.test.type", "usefulness.test.type", "efficacy.test.type",
    ],
    "usefulness_efficacy_testing_data_description": [
        "metrics.usefulness.testing_data_description",
        "key_metrics.usefulness.testing_data_description",
        "usefulness.efficacy.testing.data.description",
        "usefulness.testing.data.description", "efficacy.testing.data.description",
    ],
    "usefulness_efficacy_validation_process_and_justification": [
        "metrics.usefulness.validation_process_and_justification",
        "key_metrics.usefulness.validation_process_and_justification",
        "usefulness.efficacy.validation.process.and.justification",
        "usefulness.validation.process.and.justification",
        "efficacy.validation.process.and.justification",
    ],
    "usefulness_efficacy_auroc_accuracy_etc": [
        "metrics.usefulness.auroc_accuracy_etc",
        "key_metrics.usefulness.auroc_accuracy_etc",
        "usefulness.efficacy.auroc.accuracy.etc", "usefulness.auroc", "efficacy.auroc",
    ],

    # ---------- Key Metrics: Fairness & Equity ----------
    "fairness_equity_goal_of_metrics": [
        "metrics.fairness.goal", "key_metrics.fairness.goal",
        "fairness.and.equity.goal", "fairness/equity.goal", "fairness.equity.goal",
    ],
    "fairness_equity_result": [
        "metrics.fairness.result", "key_metrics.fairness.result",
        "fairness.equity.result", "equity.result", "fairness.result",
    ],
    "fairness_equity_interpretation": [
        "metrics.fairness.interpretation", "key_metrics.fairness.interpretation",
        "fairness.equity.interpretation",
    ],
    "fairness_equity_test_type": [
        "metrics.fairness.test_type", "key_metrics.fairness.test_type",
        "fairness.equity.test.type",
    ],
    "fairness_equity_testing_data_description": [
        "metrics.fairness.testing_data_description",
        "key_metrics.fairness.testing_data_description",
        "fairness.equity.testing.data.description",
    ],
    "fairness_equity_validation_process_and_justification": [
        "metrics.fairness.validation_process_and_justification",
        "key_metrics.fairness.validation_process_and_justification",
        "fairness.equity.validation.process.and.justification",
    ],

    # ---------- Key Metrics: Safety & Reliability ----------
    "safety_reliability_goal_of_metrics": [
        "metrics.safety.goal", "key_metrics.safety.goal",
        "safety.and.reliability.goal", "safety/reliability.goal", "safety.reliability.goal",
    ],
    "safety_reliability_result": [
        "metrics.safety.result", "key_metrics.safety.result", "safety.reliability.result",
    ],
    "safety_reliability_interpretation": [
        "metrics.safety.interpretation", "key_metrics.safety.interpretation",
        "safety.reliability.interpretation",
    ],
    "safety_reliability_test_type": [
        "metrics.safety.test_type", "key_metrics.safety.test_type",
        "safety.reliability.test.type",
    ],
    "safety_reliability_testing_data_description": [
        "metrics.safety.testing_data_description",
        "key_metrics.safety.testing_data_description",
        "safety.reliability.testing.data.description",
    ],
    "safety_reliability_validation_process_and_justification": [
        "metrics.safety.validation_process_and_justification",
        "key_metrics.safety.validation_process_and_justification",
        "safety.reliability.validation.process.and.justification",
    ],

    # ---------- Resources ----------
    "evaluation_references_if_available": [
        "resources.evaluation_references", "resources.evaluation.references",
        "resources.evaluation.refs", "evaluation.references",
    ],
    "clinical_trial_if_available": [
        "resources.clinical_trial", "resources.clinical.trial", "clinical.trial",
    ],
    "peer_reviewed_publications": [
        "resources.publications", "resources.peer.reviewed.publications",
        "peer.reviewed.publications", "publications",
    ],
    "reimbursement_status_if_applicable": [
        "resources.reimbursement_status", "reimbursement.status",
    ],
    "stakeholders_consulted_during_design_of_solution": [
        "resources.stakeholders_consulted", "stakeholders.consulted",
    ],

    # ---------- Helpful metadata/uses/warnings/trust synonyms ----------
    "model_name": [
        "metadata.name", "metadata.model", "name", "model", "metadata.model_title", "model.title",
    ],
    "developer": [
        "metadata.maker", "metadata.publisher", "metadata.organization",
        "maker", "publisher", "organization", "company", "lab", "team",
    ],
    "release_stage": [
        "metadata.stage", "metadata.maturity", "stage", "maturity", "release.status", "status",
    ],
    "release_date": [
        "metadata.release_date_iso", "metadata.date", "release.date", "date",
        "publication.date", "published.date",
    ],
    "version": [
        "metadata.version_tag", "metadata.ver", "ver", "release.version",
    ],
    "regulatory_approval_status_if_applicable": [
        "metadata.approval_status", "metadata.regulatory_status",
        "approval.status", "regulatory.status", "clearance.status",
    ],
    "global_availability": [
        "metadata.availability", "availability", "markets", "regions",
        "countries.available", "distribution",
    ],
    "summary": [
        "metadata.summary", "overview", "abstract", "description", "executive.summary",
    ],
    "keywords": [
        "metadata.keywords", "tags", "topics", "labels",
    ],
    "intended_use_and_workflow": [
        "uses.purpose", "uses.intended_use", "purpose", "intended.use",
        "workflow", "intended.workflow", "clinical.workflow",
    ],
    "primary_intended_users": [
        "uses.primary_users", "users", "intended.users", "end.users", "target.users",
    ],
    "necessary_knowledge_expertise": [
        "uses.expertise_required", "expertise.required", "required.expertise",
        "required.knowledge", "skills.required",
    ],
    "how_to_use": [
        "uses.how_to_use", "instructions", "usage", "user.guide", "directions",
    ],
    "targeted_patient_population": [
        "uses.target.population", "target.population", "patient.population", "intended.population",
    ],
    "patient_consent_or_disclosure_required_or_suggested": [
        "uses.patient_consent_required", "patient.consent", "disclosure.required",
        "consent", "informed.consent",
    ],
    "developer_supplied_warnings": [
        "warnings.developer_warnings", "warnings", "cautions", "contraindications", "developer.warnings",
    ],
    "model_limitations": [
        "warnings.limitations", "limitations", "known.limitations", "model.limits",
    ],
    "skin_type_representation_and_equity": [
        "warnings.skin_type_representation_and_equity", "skin.tone.representation",
        "fitzpatrick.representation", "representation.and.equity",
    ],
    "clinical_risk_level": [
        "warnings.clinical_risk_level", "risk.level", "clinical.risk", "harm.risk",
    ],
    "ai_system_facts": [
        "trust.ai_system_facts", "system.facts", "model.facts",
    ],
    "model_type": [
        "trust.model_type", "architecture", "model.architecture", "type",
    ],
    "interaction_with_other_systems": [
        "trust.interaction_with_other_systems", "system.integration",
        "integrations", "dependencies", "interop",
    ],
    "outcomes_and_output": [
        "trust.outcomes_output", "outputs", "outcomes", "model.outputs",
    ],
    "type_and_value_of_solution_output": [
        "trust.type_value_output", "output.value", "value.of.output", "benefits", "utility",
    ],
    "explanation_for_how_an_output_is_generated": [
        "trust.explainability", "explainability", "explanation",
        "how.output.is.generated", "interpretability",
    ],
    "foundation_models_used_in_application_if_applicable": [
        "trust.foundation_models", "foundation.models", "base.models", "pretrained.models",
    ],
    "input_data_source": [
        "trust.input_data_source", "inputs.source", "data.source", "input.source", "ingestion.source",
    ],
    "output_input_data_type": [
        "trust.output_input_data_type", "data.types", "input.output.types", "modalities", "modality",
    ],
    "development_data_characterization": [
        "trust.development_data_characterization", "dev.data.characterization", "development.dataset.characteristics",
    ],
    "training_data": [
        "trust.training_data", "training.dataset", "training.data.set", "train.data",
    ],
    "exclusion_inclusion_criteria": [
        "trust.exclusion_criteria", "trust.inclusion_criteria", "inclusion.criteria", "exclusion.criteria",
    ],
    "demographic_representativeness": [
        "trust.demographics", "demographic.representation", "population.representation",
    ],
    "dataset_doi_if_applicable": [
        "trust.dataset_doi", "metadata.dataset_doi", "dataset.doi", "doi",
    ],
    "dataset_transparency": [
        "trust.dataset_transparency", "dataset.transparency", "data.transparency",
    ],
    "validation_test_dataset": [
        "trust.validation_test_dataset", "validation.dataset", "test.dataset", "eval.dataset",
    ],
    "timeline_of_data_collection": [
        "trust.data_timeline", "data.collection.timeline", "timeline", "collection.timeline",
    ],
    "skin_tone_diversity": [
        "trust.skin_tone_diversity", "skin.tone.diversity", "fitzpatrick.diversity",
    ],
    "did_the_data_collection_process_undergo_ethical_review": [
        "trust.did_the_data_collection_process_undergo_ethical_review",
        "ethical.review", "ethics.review", "irb.reviewed",
    ],
    "ethical_review_board_oversight": [
        "trust.ethical_review_board_oversight", "ethics.board.oversight", "irb.oversight",
    ],
    "irb_approval": [
        "trust.irb_approval", "irb", "irb.approval", "ethics.approval",
    ],
    "relevance_of_training_data_to_intended_population": [
        "trust.relevance_of_training_data_to_intended_population",
        "data.relevance.to.population", "relevance.to.intended.population",
    ],
    "bias_mitigation_approaches": [
        "trust.bias_mitigation_approaches", "bias.mitigation", "debiasing.methods",
    ],
    "ongoing_maintenance": [
        "trust.ongoing_maintenance", "maintenance", "updates", "lifecycle.management",
    ],
    "security_and_compliance_environment_practices_or_accreditations_if_applicable": [
        "trust.security_and_compliance_environment_practices_or_accreditations_if_applicable",
        "security.and.compliance", "compliance.certifications", "security.certifications",
    ],
    "transparency_intelligibility_and_accountability_mechanisms_if_applicable": [
        "trust.transparency_intelligibility_and_accountability_mechanisms_if_applicable",
        "transparency.mechanisms", "accountability.mechanisms", "intelligibility.mechanisms",
    ],
    "transparency_information": [
        "trust.transparency_information", "transparency.info", "disclosures", "documentation.transparency",
    ],
    "funding_source_of_the_technical_implementation": [
        "trust.funding_source_of_the_technical_implementation", "funding.source", "grants", "sponsors",
    ],
    "third_party_information_if_applicable": [
        "trust.third_party_information_if_applicable", "third.party.info", "third.parties", "vendors",
    ],

    # helpful metadata synonym
    "inquiries_or_to_report_an_issue": [
        "metadata.support_contact", "metadata.contact", "metadata.support", "contact", "support",
        "inquiries.or.to.report.an.issue",
    ],
}


def _coerce_scalar_or_join(value: Any) -> str | None:
    """Join lists to a sentence; pass scalars through; preserve None."""
    if value is None:
        return None
    if isinstance(value, list):
        return "; ".join(str(x).strip() for x in value if str(x).strip())
    return str(value)


def _map_agent_dump_to_chai(agent_dump: Dict[str, Any], *, user_model_name: str = "", user_developer_name: str = "", user_application_url: str = "") -> CHAIModelCard:
    """
    Prefer flat CHAI keys directly. Fall back to your normalization + aliasing map
    for backward compatibility with older agent outputs.
    
    Args:
        agent_dump: Agent output dictionary
        user_model_name: User-provided model name (takes precedence)
        user_developer_name: User-provided developer name (takes precedence)
        user_application_url: User-provided application URL (takes precedence)
    """
    # 0) If the agent already returned CHAI-shaped flat keys, use them (type-safe)
    chai_field_names = {f.name for f in dc_fields(CHAIModelCard)}
    direct = {k: v for k, v in (agent_dump or {}).items() if k in chai_field_names}

    if direct:
        card = CHAIModelCard()  # correct typed defaults
        for k, v in direct.items():
            if k in ("keywords", "foundation_models_used_in_application_if_applicable"):
                if isinstance(v, list):
                    setattr(card, k, [str(x).strip() for x in v if str(x).strip()])
                elif v is None or (isinstance(v, str) and not v.strip()):
                    setattr(card, k, [])
                else:
                    setattr(card, k, [str(v).strip()])
            else:
                setattr(card, k, None if v is None else str(v).strip())
        
        # Override with user input if provided
        if user_model_name:
            card.model_name = user_model_name
        if user_developer_name:
            card.developer = user_developer_name
        if user_application_url:
            card.application_url = user_application_url
            
        return card

    # --- Legacy / mixed keys path (uses your existing normalization & fallbacks) ---
    flat = _flatten_with_normalization(agent_dump)
    kwargs: Dict[str, Any] = {}

    # 2) Direct one-to-one mappings (your existing _AGENT_TO_CHAI), if you keep it
    for agent_key, chai_field in _AGENT_TO_CHAI.items():
        candidates = [agent_key, _norm_key(agent_key)]
        for c in candidates:
            if c in flat:
                val = flat[c]
                if chai_field in ("keywords", "foundation_models_used_in_application_if_applicable") and isinstance(val, list):
                    kwargs[chai_field] = [str(x).strip() for x in val if str(x).strip()]
                else:
                    kwargs[chai_field] = _coerce_scalar_or_join(val)
                break

    # 3) Fallbacks
    for chai_field, cand_keys in _FALLBACKS.items():
        if chai_field in kwargs:
            continue
        for ck in cand_keys:
            nk = _norm_key(ck)
            if nk in flat:
                val = flat[nk]
                kwargs[chai_field] = _coerce_scalar_or_join(val)
                break

    # Override with user input if provided
    if user_model_name:
        kwargs["model_name"] = user_model_name
    if user_developer_name:
        kwargs["developer"] = user_developer_name
    if user_application_url:
        kwargs["application_url"] = user_application_url

    return CHAIModelCard(**kwargs)



# ------------------------- enrichment helpers -------------------------

def _looks_clinical(text: str) -> bool:
    """Tiny heuristic to decide if we should try FDA search."""
    t = (text or "").lower()
    hints = ("derm", "skin", "lesion", "melanoma", "biopsy", "clinical", "patient", "diagnos", "risk")
    return any(h in t for h in hints)


async def _fetch_publications(model_name: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (publications, seed_pages_from_pubs)
    Each publication -> seed page uses title + abstract for high-signal priming.
    """
    pubs: list[dict] = []
    pages: list[dict] = []
    if not _HAS_PUBS or not EnhancedPublicationFinder:
        return pubs, pages

    try:
        async with EnhancedPublicationFinder() as finder:
            pubs = await finder.comprehensive_publication_search(model_name)
        for p in pubs:
            url = p.get("url") or p.get("doi_url") or ""
            title = (p.get("title") or "").strip()
            abstract = (p.get("abstract") or "").strip()
            if not url or not (title or abstract):
                continue
            body = f"{title}\n\n{abstract}".strip()
            pages.append({"url": url, "text": body})
    except Exception:
        pubs, pages = [], []
    return pubs, pages


async def _fetch_fda_records(model_name: str, developer_name: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (fda_records, seed_pages_from_fda)
    We accept either sync or async implementations of find_510k_for_product.
    """
    fda: list[dict] = []
    pages: list[dict] = []
    if not _HAS_FDA or not find_510k_for_product:
        return fda, pages

    try:
        # try await if coroutine
        if asyncio.iscoroutinefunction(find_510k_for_product):
            fda = await find_510k_for_product(model_name, developer_name)
        else:
            fda = await asyncio.to_thread(find_510k_for_product, model_name, developer_name)
    except Exception:
        fda = []

    # Build seed pages (compact summary for Gemini context)
    for rec in fda or []:
        url = (rec.get("url") or rec.get("k_number_url") or "").strip()
        knum = (rec.get("k_number") or rec.get("kNumber") or "").strip()
        decision = (rec.get("decision") or rec.get("decision_date") or "").strip()
        dev = (rec.get("applicant") or rec.get("applicant_name") or "").strip()
        indications = (rec.get("indications_for_use") or "").strip()
        blurb = f"FDA 510(k) Record {knum} — Decision: {decision} — Applicant: {dev}\nIndications: {indications}".strip()
        if url and blurb:
            pages.append({"url": url, "text": blurb})
    return fda, pages


# ------------------------- post-fill helpers -------------------------

def _collect_empty_chai_fields(card: CHAIModelCard) -> list[str]:
    """Return CHAI field names that are empty ('' or empty list)."""
    empties: list[str] = []
    if not is_dataclass(card):
        return empties
    for f in dc_fields(card):
        if f.name == "extraction_timestamp":
            continue
        val = getattr(card, f.name, None)
        if (isinstance(val, str) and not val.strip()) or (isinstance(val, list) and not any(str(x).strip() for x in val)):
            empties.append(f.name)
    return empties


def _build_context_block(seed_pages: list[dict], citations: dict, max_chars: int = 40000) -> str:
    """
    Build a compact text blob from seed_pages + citations for Gemini post-fill.
    """
    parts: list[str] = []
    # Seed pages first (highest signal, already pre-cleaned)
    for i, p in enumerate(seed_pages[:20], 1):
        u = (p.get("url") or "").strip()
        t = (p.get("text") or "").strip()
        if not u or not t:
            continue
        parts.append(f"[SEED {i}] {u}\n{t}\n")
        # Then citations snippets we already gathered
        if isinstance(citations, dict):
            for k, lst in list(citations.items())[:30]:
                # Skip metadata key
                if k == "_sources_metadata":
                    continue
                if not isinstance(lst, list):
                    continue
                for j, ev in enumerate(lst[:3], 1):
                    u = (ev.get("url") or "").strip()
                    snip = (ev.get("snippet") or "").strip()
                    if u and snip:
                        parts.append(f"[EVIDENCE {k} #{j}] {u}\n{snip}\n")

    blob = "\n".join(parts).strip()
    if len(blob) > max_chars:
        blob = blob[:max_chars].rsplit("\n", 1)[0]
    return blob


def _postfill_client():
    """
    Returns (client, model, config). Safe no-op if genai/settings are unavailable.
    The config includes ThinkingConfig for Gemini 2.5 Flash.
    """
    try:
        if not _HAS_GENAI or _genai is None or _get_settings is None or _genai_types is None:
            return None, "", None
        s = _get_settings()
        api_key = os.getenv("GEMINI_API_KEY") or s.google_api_key
        if not api_key:
            return None, "", None
        client = _genai.Client(api_key=api_key)
        config = _genai_types.GenerateContentConfig(
            temperature=s.gemini_temperature,
            thinking_config=_genai_types.ThinkingConfig(
                include_thoughts=s.gemini_include_thoughts,
                thinking_budget=s.gemini_thinking_budget,
            ),
        )
        return client, s.gemini_model, config
    except Exception:
        return None, "", None



import json, re
from typing import List, Dict, Tuple

def _get_field_specific_guidance(field_name: str) -> str:
    """Get field-specific extraction guidance for post-fill."""
    guidance_map = {
        "release_date": "Look for dates in press releases, announcements, blog posts. Format: YYYY-MM-DD or 'Month Day, Year'",
        "global_availability": "Look for geographic information, country lists, regional availability statements",
        "how_to_use": "Look for tutorials, guides, documentation, getting started pages, user manuals",
        "developer_supplied_warnings": "Look for warnings, cautions, disclaimers, terms of service, safety pages",
        "model_limitations": "Look for limitations sections, constraints, 'does not' statements, restriction lists",
        "training_data": "Look for dataset descriptions, training corpus information, data collection details",
        "output_input_data_type": "Look for API documentation, technical specs, input/output format descriptions",
        "ongoing_maintenance": "Look for version history, changelogs, update schedules, maintenance policies",
        "transparency_information": "Look for transparency reports, disclosure statements, open source information",
        "usefulness_efficacy_result": "Look for performance metrics, time savings data, efficiency studies, validation results",
        "safety_reliability_goal_of_metrics": "Look for safety objectives, reliability targets, risk mitigation goals",
        "safety_reliability_result": "Look for safety metrics, reliability data, validation studies, error rates",
        "safety_reliability_interpretation": "Look for safety analysis, risk assessments, reliability evaluations",
    }
    return guidance_map.get(field_name, "Extract all relevant information from the context.")


async def _postfill_one_field(client, model: str, field_name: str, context_block: str, config=None) -> tuple[str, list[dict]]:
    """
    Ask Gemini to fill exactly one CHAI field. Returns (value, evidence_list).
    Evidence list items: {url, snippet}
    - Uses text 'contents' (not role-based messages) per google-genai
    - Recovers a JSON block leniently
    - Tolerates "value" or "values" and several evidence key shapes
    """
    if client is None or not model:
        return "", []

    system = (
        "You are assisting with a medical AI model card. "
        "Return ONLY a compact JSON object with keys: value (string) and evidence (array of {url, snippet}). "
        "Use the provided context; do not fabricate URLs."
    )

    field_guidance = _get_field_specific_guidance(field_name)
    
    prompt = f"""
Fill the following CHAI model card field using only the context below.

FIELD: {field_name}

FIELD-SPECIFIC GUIDANCE:
{field_guidance}

CONTEXT (seed pages and prior evidence):
{context_block}

CRITICAL: 
- If the information is not in the context, return empty string for value
- Do NOT fabricate information
- Extract exact quotes when possible
- Include specific details: dates, numbers, metrics

Respond as JSON:
{{
  "value": "<concise answer for this field or empty if unknown>",
  "evidence": [{{"url":"<source url>", "snippet":"<short supporting quote>"}}, ...]
}}
""".strip()

    try:
        text_content = system + "\n\n" + prompt
        resp = await client.aio.models.generate_content(
            model=model,
            contents=text_content,
            config=config,
        )
        # Extract text, skipping thought parts
        raw = ""
        if hasattr(resp, "candidates") and resp.candidates:
            candidate = resp.candidates[0]
            if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                for part in candidate.content.parts:
                    if hasattr(part, "thought") and part.thought:
                        continue
                    if hasattr(part, "text") and part.text:
                        raw = part.text
                        break
        if not raw:
            raw = getattr(resp, "text", None) or getattr(resp, "output_text", None) or ""

        # lenient JSON block recovery
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return "", []

        try:
            obj = json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # try to sanitize trailing commas / smart quotes quickly
            cleaned = re.sub(r",\s*([}\]])", r"\1", m.group(0))
            cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'")
            try:
                obj = json.loads(cleaned)
            except Exception:
                return "", []

        # Accept "value" or "values"
        val = obj.get("value")
        if not val and isinstance(obj.get("values"), dict):
            # if the model used plural, try to pick the single field's value
            vmap = obj["values"]
            if field_name in vmap and isinstance(vmap[field_name], (str, int, float)):
                val = vmap[field_name]
            else:
                # otherwise pick any first scalar
                for _k, _v in vmap.items():
                    if isinstance(_v, (str, int, float)):
                        val = _v
                        break

        # Coerce to string
        if isinstance(val, list):
            val = "; ".join(str(x).strip() for x in val if str(x).strip())
        elif isinstance(val, (int, float)):
            val = str(val)
        elif not isinstance(val, str):
            val = ""

        # Evidence may be under 'evidence' (dict or list) or 'citations'
        ev_raw = obj.get("evidence") or obj.get("citations") or {}
        ev_out: list[dict] = []

        def _clean_ev_list(lst):
            out = []
            for e in lst:
                if not isinstance(e, dict): 
                    continue
                u = (e.get("url") or "").strip()
                sn = (e.get("snippet") or e.get("quote") or "").strip()
                if u and sn:
                    out.append({"url": u, "snippet": sn[:240]})
            return out

        if isinstance(ev_raw, list):
            ev_out = _clean_ev_list(ev_raw)
        elif isinstance(ev_raw, dict):
            # pick evidence for this field, else flatten all
            if isinstance(ev_raw.get(field_name), list):
                ev_out = _clean_ev_list(ev_raw[field_name])
            else:
                flat = []
                for k, lst in ev_raw.items():
                    if isinstance(lst, list):
                        flat.extend(_clean_ev_list(lst))
                ev_out = flat

        return (val.strip() if isinstance(val, str) else ""), ev_out
    except Exception:
        return "", []




async def _postfill_one_critical_field(
    chai_card: CHAIModelCard,
    field_name: str,
    seed_pages: list[dict],
    citations: dict,
) -> tuple[CHAIModelCard, dict]:
    """Post-fill a single critical field with enhanced context."""
    client, model, config = _postfill_client()
    if client is None or not model:
        return chai_card, citations
    
    context_block = _build_context_block(seed_pages, citations, max_chars=50000)
    val, ev = await _postfill_one_field(client, model, field_name, context_block, config=config)
    
    if val:
        setattr(chai_card, field_name, val)
        if ev:
            citations[f"postfill.{field_name}"] = ev
    
    return chai_card, citations


async def _postfill_missing_fields(
    chai_card: CHAIModelCard,
    seed_pages: list[dict],
    citations: dict,
    *,
    max_fields: int = 74,  # Process all CHAI fields
    pass_name: str = "default",
) -> tuple[CHAIModelCard, dict]:
    """
    For any empty CHAI field, ask Gemini to fill it using (seed_pages + citations) as context.
    Adds citations under 'postfill.<field>'.
    """
    empty_fields = _collect_empty_chai_fields(chai_card)[:max_fields]
    if not empty_fields:
        return chai_card, citations

    client, model, config = _postfill_client()
    if client is None or not model:
        return chai_card, citations

    context_block = _build_context_block(seed_pages, citations)

    for fname in empty_fields:
        val, ev = await _postfill_one_field(client, model, fname, context_block, config=config)
        if val:
            setattr(chai_card, fname, val)
            if ev:
                citations[f"postfill.{fname}"] = ev

    return chai_card, citations



# ------------------------- main pipeline -------------------------

class CardGenPipeline:
    """
    Gemini-as-Agent pipeline that outputs a CHAIModelCard and artifacts.
    Public return shape: (chai_card, sources, content)
    """

    def __init__(self, out_dir: str | Path = "outputs", use_web_discovery: bool = True):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.use_web_discovery = use_web_discovery

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def discover_model_sources(self, model_name: str, developer_name: str = "", application_url: str = "") -> Dict[str, Any]:
        """
        Discover sources for the model, prioritizing the application URL if provided.
        """
        # If application URL is provided, prioritize it with second-hop scraping
        if application_url:
            try:
                # Use second-hop scraper for user inputted URL
                from scrapers.robust_scraper_v2 import RobustWebScraper
                scraper = RobustWebScraper()
                
                # Extract content with second-hop functionality
                app_result = await scraper.extract_content_with_second_hop(application_url, model_name)
                
                if app_result.get('status') == 'success':
                    return {
                        "application_url": application_url,
                        "application_content": app_result.get("clean_text", ""),
                        "application_title": app_result.get("title", ""),
                        "application_metadata": app_result.get("metadata", {}),
                        "second_hop_content": app_result.get("second_hop_content", []),
                        "second_hop_count": app_result.get("second_hop_count", 0),
                        "total_text_length": app_result.get("total_text_length", len(app_result.get("clean_text", ""))),
                        "priority_source": True,
                        "model_name": model_name,
                        "developer_name": developer_name
                    }
                else:
                    # Fallback to regular fetch if second-hop fails
                    from utils.web_search import fetch_many
                    app_pages = await fetch_many([application_url])
                    if app_pages and app_pages[0]:
                        app_page = app_pages[0]
                        return {
                            "application_url": application_url,
                            "application_content": app_page.get("text", ""),
                            "priority_source": True,
                            "model_name": model_name,
                            "developer_name": developer_name
                        }
            except Exception as e:
                print(f"Warning: Second-hop scraping failed for {application_url}: {e}")
                # Fallback to regular fetch
                try:
                    from utils.web_search import fetch_many
                    app_pages = await fetch_many([application_url])
                    if app_pages and app_pages[0]:
                        app_page = app_pages[0]
                        return {
                            "application_url": application_url,
                            "application_content": app_page.get("text", ""),
                            "priority_source": True,
                            "model_name": model_name,
                            "developer_name": developer_name
                        }
                except Exception:
                    pass
        
        # Fall back to regular discovery
        discovered: List[Dict[str, Any]] = []
        seed_pages_web: List[Dict[str, Any]] = []
        if self.use_web_discovery:
            try:
                discovered, seed_pages_web = await discover_and_fetch(model_name, developer_name, top_k=5)
            except Exception:
                discovered, seed_pages_web = ([], [])
        
        return {
            "discovered": discovered,
            "seed_pages_web": seed_pages_web,
            "model_name": model_name,
            "developer_name": developer_name,
            "application_url": application_url
        }

    async def extract_content_from_sources(self, sources: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract content from discovered sources.
        """
        # This is a placeholder - in a real implementation, this would extract content
        # from the sources and return structured data
        return {
            "sources": sources,
            "extracted_content": "Content extraction placeholder"
        }

    async def generate_chai_model_card(self, model_name: str, extracted_content: Dict[str, Any], developer_name: str = "", application_url: str = "") -> CHAIModelCard:
        """
        Generate a CHAI model card using the extracted content and user inputs.
        """
        # Use the existing generate_model_card method but with application URL support
        return await self.generate_model_card(
            model_name=model_name,
            developer_name=developer_name,
            application_url=application_url
        )

    async def generate_model_card(
        self,
        model_name: str,
        developer_name: str = "",
        application_url: str = "",
        *,
        iters: int = 5,
        coverage_target: float = 0.75,
        finalize_policy: str = "not_specified",  # or "none"
        write_files: bool = True,
        file_prefix: str | None = None,
    ) -> Tuple[CHAIModelCard, Dict, Dict]:
        """
        Generate model card with adaptive iteration count based on initial completeness.
        """
        """
        Returns:
          - chai_card: CHAIModelCard (flat dataclass)
          - sources:   {"agent": "gemini", "citations": {...}, "hint": str,
                        "web_search": {...}, "publications": [...], "fda": [...],
                        "postfill": {"ran": bool}}
          - content:   {"json": str, "markdown": str, "xml": str, "paths": PipelineOutputs|None}
        """
        model_hint = f"{model_name} ({developer_name})" if developer_name else model_name

        # 0) Discovery (DuckDuckGo) + prefetch top pages (WEB ONLY for first pass)
        discovered: List[Dict[str, Any]] = []
        seed_pages_web: List[Dict[str, Any]] = []
        
        # Prioritize application URL if provided with second-hop scraping
        if application_url:
            try:
                # Use second-hop scraper for user inputted URL
                from scrapers.robust_scraper_v2 import RobustWebScraper
                scraper = RobustWebScraper()
                
                # Extract content with second-hop functionality
                app_result = await scraper.extract_content_with_second_hop(application_url, model_name)
                
                if app_result.get('status') == 'success':
                    # Add application URL as highest priority source with enhanced content
                    seed_pages_web.insert(0, {
                        "url": application_url,
                        "text": app_result.get("clean_text", ""),
                        "title": app_result.get("title", ""),
                        "second_hop_content": app_result.get("second_hop_content", []),
                        "second_hop_count": app_result.get("second_hop_count", 0),
                        "total_text_length": app_result.get("total_text_length", len(app_result.get("clean_text", ""))),
                        "metadata": app_result.get("metadata", {}),
                        "priority": "user_inputted"
                    })
                    print(f"✅ Enhanced application URL with second-hop: {app_result.get('second_hop_count', 0)} additional sections")
                else:
                    # Fallback to regular fetch if second-hop fails
                    from utils.web_search import fetch_many
                    app_pages = await fetch_many([application_url])
                    if app_pages and app_pages[0]:
                        app_page = app_pages[0]
                        seed_pages_web.insert(0, {
                            "url": application_url,
                            "text": app_page.get("text", ""),
                            "title": app_page.get("title", ""),
                            "priority": "user_inputted"
                        })
            except Exception as e:
                print(f"Warning: Second-hop scraping failed for {application_url}: {e}")
                # Fallback to regular fetch
                try:
                    from utils.web_search import fetch_many
                    app_pages = await fetch_many([application_url])
                    if app_pages and app_pages[0]:
                        app_page = app_pages[0]
                        seed_pages_web.insert(0, {
                            "url": application_url,
                            "text": app_page.get("text", ""),
                            "title": app_page.get("title", ""),
                            "priority": "user_inputted"
                        })
                except Exception:
                    pass
        
        if self.use_web_discovery:
            try:
                discovered, additional_seed_pages = await discover_and_fetch(model_name, developer_name, top_k=10)
                # Add additional discovered pages (but don't override application URL)
                seed_pages_web.extend(additional_seed_pages)
            except Exception:
                pass

        # top URLs (bias early targets) - prioritize application URL
        top_urls = []
        if application_url:
            top_urls.append(application_url)
        top_urls.extend([s["url"] for s in discovered[:4] if s.get("url")])  # Take 4 more to keep total at 5

        # 1) Run Gemini agent with WEB ONLY seed (no publications/FDA yet)
        # Adaptive iteration: Adjust based on initial completeness estimate
        # If we have many sources, we may need more iterations
        estimated_iters = iters
        if len(seed_pages_web) > 8 or len(discovered) > 15:
            # More sources available, allow more iterations to process them
            estimated_iters = min(iters + 2, 8)  # Cap at 8 iterations
            print(f"📊 Adaptive iteration: Increased to {estimated_iters} iterations based on source count")
        
        try:
            agent_card_like, citations = await gemini_run_async(
                model_hint=model_hint,
                max_iters=estimated_iters,
                coverage_target=coverage_target,
                finalize_policy=finalize_policy,
                developer=developer_name,
                seed_urls=top_urls,
                seed_pages=list(seed_pages_web),
            )
        except TypeError:
            agent_card_like, citations = await gemini_run_async(
                model_hint=model_hint,
                max_iters=estimated_iters,
                coverage_target=coverage_target,
                finalize_policy=finalize_policy,
                developer=developer_name,
            )

        # 2) Normalize agent output to a plain dict
        if hasattr(agent_card_like, "model_dump"):
            agent_dump = agent_card_like.model_dump()
        elif isinstance(agent_card_like, dict):
            agent_dump = agent_card_like
        else:
            agent_dump = getattr(agent_card_like, "__dict__", {}) or {}

        # 3) Map nested agent fields → CHAI flat dataclass
        chai_card = _map_agent_dump_to_chai(agent_dump, user_model_name=model_name, user_developer_name=developer_name, user_application_url=application_url)

        # ---- NOW fetch Publications + FDA (late) and use them for post-fill only ----
        publications: List[Dict[str, Any]] = []
        seed_pages_pubs: List[Dict[str, Any]] = []
        try:
            publications, seed_pages_pubs = await _fetch_publications(model_name)
        except Exception:
            publications, seed_pages_pubs = ([], [])

        fda_records: List[Dict[str, Any]] = []
        seed_pages_fda: List[Dict[str, Any]] = []
        if _looks_clinical(model_hint):
            try:
                fda_records, seed_pages_fda = await _fetch_fda_records(model_name, developer_name)
            except Exception:
                fda_records, seed_pages_fda = ([], [])

        # Merge all seed pages (web + pubs + fda) for POST-FILL
        seed_pages_post: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        for group in (seed_pages_web, seed_pages_pubs, seed_pages_fda):
            for p in group:
                u = (p.get("url") or "").strip()
                t = (p.get("text") or "").strip()
                if not u or not t or u in seen_urls:
                    continue
                seen_urls.add(u)
                seed_pages_post.append({"url": u, "text": t})

        # 3.5) Multi-pass Post-fill: have Gemini fill remaining blanks using the expanded context
        postfill_ran = False
        try:
            # Pass 1: Fill from seed_pages (high confidence sources)
            chai_card, citations = await _postfill_missing_fields(
                chai_card=chai_card,
                seed_pages=seed_pages_post,
                citations=citations,
                max_fields=74,  # Process all CHAI fields
                pass_name="seed_pages"
            )
            
            # Pass 2: Fill from citations (medium confidence)
            chai_card, citations = await _postfill_missing_fields(
                chai_card=chai_card,
                seed_pages=[],  # Use only citations in this pass
                citations=citations,
                max_fields=74,
                pass_name="citations"
            )
            
            # Pass 3: Targeted fill for critical missing fields
            critical_missing = [
                "release_date", "global_availability", "how_to_use",
                "developer_supplied_warnings", "model_limitations",
                "training_data", "usefulness_efficacy_result"
            ]
            for field in critical_missing:
                if not getattr(chai_card, field, None) or not str(getattr(chai_card, field, "")).strip():
                    chai_card, citations = await _postfill_one_critical_field(
                        chai_card=chai_card,
                        field_name=field,
                        seed_pages=seed_pages_post,
                        citations=citations
                    )
            
            postfill_ran = True
        except Exception as e:
            print(f"Warning: Post-fill failed: {e}")
            postfill_ran = False  # safe failure; continue

        # 4) Build artifacts
        json_text = chai_card.to_json()
        md_text = chai_card.to_markdown(citations=citations)
        xml_text = chai_card.to_xml()

        outputs: Optional[PipelineOutputs] = None
        if write_files:
            outputs = self._write_all(
                chai_card=chai_card,
                citations=citations,
                base_name=(file_prefix or _slugify(model_name)) + "-" + _now_stamp(),
                json_text=json_text,
                md_text=md_text,
                xml_text=xml_text,
            )

        sources = {
            "agent": "gemini",
            "citations": citations,
            "hint": model_hint,
            "web_search": {
                "discovered": discovered,
                "top_urls": top_urls,
            },
            "publications": publications,
            "fda": fda_records,
            "postfill": {"ran": postfill_ran},
        }
        content = {
            "json": json_text,
            "markdown": md_text,
            "xml": xml_text,
            "paths": outputs,
        }
        # Generate scoring report
        scorer = ModelCardScorer()
        model_card_dict = chai_card.model_dump() if hasattr(chai_card, 'model_dump') else chai_card.__dict__
        score = scorer.score_model_card(model_card_dict)
        
        # Add scoring information to sources
        sources["scoring"] = {
            "completion_percentage": score.completion_percentage,
            "clinical_usability_score": score.clinical_usability_score,
            "clinical_usability_level": score.clinical_usability_level.value,
            "overall_rating": score.overall_rating,
            "total_fields": score.total_fields,
            "filled_fields": score.filled_fields,
            "critical_missing_fields": score.critical_missing_fields,
            "recommendations_count": len(score.recommendations),
            "quality_issues_count": len(score.quality_issues)
        }
        
        # Add detailed scoring report to content
        scoring_report = format_score_report(score)
        content["scoring_report"] = scoring_report
        content["scoring_summary"] = get_score_summary(score)
        
        # Write scoring report to file if requested
        if write_files and outputs:
            scoring_path = outputs.json_path.with_suffix(".scoring.txt")
            scoring_path.write_text(scoring_report, encoding="utf-8")
            outputs.scoring_txt = scoring_path
        
        return chai_card, sources, content

    # ------------------------- writers -------------------------

    def _write_all(
        self,
        *,
        chai_card: CHAIModelCard,
        citations: Dict,
        base_name: str,
        json_text: str,
        md_text: str,
        xml_text: str,
    ) -> PipelineOutputs:
        base = self.out_dir / base_name
        json_path = base.with_suffix(".json")
        md_path = base.with_suffix(".md")
        xml_path = base.with_suffix(".xml")
        cites_path = base.with_suffix(".citations.json")

        json_path.write_text(json_text, encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")
        xml_path.write_text(xml_text, encoding="utf-8")

        if citations:
            cites_path.write_text(json.dumps(citations, indent=2), encoding="utf-8")
        else:
            cites_path = None

        return PipelineOutputs(
            json_path=json_path,
            md_path=md_path,
            xml_path=xml_path,
            citations_json_path=cites_path,
        )


# ------------------------- CLI convenience -------------------------

async def _amain():
    import argparse
    p = argparse.ArgumentParser(description="Generate a CHAI model card via Gemini agent")
    p.add_argument("--model-name", required=True)
    p.add_argument("--developer-name", default="")
    p.add_argument("--iters", type=int, default=3)
    p.add_argument("--coverage", type=float, default=0.60)
    p.add_argument("--finalize", default="not_specified", choices=["not_specified", "none"])
    p.add_argument("--out-dir", default="outputs")
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--prefix", default=None)
    p.add_argument("--no-discovery", action="store_true", help="Disable DuckDuckGo discovery step")
    args = p.parse_args()

    pipeline = CardGenPipeline(out_dir=args.out_dir, use_web_discovery=not args.no_discovery)
    chai_card, sources, content = await pipeline.generate_model_card(
        model_name=args.model_name,
        developer_name=args.developer_name,
        iters=args.iters,
        coverage_target=args.coverage,
        finalize_policy=args.finalize,
        write_files=not args.no_write,
        file_prefix=args.prefix,
    )
    print(chai_card.to_json())
    if content.get("paths"):
        outs: PipelineOutputs = content["paths"]
        print("\nArtifacts:")
        if outs.json_path: print(f"- {outs.json_path}")
        if outs.md_path: print(f"- {outs.md_path}")
        if outs.xml_path: print(f"- {outs.xml_path}")
        if outs.citations_json_path: print(f"- {outs.citations_json_path}")
        if outs.scoring_txt: print(f"- {outs.scoring_txt}")
        
        # Show scoring summary
        if content.get("scoring_summary"):
            summary = content["scoring_summary"]
            print(f"\n📊 SCORING SUMMARY:")
            print(f"   Completion: {summary['completion_percentage']}%")
            print(f"   Clinical Usability: {summary['clinical_usability_level'].upper()}")
            print(f"   Overall Rating: {summary['overall_rating']}")


def main():
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
