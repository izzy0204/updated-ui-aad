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
from utils.cache_system import get_cache

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
    DuckDuckGo HTML search (no API key) with caching.
    Returns: [{title, url, snippet, source='duckduckgo', rank}, ...]
    """
    cache = get_cache()
    
    # Check cache first
    cached_results = await cache.get("web_search", query, max_results=max_results)
    if cached_results is not None:
        logger.info(f"Cache HIT for web search: {query}")
        return cached_results[:max_results]
    
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

    final_results = results[:max_results]
    
    # Cache the results
    await cache.set(
        "web_search", 
        query, 
        final_results,
        metadata={"max_results": max_results, "query": query},
        max_results=max_results
    )
    
    logger.info(f"Cache SET for web search: {query} ({len(final_results)} results)")
    return final_results


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

async def _fetch_one(session: aiohttp.ClientSession, url: str, timeout: float = 20.0, use_selenium_fallback: bool = True) -> Dict[str, Any]:
    cache = get_cache()
    
    # Check cache first
    cached_result = await cache.get("web_fetch", url, timeout=timeout)
    if cached_result is not None:
        logger.info(f"Cache HIT for web fetch: {url}")
        return cached_result
    
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
                
                # Check if we need Selenium fallback for JavaScript-rendered content
                if use_selenium_fallback and kind == "html" and len(text.strip()) < 200:
                    # Try Selenium if content seems too short (might be JS-rendered)
                    try:
                        from scrapers.selenium_scraper import scrape_with_selenium, SELENIUM_AVAILABLE
                        if SELENIUM_AVAILABLE:
                            logger.info(f"Trying Selenium fallback for {u} (content too short: {len(text)} chars)")
                            selenium_result = await scrape_with_selenium(u, headless=True, wait_for_content=True)
                            if selenium_result.get('status') == 'success':
                                selenium_text = selenium_result.get('clean_text', '')
                                if len(selenium_text.strip()) > len(text.strip()):
                                    text = selenium_text
                                    logger.info(f"Selenium improved content for {u} ({len(text)} vs {len(selenium_text)} chars)")
                    except ImportError:
                        pass  # Selenium not available, continue with static content
                    except Exception as e:
                        logger.debug(f"Selenium fallback failed for {u}: {e}")

            result = {"url": u, "status": r.status, "type": kind, "text": text}
            
            # Cache the result
            await cache.set(
                "web_fetch",
                url,
                result,
                url=url,
                metadata={"timeout": timeout, "content_type": ct, "status": r.status},
                timeout=timeout
            )
            
            logger.info(f"Cache SET for web fetch: {url} (status: {r.status}, type: {kind})")
            return result
            
    except Exception as e:
        error_result = {"url": u, "status": 0, "type": "error", "error": str(e), "text": ""}
        
        # Cache error results too (with shorter TTL)
        await cache.set(
            "web_fetch",
            url,
            error_result,
            url=url,
            metadata={"timeout": timeout, "error": str(e)},
            timeout=timeout
        )
        
        return error_result


async def fetch_many(urls: List[str], *, concurrency: int = 6, timeout: float = 20.0) -> List[Dict[str, Any]]:
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
                    res = await _fetch_one(session, u, timeout=timeout)
                    if res.get("status", 0) in (0, 408, 429, 500, 502, 503, 504):
                        await asyncio.sleep(0.6 * (2 ** attempt))
                        continue
                    break
                return res

        return await asyncio.gather(*[_task(u) for u in urls])


# ---------- Discovery helpers (queries + fetch) ----------

def _score_source_quality(source: Dict[str, Any], model_name: str, developer: str = "") -> float:
    """Score source quality based on relevance, official status, and content indicators."""
    score = 0.0
    title = (source.get("title") or "").lower()
    url = (source.get("url") or "").lower()
    description = (source.get("description") or "").lower()
    
    # Official status indicators (high weight)
    official_indicators = ['official', 'homepage', 'main site', 'product page', 'company']
    if any(indicator in title or indicator in url for indicator in official_indicators):
        score += 0.4
    
    # Documentation indicators
    doc_indicators = ['documentation', 'docs', 'guide', 'tutorial', 'help']
    if any(indicator in title or indicator in url for indicator in doc_indicators):
        score += 0.3
    
    # Relevance to model name
    model_lower = model_name.lower()
    if model_lower in title or model_lower in description:
        score += 0.2
    
    # Developer relevance
    if developer:
        dev_lower = developer.lower()
        if dev_lower in title or dev_lower in description:
            score += 0.1
    
    # Domain quality
    trusted_domains = ['edu', 'gov', 'org', 'pubmed', 'arxiv', 'github']
    if any(domain in url for domain in trusted_domains):
        score += 0.1
    
    return min(1.0, score)


async def discover_model_sources(model_name: str, developer: str = "") -> List[Dict[str, Any]]:
    """
    Run several targeted queries and return de-duplicated search results with caching.
    Includes source quality scoring.
    """
    cache = get_cache()
    
    # Check cache first
    cache_key = f"{model_name}_{developer}"
    cached_results = await cache.get("model_sources", cache_key)
    if cached_results is not None:
        logger.info(f"Cache HIT for model sources: {cache_key}")
        return cached_results
    
    # Always include developer when available to make searches more specific
    base_query = f"{developer} {model_name}" if developer else model_name
    
    queries = [
        f"{base_query} official site",
        f"{base_query} documentation", 
        f"{base_query} dermatology AI",
        f"{base_query} paper",
        f"{base_query} AI model",
        f"{base_query} publication",
        # Enhanced queries for missing fields
        f"{base_query} release date launch announcement",
        f"{base_query} version history changelog",
        f"{base_query} how to use tutorial guide",
        f"{base_query} limitations warnings contraindications",
        f"{base_query} training data dataset",
        f"{base_query} bias mitigation fairness equity",
        f"{base_query} safety reliability metrics",
        f"{base_query} time savings efficiency metrics",
        f"{base_query} user count adoption statistics",
        f"{base_query} maintenance updates",
        # Specialized CHAI field queries
        f"{base_query} FDA clearance regulatory approval",
        f"{base_query} clinical trial validation study",
        f"{base_query} IRB approval ethics review",
        f"{base_query} bias analysis fairness metrics",
        f"{base_query} reimbursement insurance coverage",
        f"{base_query} stakeholder consultation user research",
        # Domain-specific searches
        f"site:pubmed.ncbi.nlm.nih.gov {base_query}",
        f"site:fda.gov {base_query}",
        f"site:clinicaltrials.gov {base_query}",
        f"site:github.com {base_query}",
        f"site:arxiv.org {base_query}",
        f"site:researchgate.net {base_query}",
    ]
    
    # If no developer provided, add some fallback queries without developer
    if not developer:
        queries.extend([
            f"{model_name} official site",
            f"{model_name} documentation",
            f"{model_name} FDA clearance regulatory approval",
            f"{model_name} clinical trial validation study",
            f"{model_name} IRB approval ethics review",
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
            source = {
                "title": (h or {}).get("title", ""),
                "url": url,
                "description": (h or {}).get("snippet", ""),
                "type": "web",
                "priority_score": 5.0,
            }
            # Add quality score
            quality_score = _score_source_quality(source, model_name, developer)
            source["quality_score"] = quality_score
            # Adjust priority_score based on quality
            source["priority_score"] = 5.0 + (quality_score * 5.0)  # Scale to 5.0-10.0
            found.append(source)
    
    # Sort by priority_score (quality-weighted) and take top results
    found.sort(key=lambda x: x.get("priority_score", 5.0), reverse=True)
    final_results = found[:25]  # Take more to allow for quality filtering
    
    # Cache the results
    await cache.set(
        "model_sources",
        cache_key,
        final_results,
        model_name=model_name,
        metadata={"developer": developer, "query_count": len(queries), "found_count": len(found)},
        developer=developer
    )
    
    logger.info(f"Cache SET for model sources: {cache_key} ({len(final_results)} results)")
    return final_results


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
