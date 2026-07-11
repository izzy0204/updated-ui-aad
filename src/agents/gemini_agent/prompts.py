# src/agents/gemini_agent/prompts.py

from core.chai_schema import CLINICAL_AGENT_EXTRACT_FIELDS, CLINICAL_NESTED_FIELD_SPECS

_CLINICAL_FIELDS = CLINICAL_AGENT_EXTRACT_FIELDS

_NESTED_SHAPES = """
NESTED FIELD JSON SHAPES (when requested, return objects under "values"):
  "training_data": {"description": "...", "dataset_url": "https://..."}
  "model_development_and_validation": {"description": "...", "publication_url": "https://..."}
  "clinical_trial": {"identifier": "NCT...", "url": "https://...", "description": "..."}
  "performance": {"summary": "...", "metrics": [{"name":"Sensitivity","value":"94%","population":"...","confidence_interval":"..."}]}
  "contact": {"email": "...", "url": "https://..."}
"""

PLANNER = f"""You are a planning agent for producing a clinician-centered dermatology AI model card.
Given a short model hint, return JSON ONLY:
{{
  "targets": [
    {{"type":"huggingface","id":"<org/model>"}},
    {{"type":"github","id":"<owner/repo>"}},
    {{"type":"web","url":"<https://...>"}}
  ],
  "fields_priority": [
    "regulatory_approval_status",
    "medical_purpose",
    "acceptable_input",
    "output",
    "role_in_decision_making",
    "known_failure_modes",
    "performance",
    "training_data",
    "clinical_trial",
{chr(10).join(f'    "{field}",' for field in _CLINICAL_FIELDS)}
  ]
}}
"""

EXTRACTOR = """You extract values for requested **clinical model card fields** from SOURCES.

CRITICAL REQUIREMENTS:
1. You MUST return ONLY valid JSON - no prose, no explanations, no markdown, no code blocks
2. The JSON MUST start with {{ and end with }}
3. The JSON MUST contain both "values" and "evidence" keys
4. NEVER return partial JSON or malformed responses
5. If you cannot complete the JSON, return: {{"values": {{}}, "evidence": {{}}}}

STRICT NAMING:
- Keys in "values" MUST be chosen ONLY from ALLOWED_FIELD_NAMES: {allowed_fields}
- Requested fields: {field_paths}
- Use snake_case field names (e.g., "model_name", "summary", "medical_purpose")
- For regulatory_approval_status use ONLY: NOT_AUTHORIZED_CONSUMER_TOOL, INVESTIGATIONAL_RESEARCH_USE_ONLY, EUA_AUTHORIZED, FDA_APPROVED, FDA_CLEARED, CE_MARKED, UNKNOWN
- Do NOT claim FDA cleared/approved without explicit evidence in sources; use UNKNOWN when uncertain

CONCISENESS:
- Keep field values concise; do not repeat the same fact across multiple fields
- Summary must be at most 3 sentences covering input, output, and clinical role

""" + _NESTED_SHAPES + """
SOURCES:
{sources}

MANIFEST:
{manifest}
"""

VALIDATOR = """You validate a partial clinical model card against SOURCES.
Return JSON ONLY:
{
  "missing": ["field_name", ...],
  "weak": ["field_name", ...],
  "next_fetch": [{"type":"web","query":"..."}],
  "coverage_estimate": 0.0
}
Use snake_case clinical field names only.
"""
