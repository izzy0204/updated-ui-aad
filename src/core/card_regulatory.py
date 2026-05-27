"""Per-field regulatory status tier inferred from statement text."""

from __future__ import annotations

import re
from typing import Dict, Pattern

from core.dermauto_card_render import composite_section_field_key, strip_citations

# Higher index = lower priority when multiple signals appear in one statement.
_TIER_PRIORITY: Dict[str, int] = {
    "green": 5,
    "yellow": 4,
    "blue": 3,
    "orange": 2,
    "red": 1,
    "gray": 0,
}

_ABSENCE_PHRASES: tuple[str, ...] = (
    "not specified",
    "none found",
    "none disclosed",
    "not disclosed",
    "not available",
    "unknown",
    "n/a",
)

_RED_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bnot\s+(?:fda\s+)?(?:approved|cleared|authorized|authorised)\b", re.I),
    re.compile(r"\bno\s+fda\s+(?:clearance|approval|authorization|authorisation)\b", re.I),
    re.compile(r"\bnot\s+(?:a\s+)?(?:regulated\s+)?medical\s+device\b", re.I),
    re.compile(r"\bnot\s+classified\s+as\s+(?:a\s+)?medical\s+device\b", re.I),
    re.compile(r"\bconsumer\s+(?:tool|app|application|product)\b", re.I),
    re.compile(r"\bwellness\s+(?:app|application|tool)\b", re.I),
    re.compile(r"\bnot\s+authorized\b", re.I),
    re.compile(r"\bnot\s+authorised\b", re.I),
    re.compile(r"\bwithout\s+fda\s+(?:clearance|approval)\b", re.I),
)

_ORANGE_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\binvestigational\b", re.I),
    re.compile(r"\bresearch\s+use\s+only\b", re.I),
    re.compile(r"\bfor\s+research\s+purposes\s+only\b", re.I),
    re.compile(r"\bnot\s+for\s+clinical\s+use\b", re.I),
    re.compile(r"\birb\s+approval\b", re.I),
    re.compile(r"\bclinical\s+trial\s+only\b", re.I),
    re.compile(r"\bunder\s+investigation\b", re.I),
    re.compile(r"\bexperimental\s+use\b", re.I),
)

_YELLOW_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\beua\b", re.I),
    re.compile(r"\bemergency\s+use\s+authorization\b", re.I),
    re.compile(r"\bemergency\s+use\s+authorisation\b", re.I),
)

_BLUE_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bce\s*[- ]?mark(?:ed|ing)?\b", re.I),
    re.compile(r"\bauthorized\s+in\s+europe\b", re.I),
    re.compile(r"\bauthorised\s+in\s+europe\b", re.I),
    re.compile(r"\beuropean\s+conformity\b", re.I),
)

_GREEN_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bfda[\s-]+(?:approved|cleared|clearance|authorization|authorisation)\b", re.I),
    re.compile(r"\b(?:approved|cleared)[\s-]+by[\s-]+(?:the[\s-]+)?fda\b", re.I),
    re.compile(r"\b510\s*\(\s*k\s*\)", re.I),
    re.compile(r"\bde\s+novo\b", re.I),
    re.compile(r"\bpma\s+approved\b", re.I),
    re.compile(r"\bpremarket\s+approval\b", re.I),
    re.compile(r"\bclass\s+ii(?:\s+)?(?:device|classification)\b", re.I),
    re.compile(r"\bprescription[\s-]*only\b.*\b(?:medical\s+device|rx\s+only)\b", re.I),
    re.compile(r"\brx\s+only\b.*\bmedical\s+device\b", re.I),
)


def _is_absence_placeholder(text: str) -> bool:
    if not text:
        return True
    stripped = text.strip().lower()
    if stripped in _ABSENCE_PHRASES:
        return True
    if len(stripped) >= 42:
        return False
    return any(p in stripped for p in _ABSENCE_PHRASES)


def _positive_tiers_matching(text: str) -> set[str]:
    found: set[str] = set()
    if any(p.search(text) for p in _ORANGE_PATTERNS):
        found.add("orange")
    if any(p.search(text) for p in _YELLOW_PATTERNS):
        found.add("yellow")
    if any(p.search(text) for p in _BLUE_PATTERNS):
        found.add("blue")
    if any(p.search(text) for p in _GREEN_PATTERNS):
        found.add("green")
    return found


def classify_regulatory_status(raw_value: str) -> str:
    """
    Map statement text to a regulatory tier:
    green | yellow | blue | orange | red | gray.
    """
    text = strip_citations(raw_value).strip()
    if _is_absence_placeholder(text):
        return "gray"

    lowered = text.lower()
    # Negated / unauthorized wording wins over incidental "FDA approved" substrings.
    if any(p.search(lowered) for p in _RED_PATTERNS):
        return "red"

    matches = _positive_tiers_matching(lowered)
    if not matches:
        return "gray"

    # Prefer the strongest authorization signal when multiple appear (e.g. FDA cleared + CE marked).
    return max(matches, key=lambda t: _TIER_PRIORITY[t])


def compute_regulatory_for_sections(
    sections: Dict[str, Dict[str, str]],
) -> Dict[str, str]:
    """Map composite_section_field_key -> regulatory tier name."""
    out: Dict[str, str] = {}
    for sec_name, fields in sections.items():
        if sec_name.strip().lower() == "references":
            continue
        for field_name, raw_value in fields.items():
            ck = composite_section_field_key(sec_name, field_name)
            out[ck] = classify_regulatory_status(raw_value)
    return out
