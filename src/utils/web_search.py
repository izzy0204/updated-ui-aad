"""
Web Search & Fetch Module for AI Model Card Generator

- DuckDuckGo HTML search (no API key)
- Robust async fetcher (HTML/PDF) with retries
- Clean text extraction (trafilatura, PyPDF)
- Helpers to discover and fetch seed pages
"""

from __future__ import annotations

import asyncio
import logging
import re
from io import BytesIO
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, unquote

import aiohttp
from bs4 import BeautifulSoup
from pypdf import PdfReader
import trafilatura

from utils.net import new_session  # centralized session (certifi CA, proxy-aware, sane timeouts)

logger = logging.getLogger(__name__)

# ---------- URL normalization ----------

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, unquote

_TRACKING_KEYS = ("utm_", "fbclid", "gclid", "_ga", "_gac", "mc_", "ref", "source")

def canonical_url(url: str) -> str:
    try:
        if not url:
            return ""
        url = url.strip()

        # Add https for schemeless //example.com
        if url.startswith("//"):
            url = "https:" + url

        s = urlsplit(url)

        # Unwrap DuckDuckGo redirect: https://duckduckgo.com/l?uddg=<encoded>
        if s.netloc.endswith("duckduckgo.com") and s.path.startswith("/l"):
            qs = dict(parse_qsl(s.query, keep_blank_values=True))
            uddg = qs.get("uddg")
            if uddg:
                # uddg itself can contain percent-encoding
                return canonical_url(unquote(uddg))

        # Normal clean-up for tracking params
        q = [
            (k, v)
            for (k, v) in parse_qsl(s.query, keep_blank_values=True)
            if not any(k.lower().startswith(tk) for tk in _TRACKING_KEYS)
        ]
        # Normalize path: remove trailing slash except for root
        path = s.path.rstrip("/") or "/"
        return urlunsplit((s.scheme or "https", s.netloc, path, urlencode(q), ""))
    except Exception:
        return (url or "").strip()



# ---------- Search (DuckDuckGo HTML) ----------

_DDG_PRIMARY = "https://duckduckgo.com/html/"
_DDG_FALLBACK = "https://html.duckduckgo.com/html/"

async def _ddg_search_once(session: aiohttp.ClientSession, base_url: str, query: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    params = {"q": query, "kl": "us-en"}
    # Per-request UA is okay; session already has a polite default as well
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ModelCardGenerator/1.0; +https://example.invalid)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    async with session.get(base_url, params=params, headers=headers) as r:
        if r.status != 200:
            logger.warning("DuckDuckGo %s returned %s for %r", base_url, r.status, query)
            return results
        html = await r.text()
        soup = BeautifulSoup(html, "html.parser")

        # DDG HTML layout: links usually in a.result__a, snippet nearby.
        # Keep lenient fallbacks for robustness.
        link_nodes = soup.select("a.result__a") or soup.select("a[href]")
        rank = 0
        seen: set[str] = set()

        for a in link_nodes:
            title = (a.get_text(strip=True) or "").strip()
            href = canonical_url(a.get("href", ""))

            if not title or not href or href in seen:
                continue

            # Try common snippet containers near the link
            snip_el = a.find_next_sibling(class_="result__snippet")
            if not snip_el:
                # Some templates put snippet inside a parent container
                parent = a.find_parent(class_="result") or a.parent
                snip_el = parent.find(class_="result__snippet") if parent else None
            snippet = (snip_el.get_text(strip=True) if snip_el else "").strip()

            rank += 1
            seen.add(href)
            results.append({
                "title": title,
                "url": href,
                "snippet": snippet,
                "source": "duckduckgo",
                "rank": rank,
            })

    return results


async def web_search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    DuckDuckGo HTML search (no API key).
    Returns: [{title, url, snippet, source='duckduckgo', rank}, ...]
    """
    results: List[Dict[str, Any]] = []
    try:
        async with new_session() as session:
            # Try primary (main domain) first; fallback to html subdomain if needed
            try:
                results = await _ddg_search_once(session, _DDG_PRIMARY, query)
            except Exception as e:
                logger.warning("DDG primary failed (%s). Trying fallback…", e)
                results = []

            if not results:
                try:
                    results = await _ddg_search_once(session, _DDG_FALLBACK, query)
                except Exception as e:
                    logger.error("DDG fallback failed for %r: %s", query, e)
                    results = []
    except Exception as e:
        logger.error("Error in web_search(%r): %s", query, e)

    return results[:max_results]


def is_web_search_available() -> bool:
    return True


def get_web_search_providers() -> List[str]:
    return ["duckduckgo"]


# ---------- Extraction helpers ----------

def _extract_html_text(html: str, url: str) -> str:
    txt = trafilatura.extract(html, url=url, include_comments=False, include_images=False) or ""
    return re.sub(r"\s+\n", "\n", txt).strip()


def _extract_pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(data))
        pages: List[str] = []
        for p in reader.pages:
            t = p.extract_text() or ""
            if t.strip():
                pages.append(t)
        return "\n\n".join(pages).strip()
    except Exception:
        return ""


# ---------- Robust async fetcher (HTML/PDF + retries) ----------

async def _fetch_one(session: aiohttp.ClientSession, url: str, timeout: float = 20.0) -> Dict[str, Any]:
    u = canonical_url(url)
    try:
        async with session.get(u, timeout=timeout, allow_redirects=True) as r:
            ct = (r.headers.get("Content-Type") or "").lower()
            raw = await r.read()

            if "pdf" in ct or u.lower().endswith(".pdf"):
                text = _extract_pdf_text(raw)
                kind = "pdf"
            else:
                try:
                    html = raw.decode(r.charset or "utf-8", errors="ignore")
                except Exception:
                    html = raw.decode("utf-8", errors="ignore")
                text = _extract_html_text(html, u)
                kind = "html"

            return {"url": u, "status": r.status, "type": kind, "text": text}
    except Exception as e:
        return {"url": u, "status": 0, "type": "error", "error": str(e), "text": ""}


async def fetch_many(urls: List[str], *, concurrency: int = 6) -> List[Dict[str, Any]]:
    """
    Fetch a list of URLs with retries + backoff.
    Returns: [{url, status, type: 'html'|'pdf'|'error', text, error?}, ...]
    """
    if not urls:
        return []

    sem = asyncio.Semaphore(concurrency)

    async with new_session() as session:
        async def _task(u: str):
            async with sem:
                res: Dict[str, Any] = {}
                # naive retry on transient statuses
                for attempt in range(3):
                    res = await _fetch_one(session, u)
                    if res.get("status", 0) in (0, 408, 429, 500, 502, 503, 504):
                        await asyncio.sleep(0.6 * (2 ** attempt))
                        continue
                    break
                return res

        return await asyncio.gather(*[_task(u) for u in urls])


# ---------- Discovery helpers (queries + fetch) ----------

async def discover_model_sources(model_name: str, developer: str = "") -> List[Dict[str, Any]]:
    """
    Run several targeted queries and return de-duplicated search results.
    """
    # Always include developer when available to make searches more specific
    base_query = f"{developer} {model_name}" if developer else model_name
    
    queries = [
        f"{base_query} official site",
        f"{base_query} documentation", 
        f"{base_query} dermatology AI",
        f"{base_query} paper",
        f"{base_query} AI model",
        f"{base_query} publication",
    ]
    
    # If no developer provided, add some fallback queries without developer
    if not developer:
        queries.extend([
            f"{model_name} official site",
            f"{model_name} documentation",
        ])
    
    seen: set[str] = set()
    found: List[Dict[str, Any]] = []
    
    for q in queries:
        hits = await web_search(q, max_results=6)
        for h in hits:
            url = canonical_url((h or {}).get("url", ""))
            if not url or url in seen:
                continue
            seen.add(url)
            found.append({
                "title": (h or {}).get("title", ""),
                "url": url,
                "description": (h or {}).get("snippet", ""),
                "type": "web",
                "priority_score": 5.0,
            })
    return found[:20]


async def discover_and_fetch(
    model_name: str,
    developer: str = "",
    top_k: int = 5,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Convenience: discover sources then fetch the top_k to get clean text.
    Returns (discovered_list, seed_pages_with_text)
    """
    discovered = await discover_model_sources(model_name, developer)
    urls = [s["url"] for s in discovered[:top_k] if s.get("url")]

    pages: List[Dict[str, Any]] = []
    if urls:
        fetched = await fetch_many(urls, concurrency=6)
        pages = [
            {"url": r["url"], "text": r.get("text", "")}
            for r in fetched
            if (r.get("text") or "").strip()
        ]
    return discovered, pages


__all__ = [
    "web_search",
    "is_web_search_available",
    "get_web_search_providers",
    "canonical_url",
    "fetch_many",
    "discover_model_sources",
    "discover_and_fetch",
]
