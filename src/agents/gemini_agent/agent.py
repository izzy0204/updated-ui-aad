# src/agents/gemini_agent/agent.py
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import fields as dc_fields
from typing import Any, Dict, List, Optional, Tuple

from utils.web_search import fetch_many
from config.config import get_settings
from core.chai_schema import CHAIModelCard
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

import google.generativeai as genai


# ----------------------------- CHAI fields -----------------------------

_CHAI_FIELDS = [f.name for f in dc_fields(CHAIModelCard) if f.name != "extraction_timestamp"]


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

def _client_and_model() -> tuple[genai.GenerativeModel, str, float]:
    s = get_settings()
    genai.configure(api_key=s.google_api_key)
    model_obj = genai.GenerativeModel(s.gemini_model)
    return model_obj, s.gemini_model, s.http_timeout


def _gemini_json(gmodel: genai.GenerativeModel, *, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
    """
    Safe single-turn call that extracts the first JSON object the model returns.
    Keyword-only args prevent accidental positional swaps (fix B).
    """
    try:
        if not hasattr(gmodel, "generate_content"):
            # Someone passed a string model id instead of the GenerativeModel object
            return {}

        text = ((system + "\n\n") if system else "") + prompt
        resp = gmodel.generate_content(text)
        out_text = getattr(resp, "text", None) or ""

        if not out_text:
            return {}

        # extract_json_block already tolerates ```json fences and stray prose
        obj = extract_json_block(out_text)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


# ----------------------------- Agent steps -----------------------------

def _plan_targets(model, model_hint: str, *, developer: str, seed_context: str = "") -> Dict[str, Any]:
    print(f"DEBUG: _plan_targets called with model_hint={repr(model_hint)}, developer={repr(developer)}")
    seed_block = f"\n\nSEED CONTEXT (pre-extracted pages):\n{seed_context}\n" if seed_context else ""

    guardrails = []
    if developer:
        guardrails.append(
            "DEVELOPER CONSTRAINT:\n"
            f"- The developer/owner of this AI model is **{developer}**.\n"
            "- Prefer sources on the developer’s official domains (e.g., *.<developer>.com, <model_name.com>, github.com/<developer>, huggingface.co/<developer>) when selecting targets.\n"
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

    result = _gemini_json(model, prompt=planner_prompt)
    print(f"DEBUG: _plan_targets result: {type(result)} = {repr(result)[:200]}...")
    return result

async def _gather_targets_async(
    targets: List[Dict[str, str]],
    *,
    concurrency: int = 4,
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
    gmodel: genai.GenerativeModel,
    field_paths: List[str],
    manifest: str,
    sources_blob: str,
) -> Dict[str, Any]:
    allowed_fields = _CHAI_FIELDS
    prompt = EXTRACTOR.format(
        field_paths=json.dumps(field_paths),
        allowed_fields=json.dumps(allowed_fields),
        manifest=manifest,
        sources=sources_blob,
    )
    return _gemini_json(gmodel, prompt=prompt) or {}


def _validate_patch(gmodel: genai.GenerativeModel, model_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
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
        out = _gemini_json(gmodel, prompt=prompt) or {}
        return {
            "missing": out.get("missing") if isinstance(out.get("missing"), list) else local_missing,
            "weak": out.get("weak") if isinstance(out.get("weak"), list) else [],
            "next_fetch": out.get("next_fetch") if isinstance(out.get("next_fetch"), list) else [],
        }
    except Exception:
        return {"missing": local_missing, "weak": [], "next_fetch": []}


# ----------------------------- Utilities -----------------------------

def _get_by_path(root: Dict[str, Any], path: str) -> Any:
    cur: Any = root
    for k in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


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

    if not isinstance(raw, dict):
        if isinstance(raw, str) and len(want_fields) == 1:
            values[want_fields[0]] = raw.strip()
        return values, evidence

    # 1) Primary "values" object
    if isinstance(raw.get("values"), dict):
        for k, v in raw["values"].items():
            if isinstance(v, (str, int, float)):
                values[str(k)] = str(v).strip()
            elif v is None:
                values[str(k)] = ""
            elif isinstance(v, list):
                values[str(k)] = "; ".join(str(x).strip() for x in v if str(x).strip())

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


# ----------------------------- Public API -----------------------------

def run(
    model_hint: str,
    max_iters: int = 3,
    coverage_target: float = 0.60,
    finalize_policy: str = "not_specified",
    *,
    developer: str = "",
    seed_urls: list[str] | None = None,
    seed_pages: list[dict] | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    gmodel, gemini_model, timeout = _client_and_model()

    state: Dict[str, Any] = _empty_agent_state()
    citations: Dict[str, List[Dict[str, str]]] = {}

    seed_context, seed_urls_from_pages = _prep_seed_context(seed_pages)
    initial_seed_urls = list(seed_urls or []) + seed_urls_from_pages

    plan = _plan_targets(gmodel, model_hint, developer=developer, seed_context=seed_context) or {}
    targets = plan.get("targets", []) or []
    priority = plan.get("fields_priority", []) or []

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
            return asyncio.run(_gather_targets_async(targets, concurrency=4))

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
        if not want:
            want = ["summary", "intended_use_and_workflow", "model_limitations", "model_type"]

        # 4) Extract
        try:
            resp = _extract_fields(
                gmodel=gmodel,
                field_paths=want,
                manifest=manifest,
                sources_blob=sources_blob,
            )
        except Exception:
            resp = {}

        values, ev = _normalize_extractor_output(resp, want)

        # Merge values
        for k, v in values.items():
            try:
                if not isinstance(k, str) or not k.strip():
                    continue
                if any(x in k for x in ["CRITICAL REQUIREMENTS", "You MUST", "The JSON MUST", " and end with"]):
                    continue
                if "." in k:
                    set_by_path(state, k, v)
                else:
                    state[k] = v
            except Exception:
                continue

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
        verdict = _validate_patch(gmodel, gemini_model, state) or {}
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

        # 6) Stop criteria
        total_nonempty = flatten_nonempty(state)
        denom = max(50, total_nonempty)
        coverage = total_nonempty / denom
        if (not missing and not weak) or coverage >= coverage_target:
            break

    if finalize_policy == "not_specified":
        state = _finalize_not_specified(state)

    return state, citations


async def run_async(
    *,
    model_hint: str,
    max_iters: int = 3,
    coverage_target: float = 0.60,
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
