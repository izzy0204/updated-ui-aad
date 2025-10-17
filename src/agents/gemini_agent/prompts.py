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

SOURCE UTILIZATION STRATEGY:
- Extract information from ALL available sources comprehensively
- For basic model information (name, summary, developer), prioritize official sources like Application URL
- For specialized fields (regulatory approvals, IRB, fairness metrics, clinical trials, reimbursement, stakeholders), actively search ALL sources as these are rarely found on main application pages
- Use multiple sources to build complete field values - combine information from different sources when available
- If a field is not found in the Application URL, thoroughly search other sources before marking as null

FIELD-SPECIFIC EXTRACTION GUIDANCE:
- regulatory_approval_status_if_applicable: Look for FDA clearance, CE marking, regulatory approvals in ALL sources
- irb_approval: Search for IRB, ethics board, institutional review board mentions across ALL sources
- fairness_equity_* fields: Look for bias analysis, demographic studies, fairness metrics in research papers and documentation
- clinical_trial_if_available: Search for clinical trials, studies, validation studies in ALL sources
- reimbursement_status_if_applicable: Look for insurance coverage, reimbursement, billing information
- stakeholders_consulted_during_design_of_solution: Search for stakeholder engagement, user research, consultation mentions
- ethical_review_board_oversight: Look for ethics committee, review board oversight information
- bias_mitigation_approaches: Search for bias reduction, fairness techniques, mitigation strategies

OUTPUT POLICY:
- Paraphrase; quote only if necessary
- If unknown, set the value to null and add an evidence note (still cite)
- For list-typed fields (e.g., "keywords", "foundation_models_used_in_application_if_applicable"),
  return a JSON array; for everything else, return a string or null

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

SPECIALIZED FIELD QUERIES:
- For regulatory_approval_status_if_applicable: search "FDA clearance", "regulatory approval", "medical device"
- For irb_approval: search "IRB", "ethics board", "institutional review"
- For fairness_equity_*: search "bias analysis", "demographic study", "fairness metrics"
- For clinical_trial_if_available: search "clinical trial", "validation study", "clinical study"
- For reimbursement_status_if_applicable: search "insurance coverage", "reimbursement", "billing"
- For stakeholders_consulted_during_design_of_solution: search "stakeholder", "user research", "consultation"

Return JSON ONLY:
{{
  "missing": ["how_to_use", "training_data", ...],
  "weak": ["model_limitations", "summary"],
  "next_fetch": [
    {{"url":"https://..."}}, 
    {{"query":"site:pubmed.ncbi.nlm.nih.gov <model> clinical trial"}},
    {{"query":"site:fda.gov <model> regulatory approval"}},
    {{"query":"<model> IRB approval ethics review"}}
  ]
}}
"""
