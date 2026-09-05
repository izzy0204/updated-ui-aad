# src/pipelines/cardgen_pipeline.py
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, fields as dc_fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List

# Web discovery (DuckDuckGo) + prefetch (HTML/PDF → text)
from utils.web_search import discover_and_fetch

# Model card scoring system
from utils.model_card_scorer import ModelCardScorer, format_score_report, get_score_summary

# Publications finder (Crossref + ArXiv)
try:
    from utils.enhanced_publication_finder import EnhancedPublicationFinder
    _HAS_PUBS = True
except Exception:
    _HAS_PUBS = False
    EnhancedPublicationFinder = None  # type: ignore

# FDA/510(k) lookup (optional — skip if not present)
try:
    # expected API: async or sync find_510k_for_product(model_name, developer?) -> List[dict]
    from utils.fda_discovery import find_510k_for_product  # type: ignore
    _HAS_FDA = True
except Exception:
    _HAS_FDA = False
    find_510k_for_product = None  # type: ignore

# === CHAI schema: single source of truth ===
from core.chai_schema import (
    CLINICAL_CARD_FIELD_NAMES,
    CLINICAL_NESTED_FIELD_SPECS,
    ClinicalModelCard,
    validate_model_card,
)
from pipelines.clinical_card_mapper import (
    _map_agent_dump_to_card,
    apply_nested_postfill,
    enforce_summary_length,
)
from core.citation_sidecar import build_sidecar_from_evidence, merge_citation_sidecars

# === Gemini agent (planning/fetch/fill/validate/backfill/finalize) ===
from agents.gemini_agent.agent import run_async as gemini_run_async

# Optional: direct Gemini access for post-fill (safe no-op if absent)
try:
    import google.genai as _genai
    from google.genai import types as _genai_types
    from config.config import get_settings as _get_settings
    _HAS_GENAI = True
except Exception:
    _HAS_GENAI = False
    _genai = None  # type: ignore
    _genai_types = None  # type: ignore
    _get_settings = None  # type: ignore



# ------------------------- small helpers -------------------------

@dataclass
class PipelineOutputs:
    json_path: Optional[Path]
    md_path: Optional[Path]
    xml_path: Optional[Path]
    citations_json_path: Optional[Path]
    scoring_txt: Optional[Path] = None


def _slugify(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in s).strip("-")[:64]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _is_placeholder_value(val: object) -> bool:
    if val is None:
        return True
    if isinstance(val, list):
        return len([x for x in val if str(x).strip()]) == 0
    s = str(val).strip()
    return (not s) or s.lower() in {"not specified", "unknown", "tbd", "n/a", "na"}


def _ensure_field_level_citations(
    chai_card: ClinicalModelCard,
    citations: Dict[str, Any],
    *,
    fallback_urls: List[str],
) -> Dict[str, Any]:
    """Ensure every substantive CHAI field has at least one citation entry.

    The markdown renderer will attach citations per sentence using URLs referenced
    under either `<field_name>` or `postfill.<field_name>`. If neither is present
    for a non-placeholder field, we inject a minimal fallback citation so the
    final model card has no uncited claims.
    """
    if not isinstance(citations, dict):
        citations = {}

    fallback_url = next((u for u in fallback_urls if str(u).strip()), "")
    if not fallback_url:
        return citations

    field_names: List[str] = []
    if is_dataclass(chai_card):
        field_names = [f.name for f in dc_fields(chai_card)]
    else:
        field_names = list(getattr(chai_card, "__dict__", {}).keys())

    skip = {"schema_version", "regulatory_approval_date", "last_updated", "application_url", "availability", "clinical_trial", "training_data", "model_development_and_validation", "performance", "contact", "ongoing_monitoring_plan", "scheduled_updates", "regulatory_approval_status"}
    for fname in field_names:
        if fname in skip:
            continue
        v = getattr(chai_card, fname, None)
        if _is_placeholder_value(v):
            continue

        has_any = False
        for key in (fname, f"postfill.{fname}"):
            lst = citations.get(key)
            if isinstance(lst, list) and any(isinstance(it, dict) and str(it.get("url", "")).strip() for it in lst):
                has_any = True
                break

        if not has_any:
            citations[fname] = [{"url": fallback_url, "snippet": "Fallback citation (field-level)."}]

    return citations


# ---------- Normalization + resilient fallback mapping ----------

def _norm_key(s: str) -> str:
    """
    Normalize section/key names from Gemini dumps (handles human headings, punctuation, case).
    Examples:
      "Usefulness / Efficacy: Goal" -> "usefulness.efficacy.goal"
      "resources.evaluation references" -> "resources.evaluation.references"
    """
    s = s or ""
    s = s.strip().lower()
    s = re.sub(r"[／/|]+", " ", s)          # slashes/pipes → space
    s = re.sub(r"\s+", " ", s)              # collapse spaces
    s = s.replace(" & ", " and ")
    s = s.replace(" - ", " ")
    s = s.replace("-", " ")
    s = s.replace(":", "")
    s = s.replace(",", "")
    s = s.replace("(", "").replace(")", "")
    s = s.replace("’", "'")
    s = s.strip()
    return s.replace(" ", ".")


def _flatten_with_normalization(d: dict) -> dict:
    """Flatten 1-level dict and add normalized keys; handles human headings."""
    flat = {}
    for k, v in d.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                raw = f"{k}.{k2}"
                flat[raw] = v2
                flat[_norm_key(raw)] = v2
        else:
            flat[k] = v
            flat[_norm_key(k)] = v
    return flat


def _map_agent_dump_to_chai(agent_dump: Dict[str, Any], *, user_model_name: str = "", user_developer_name: str = "", user_application_url: str = "", fda_records: Optional[List[Dict[str, Any]]] = None) -> ClinicalModelCard:
    """Map agent output to ClinicalModelCard (v1.0)."""
    return _map_agent_dump_to_card(
        agent_dump,
        user_model_name=user_model_name,
        user_developer_name=user_developer_name,
        user_application_url=user_application_url,
        fda_records=fda_records,
    )


# ------------------------- enrichment helpers -------------------------

def _looks_clinical(text: str) -> bool:
    """Tiny heuristic to decide if we should try FDA search."""
    t = (text or "").lower()
    hints = ("derm", "skin", "lesion", "melanoma", "biopsy", "clinical", "patient", "diagnos", "risk")
    return any(h in t for h in hints)


async def _fetch_publications(model_name: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (publications, seed_pages_from_pubs)
    Each publication -> seed page uses title + abstract for high-signal priming.
    """
    pubs: list[dict] = []
    pages: list[dict] = []
    if not _HAS_PUBS or not EnhancedPublicationFinder:
        return pubs, pages

    try:
        async with EnhancedPublicationFinder() as finder:
            pubs = await finder.comprehensive_publication_search(model_name)
        for p in pubs:
            url = p.get("url") or p.get("doi_url") or ""
            title = (p.get("title") or "").strip()
            abstract = (p.get("abstract") or "").strip()
            if not url or not (title or abstract):
                continue
            body = f"{title}\n\n{abstract}".strip()
            pages.append({"url": url, "text": body})
    except Exception:
        pubs, pages = [], []
    return pubs, pages


async def _fetch_fda_records(model_name: str, developer_name: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (fda_records, seed_pages_from_fda)
    We accept either sync or async implementations of find_510k_for_product.
    """
    fda: list[dict] = []
    pages: list[dict] = []
    if not _HAS_FDA or not find_510k_for_product:
        return fda, pages

    try:
        # try await if coroutine
        if asyncio.iscoroutinefunction(find_510k_for_product):
            fda = await find_510k_for_product(model_name, developer_name)
        else:
            fda = await asyncio.to_thread(find_510k_for_product, model_name, developer_name)
    except Exception:
        fda = []

    # Build seed pages (compact summary for Gemini context)
    for rec in fda or []:
        url = (rec.get("url") or rec.get("k_number_url") or "").strip()
        knum = (rec.get("k_number") or rec.get("kNumber") or "").strip()
        decision = (rec.get("decision") or rec.get("decision_date") or "").strip()
        dev = (rec.get("applicant") or rec.get("applicant_name") or "").strip()
        indications = (rec.get("indications_for_use") or "").strip()
        blurb = f"FDA 510(k) Record {knum} — Decision: {decision} — Applicant: {dev}\nIndications: {indications}".strip()
        if url and blurb:
            pages.append({"url": url, "text": blurb})
    return fda, pages


# ------------------------- post-fill helpers -------------------------

def _collect_empty_clinical_fields(card: ClinicalModelCard) -> list[str]:
    """Return clinical field paths that are empty (including nested subfields)."""
    empties: list[str] = []
    if not is_dataclass(card):
        return empties
    skip = {
        "schema_version",
        "regulatory_approval_date",
        "last_updated",
        "application_url",
        "availability",
        "ongoing_monitoring_plan",
        "scheduled_updates",
        "regulatory_approval_status",
    }
    for f in dc_fields(card):
        if f.name in skip:
            continue
        val = getattr(card, f.name, None)
        if f.name == "training_data":
            if not (getattr(val, "description", None) or "").strip():
                empties.append("training_data.description")
            continue
        if f.name == "model_development_and_validation":
            if not (getattr(val, "description", None) or "").strip():
                empties.append("model_development_and_validation.description")
            continue
        if f.name == "clinical_trial":
            ct = val
            if ct is None or not any(
                (getattr(ct, "identifier", None) or "").strip()
                or (getattr(ct, "url", None) or "").strip()
                or (getattr(ct, "description", None) or "").strip()
            ):
                empties.append("clinical_trial.description")
            continue
        if f.name == "performance":
            if not (getattr(val, "summary", None) or "").strip():
                empties.append("performance.summary")
            for i, m in enumerate(getattr(val, "metrics", None) or []):
                if not (getattr(m, "name", None) or "").strip() or not (getattr(m, "value", None) or "").strip():
                    empties.append(f"performance.metrics[{i}]")
            continue
        if f.name == "contact":
            if not (getattr(val, "email", None) or "").strip() and not (getattr(val, "url", None) or "").strip():
                empties.append("contact.url")
            continue
        if isinstance(val, str) and not val.strip():
            empties.append(f.name)
    return empties


def _is_clinical_field_filled(card: ClinicalModelCard, field_name: str) -> bool:
    if field_name == "training_data":
        return bool((card.training_data.description or "").strip())
    if field_name == "performance":
        return bool((card.performance.summary or "").strip()) or bool(card.performance.metrics)
    if field_name == "contact":
        return bool(card.contact.email or card.contact.url)
    val = getattr(card, field_name, None)
    if isinstance(val, str):
        return bool(val.strip())
    return val is not None


def _apply_postfill_value(card: ClinicalModelCard, field_name: str, val: str) -> None:
    if "." in field_name or field_name.startswith("performance.metrics"):
        apply_nested_postfill(card, field_name, val)
    else:
        setattr(card, field_name, val)


_collect_empty_chai_fields = _collect_empty_clinical_fields


def _build_context_block(seed_pages: list[dict], citations: dict, max_chars: int = 40000) -> str:
    """
    Build a compact text blob from seed_pages + citations for Gemini post-fill.
    """
    parts: list[str] = []
    # Seed pages first (highest signal, already pre-cleaned)
    for i, p in enumerate(seed_pages[:20], 1):
        u = (p.get("url") or "").strip()
        t = (p.get("text") or "").strip()
        if not u or not t:
            continue
        parts.append(f"[SEED {i}] {u}\n{t}\n")
        # Then citations snippets we already gathered
        if isinstance(citations, dict):
            for k, lst in list(citations.items())[:30]:
                # Skip metadata key
                if k == "_sources_metadata":
                    continue
                if not isinstance(lst, list):
                    continue
                for j, ev in enumerate(lst[:3], 1):
                    u = (ev.get("url") or "").strip()
                    snip = (ev.get("snippet") or "").strip()
                    if u and snip:
                        parts.append(f"[EVIDENCE {k} #{j}] {u}\n{snip}\n")

    blob = "\n".join(parts).strip()
    if len(blob) > max_chars:
        blob = blob[:max_chars].rsplit("\n", 1)[0]
    return blob


def _postfill_client():
    """
    Returns (client, model, config). Safe no-op if genai/settings are unavailable.
    The config includes ThinkingConfig for Gemini 2.5 Flash.
    """
    try:
        if not _HAS_GENAI or _genai is None or _get_settings is None or _genai_types is None:
            return None, "", None
        s = _get_settings()
        api_key = os.getenv("GEMINI_API_KEY") or s.google_api_key
        if not api_key:
            return None, "", None
        client = _genai.Client(api_key=api_key)
        config = _genai_types.GenerateContentConfig(
            temperature=s.gemini_temperature,
            thinking_config=_genai_types.ThinkingConfig(
                include_thoughts=s.gemini_include_thoughts,
                thinking_budget=s.gemini_thinking_budget,
            ),
        )
        return client, s.gemini_model, config
    except Exception:
        return None, "", None



import json, re
from typing import List, Dict, Tuple

def _get_field_specific_guidance(field_name: str) -> str:
    """Get field-specific extraction guidance for post-fill."""
    guidance_map = {
        "release_date": "Look for dates in press releases, announcements, blog posts. Format: YYYY-MM-DD or 'Month Day, Year'",
        "global_availability": "Look for geographic information, country lists, regional availability statements",
        "how_to_use": "Look for tutorials, guides, documentation, getting started pages, user manuals",
        "developer_supplied_warnings": "Look for warnings, cautions, disclaimers, terms of service, safety pages",
        "model_limitations": "Look for limitations sections, constraints, 'does not' statements, restriction lists",
        "training_data": "Look for dataset descriptions, training corpus information, data collection details",
        "output_input_data_type": "Look for API documentation, technical specs, input/output format descriptions",
        "ongoing_maintenance": "Look for version history, changelogs, update schedules, maintenance policies",
        "transparency_information": "Look for transparency reports, disclosure statements, open source information",
        "usefulness_efficacy_result": "Look for performance metrics, time savings data, efficiency studies, validation results",
        "safety_reliability_goal_of_metrics": "Look for safety objectives, reliability targets, risk mitigation goals",
        "safety_reliability_result": "Look for safety metrics, reliability data, validation studies, error rates",
        "safety_reliability_interpretation": "Look for safety analysis, risk assessments, reliability evaluations",
    }
    return guidance_map.get(field_name, "Extract all relevant information from the context.")


async def _postfill_one_field(client, model: str, field_name: str, context_block: str, config=None) -> tuple[str, list[dict]]:
    """
    Ask Gemini to fill exactly one CHAI field. Returns (value, evidence_list).
    Evidence list items: {url, snippet}
    - Uses text 'contents' (not role-based messages) per google-genai
    - Recovers a JSON block leniently
    - Tolerates "value" or "values" and several evidence key shapes
    """
    if client is None or not model:
        return "", []

    system = (
        "You are assisting with a medical AI model card. "
        "Return ONLY a compact JSON object with keys: value (string) and evidence (array of {url, snippet}). "
        "Use the provided context; do not fabricate URLs."
    )

    field_guidance = _get_field_specific_guidance(field_name)
    
    prompt = f"""
Fill the following CHAI model card field using only the context below.

FIELD: {field_name}

FIELD-SPECIFIC GUIDANCE:
{field_guidance}

CONTEXT (seed pages and prior evidence):
{context_block}

CRITICAL:
- If the information is not in the context, return empty string for value
- Do NOT fabricate information
- Extract exact quotes when possible
- Include specific details: dates, numbers, metrics

EVIDENCE (MANDATORY if value is non-empty):
- "evidence" MUST include one entry per distinct source URL in CONTEXT that contributed
  to your answer — if you drew on multiple pages, list ALL of them, not just one.
- "url" must be copied EXACTLY from CONTEXT; never invent or alter a URL.
- "snippet" should be a short phrase that appears verbatim in the "value" you wrote, so the
  exact claim it supports can be located; if none carries over, still include the source URL
  with your best short snippet from that source.

Respond as JSON:
{{
  "value": "<concise answer for this field or empty if unknown>",
  "evidence": [{{"url":"<source url>", "snippet":"<short supporting quote>"}}, ...]
}}
""".strip()

    try:
        text_content = system + "\n\n" + prompt
        resp = await client.aio.models.generate_content(
            model=model,
            contents=text_content,
            config=config,
        )
        # Extract text, skipping thought parts
        raw = ""
        if hasattr(resp, "candidates") and resp.candidates:
            candidate = resp.candidates[0]
            if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                for part in candidate.content.parts:
                    if hasattr(part, "thought") and part.thought:
                        continue
                    if hasattr(part, "text") and part.text:
                        raw = part.text
                        break
        if not raw:
            raw = getattr(resp, "text", None) or getattr(resp, "output_text", None) or ""

        # lenient JSON block recovery
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return "", []

        try:
            obj = json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # try to sanitize trailing commas / smart quotes quickly
            cleaned = re.sub(r",\s*([}\]])", r"\1", m.group(0))
            cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'")
            try:
                obj = json.loads(cleaned)
            except Exception:
                return "", []

        # Accept "value" or "values"
        val = obj.get("value")
        if not val and isinstance(obj.get("values"), dict):
            # if the model used plural, try to pick the single field's value
            vmap = obj["values"]
            if field_name in vmap and isinstance(vmap[field_name], (str, int, float)):
                val = vmap[field_name]
            else:
                # otherwise pick any first scalar
                for _k, _v in vmap.items():
                    if isinstance(_v, (str, int, float)):
                        val = _v
                        break

        # Coerce to string
        if isinstance(val, list):
            val = "; ".join(str(x).strip() for x in val if str(x).strip())
        elif isinstance(val, (int, float)):
            val = str(val)
        elif not isinstance(val, str):
            val = ""

        # Evidence may be under 'evidence' (dict or list) or 'citations'
        ev_raw = obj.get("evidence") or obj.get("citations") or {}
        ev_out: list[dict] = []

        def _clean_ev_list(lst):
            out = []
            for e in lst:
                if not isinstance(e, dict): 
                    continue
                u = (e.get("url") or "").strip()
                sn = (e.get("snippet") or e.get("quote") or "").strip()
                if u and sn:
                    out.append({"url": u, "snippet": sn[:240]})
            return out

        if isinstance(ev_raw, list):
            ev_out = _clean_ev_list(ev_raw)
        elif isinstance(ev_raw, dict):
            # pick evidence for this field, else flatten all
            if isinstance(ev_raw.get(field_name), list):
                ev_out = _clean_ev_list(ev_raw[field_name])
            else:
                flat = []
                for k, lst in ev_raw.items():
                    if isinstance(lst, list):
                        flat.extend(_clean_ev_list(lst))
                ev_out = flat

        return (val.strip() if isinstance(val, str) else ""), ev_out
    except Exception:
        return "", []




async def _postfill_one_critical_field(
    chai_card: ClinicalModelCard,
    field_name: str,
    seed_pages: list[dict],
    citations: dict,
) -> tuple[ClinicalModelCard, dict]:
    """Post-fill a single critical field with enhanced context."""
    client, model, config = _postfill_client()
    if client is None or not model:
        return chai_card, citations
    
    context_block = _build_context_block(seed_pages, citations, max_chars=50000)
    val, ev = await _postfill_one_field(client, model, field_name, context_block, config=config)
    
    if val:
        _apply_postfill_value(chai_card, field_name, val)
        if ev:
            citations[f"postfill.{field_name}"] = ev
    
    return chai_card, citations


async def _postfill_missing_fields(
    chai_card: ClinicalModelCard,
    seed_pages: list[dict],
    citations: dict,
    *,
    max_fields: int = 0,
    pass_name: str = "default",
) -> tuple[ClinicalModelCard, dict]:
    """
    For any empty clinical field, ask Gemini to fill it using (seed_pages + citations) as context.
    Adds citations under 'postfill.<field>'.
    """
    empty_fields = _collect_empty_clinical_fields(chai_card)
    cap = max_fields if max_fields > 0 else len(CLINICAL_CARD_FIELD_NAMES) + len(CLINICAL_NESTED_FIELD_SPECS)
    empty_fields = empty_fields[:cap]
    if not empty_fields:
        return chai_card, citations

    client, model, config = _postfill_client()
    if client is None or not model:
        return chai_card, citations

    context_block = _build_context_block(seed_pages, citations)

    for fname in empty_fields:
        val, ev = await _postfill_one_field(client, model, fname, context_block, config=config)
        if val:
            _apply_postfill_value(chai_card, fname, val)
            if ev:
                citations[f"postfill.{fname}"] = ev

    return chai_card, citations



# ------------------------- main pipeline -------------------------

class CardGenPipeline:
    """
    Gemini-as-Agent pipeline that outputs a ClinicalModelCard and artifacts.
    Public return shape: (chai_card, sources, content)
    """

    def __init__(self, out_dir: str | Path = "outputs", use_web_discovery: bool = True):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.use_web_discovery = use_web_discovery
        self._rewrite_summary_callback = self._gemini_rewrite_summary

    def _gemini_rewrite_summary(self, original: str) -> Optional[str]:
        """Rewrite an over-long summary via Gemini (sync); returns None when unavailable."""
        client, model, config = _postfill_client()
        if client is None or not model:
            return None
        prompt = (
            "Rewrite the following clinical AI model card summary in at most three complete sentences. "
            "Preserve factual claims only; do not add new claims. Return only the rewritten summary.\n\n"
            f"{original}"
        )
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=config)
            text = (getattr(resp, "text", None) or "").strip()
            return text or None
        except Exception as exc:
            print(f"Warning: summary rewrite failed: {exc}")
            return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def discover_model_sources(self, model_name: str, developer_name: str = "", application_url: str = "") -> Dict[str, Any]:
        """
        Discover sources for the model, prioritizing the application URL if provided.
        """
        # If application URL is provided, prioritize it with second-hop scraping
        if application_url:
            try:
                # Use second-hop scraper for user inputted URL
                from scrapers.robust_scraper_v2 import RobustWebScraper
                scraper = RobustWebScraper()
                
                # Extract content with second-hop functionality
                app_result = await scraper.extract_content_with_second_hop(application_url, model_name)
                
                if app_result.get('status') == 'success':
                    return {
                        "application_url": application_url,
                        "application_content": app_result.get("clean_text", ""),
                        "application_title": app_result.get("title", ""),
                        "application_metadata": app_result.get("metadata", {}),
                        "second_hop_content": app_result.get("second_hop_content", []),
                        "second_hop_count": app_result.get("second_hop_count", 0),
                        "total_text_length": app_result.get("total_text_length", len(app_result.get("clean_text", ""))),
                        "priority_source": True,
                        "model_name": model_name,
                        "developer_name": developer_name
                    }
                else:
                    # Fallback to regular fetch if second-hop fails
                    from utils.web_search import fetch_many
                    app_pages = await fetch_many([application_url])
                    if app_pages and app_pages[0]:
                        app_page = app_pages[0]
                        return {
                            "application_url": application_url,
                            "application_content": app_page.get("text", ""),
                            "priority_source": True,
                            "model_name": model_name,
                            "developer_name": developer_name
                        }
            except Exception as e:
                print(f"Warning: Second-hop scraping failed for {application_url}: {e}")
                # Fallback to regular fetch
                try:
                    from utils.web_search import fetch_many
                    app_pages = await fetch_many([application_url])
                    if app_pages and app_pages[0]:
                        app_page = app_pages[0]
                        return {
                            "application_url": application_url,
                            "application_content": app_page.get("text", ""),
                            "priority_source": True,
                            "model_name": model_name,
                            "developer_name": developer_name
                        }
                except Exception:
                    pass
        
        # Fall back to regular discovery
        discovered: List[Dict[str, Any]] = []
        seed_pages_web: List[Dict[str, Any]] = []
        if self.use_web_discovery:
            try:
                discovered, seed_pages_web = await discover_and_fetch(model_name, developer_name, top_k=5)
            except Exception:
                discovered, seed_pages_web = ([], [])
        
        return {
            "discovered": discovered,
            "seed_pages_web": seed_pages_web,
            "model_name": model_name,
            "developer_name": developer_name,
            "application_url": application_url
        }

    async def extract_content_from_sources(self, sources: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract content from discovered sources.
        """
        # This is a placeholder - in a real implementation, this would extract content
        # from the sources and return structured data
        return {
            "sources": sources,
            "extracted_content": "Content extraction placeholder"
        }

    async def generate_chai_model_card(self, model_name: str, extracted_content: Dict[str, Any], developer_name: str = "", application_url: str = "") -> ClinicalModelCard:
        """
        Generate a clinical model card. Returns only the card object.

        Prefer ``generate_model_card`` when callers also need sources/content.
        ``extracted_content`` is unused; discovery runs inside ``generate_model_card``.
        """
        chai_card, _, _ = await self.generate_model_card(
            model_name=model_name,
            developer_name=developer_name,
            application_url=application_url,
        )
        return chai_card

    async def generate_model_card(
        self,
        model_name: str,
        developer_name: str = "",
        application_url: str = "",
        *,
        iters: int = 5,
        coverage_target: float = 0.75,
        finalize_policy: str = "not_specified",  # or "none"
        write_files: bool = True,
        file_prefix: str | None = None,
    ) -> Tuple[ClinicalModelCard, Dict, Dict]:
        """
        Generate model card with adaptive iteration count based on initial completeness.
        """
        """
        Returns:
          - chai_card: ClinicalModelCard (flat dataclass)
          - sources:   {"agent": "gemini", "citations": {...}, "hint": str,
                        "web_search": {...}, "publications": [...], "fda": [...],
                        "postfill": {"ran": bool}}
          - content:   {"json": str, "markdown": str, "xml": str, "paths": PipelineOutputs|None}
        """
        model_hint = f"{model_name} ({developer_name})" if developer_name else model_name

        # 0) Discovery (DuckDuckGo) + prefetch top pages (WEB ONLY for first pass)
        discovered: List[Dict[str, Any]] = []
        seed_pages_web: List[Dict[str, Any]] = []
        
        # Prioritize application URL if provided with second-hop scraping
        if application_url:
            try:
                # Use second-hop scraper for user inputted URL
                from scrapers.robust_scraper_v2 import RobustWebScraper
                scraper = RobustWebScraper()
                
                # Extract content with second-hop functionality
                app_result = await scraper.extract_content_with_second_hop(application_url, model_name)
                
                if app_result.get('status') == 'success':
                    # Add application URL as highest priority source with enhanced content
                    seed_pages_web.insert(0, {
                        "url": application_url,
                        "text": app_result.get("clean_text", ""),
                        "title": app_result.get("title", ""),
                        "second_hop_content": app_result.get("second_hop_content", []),
                        "second_hop_count": app_result.get("second_hop_count", 0),
                        "total_text_length": app_result.get("total_text_length", len(app_result.get("clean_text", ""))),
                        "metadata": app_result.get("metadata", {}),
                        "priority": "user_inputted"
                    })
                    print(f"Enhanced application URL with second-hop: {app_result.get('second_hop_count', 0)} additional sections")
                else:
                    # Fallback to regular fetch if second-hop fails
                    from utils.web_search import fetch_many
                    app_pages = await fetch_many([application_url])
                    if app_pages and app_pages[0]:
                        app_page = app_pages[0]
                        seed_pages_web.insert(0, {
                            "url": application_url,
                            "text": app_page.get("text", ""),
                            "title": app_page.get("title", ""),
                            "priority": "user_inputted"
                        })
            except Exception as e:
                print(f"Warning: Second-hop scraping failed for {application_url}: {e}")
                # Fallback to regular fetch
                try:
                    from utils.web_search import fetch_many
                    app_pages = await fetch_many([application_url])
                    if app_pages and app_pages[0]:
                        app_page = app_pages[0]
                        seed_pages_web.insert(0, {
                            "url": application_url,
                            "text": app_page.get("text", ""),
                            "title": app_page.get("title", ""),
                            "priority": "user_inputted"
                        })
                except Exception:
                    pass
        
        if self.use_web_discovery:
            try:
                discovered, additional_seed_pages = await discover_and_fetch(model_name, developer_name, top_k=10)
                # Add additional discovered pages (but don't override application URL)
                seed_pages_web.extend(additional_seed_pages)
            except Exception:
                pass

        # top URLs (bias early targets) - prioritize application URL
        top_urls = []
        if application_url:
            top_urls.append(application_url)
        top_urls.extend([s["url"] for s in discovered[:4] if s.get("url")])  # Take 4 more to keep total at 5

        # 1) Run Gemini agent with WEB ONLY seed (no publications/FDA yet)
        # Adaptive iteration: Adjust based on initial completeness estimate
        # If we have many sources, we may need more iterations
        estimated_iters = iters
        if len(seed_pages_web) > 8 or len(discovered) > 15:
            # More sources available, allow more iterations to process them
            estimated_iters = min(iters + 2, 8)  # Cap at 8 iterations
            print(f"Adaptive iteration: Increased to {estimated_iters} iterations based on source count")
        
        try:
            agent_card_like, citations = await gemini_run_async(
                model_hint=model_hint,
                max_iters=estimated_iters,
                coverage_target=coverage_target,
                finalize_policy=finalize_policy,
                developer=developer_name,
                seed_urls=top_urls,
                seed_pages=list(seed_pages_web),
            )
        except TypeError:
            agent_card_like, citations = await gemini_run_async(
                model_hint=model_hint,
                max_iters=estimated_iters,
                coverage_target=coverage_target,
                finalize_policy=finalize_policy,
                developer=developer_name,
            )

        # 2) Normalize agent output to a plain dict
        if hasattr(agent_card_like, "model_dump"):
            agent_dump = agent_card_like.model_dump()
        elif isinstance(agent_card_like, dict):
            agent_dump = agent_card_like
        else:
            agent_dump = getattr(agent_card_like, "__dict__", {}) or {}

        # 3) Fetch Publications + FDA before mapping (regulatory evidence)
        publications: List[Dict[str, Any]] = []
        seed_pages_pubs: List[Dict[str, Any]] = []
        try:
            publications, seed_pages_pubs = await _fetch_publications(model_name)
        except Exception:
            publications, seed_pages_pubs = ([], [])

        fda_records: List[Dict[str, Any]] = []
        seed_pages_fda: List[Dict[str, Any]] = []
        if _looks_clinical(model_hint):
            try:
                fda_records, seed_pages_fda = await _fetch_fda_records(model_name, developer_name)
            except Exception:
                fda_records, seed_pages_fda = ([], [])

        # Re-classify regulatory status with FDA evidence
        chai_card = _map_agent_dump_to_chai(
            agent_dump,
            user_model_name=model_name,
            user_developer_name=developer_name,
            user_application_url=application_url,
            fda_records=fda_records,
        )

        # Merge all seed pages (web + pubs + fda) for POST-FILL
        seed_pages_post: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        for group in (seed_pages_web, seed_pages_pubs, seed_pages_fda):
            for p in group:
                u = (p.get("url") or "").strip()
                t = (p.get("text") or "").strip()
                if not u or not t or u in seen_urls:
                    continue
                seen_urls.add(u)
                seed_pages_post.append({"url": u, "text": t})

        # 3.5) Multi-pass Post-fill: have Gemini fill remaining blanks using the expanded context
        postfill_ran = False
        try:
            # Pass 1: Fill from seed_pages (high confidence sources)
            chai_card, citations = await _postfill_missing_fields(
                chai_card=chai_card,
                seed_pages=seed_pages_post,
                citations=citations,
                pass_name="seed_pages"
            )
            
            # Pass 2: Fill from citations (medium confidence)
            chai_card, citations = await _postfill_missing_fields(
                chai_card=chai_card,
                seed_pages=[],  # Use only citations in this pass
                citations=citations,
                pass_name="citations"
            )
            
            # Pass 3: Targeted fill for critical missing fields
            critical_missing = [
                "medical_purpose", "acceptable_input", "output",
                "known_performance_limitations", "skin_type_representation_equity", "performance",
                "training_data",
            ]
            for field in critical_missing:
                if not _is_clinical_field_filled(chai_card, field):
                    chai_card, citations = await _postfill_one_critical_field(
                        chai_card=chai_card,
                        field_name=field,
                        seed_pages=seed_pages_post,
                        citations=citations
                    )
            
            postfill_ran = True
        except Exception as e:
            print(f"Warning: Post-fill failed: {e}")
            postfill_ran = False  # safe failure; continue

        # 3.75) Enforce citations for all substantive fields (fallback to top URLs)
        try:
            citations = _ensure_field_level_citations(
                chai_card,
                citations,
                fallback_urls=list(dict.fromkeys([application_url, *top_urls, *[d.get("url") for d in discovered if isinstance(d, dict)] ])),
            )
        except Exception:
            # Never fail generation just because the citation-enforcer failed
            pass

        # 3.8) Tag each field's sources with regulatory tier (for UI color-coding)
        try:
            from core.source_regulatory import (
                attach_fda_records_to_citations,
                compute_regulatory_tiers_for_card,
            )

            citations = attach_fda_records_to_citations(citations, fda_records)
            compute_regulatory_tiers_for_card(chai_card, citations)
        except Exception as exc:
            print(f"Warning: regulatory tier tagging failed: {exc}")

        # 4) Build artifacts
        chai_card, summary_warnings = enforce_summary_length(
            chai_card,
            rewrite_callback=getattr(self, "_rewrite_summary_callback", None),
        )
        validation = validate_model_card(chai_card)

        try:
            span_sidecar = build_sidecar_from_evidence(chai_card, citations)
            citations = merge_citation_sidecars(citations, span_sidecar)
        except Exception as exc:
            print(f"Warning: citation span builder failed: {exc}")

        json_text = chai_card.to_json()
        md_text = chai_card.to_markdown(citations=citations)

        outputs: Optional[PipelineOutputs] = None
        if write_files:
            outputs = self._write_all(
                chai_card=chai_card,
                citations=citations,
                base_name=(file_prefix or _slugify(model_name)) + "-" + _now_stamp(),
                json_text=json_text,
                md_text=md_text,
            )

        sources = {
            "agent": "gemini",
            "citations": citations,
            "hint": model_hint,
            "web_search": {
                "discovered": discovered,
                "top_urls": top_urls,
            },
            "publications": publications,
            "fda": fda_records,
            "postfill": {"ran": postfill_ran},
            "validation": {"errors": validation.errors, "warnings": validation.warnings + summary_warnings},
        }
        content = {
            "json": json_text,
            "markdown": md_text,
            "paths": outputs,
        }
        # Generate scoring report
        scorer = ModelCardScorer()
        model_card_dict = chai_card.to_dict_camel()
        score = scorer.score_model_card(model_card_dict, citations=citations)
        
        # Add scoring information to sources
        sources["scoring"] = {
            "completion_percentage": score.completion_percentage,
            "clinical_usability_score": score.clinical_usability_score,
            "clinical_usability_level": score.clinical_usability_level.value,
            "overall_rating": score.overall_rating,
            "total_fields": score.total_fields,
            "filled_fields": score.filled_fields,
            "critical_missing_fields": score.critical_missing_fields,
            "recommendations_count": len(score.recommendations),
            "quality_issues_count": len(score.quality_issues)
        }
        
        # Add detailed scoring report to content
        scoring_report = format_score_report(score)
        content["scoring_report"] = scoring_report
        content["scoring_summary"] = get_score_summary(score)
        
        # Write scoring report to file if requested
        if write_files and outputs:
            scoring_path = outputs.json_path.with_suffix(".scoring.txt")
            scoring_path.write_text(scoring_report, encoding="utf-8")
            outputs.scoring_txt = scoring_path
        
        return chai_card, sources, content

    # ------------------------- writers -------------------------

    def _write_all(
        self,
        *,
        chai_card: ClinicalModelCard,
        citations: Dict,
        base_name: str,
        json_text: str,
        md_text: str,
    ) -> PipelineOutputs:
        base = self.out_dir / base_name
        json_path = base.with_suffix(".clinical.json")
        md_path = base.with_suffix(".clinical.md")
        cites_path = base.with_suffix(".citations.json")

        json_path.write_text(json_text, encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")

        if citations:
            sidecar = dict(citations)
            sidecar.setdefault("schema_version", "clinical-model-card-citations-1.0")
            cites_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        else:
            cites_path = None

        return PipelineOutputs(
            json_path=json_path,
            md_path=md_path,
            xml_path=None,
            citations_json_path=cites_path,
        )


# ------------------------- CLI convenience -------------------------

async def _amain():
    import argparse
    p = argparse.ArgumentParser(description="Generate a CHAI model card via Gemini agent")
    p.add_argument("--model-name", required=True)
    p.add_argument("--developer-name", default="")
    p.add_argument("--iters", type=int, default=3)
    p.add_argument("--coverage", type=float, default=0.60)
    p.add_argument("--finalize", default="not_specified", choices=["not_specified", "none"])
    p.add_argument("--out-dir", default="outputs")
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--prefix", default=None)
    p.add_argument("--no-discovery", action="store_true", help="Disable DuckDuckGo discovery step")
    args = p.parse_args()

    pipeline = CardGenPipeline(out_dir=args.out_dir, use_web_discovery=not args.no_discovery)
    chai_card, sources, content = await pipeline.generate_model_card(
        model_name=args.model_name,
        developer_name=args.developer_name,
        iters=args.iters,
        coverage_target=args.coverage,
        finalize_policy=args.finalize,
        write_files=not args.no_write,
        file_prefix=args.prefix,
    )
    print(chai_card.to_json())
    if content.get("paths"):
        outs: PipelineOutputs = content["paths"]
        print("\nArtifacts:")
        if outs.json_path: print(f"- {outs.json_path}")
        if outs.md_path: print(f"- {outs.md_path}")
        if outs.xml_path: print(f"- {outs.xml_path}")
        if outs.citations_json_path: print(f"- {outs.citations_json_path}")
        if outs.scoring_txt: print(f"- {outs.scoring_txt}")
        
        # Show scoring summary
        if content.get("scoring_summary"):
            summary = content["scoring_summary"]
            print("\nSCORING SUMMARY:")
            print(f"   Completion: {summary['completion_percentage']}%")
            print(f"   Clinical Usability: {summary['clinical_usability_level'].upper()}")
            print(f"   Overall Rating: {summary['overall_rating']}")


def main():
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
