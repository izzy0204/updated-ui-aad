from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import re


@dataclass
class CHAIModelCard:
    """
    CHAI Applied Model Card Data Structure (v0.3)
    Categories: Metadata, Uses & Directions, Warnings, Trust Ingredients,
    Key Metrics, and Resources.
    """

    # 1) METADATA
    model_name: str = ""
    developer: str = ""
    application_url: str = ""
    inquiries_or_to_report_an_issue: str = ""
    release_stage: str = ""
    release_date: str = ""
    version: str = ""
    regulatory_approval_status_if_applicable: str = ""
    global_availability: str = ""
    summary: str = ""
    keywords: List[str] = field(default_factory=list)

    # 2) USES & DIRECTIONS
    intended_use_and_workflow: str = ""
    primary_intended_users: str = ""
    necessary_knowledge_expertise: str = ""
    how_to_use: str = ""
    targeted_patient_population: str = ""
    patient_consent_or_disclosure_required_or_suggested: str = ""

    # 3) WARNINGS
    developer_supplied_warnings: str = ""
    model_limitations: str = ""
    skin_type_representation_and_equity: str = ""
    clinical_risk_level: str = ""

    # 4) TRUST INGREDIENTS
    ai_system_facts: str = ""
    model_type: str = ""
    interaction_with_other_systems: str = ""
    outcomes_and_output: str = ""
    type_and_value_of_solution_output: str = ""
    explanation_for_how_an_output_is_generated: str = ""
    foundation_models_used_in_application_if_applicable: List[str] = field(default_factory=list)
    input_data_source: str = ""
    output_input_data_type: str = ""
    development_data_characterization: str = ""
    training_data: str = ""
    exclusion_inclusion_criteria: str = ""
    demographic_representativeness: str = ""
    dataset_doi_if_applicable: str = ""
    dataset_transparency: str = ""
    validation_test_dataset: str = ""
    timeline_of_data_collection: str = ""
    skin_tone_diversity: str = ""
    did_the_data_collection_process_undergo_ethical_review: str = ""
    ethical_review_board_oversight: str = ""
    irb_approval: str = ""
    relevance_of_training_data_to_intended_population: str = ""
    bias_mitigation_approaches: str = ""
    ongoing_maintenance: str = ""
    security_and_compliance_environment_practices_or_accreditations_if_applicable: str = ""
    transparency_intelligibility_and_accountability_mechanisms_if_applicable: str = ""
    transparency_information: str = ""
    funding_source_of_the_technical_implementation: str = ""
    third_party_information_if_applicable: str = ""

    # 5) KEY METRICS
    # Usefulness / Efficacy
    usefulness_efficacy_goal_of_metrics: str = ""
    usefulness_efficacy_result: str = ""
    usefulness_efficacy_interpretation: str = ""
    usefulness_efficacy_test_type: str = ""
    usefulness_efficacy_testing_data_description: str = ""
    usefulness_efficacy_validation_process_and_justification: str = ""
    usefulness_efficacy_auroc_accuracy_etc: str = ""

    # Fairness & Equity
    fairness_equity_goal_of_metrics: str = ""
    fairness_equity_result: str = ""
    fairness_equity_interpretation: str = ""
    fairness_equity_test_type: str = ""
    fairness_equity_testing_data_description: str = ""
    fairness_equity_validation_process_and_justification: str = ""

    # Safety & Reliability
    safety_reliability_goal_of_metrics: str = ""
    safety_reliability_result: str = ""
    safety_reliability_interpretation: str = ""
    safety_reliability_test_type: str = ""
    safety_reliability_testing_data_description: str = ""
    safety_reliability_validation_process_and_justification: str = ""

    # 6) RESOURCES
    evaluation_references_if_available: str = ""
    clinical_trial_if_available: str = ""
    peer_reviewed_publications: str = ""
    reimbursement_status_if_applicable: str = ""
    stakeholders_consulted_during_design_of_solution: str = ""

    # --- generation metadata ---
    extraction_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # ---------- EXPORTS ----------
    def to_json(self) -> str:
        """Export model card to JSON format."""
        return json.dumps(self.__dict__, indent=2, default=str)

    def to_xml(self) -> str:
        """Export model card to a simple CHAI XML."""
        root = ET.Element("AppliedModelCard", attrib={"xmlns": "https://mc.chai.org/v0.3/schema.xsd"})

        # Metadata
        meta = ET.SubElement(root, "Metadata")
        ET.SubElement(meta, "ModelName").text = self.model_name
        ET.SubElement(meta, "Developer").text = self.developer
        ET.SubElement(meta, "ApplicationURL").text = self.application_url
        ET.SubElement(meta, "InquiriesOrToReportAnIssue").text = self.inquiries_or_to_report_an_issue
        ET.SubElement(meta, "ReleaseStage").text = self.release_stage
        ET.SubElement(meta, "ReleaseDate").text = self.release_date
        ET.SubElement(meta, "Version").text = self.version
        ET.SubElement(meta, "RegulatoryApprovalStatusIfApplicable").text = self.regulatory_approval_status_if_applicable
        ET.SubElement(meta, "GlobalAvailability").text = self.global_availability
        ET.SubElement(meta, "Summary").text = self.summary
        ET.SubElement(meta, "Keywords").text = ", ".join(self.keywords) if self.keywords else ""

        # Uses & Directions
        uses = ET.SubElement(root, "UsesAndDirections")
        ET.SubElement(uses, "IntendedUseAndWorkflow").text = self.intended_use_and_workflow
        ET.SubElement(uses, "PrimaryIntendedUsers").text = self.primary_intended_users
        ET.SubElement(uses, "NecessaryKnowledgeExpertise").text = self.necessary_knowledge_expertise
        ET.SubElement(uses, "HowToUse").text = self.how_to_use
        ET.SubElement(uses, "TargetedPatientPopulation").text = self.targeted_patient_population
        ET.SubElement(uses, "PatientConsentOrDisclosureRequiredOrSuggested").text = self.patient_consent_or_disclosure_required_or_suggested

        # Warnings
        warn = ET.SubElement(root, "Warnings")
        ET.SubElement(warn, "DeveloperSuppliedWarnings").text = self.developer_supplied_warnings
        ET.SubElement(warn, "ModelLimitations").text = self.model_limitations
        ET.SubElement(warn, "SkinTypeRepresentationAndEquity").text = self.skin_type_representation_and_equity
        ET.SubElement(warn, "ClinicalRiskLevel").text = self.clinical_risk_level

        # Trust Ingredients
        trust = ET.SubElement(root, "TrustIngredients")
        ET.SubElement(trust, "AISystemFacts").text = self.ai_system_facts
        ET.SubElement(trust, "ModelType").text = self.model_type
        ET.SubElement(trust, "InteractionWithOtherSystems").text = self.interaction_with_other_systems
        ET.SubElement(trust, "OutcomesAndOutput").text = self.outcomes_and_output
        ET.SubElement(trust, "TypeAndValueOfSolutionOutput").text = self.type_and_value_of_solution_output
        ET.SubElement(trust, "ExplanationForHowAnOutputIsGenerated").text = self.explanation_for_how_an_output_is_generated
        ET.SubElement(trust, "FoundationModelsUsedInApplicationIfApplicable").text = ", ".join(self.foundation_models_used_in_application_if_applicable) if self.foundation_models_used_in_application_if_applicable else ""
        ET.SubElement(trust, "InputDataSource").text = self.input_data_source
        ET.SubElement(trust, "OutputInputDataType").text = self.output_input_data_type
        ET.SubElement(trust, "DevelopmentDataCharacterization").text = self.development_data_characterization
        ET.SubElement(trust, "TrainingData").text = self.training_data
        ET.SubElement(trust, "ExclusionInclusionCriteria").text = self.exclusion_inclusion_criteria
        ET.SubElement(trust, "DemographicRepresentativeness").text = self.demographic_representativeness
        ET.SubElement(trust, "DatasetDOIIfApplicable").text = self.dataset_doi_if_applicable
        ET.SubElement(trust, "DatasetTransparency").text = self.dataset_transparency
        ET.SubElement(trust, "ValidationTestDataset").text = self.validation_test_dataset
        ET.SubElement(trust, "TimelineOfDataCollection").text = self.timeline_of_data_collection
        ET.SubElement(trust, "SkinToneDiversity").text = self.skin_tone_diversity
        ET.SubElement(trust, "DidTheDataCollectionProcessUndergoEthicalReview").text = self.did_the_data_collection_process_undergo_ethical_review
        ET.SubElement(trust, "EthicalReviewBoardOversight").text = self.ethical_review_board_oversight
        ET.SubElement(trust, "IRBApproval").text = self.irb_approval
        ET.SubElement(trust, "RelevanceOfTrainingDataToIntendedPopulation").text = self.relevance_of_training_data_to_intended_population
        ET.SubElement(trust, "BiasMitigationApproaches").text = self.bias_mitigation_approaches
        ET.SubElement(trust, "OngoingMaintenance").text = self.ongoing_maintenance
        ET.SubElement(trust, "SecurityAndComplianceEnvironmentPracticesOrAccreditationsIfApplicable").text = self.security_and_compliance_environment_practices_or_accreditations_if_applicable
        ET.SubElement(trust, "TransparencyIntelligibilityAndAccountabilityMechanismsIfApplicable").text = self.transparency_intelligibility_and_accountability_mechanisms_if_applicable
        ET.SubElement(trust, "TransparencyInformation").text = self.transparency_information
        ET.SubElement(trust, "FundingSourceOfTheTechnicalImplementation").text = self.funding_source_of_the_technical_implementation
        ET.SubElement(trust, "ThirdPartyInformationIfApplicable").text = self.third_party_information_if_applicable

        # Key Metrics
        km = ET.SubElement(root, "KeyMetrics")

        u = ET.SubElement(km, "UsefulnessEfficacy")
        ET.SubElement(u, "GoalOfMetrics").text = self.usefulness_efficacy_goal_of_metrics
        ET.SubElement(u, "Result").text = self.usefulness_efficacy_result
        ET.SubElement(u, "Interpretation").text = self.usefulness_efficacy_interpretation
        ET.SubElement(u, "TestType").text = self.usefulness_efficacy_test_type
        ET.SubElement(u, "TestingDataDescription").text = self.usefulness_efficacy_testing_data_description
        ET.SubElement(u, "ValidationProcessAndJustification").text = self.usefulness_efficacy_validation_process_and_justification
        ET.SubElement(u, "AUROCAccuracyEtc").text = self.usefulness_efficacy_auroc_accuracy_etc

        f = ET.SubElement(km, "FairnessEquity")
        ET.SubElement(f, "GoalOfMetrics").text = self.fairness_equity_goal_of_metrics
        ET.SubElement(f, "Result").text = self.fairness_equity_result
        ET.SubElement(f, "Interpretation").text = self.fairness_equity_interpretation
        ET.SubElement(f, "TestType").text = self.fairness_equity_test_type
        ET.SubElement(f, "TestingDataDescription").text = self.fairness_equity_testing_data_description
        ET.SubElement(f, "ValidationProcessAndJustification").text = self.fairness_equity_validation_process_and_justification

        s = ET.SubElement(km, "SafetyReliability")
        ET.SubElement(s, "GoalOfMetrics").text = self.safety_reliability_goal_of_metrics
        ET.SubElement(s, "Result").text = self.safety_reliability_result
        ET.SubElement(s, "Interpretation").text = self.safety_reliability_interpretation
        ET.SubElement(s, "TestType").text = self.safety_reliability_test_type
        ET.SubElement(s, "TestingDataDescription").text = self.safety_reliability_testing_data_description
        ET.SubElement(s, "ValidationProcessAndJustification").text = self.safety_reliability_validation_process_and_justification

        # Resources
        res = ET.SubElement(root, "Resources")
        ET.SubElement(res, "EvaluationReferencesIfAvailable").text = self.evaluation_references_if_available
        ET.SubElement(res, "ClinicalTrialIfAvailable").text = self.clinical_trial_if_available
        ET.SubElement(res, "PeerReviewedPublications").text = self.peer_reviewed_publications
        ET.SubElement(res, "ReimbursementStatusIfApplicable").text = self.reimbursement_status_if_applicable
        ET.SubElement(res, "StakeholdersConsultedDuringDesignOfSolution").text = self.stakeholders_consulted_during_design_of_solution

        return ET.tostring(root, encoding="unicode")

    def to_markdown(self, citations: Optional[Dict[str, List[Dict[str, str]]]] = None) -> str:
        """Export model card to Markdown format (covers all required fields).

        Citation policy:
        - If citations are provided, every non-placeholder sentence in the model card body
          receives at least one inline numeric citation like " [3]" or " [2,5]".
        """

        def _is_placeholder(val: object) -> bool:
            if val is None:
                return True
            if isinstance(val, list):
                return len([x for x in val if str(x).strip()]) == 0
            s = str(val).strip()
            return (not s) or s.lower() in {"not specified", "unknown", "tbd", "n/a", "na"}

        def _urls_from_citations(field_name: str) -> List[str]:
            if not citations or not isinstance(citations, dict):
                return []
            urls: List[str] = []
            for key in (field_name, f"postfill.{field_name}"):
                lst = citations.get(key)
                if not isinstance(lst, list):
                    continue
                for item in lst:
                    if not isinstance(item, dict):
                        continue
                    u = (item.get("url") or "").strip()
                    if u and u not in urls:
                        urls.append(u)
            return urls

        def _append_citations_per_sentence(text: str, cite_suffix: str) -> str:
            """Append citations to every sentence that doesn't already end with a citation."""
            if not text or not cite_suffix:
                return text

            # Keep existing explicit numeric citations if already present at sentence end.
            parts = re.split(r"(\n+)", text)  # preserve paragraph breaks
            out: List[str] = []
            for part in parts:
                if part.startswith("\n"):
                    out.append(part)
                    continue

                chunk = part.strip()
                if not chunk:
                    out.append(part)
                    continue

                # Sentence-ish split; good enough for model card prose.
                sentences = re.split(r"(?<=[.!?])\s+", chunk)
                patched: List[str] = []
                for s in sentences:
                    ss = s.strip()
                    if not ss:
                        continue
                    if re.search(r"\s\[\d+(?:,\d+)*\]\s*$", ss):
                        patched.append(ss)
                    else:
                        patched.append(ss + cite_suffix)
                out.append(" ".join(patched))
            return "".join(out)

        def _format_value(field_name: str, value: object) -> str:
            if isinstance(value, list):
                v = ", ".join(str(x).strip() for x in value if str(x).strip())
            else:
                v = str(value).strip() if value is not None else ""

            if _is_placeholder(v):
                return "Not specified"

            if not citations:
                return v

            urls = _urls_from_citations(field_name)
            nums = sorted({url_to_num.get(u) for u in urls if u in url_to_num})
            nums = [n for n in nums if isinstance(n, int)]
            cite_suffix = f" [{','.join(map(str, nums))}]" if nums else ""
            rendered = _append_citations_per_sentence(v, cite_suffix)
            # Keep multi-line values inside the bullet list item.
            rendered = rendered.replace("\n", "\n  ")
            return rendered

        # --- Build reference numbering ---
        url_to_num: Dict[str, int] = {}
        ordered_urls: List[str] = []

        if citations and isinstance(citations, dict):
            sources_metadata = citations.get("_sources_metadata", {}) if isinstance(citations.get("_sources_metadata", {}), dict) else {}

            # Prefer the explicit metadata list if present (it includes implicit + explicit sources),
            # otherwise fall back to URLs observed in field citation lists.
            candidate_urls: List[str] = []
            if sources_metadata:
                candidate_urls = list(sources_metadata.keys())
            else:
                seen = set()
                for k, lst in citations.items():
                    if k == "_sources_metadata" or not isinstance(lst, list):
                        continue
                    for it in lst:
                        if not isinstance(it, dict):
                            continue
                        u = (it.get("url") or "").strip()
                        if u and u not in seen:
                            seen.add(u)
                            candidate_urls.append(u)

            ordered_urls = sorted([u for u in candidate_urls if str(u).strip()])
            url_to_num = {u: i for i, u in enumerate(ordered_urls, 1)}

        def _line(field_name: str, label: str, value: object) -> str:
            return f"- **{label}:** {_format_value(field_name, value)}"

        lines: List[str] = []
        lines.append(f"# {self.model_name or 'Unnamed Model'} — CHAI Model Card (v0.3)")
        lines.append("")
        lines.append("## 1) Metadata")
        lines.append(_line("model_name", "Model Name", self.model_name))
        lines.append(_line("developer", "Developer", self.developer))
        lines.append(_line("application_url", "Application URL", self.application_url))
        lines.append(_line("inquiries_or_to_report_an_issue", "Inquiries or to report an issue", self.inquiries_or_to_report_an_issue))
        lines.append(_line("release_stage", "Release Stage", self.release_stage))
        lines.append(_line("release_date", "Release Date", self.release_date))
        lines.append(_line("version", "Version", self.version))
        lines.append(_line("regulatory_approval_status_if_applicable", "Regulatory Approval Status, if applicable", self.regulatory_approval_status_if_applicable))
        lines.append(_line("global_availability", "Global Availability", self.global_availability))
        lines.append(_line("summary", "Summary", self.summary))
        lines.append(_line("keywords", "Keywords", self.keywords))
        lines.append("")

        lines.append("## 2) Uses & Directions")
        lines.append(_line("intended_use_and_workflow", "Intended Use & Workflow", self.intended_use_and_workflow))
        lines.append(_line("primary_intended_users", "Primary Intended Users", self.primary_intended_users))
        lines.append(_line("necessary_knowledge_expertise", "Necessary knowledge/expertise", self.necessary_knowledge_expertise))
        lines.append(_line("how_to_use", "How to Use", self.how_to_use))
        lines.append(_line("targeted_patient_population", "Targeted patient population", self.targeted_patient_population))
        lines.append(_line("patient_consent_or_disclosure_required_or_suggested", "Patient consent or disclosure required or suggested?", self.patient_consent_or_disclosure_required_or_suggested))
        lines.append("")

        lines.append("## 3) Warnings")
        lines.append(_line("developer_supplied_warnings", "Developer-Supplied Warnings", self.developer_supplied_warnings))
        lines.append(_line("model_limitations", "Model Limitations", self.model_limitations))
        lines.append(_line("skin_type_representation_and_equity", "Skin type representation & equity", self.skin_type_representation_and_equity))
        lines.append(_line("clinical_risk_level", "Clinical Risk Level", self.clinical_risk_level))
        lines.append("")

        lines.append("## 4) Trust Ingredients")
        lines.append(_line("ai_system_facts", "AI System Facts", self.ai_system_facts))
        lines.append(_line("model_type", "Model Type", self.model_type))
        lines.append(_line("interaction_with_other_systems", "Interaction with other systems", self.interaction_with_other_systems))
        lines.append(_line("outcomes_and_output", "Outcomes & Output", self.outcomes_and_output))
        lines.append(_line("type_and_value_of_solution_output", "Type & Value of Solution Output", self.type_and_value_of_solution_output))
        lines.append(_line("explanation_for_how_an_output_is_generated", "Explanation for how an output is generated", self.explanation_for_how_an_output_is_generated))
        lines.append(_line("foundation_models_used_in_application_if_applicable", "Foundation Models Used in application, if applicable", self.foundation_models_used_in_application_if_applicable))
        lines.append(_line("input_data_source", "Input Data Source", self.input_data_source))
        lines.append(_line("output_input_data_type", "Output/Input Data Type", self.output_input_data_type))
        lines.append(_line("development_data_characterization", "Development Data Characterization", self.development_data_characterization))
        lines.append(_line("training_data", "Training Data", self.training_data))
        lines.append(_line("exclusion_inclusion_criteria", "Exclusion/Inclusion Criteria", self.exclusion_inclusion_criteria))
        lines.append(_line("demographic_representativeness", "Demographic representativeness", self.demographic_representativeness))
        lines.append(_line("dataset_doi_if_applicable", "Dataset (DOI if applicable)", self.dataset_doi_if_applicable))
        lines.append(_line("dataset_transparency", "Dataset Transparency", self.dataset_transparency))
        lines.append(_line("validation_test_dataset", "Validation/Test Dataset", self.validation_test_dataset))
        lines.append(_line("timeline_of_data_collection", "Timeline of Data collection", self.timeline_of_data_collection))
        lines.append(_line("skin_tone_diversity", "Skin tone diversity", self.skin_tone_diversity))
        lines.append(_line("did_the_data_collection_process_undergo_ethical_review", "Did the data collection process undergo ethical review", self.did_the_data_collection_process_undergo_ethical_review))
        lines.append(_line("ethical_review_board_oversight", "Ethical Review Board Oversight", self.ethical_review_board_oversight))
        lines.append(_line("irb_approval", "IRB Approval", self.irb_approval))
        lines.append(_line("relevance_of_training_data_to_intended_population", "Relevance of training data to intended population", self.relevance_of_training_data_to_intended_population))
        lines.append(_line("bias_mitigation_approaches", "Bias Mitigation Approaches", self.bias_mitigation_approaches))
        lines.append(_line("ongoing_maintenance", "Ongoing Maintenance", self.ongoing_maintenance))
        lines.append(_line("security_and_compliance_environment_practices_or_accreditations_if_applicable", "Security and compliance environment practices or accreditations, if applicable", self.security_and_compliance_environment_practices_or_accreditations_if_applicable))
        lines.append(_line("transparency_intelligibility_and_accountability_mechanisms_if_applicable", "Transparency, Intelligibility, and Accountability mechanisms, if applicable", self.transparency_intelligibility_and_accountability_mechanisms_if_applicable))
        lines.append(_line("transparency_information", "Transparency Information", self.transparency_information))
        lines.append(_line("funding_source_of_the_technical_implementation", "Funding Source of the technical implementation", self.funding_source_of_the_technical_implementation))
        lines.append(_line("third_party_information_if_applicable", "3rd Party Information, if applicable", self.third_party_information_if_applicable))
        lines.append("")

        lines.append("## 5) Key Metrics")
        lines.append("### Usefulness / Efficacy")
        lines.append(_line("usefulness_efficacy_goal_of_metrics", "Goal of Metric(s)", self.usefulness_efficacy_goal_of_metrics))
        lines.append(_line("usefulness_efficacy_result", "Result", self.usefulness_efficacy_result))
        lines.append(_line("usefulness_efficacy_interpretation", "Interpretation", self.usefulness_efficacy_interpretation))
        lines.append(_line("usefulness_efficacy_test_type", "Test Type", self.usefulness_efficacy_test_type))
        lines.append(_line("usefulness_efficacy_testing_data_description", "Testing Data Description", self.usefulness_efficacy_testing_data_description))
        lines.append(_line("usefulness_efficacy_validation_process_and_justification", "Validation Process and Justification", self.usefulness_efficacy_validation_process_and_justification))
        lines.append(_line("usefulness_efficacy_auroc_accuracy_etc", "AUROC/Accuracy/etc.", self.usefulness_efficacy_auroc_accuracy_etc))
        lines.append("")

        lines.append("### Fairness & Equity")
        lines.append(_line("fairness_equity_goal_of_metrics", "Goal of Metric(s)", self.fairness_equity_goal_of_metrics))
        lines.append(_line("fairness_equity_result", "Result", self.fairness_equity_result))
        lines.append(_line("fairness_equity_interpretation", "Interpretation", self.fairness_equity_interpretation))
        lines.append(_line("fairness_equity_test_type", "Test Type", self.fairness_equity_test_type))
        lines.append(_line("fairness_equity_testing_data_description", "Testing Data Description", self.fairness_equity_testing_data_description))
        lines.append(_line("fairness_equity_validation_process_and_justification", "Validation Process and Justification", self.fairness_equity_validation_process_and_justification))
        lines.append("")

        lines.append("### Safety & Reliability")
        lines.append(_line("safety_reliability_goal_of_metrics", "Goal of Metric(s)", self.safety_reliability_goal_of_metrics))
        lines.append(_line("safety_reliability_result", "Result", self.safety_reliability_result))
        lines.append(_line("safety_reliability_interpretation", "Interpretation", self.safety_reliability_interpretation))
        lines.append(_line("safety_reliability_test_type", "Test Type", self.safety_reliability_test_type))
        lines.append(_line("safety_reliability_testing_data_description", "Testing Data Description", self.safety_reliability_testing_data_description))
        lines.append(_line("safety_reliability_validation_process_and_justification", "Validation Process and Justification", self.safety_reliability_validation_process_and_justification))
        lines.append("")

        lines.append("## 6) Resources")
        lines.append(_line("evaluation_references_if_available", "Evaluation References, if available", self.evaluation_references_if_available))
        lines.append(_line("clinical_trial_if_available", "Clinical Trial, if available", self.clinical_trial_if_available))
        lines.append(_line("peer_reviewed_publications", "Peer-Reviewed Publication(s)", self.peer_reviewed_publications))
        lines.append(_line("reimbursement_status_if_applicable", "Reimbursement status, if applicable", self.reimbursement_status_if_applicable))
        lines.append(_line("stakeholders_consulted_during_design_of_solution", "Stakeholders consulted during design of solution", self.stakeholders_consulted_during_design_of_solution))

        if citations and ordered_urls:
            lines.append("")
            lines.append("## References")
            lines.extend([f"[{i}] {u}" for i, u in enumerate(ordered_urls, 1)])
        elif citations:
            lines.append("")
            lines.append("## References")
            lines.append("No sources available.")

        lines.append(f"\n---\n*Generated on {self.extraction_timestamp} (CHAI Schema v0.3)*")
        return "\n".join(lines) + "\n"
