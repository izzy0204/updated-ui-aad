# src/agents/gemini_agent/agent.py
from __future__ import annotations

import asyncio
from typing import List, Dict, Any, Tuple, Optional
import json
from config.config import get_settings  # centralized config (single .env load)
from .prompts import PLANNER, EXTRACTOR, VALIDATOR
from .tools import (
    ddg_search,
    fetch_text_url,
    fetch_hf_readme,
    fetch_github_readme,
    normalize_sources,
    extract_json_block,
    set_by_path,
    flatten_nonempty,
)

from google import genai
from core.chai_schema import CHAIModelCard
from dataclasses import fields as dc_fields  # add if not already imported

# All CHAI field names except the generated timestamp
_CHAI_FIELDS = [f.name for f in dc_fields(CHAIModelCard) if f.name != "extraction_timestamp"]

def _prep_seed_context(seed_pages: list[dict] | None, *, max_chars_per_page: int = 8000, max_pages: int = 8) -> tuple[str, list[str]]:
    """
    Returns (context_text, ordered_urls_used). Truncates aggressively to stay under token limits.
    seed_pages: [{ "url": str, "text": str }]
    """
    if not seed_pages:
        return "", []
    cleaned = []
    seen = set()
    for page in seed_pages:
        url = (page or {}).get("url", "").strip()
        txt = (page or {}).get("text", "").strip()
        if not url or not txt or url in seen:
            continue
        seen.add(url)
        # naive trim; you can switch to a real chunker later
        snippet = txt[:max_chars_per_page].strip()
        if snippet:
            cleaned.append((url, snippet))
        if len(cleaned) >= max_pages:
            break
    # Build a compact context block the model can scan quickly
    parts = []
    ordered_urls = []
    for i, (u, snip) in enumerate(cleaned, 1):
        ordered_urls.append(u)
        parts.append(f"[SEED {i}] URL: {u}\nCONTENT:\n{snip}\n")
    return ("\n\n".join(parts).strip(), ordered_urls)


# ----------------------------- Client / I/O -----------------------------

def _client_and_model():
    """
    Creates a Gemini client using centralized settings.
    No .env reads here; config.config already loaded it once.
    """
    s = get_settings()
    client = genai.Client(api_key=s.google_api_key)
    return client, s.gemini_model, s.http_timeout


def _chat_json(client, model: str, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
    """
    Fire a single-turn chat to Gemini and recover the first JSON object found.
    """
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    resp = client.models.generate_content(model=model, contents=msgs)
    text = getattr(resp, "text", None) or getattr(resp, "output_text", None) or ""
    return extract_json_block(text)


# ----------------------------- Agent Steps -----------------------------

def _plan_targets(client, model, model_hint: str, seed_context: str = "") -> Dict[str, Any]:
    """
    Ask Gemini to propose initial fetch targets and a field priority list.
    If seed_context is provided (from pre-extracted seed_pages), include it up front
    so the planner can leverage already-available content.
    """
    seed_block = f"\n\nSEED CONTEXT (pre-extracted pages):\n{seed_context}\n" if seed_context else ""
    return _chat_json(client, model, PLANNER + f"\n\nMODEL HINT: {model_hint}{seed_block}")



def _gather_targets(
    targets: List[Dict[str, str]],
    timeout: float,
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """
    Fetches content for each planned target.

    Returns:
        blobs: list of (url, text)
        types: parallel list of 'huggingface' | 'github' | 'web'
    """
    blobs: List[Tuple[str, str]] = []
    types: List[str] = []

    for t in targets:
        try:
            ttype = t.get("type")
            if ttype == "huggingface":
                url, txt = fetch_hf_readme(t.get("id", ""), timeout)
            elif ttype == "github":
                url, txt = fetch_github_readme(t.get("id", ""), timeout)
            elif ttype == "web":
                u = t.get("url", "")
                url, txt = u, fetch_text_url(u, timeout)
            else:
                continue

            if txt:
                blobs.append((url, txt))
                types.append(ttype or "web")
        except Exception:
            # ignore individual fetch failures
            continue

    return blobs, types


def _extract_fields(
    client,
    model,
    field_paths: List[str],
    manifest: str,
    sources_blob: str,
) -> Dict[str, Any]:
    """
    Ask Gemini to fill requested fields from the given sources.
    We enforce CHAI field names and pass JSON-encoded arrays to the prompt.
    """
    allowed_fields = _CHAI_FIELDS  # superset → fewer "unknown key" errors
    prompt = EXTRACTOR.format(
        field_paths=json.dumps(field_paths),       # IMPORTANT: JSON
        allowed_fields=json.dumps(allowed_fields), # IMPORTANT: JSON
        manifest=manifest,
        sources=sources_blob,
    )
    return _chat_json(client, model, prompt)

def _validate_patch(client, model: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ask the VALIDATOR prompt to assess the current 'state' and suggest:
      - missing: list of CHAI field names that are absent/empty
      - weak: list of CHAI field names that are vague/underspecified
      - next_fetch: list of {"url": "..."} and/or {"query": "..."} items

    Also computes a conservative local 'missing' fallback using the CHAI schema,
    in case the LLM returns nothing usable.
    """
    # --- local fallback 'missing' based on CHAI schema field names ---
    chai_fields = [f.name for f in dc_fields(CHAIModelCard) if f.name != "extraction_timestamp"]

    def _get_by_path(root: Dict[str, Any], path: str) -> Any:
        cur: Any = root
        for k in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    # A field is considered present if it exists as a flat key or as a dotted key somewhere in state
    def _present(field: str) -> bool:
        # flat CHAI key?
        v = state.get(field, None)
        if isinstance(v, str) and v.strip():
            return True
        if isinstance(v, list) and any(str(x).strip() for x in v):
            return True
        # legacy dotted keys (e.g., "metadata.summary")
        for k, val in state.items():
            if isinstance(k, str) and "." in k and k.split(".")[-1] == field:
                if isinstance(val, str) and val.strip():
                    return True
                if isinstance(val, list) and any(str(x).strip() for x in val):
                    return True
        return False

    local_missing = [f for f in chai_fields if not _present(f)]

    # --- call the validator LLM ---
    try:
        card_json = json.dumps(state, ensure_ascii=False, indent=2)
        prompt = VALIDATOR + "\n\nCURRENT CARD (partial JSON; may include flat and dotted keys):\n" + card_json
        out = _chat_json(client, model, prompt) or {}
        # Normalize shape & apply conservative fallbacks
        verdict = {
            "missing": out.get("missing") if isinstance(out.get("missing"), list) else local_missing,
            "weak": out.get("weak") if isinstance(out.get("weak"), list) else [],
            "next_fetch": out.get("next_fetch") if isinstance(out.get("next_fetch"), list) else [],
        }
        return verdict
    except Exception:
        # If anything goes wrong, fall back to local heuristic only
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
    """
    Basic nested structure the agent uses internally.
    Kept minimal; only sections the agent actively fills today.
    """
    return {
        "metadata": {},
        "uses": {},
        "warnings": {},
        "trust": {},
    }


def _finalize_not_specified(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace empty/None/list-blank leaves with 'Not specified' recursively.
    """
    def fill(node: Any):
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if isinstance(v, dict):
                    fill(v)
                elif v in (None, "", []) or (isinstance(v, list) and not v):
                    node[k] = "Not specified"
        return node

    return fill(state)


# ----------------------------- Public API -----------------------------

def run(
    model_hint: str,
    max_iters: int = 3,
    coverage_target: float = 0.60,
    finalize_policy: str = "not_specified",
    *,
    seed_urls: list[str] | None = None,
    seed_pages: list[dict] | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Run the Gemini-as-Agent loop.

    Returns:
        state: nested agent-style dict with sections: metadata/uses/warnings/trust
        citations: { field_path: [ {url, snippet}, ... ] }
    """
    client, gemini_model, timeout = _client_and_model()

    # Agent's internal nested state (NOT your CHAI dataclass)
    state: Dict[str, Any] = _empty_agent_state()
    citations: Dict[str, List[Dict[str, str]]] = {}

    # -- Prep seed context from seed_pages (compact, truncated)
    seed_context, seed_urls_from_pages = _prep_seed_context(seed_pages)
    # We'll also use the ordered URLs here to bias early targets
    initial_seed_urls = list(seed_urls or []) + seed_urls_from_pages

    # 1) Plan initial targets + priorities (planner sees seed context)
    plan = _plan_targets(client, gemini_model, model_hint, seed_context) or {}
    targets = plan.get("targets", []) or []
    priority = plan.get("fields_priority", []) or []

    # Prepend explicit seed_urls as web targets (first come, first fetched)
    seen_urls = set()
    prefixed = []
    for u in initial_seed_urls:
        uu = (u or "").strip()
        if uu and uu not in seen_urls:
            prefixed.append({"type": "web", "url": uu})
            seen_urls.add(uu)
    # Keep original plan targets after seed-prepended ones
    targets = prefixed + targets

    first_round = True
    for _ in range(max_iters):
        if not targets and not first_round:
            break

        # 2) Gather sources
        blobs, types = _gather_targets(targets, timeout=timeout)

        # 2a) Prime the first round with seed_pages text (no network fetch)
        if first_round and seed_pages:
            for sp in seed_pages:
                su = (sp or {}).get("url", "").strip()
                st = (sp or {}).get("text", "").strip()
                if su and st:
                    blobs.append((su, st))
                    types.append("web")
            first_round = False

        manifest, sources_blob = normalize_sources(blobs, types)

        # 2b) Also prepend seed_context to the extractor’s sources blob for extra recall
        if seed_context:
            sources_blob = f"{seed_context}\n\n{sources_blob}"

        # 3) Pick fields to fill: missing among priority, else a small core set (CHAI names)
        def _is_empty(val: Any) -> bool:
            return val in (None, "", [], {}) or (isinstance(val, list) and not any(str(x).strip() for x in val))

        want: List[str] = []
        for path in priority:
            cur = _get_by_path(state, path)  # works for flat ("summary") or dotted ("metadata.summary")
            if _is_empty(cur):
                want.append(path)

        if not want:
            want = ["summary", "intended_use_and_workflow", "model_limitations", "model_type"]


                # 4) Ask Gemini to extract values + evidence for the chosen fields
        out = _extract_fields(
            client=client,
            model=gemini_model,
            field_paths=want,
            manifest=manifest,
            sources_blob=sources_blob,
        ) or {}

        # Normalize expected shape from extractor
        values = out.get("values") or out.get("fields") or {}
        evidence = out.get("evidence") or {}

        # Merge values into nested state
        for k, v in values.items():
            try:
                if isinstance(k, str) and "." in k:
                    # legacy nested path from older prompts
                    set_by_path(state, k, v)
                else:
                    # flat key (CHAI field name) → store at top level
                    state[k] = v
            except Exception:
                pass

        # Merge evidence
        for k, lst in evidence.items():
            if not isinstance(lst, list):
                continue
            citations.setdefault(k, [])
            for ev in lst:
                url = (ev or {}).get("url")
                snip = (ev or {}).get("snippet")
                if url and snip:
                    citations[k].append({"url": url, "snippet": snip[:240]})


        # 5) Validate → missing/weak + next_fetch
        verdict = _validate_patch(client, gemini_model, state) or {}
        missing = verdict.get("missing", []) or []
        weak = verdict.get("weak", []) or []

        # Expand targets from suggested queries/urls
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

        # 6) Stop if coverage is good or there's nothing left to chase
        total_nonempty = flatten_nonempty(state)
        denom = max(50, total_nonempty)  # conservative lower bound
        coverage = total_nonempty / denom

        if not missing and not weak:
            break
        if coverage >= coverage_target:
            break

    # 7) Finalize
    if finalize_policy == "not_specified":
        state = _finalize_not_specified(state)

    return state, citations



async def run_async(
    *,
    model_hint: str,
    max_iters: int = 3,
    coverage_target: float = 0.60,
    finalize_policy: str = "not_specified",
    seed_urls: list[str] | None = None,
    seed_pages: list[dict] | None = None,
) -> tuple[dict | object, dict]:
    """
    Async convenience wrapper that runs the agent in a worker thread.
    """
    return await asyncio.to_thread(
        run,
        model_hint,
        max_iters,
        coverage_target,
        finalize_policy,
        seed_urls=seed_urls,
        seed_pages=seed_pages,
    )
