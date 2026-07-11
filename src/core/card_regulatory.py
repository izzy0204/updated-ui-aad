"""Regulatory status tiers for model cards (status row/badge only)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Pattern, Union

from core.chai_schema import RegulatoryApprovalStatus
from core.dermauto_card_render import composite_section_field_key, strip_citations

_REGULATORY_STATUS_LABEL = "Regulatory Approval Status"


def tier_for_regulatory_status(status: Union[RegulatoryApprovalStatus, str]) -> str:
    """Map enum to UI tier color."""
    if isinstance(status, str):
        try:
            status = RegulatoryApprovalStatus(status)
        except ValueError:
            return "gray"
    mapping = {
        RegulatoryApprovalStatus.NOT_AUTHORIZED_CONSUMER_TOOL: "red",
        RegulatoryApprovalStatus.INVESTIGATIONAL_RESEARCH_USE_ONLY: "orange",
        RegulatoryApprovalStatus.EUA_AUTHORIZED: "yellow",
        RegulatoryApprovalStatus.FDA_APPROVED: "green",
        RegulatoryApprovalStatus.FDA_CLEARED: "green",
        RegulatoryApprovalStatus.CE_MARKED: "blue",
        RegulatoryApprovalStatus.UNKNOWN: "gray",
    }
    return mapping.get(status, "gray")

# Higher index = stronger authorization when merging tiers.
_TIER_PRIORITY: Dict[str, int] = {
    "green": 5,
    "yellow": 4,
    "blue": 3,
    "orange": 2,
    "red": 1,
    "gray": 0,
}

_VALID_TIERS = frozenset(_TIER_PRIORITY.keys())

_REGULATORY_METADATA_FIELD_MARKERS: tuple[str, ...] = (
    "regulatory approval status",
    "global availability",
)

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
    Map text to a regulatory tier: green | yellow | blue | orange | red | gray.
    """
    text = strip_citations(raw_value).strip()
    if _is_absence_placeholder(text):
        return "gray"

    lowered = text.lower()
    if any(p.search(lowered) for p in _RED_PATTERNS):
        return "red"

    matches = _positive_tiers_matching(lowered)
    if not matches:
        return "gray"

    return max(matches, key=lambda t: _TIER_PRIORITY[t])


def merge_regulatory_tiers(*tiers: str) -> str:
    """Pick the strongest non-gray tier, or gray if none."""
    valid = [t for t in tiers if t in _VALID_TIERS and t != "gray"]
    if not valid:
        return "gray"
    return max(valid, key=lambda t: _TIER_PRIORITY[t])


def resolve_card_regulatory_tier_from_metadata(
    *,
    regulatory_approval: str = "",
    global_availability: str = "",
) -> str:
    """Card-level tier from pipeline metadata fields (used when exporting markdown)."""
    return merge_regulatory_tiers(
        classify_regulatory_status(regulatory_approval),
        classify_regulatory_status(global_availability),
    )


def _is_regulatory_metadata_field(field_name: str) -> bool:
    low = field_name.lower()
    return any(marker in low for marker in _REGULATORY_METADATA_FIELD_MARKERS)


def resolve_card_regulatory_tier(sections: Dict[str, Dict[str, str]]) -> str:
    """Derive card-level tier from Regulatory Approval / Global Availability fields."""
    texts: List[str] = []
    for sec_name, fields in sections.items():
        if sec_name.strip().lower() == "references":
            continue
        for field_name, raw_value in fields.items():
            if _is_regulatory_metadata_field(field_name):
                texts.append(raw_value)
    if not texts:
        return "gray"
    return merge_regulatory_tiers(*(classify_regulatory_status(t) for t in texts))


def parse_regulatory_tier_frontmatter(md_text: str) -> Optional[str]:
    """Read optional `regulatory_tier:` from YAML frontmatter (pipeline-generated cards)."""
    lines = md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        m = re.match(r"^regulatory_tier:\s*(\w+)\s*$", stripped, re.I)
        if m:
            tier = m.group(1).lower()
            if tier in _VALID_TIERS:
                return tier
    return None


def compute_regulatory_for_sections(
    sections: Dict[str, Dict[str, str]],
    *,
    md_text: Optional[str] = None,
    citations: Optional[Dict[str, Any]] = None,
    refs: Optional[Dict[int, str]] = None,
) -> Dict[str, str]:
    """
    Map composite_section_field_key -> regulatory tier for UI row coloring.

    Prefer pipeline citation metadata (`_regulatory_tiers_composite`) when present.
    Otherwise use per-field reference URLs, then card-level metadata text.
    """
    if citations:
        try:
            from core.source_regulatory import (
                regulatory_by_key_from_citations,
                regulatory_by_key_from_field_citations,
            )

            by_cites = regulatory_by_key_from_citations(sections, citations)
            if by_cites and any(t != "gray" for t in by_cites.values()):
                return by_cites
            if refs:
                cite_src = citations if citations else {
                    "_sources_metadata": {u: {"url": u} for u in refs.values() if str(u).strip()}
                }
                by_refs = regulatory_by_key_from_field_citations(sections, cite_src, refs)
                if by_refs and any(t != "gray" for t in by_refs.values()):
                    return by_refs
        except ImportError:
            pass

    card_tier: Optional[str] = None
    if md_text:
        card_tier = parse_regulatory_tier_frontmatter(md_text)
    if card_tier is None:
        card_tier = resolve_card_regulatory_tier(sections)

    out: Dict[str, str] = {}
    for sec_name, fields in sections.items():
        if sec_name.strip().lower() == "references":
            continue
        for field_name, raw_value in fields.items():
            ck = composite_section_field_key(sec_name, field_name)
            # Color only the regulatory approval status row/badge.
            if field_name.strip().lower() == _REGULATORY_STATUS_LABEL.lower():
                out[ck] = card_tier if card_tier else classify_regulatory_status(raw_value)
            else:
                out[ck] = "gray"
    return out


def regulatory_tier_for_card(card: Any) -> str:
    """Tier from ClinicalModelCard enum when available."""
    status = getattr(card, "regulatory_approval_status", None)
    if status is not None:
        return tier_for_regulatory_status(status)
    return "gray"
