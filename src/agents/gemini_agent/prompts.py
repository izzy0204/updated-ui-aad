# src/agents/gemini_agent/prompts.py

from core.chai_schema import CLINICAL_AGENT_EXTRACT_FIELDS, CLINICAL_NESTED_FIELD_SPECS

_CLINICAL_FIELDS = CLINICAL_AGENT_EXTRACT_FIELDS

_NESTED_SHAPES = """
NESTED FIELD JSON SHAPES (when requested, return objects under "values"):
  "training_data": {{"description": "...", "dataset_url": "https://..."}}
  "model_development_and_validation": {{"description": "...", "publication_url": "https://..."}}
  "clinical_trial": {{"identifier": "NCT...", "url": "https://...", "description": "..."}}
  "performance": {{"summary": "...", "metrics": [{{"name":"Sensitivity","value":"94%","population":"...","confidence_interval":"..."}}]}}
  "contact": {{"email": "...", "url": "https://..."}}
"""

EXTRACTOR_HEAD = """You extract values for requested **clinical model card fields** from SOURCES.

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

EVIDENCE (MANDATORY — every populated field MUST have matching evidence):
- "evidence" MUST have one key per field you populated in "values"; a field with no
  evidence entries is treated as unsupported and may be dropped.
- Each evidence entry is {{"url": "<source URL>", "snippet": "<short excerpt>"}}.
- The "url" MUST be copied EXACTLY as it appears after "URL:" in a SOURCES/[SEED n] block.
  Never invent, alter, or guess a URL.
- If a field's value combines information from more than one SOURCES entry, include ONE
  evidence object per contributing URL — list ALL of them, not just the first. Do not
  collapse multiple sources into a single citation.
- The "snippet" should be a short phrase (a few words, under ~200 chars) that appears
  verbatim in the "values" text you wrote for that field, so the exact sentence it supports
  can be located. If no exact phrase carries over, still include the source URL with your
  best short snippet from that source rather than omitting the source.
- Example: if training_data draws facts from both https://a.example/paper and
  https://b.example/faq, return
  "evidence": {{"training_data": [
      {{"url": "https://a.example/paper", "snippet": "trained on 2,000 lesions"}},
      {{"url": "https://b.example/faq", "snippet": "images from three clinical sites"}}
  ]}}

SOURCE PRIORITY:
- If a SOURCES entry is labeled PRIMARY SOURCE, it is the developer-provided Application URL.
- Treat it as the most authoritative source; prefer its content for field values when other
  sources conflict with it, and only fall back to other sources for fields it does not cover.

FIELD GUIDANCE:
- output: include the basis for how the output is generated (e.g., the model/algorithm or
  clinical reasoning that produces the result), not just what the output looks like
- intended_users: include the knowledge/expertise necessary to use the model appropriately
- model_type: a short description only, e.g., "Convolutional Neural Network"
- training_data.description: a brief description of dataset source and population
  characteristics; put a DOI or reference link in dataset_url if available
- model_development_and_validation.publication_url: prefer a link to a peer-reviewed
  research paper
- clinical_trial.url: prefer a clinicaltrials.gov link
- performance: include subgroup performance (e.g., by skin type, age, sex) where clinically
  relevant, not just an aggregate metric
- skin_type_representation_equity: performance across various skin types and populations
  underrepresented in development, if applicable; leave empty if not disclosed anywhere in
  SOURCES rather than guessing
- contact.email: prefer an email address over a generic contact-page URL

""" + _NESTED_SHAPES


def build_extractor_prompt(
    *,
    field_paths: str,
    allowed_fields: str,
    manifest: str,
    sources: str,
) -> str:
    """Build extractor prompt without interpreting braces inside source blobs."""
    head = EXTRACTOR_HEAD.format(field_paths=field_paths, allowed_fields=allowed_fields)
    return f"{head}\n\nSOURCES:\n{sources}\n\nMANIFEST:\n{manifest}\n"


# Back-compat alias (head only; use build_extractor_prompt for full prompt).
EXTRACTOR = EXTRACTOR_HEAD

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
    "known_performance_limitations",
    "skin_type_representation_equity",
    "performance",
    "training_data",
    "clinical_trial",
{chr(10).join(f'    "{field}",' for field in _CLINICAL_FIELDS)}
  ]
}}
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
