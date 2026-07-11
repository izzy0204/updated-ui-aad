"""Evidence-based regulatory status classification for clinical model cards."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Literal, Optional, Tuple

from core.chai_schema import RegulatoryApprovalStatus

RegulatoryConfidence = Literal["authoritative", "cited_explicit", "conservative_map", "unknown"]

_CONSERVATIVE_MAP: List[Tuple[re.Pattern[str], RegulatoryApprovalStatus]] = [
    (re.compile(r"\bnot\s+(?:fda\s+)?(?:approved|cleared|authorized)\b", re.I), RegulatoryApprovalStatus.NOT_AUTHORIZED_CONSUMER_TOOL),
    (re.compile(r"\bconsumer\s+(?:tool|app|application)\b", re.I), RegulatoryApprovalStatus.NOT_AUTHORIZED_CONSUMER_TOOL),
    (re.compile(r"\bwellness\s+(?:app|tool)\b", re.I), RegulatoryApprovalStatus.NOT_AUTHORIZED_CONSUMER_TOOL),
    (re.compile(r"\binvestigational\b|\bresearch\s+use\s+only\b", re.I), RegulatoryApprovalStatus.INVESTIGATIONAL_RESEARCH_USE_ONLY),
    (re.compile(r"\beua\b|emergency\s+use\s+authorization", re.I), RegulatoryApprovalStatus.EUA_AUTHORIZED),
    (re.compile(r"\bce\s*[- ]?mark", re.I), RegulatoryApprovalStatus.CE_MARKED),
    (re.compile(r"\bde\s*novo\b", re.I), RegulatoryApprovalStatus.FDA_CLEARED),
    (re.compile(r"\bfda\s+approved\b|\bapproved\s+by\s+(?:the\s+)?fda\b", re.I), RegulatoryApprovalStatus.FDA_APPROVED),
    (re.compile(r"\bfda\s+cleared\b|\b510\s*\(\s*k\s*\)|\bcleared\s+by\s+(?:the\s+)?fda\b", re.I), RegulatoryApprovalStatus.FDA_CLEARED),
]

_MARKETING_AMBIGUOUS = re.compile(
    r"\bfda[\s-]*grade\b|\bclinically\s+validated\b|\bmedical[\s-]*grade\b",
    re.I,
)


def conservative_text_to_status(text: str) -> RegulatoryApprovalStatus:
    t = (text or "").strip()
    if not t or t.lower() in {"not specified", "unknown", "n/a", "not disclosed"}:
        return RegulatoryApprovalStatus.UNKNOWN
    if _MARKETING_AMBIGUOUS.search(t):
        return RegulatoryApprovalStatus.UNKNOWN
    if re.search(r"\bde\s*novo\b", t, re.I):
        return RegulatoryApprovalStatus.FDA_CLEARED
    for pat, status in _CONSERVATIVE_MAP:
        if pat.search(t):
            return status
    return RegulatoryApprovalStatus.UNKNOWN


def classify_from_fda_record(record: Dict[str, Any]) -> Tuple[RegulatoryApprovalStatus, Optional[date], str]:
    """Authoritative classification from FDA API record."""
    decision = str(record.get("decision") or record.get("decision_description") or "").lower()
    knum = str(record.get("k_number") or record.get("kNumber") or "").strip()
    source = f"fda_api:{knum}" if knum else "fda_api:record"

    status = RegulatoryApprovalStatus.FDA_CLEARED
    if "approved" in decision and "cleared" not in decision:
        status = RegulatoryApprovalStatus.FDA_APPROVED

    approval_date: Optional[date] = None
    for key in ("decision_date", "date_received", "decisionDate"):
        raw = record.get(key)
        if raw:
            try:
                approval_date = date.fromisoformat(str(raw)[:10])
                break
            except ValueError:
                pass

    return status, approval_date, source


def classify_regulatory_status(
    *,
    legacy_text: str = "",
    fda_records: Optional[List[Dict[str, Any]]] = None,
    cited_snippets: Optional[List[Dict[str, str]]] = None,
) -> Tuple[RegulatoryApprovalStatus, Optional[date], Optional[str], RegulatoryConfidence]:
    """
    Evidence hierarchy:
    1. FDA API record
    2. Explicit language in cited manufacturer/regulatory sources
    3. Conservative text map on legacy field
    4. UNKNOWN
    """
    if fda_records:
        for rec in fda_records:
            if isinstance(rec, dict):
                status, approval_date, source = classify_from_fda_record(rec)
                return status, approval_date, source, "authoritative"

    if cited_snippets:
        for item in cited_snippets:
            snippet = str(item.get("snippet") or "")
            url = str(item.get("url") or "").lower()
            host_ok = any(h in url for h in ("fda.gov", "accessdata.fda.gov", "ema.europa.eu", "ec.europa.eu"))
            text_for_map = snippet.strip() or (legacy_text if host_ok else "")
            if not text_for_map:
                continue
            if host_ok or "manufacturer" in str(item.get("source_type", "")):
                status = conservative_text_to_status(text_for_map)
                if status != RegulatoryApprovalStatus.UNKNOWN:
                    return status, None, f"citation:{url[:80]}", "cited_explicit"

    if legacy_text.strip():
        status = conservative_text_to_status(legacy_text)
        if status != RegulatoryApprovalStatus.UNKNOWN:
            return status, None, "conservative_text_map", "conservative_map"

    return RegulatoryApprovalStatus.UNKNOWN, None, None, "unknown"
