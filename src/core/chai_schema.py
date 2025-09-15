"""
CHAI SCHEMA IMPLEMENTATION - MODEL CARD DATA STRUCTURE

PURPOSE:
Defines the comprehensive data structure for medical AI model cards following
Coalition for Healthcare AI (CHAI) standards. Contains 80+ fields organized
into 6 main categories for complete model documentation.

HOW IT WORKS:
- CHAIModelCard dataclass with all required fields for medical AI compliance
- Export methods for JSON, Markdown, and XML formats
- Validation and field mapping utilities
- Trust Ingredients categorization for transparency
- Metrics extraction for performance evaluation

FIELD CATEGORIES:
1. Metadata: Basic model information (name, developer, version, etc.)
2. Uses & Directions: Intended use, workflow integration, user guidance
3. Warnings: Risk levels, limitations, bias information
4. Trust Ingredients: AI system facts, data sources, ethics, security
5. Key Metrics: Performance, fairness, safety measurements
6. Resources: Publications, compliance, regulatory information

COMPLIANCE:
- CHAI schema v0.1 compliant
- HTI-1 regulation ready
- 45 CFR 170.315 compatible
- Medical AI documentation standards

USAGE:
card = CHAIModelCard()
card.model_name = "DermNet"
json_output = card.to_json()
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import re


@dataclass
class CHAIModelCard:
    """
    CHAI Applied Model Card Data Structure
    HTI-1 and OCR Compliant Model Card following CHAI schema v0.1
    Enhanced with comprehensive fields from manual model card analysis
    """
    
    # 1. METADATA
    model_name: str = ""
    model_developer: str = ""
    developer_organization: str = ""
    model_software_release_stage: str = ""
    release_date: str = ""
    model_version: str = ""
    geographic_availability: str = ""
    inquiries_support: str = ""
    contact: str = ""
    summary: str = ""
    keywords: List[str] = field(default_factory=list)
    doi_of_dataset_used: str = ""
    
    # 2. USES & DIRECTIONS
    intended_use_and_workflow: str = ""
    purpose: str = ""
    use_cases: List[str] = field(default_factory=list)
    primary_intended_users: str = ""
    how_to_use: Dict[str, str] = field(default_factory=dict)  # 4 Ways
    necessary_knowledge_expertise: str = ""
    patient_consent_required: str = ""
    patient_consent_or_disclosure: str = ""
    targeted_patient_population: str = ""
    cautioned_out_of_scope_settings: str = ""
    
    # 3. WARNINGS
    developer_supplied_warnings: str = ""
    model_limitations: str = ""
    known_risks_and_limitations: str = ""
    clinical_risk_level: str = ""
    
    # 4. TRUST INGREDIENTS - AI System Facts
    model_type: str = ""
    interaction: str = ""
    outcomes_and_output: str = ""
    outcomes_and_outputs: str = ""
    type_and_value_of_solution_output: str = ""
    explainability: str = ""
    foundation_models_used: List[str] = field(default_factory=list)
    input_data_source: str = ""
    output_input_type: str = ""
    output: str = ""
    exclusion_inclusion_criteria: str = ""
    demographics: str = ""
    development_data_characterization: str = ""
    training_data: str = ""
    dataset: str = ""
    dataset_transparency: str = ""
    validation_test_dataset: str = ""
    timeline_data_collection: str = ""
    timeline_of_data_collection: str = ""
    derm_specific: str = ""
    data_collection_ethical_review: str = ""
    ethical_review_board_oversight: str = ""
    irb_approval: str = ""
    relevance_training_data_to_intended_population: str = ""
    relevance_to_intended_population: str = ""
    bias_mitigation: str = ""
    bias_mitigation_approaches: str = ""
    ongoing_maintenance: str = ""
    security_compliance: str = ""
    transparency: str = ""
    funding_source: str = ""
    stakeholders: str = ""
    stakeholders_consulted: str = ""
    third_party_info: str = ""
    third_party_information: str = ""
    third_party_evaluations: str = ""
    
    # 5. KEY METRICS
    # Usefulness / Efficacy
    usefulness_efficacy_goal: str = ""
    usefulness_efficacy_result: str = ""
    usefulness_efficacy_interpretation: str = ""
    usefulness_efficacy_test_type: str = ""
    usefulness_efficacy_testing_data_description: str = ""
    usefulness_efficacy_validation_process: str = ""
    usefulness_usability_efficacy: Dict[str, str] = field(default_factory=dict)
    auroc_accuracy_etc: str = ""
    
    # Fairness & Equity
    fairness_equity_goal: str = ""
    fairness_equity_result: str = ""
    fairness_equity_interpretation: str = ""
    fairness_equity_test_type: str = ""
    fairness_equity_testing_data_description: str = ""
    fairness_equity_validation_process: str = ""
    fairness_equity: Dict[str, str] = field(default_factory=dict)
    bias_mitigation_strategies: str = ""
    known_potential_biases: str = ""
    known_biases_or_ethical_considerations: str = ""
    output_and_input_data_types: str = ""  # Missing field for data types
    
    # Safety & Reliability
    safety_reliability_goal: str = ""
    safety_reliability_result: str = ""
    safety_reliability_interpretation: str = ""
    safety_reliability_test_type: str = ""
    safety_reliability_testing_data_description: str = ""
    safety_reliability_validation_process: str = ""
    safety_reliability: Dict[str, str] = field(default_factory=dict)
    regulatory_approval_status: str = ""
    regulatory_approval: str = ""
    privacy_security_protocols: str = ""
    
    # 6. RESOURCES
    evaluation_references: str = ""
    peer_reviewed_publications: str = ""
    clinical_trial: str = ""
    model_documentation: str = ""
    reimbursement: str = ""
    reimbursement_status: str = ""
    data_security_standards_followed: str = ""  # HIPAA, SOC2
    compliance_frameworks: str = ""  # GDPR
    relevant_accreditations: str = ""  # ISO, ONC
    
    # Bibliography and Sources Section
    bibliography: str = ""
    sources_summary: Dict[str, Any] = field(default_factory=dict)  # Comprehensive list of all sources used
    source_reliability_assessment: Dict[str, Any] = field(default_factory=dict)  # Assessment of source quality
    
    # Metadata
    sources_extracted_from: List[str] = field(default_factory=list)
    extraction_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    extraction_summary: Dict[str, Any] = field(default_factory=lambda: {
        'sources_discovered': {'total': 0, 'huggingface': 0, 'github': 0, 'pubmed': 0, 'arxiv': 0, 'websites': 0},
        'content_extracted': 0,
        'metrics_found': 0,
        'analysis_complete': False
    })
    
    # CITATION TRACKING - NEW: Track sources for each field
    source_citations: Dict[str, List[Dict]] = field(default_factory=dict)
    citation_summary: Dict[str, Any] = field(default_factory=dict)
    

    
    def safe_xml_text(self, value) -> str:
        """Safely convert any value to XML-compatible string"""
        if value is None:
            return ""
        elif isinstance(value, str):
            return value
        elif isinstance(value, list):
            if not value:
                return ""
            return '; '.join(str(item) for item in value if item)
        elif isinstance(value, dict):
            if not value:
                return ""
            return '; '.join(f"{k}: {v}" for k, v in value.items() if v is not None)
        else:
            return str(value)

    def to_xml(self) -> str:
        """Export model card to CHAI XML format"""
        root = ET.Element('AppliedModelCard')
        root.set('xmlns', 'https://mc.chai.org/v0.1/schema.xsd')
        
        # Basic Info
        basic_info = ET.SubElement(root, 'BasicInfo')
        ET.SubElement(basic_info, 'ModelName').text = self.safe_xml_text(self.model_name)
        ET.SubElement(basic_info, 'DeveloperOrganization').text = self.safe_xml_text(self.developer_organization)
        ET.SubElement(basic_info, 'InquiriesSupport').text = self.safe_xml_text(self.inquiries_support)
        
        # Release Info
        release_info = ET.SubElement(root, 'ReleaseInfo')
        ET.SubElement(release_info, 'ReleaseStage').text = self.safe_xml_text(self.model_software_release_stage)
        ET.SubElement(release_info, 'ReleaseDate').text = self.safe_xml_text(self.release_date)
        ET.SubElement(release_info, 'DOIOfDatasetUsed').text = self.safe_xml_text(self.doi_of_dataset_used)
        
        # Model Summary
        model_summary = ET.SubElement(root, 'ModelSummary')
        ET.SubElement(model_summary, 'Summary').text = self.safe_xml_text(self.summary)
        keywords_elem = ET.SubElement(model_summary, 'Keywords')
        if isinstance(self.keywords, list):
            for keyword in self.keywords:
                ET.SubElement(keywords_elem, 'Keyword').text = self.safe_xml_text(keyword)
        else:
            ET.SubElement(keywords_elem, 'Keyword').text = self.safe_xml_text(self.keywords)
        
        # Uses and Directions
        uses_directions = ET.SubElement(root, 'UsesAndDirections')
        ET.SubElement(uses_directions, 'IntendedUseAndWorkflow').text = self.safe_xml_text(self.intended_use_and_workflow)
        ET.SubElement(uses_directions, 'Purpose').text = self.safe_xml_text(self.purpose)
        use_cases_elem = ET.SubElement(uses_directions, 'UseCases')
        if isinstance(self.use_cases, list):
            for use_case in self.use_cases:
                ET.SubElement(use_cases_elem, 'UseCase').text = self.safe_xml_text(use_case)
        else:
            ET.SubElement(use_cases_elem, 'UseCase').text = self.safe_xml_text(self.use_cases)
        ET.SubElement(uses_directions, 'PrimaryIntendedUsers').text = self.safe_xml_text(self.primary_intended_users)
        ET.SubElement(uses_directions, 'HowToUse').text = self.safe_xml_text(self.how_to_use)
        ET.SubElement(uses_directions, 'NecessaryKnowledgeExpertise').text = self.safe_xml_text(self.necessary_knowledge_expertise)
        ET.SubElement(uses_directions, 'PatientConsentRequired').text = self.safe_xml_text(self.patient_consent_required)
        
        # Warnings
        warnings = ET.SubElement(root, 'Warnings')
        ET.SubElement(warnings, 'DeveloperSuppliedWarnings').text = self.safe_xml_text(self.developer_supplied_warnings)
        ET.SubElement(warnings, 'ModelLimitations').text = self.safe_xml_text(self.model_limitations)
        ET.SubElement(warnings, 'ClinicalRiskLevel').text = self.safe_xml_text(self.clinical_risk_level)
        
        # Trust Ingredients
        trust_ingredients = ET.SubElement(root, 'TrustIngredients')
        
        # AI System Facts
        ai_facts = ET.SubElement(trust_ingredients, 'AISystemFacts')
        ET.SubElement(ai_facts, 'ModelType').text = self.safe_xml_text(self.model_type)
        ET.SubElement(ai_facts, 'Interaction').text = self.safe_xml_text(self.interaction)
        ET.SubElement(ai_facts, 'OutcomesAndOutput').text = self.safe_xml_text(self.outcomes_and_output)
        ET.SubElement(ai_facts, 'TypeAndValueOfSolutionOutput').text = self.safe_xml_text(self.type_and_value_of_solution_output)
        ET.SubElement(ai_facts, 'Explainability').text = self.safe_xml_text(self.explainability)
        foundation_models_elem = ET.SubElement(ai_facts, 'FoundationModelsUsed')
        if isinstance(self.foundation_models_used, list):
            for foundation_model in self.foundation_models_used:
                ET.SubElement(foundation_models_elem, 'FoundationModel').text = self.safe_xml_text(foundation_model)
        else:
            ET.SubElement(foundation_models_elem, 'FoundationModel').text = self.safe_xml_text(self.foundation_models_used)
        ET.SubElement(ai_facts, 'InputDataSource').text = self.safe_xml_text(self.input_data_source)
        ET.SubElement(ai_facts, 'OutputInputType').text = self.safe_xml_text(self.output_input_type)
        ET.SubElement(ai_facts, 'Output').text = self.safe_xml_text(self.output)
        ET.SubElement(ai_facts, 'ExclusionInclusionCriteria').text = self.safe_xml_text(self.exclusion_inclusion_criteria)
        ET.SubElement(ai_facts, 'Demographics').text = self.safe_xml_text(self.demographics)
        ET.SubElement(ai_facts, 'DevelopmentDataCharacterization').text = self.safe_xml_text(self.development_data_characterization)
        ET.SubElement(ai_facts, 'TrainingData').text = self.safe_xml_text(self.training_data)
        ET.SubElement(ai_facts, 'Dataset').text = self.safe_xml_text(self.dataset)
        ET.SubElement(ai_facts, 'DatasetTransparency').text = self.safe_xml_text(self.dataset_transparency)
        ET.SubElement(ai_facts, 'ValidationTestDataset').text = self.safe_xml_text(self.validation_test_dataset)
        ET.SubElement(ai_facts, 'TimelineOfDataCollection').text = self.safe_xml_text(self.timeline_of_data_collection)
        ET.SubElement(ai_facts, 'DermSpecific').text = self.safe_xml_text(self.derm_specific)
        ET.SubElement(ai_facts, 'DataCollectionEthicalReview').text = self.safe_xml_text(self.data_collection_ethical_review)
        ET.SubElement(ai_facts, 'EthicalReviewBoardOversight').text = self.safe_xml_text(self.ethical_review_board_oversight)
        ET.SubElement(ai_facts, 'IRBApproval').text = self.safe_xml_text(self.irb_approval)
        ET.SubElement(ai_facts, 'RelevanceToIntendedPopulation').text = self.safe_xml_text(self.relevance_to_intended_population)
        ET.SubElement(ai_facts, 'BiasMitigation').text = self.safe_xml_text(self.bias_mitigation)
        ET.SubElement(ai_facts, 'OngoingMaintenance').text = self.safe_xml_text(self.ongoing_maintenance)
        ET.SubElement(ai_facts, 'SecurityCompliance').text = self.safe_xml_text(self.security_compliance)
        ET.SubElement(ai_facts, 'Transparency').text = self.safe_xml_text(self.transparency)
        ET.SubElement(ai_facts, 'FundingSource').text = self.safe_xml_text(self.funding_source)
        ET.SubElement(ai_facts, 'Stakeholders').text = self.safe_xml_text(self.stakeholders)
        ET.SubElement(ai_facts, 'ThirdPartyInfo').text = self.safe_xml_text(self.third_party_info)
        
        # Key Metrics
        key_metrics = ET.SubElement(root, 'KeyMetrics')
        
        # Usefulness / Efficacy
        usefulness = ET.SubElement(key_metrics, 'UsefulnessEfficacy')
        ET.SubElement(usefulness, 'Goal').text = self.safe_xml_text(self.usefulness_efficacy_goal)
        ET.SubElement(usefulness, 'Result').text = self.safe_xml_text(self.usefulness_efficacy_result)
        ET.SubElement(usefulness, 'Interpretation').text = self.safe_xml_text(self.usefulness_efficacy_interpretation)
        ET.SubElement(usefulness, 'TestType').text = self.safe_xml_text(self.usefulness_efficacy_test_type)
        ET.SubElement(usefulness, 'TestingDataDescription').text = self.safe_xml_text(self.usefulness_efficacy_testing_data_description)
        ET.SubElement(usefulness, 'ValidationProcess').text = self.safe_xml_text(self.usefulness_efficacy_validation_process)
        ET.SubElement(usefulness, 'AUROCAccuracyEtc').text = self.safe_xml_text(self.auroc_accuracy_etc)
        
        # Fairness & Equity
        fairness = ET.SubElement(key_metrics, 'FairnessEquity')
        ET.SubElement(fairness, 'Goal').text = self.safe_xml_text(self.fairness_equity_goal)
        ET.SubElement(fairness, 'Result').text = self.safe_xml_text(self.fairness_equity_result)
        ET.SubElement(fairness, 'Interpretation').text = self.safe_xml_text(self.fairness_equity_interpretation)
        ET.SubElement(fairness, 'TestType').text = self.safe_xml_text(self.fairness_equity_test_type)
        ET.SubElement(fairness, 'TestingDataDescription').text = self.safe_xml_text(self.fairness_equity_testing_data_description)
        ET.SubElement(fairness, 'ValidationProcess').text = self.safe_xml_text(self.fairness_equity_validation_process)
        ET.SubElement(fairness, 'BiasMitigationStrategies').text = self.safe_xml_text(self.bias_mitigation_strategies)
        ET.SubElement(fairness, 'KnownPotentialBiases').text = self.safe_xml_text(self.known_potential_biases)
        
        # Safety & Reliability
        safety = ET.SubElement(key_metrics, 'SafetyReliability')
        ET.SubElement(safety, 'Goal').text = self.safe_xml_text(self.safety_reliability_goal)
        ET.SubElement(safety, 'Result').text = self.safe_xml_text(self.safety_reliability_result)
        ET.SubElement(safety, 'Interpretation').text = self.safe_xml_text(self.safety_reliability_interpretation)
        ET.SubElement(safety, 'TestType').text = self.safe_xml_text(self.safety_reliability_test_type)
        ET.SubElement(safety, 'TestingDataDescription').text = self.safe_xml_text(self.safety_reliability_testing_data_description)
        ET.SubElement(safety, 'ValidationProcess').text = self.safe_xml_text(self.safety_reliability_validation_process)
        ET.SubElement(safety, 'RegulatoryApprovalStatus').text = self.safe_xml_text(self.regulatory_approval_status)
        ET.SubElement(safety, 'PrivacySecurityProtocols').text = self.safe_xml_text(self.privacy_security_protocols)
        
        # Resources
        resources = ET.SubElement(root, 'Resources')
        ET.SubElement(resources, 'EvaluationReferences').text = self.safe_xml_text(self.evaluation_references)
        ET.SubElement(resources, 'PeerReviewedPublications').text = self.safe_xml_text(self.peer_reviewed_publications)
        ET.SubElement(resources, 'Reimbursement').text = self.safe_xml_text(self.reimbursement)
        ET.SubElement(resources, 'DataSecurityStandardsFollowed').text = self.safe_xml_text(self.data_security_standards_followed)
        ET.SubElement(resources, 'ComplianceFrameworks').text = self.safe_xml_text(self.compliance_frameworks)
        ET.SubElement(resources, 'RelevantAccreditations').text = self.safe_xml_text(self.relevant_accreditations)
        if self.reimbursement_status:
            ET.SubElement(resources, 'ReimbursementStatus').text = self.safe_xml_text(self.reimbursement_status)
        ET.SubElement(resources, 'PatientConsentOrDisclosure').text = self.safe_xml_text(self.patient_consent_or_disclosure)
        
        # Bibliography and Sources
        ET.SubElement(root, 'Bibliography').text = self.safe_xml_text(self.bibliography)
        ET.SubElement(root, 'SourcesSummary').text = self.safe_xml_text(self.sources_summary)
        ET.SubElement(root, 'SourceReliabilityAssessment').text = self.safe_xml_text(self.source_reliability_assessment)
        
        return ET.tostring(root, encoding='unicode')
    
    def to_json(self) -> str:
        """Export model card to JSON format"""
        return json.dumps(self.__dict__, indent=2, default=str)
    
    def __post_init__(self):
        """Initialize after dataclass creation"""
        # Initialize footnote tracking for proper academic citations
        self._footnote_map = {}  # Maps URL -> footnote number
        self._footnote_counter = 0
        
        # Initialize default values for how_to_use (4 Ways)
        if not self.how_to_use or not isinstance(self.how_to_use, dict):
            self.how_to_use = {
                'way_1': '',
                'way_2': '', 
                'way_3': '',
                'way_4': ''
            }
        
        # Ensure other dictionary fields are properly initialized
        if not isinstance(self.usefulness_usability_efficacy, dict):
            self.usefulness_usability_efficacy = {}
        if not isinstance(self.fairness_equity, dict):
            self.fairness_equity = {}
        if not isinstance(self.safety_reliability, dict):
            self.safety_reliability = {}
    
    def _get_footnote_number(self, url: str) -> int:
        """Get or assign a footnote number for a URL"""
        if url not in self._footnote_map:
            self._footnote_counter += 1
            self._footnote_map[url] = self._footnote_counter
        return self._footnote_map[url]
    
    def _generate_bibliography(self) -> str:
        """
        Return formatted reference list items only (no header).
        Ignores non-URLs and 'generated'/'internal' source types.
        """
        cites = getattr(self, 'source_citations', {}) or {}
        if not cites:
            return ""

        bibliography_entries = {}

        for field_citations in cites.values():
            for citation in (field_citations or []):
                if not isinstance(citation, dict):
                    continue
                url = citation.get('url', '')
                source_type = (citation.get('type', 'web') or 'web').lower()
                if source_type in {'generated', 'internal'}:
                    continue
                if not self._valid_citation_url(url):
                    continue

                footnote_num = self._get_footnote_number(url)
                title = citation.get('title', 'Unknown Title')

                # Source-type specific label
                if source_type == 'pubmed':
                    label = 'PubMed'
                elif source_type == 'arxiv':
                    label = 'arXiv'
                elif source_type == 'github':
                    label = 'GitHub Repository'
                elif source_type == 'huggingface':
                    label = 'Hugging Face Model Hub'
                elif source_type == 'fda':
                    label = 'U.S. Food and Drug Administration'
                elif source_type == 'nih':
                    label = 'National Institutes of Health'
                else:
                    label = None

                entry = f"{title}. "
                if label:
                    entry += f"{label}. "
                entry += f"Retrieved from {url}"

                confidence = citation.get('confidence', 1.0)
                conf_label = "High" if confidence >= 0.8 else "Medium" if confidence >= 0.5 else "Low"
                entry += f" (Reliability: {conf_label})"

                bibliography_entries[footnote_num] = entry

        if not bibliography_entries:
            return ""

        # Sort and render as numbered list
        out = ""
        for num in sorted(bibliography_entries):
            out += f"{num}. {bibliography_entries[num]}\n\n"
        return out
    
    def _format_sources_summary_md(self) -> str:
        d = self.sources_summary or {}
        total = int(d.get("total_analyzed", d.get("total", 0)) or 0)
        succ = int(d.get("successes", d.get("success_count", 0)) or 0)
        # support either ratio (0..1) or percentage number
        ratio = d.get("success_ratio", 0.0)
        try:
            pct = (float(ratio) * 100.0) if float(ratio) <= 1.0 else float(ratio)
        except Exception:
            pct = 0.0
        types_count = int(d.get("source_types_analyzed", d.get("types_count", 0)) or 0)

        lines = []
        lines.append("### Information Sources Used")
        lines.append(f"**Total Sources Analyzed:** {total}\n")
        lines.append("**Extraction Statistics:**")
        lines.append(f"- Sources with successful extraction: {succ}/{total} ({pct:.1f}%)")
        lines.append(f"- Source types analyzed: {types_count}")
        return "\n".join(lines)

    def _format_source_reliability_md(self) -> str:
        d = self.source_reliability_assessment or {}
        official = int(d.get("official", 0) or 0)
        academic = int(d.get("academic", 0) or 0)
        general = int(d.get("general", d.get("web", 0)) or 0)

        lines = []
        lines.append("### Source Reliability Assessment")
        lines.append("**Quality Assessment:**")
        lines.append(f"- Official sources: {official}")
        lines.append(f"- Academic sources: {academic}")
        lines.append(f"- General web sources: {general}")
        return "\n".join(lines)
    
    # --- SOURCES / SUMMARY UTILITIES ---
    def _valid_citation_url(self, url: str) -> bool:
        return isinstance(url, str) and url.lower().startswith(("http://","https://","doi:","arxiv:"))

    def _compute_source_stats(self):
        """
        Build source stats from self.source_citations and the actual populated fields.
        Counts unique valid source URLs and how many were actually used to populate non-empty fields.
        """
        cites = getattr(self, "source_citations", {}) or {}
        valid_urls = set()
        hits = {}
        # Count a "hit" only if the field has a non-empty value.
        for field_name, field_cites in cites.items():
            value = getattr(self, field_name, None)
            has_value = bool(value) and str(value).strip().lower() not in {"not specified"}
            for c in (field_cites or []):
                u = (c or {}).get("url", "")
                t = (c or {}).get("type", "web").lower()
                if t in {"generated", "internal"}:
                    continue
                if not self._valid_citation_url(u):
                    continue
                valid_urls.add(u)
                if has_value:
                    hits[u] = hits.get(u, 0) + 1
        total = len(valid_urls)
        success = sum(1 for u in valid_urls if hits.get(u, 0) > 0)
        return total, success, valid_urls

    def _classify_source(self, url: str) -> str:
        u = url.lower()
        if any(x in u for x in ["fda.gov","ema.europa.eu","who.int","nih.gov","hhs.gov"]):
            return "official"
        if any(x in u for x in ["ncbi.nlm.nih.gov","nature.com","nejm.org","thelancet.com",
                                "sciencedirect.com",".edu","arxiv.org","doi:"]):
            return "academic"
        return "web"

    def _compute_sources_summary(self) -> str:
        """
        Generate the summary block ONLY from real, valid sources.
        """
        total, success, valid_urls = self._compute_source_stats()
        if total == 0:
            return "No sources identified."

        classes = {"official": 0, "academic": 0, "web": 0}
        for u in valid_urls:
            classes[self._classify_source(u)] += 1

        return (
            f"**Total Sources Analyzed:** {total}\n\n"
            f"**Extraction Statistics:**\n"
            f"- Sources with successful extraction: {success}/{total} ({(success/total*100):.1f}%)\n"
            f"- Source types analyzed: {len([v for v in classes.values() if v>0])}\n\n"
            f"**Quality Assessment:**\n"
            f"- Official sources: {classes['official']}\n"
            f"- Academic sources: {classes['academic']}\n"
            f"- General web sources: {classes['web']}\n"
        )

    def _bump_extraction_counters(self, found_metrics: int = 0, found_content: bool = False):
        """
        Keep extraction_summary in sync as fields/metrics are populated.
        Call this from your extraction paths when you successfully set fields or parse metrics.
        """
        es = getattr(self, "extraction_summary", None)
        if not isinstance(es, dict):
            return
        # Update total sources from current citations
        total, _, _ = self._compute_source_stats()
        es.setdefault("sources_discovered", {"total": 0, "huggingface": 0, "github": 0, "pubmed": 0, "arxiv": 0, "websites": 0})
        es["sources_discovered"]["total"] = max(es["sources_discovered"].get("total", 0), total)
        es["metrics_found"] = es.get("metrics_found", 0) + int(found_metrics)
        if found_content:
            es["content_extracted"] = es.get("content_extracted", 0) + 1
        es["analysis_complete"] = bool(es["sources_discovered"]["total"] or es.get("content_extracted", 0))

    def finalize_source_stats(self):
        seen = set()
        official = academic = general = 0
        for field, cites in (self.source_citations or {}).items():
            for c in (cites or []):
                url = (c or {}).get("url") or ""
                title = (c or {}).get("title") or ""
                if (not url or
                    url in ["Generated","generated","unknown"] or
                    "generated" in url.lower() or
                    not url.startswith(("http://","https://")) or
                    title in ["Unknown Title","AI Generated Content",""]):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                src_type = (c or {}).get("type","web").lower()
                if src_type in ("fda","nih","gov","regulator","official"):
                    official += 1
                elif src_type in ("pubmed","arxiv","journal","academic"):
                    academic += 1
                else:
                    general += 1
        total = len(seen)
        self.sources_summary = {
            "total": total,
            "success_count": total,
            "success_ratio": 1.0 if total else 0.0,
            "types_count": sum(1 for x in [official,academic,general] if x>0),
        }
        self.source_reliability_assessment = {
            "official": official,
            "academic": academic,
            "web": general,
        }
    
    def to_markdown(self) -> str:
        """Export model card to Markdown format with footnote-style citations"""
        
        def safe_format(value, default="Not specified"):
            """Safely format various data types for markdown"""
            if not value:
                return default
            if isinstance(value, str):
                return value
            elif isinstance(value, dict):
                if not value:
                    return default
                return '\n'.join([f"- **{k}**: {v}" for k, v in value.items() if v is not None])
            elif isinstance(value, list):
                if not value:
                    return default
                return '\n'.join([f"- {item}" for item in value if item])
            else:
                return str(value)
        
        def format_with_citations(field_name: str, value, default="Not specified"):
            """Format field value with proper footnote-style citations"""
            formatted_value = safe_format(value, default)
            if formatted_value == default:
                return formatted_value
            
            # Get citations for this field with error handling
            try:
                citations = getattr(self, 'source_citations', {}).get(field_name, [])
                if citations and isinstance(citations, list):
                    # Add footnote-style citations with superscript numbers
                    citation_numbers = []
                    for citation in citations[:3]:  # Max 3 citations per field
                        if isinstance(citation, dict) and citation.get('url'):
                            # Get or assign global footnote number
                            footnote_num = self._get_footnote_number(citation['url'])
                            citation_numbers.append(f"^{footnote_num}")
                    
                    if citation_numbers:
                        formatted_value += f" {','.join(citation_numbers)}"
            except Exception:
                # If citation system fails, just return the formatted value without citations
                pass
            
            return formatted_value
        
        md = f"""# {format_with_citations('model_name', self.model_name, 'Unnamed Model')} - CHAI Applied Model Card

## Basic Information
- **Model Name**: {format_with_citations('model_name', self.model_name)}
- **Developer**: {format_with_citations('model_developer', self.model_developer)}
- **Organization**: {format_with_citations('developer_organization', self.developer_organization)}
- **Contact**: {format_with_citations('contact', getattr(self, 'contact', '') or getattr(self, 'developer_contact', ''))}

## Release Information
- **Stage**: {format_with_citations('model_software_release_stage', self.model_software_release_stage)}
- **Date**: {format_with_citations('release_date', self.release_date)}
- **Version**: {format_with_citations('model_version', getattr(self, 'model_version', '') or getattr(self, 'release_version', ''))}
- **Availability**: {format_with_citations('geographic_availability', self.geographic_availability)}
- **Regulatory Status**: {format_with_citations('regulatory_approval_status', self.regulatory_approval_status)}

## Model Summary
{format_with_citations('summary', self.summary)}

**Keywords**: {', '.join(self.keywords) if self.keywords else 'Not specified'}

## Uses & Directions
### Intended Use and Workflow
{format_with_citations('intended_use_and_workflow', self.intended_use_and_workflow)}

### Primary Intended Users
{format_with_citations('primary_intended_users', self.primary_intended_users)}

### How to Use
{format_with_citations('how_to_use', self.how_to_use)}

### Targeted Patient Population
{format_with_citations('targeted_patient_population', self.targeted_patient_population)}

### Cautioned Out-of-Scope Settings
{format_with_citations('cautioned_out_of_scope_settings', self.cautioned_out_of_scope_settings)}

## Warnings
### Known Risks and Limitations
{format_with_citations('known_risks_and_limitations', self.known_risks_and_limitations)}

### Developer Supplied Warnings
{format_with_citations('developer_supplied_warnings', self.developer_supplied_warnings)}

### Model Limitations
{format_with_citations('model_limitations', self.model_limitations)}

### Known Biases or Ethical Considerations
{format_with_citations('known_biases_or_ethical_considerations', getattr(self, 'known_biases_or_ethical_considerations', '') or getattr(self, 'known_potential_biases', ''))}

### Clinical Risk Level
{format_with_citations('clinical_risk_level', self.clinical_risk_level)}

## Trust Ingredients
### AI System Facts
{format_with_citations('ai_system_facts', getattr(self, 'ai_system_facts', {}))}

### Outcomes and Outputs
{format_with_citations('outcomes_and_outputs', self.outcomes_and_outputs)}

### Model Type and Architecture
- **Model Type**: {format_with_citations('model_type', self.model_type)}
- **Foundation Models**: {format_with_citations('foundation_models_used', getattr(self, 'foundation_models_used', []) or getattr(self, 'foundation_models', ''))}
- **Input Data Source**: {format_with_citations('input_data_source', self.input_data_source)}
- **Data Types**: {format_with_citations('output_and_input_data_types', getattr(self, 'output_and_input_data_types', '') or getattr(self, 'output_input_data_types', {}))}

### Development Data Characterization
{format_with_citations('development_data_characterization', self.development_data_characterization)}

### Bias Mitigation Approaches
{format_with_citations('bias_mitigation_approaches', self.bias_mitigation_approaches)}

### Ongoing Maintenance
{format_with_citations('ongoing_maintenance', getattr(self, 'ongoing_maintenance', {}))}

### Security and Compliance
{format_with_citations('security_compliance', getattr(self, 'security_compliance', '') or getattr(self, 'security', ''))}

### Transparency Information
{safe_format(getattr(self, 'transparency_info', {}) or getattr(self, 'transparency', ''))}

- **Funding Source**: {safe_format(self.funding_source)}
- **Third Party Information**: {safe_format(self.third_party_information)}
- **Stakeholders Consulted**: {safe_format(self.stakeholders_consulted)}

## Key Metrics
### Usefulness, Usability & Efficacy
{safe_format(self.usefulness_usability_efficacy)}

### Fairness & Equity
{safe_format(self.fairness_equity)}

### Safety & Reliability
{safe_format(self.safety_reliability)}

## Resources
### Evaluation References
{safe_format(self.evaluation_references)}

### Clinical Trial Information
{safe_format(self.clinical_trial)}

### Peer-Reviewed Publications
{safe_format(self.peer_reviewed_publications)}

### Model Documentation
{safe_format(self.model_documentation)}

### Reimbursement Status
{safe_format(self.reimbursement_status)}

### Patient Consent or Disclosure
{safe_format(self.patient_consent_or_disclosure)}

"""
        
        md += "\n## Sources and References\n"

        # Information Sources Used (computed if not provided)
        computed_sources_summary = self.sources_summary or self._compute_sources_summary()
        if isinstance(computed_sources_summary, dict):
            # Format dictionary as markdown
            computed_sources_summary = self._format_sources_summary_md()
        md += "### Information Sources Used\n" + str(computed_sources_summary) + "\n"

        # Optionally keep your separate reliability narrative if you use it elsewhere
        if getattr(self, "source_reliability_assessment", ""):
            md += "### Source Reliability Assessment\n"
            md += format_with_citations('source_reliability_assessment', self.source_reliability_assessment) + "\n"

        # References: add header only if there are actual items
        refs = self._generate_bibliography()
        if refs:
            md += "### References\n" + refs
        
        # Add extraction summary if available
        extraction_summary = getattr(self, 'extraction_summary', {})
        if extraction_summary:
            md += f"""
## Extraction Summary
{safe_format(extraction_summary, 'No extraction data available')}
"""
        
        md += f"""
---
*Generated on {self.extraction_timestamp} using automated model discovery and analysis.*
*This model card follows CHAI Schema v0.1 standards with academic-style footnote citations and comprehensive source attribution.*
"""
        
        return md


def extract_metrics_from_text(text: str) -> Dict[str, str]:
    """Extract performance metrics from text content"""
    metrics = {}
    
    # Common metric patterns
    patterns = {
        'sensitivity': r'sensitivity[:\s=]*(\d+\.?\d*%?)',
        'specificity': r'specificity[:\s=]*(\d+\.?\d*%?)',
        'accuracy': r'accuracy[:\s=]*(\d+\.?\d*%?)',
        'auc': r'AUC|AUROC[:\s=]*(\d+\.?\d*)',
        'precision': r'precision[:\s=]*(\d+\.?\d*%?)',
        'recall': r'recall[:\s=]*(\d+\.?\d*%?)',
        'f1': r'F1[:\s=]*(\d+\.?\d*)'
    }
    
    for metric_name, pattern in patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            metrics[metric_name] = matches[0]
    
    return metrics


def extract_clinical_info_from_text(text: str) -> Dict[str, str]:
    """Extract clinical information from text content"""
    info = {}
    
    # Look for clinical oversight mentions
    oversight_patterns = [
        r'dermatologist[s]?\s+[^.]*involved',
        r'clinical oversight[^.]*',
        r'physician[s]?\s+[^.]*validated',
        r'medical professional[s]?\s+[^.]*review'
    ]
    
    for pattern in oversight_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            info['clinical_oversight'] = matches[0]
            break
    
    # Look for FDA/regulatory approval
    regulatory_patterns = [
        r'FDA[^.]*approval',
        r'CE mark[^.]*',
        r'regulatory[^.]*approval',
        r'cleared[^.]*FDA'
    ]
    
    for pattern in regulatory_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            info['regulatory_approval'] = matches[0]
            break
    
    # Look for bias mitigation
    bias_patterns = [
        r'bias[^.]*mitigation',
        r'fairness[^.]*approach',
        r'equity[^.]*consideration',
        r'diverse[^.]*dataset'
    ]
    
    for pattern in bias_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            info['bias_mitigation'] = matches[0]
            break
    
    return info