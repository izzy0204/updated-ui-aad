#!/usr/bin/env python3
"""Fill in missing per-field citations on already-generated auto eval-2 cards,
WITHOUT re-running generation. Reuses each card's own already-cited source URLs
(refetched from cache — no new discovery/scraping), plus a couple of known-good
extra URLs for SkinVision (which only ever got one source). Asks Gemini only
for evidence supporting text that's already written; never rewrites values.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from core.chai_schema import ClinicalModelCard, REGULATORY_STATUS_LABELS  # noqa: E402
from core.dermauto_card_render import (  # noqa: E402
    format_clinical_trial,
    format_contact,
    format_development,
    format_performance_summary,
    format_training_data,
    format_version_with_date,
)
from core.citation_sidecar import align_snippet_to_field_text  # noqa: E402
from pipelines.cardgen_pipeline import _postfill_client  # noqa: E402
from utils.web_search import fetch_many  # noqa: E402

PRELOADED = REPO / "src" / "core" / "pages" / "preloaded_cards"

# Missing (field_key -> displayed value already written); field_key matches
# the dotted convention used by field_citations elsewhere in this codebase.
MISSING_FIELDS = {
    "dermasensor": ["regulatory_approval_status", "availability", "ongoing_monitoring_plan"],
    "skinanalytics": [
        "availability",
        "model_development_and_validation.description",
        "clinical_trial",
        "ongoing_monitoring_plan",
        "scheduled_updates",
    ],
    "dermgpt": [
        "regulatory_approval_status",
        "version",
        "availability",
        "performance.summary",
        "ongoing_monitoring_plan",
        "scheduled_updates",
        "contact",
    ],
    "skinvision": ["target_patient_population", "known_performance_limitations", "contact"],
    "tandem": ["contact"],
}

# SkinVision only ever got one real source; add known-good pages (referenced
# in the manual card / publicly on skinvision.com) to give the backfill pass
# something to actually search for support in.
EXTRA_SOURCE_URLS = {
    "skinvision": [
        "https://www.skinvision.com/about/",
        "https://www.skinvision.com/scientific-evidence",
        "https://www.skinvision.com/contact-us",
    ],
    "tandem": ["https://forus.com", "https://forus.com/stories"],
}


def displayed_text(card: ClinicalModelCard, field_key: str) -> str:
    if field_key == "regulatory_approval_status":
        return REGULATORY_STATUS_LABELS.get(card.regulatory_approval_status, str(card.regulatory_approval_status.value))
    if field_key == "version":
        return format_version_with_date(card.version, card.last_updated)
    if field_key == "training_data.description":
        return format_training_data(card.training_data)
    if field_key == "model_development_and_validation.description":
        return format_development(card.model_development_and_validation)
    if field_key == "clinical_trial":
        return format_clinical_trial(card.clinical_trial) or ""
    if field_key == "performance.summary":
        return format_performance_summary(card.performance)
    if field_key == "contact":
        return format_contact(card.contact)
    return str(getattr(card, field_key, "") or "")


def build_sources_blob(urls: list[str], pages: list[dict], max_chars_per_page: int = 6000) -> str:
    by_url = {p.get("url", "").strip(): (p.get("text") or "").strip() for p in pages}
    parts = []
    for i, u in enumerate(urls, 1):
        text = by_url.get(u, "")
        if not text:
            continue
        parts.append(f"[SOURCE {i}] URL: {u}\nCONTENT:\n{text[:max_chars_per_page]}\n")
    return "\n\n".join(parts)


async def backfill_card(slug: str, client, model, config) -> None:
    json_path = PRELOADED / f"{slug}-auto-eval-2.clinical.json"
    cite_path = PRELOADED / f"{slug}-auto-eval-2.citations.json"
    md_path = PRELOADED / f"{slug}-auto-eval-2.clinical.md"

    card = ClinicalModelCard.from_dict(json.loads(json_path.read_text(encoding="utf-8")))
    citations = json.loads(cite_path.read_text(encoding="utf-8"))
    references: dict[str, dict] = citations.get("references", {})
    field_citations: dict[str, list[dict]] = citations.get("field_citations", {})

    known_urls = [meta["url"] for meta in references.values() if meta.get("url")]
    extra = EXTRA_SOURCE_URLS.get(slug, [])
    all_urls = list(dict.fromkeys(known_urls + extra))

    print(f"=== {slug}: fetching {len(all_urls)} known/extra source(s) ===", flush=True)
    pages = await fetch_many(all_urls)
    sources_blob = build_sources_blob(all_urls, pages)

    missing = MISSING_FIELDS.get(slug, [])
    to_ask = []
    field_values: dict[str, str] = {}
    for fkey in missing:
        val = displayed_text(card, fkey)
        if not val.strip() or val.strip() == "Not disclosed":
            print(f"  skip {fkey}: no content")
            continue
        field_values[fkey] = val
        to_ask.append(fkey)

    if not to_ask:
        print("  nothing to backfill")
        return

    prompt = f"""You are checking citations for an already-written medical AI model card.
For each field below, the VALUE was already extracted and is FINAL — do not rewrite it.
Your only job is to find which of the SOURCES below support that value, and return evidence.

Return ONLY JSON: {{"evidence": {{"<field>": [{{"url": "...", "snippet": "..."}}, ...]}}}}

Rules:
- "url" MUST be copied EXACTLY from a "URL:" line in SOURCES below. Never invent a URL.
- If a field's value draws on more than one source, list evidence for ALL of them.
- "snippet" should be a short phrase (a few words) that appears VERBATIM in the field's
  VALUE text (not the source page), so it can be located within that text.
- If truly no source supports a field, omit that field's key from "evidence" entirely
  (do not fabricate).

FIELDS:
{json.dumps(field_values, indent=2)}

SOURCES:
{sources_blob}
"""

    resp = await client.aio.models.generate_content(model=model, contents=prompt, config=config)
    raw = ""
    if hasattr(resp, "candidates") and resp.candidates:
        for part in resp.candidates[0].content.parts:
            if getattr(part, "thought", False):
                continue
            if getattr(part, "text", None):
                raw = part.text
                break
    if not raw:
        raw = getattr(resp, "text", None) or ""

    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        print("  ERROR: no JSON in response")
        return
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        cleaned = re.sub(r",\s*([}\]])", r"\1", m.group(0))
        obj = json.loads(cleaned)

    evidence = obj.get("evidence", {}) if isinstance(obj, dict) else {}

    def _ref_id_for_url(url: str) -> str | None:
        for rid, meta in references.items():
            if meta.get("url") == url:
                return rid
        return None

    next_id = max((int(k) for k in references.keys() if str(k).isdigit()), default=0) + 1

    for fkey in to_ask:
        items = evidence.get(fkey, [])
        if not isinstance(items, list) or not items:
            print(f"  no evidence found for {fkey}")
            continue

        field_text = field_values[fkey]
        spans = []
        ref_ids: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url or url not in all_urls:
                continue
            rid = _ref_id_for_url(url)
            if rid is None:
                rid = str(next_id)
                references[rid] = {"url": url, "title": "", "source": ""}
                next_id += 1
            ref_ids.append(rid)
            snippet = str(item.get("snippet") or "").strip()
            if snippet:
                aligned = align_snippet_to_field_text(field_text, snippet)
                if aligned:
                    start, end = aligned
                    spans.append({"text": field_text[start:end], "citationIds": [rid]})

        if spans:
            field_citations[fkey] = spans
            print(f"  backfilled {fkey}: exact spans -> refs {sorted(set(ref_ids))}")
        elif ref_ids:
            field_citations[fkey] = [{"citationIds": sorted(set(ref_ids)), "sentence_level": True}]
            print(f"  backfilled {fkey}: sentence_level -> refs {sorted(set(ref_ids))}")

    citations["references"] = references
    citations["field_citations"] = field_citations
    cite_path.write_text(json.dumps(citations, indent=2), encoding="utf-8")
    md_path.write_text(card.to_markdown(citations=citations), encoding="utf-8")
    print(f"  wrote {cite_path.name}, {md_path.name}")


async def main() -> int:
    client, model, config = _postfill_client()
    if client is None:
        print("ERROR: no Gemini client available (missing API key?)")
        return 1

    for slug in MISSING_FIELDS:
        try:
            await backfill_card(slug, client, model, config)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR backfilling {slug}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
