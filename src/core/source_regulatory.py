"""Regulatory tier inference from per-field citation sources (URLs + snippets)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from core.card_regulatory import classify_regulatory_status, merge_regulatory_tiers
from core.chai_schema import ClinicalModelCard, iter_field_placements
from core.dermauto_card_render import composite_section_field_key

_RESERVED_CITATION_KEYS = frozenset(
    {"_sources_metadata", "_regulatory_tiers", "_regulatory_tiers_composite"}
)

# source_type -> default regulatory tier when snippet has no stronger signal
_SOURCE_TYPE_TIER: Dict[str, str] = {
    "fda_approval": "green",
    "ema_approval": "blue",
    "ce_marking": "blue",
    "eua": "yellow",
    "clinical_trial": "orange",
    "investigational": "orange",
    "pubmed_paper": "gray",
    "arxiv_paper": "gray",
    "github_repo": "gray",
    "manufacturer_site": "gray",
    "web": "gray",
}

_FDA_HOSTS = frozenset(
    {
        "fda.gov",
        "www.fda.gov",
        "accessdata.fda.gov",
        "www.accessdata.fda.gov",
    }
)
_EU_REG_HOSTS = frozenset(
    {
        "ema.europa.eu",
        "ec.europa.eu",
        "eudamedweb.ec.europa.eu",
    }
)
_TRIAL_HOSTS = frozenset(
    {
        "clinicaltrials.gov",
        "www.clinicaltrials.gov",
    }
)


def infer_source_type(url: str, *, snippet: str = "") -> str:
    """Classify a citation URL (and optional snippet) into a source_type string."""
    u = (url or "").strip()
    if not u:
        return "web"

    try:
        host = (urlparse(u).netloc or "").lower()
    except Exception:
        host = ""

    path = (urlparse(u).path or "").lower()
    blob = f"{host} {path} {snippet}".lower()

    if host in _FDA_HOSTS or "fda.gov" in host:
        if "emergency" in blob or re.search(r"\beua\b", blob):
            return "eua"
        return "fda_approval"

    if host in _EU_REG_HOSTS or "ce-mark" in path or "cemark" in path:
        return "ce_marking"

    if host in _TRIAL_HOSTS:
        return "clinical_trial"

    if "clinicaltrials" in blob or "clinical trial" in blob:
        return "clinical_trial"

    if "pubmed.ncbi.nlm.nih.gov" in host or "ncbi.nlm.nih.gov/pubmed" in u.lower():
        return "pubmed_paper"

    if "arxiv.org" in host:
        return "arxiv_paper"

    if "github.com" in host or "huggingface.co" in host:
        return "github_repo"

    if re.search(r"\binvestigational\b|\bresearch\s+use\s+only\b", blob):
        return "investigational"

    if re.search(r"\bce\s*[- ]?mark", blob):
        return "ce_marking"

    if re.search(r"\beua\b|emergency\s+use\s+authorization", blob):
        return "eua"

    return "web"


def tier_from_source_type(source_type: str) -> str:
    return _SOURCE_TYPE_TIER.get(source_type, "gray")


def tier_from_citation_item(item: Dict[str, Any]) -> str:
    """Regulatory tier for one evidence item {url, snippet, ...}."""
    if not isinstance(item, dict):
        return "gray"
    url = str(item.get("url") or "").strip()
    snippet = str(item.get("snippet") or "").strip()
    source_type = str(item.get("source_type") or "").strip() or infer_source_type(url, snippet=snippet)

    from_snippet = classify_regulatory_status(snippet) if snippet else "gray"
    from_source = tier_from_source_type(source_type)

    # Snippet can sharpen generic FDA pages (e.g. EUA called out in quote).
    if from_snippet != "gray":
        return merge_regulatory_tiers(from_snippet, from_source)
    return from_source


def _citation_lists_for_field(citations: Dict[str, Any], field_name: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    keys = [field_name, f"postfill.{field_name}"]
    for key in keys:
        lst = citations.get(key)
        if not isinstance(lst, list):
            continue
        for item in lst:
            if isinstance(item, dict) and str(item.get("url", "")).strip():
                out.append(item)
    return out


def _norm_field_key(key: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", key.lower()).strip("_")


def _citation_lists_for_field_fuzzy(citations: Dict[str, Any], field_name: str) -> List[Dict[str, Any]]:
    """Gather citations keyed by CHAI name or agent dotted paths ending in the field."""
    out = _citation_lists_for_field(citations, field_name)
    if out:
        return out
    want = _norm_field_key(field_name)
    for key, lst in citations.items():
        if key in _RESERVED_CITATION_KEYS or not isinstance(lst, list):
            continue
        kn = _norm_field_key(key.replace("postfill.", ""))
        if kn == want or kn.endswith("_" + want) or want.endswith("_" + kn):
            for item in lst:
                if isinstance(item, dict) and str(item.get("url", "")).strip():
                    out.append(item)
    return out


def regulatory_tier_for_field(citations: Dict[str, Any], field_name: str) -> str:
    """Merge tiers from all citation sources attached to a CHAI field."""
    items = _citation_lists_for_field_fuzzy(citations, field_name)
    if not items:
        return "gray"
    tiers = [tier_from_citation_item(it) for it in items]
    return merge_regulatory_tiers(*tiers)


def enrich_citations_with_source_metadata(citations: Dict[str, Any]) -> Dict[str, Any]:
    """Attach source_type and regulatory_tier on each citation dict (in place)."""
    if not isinstance(citations, dict):
        return citations

    meta = citations.get("_sources_metadata")
    if isinstance(meta, dict):
        for url, info in meta.items():
            if not isinstance(info, dict):
                continue
            snip = str(info.get("reason") or "")
            st = infer_source_type(url, snippet=snip)
            info.setdefault("source_type", st)
            info.setdefault("regulatory_tier", tier_from_source_type(st))

    for key, lst in citations.items():
        if key in _RESERVED_CITATION_KEYS or not isinstance(lst, list):
            continue
        for item in lst:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if not item.get("source_type"):
                item["source_type"] = infer_source_type(url, snippet=snippet)
            if not item.get("regulatory_tier"):
                item["regulatory_tier"] = tier_from_citation_item(item)
    return citations


def compute_regulatory_tiers_for_card(
    chai_card: ClinicalModelCard,
    citations: Dict[str, Any],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Return (tiers_by_field_name, tiers_by_composite_section_label_key).

  Enum-first: only the regulatory approval status row receives a non-gray tier.
    """
    from core.card_regulatory import regulatory_tier_for_card

    enrich_citations_with_source_metadata(citations)

    status_tier = regulatory_tier_for_card(chai_card)
    by_field: Dict[str, str] = {}
    by_composite: Dict[str, str] = {}

    for section, field_name, label in iter_field_placements():
        tier = status_tier if field_name == "regulatory_approval_status" else "gray"
        by_field[field_name] = tier
        by_composite[composite_section_field_key(section, label)] = tier

    citations["_regulatory_tiers"] = by_field
    citations["_regulatory_tiers_composite"] = by_composite
    return by_field, by_composite


def _fda_records_as_list(fda_records: Any) -> List[Dict[str, Any]]:
    if not fda_records:
        return []
    if isinstance(fda_records, dict):
        if "k_number" in fda_records or "url" in fda_records or "k_number_url" in fda_records:
            return [fda_records]
        return []
    return [r for r in fda_records if isinstance(r, dict)]


def attach_fda_records_to_citations(
    citations: Dict[str, Any],
    fda_records: Any,
) -> Dict[str, Any]:
    """Add FDA API / accessdata URLs as typed sources for the regulatory field."""
    records = _fda_records_as_list(fda_records)
    if not records:
        return citations
    field = "regulatory_approval_status"
    lst = citations.setdefault(field, [])
    if not isinstance(lst, list):
        lst = []
        citations[field] = lst

    for rec in records[:5]:
        if not isinstance(rec, dict):
            continue
        url = str(rec.get("url") or rec.get("link") or "").strip()
        if not url and rec.get("k_number"):
            from utils.fda_discovery import make_510k_record_urls  # type: ignore

            urls = make_510k_record_urls(str(rec["k_number"]))
            url = urls.get("search") or urls.get("alt_search") or ""
        if not url:
            continue
        snippet = str(rec.get("device_name") or rec.get("summary") or "FDA 510(k) record")[:240]
        lst.append(
            {
                "url": url,
                "snippet": snippet,
                "source_type": "fda_approval",
                "regulatory_tier": "green",
            }
        )
    return citations


def citations_json_path_for_markdown(md_path: Path) -> Path:
    name = md_path.name
    if name.endswith(".clinical.md"):
        return md_path.with_name(name.replace(".clinical.md", ".citations.json"))
    if name.endswith(".clinical.json"):
        return md_path.with_name(name.replace(".clinical.json", ".citations.json"))
    return md_path.with_suffix(".citations.json")


def load_citations_for_markdown(md_path: Path) -> Optional[Dict[str, Any]]:
    path = citations_json_path_for_markdown(md_path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def regulatory_by_key_from_citations(
    sections: Dict[str, Dict[str, str]],
    citations: Dict[str, Any],
) -> Dict[str, str]:
    """Build composite_key -> tier for UI rendering from pipeline citations."""
    composite = citations.get("_regulatory_tiers_composite")
    if isinstance(composite, dict) and composite:
        out: Dict[str, str] = {}
        for sec_name, fields in sections.items():
            if sec_name.strip().lower() == "references":
                continue
            for field_name in fields:
                ck = composite_section_field_key(sec_name, field_name)
                tier = composite.get(ck)
                if tier:
                    out[ck] = str(tier)
                else:
                    out[ck] = "gray"
        return out

    # Recompute if only _regulatory_tiers present
    by_field = citations.get("_regulatory_tiers")
    if not isinstance(by_field, dict):
        return {}

    label_to_field: Dict[str, str] = {}
    for _sec, fname, label in iter_field_placements():
        label_to_field[label] = fname

    out = {}
    for sec_name, fields in sections.items():
        if sec_name.strip().lower() == "references":
            continue
        for label in fields:
            ck = composite_section_field_key(sec_name, label)
            fname = label_to_field.get(label)
            out[ck] = str(by_field.get(fname, "gray")) if fname else "gray"
    return out


def regulatory_by_key_from_field_citations(
    sections: Dict[str, Dict[str, str]],
    citations: Dict[str, Any],
    refs: Dict[int, str],
) -> Dict[str, str]:
    """
    Derive per-row tiers from inline [n] markers -> reference URLs when composite
    metadata is missing (e.g. hand-edited markdown with references).
    """
    from core.dermauto_card_render import CITATION_IN_TEXT

    enrich_citations_with_source_metadata(citations)
    url_tier_cache: Dict[str, str] = {}
    out: Dict[str, str] = {}

    for sec_name, fields in sections.items():
        if sec_name.strip().lower() == "references":
            continue
        for label, raw_value in fields.items():
            ck = composite_section_field_key(sec_name, label)
            tiers: List[str] = []
            for m in CITATION_IN_TEXT.finditer(raw_value):
                inner = m.group(1)
                for x in inner.split(","):
                    xs = x.strip()
                    if not xs.isdigit():
                        continue
                    url = refs.get(int(xs), "")
                    if not url:
                        continue
                    if url not in url_tier_cache:
                        url_tier_cache[url] = tier_from_citation_item(
                            {"url": url, "snippet": "", "source_type": infer_source_type(url)}
                        )
                    tiers.append(url_tier_cache[url])
            out[ck] = merge_regulatory_tiers(*tiers) if tiers else "gray"
    return out
