from dataclasses import dataclass, field
from typing import Dict, List
import json
import xml.etree.ElementTree as ET
from datetime import datetime


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

    def to_markdown(self) -> str:
        """Export model card to Markdown format (covers all required fields)."""
        md = f"""# {self.model_name or "Unnamed Model"} — CHAI Model Card (v0.3)

## 1) Metadata
- **Model Name:** {self.model_name or "Not specified"}
- **Developer:** {self.developer or "Not specified"}
- **Application URL:** {self.application_url or "Not specified"}
- **Inquiries or to report an issue:** {self.inquiries_or_to_report_an_issue or "Not specified"}
- **Release Stage:** {self.release_stage or "Not specified"}
- **Release Date:** {self.release_date or "Not specified"}
- **Version:** {self.version or "Not specified"}
- **Regulatory Approval Status, if applicable:** {self.regulatory_approval_status_if_applicable or "Not specified"}
- **Global Availability:** {self.global_availability or "Not specified"}
- **Summary:** {self.summary or "Not specified"}
- **Keywords:** {", ".join(self.keywords) if self.keywords else "Not specified"}

## 2) Uses & Directions
- **Intended Use & Workflow:** {self.intended_use_and_workflow or "Not specified"}
- **Primary Intended Users:** {self.primary_intended_users or "Not specified"}
- **Necessary knowledge/expertise:** {self.necessary_knowledge_expertise or "Not specified"}
- **How to Use:** {self.how_to_use or "Not specified"}
- **Targeted patient population:** {self.targeted_patient_population or "Not specified"}
- **Patient consent or disclosure required or suggested?:** {self.patient_consent_or_disclosure_required_or_suggested or "Not specified"}

## 3) Warnings
- **Developer-Supplied Warnings:** {self.developer_supplied_warnings or "Not specified"}
- **Model Limitations:** {self.model_limitations or "Not specified"}
- **Skin type representation & equity:** {self.skin_type_representation_and_equity or "Not specified"}
- **Clinical Risk Level:** {self.clinical_risk_level or "Not specified"}

## 4) Trust Ingredients
- **AI System Facts:** {self.ai_system_facts or "Not specified"}
- **Model Type:** {self.model_type or "Not specified"}
- **Interaction with other systems:** {self.interaction_with_other_systems or "Not specified"}
- **Outcomes & Output:** {self.outcomes_and_output or "Not specified"}
- **Type & Value of Solution Output:** {self.type_and_value_of_solution_output or "Not specified"}
- **Explanation for how an output is generated:** {self.explanation_for_how_an_output_is_generated or "Not specified"}
- **Foundation Models Used in application, if applicable:** {", ".join(self.foundation_models_used_in_application_if_applicable) if self.foundation_models_used_in_application_if_applicable else "Not specified"}
- **Input Data Source:** {self.input_data_source or "Not specified"}
- **Output/Input Data Type:** {self.output_input_data_type or "Not specified"}
- **Development Data Characterization:** {self.development_data_characterization or "Not specified"}
- **Training Data:** {self.training_data or "Not specified"}
- **Exclusion/Inclusion Criteria:** {self.exclusion_inclusion_criteria or "Not specified"}
- **Demographic representativeness:** {self.demographic_representativeness or "Not specified"}
- **Dataset (DOI if applicable):** {self.dataset_doi_if_applicable or "Not specified"}
- **Dataset Transparency:** {self.dataset_transparency or "Not specified"}
- **Validation/Test Dataset:** {self.validation_test_dataset or "Not specified"}
- **Timeline of Data collection:** {self.timeline_of_data_collection or "Not specified"}
- **Skin tone diversity:** {self.skin_tone_diversity or "Not specified"}
- **Did the data collection process undergo ethical review:** {self.did_the_data_collection_process_undergo_ethical_review or "Not specified"}
- **Ethical Review Board Oversight:** {self.ethical_review_board_oversight or "Not specified"}
- **IRB Approval:** {self.irb_approval or "Not specified"}
- **Relevance of training data to intended population:** {self.relevance_of_training_data_to_intended_population or "Not specified"}
- **Bias Mitigation Approaches:** {self.bias_mitigation_approaches or "Not specified"}
- **Ongoing Maintenance:** {self.ongoing_maintenance or "Not specified"}
- **Security and compliance environment practices or accreditations, if applicable:** {self.security_and_compliance_environment_practices_or_accreditations_if_applicable or "Not specified"}
- **Transparency, Intelligibility, and Accountability mechanisms, if applicable:** {self.transparency_intelligibility_and_accountability_mechanisms_if_applicable or "Not specified"}
- **Transparency Information:** {self.transparency_information or "Not specified"}
- **Funding Source of the technical implementation:** {self.funding_source_of_the_technical_implementation or "Not specified"}
- **3rd Party Information, if applicable:** {self.third_party_information_if_applicable or "Not specified"}

## 5) Key Metrics
### Usefulness / Efficacy
- **Goal of Metric(s):** {self.usefulness_efficacy_goal_of_metrics or "Not specified"}
- **Result:** {self.usefulness_efficacy_result or "Not specified"}
- **Interpretation:** {self.usefulness_efficacy_interpretation or "Not specified"}
- **Test Type:** {self.usefulness_efficacy_test_type or "Not specified"}
- **Testing Data Description:** {self.usefulness_efficacy_testing_data_description or "Not specified"}
- **Validation Process and Justification:** {self.usefulness_efficacy_validation_process_and_justification or "Not specified"}
- **AUROC/Accuracy/etc.:** {self.usefulness_efficacy_auroc_accuracy_etc or "Not specified"}

### Fairness & Equity
- **Goal of Metric(s):** {self.fairness_equity_goal_of_metrics or "Not specified"}
- **Result:** {self.fairness_equity_result or "Not specified"}
- **Interpretation:** {self.fairness_equity_interpretation or "Not specified"}
- **Test Type:** {self.fairness_equity_test_type or "Not specified"}
- **Testing Data Description:** {self.fairness_equity_testing_data_description or "Not specified"}
- **Validation Process and Justification:** {self.fairness_equity_validation_process_and_justification or "Not specified"}

### Safety & Reliability
- **Goal of Metric(s):** {self.safety_reliability_goal_of_metrics or "Not specified"}
- **Result:** {self.safety_reliability_result or "Not specified"}
- **Interpretation:** {self.safety_reliability_interpretation or "Not specified"}
- **Test Type:** {self.safety_reliability_test_type or "Not specified"}
- **Testing Data Description:** {self.safety_reliability_testing_data_description or "Not specified"}
- **Validation Process and Justification:** {self.safety_reliability_validation_process_and_justification or "Not specified"}

## 6) Resources
- **Evaluation References, if available:** {self.evaluation_references_if_available or "Not specified"}
- **Clinical Trial, if available:** {self.clinical_trial_if_available or "Not specified"}
- **Peer-Reviewed Publication(s):** {self.peer_reviewed_publications or "Not specified"}
- **Reimbursement status, if applicable:** {self.reimbursement_status_if_applicable or "Not specified"}
- **Stakeholders consulted during design of solution:** {self.stakeholders_consulted_during_design_of_solution or "Not specified"}

---
*Generated on {self.extraction_timestamp} (CHAI Schema v0.3)*
"""
        return md
