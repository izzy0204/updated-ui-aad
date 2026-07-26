# src/agents/gemini_agent/agent.py
"""
Gemini 2.5 Flash agent – fully async with Thinking configuration.

Key design:
  • Every Gemini call goes through _gemini_json (async, uses client.aio)
  • A module-level asyncio.Semaphore caps concurrent API requests
  • ThinkingConfig gives the model a reasoning budget for complex extraction
  • Exponential back-off + retry on 429 / 5xx errors
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import random
import hashlib
import logging
import traceback
from dataclasses import fields as dc_fields
from typing import Any, Dict, List, Optional, Tuple

from utils.web_search import fetch_many
from config.config import get_settings
from core.chai_schema import CLINICAL_AGENT_EXTRACT_FIELDS, CLINICAL_NESTED_FIELD_SPECS, ClinicalModelCard
from utils.cache_system import get_cache
from .prompts import PLANNER, VALIDATOR, build_extractor_prompt
from .tools import (
    ddg_search,
    extract_json_block,
    fetch_github_readme,
    fetch_hf_readme,
    flatten_nonempty,
    normalize_sources,
    set_by_path,
)

import google.genai as genai
from google.genai import types

# ----------------------------- CHAI fields -----------------------------

_CHAI_FIELDS = CLINICAL_AGENT_EXTRACT_FIELDS
_NESTED_FIELD_NAMES = frozenset(CLINICAL_NESTED_FIELD_SPECS.keys())

logger = logging.getLogger(__name__)

# ----------------------------- Numeric Specificity -----------------------------
_NUMERIC_HINTS = {
    "dataset.num_images": " images",
    "dataset.num_patients": " patients",
    "dataset.num_classes": " classes",
    "dataset.num_sites": " sites",
    "evaluation.num_cases": " cases",
    "training.num_images": " images",
    "training.epochs": " epochs",
    "training.steps": "",
    "evaluation.num_images": " images",
    "evaluation.num_readers": " readers",
    "performance.accuracy": "%",
    "performance.sensitivity": "%",
    "performance.specificity": "%",
    "performance.ppv": "%",
    "performance.npv": "%",
    "performance.auc": "",  # leave as is (0–1)
}

# ----------------------------- Module-level concurrency control --------

_SEM: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazy-initialise the semaphore inside the running loop."""
    global _SEM
    if _SEM is None:
        _SEM = asyncio.Semaphore(get_settings().gemini_max_concurrent)
    return _SEM


# ----------------------------- Seed context -----------------------------

def _prep_seed_context(
    seed_pages: list[dict] | None,
    *,
    max_chars_per_page: int = 8000,
    max_pages: int = 8,
) -> tuple[str, list[str]]:
    if not seed_pages:
        return "", []
    cleaned: list[tuple[str, str, bool]] = []
    seen: set[str] = set()
    for page in seed_pages:
        url = (page or {}).get("url", "").strip()
        txt = (page or {}).get("text", "").strip()
        if not url or not txt or url in seen:
            continue
        seen.add(url)
        snippet = txt[:max_chars_per_page].strip()
        if snippet:
            cleaned.append((url, snippet, (page or {}).get("priority") == "user_inputted"))
        if len(cleaned) >= max_pages:
            break

    parts: list[str] = []
    ordered_urls: list[str] = []
    for i, (u, snip, is_primary) in enumerate(cleaned, 1):
        ordered_urls.append(u)
        tag = (
            " — PRIMARY SOURCE (developer-provided Application URL; prefer this source "
            "when information conflicts)"
            if is_primary
            else ""
        )
        parts.append(f"[SEED {i}] URL: {u}{tag}\nCONTENT:\n{snip}\n")
    return ("\n\n".join(parts).strip(), ordered_urls)


# ----------------------------- Client / I/O -----------------------------

def _client_and_model() -> tuple[genai.Client, str, float]:
    s = get_settings()
    api_key = os.getenv("GEMINI_API_KEY") or s.google_api_key
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    client = genai.Client(api_key=api_key)
    return client, s.gemini_model, s.http_timeout


def _thinking_config() -> types.GenerateContentConfig:
    """Build the standard GenerateContentConfig with Thinking enabled."""
    s = get_settings()
    return types.GenerateContentConfig(
        temperature=s.gemini_temperature,
        thinking_config=types.ThinkingConfig(
            include_thoughts=s.gemini_include_thoughts,
            thinking_budget=s.gemini_thinking_budget,
        ),
    )


def _extract_response_text(resp) -> str:
    """
    Robustly pull the text answer from a Gemini response, skipping thought parts.
    """
    # With thinking enabled, there may be thought parts + text parts.
    # We want only the non-thought text.
    if hasattr(resp, "candidates") and resp.candidates:
        candidate = resp.candidates[0]
        if hasattr(candidate, "content") and hasattr(candidate.content, "parts") and candidate.content.parts:
            text_parts = []
            for part in candidate.content.parts:
                # Skip thought parts
                if hasattr(part, "thought") and part.thought:
                    continue
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
            if text_parts:
                return "\n".join(text_parts)
    # Fallback to simple accessors
    if hasattr(resp, "text") and resp.text:
        return resp.text
    if hasattr(resp, "output_text") and resp.output_text:
        return resp.output_text
    return ""


async def _gemini_json(
    client: genai.Client,
    model_name: str,
    *,
    prompt: str,
    system: Optional[str] = None,
    retries: int = 3,
) -> Dict[str, Any]:
    """
    Async single-turn call that extracts the first JSON object the model returns.
    Uses client.aio for true async I/O, semaphore for concurrency, and retry on 429/5xx.
    """
    config = _thinking_config()
    sem = _get_semaphore()

    text_content = ((system + "\n\n") if system else "") + prompt

    async with sem:
        for attempt in range(retries):
            try:
                resp = await client.aio.models.generate_content(
                    model=model_name,
                    contents=text_content,
                    config=config,
                )

                out_text = _extract_response_text(resp)

                if not out_text:
                    print(f"DEBUG: Empty response from Gemini (attempt {attempt+1})")
                    return {"error": "empty_response", "message": "Model returned no text"}

                obj = extract_json_block(out_text)
                if isinstance(obj, dict):
                    return obj
                return {"error": "json_parse_failed", "message": "No JSON in response", "raw_text": out_text[:200]}

            except Exception as e:
                err_str = str(e)
                retryable = any(code in err_str for code in ("429", "503", "500", "RESOURCE_EXHAUSTED"))
                if retryable and attempt < retries - 1:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    print(f"Gemini {err_str[:60]}… retry in {wait:.1f}s (attempt {attempt+1}/{retries})")
                    await asyncio.sleep(wait)
                else:
                    return {"error": "exception", "message": err_str, "exception_type": type(e).__name__}


# ----------------------------- Agent steps (all async) -----------------

async def _plan_targets(
    client: genai.Client,
    model_name: str,
    model_hint: str,
    *,
    developer: str,
    seed_context: str = "",
) -> Dict[str, Any]:
    print(f"DEBUG: _plan_targets called with model_hint={repr(model_hint)}, developer={repr(developer)}")

    cache = get_cache()

    cache_key = f"{model_hint}_{developer}"
    cached_plan = await cache.get("gemini_planning", cache_key)
    if cached_plan is not None:
        print(f"DEBUG: Cache HIT for planning: {cache_key}")
        return cached_plan

    seed_block = f"\n\nSEED CONTEXT (pre-extracted pages):\n{seed_context}\n" if seed_context else ""

    guardrails = []
    if developer:
        guardrails.append(
            "DEVELOPER CONSTRAINT:\n"
            f"- The developer/owner of this AI model is **{developer}**.\n"
            "- Prefer sources on the developer's official domains.\n"
        )
    if "PRIMARY SOURCE" in seed_context:
        guardrails.append(
            "SOURCE PRIORITY:\n"
            "- A SEED source below is labeled PRIMARY SOURCE — it is the developer-provided "
            "Application URL.\n"
            "- Treat it as the most authoritative source and prefer its content for field "
            "filling when other sources conflict with it.\n"
        )
    guardrails.append(
        "DISAMBIGUATION:\n"
        "- You are looking for an **AI model or device and its information**.\n"
        "- Avoid pages that only describe grants, education, or institutional history "
        "unless they explicitly mention 'model', 'model card', 'architecture', or 'training'."
    )

    planner_prompt = (
        PLANNER
        + f"\n\nMODEL NAME: {model_hint}"
        + (f"\nDEVELOPER: {developer}" if developer else "")
        + f"{seed_block}\n\n"
        + "\n".join(guardrails) + "\n"
        "OUTPUT STRICTLY IN JSON as specified in PLANNER."
    )

    result = await _gemini_json(client, model_name, prompt=planner_prompt)
    print(f"DEBUG: _plan_targets result: {type(result)} = {repr(result)[:200]}...")

    await cache.set(
        "gemini_planning", cache_key, result,
        model_name=model_hint,
        metadata={"developer": developer, "seed_context_length": len(seed_context)},
        developer=developer,
    )
    return result


async def _gather_targets_async(
    targets: List[Dict[str, str]],
    *,
    concurrency: int = 4,
    model_name: str = "",
    developer: str = "",
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """
    Fetch content for each planned target using the robust fetcher (PDF-aware).
    """
    print(f"DEBUG: _gather_targets called with {len(targets)} targets")

    ordered: List[Dict[str, str]] = []
    seen = set()

    def push(t):
        key = (t.get("type"), t.get("id") or t.get("url"))
        if key not in seen:
            seen.add(key)
            ordered.append(t)

    for t in targets:
        if t.get("type") in ("huggingface", "github"):
            push(t)
    for t in targets:
        if t.get("type") == "web":
            push(t)

    blobs: List[Tuple[str, str]] = []
    types_list: List[str] = []

    for t in ordered:
        try:
            ttype = t.get("type")
            if ttype == "huggingface":
                url, txt = fetch_hf_readme(t.get("id", ""), timeout=20)
                if txt and txt.strip():
                    blobs.append((url, txt))
                    types_list.append("huggingface")
                else:
                    logger.warning("Empty HuggingFace README for %s", t.get("id"))
            elif ttype == "github":
                url, txt = fetch_github_readme(t.get("id", ""), timeout=20)
                if txt and txt.strip():
                    blobs.append((url, txt))
                    types_list.append("github")
                else:
                    logger.warning("Empty GitHub README for %s", t.get("id"))
        except Exception as exc:
            logger.warning(
                "Skipping failed %s target %s: %s: %s",
                t.get("type"),
                t.get("id") or t.get("url"),
                type(exc).__name__,
                exc,
            )
            continue

    web_urls = [t.get("url", "") for t in ordered if t.get("type") == "web"]
    web_urls = [u for u in web_urls if isinstance(u, str) and u.strip()]
    if web_urls:
        fetched = await fetch_many(web_urls, concurrency=concurrency)
        for r in fetched:
            url = (r or {}).get("url") or ""
            text = (r or {}).get("text") or ""
            status = (r or {}).get("status", 0)
            err = (r or {}).get("error")

            if status != 200 or not text.strip():
                logger.warning(
                    "Skipping web fetch url=%s status=%s error=%s text_len=%s",
                    url,
                    status,
                    err,
                    len(text.strip()),
                )
                continue
            if "Sorry, the page you were looking for in this blog does not exist" in text:
                continue
            if "Enable JavaScript and cookies" in text:
                continue

            blobs.append((url, text))
            types_list.append("web")

    print(f"DEBUG: _gather_targets completed, got {len(blobs)} blobs")
    return blobs, types_list


async def _extract_fields(
    client: genai.Client,
    model_name: str,
    field_paths: List[str],
    manifest: str,
    sources_blob: str,
) -> Dict[str, Any]:
    cache = get_cache()

    sources_hash = hashlib.sha256(sources_blob.encode()).hexdigest()[:16]
    cache_key = f"{'_'.join(field_paths)}_{sources_hash}"

    cached = await cache.get("gemini_extraction", cache_key)
    if cached is not None:
        print(f"DEBUG: Cache HIT for extraction: {cache_key}")
        return cached

    allowed_fields = _CHAI_FIELDS
    prompt = build_extractor_prompt(
        field_paths=json.dumps(field_paths),
        allowed_fields=json.dumps(allowed_fields),
        manifest=manifest,
        sources=sources_blob,
    )

    max_retries = 2
    for attempt in range(max_retries + 1):
        result = await _gemini_json(client, model_name, prompt=prompt)

        if "error" in result:
            error_type = result.get("error", "unknown")
            error_message = result.get("message", "")
            print(f"ERROR: Gemini extraction failed for fields {field_paths} "
                  f"(attempt {attempt+1}/{max_retries+1}): {error_type} - {error_message[:120]}")
            if attempt < max_retries:
                await asyncio.sleep(1)
                continue
            else:
                print(f"ERROR: All extraction attempts failed for fields {field_paths}")
                return {"values": {}, "error": error_type, "error_message": error_message}
        else:
            break

    print(f"DEBUG: Gemini extraction result for fields {field_paths}: {repr(result)[:200]}...")

    await cache.set(
        "gemini_extraction", cache_key, result,
        metadata={"field_paths": field_paths, "sources_length": len(sources_blob)},
        field_paths=field_paths, sources_hash=sources_hash,
    )
    return result


async def _validate_patch(
    client: genai.Client,
    model_name: str,
    model_id: str,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    chai_fields = [f.name for f in dc_fields(ClinicalModelCard) if f.name != "extraction_timestamp"]

    def _present(field: str) -> bool:
        v = state.get(field, None)
        if isinstance(v, str) and v.strip():
            return True
        if isinstance(v, list) and any(str(x).strip() for x in v):
            return True
        for k, val in state.items():
            if isinstance(k, str) and "." in k and k.split(".")[-1] == field:
                if isinstance(val, str) and val.strip():
                    return True
                if isinstance(val, list) and any(str(x).strip() for x in val):
                    return True
        return False

    local_missing = [f for f in chai_fields if not _present(f)]

    try:
        card_json = json.dumps(state, ensure_ascii=False, indent=2)
        prompt = VALIDATOR + "\n\nCURRENT CARD (partial JSON):\n" + card_json
        out = await _gemini_json(client, model_name, prompt=prompt) or {}
        return {
            "missing": out.get("missing") if isinstance(out.get("missing"), list) else local_missing,
            "weak": out.get("weak") if isinstance(out.get("weak"), list) else [],
            "next_fetch": out.get("next_fetch") if isinstance(out.get("next_fetch"), list) else [],
        }
    except Exception:
        return {"missing": local_missing, "weak": [], "next_fetch": []}


# ----------------------------- Utilities -----------------------------

def _get_by_path(root: Dict[str, Any], path: str) -> Any:
    if not isinstance(root, dict) or not path or not isinstance(path, str):
        return None
    if any(x in path for x in ["CRITICAL REQUIREMENTS", "You MUST", "The JSON MUST"]):
        return None
    if path.strip() == "" or len(path.strip()) < 2:
        return None
    invalid_chars = ['\n', '\r', '\t', '"', "'", '`', '(', ')', '[', ']', '{', '}']
    if any(char in path for char in invalid_chars):
        return None
    try:
        cur: Any = root
        for k in path.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur.get(k)
        return cur
    except Exception:
        return None


def _is_good_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        return stripped and stripped not in ("", "Not specified", "N/A", "Unknown", "TBD", "To be determined")
    if isinstance(value, (list, dict)):
        return bool(value)
    if isinstance(value, (int, float)):
        return True
    return bool(value)


def _sanitize_batch_keys(batch: List[str]) -> List[str]:
    return [str(k) for k in batch]


def _response_shape(resp: Any) -> Dict[str, Any]:
    if isinstance(resp, Exception):
        return {"type": type(resp).__name__, "message": str(resp)}
    if isinstance(resp, dict):
        values = resp.get("values")
        return {
            "type": "dict",
            "top_level_keys": list(resp.keys())[:30],
            "values_keys": list(values.keys())[:30] if isinstance(values, dict) else None,
            "has_error": "error" in resp,
            "error": resp.get("error"),
        }
    return {"type": type(resp).__name__}


def _log_batch_failure(
    batch_index: int,
    batch: List[str],
    exc: BaseException,
    *,
    resp: Any = None,
) -> None:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    shape = _response_shape(resp) if resp is not None else None
    logger.error(
        "Batch %s failed\n"
        "  exception_class: %s\n"
        "  exception: %s\n"
        "  batch_fields: %s\n"
        "  response_shape: %s\n"
        "  traceback:\n%s",
        batch_index,
        type(exc).__name__,
        exc,
        _sanitize_batch_keys(batch),
        shape,
        tb,
    )
    print(
        f"ERROR: Batch {batch_index} raised {type(exc).__name__}: {exc}\n"
        f"  batch_fields={_sanitize_batch_keys(batch)}\n"
        f"  response_shape={shape}\n"
        f"  traceback:\n{tb}"
    )


def _is_failed_batch(values: Dict[str, Any], evidence: Dict[str, List[Dict[str, str]]]) -> bool:
    if not values and not evidence:
        return True
    if values:
        good_values = sum(1 for v in values.values() if _is_good_value(v))
        total_values = len(values)
        if total_values > 0 and good_values == 0:
            return True
        if total_values > 5 and good_values < 2:
            return True
    return False


def _safe_merge_value(existing: Any, new: Any, field_name: str) -> tuple[Any, bool]:
    existing_good = _is_good_value(existing)
    new_good = _is_good_value(new)
    if not new_good:
        return existing, False
    if not existing_good:
        return new, True
    if isinstance(existing, str) and isinstance(new, str):
        if len(new.strip()) > len(existing.strip()):
            return new, True
        return existing, False
    if isinstance(new, dict):
        if isinstance(existing, dict):
            merged = dict(existing)
            changed = False
            for k, v in new.items():
                if v in (None, "", [], {}):
                    continue
                if merged.get(k) != v:
                    merged[k] = v
                    changed = True
            return merged, changed
        return new, True
    return existing, False


def _empty_agent_state() -> Dict[str, Any]:
    return {"metadata": {}, "uses": {}, "warnings": {}, "trust": {}}


def _finalize_not_specified(state: Dict[str, Any]) -> Dict[str, Any]:
    def fill(node: Any):
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if isinstance(v, dict):
                    fill(v)
                elif v in (None, "", []) or (isinstance(v, list) and not v):
                    node[k] = "Not specified"
        return node
    return fill(state)


def _normalize_extractor_output(
    raw: Any, want_fields: List[str]
) -> tuple[Dict[str, Any], Dict[str, List[Dict[str, str]]]]:
    values: Dict[str, Any] = {}
    evidence: Dict[str, List[Dict[str, str]]] = {}

    if isinstance(raw, dict) and "error" in raw:
        return values, evidence

    if not isinstance(raw, dict):
        if isinstance(raw, str) and len(want_fields) == 1:
            values[want_fields[0]] = raw.strip()
        return values, evidence

    # 1) Primary "values" object
    if isinstance(raw.get("values"), dict):
        for k, v in raw["values"].items():
            if isinstance(v, dict) and str(k) in _NESTED_FIELD_NAMES:
                values[str(k)] = v
            elif isinstance(v, (str, int, float)):
                values[str(k)] = str(v).strip()
            elif v is None:
                values[str(k)] = None
            elif isinstance(v, list) and str(k) == "performance":
                values[str(k)] = v
            elif isinstance(v, list):
                values[str(k)] = "; ".join(str(x).strip() for x in v if str(x).strip())

    # 2) Single "value"
    if "value" in raw and len(want_fields) == 1 and not values:
        vv = raw.get("value")
        if isinstance(vv, (str, int, float)):
            values[want_fields[0]] = str(vv).strip()
        elif isinstance(vv, list):
            values[want_fields[0]] = "; ".join(str(x).strip() for x in vv if str(x).strip())

    # 3) Flat keys fallback
    if not values:
        for k, v in list(raw.items()):
            if not isinstance(k, str):
                continue
            if any(x in k for x in ["CRITICAL REQUIREMENTS", "You MUST", "The JSON MUST"]):
                continue
            if k in want_fields or "." in k:
                if isinstance(v, (str, int, float)):
                    values[k] = str(v).strip()
                elif isinstance(v, list):
                    values[k] = "; ".join(str(x).strip() for x in v if str(x).strip())

    # 4) Evidence
    def _clean_ev_list(lst: Any) -> list[dict]:
        cleaned: list[dict] = []
        if not isinstance(lst, list):
            return cleaned
        for e in lst:
            if not isinstance(e, dict):
                continue
            u = (e.get("url") or "").strip()
            sn = (e.get("snippet") or e.get("quote") or "").strip()
            if not u or u.lower() in ("none", "missing"):
                continue
            if sn:
                cleaned.append({"url": u, "snippet": sn[:240]})
        return cleaned

    top_ev = raw.get("evidence") or raw.get("citations")
    if isinstance(top_ev, dict):
        for k, lst in top_ev.items():
            cleaned = _clean_ev_list(lst)
            if cleaned:
                evidence.setdefault(k, []).extend(cleaned)
    elif isinstance(top_ev, list) and len(want_fields) == 1:
        fld = want_fields[0]
        cleaned = _clean_ev_list(top_ev)
        if cleaned:
            evidence.setdefault(fld, []).extend(cleaned)

    # 5) Items shape
    if isinstance(raw.get("items"), list):
        for it in raw["items"]:
            if not isinstance(it, dict):
                continue
            fld = (it.get("field") or "").strip()
            if not fld:
                continue
            val = it.get("value", "")
            if isinstance(val, (str, int, float)):
                values[fld] = str(val).strip()
            elif isinstance(val, list):
                values[fld] = "; ".join(str(x).strip() for x in val if str(x).strip())
            cleaned = _clean_ev_list(it.get("evidence") or it.get("citations") or [])
            if cleaned:
                evidence.setdefault(fld, []).extend(cleaned)

    return values, evidence


def _norm_num_phrase(s: str, unit_hint: str) -> str | None:
    if not isinstance(s, str) or not s.strip():
        return None
    t = s.strip()
    approx = bool(re.search(r"\b(about|around|approx|approximately|roughly|nearly|almost|~)\b", t, re.I))

    m = re.search(r"(\d[\d,]*\.?\d*)\s*([kKmMbB]?)\s*(?:[-–—]|to)\s*(\d[\d,]*\.?\d*)\s*([kKmMbB]?)(\s*%)?", t)
    if m:
        def _val(n, abbr):
            x = float(n.replace(",", ""))
            f = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(abbr.lower(), 1)
            return x * f
        lo = _val(m.group(1), m.group(2) or "")
        hi = _val(m.group(3), m.group(4) or "")
        pct = bool((m.group(5) or "").strip())

        def fmt(x):
            return f"{int(x):,}" if float(x).is_integer() else f"{x:,.2f}"
        unit = "%" if pct else unit_hint
        return f"{fmt(lo)}{unit}–{fmt(hi)}{unit}".strip()

    m = re.search(r"([<>]=?|≈?)?\s*(\d[\d,]*\.?\d*)\s*([kKmMbB]?)(\s*%)?", t)
    if m:
        bound = (m.group(1) or "").strip()
        val = float(m.group(2).replace(",", ""))
        abbr = (m.group(3) or "").lower()
        pct = bool((m.group(4) or "").strip())
        mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(abbr, 1)
        val *= mult
        pretty = f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"
        unit = "%" if pct else unit_hint
        prefix = bound if bound else ("≈" if approx else "")
        return f"{prefix}{pretty}{unit}".strip()
    return None


def _set_by_path_inplace(root: dict, path: str, value: str) -> None:
    cur = root
    parts = path.split(".")
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            return
        cur = cur[p]
    if parts[-1] in cur:
        cur[parts[-1]] = value


def _normalize_numeric_fields_in_place(state: dict) -> None:
    for path, unit in _NUMERIC_HINTS.items():
        v = _get_by_path(state, path)
        if isinstance(v, str) and v.strip():
            norm = _norm_num_phrase(v, unit_hint=unit)
            if norm:
                _set_by_path_inplace(state, path, norm)


# ----------------------------- Public API (fully async) ----------------

async def run(
    model_hint: str,
    max_iters: int = 5,
    coverage_target: float = 0.75,
    finalize_policy: str = "not_specified",
    *,
    developer: str = "",
    seed_urls: list[str] | None = None,
    seed_pages: list[dict] | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Main agent loop – now fully async (no asyncio.run / ThreadPoolExecutor).
    """
    client, gemini_model, timeout = _client_and_model()

    state: Dict[str, Any] = _empty_agent_state()
    citations: Dict[str, List[Dict[str, str]]] = {}
    implicit_sources: set[str] = set()

    seed_context, seed_urls_from_pages = _prep_seed_context(seed_pages)
    initial_seed_urls = list(seed_urls or []) + seed_urls_from_pages

    plan = await _plan_targets(
        client, gemini_model, model_hint,
        developer=developer, seed_context=seed_context,
    ) or {}
    targets = plan.get("targets", []) or []
    priority = plan.get("fields_priority", []) or []

    # Extract model name from hint
    model_name = model_hint
    if developer and developer in model_hint:
        parts = model_hint.split("(")
        model_name = parts[0].strip() if len(parts) > 1 else model_hint.replace(developer, "").strip()
    if not model_name or model_name == model_hint:
        if "(" in model_hint and ")" in model_hint:
            model_name = model_hint.split("(")[0].strip()

    # Prepend explicit seed URLs as web targets
    seen_urls = set()
    prefixed: list[dict] = []
    for u in initial_seed_urls:
        uu = (u or "").strip()
        if uu and uu not in seen_urls:
            prefixed.append({"type": "web", "url": uu})
            seen_urls.add(uu)
    targets = prefixed + targets

    first_round = True
    for _ in range(max_iters):
        if not targets and not first_round:
            break

        # 2) Gather sources (already async – call directly)
        blobs, types_list = await _gather_targets_async(
            targets, concurrency=4,
            model_name=model_name, developer=developer,
        )

        if first_round and seed_pages:
            for sp in seed_pages:
                su = (sp or {}).get("url", "").strip()
                st = (sp or {}).get("text", "").strip()
                if su and st:
                    blobs.append((su, st))
                    types_list.append("web")
            first_round = False

        for url, _ in blobs:
            if url and url.strip():
                implicit_sources.add(url.strip())

        manifest, sources_blob = normalize_sources(blobs, types_list)
        if seed_context:
            sources_blob = f"{seed_context}\n\n{sources_blob}"

        # 3) Choose fields
        def _is_empty(val: Any) -> bool:
            return val in (None, "", [], {}) or (isinstance(val, list) and not any(str(x).strip() for x in val))

        want: List[str] = []
        for path in priority:
            cur = _get_by_path(state, path)
            if _is_empty(cur):
                want.append(path)

        if not want:
            for field in _CHAI_FIELDS:
                cur = _get_by_path(state, field) if "." in field else state.get(field)
                if _is_empty(cur):
                    want.append(field)

        # 4) Extract – launch batches concurrently
        BATCH_SIZE = 15
        batch_tasks = []
        for i in range(0, len(want), BATCH_SIZE):
            batch = want[i:i + BATCH_SIZE]
            batch_tasks.append(
                _extract_fields(client, gemini_model, batch, manifest, sources_blob)
            )

        # Run extraction batches concurrently (semaphore caps Gemini calls)
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        successful_batches = 0
        failed_batches = 0
        for idx, resp in enumerate(batch_results):
            batch = want[idx * BATCH_SIZE: (idx + 1) * BATCH_SIZE]
            if isinstance(resp, Exception):
                failed_batches += 1
                _log_batch_failure(idx + 1, batch, resp)
                continue

            values, ev = _normalize_extractor_output(resp, batch)

            if _is_failed_batch(values, ev):
                failed_batches += 1
                print(f"DEBUG: Detected failed batch {idx+1} – skipping merge")
                continue

            successful_batches += 1

            merge_count = 0
            for k, v in values.items():
                try:
                    if not isinstance(k, str) or not k.strip():
                        continue
                    if any(x in k for x in ["CRITICAL REQUIREMENTS", "You MUST", "The JSON MUST"]):
                        continue
                    existing = _get_by_path(state, k) if "." in k else state.get(k)
                    merged_value, was_changed = _safe_merge_value(existing, v, k)
                    if was_changed:
                        if "." in k:
                            set_by_path(state, k, merged_value)
                        else:
                            state[k] = merged_value
                        merge_count += 1
                except Exception:
                    continue

            for k, lst in ev.items():
                if not isinstance(lst, list):
                    continue
                citations.setdefault(k, [])
                for e in lst:
                    u = e.get("url")
                    sn = e.get("snippet")
                    if u and sn:
                        citations[k].append({"url": u, "snippet": sn[:240]})

        logger.info(
            "Extraction batches: successful=%s failed=%s total=%s blobs=%s",
            successful_batches,
            failed_batches,
            len(batch_results),
            len(blobs),
        )

        # 5) Validate
        verdict = await _validate_patch(client, gemini_model, gemini_model, state) or {}
        missing = verdict.get("missing", []) or []
        weak = verdict.get("weak", []) or []
        next_fetch = verdict.get("next_fetch", []) or []

        new_targets: list[dict] = []
        queries = [nf.get("query") for nf in next_fetch if nf.get("query")]
        if queries:
            for q in queries:
                for u in ddg_search(q, timeout=timeout, n=3):
                    if u and u not in seen_urls:
                        new_targets.append({"type": "web", "url": u})
                        seen_urls.add(u)
        for nf in next_fetch:
            u = nf.get("url")
            if u and u not in seen_urls:
                new_targets.append({"type": "web", "url": u})
                seen_urls.add(u)

        targets = new_targets

        # 6) Field-specific pass for commonly missing clinical fields
        commonly_missing = [
            "version",
            "availability",
            "performance_evaluation_limitations",
            "ongoing_monitoring_plan",
            "scheduled_updates",
            "clinical_trial",
            "model_development_and_validation",
        ]
        missing_common = [f for f in commonly_missing if _is_empty(_get_by_path(state, f))]
        if missing_common and sources_blob:
            try:
                resp = await _extract_fields(
                    client, gemini_model,
                    missing_common[:10], manifest, sources_blob,
                )
                vals, ev = _normalize_extractor_output(resp, missing_common[:10])
                for k, v in vals.items():
                    if v and _is_empty(_get_by_path(state, k)):
                        if "." in k:
                            set_by_path(state, k, v)
                        else:
                            state[k] = v
            except Exception:
                pass

        # 7) Stop criteria
        total_nonempty = flatten_nonempty(state)
        critical_fields = [
            "model_name",
            "developer",
            "summary",
            "medical_purpose",
            "known_performance_limitations",
            "training_data",
            "performance",
        ]
        critical_filled = sum(1 for f in critical_fields if not _is_empty(_get_by_path(state, f)))
        weighted_coverage = (total_nonempty + critical_filled) / max(50, total_nonempty + critical_filled)
        denom = max(50, total_nonempty)
        coverage = total_nonempty / denom
        effective_coverage = max(coverage, weighted_coverage)

        if (not missing and not weak) or effective_coverage >= coverage_target:
            break

    _normalize_numeric_fields_in_place(state)
    if finalize_policy == "not_specified":
        state = _finalize_not_specified(state)

    # Combine sources
    explicit_sources: set[str] = set()
    for field_citations in citations.values():
        if not isinstance(field_citations, list):
            continue
        for citation in field_citations:
            if isinstance(citation, dict):
                url = citation.get("url", "").strip()
                if url:
                    explicit_sources.add(url)

    all_used = implicit_sources.union(explicit_sources)
    enhanced_citations = {"_sources_metadata": {}}
    for field_name, field_citations in citations.items():
        enhanced_citations[field_name] = field_citations
    for url in all_used:
        if url in explicit_sources and url in implicit_sources:
            usage, reason = "both", "Included in context and directly cited"
        elif url in explicit_sources:
            usage, reason = "explicit", "Directly cited for extracted claims"
        else:
            usage, reason = "implicit", "Included in context, informed reasoning but not directly quoted"
        enhanced_citations["_sources_metadata"][url] = {"usage": usage, "reason": reason}

    return state, enhanced_citations


async def run_async(
    *,
    model_hint: str,
    max_iters: int = 5,
    coverage_target: float = 0.75,
    finalize_policy: str = "not_specified",
    developer: str = "",
    seed_urls: list[str] | None = None,
    seed_pages: list[dict] | None = None,
) -> tuple[dict | object, dict]:
    """Public entry-point – now just a thin wrapper around the async run()."""
    return await run(
        model_hint,
        max_iters,
        coverage_target,
        finalize_policy,
        developer=developer,
        seed_urls=seed_urls,
        seed_pages=seed_pages,
    )
