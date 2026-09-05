"""Render-time citation normalization and injection for clinical model cards."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.dermauto_card_render import CITATION_IN_TEXT
from utils.sentence_utils import split_sentences

logger = logging.getLogger(__name__)

_RESERVED_SIDEcar_KEYS = frozenset(
    {
        "_sources_metadata",
        "_regulatory_tiers",
        "_regulatory_tiers_composite",
        "schema_version",
        "schemaVersion",
        "regulatory_status_source",
        "regulatory_status_confidence",
        "regulatoryStatusSource",
        "regulatoryStatusConfidence",
    }
)

_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_URL = re.compile(r"https?://[^\s<>()]+")


@dataclass
class NormalizedCitations:
    """Normalized citation sidecar for rendering."""

    references: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    field_spans: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    available: bool = False


def parse_citation_numbers(marker_inner: str) -> List[int]:
    nums: List[int] = []
    for part in marker_inner.split(","):
        xs = part.strip()
        if xs.isdigit():
            nums.append(int(xs))
    return nums


def format_citation_marker(citation_ids: List[int]) -> str:
    """Grouped marker format used across the project: ``[1,3]``."""
    uniq: List[int] = []
    seen: Set[int] = set()
    for n in citation_ids:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    if not uniq:
        return ""
    return f" [{','.join(str(n) for n in sorted(uniq))}]"


def strip_inline_citation_markers(text: str) -> str:
    return re.sub(r"\s*\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", text).strip()


def parse_text_citation_spans(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parse legacy inline ``[n]`` markers into clean text plus span records.

    Returns ``(clean_text, [{"text": segment, "citationIds": ["1", ...]}, ...])``.
    """
    if not text or not text.strip():
        return text, []

    spans: List[Dict[str, Any]] = []
    clean_parts: List[str] = []
    pos = 0
    for m in CITATION_IN_TEXT.finditer(text):
        segment = text[pos : m.start()].strip()
        ids = parse_citation_numbers(m.group(1))
        if segment:
            spans.append({"text": segment, "citationIds": [str(i) for i in ids]})
            clean_parts.append(segment)
        pos = m.end()

    tail = text[pos:].strip()
    if tail:
        spans.append({"text": tail, "citationIds": []})
        clean_parts.append(tail)

    if not spans:
        return text, []

    clean = " ".join(clean_parts)
    return clean, spans


def _url_for_ref_entry(entry: Dict[str, Any]) -> str:
    return str(entry.get("url") or entry.get("href") or "").strip()


def _get_or_create_ref_id(
    refs: Dict[int, Dict[str, Any]],
    url: str,
    item: Optional[Dict[str, Any]] = None,
) -> int:
    for rid, meta in refs.items():
        if _url_for_ref_entry(meta) == url:
            return rid
    rid = max(refs.keys(), default=0) + 1
    meta: Dict[str, Any] = {"url": url}
    if item:
        for k in ("title", "snippet", "source", "accessed", "type"):
            if item.get(k):
                meta[k] = item[k]
        if not meta.get("title") and meta.get("snippet"):
            meta["title"] = str(meta["snippet"])[:120]
    refs[rid] = meta
    return rid


def normalize_citation_sidecar(sidecar: Optional[Dict[str, Any]]) -> NormalizedCitations:
    """Normalize legacy ``fields`` and new ``references`` / ``fieldCitations`` shapes."""
    if not sidecar or not isinstance(sidecar, dict):
        return NormalizedCitations(available=False)

    refs: Dict[int, Dict[str, Any]] = {}
    field_spans: Dict[str, List[Dict[str, Any]]] = {}

    raw_refs = sidecar.get("references") or {}
    if isinstance(raw_refs, dict):
        for k, v in raw_refs.items():
            if not isinstance(v, dict):
                continue
            try:
                rid = int(str(k))
            except ValueError:
                continue
            url = _url_for_ref_entry(v)
            if url:
                refs[rid] = dict(v)
                refs[rid]["url"] = url

    raw_fc = sidecar.get("field_citations") or sidecar.get("fieldCitations") or {}
    if isinstance(raw_fc, dict):
        for fk, spans in raw_fc.items():
            if isinstance(spans, list) and spans:
                field_spans[str(fk)] = [dict(s) for s in spans if isinstance(s, dict)]

    legacy_fields = sidecar.get("fields") or {}
    if isinstance(legacy_fields, dict):
        for fname, lst in legacy_fields.items():
            if not isinstance(lst, list) or not lst:
                continue
            ids: List[int] = []
            for item in lst:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()
                if not url:
                    continue
                ids.append(_get_or_create_ref_id(refs, url, item))
            if ids and str(fname) not in field_spans:
                field_spans[str(fname)] = [
                    {"citationIds": [str(i) for i in ids], "sentence_level": True}
                ]

    # Top-level field keys from pipeline (non-reserved)
    for key, lst in sidecar.items():
        if key in _RESERVED_SIDEcar_KEYS or key in ("fields", "references", "field_citations", "fieldCitations"):
            continue
        if not isinstance(lst, list):
            continue
        ids = []
        for item in lst:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if url:
                ids.append(_get_or_create_ref_id(refs, url, item))
        if ids and str(key) not in field_spans:
            field_spans[str(key)] = [{"citationIds": [str(i) for i in ids], "sentence_level": True}]

    available = bool(refs) or bool(field_spans)
    return NormalizedCitations(references=refs, field_spans=field_spans, available=available)


def references_url_map(refs: Dict[int, Dict[str, Any]]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for rid, meta in refs.items():
        url = _url_for_ref_entry(meta)
        if url:
            out[rid] = url
    return out


def _marker_already_at(text: str, pos: int, marker: str) -> bool:
    return text[pos : pos + len(marker)] == marker


def _protected_spans(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    for pat in (_MD_LINK, _URL):
        for m in pat.finditer(text):
            spans.append((m.start(), m.end()))
    return spans


def _inside_protected(pos: int, protected: List[Tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in protected)


def inject_citations_into_text(
    text: str,
    spans: Optional[List[Dict[str, Any]]],
    *,
    fallback_ids: Optional[List[int]] = None,
) -> str:
    """
    Insert plain-text ``[n]`` markers into *text* using explicit spans or sentence-level fallback.

    Does not escape HTML. Skips protected URL / markdown-link regions.
    """
    if not text or not text.strip():
        return text

    base = strip_inline_citation_markers(text)
    if not spans and not fallback_ids:
        return base

    protected = _protected_spans(base)
    out = base

    explicit = [s for s in (spans or []) if not s.get("sentence_level")]
    if explicit:
        insertions: List[Tuple[int, str]] = []
        for span in explicit:
            cite_raw = span.get("citationIds") or span.get("citation_ids") or []
            ids = [int(x) for x in cite_raw if str(x).strip().isdigit()]
            if not ids:
                continue
            snippet = str(span.get("text") or "").strip()
            if not snippet:
                continue
            idx = out.find(snippet)
            if idx < 0:
                logger.warning("Citation span not found in field text; skipping exact span")
                continue
            pos = idx + len(snippet)
            if _inside_protected(pos, protected):
                continue
            marker = format_citation_marker(ids)
            if marker and not _marker_already_at(out, pos, marker):
                insertions.append((pos, marker))

        for pos, marker in sorted(insertions, key=lambda x: x[0], reverse=True):
            out = out[:pos] + marker + out[pos:]
        return out

    ids = fallback_ids or []
    for span in spans or []:
        if span.get("sentence_level"):
            raw = span.get("citationIds") or span.get("citation_ids") or []
            ids = [int(x) for x in raw if str(x).strip().isdigit()]
            break

    if not ids:
        return out

    if spans:
        logger.warning("Using sentence_level citation fallback for field text")

    marker = format_citation_marker(ids)
    if not marker:
        return out

    sentences = split_sentences(out)
    if not sentences:
        return out + marker

    rebuilt: List[str] = []
    cursor = 0
    for sent in sentences:
        idx = out.find(sent, cursor)
        if idx < 0:
            rebuilt.append(sent + marker)
            continue
        end = idx + len(sent)
        chunk = out[cursor:end]
        if not chunk.rstrip().endswith("]"):
            chunk = chunk.rstrip() + marker
        rebuilt.append(chunk)
        cursor = end
    tail = out[cursor:]
    if tail:
        rebuilt.append(tail)
    return "".join(rebuilt) if rebuilt else out + marker


def build_references_from_md(md_text: str) -> Dict[int, Dict[str, Any]]:
    from core.dermauto_card_render import parse_references

    ref_urls = parse_references(md_text)
    return {n: {"url": url, "title": "", "source": ""} for n, url in ref_urls.items()}


def build_field_citations_from_legacy_text(
    legacy_text: str,
    references: Dict[int, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[int], Set[int]]:
    """
    Parse inline markers from legacy v0.3 field prose.

    Returns ``(spans, unmatched_ids, cited_ids)``.
    """
    _, spans = parse_text_citation_spans(legacy_text)
    unmatched: List[int] = []
    cited: Set[int] = set()
    for span in spans:
        for raw in span.get("citationIds") or []:
            if not str(raw).isdigit():
                continue
            n = int(raw)
            cited.add(n)
            if n not in references:
                unmatched.append(n)
    return spans, unmatched, cited


def section_label_to_field_key(section: str, label: str, card: Any) -> str:
    from core.chai_schema import iter_field_placements

    for sec, fname, disp in iter_field_placements():
        if sec == section and disp == label:
            if fname == "training_data":
                return "training_data.description"
            if fname == "model_development_and_validation":
                return "model_development_and_validation.description"
            if fname == "performance":
                return "performance.summary"
            if fname == "contact":
                return "contact"
            if fname == "clinical_trial":
                return "clinical_trial"
            return fname

    if label.startswith("Performance — ") and card is not None:
        name = label[len("Performance — ") :]
        for i, m in enumerate(getattr(getattr(card, "performance", None), "metrics", []) or []):
            if getattr(m, "name", None) == name:
                return f"performance.metrics[{i}]"
    return label


def apply_render_time_citations(
    sections: Dict[str, Dict[str, str]],
    *,
    card: Any,
    normalized: NormalizedCitations,
) -> Dict[str, Dict[str, str]]:
    """Strip presentation markers from section text and inject from the citation sidecar."""
    out: Dict[str, Dict[str, str]] = {}
    for sec_name, fields in sections.items():
        out[sec_name] = {}
        for label, value in fields.items():
            field_key = section_label_to_field_key(sec_name, label, card)
            clean = strip_inline_citation_markers(value)
            spans = normalized.field_spans.get(field_key) or normalized.field_spans.get(
                field_key.split(".")[0]
            )
            fallback: List[int] = []
            if spans:
                for span in spans:
                    if span.get("sentence_level"):
                        raw = span.get("citationIds") or span.get("citation_ids") or []
                        fallback = [int(x) for x in raw if str(x).strip().isdigit()]
                        break
            injected = inject_citations_into_text(clean, spans, fallback_ids=fallback or None)
            out[sec_name][label] = injected
    return out


# Display-label prefixes used in clinical markdown bullets → sidecar field keys.
_MD_LABEL_TO_FIELD_KEY: Tuple[Tuple[str, str], ...] = (
    ("Model Name", "model_name"),
    ("Developer", "developer"),
    ("Regulatory Approval Status", "regulatory_approval_status"),
    ("Regulatory Approval Date", "regulatory_approval_date"),
    ("Version", "version"),
    ("Last Updated", "last_updated"),
    ("Availability", "availability"),
    ("Summary", "summary"),
    ("Medical Purpose", "medical_purpose"),
    ("Acceptable Input", "acceptable_input"),
    ("Output", "output"),
    ("Role in Decision-Making", "role_in_decision_making"),
    ("Intended Users", "intended_users"),
    ("Target Patient Population", "target_patient_population"),
    ("Known Performance Limitations", "known_performance_limitations"),
    ("Skin Type Representation & Equity", "skin_type_representation_equity"),
    ("Required Clinician Oversight", "required_clinician_oversight"),
    ("Model Type", "model_type"),
    ("Training Data", "training_data.description"),
    ("Model Development & Validation", "model_development_and_validation.description"),
    ("Clinical Trial", "clinical_trial"),
    ("Performance", "performance.summary"),
    ("Limitations in Evaluating Performance", "performance_evaluation_limitations"),
    ("Plans for Ongoing Monitoring", "ongoing_monitoring_plan"),
    ("Scheduled Updates", "scheduled_updates"),
    ("Inquiries / Report an Issue", "contact"),
)

_MD_FIELD_BULLET = re.compile(r"^\s*-\s*\*\*([^*]+):\*\*\s*(.*)$")
_MD_CITE_GROUP = re.compile(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]")


def _md_label_to_field_key(label: str) -> Optional[str]:
    label = label.strip()
    for base, key in sorted(_MD_LABEL_TO_FIELD_KEY, key=lambda x: -len(x[0])):
        if label == base:
            return key
        if (
            label.startswith(base + " ")
            or label.startswith(base + "—")
            or label.startswith(base + "–")
            or label.startswith(base + " /")
            or label.startswith(base + " (")
        ):
            return key
    return None


def build_sidecar_from_clinical_md(md_text: str) -> Dict[str, Any]:
    """Build ``references`` + ``field_citations`` from clinical markdown with inline ``[n]`` markers."""
    references = build_references_from_md(md_text)
    ids_by_field: Dict[str, Set[int]] = {}
    for raw in md_text.splitlines():
        m = _MD_FIELD_BULLET.match(raw)
        if not m:
            continue
        field_key = _md_label_to_field_key(m.group(1))
        if not field_key:
            continue
        ids: Set[int] = set()
        for group in _MD_CITE_GROUP.findall(m.group(2)):
            for part in group.split(","):
                part = part.strip()
                if part.isdigit():
                    n = int(part)
                    if n in references:
                        ids.add(n)
        if ids:
            ids_by_field.setdefault(field_key, set()).update(ids)

    field_citations = {
        fk: [{"citationIds": [str(i) for i in sorted(ids)], "sentence_level": True}]
        for fk, ids in sorted(ids_by_field.items())
    }
    return {
        "schema_version": "clinical-model-card-citations-1.0",
        "references": {str(n): meta for n, meta in sorted(references.items())},
        "field_citations": field_citations,
    }


def ensure_clickable_citations(
    citations: Optional[Dict[str, Any]],
    md_path: Optional[Path] = None,
    md_text: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    If the sidecar has no usable references/field citations, fill them from companion
    clinical markdown (keeps existing keys such as ``_sources_metadata``).
    """
    normalized = normalize_citation_sidecar(citations)
    if normalized.available:
        return citations

    text = md_text
    if text is None and md_path is not None:
        p = Path(md_path)
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                text = None
    if not text or not str(text).strip():
        return citations

    built = build_sidecar_from_clinical_md(text)
    if not built.get("references"):
        return citations

    merged: Dict[str, Any] = dict(citations) if isinstance(citations, dict) else {}
    merged.setdefault("schema_version", built["schema_version"])
    merged["references"] = built["references"]
    merged["field_citations"] = built["field_citations"]
    logger.info(
        "Enriched empty citation sidecar from clinical markdown (%d refs, %d fields)",
        len(built["references"]),
        len(built["field_citations"]),
    )
    return merged
