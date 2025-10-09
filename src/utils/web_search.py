

"""
Web Search & Fetch Module for AI Model Card Generator

- DuckDuckGo HTML search (no API key)
- Robust async fetcher (HTML/PDF) with retries
- Clean text extraction (trafilatura, PyPDF)
- Helpers to discover and fetch seed pages
"""

from __future__ import annotations
import ssl
import certifi
import asyncio
import aiohttp
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from bs4 import BeautifulSoup
import trafilatura
from pypdf import PdfReader
from io import BytesIO

logger = logging.getLogger(__name__)

def _default_connector():
    return aiohttp.TCPConnector(
        ssl=ssl.create_default_context(cafile=certifi.where()),
        limit=8,
        limit_per_host=4,
        enable_cleanup_closed=True,
    )


# ---------- URL normalization ----------

_TRACKING_KEYS = ("utm_", "fbclid", "gclid", "_ga", "_gac", "mc_", "ref", "source")

def canonical_url(url: str) -> str:
    try:
        s = urlsplit(url)
        q = [(k, v) for (k, v) in parse_qsl(s.query, keep_blank_values=True)
             if not any(k.lower().startswith(tk) for tk in _TRACKING_KEYS)]
        return urlunsplit((s.scheme, s.netloc, s.path.rstrip("/") or "/", urlencode(q), ""))
    except Exception:
        return (url or "").strip()

# ---------- Search (DuckDuckGo HTML) ----------

async def web_search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    DuckDuckGo HTML search (no API key).
    Returns: [{title, url, snippet, source='duckduckgo', rank}, ...]
    """
    results: List[Dict[str, Any]] = []
    params = {"q": query, "kl": "us-en"}
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ModelCardGenerator/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers, connector=_default_connector()) as session:
            async with session.get("https://html.duckduckgo.com/html/", params=params) as r:
                if r.status != 200:
                    logger.warning("DuckDuckGo returned %s for %r", r.status, query)
                    return results
                html = await r.text()
                soup = BeautifulSoup(html, "html.parser")
                # ddg html sometimes uses result__a; keep a lenient selector as fallback
                links = soup.select("a.result__a") or soup.select("a[href]")
                rank = 0
                seen: set[str] = set()
                for a in links:
                    title = (a.get_text(strip=True) or "").strip()
                    href = canonical_url(a.get("href", ""))
                    if not title or not href or href in seen:
                        continue
                    # best-effort snippet
                    snip_el = a.find_next_sibling(class_="result__snippet")
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
                    if len(results) >= max_results:
                        break
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
        pages = []
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
            kind = "html"
            text = ""
            if "pdf" in ct or u.lower().endswith(".pdf"):
                text = _extract_pdf_text(raw)
                kind = "pdf"
            else:
                try:
                    html = raw.decode(r.charset or "utf-8", errors="ignore")
                except Exception:
                    html = raw.decode("utf-8", errors="ignore")
                text = _extract_html_text(html, u)
            return {"url": u, "status": r.status, "type": kind, "text": text}
    except Exception as e:
        return {"url": u, "status": 0, "type": "error", "error": str(e), "text": ""}

async def fetch_many(urls: List[str], *, concurrency: int = 6) -> List[Dict[str, Any]]:
    """
    Fetch a list of URLs with retries + backoff.
    Returns: [{url, status, type: 'html'|'pdf'|'error', text, error?}, ...]
    """
    sem = asyncio.Semaphore(concurrency)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ModelCardGenerator/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)

    async with aiohttp.ClientSession(timeout=timeout, headers=headers, connector=_default_connector()) as session:
        async def _task(u: str):
            async with sem:
                # naive retry on transient statuses
                for attempt in range(3):
                    res = await _fetch_one(session, u)
                    if res.get("status", 0) in (0, 408, 429, 500, 502, 503, 504):
                        await asyncio.sleep(0.6 * (2 ** attempt))
                        continue
                    return res
                return res
        return await asyncio.gather(*[_task(u) for u in urls])

# ---------- Discovery helpers (queries + fetch) ----------

async def discover_model_sources(model_name: str, developer: str = "") -> List[Dict[str, Any]]:
    """
    Run several targeted queries and return de-duplicated search results.
    """
    queries = [
        f"{model_name} official site",
        f"{model_name} documentation",
        f"{model_name} dermatology AI",
        f"{model_name} paper",
        f"{developer} {model_name} AI" if developer else f"{model_name} publication",
    ]
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

async def discover_and_fetch(model_name: str, developer: str = "", top_k: int = 5
                             ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Convenience: discover sources then fetch the top_k to get clean text.
    Returns (discovered_list, seed_pages_with_text)
    """
    discovered = await discover_model_sources(model_name, developer)
    urls = [s["url"] for s in discovered[:top_k] if s.get("url")]
    pages = []
    if urls:
        fetched = await fetch_many(urls, concurrency=6)
        pages = [{"url": r["url"], "text": r.get("text", "")} for r in fetched if (r.get("text") or "").strip()]
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
