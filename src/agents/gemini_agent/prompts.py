# src/agents/gemini_agent/prompts.py

from core.chai_schema import CHAIModelCard
from dataclasses import fields as dc_fields

# Get all CHAI field names dynamically
_CHAI_FIELDS = [f.name for f in dc_fields(CHAIModelCard) if f.name != "extraction_timestamp"]

PLANNER = f"""You are a planning agent for producing a CHAI-aligned dermatology AI model card.
Given a short model hint, return JSON ONLY:
{{
  "targets": [
    {{"type":"huggingface","id":"<org/model>"}},
    {{"type":"github","id":"<owner/repo>"}},
    {{"type":"web","url":"<https://...>"}}
  ],
  "fields_priority": [
    // IMPORTANT: Use ONLY CHAI field names (flat), not dotted paths.
    // Prioritize specialized fields that require external sources:
    "regulatory_approval_status_if_applicable",
    "irb_approval",
    "ethical_review_board_oversight", 
    "clinical_trial_if_available",
    "reimbursement_status_if_applicable",
    "stakeholders_consulted_during_design_of_solution",
    "fairness_equity_goal_of_metrics",
    "fairness_equity_result",
    "fairness_equity_interpretation",
    "bias_mitigation_approaches",
    "skin_tone_diversity",
    "demographic_representativeness",
    // Then include ALL other available CHAI fields for comprehensive model card generation:
{chr(10).join(f'    "{field}",' for field in _CHAI_FIELDS)}
  ]
}}
"""

EXTRACTOR = """You extract values for requested **CHAI model card fields** from SOURCES.

CRITICAL REQUIREMENTS:
1. You MUST return ONLY valid JSON - no prose, no explanations, no markdown, no code blocks
2. The JSON MUST start with {{ and end with }}
3. The JSON MUST contain both "values" and "evidence" keys
4. NEVER return partial JSON or malformed responses
5. If you cannot complete the JSON, return: {{"values": {{}}, "evidence": {{}}}}

STRICT NAMING:
- Keys in "values" MUST be chosen ONLY from ALLOWED_FIELD_NAMES shown below
- Do NOT invent new keys. Do NOT use dotted paths like "metadata.summary"
- Emit CHAI field names exactly (e.g., "model_name", "summary", "model_limitations", ...)

EXTRACTION QUALITY STANDARDS (MANDATORY):
You must be SPECIFIC, ACCURATE, PRECISE, and INCLUSIVE for each field:

**SPECIFICITY:**
- Include concrete details: exact numbers, dates, percentages, metrics, specific features
- Use specific terminology rather than generic descriptions
- Include all relevant qualifiers and context (e.g., "FDA 510(k) clearance" not just "FDA approval")
- Capture complete information: if a source mentions "3,000+ peer-reviewed articles", include the exact number and context

**ACCURACY:**
- Verify information across multiple sources when available
- Use exact quotes when precision matters (especially for technical specifications, regulatory status, metrics)
- Cross-reference claims between sources to ensure consistency
- Preserve exact terminology from sources (e.g., "IRB approval" vs "ethics review")

**PRECISION:**
- Be exact with technical terms, avoid approximations unless source is vague
- Include all relevant details that make the information complete and unambiguous
- For metrics: include exact values, confidence intervals, sample sizes when available
- For dates: include specific dates, not just "recently" or "2023"
- For lists: include ALL items mentioned, not just a subset

**INCLUSIVENESS:**
- Extract ALL relevant information from ALL sources - do not omit details
- Combine complementary information from multiple sources to create comprehensive field values
- Include all aspects mentioned: if a source describes multiple use cases, include all of them
- For fields with multiple components (e.g., "outcomes_and_output"), include ALL mentioned outcomes
- Capture edge cases, limitations, and nuances - completeness is critical

SOURCE UTILIZATION STRATEGY:
- Extract information from ALL available sources comprehensively
- For basic model information (name, summary, developer), prioritize official sources like Application URL
- For specialized fields (regulatory approvals, IRB, fairness metrics, clinical trials, reimbursement, stakeholders), actively search ALL sources as these are rarely found on main application pages
- Use multiple sources to build complete field values - combine information from different sources when available
- If a field is not found in the Application URL, thoroughly search other sources before marking as null
- When multiple sources provide information for the same field, synthesize them into a comprehensive, detailed value that includes all relevant aspects

FIELD-SPECIFIC EXTRACTION GUIDANCE (CRITICAL - ALWAYS EXTRACT IF AVAILABLE):
- release_date: Search for "released", "launched", "announced", "unveiled", "published", "introduced" with specific dates (e.g., "November 11, 2023", "2023-11-11"). Check press releases, blog posts, news articles, and announcement pages.
- global_availability: Search for "available in", "countries", "regions", "worldwide", "global", "international", "markets", "geographic distribution". Check FAQ pages, about pages, and legal/terms pages.
- how_to_use: Search for "how to", "tutorial", "guide", "instructions", "getting started", "user guide", "documentation", "quick start". Check documentation pages, help sections, and onboarding content.
- developer_supplied_warnings: Search for "warning", "caution", "important notice", "limitation", "not for", "do not use", "contraindication", "precaution". Check terms of service, disclaimers, and safety pages.
- model_limitations: Search for "limitation", "constraint", "cannot", "does not", "restriction", "not suitable for", "limitations include". Check documentation, research papers, and technical specifications.
- training_data: Search for "training data", "dataset", "training set", "data used", "training corpus", "data source", "data collection". Check research papers, technical documentation, and methodology sections.
- output_input_data_type: Search for "input", "output", "data type", "format", "modality", "accepts", "returns", "input format", "output format". Check API documentation, technical specs, and user guides.
- ongoing_maintenance: Search for "updated", "maintained", "version", "release", "changelog", "version history", "updates", "maintenance schedule", "support". Check version pages, changelogs, and support pages.
- transparency_information: Search for "transparent", "disclosure", "open", "public", "transparency", "open source", "documentation", "explainable". Check about pages, transparency reports, and documentation.
- usefulness_efficacy_result: Search for "saves time", "minutes", "efficiency", "reduced", "metrics", "performance", "results", "study shows", "clinical trial", "validation", "evaluation results", "time savings", "productivity". Check research papers, case studies, and validation reports.
- safety_reliability_goal_of_metrics: Search for "safety goal", "reliability objective", "risk mitigation goal", "safety target", "reliability target", "safety objective". Check research papers, methodology sections, and technical documentation.
- safety_reliability_result: Search for "safety metrics", "reliability data", "trustworthiness measures", "safety validation", "reliability testing", "safety study", "adverse events", "error rate". Check validation studies, safety reports, and research papers.
- safety_reliability_interpretation: Search for "safety analysis", "reliability assessment", "risk interpretation", "safety evaluation", "reliability evaluation", "risk assessment", "safety conclusion". Check research papers and validation reports.
- regulatory_approval_status_if_applicable: Look for FDA clearance, CE marking, regulatory approvals, 510(k), De Novo, PMA in ALL sources
- irb_approval: Search for IRB, ethics board, institutional review board, ethical approval, ethics committee mentions across ALL sources
- fairness_equity_* fields: Look for bias analysis, demographic studies, fairness metrics, equity analysis, demographic representation in research papers and documentation
- clinical_trial_if_available: Search for clinical trials, studies, validation studies, clinical validation, clinical evaluation in ALL sources
- reimbursement_status_if_applicable: Look for insurance coverage, reimbursement, billing information, CPT codes, insurance approval
- stakeholders_consulted_during_design_of_solution: Search for stakeholder engagement, user research, consultation, user feedback, stakeholder input, co-design mentions
- ethical_review_board_oversight: Look for ethics committee, review board oversight, ethical review, ethics approval information
- bias_mitigation_approaches: Search for bias reduction, fairness techniques, mitigation strategies, debiasing methods, fairness interventions

OUTPUT POLICY:
- Prioritize completeness and specificity: include ALL relevant details from sources
- When paraphrasing, preserve all specific details, numbers, dates, and technical terms
- Quote directly when exact wording is important (regulatory status, specific metrics, exact feature descriptions)
- Combine information from multiple sources to create comprehensive, detailed field values
- If information is partially available, include what is known rather than setting to null
- If unknown, set the value to null and add an evidence note (still cite)
- For list-typed fields (e.g., "keywords", "foundation_models_used_in_application_if_applicable"),
  return a JSON array with ALL items found; for everything else, return a detailed string or null
- Field values should be as complete and informative as possible - favor longer, more detailed responses over brief summaries

MANDATORY JSON FORMAT (return exactly this structure):
{{
  "values": {{ "<chai_field_name>": <string | array | null>, ... }},
  "evidence": {{
    "<chai_field_name>": [
      {{"source_id": <int>, "url": "<url>", "snippet": "<=240 chars>"}} , ...
    ]
  }}
}}

ALLOWED_FIELD_NAMES:
{allowed_fields}

REQUESTED FIELDS (subset of allowed):
{field_paths}

SOURCE MANIFEST:
{manifest}

SOURCES (use [SOURCE n] tags to cite):
{sources}
"""

VALIDATOR = """Validate the card JSON for (a) completeness, (b) specificity, (c) evidence-backed claims.

STRICT NAMING:
- Report "missing" and "weak" using ONLY CHAI field names (no dotted paths).

COMPLETENESS CHECKLIST - Report ALL missing fields systematically:

METADATA SECTION:
- release_date: Check for launch dates, announcement dates, publication dates
- global_availability: Check for geographic availability information
- version: Check for version numbers, release versions
- release_stage: Check for development stage, maturity level
- inquiries_or_to_report_an_issue: Check for contact information, support pages

USES & DIRECTIONS SECTION:
- how_to_use: Check for usage instructions, tutorials, guides
- patient_consent_or_disclosure_required_or_suggested: Check for consent requirements

WARNINGS SECTION:
- developer_supplied_warnings: Check for warnings, cautions, disclaimers
- model_limitations: Check for limitations, constraints, restrictions

TRUST INGREDIENTS SECTION:
- training_data: Check for training dataset information
- output_input_data_type: Check for data type specifications
- development_data_characterization: Check for data characterization
- ongoing_maintenance: Check for update/maintenance information
- transparency_information: Check for transparency disclosures

KEY METRICS SECTION:
- usefulness_efficacy_result: Check for performance results, metrics, time savings
- usefulness_efficacy_validation_process_and_justification: Check for validation methods
- safety_reliability_goal_of_metrics: Check for safety objectives
- safety_reliability_result: Check for safety metrics, reliability data
- safety_reliability_interpretation: Check for safety analysis
- safety_reliability_test_type: Check for testing methodology
- safety_reliability_testing_data_description: Check for test data info
- safety_reliability_validation_process_and_justification: Check for validation process

RESOURCES SECTION:
- peer_reviewed_publications: Check for research papers, publications
- stakeholders_consulted_during_design_of_solution: Check for stakeholder engagement

SPECIALIZED FIELD QUERIES (suggest specific searches for missing fields):
- release_date: {{"query": "site:<application_url> release date launch announcement"}}
- how_to_use: {{"query": "site:<application_url> how to use tutorial guide"}}
- training_data: {{"query": "<model> training data dataset"}}
- usefulness_efficacy_result: {{"query": "<model> time savings efficiency metrics results"}}
- safety_reliability_result: {{"query": "<model> safety reliability metrics validation"}}
- For regulatory_approval_status_if_applicable: {{"query": "site:fda.gov <model> regulatory approval"}}
- For irb_approval: {{"query": "<model> IRB approval ethics review"}}
- For fairness_equity_*: {{"query": "<model> bias analysis demographic study fairness metrics"}}
- For clinical_trial_if_available: {{"query": "site:pubmed.ncbi.nlm.nih.gov <model> clinical trial"}}
- For reimbursement_status_if_applicable: {{"query": "<model> insurance coverage reimbursement billing"}}
- For stakeholders_consulted_during_design_of_solution: {{"query": "<model> stakeholder user research consultation"}}

Return JSON ONLY:
{{
  "missing": ["how_to_use", "training_data", "release_date", "global_availability", ...],
  "weak": ["model_limitations", "summary", "usefulness_efficacy_result"],
  "next_fetch": [
    {{"url":"https://..."}}, 
    {{"query":"site:pubmed.ncbi.nlm.nih.gov <model> clinical trial"}},
    {{"query":"site:fda.gov <model> regulatory approval"}},
    {{"query":"<model> IRB approval ethics review"}},
    {{"query":"site:<application_url> release date launch"}},
    {{"query":"site:<application_url> how to use tutorial"}},
    {{"query":"<model> training data dataset"}},
    {{"query":"<model> time savings efficiency metrics"}}
  ]
}}
"""
