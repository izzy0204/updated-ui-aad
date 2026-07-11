"""Build citation sidecars with field-level spans from pipeline evidence."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from core.chai_schema import CITATIONS_SCHEMA_VERSION, ClinicalModelCard, iter_field_placements

logger = logging.getLogger(__name__)


def _field_text(card: ClinicalModelCard, field_key: str) -> str:
    if "." in field_key:
        top, sub = field_key.split(".", 1)
        obj = getattr(card, top, None)
        if obj is None:
            return ""
        return str(getattr(obj, sub, "") or "").strip()
    if field_key.startswith("performance.metrics["):
        return ""
    val = getattr(card, field_key, None)
    if val is None:
        return ""
    if hasattr(val, "description"):
        return str(getattr(val, "description", "") or "").strip()
    if hasattr(val, "summary"):
        return str(getattr(val, "summary", "") or "").strip()
    return str(val).strip()


def align_snippet_to_field_text(field_text: str, snippet: str) -> Optional[Tuple[int, int]]:
    """Return ``(start, end)`` when *snippet* aligns in *field_text*, else ``None``."""
    if not field_text or not snippet:
        return None
    snip = snippet.strip()
    if not snip:
        return None
    idx = field_text.find(snip)
    if idx >= 0:
        return idx, idx + len(snip)
    lower_field = field_text.lower()
    lower_snip = snip.lower()
    idx = lower_field.find(lower_snip)
    if idx >= 0:
        return idx, idx + len(snip)
    return None


def _get_or_create_ref_id(
    refs: Dict[str, Dict[str, Any]],
    url: str,
    item: Optional[Dict[str, Any]] = None,
) -> str:
    for rid, meta in refs.items():
        if str(meta.get("url") or "") == url:
            return str(rid)
    rid = str(max((int(k) for k in refs.keys() if str(k).isdigit()), default=0) + 1)
    meta: Dict[str, Any] = {"url": url}
    if item:
        for k in ("title", "snippet", "source", "accessed", "type"):
            if item.get(k):
                meta[k] = item[k]
    refs[rid] = meta
    return rid


def build_sidecar_from_evidence(
    card: ClinicalModelCard,
    evidence_by_field: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build ``references`` + ``field_citations`` from agent/post-fill evidence lists.

    Uses exact snippet alignment when possible; otherwise sentence-level fallback with warning.
    """
    refs: Dict[str, Dict[str, Any]] = {}
    field_citations: Dict[str, List[Dict[str, Any]]] = {}
    alignment_warnings: List[str] = []

    for field_key, items in (evidence_by_field or {}).items():
        if str(field_key).startswith("_") or str(field_key).startswith("postfill."):
            continue
        if not isinstance(items, list) or not items:
            continue

        field_text = _field_text(card, str(field_key))
        spans: List[Dict[str, Any]] = []
        ref_ids: List[str] = []

        for item in items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            rid = _get_or_create_ref_id(refs, url, item)
            ref_ids.append(rid)
            snippet = str(item.get("snippet") or "").strip()
            if field_text and snippet:
                aligned = align_snippet_to_field_text(field_text, snippet)
                if aligned:
                    start, end = aligned
                    spans.append(
                        {
                            "text": field_text[start:end],
                            "citationIds": [rid],
                        }
                    )
                else:
                    alignment_warnings.append(f"snippet_mismatch:{field_key}")

        if spans:
            field_citations[str(field_key)] = spans
        elif ref_ids:
            field_citations[str(field_key)] = [
                {"citationIds": ref_ids, "sentence_level": True}
            ]
            alignment_warnings.append(f"sentence_level_fallback:{field_key}")

    return {
        "schema_version": CITATIONS_SCHEMA_VERSION,
        "references": refs,
        "field_citations": field_citations,
        "_alignment_warnings": alignment_warnings,
    }


def merge_citation_sidecars(
    base: Optional[Dict[str, Any]],
    built: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge span sidecar into existing pipeline citations without losing legacy keys."""
    out: Dict[str, Any] = dict(base or {})
    out.setdefault("schema_version", built.get("schema_version", CITATIONS_SCHEMA_VERSION))

    refs = dict(out.get("references") or {})
    for rid, meta in (built.get("references") or {}).items():
        if rid not in refs and isinstance(meta, dict):
            refs[rid] = meta
    if refs:
        out["references"] = refs

    fc = dict(out.get("field_citations") or out.get("fieldCitations") or {})
    for fk, spans in (built.get("field_citations") or {}).items():
        if fk not in fc:
            fc[fk] = spans
    if fc:
        out["field_citations"] = fc

    warns = list(out.get("_alignment_warnings") or [])
    warns.extend(built.get("_alignment_warnings") or [])
    if warns:
        out["_alignment_warnings"] = warns
    return out
