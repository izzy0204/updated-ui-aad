"""Per-field provenance tier (public citation vs SWG survey mapping)."""

from __future__ import annotations

from typing import Dict, Optional, Set

from core.dermauto_card_render import CITATION_IN_TEXT, URL, composite_section_field_key, strip_citations

# Case-insensitive absence wording → always tier red (overrides citations/survey).
_ABSENCE_PHRASES: tuple[str, ...] = (
    "not specified",
    "none found",
    "none disclosed",
)


def field_is_absence_placeholder(raw_value: str) -> bool:
    """True when the text signals missing/unknown info (always tier red)."""
    text = strip_citations(raw_value).strip().lower()
    if not text:
        return False
    return any(p in text for p in _ABSENCE_PHRASES)


def field_has_public_source(raw_value: str, refs: Dict[int, str]) -> bool:
    """True if the markdown field cites a resolved reference URL or contains a bare http(s) URL."""
    for m in CITATION_IN_TEXT.finditer(raw_value):
        inner = m.group(1)
        for x in inner.split(","):
            xs = x.strip()
            if xs.isdigit():
                n = int(xs)
                u = refs.get(n)
                if u and str(u).strip():
                    return True
    if URL.search(raw_value):
        return True
    # Markdown links [text](url) — URL pattern may miss multi-line; strip common form:
    if "](" in raw_value and "http" in raw_value.lower():
        return True
    return False


def provenance_tier(*, public: bool, survey: bool) -> str:
    if public and survey:
        return "green"
    if public and not survey:
        return "blue"
    if not public and survey:
        return "yellow"
    return "red"


def compute_provenance_for_sections(
    sections: Dict[str, Dict[str, str]],
    refs: Dict[int, str],
    survey_reported_keys: Optional[Set[str]],
) -> Dict[str, str]:
    """
    Map composite_section_field_key -> provenance tier name (green|blue|yellow|red).
    """
    out: Dict[str, str] = {}
    for sec_name, fields in sections.items():
        if sec_name.strip().lower() == "references":
            continue
        for field_name, raw_value in fields.items():
            ck = composite_section_field_key(sec_name, field_name)
            if field_is_absence_placeholder(raw_value):
                out[ck] = "red"
                continue
            public = field_has_public_source(raw_value, refs)
            survey = bool(survey_reported_keys and ck in survey_reported_keys)
            out[ck] = provenance_tier(public=public, survey=survey)
    return out
