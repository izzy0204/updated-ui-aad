# src/agents/gemini_agent/prompts.py

PLANNER = """You are a planning agent for producing a CHAI-aligned dermatology AI model card.
Given a short model hint, return JSON ONLY:
{
  "targets": [
    {"type":"huggingface","id":"<org/model>"},
    {"type":"github","id":"<owner/repo>"},
    {"type":"web","url":"<https://...>"}
  ],
  "fields_priority": [
    // IMPORTANT: Use ONLY CHAI field names (flat), not dotted paths.
    "summary",
    "intended_use_and_workflow",
    "model_type",
    "model_limitations",
    "training_data",
    "validation_test_dataset",
    "skin_tone_diversity",
    "foundation_models_used_in_application_if_applicable"
  ]
}
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

Return JSON ONLY:
{{
  "missing": ["how_to_use", "training_data", ...],
  "weak": ["model_limitations", "summary"],
  "next_fetch": [
    {{"url":"https://..."}}, 
    {{"query":"site:github.com <model> training details"}}
  ]
}}
"""
