# src/agents/gemini_agent/agent.py
from __future__ import annotations

import asyncio
import json
import re
import hashlib
from dataclasses import fields as dc_fields
from typing import Any, Dict, List, Optional, Tuple

from utils.web_search import fetch_many
from config.config import get_settings
from core.chai_schema import CHAIModelCard
from utils.cache_system import get_cache
from .prompts import PLANNER, EXTRACTOR, VALIDATOR
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


# ----------------------------- CHAI fields -----------------------------

_CHAI_FIELDS = [f.name for f in dc_fields(CHAIModelCard) if f.name != "extraction_timestamp"]

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

# ----------------------------- Seed context -----------------------------

def _prep_seed_context(
    seed_pages: list[dict] | None,
    *,
    max_chars_per_page: int = 8000,
    max_pages: int = 8,
) -> tuple[str, list[str]]:
    if not seed_pages:
        return "", []
    cleaned: list[tuple[str, str]] = []
    seen: set[str] = set()
    for page in seed_pages:
        url = (page or {}).get("url", "").strip()
        txt = (page or {}).get("text", "").strip()
        if not url or not txt or url in seen:
            continue
        seen.add(url)
        snippet = txt[:max_chars_per_page].strip()
        if snippet:
            cleaned.append((url, snippet))
        if len(cleaned) >= max_pages:
            break

    parts: list[str] = []
    ordered_urls: list[str] = []
    for i, (u, snip) in enumerate(cleaned, 1):
        ordered_urls.append(u)
        parts.append(f"[SEED {i}] URL: {u}\nCONTENT:\n{snip}\n")
    return ("\n\n".join(parts).strip(), ordered_urls)


# ----------------------------- Client / I/O -----------------------------

def _client_and_model() -> tuple[genai.Client, str, float]:
    s = get_settings()
    client = genai.Client(api_key=s.google_api_key)
    return client, s.gemini_model, s.http_timeout


def _gemini_json(client: genai.Client, model_name: str, *, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
    """
    Safe single-turn call that extracts the first JSON object the model returns.
    Keyword-only args prevent accidental positional swaps (fix B).
    Returns proper error structure to distinguish failures from empty results.
    """
    try:
        text = ((system + "\n\n") if system else "") + prompt
        resp = client.models.generate_content(
            model=model_name,
            contents=text
        )
        out_text = getattr(resp, "text", None) or ""

        if not out_text:
            return {"error": "empty_response", "message": "Model returned no text content"}

        # extract_json_block already tolerates ```json fences and stray prose
        obj = extract_json_block(out_text)
        if isinstance(obj, dict):
            return obj
        else:
            return {"error": "json_parse_failed", "message": "Failed to parse JSON from model response", "raw_text": out_text[:200]}
    except Exception as e:
        return {"error": "exception", "message": str(e), "exception_type": type(e).__name__}


# ----------------------------- Agent steps -----------------------------

def _plan_targets(client: genai.Client, model_name: str, model_hint: str, *, developer: str, seed_context: str = "") -> Dict[str, Any]:
    print(f"DEBUG: _plan_targets called with model_hint={repr(model_hint)}, developer={repr(developer)}")
    
    cache = get_cache()
    
    # Check cache first
    cache_key = f"{model_hint}_{developer}"
    cached_plan = asyncio.run(cache.get("gemini_planning", cache_key))
    if cached_plan is not None:
        print(f"DEBUG: Cache HIT for planning: {cache_key}")
        return cached_plan
    
    seed_block = f"\n\nSEED CONTEXT (pre-extracted pages):\n{seed_context}\n" if seed_context else ""

    guardrails = []
    if developer:
        guardrails.append(
            "DEVELOPER CONSTRAINT:\n"
            f"- The developer/owner of this AI model is **{developer}**.\n"
            "- Prefer sources on the developer's official domains (e.g., *.<developer>.com, <model_name.com>, github.com/<developer>, huggingface.co/<developer>) when selecting targets.\n"
        )

    guardrails.append(
        "DISAMBIGUATION:\n"
        "- You are looking for an **AI model or device and its information**.\n"
        "- Avoid pages that only describe grants, education, or institutional history unless they explicitly mention 'model', 'model card', 'architecture', or 'training'."
    )

    guardrails_text = "\n".join(guardrails)

    planner_prompt = (
        PLANNER
        + f"\n\nMODEL NAME: {model_hint}"
        + (f"\nDEVELOPER: {developer}" if developer else "")
        + f"{seed_block}\n\n"
        f"{guardrails_text}\n"
        "OUTPUT STRICTLY IN JSON as specified in PLANNER."
    )

    result = _gemini_json(client, model_name, prompt=planner_prompt)
    print(f"DEBUG: _plan_targets result: {type(result)} = {repr(result)[:200]}...")
    
    # Cache the result
    asyncio.run(cache.set(
        "gemini_planning",
        cache_key,
        result,
        model_name=model_hint,
        metadata={"developer": developer, "seed_context_length": len(seed_context)},
        developer=developer
    ))
    
    print(f"DEBUG: Cache SET for planning: {cache_key}")
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
    Returns:
        blobs: list[(url, text)]
        types: list['huggingface'|'github'|'web'] parallel to blobs
    """
    print(f"DEBUG: _gather_targets called with {len(targets)} targets")

    # Normalize & tier: HF/GitHub first (C), then web
    ordered: List[Dict[str, str]] = []
    seen = set()
    def push(t):
        key = (t.get("type"), t.get("id") or t.get("url"))
        if key not in seen:
            seen.add(key)
            ordered.append(t)

    # Tier 1: HF, GitHub
    for t in targets:
        if (t.get("type") in ("huggingface", "github")):
            push(t)
    # Tier 2: web
    for t in targets:
        if t.get("type") == "web":
            push(t)

    # First fetch HF/GitHub readmes via the existing helpers (cheap)
    blobs: List[Tuple[str, str]] = []
    types: List[str] = []

    for t in ordered:
        try:
            ttype = t.get("type")
            if ttype == "huggingface":
                url, txt = fetch_hf_readme(t.get("id", ""), timeout=20)
                if txt and txt.strip():
                    blobs.append((url, txt))
                    types.append("huggingface")
            elif ttype == "github":
                url, txt = fetch_github_readme(t.get("id", ""), timeout=20)
                if txt and txt.strip():
                    blobs.append((url, txt))
                    types.append("github")
        except Exception:
            continue

    # Then fetch web targets (PDF-aware) with fetch_many
    web_urls = [t.get("url", "") for t in ordered if t.get("type") == "web"]
    web_urls = [u for u in web_urls if isinstance(u, str) and u.strip()]
    if web_urls:
        # NOTE: fetch_many is async; call directly
        fetched = await fetch_many(web_urls, concurrency=concurrency)
        for r in fetched:
            url = (r or {}).get("url") or ""
            text = (r or {}).get("text") or ""
            status = (r or {}).get("status", 0)
            kind = (r or {}).get("type", "html")

            # Filter out obvious junk (404s, error stubs, cookie walls)
            if status != 200 or not text.strip():
                continue
            if "Sorry, the page you were looking for in this blog does not exist" in text:
                continue
            if "Enable JavaScript and cookies" in text:
                continue

            blobs.append((url, text))
            types.append("web")

    print(f"DEBUG: _gather_targets completed, got {len(blobs)} blobs")
    return blobs, types

def _extract_fields(
    client: genai.Client,
    model_name: str,
    field_paths: List[str],
    manifest: str,
    sources_blob: str,
) -> Dict[str, Any]:
    cache = get_cache()
    
    # Create cache key from field paths and sources content hash
    sources_hash = hashlib.sha256(sources_blob.encode()).hexdigest()[:16]
    cache_key = f"{'_'.join(field_paths)}_{sources_hash}"
    
    # Check cache first
    cached_extraction = asyncio.run(cache.get("gemini_extraction", cache_key))
    if cached_extraction is not None:
        print(f"DEBUG: Cache HIT for extraction: {cache_key}")
        return cached_extraction
    
    allowed_fields = _CHAI_FIELDS
    prompt = EXTRACTOR.format(
        field_paths=json.dumps(field_paths),
        allowed_fields=json.dumps(allowed_fields),
        manifest=manifest,
        sources=sources_blob,
    )
    
    # Try extraction with retry logic
    max_retries = 2
    for attempt in range(max_retries + 1):
        result = _gemini_json(client, model_name, prompt=prompt)
        
        # Check if this is an error response
        if "error" in result:
            error_type = result.get("error", "unknown")
            error_message = result.get("message", "No message provided")
            
            print(f"ERROR: Gemini extraction failed for fields {field_paths} (attempt {attempt + 1}/{max_retries + 1}): {error_type} - {error_message}")
            
            if attempt < max_retries:
                print(f"DEBUG: Retrying extraction for fields {field_paths}...")
                import time
                time.sleep(1)  # Brief delay before retry
                continue
            else:
                # Final attempt failed, return proper error structure
                print(f"ERROR: All extraction attempts failed for fields {field_paths}")
                error_result = {
                    "values": {},
                    "error": error_type,
                    "error_message": error_message,
                    "attempts": attempt + 1,
                    "field_paths": field_paths
                }
                # Don't cache errors
                return error_result
        else:
            # Success - break out of retry loop
            break
    
    # Add debugging output
    print(f"DEBUG: Gemini extraction result for fields {field_paths}: {type(result)} = {repr(result)[:200]}...")
    
    # Cache the result (only if successful)
    asyncio.run(cache.set(
        "gemini_extraction",
        cache_key,
        result,
        metadata={"field_paths": field_paths, "sources_length": len(sources_blob), "manifest_length": len(manifest)},
        field_paths=field_paths,
        sources_hash=sources_hash
    ))
    
    print(f"DEBUG: Cache SET for extraction: {cache_key}")
    return result


def _validate_patch(client: genai.Client, model_name: str, model_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ask the VALIDATOR to assess current 'state' and suggest:
      - missing: list of CHAI field names that are absent/empty
      - weak: list of CHAI field names that are vague/underspecified
      - next_fetch: list of {"url": "..."} and/or {"query": "..."} items
    Also computes a conservative local 'missing' fallback.
    """
    chai_fields = [f.name for f in dc_fields(CHAIModelCard) if f.name != "extraction_timestamp"]

    def _get_by_path(root: Dict[str, Any], path: str) -> Any:
        cur: Any = root
        for k in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

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
        prompt = VALIDATOR + "\n\nCURRENT CARD (partial JSON; may include flat and dotted keys):\n" + card_json
        out = _gemini_json(client, model_name, prompt=prompt) or {}
        return {
            "missing": out.get("missing") if isinstance(out.get("missing"), list) else local_missing,
            "weak": out.get("weak") if isinstance(out.get("weak"), list) else [],
            "next_fetch": out.get("next_fetch") if isinstance(out.get("next_fetch"), list) else [],
        }
    except Exception:
        return {"missing": local_missing, "weak": [], "next_fetch": []}


# ----------------------------- Utilities -----------------------------

def _get_by_path(root: Dict[str, Any], path: str) -> Any:
    """Safely get a value from a nested dictionary by path.
    
    Args:
        root: The root dictionary to search in
        path: Dot-separated path to the value (e.g., "model.name")
        
    Returns:
        The value at the path, or None if not found or path is invalid
    """
    if not isinstance(root, dict) or not path or not isinstance(path, str):
        return None
        
    # Safety check: reject paths that look like prompt text or are malformed
    if any(indicator in path for indicator in ["CRITICAL REQUIREMENTS", "You MUST", "The JSON MUST", " and end with"]):
        return None
        
    # Additional safety checks for malformed paths
    if path.strip() == "" or len(path.strip()) < 2:
        return None
        
    # Check for invalid characters that shouldn't be in field paths
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
    """Check if a value is considered 'good' (non-empty and meaningful).
    
    Args:
        value: The value to check
        
    Returns:
        True if the value is good, False otherwise
    """
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        return stripped and stripped not in ("", "Not specified", "N/A", "Unknown", "TBD", "To be determined")
    if isinstance(value, (list, dict)):
        return bool(value)  # Non-empty collections are good
    if isinstance(value, (int, float)):
        return True  # All numeric values are considered good
    return bool(value)  # For other types, truthy values are good


def _is_failed_batch(values: Dict[str, Any], evidence: Dict[str, List[Dict[str, str]]]) -> bool:
    """Check if a batch extraction appears to have failed.
    
    Args:
        values: Extracted values dictionary
        evidence: Extracted evidence dictionary
        
    Returns:
        True if the batch appears to be a failure, False otherwise
    """
    # Check for empty or minimal results
    if not values and not evidence:
        return True
        
    # Check for suspicious patterns that indicate failure
    if values:
        # If all values are empty/None/Not specified, it's likely a failure
        good_values = sum(1 for v in values.values() if _is_good_value(v))
        total_values = len(values)
        if total_values > 0 and good_values == 0:
            return True
            
        # If we have very few good values compared to total, it might be a failure
        if total_values > 5 and good_values < 2:
            return True
    
    return False


def _safe_merge_value(existing: Any, new: Any, field_name: str) -> tuple[Any, bool]:
    """Safely merge two values, preferring the better one.
    
    Args:
        existing: The existing value
        new: The new value to potentially merge
        field_name: Name of the field for logging
        
    Returns:
        Tuple of (merged_value, was_changed)
    """
    existing_good = _is_good_value(existing)
    new_good = _is_good_value(new)
    
    if not new_good:
        # New value is not good, keep existing
        return existing, False
        
    if not existing_good:
        # Existing value is not good, use new value
        return new, True
        
    # Both values are good - prefer the more specific/detailed one
    if isinstance(existing, str) and isinstance(new, str):
        if len(new.strip()) > len(existing.strip()):
            return new, True
        else:
            return existing, False
    
    # For other cases, keep existing (conservative approach)
    return existing, False


def _empty_agent_state() -> Dict[str, Any]:
    return {
        "metadata": {},
        "uses": {},
        "warnings": {},
        "trust": {},
    }


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
) -> tuple[Dict[str, str], Dict[str, List[Dict[str, str]]]]:
    """
    Make extractor output predictable and robust (fix C).
    - Coerce None → "" for values
    - Join lists into a sentence
    - Drop bogus evidence urls like 'none'/'missing'
    """
    values: Dict[str, str] = {}
    evidence: Dict[str, List[Dict[str, str]]] = {}

    print(f"DEBUG: Normalizing extractor output: {type(raw)} = {repr(raw)[:300]}...")
    print(f"DEBUG: Want fields: {want_fields}")

    # Check if this is an error response
    if isinstance(raw, dict) and "error" in raw:
        error_type = raw.get("error", "unknown")
        error_message = raw.get("error_message", "No message provided")
        print(f"ERROR: Normalizing failed extraction - {error_type}: {error_message}")
        # Return empty values and evidence for error cases
        return values, evidence

    if not isinstance(raw, dict):
        print(f"DEBUG: Raw is not a dict, type: {type(raw)}")
        if isinstance(raw, str) and len(want_fields) == 1:
            values[want_fields[0]] = raw.strip()
            print(f"DEBUG: Set single field {want_fields[0]} = {raw.strip()}")
        return values, evidence

    # 1) Primary "values" object
    if isinstance(raw.get("values"), dict):
        print(f"DEBUG: Found 'values' dict with keys: {list(raw['values'].keys())}")
        for k, v in raw["values"].items():
            if isinstance(v, (str, int, float)):
                values[str(k)] = str(v).strip()
                print(f"DEBUG: Set value {k} = {str(v).strip()}")
            elif v is None:
                values[str(k)] = None
                print(f"DEBUG: Set value {k} = None (preserved None)")
            elif isinstance(v, list):
                values[str(k)] = "; ".join(str(x).strip() for x in v if str(x).strip())
                print(f"DEBUG: Set value {k} = {values[str(k)]} (from list)")
    else:
        print(f"DEBUG: No 'values' dict found, raw.get('values') = {raw.get('values')}")

    # 2) Single "value" (one-field case)
    if "value" in raw and len(want_fields) == 1 and not values:
        vv = raw.get("value")
        if isinstance(vv, (str, int, float)):
            values[want_fields[0]] = str(vv).strip()
        elif isinstance(vv, list):
            values[want_fields[0]] = "; ".join(str(x).strip() for x in vv if str(x).strip())

    # 3) Flat keys (fallback)
    if not values:
        for k, v in list(raw.items()):
            if not isinstance(k, str):
                continue
            if any(x in k for x in ["CRITICAL REQUIREMENTS", "You MUST", "The JSON MUST", " and end with"]):
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

    # detect approximation tokens
    approx = bool(re.search(r"\b(about|around|approx|approximately|roughly|nearly|almost|~)\b", t, re.I))

    # range like "2-3k" or "2 to 3M"
    m = re.search(r"(\d[\d,]*\.?\d*)\s*([kKmMbB]?)\s*(?:[-–—]|to)\s*(\d[\d,]*\.?\d*)\s*([kKmMbB]?)(\s*%)?", t)
    if m:
        def _val(n, abbr):
            x = float(n.replace(",", ""))
            f = {"k":1_000, "m":1_000_000, "b":1_000_000_000}.get(abbr.lower(), 1)
            return x * f
        lo = _val(m.group(1), m.group(2) or "")
        hi = _val(m.group(3), m.group(4) or "")
        pct = bool((m.group(5) or "").strip())
        def fmt(x):
            return f"{int(x):,}" if float(x).is_integer() else f"{x:,.2f}"
        unit = "%" if pct else unit_hint
        return f"{fmt(lo)}{unit}–{fmt(hi)}{unit}".strip()

    # single like ">= 12%", "~5k", "3.2M"
    m = re.search(r"([<>]=?|≈?)?\s*(\d[\d,]*\.?\d*)\s*([kKmMbB]?)(\s*%)?", t)
    if m:
        bound = (m.group(1) or "").strip()
        val = float(m.group(2).replace(",", ""))
        abbr = (m.group(3) or "").lower()
        pct = bool((m.group(4) or "").strip())
        mult = {"k":1_000, "m":1_000_000, "b":1_000_000_000}.get(abbr, 1)
        val *= mult
        pretty = f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"
        unit = "%" if pct else unit_hint
        # prefer exact bound if provided; else use ≈ for approximate language
        prefix = bound if bound else ("≈" if approx else "")
        return f"{prefix}{pretty}{unit}".strip()

    # no numbers found
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
    """One-pass post-process: convert '~5k images' → '≈5,000 images', etc."""
    for path, unit in _NUMERIC_HINTS.items():
        # reuse existing getter
        v = _get_by_path(state, path)
        if isinstance(v, str) and v.strip():
            norm = _norm_num_phrase(v, unit_hint=unit)
            if norm:
                _set_by_path_inplace(state, path, norm)



# ----------------------------- Public API -----------------------------

def run(
    model_hint: str,
    max_iters: int = 5,
    coverage_target: float = 0.75,
    finalize_policy: str = "not_specified",
    *,
    developer: str = "",
    seed_urls: list[str] | None = None,
    seed_pages: list[dict] | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    client, gemini_model, timeout = _client_and_model()

    state: Dict[str, Any] = _empty_agent_state()
    citations: Dict[str, List[Dict[str, str]]] = {}
    
    # Track all implicit sources (URLs included in extraction context)
    implicit_sources: set[str] = set()

    seed_context, seed_urls_from_pages = _prep_seed_context(seed_pages)
    initial_seed_urls = list(seed_urls or []) + seed_urls_from_pages

    plan = _plan_targets(client, gemini_model, model_hint, developer=developer, seed_context=seed_context) or {}
    targets = plan.get("targets", []) or []
    priority = plan.get("fields_priority", []) or []
    
    # Extract model name from hint (remove developer if present)
    model_name = model_hint
    if developer and developer in model_hint:
        # Try to extract just the model name
        parts = model_hint.split("(")
        if len(parts) > 1:
            model_name = parts[0].strip()
        else:
            model_name = model_hint.replace(developer, "").strip()
    # If no developer in hint, use the hint as model name
    if not model_name or model_name == model_hint:
        # Try to extract from hint format "ModelName (Developer)"
        if "(" in model_hint and ")" in model_hint:
            model_name = model_hint.split("(")[0].strip()
        else:
            model_name = model_hint

    # Prepend explicit seed_urls as web targets
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

        # 2) Gather sources
                # Always spawn a fresh loop in a worker thread to avoid "running loop" errors
        from concurrent.futures import ThreadPoolExecutor

        def _run():
            return asyncio.run(_gather_targets_async(
                targets, 
                concurrency=4,
                model_name=model_name,
                developer=developer
            ))

        with ThreadPoolExecutor(max_workers=1) as ex:
            blobs, types = ex.submit(_run).result()

        # 2a) Prime with provided seed page text
        if first_round and seed_pages:
            for sp in seed_pages:
                su = (sp or {}).get("url", "").strip()
                st = (sp or {}).get("text", "").strip()
                if su and st:
                    blobs.append((su, st))
                    types.append("web")
            first_round = False

        # Track implicit sources: all URLs included in extraction context
        for url, _ in blobs:
            if url and url.strip():
                implicit_sources.add(url.strip())

        manifest, sources_blob = normalize_sources(blobs, types)
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
        
        # If fields empty, prioritize specialized CHAI fields that require external sources
        if not want:
            # Priority order: specialized fields first, then all others
            specialized_fields = [
                # Commonly missing critical fields
                "release_date",
                "global_availability",
                "how_to_use",
                "developer_supplied_warnings",
                "model_limitations",
                "training_data",
                "output_input_data_type",
                "ongoing_maintenance",
                "transparency_information",
                "usefulness_efficacy_result",
                "safety_reliability_goal_of_metrics",
                "safety_reliability_result",
                "safety_reliability_interpretation",
                "safety_reliability_test_type",
                "safety_reliability_testing_data_description",
                "safety_reliability_validation_process_and_justification",
                # Regulatory and compliance fields
                "regulatory_approval_status_if_applicable",
                "irb_approval", 
                "ethical_review_board_oversight",
                "clinical_trial_if_available",
                "reimbursement_status_if_applicable",
                "stakeholders_consulted_during_design_of_solution",
                # Fairness and equity fields
                "fairness_equity_goal_of_metrics",
                "fairness_equity_result",
                "fairness_equity_interpretation",
                "bias_mitigation_approaches",
                "skin_tone_diversity",
                "demographic_representativeness"
            ]
            
            # First, add specialized fields that are empty
            for field in specialized_fields:
                cur = _get_by_path(state, field)
                if _is_empty(cur):
                    want.append(field)
            
            # Then add any other empty fields
            for field in _CHAI_FIELDS:
                if field not in specialized_fields:  # Avoid duplicates
                    cur = _get_by_path(state, field)
                    if _is_empty(cur):
                        want.append(field)
        
        print(f"DEBUG: Selected fields to extract: {want}")

        # 4) Extract - Batch fields to avoid overwhelming the model
        BATCH_SIZE = 15  # Process fields in batches to avoid token limits
        for i in range(0, len(want), BATCH_SIZE):
            batch = want[i:i + BATCH_SIZE]
            print(f"DEBUG: Processing batch {i//BATCH_SIZE + 1}/{(len(want) + BATCH_SIZE - 1)//BATCH_SIZE}: {len(batch)} fields")
            
            try:
                resp = _extract_fields(
                    client=client,
                    model_name=gemini_model,
                    field_paths=batch,
                    manifest=manifest,
                    sources_blob=sources_blob,
                )
            except Exception:
                resp = {}

            values, ev = _normalize_extractor_output(resp, batch)
            
            print(f"DEBUG: Extracted values from batch: {len(values)} fields")
            print(f"DEBUG: Extracted evidence from batch: {list(ev.keys())}")

            # Check if this batch appears to be a failure before merging
            if _is_failed_batch(values, ev):
                print(f"DEBUG: Detected failed batch - skipping merge to preserve existing data")
                continue
            
            # Merge values with safe merge strategy
            merge_count = 0
            for k, v in values.items():
                try:
                    if not isinstance(k, str) or not k.strip():
                        continue
                    if any(x in k for x in ["CRITICAL REQUIREMENTS", "You MUST", "The JSON MUST", " and end with"]):
                        continue
                    
                    # Get existing value
                    if "." in k:
                        existing = _get_by_path(state, k)
                    else:
                        existing = state.get(k)
                    
                    # Use safe merge to determine the best value
                    merged_value, was_changed = _safe_merge_value(existing, v, k)
                    
                    if was_changed:
                        if "." in k:
                            set_by_path(state, k, merged_value)
                            print(f"DEBUG: Updated nested field {k} = {merged_value}")
                        else:
                            state[k] = merged_value
                            print(f"DEBUG: Updated flat field {k} = {merged_value}")
                        merge_count += 1
                    else:
                        print(f"DEBUG: Kept existing value for field {k} = {existing} (new value was {v})")
                        
                except Exception as e:
                    print(f"DEBUG: Failed to merge field {k}: {e}")
                    continue
            
            print(f"DEBUG: Successfully merged {merge_count} fields from batch")

            # Merge evidence
            for k, lst in ev.items():
                if not isinstance(lst, list):
                    continue
                citations.setdefault(k, [])
                for e in lst:
                    u = e.get("url")
                    sn = e.get("snippet")
                    if u and sn:
                        citations[k].append({"url": u, "snippet": sn[:240]})

        # 5) Validate → expand targets
        verdict = _validate_patch(client, gemini_model, gemini_model, state) or {}
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

        # 6) Field-specific extraction passes for commonly missing fields
        # Pass 1: Extract fields that need synthesis from multiple sources
        commonly_missing_fields = [
            "release_date", "global_availability", "how_to_use",
            "developer_supplied_warnings", "model_limitations",
            "training_data", "output_input_data_type", "ongoing_maintenance",
            "transparency_information", "usefulness_efficacy_result"
        ]
        
        missing_common_fields = [f for f in commonly_missing_fields if _is_empty(_get_by_path(state, f))]
        if missing_common_fields and sources_blob:
            print(f"DEBUG: Field-specific pass 1: Attempting to extract {len(missing_common_fields)} commonly missing fields")
            try:
                resp = _extract_fields(
                    client=client,
                    model_name=gemini_model,
                    field_paths=missing_common_fields[:10],  # Limit to 10 at a time
                    manifest=manifest,
                    sources_blob=sources_blob,
                )
                values, ev = _normalize_extractor_output(resp, missing_common_fields[:10])
                for k, v in values.items():
                    if v and _is_empty(_get_by_path(state, k)):
                        if "." in k:
                            set_by_path(state, k, v)
                        else:
                            state[k] = v
                        print(f"DEBUG: Field-specific pass filled {k}")
            except Exception as e:
                print(f"DEBUG: Field-specific pass 1 failed: {e}")
        
        # 7) Stop criteria with adaptive coverage calculation
        total_nonempty = flatten_nonempty(state)
        
        # Weight critical fields 2x in coverage calculation
        critical_fields = [
            "model_name", "developer", "summary", "intended_use_and_workflow",
            "model_limitations", "training_data", "usefulness_efficacy_result"
        ]
        critical_filled = sum(1 for f in critical_fields if not _is_empty(_get_by_path(state, f)))
        weighted_coverage = (total_nonempty + critical_filled) / max(50, total_nonempty + critical_filled)
        
        denom = max(50, total_nonempty)
        coverage = total_nonempty / denom
        
        # Use weighted coverage for stopping decision
        effective_coverage = max(coverage, weighted_coverage)
        
        if (not missing and not weak) or effective_coverage >= coverage_target:
            break
    _normalize_numeric_fields_in_place(state)
    if finalize_policy == "not_specified":
        state = _finalize_not_specified(state)

    # Combine implicit + explicit sources with usage metadata
    # Extract explicit sources from citations
    explicit_sources: set[str] = set()
    for field_name, field_citations in citations.items():
        if not isinstance(field_citations, list):
            continue
        for citation in field_citations:
            if isinstance(citation, dict):
                url = citation.get("url", "").strip()
                if url:
                    explicit_sources.add(url)
    
    # Union of all used sources
    all_used_sources = implicit_sources.union(explicit_sources)
    
    # Enhance citations structure with usage metadata
    # Create a comprehensive sources dict with usage labels
    enhanced_citations = {
        "_sources_metadata": {}
    }
    
    # Copy existing field-level citations
    for field_name, field_citations in citations.items():
        enhanced_citations[field_name] = field_citations
    
    # Add metadata for all sources
    for url in all_used_sources:
        if url in explicit_sources and url in implicit_sources:
            usage = "both"
            reason = "Included in extraction context and directly cited"
        elif url in explicit_sources:
            usage = "explicit"
            reason = "Directly cited for extracted claims"
        else:
            usage = "implicit"
            reason = "Included in extraction context and informed reasoning but not directly quoted"
        
        enhanced_citations["_sources_metadata"][url] = {
            "usage": usage,
            "reason": reason
        }
    
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
    return await asyncio.to_thread(
        run,
        model_hint,
        max_iters,
        coverage_target,
        finalize_policy,
        developer=developer,
        seed_urls=seed_urls,
        seed_pages=seed_pages,
    )
