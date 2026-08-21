#!/usr/bin/env python3
"""
Build a full-text SourceCheckup corpus for eval-3 model cards.

PURPOSE
-------
Replace live OpenAI websearch during SourceCheckup with a pre-fetched local
corpus that contains *all* extractable text from every cited / listed URL —
including content that was never quoted on the card (menus, tabs, dropdowns,
lazy-loaded scroll regions, PDFs, etc.).

This script does NOT modify the card-generator scrapers. It imports
``RobustWebScraper`` from ``src/scrapers/robust_scraper_v2.py`` and copies /
extends patterns (Selenium expansions, full-body text, wall logging) in this
file only.

HOW TO RUN
----------
From the repo root (with GEMINI_API_KEY or GOOGLE_API_KEY in ``.env``):

  # Smoke test (3 URLs, no Gemini HTML pass)
  python scripts/build_eval3_source_corpus.py --smoke

  # Full eval-3 corpus
  python scripts/build_eval3_source_corpus.py

  # Limit / resume / skip Gemini
  python scripts/build_eval3_source_corpus.py --limit 20 --no-gemini
  python scripts/build_eval3_source_corpus.py --resume

OUTPUTS (default: eval/sourcecheckup_corpus_eval3/)
---------------------------------------------------
  corpus.jsonl
      One JSON object per unique URL. Primary fields for future SourceCheckup:
        - url, final_url, title, text, text_length
        - status: success | wall | empty
        - fetch_methods: list of methods tried (robust_scraper, selenium_deep, gemini_html, pdf, …)
        - wall_category / wall_detail when status != success
        - cards: which eval-3 card files referenced this URL
        - content_type, fetched_at, diagnostics
      Use ``text`` as the source document body instead of OpenAI websearch.

  corpus_factscore.jsonl
      Drop-in compatible with existing FactScore helpers:
        {"title": "<url>", "text": "<full text>"}
      (successful docs only)

  walls.jsonl
      Every hard stop / failure for later triage:
        cookies, human_verification, empty_extract, http_4xx, http_5xx,
        paywall, pdf_extract_failed, timeout, robots, selenium_unavailable,
        network_error, unknown

  urls_manifest.json
      Deduped URL list with provenance (source files).

  run_summary.json
      Counts and paths from this run.

URL SOURCES
-----------
  - src/core/pages/preloaded_cards_eval3/*.citations.json
  - src/core/pages/preloaded_cards_eval3/*.clinical.md
  - eval/ui_cards_eval3/*.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Paths / env
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
EVAL_DIR = REPO_ROOT / "eval"
DEFAULT_OUT_DIR = EVAL_DIR / "sourcecheckup_corpus_eval3"
PRELOADED = SRC_DIR / "core" / "pages" / "preloaded_cards_eval3"
UI_CARDS = EVAL_DIR / "ui_cards_eval3"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(EVAL_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("eval3_corpus")

MIN_TEXT_OK = 120
MIN_TEXT_GOOD = 400
# Standard URLs (no spaces). Separately catch PDF/HTML paths that contain spaces.
URL_RE = re.compile(r"https?://[^\s\)\]\>\"\'\<]+", re.I)
# e.g. .../PD1123_Digital Practice.pdf in markdown reference lists
URL_WITH_SPACES_RE = re.compile(
    r"https?://[^\s\)\]\>\"\'\<]+(?:\s+[^\s\)\]\>\"\'\<]+)+?\.(?:pdf|html?|aspx?)",
    re.I,
)

COOKIE_PATTERNS = [
    r"accept\s*(all\s*)?cookies",
    r"agree\s*(and\s*)?continue",
    r"i\s*agree",
    r"got\s*it",
    r"allow\s*(all\s*)?cookies",
    r"accept\s*all",
    r"consent",
    r"continue\s*without",
    r"reject\s*(optional|non-essential)?",
]
COOKIE_RE = re.compile("|".join(COOKIE_PATTERNS), re.I)

HUMAN_VERIFY_RE = re.compile(
    r"(captcha|cloudflare|are you a (human|robot)|verify you are human|"
    r"access denied|attention required|challenge-platform|"
    r"please enable cookies|bot detection)",
    re.I,
)
PAYWALL_RE = re.compile(
    r"(subscribe to (continue|read)|paywall|sign in to (continue|read)|"
    r"create an account to|purchase this article|institutional access)",
    re.I,
)


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------

def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def gemini_api_key() -> str:
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    ).strip()


# ---------------------------------------------------------------------------
# URL collection
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    u = (url or "").strip().rstrip(".,;:)")
    # Strip markdown trailing punctuation / anchors that are clearly broken
    if u.endswith("]"):
        u = u[:-1]
    # Encode literal spaces (common in poorly escaped PDF links in markdown)
    if " " in u:
        try:
            from urllib.parse import urlsplit, urlunsplit, quote

            parts = urlsplit(u)
            path = quote(parts.path, safe="/%")
            u = urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
        except Exception:
            u = u.replace(" ", "%20")
    return u


def _add_url(
    store: Dict[str, Dict[str, Any]],
    url: str,
    source_file: str,
    source_kind: str,
) -> None:
    url = _normalize_url(url)
    if not url.startswith("http"):
        return
    # Skip obvious non-documents
    low = url.lower()
    if any(low.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")):
        return
    entry = store.setdefault(
        url,
        {"url": url, "sources": [], "source_kinds": set()},
    )
    if source_file not in entry["sources"]:
        entry["sources"].append(source_file)
    entry["source_kinds"].add(source_kind)


def collect_urls_from_citations(path: Path, store: Dict[str, Dict[str, Any]]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    rel = str(path.relative_to(REPO_ROOT))

    meta = data.get("_sources_metadata") or {}
    if isinstance(meta, dict):
        for u in meta:
            _add_url(store, u, rel, "citations_metadata")

    refs = data.get("references") or {}
    if isinstance(refs, dict):
        for ref in refs.values():
            if isinstance(ref, dict) and ref.get("url"):
                _add_url(store, ref["url"], rel, "citations_references")

    for key, val in data.items():
        if key.startswith("_") or key in ("schema_version", "references", "field_citations"):
            continue
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and item.get("url"):
                    _add_url(store, item["url"], rel, "citations_field")


def collect_urls_from_markdown(path: Path, store: Dict[str, Dict[str, Any]]) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    rel = str(path.relative_to(REPO_ROOT))
    # Prefer space-tolerant matches first so we don't keep truncated PDF stems
    spaced = list(URL_WITH_SPACES_RE.findall(text))
    for m in spaced:
        _add_url(store, m, rel, "markdown")
    spaced_norm = {_normalize_url(m) for m in spaced}
    for m in URL_RE.findall(text):
        nu = _normalize_url(m)
        # Skip stubs that are prefixes of a space-containing URL we already kept
        if any(s.startswith(nu) and s != nu for s in spaced_norm):
            continue
        _add_url(store, m, rel, "markdown")


def collect_all_eval3_urls() -> Dict[str, Dict[str, Any]]:
    store: Dict[str, Dict[str, Any]] = {}
    if PRELOADED.is_dir():
        for p in sorted(PRELOADED.glob("*.citations.json")):
            collect_urls_from_citations(p, store)
        for p in sorted(PRELOADED.glob("*.clinical.md")):
            collect_urls_from_markdown(p, store)
    if UI_CARDS.is_dir():
        for p in sorted(UI_CARDS.glob("*.md")):
            collect_urls_from_markdown(p, store)
    # JSON-serialize friendly
    for entry in store.values():
        entry["source_kinds"] = sorted(entry["source_kinds"])
    return store


# ---------------------------------------------------------------------------
# Wall classification
# ---------------------------------------------------------------------------

def classify_wall(
    *,
    http_status: Optional[int],
    text: str,
    error: Optional[str],
    page_html: str = "",
) -> Tuple[Optional[str], str]:
    """Return (wall_category, detail) or (None, '') if no wall."""
    err = (error or "").lower()
    blob = f"{text}\n{page_html[:4000]}\n{error or ''}"

    if http_status == 404 or "404" in err or "not found" in err:
        return "http_4xx", f"HTTP {http_status or '404'}: {error or 'not found'}"
    if http_status in (401, 403) or "403" in err or "401" in err or "forbidden" in err:
        return "http_4xx", f"HTTP {http_status or '403'}: {error or 'forbidden'}"
    if http_status is not None and http_status >= 500:
        return "http_5xx", f"HTTP {http_status}: {error or ''}"
    if "timeout" in err or "timed out" in err:
        return "timeout", error or "timeout"
    if "robot" in err and "disallow" in err:
        return "robots", error or "robots.txt"
    if HUMAN_VERIFY_RE.search(blob):
        return "human_verification", "Captcha / Cloudflare / bot check signals in page"
    if COOKIE_RE.search(blob) and len(text.strip()) < MIN_TEXT_GOOD:
        return "cookies", "Cookie/consent wall suspected (little content after fetch)"
    if PAYWALL_RE.search(blob) and len(text.strip()) < MIN_TEXT_GOOD:
        return "paywall", "Paywall / login-to-read signals"
    if error and "pdf" in err:
        return "pdf_extract_failed", error
    if error and ("network" in err or "connection" in err or "ssl" in err):
        return "network_error", error
    if error:
        return "unknown", error
    if len(text.strip()) < MIN_TEXT_OK:
        return "empty_extract", f"Extracted only {len(text.strip())} chars"
    return None, ""


# ---------------------------------------------------------------------------
# Full-page HTML → text (keep menus / details; do NOT strip nav)
# ---------------------------------------------------------------------------

def html_to_full_text(html: str) -> str:
    """Extract as much visible text as possible, including nav / details."""
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg", "canvas", "iframe"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Expand <details> textually (keep summary + body)
    for details in soup.find_all("details"):
        summary = details.find("summary")
        label = summary.get_text(" ", strip=True) if summary else "details"
        body = details.get_text(" ", strip=True)
        details.replace_with(f"\n[DETAILS: {label}] {body}\n")

    body = soup.find("body") or soup
    text = body.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def merge_texts(*parts: str) -> str:
    """Prefer longest unique content; concatenate when complementary."""
    cleaned = [re.sub(r"\s+", " ", (p or "").strip()) for p in parts if (p or "").strip()]
    if not cleaned:
        return ""
    # Start with longest, append others that add substantial new content
    cleaned.sort(key=len, reverse=True)
    base = cleaned[0]
    for other in cleaned[1:]:
        if len(other) < 80:
            continue
        # Rough novelty: if less than half of other appears in base, append
        sample = other[: min(200, len(other))]
        if sample not in base:
            base = base + "\n\n---\n\n" + other
    return base.strip()


# ---------------------------------------------------------------------------
# Deep Selenium (copied/extended patterns; lives only in this script)
# ---------------------------------------------------------------------------

def selenium_deep_extract(url: str, max_scrolls: int = 8) -> Dict[str, Any]:
    """
    Headless Chrome pass that tries harder than the stock selenium_scraper:
    dismiss cookie banners, open details/summary, click common tab roles,
    scroll lazy regions, then dump full body text (menus included).
    """
    out: Dict[str, Any] = {
        "status": "failed",
        "text": "",
        "html": "",
        "title": "",
        "error": None,
        "diagnostics": {},
    }
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
    except ImportError as e:
        out["error"] = f"selenium_unavailable: {e}"
        out["diagnostics"]["wall_hint"] = "selenium_unavailable"
        return out

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # Unique profile per invocation so parallel/aborted runs don't collide
    import tempfile as _tempfile
    import uuid as _uuid

    _profile = _tempfile.mkdtemp(
        prefix=f"eval3_chrome_{os.getpid()}_{_uuid.uuid4().hex[:8]}_"
    )
    options.add_argument(f"--user-data-dir={_profile}")
    options.add_argument("--remote-debugging-port=0")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception:
            driver = webdriver.Chrome(options=options)

        driver.set_page_load_timeout(45)
        driver.get(url)
        time.sleep(1.5)

        # Cookie / consent buttons
        clicked_cookies = 0
        try:
            candidates = driver.find_elements(By.CSS_SELECTOR, "button, a, [role='button']")
            for el in candidates[:80]:
                try:
                    label = (el.text or el.get_attribute("aria-label") or "").strip()
                    if label and COOKIE_RE.search(label) and el.is_displayed():
                        el.click()
                        clicked_cookies += 1
                        time.sleep(0.4)
                        if clicked_cookies >= 3:
                            break
                except Exception:
                    continue
        except Exception:
            pass
        out["diagnostics"]["cookie_clicks"] = clicked_cookies

        # Open <details>
        try:
            for det in driver.find_elements(By.CSS_SELECTOR, "details:not([open])"):
                try:
                    driver.execute_script("arguments[0].open = true;", det)
                except Exception:
                    continue
        except Exception:
            pass

        # Tabs / accordions (role=tab, aria-expanded=false)
        expanded = 0
        try:
            for el in driver.find_elements(
                By.CSS_SELECTOR,
                "[role='tab'], button[aria-expanded='false'], "
                ".accordion-button, [data-toggle='tab'], [data-bs-toggle='tab']",
            )[:40]:
                try:
                    if el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
                        expanded += 1
                        time.sleep(0.25)
                except Exception:
                    continue
        except Exception:
            pass
        out["diagnostics"]["expanded_controls"] = expanded

        # Scroll for lazy content
        scrolls = 0
        try:
            last_h = 0
            for _ in range(max_scrolls):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.55)
                h = driver.execute_script("return document.body.scrollHeight") or 0
                scrolls += 1
                if h <= last_h:
                    break
                last_h = h
            driver.execute_script("window.scrollTo(0, 0);")
        except Exception:
            pass
        out["diagnostics"]["scrolls"] = scrolls

        html = driver.page_source or ""
        title = ""
        try:
            title = driver.title or ""
        except Exception:
            pass
        # Prefer live body.innerText (includes opened menus) then soup fallback
        try:
            live = driver.execute_script(
                "return document.body ? (document.body.innerText || '') : '';"
            ) or ""
        except Exception:
            live = ""
        soup_text = html_to_full_text(html)
        text = merge_texts(live, soup_text)

        out["html"] = html
        out["title"] = title
        out["text"] = text
        out["status"] = "success" if len(text.strip()) >= MIN_TEXT_OK else "empty"
        if out["status"] == "empty":
            out["error"] = f"selenium_deep returned {len(text.strip())} chars"
    except Exception as e:
        out["error"] = f"selenium_deep: {e}"
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        try:
            import shutil

            shutil.rmtree(_profile, ignore_errors=True)
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# PDF fallback (does not patch robust_scraper_v2; copies eval/robust_fetch pattern)
# ---------------------------------------------------------------------------

def fetch_pdf_text_fallback(url: str) -> Dict[str, Any]:
    """Direct PDF download + pypdf/pdfminer extract when RobustWebScraper PDF path fails."""
    import tempfile

    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,*/*",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=90)
        resp.raise_for_status()
        data = resp.content
    except Exception as e:
        return {"text": "", "error": f"pdf_download_failed: {e}"}

    text = ""
    err = None
    # Prefer pypdf
    try:
        from io import BytesIO

        import pypdf

        reader = pypdf.PdfReader(BytesIO(data))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(parts).strip()
    except Exception as e:
        err = f"pypdf: {e}"

    if len(text) < MIN_TEXT_OK:
        try:
            from pdfminer.high_level import extract_text as pdfminer_extract

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                text2 = (pdfminer_extract(tmp_path) or "").strip()
                if len(text2) > len(text):
                    text = text2
                    err = None
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        except Exception as e:
            err = f"{err}; pdfminer: {e}" if err else f"pdfminer: {e}"

    if len(text) >= MIN_TEXT_OK:
        return {"text": text, "error": None}
    return {"text": text, "error": err or "pdf_extract_empty"}


# ---------------------------------------------------------------------------
# Gemini HTML rescue (optional)
# ---------------------------------------------------------------------------

def gemini_extract_from_html(html: str, url: str, model: str) -> Dict[str, Any]:
    """Ask Gemini to pull all readable text from truncated HTML."""
    key = gemini_api_key()
    if not key:
        return {"text": "", "error": "no_gemini_key"}

    # Cap HTML to keep request size sane
    snippet = html[:120_000]
    prompt = f"""Extract ALL human-readable text from this HTML page.
Include navigation labels, menu items, tab labels, dropdown options, footnotes,
tables, and footer text. Exclude raw CSS/JS. Preserve reading order roughly.
Return plain text only (no markdown fences).

URL: {url}

HTML:
{snippet}
"""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0),
        )
        raw = (getattr(response, "text", None) or "").strip()
        if not raw and getattr(response, "candidates", None):
            try:
                parts = response.candidates[0].content.parts
                raw = "".join((getattr(p, "text", None) or "") for p in parts).strip()
            except Exception:
                raw = ""
        return {"text": raw, "error": None if raw else "empty_gemini_response"}
    except Exception as e:
        return {"text": "", "error": f"gemini_failed: {e}"}


# ---------------------------------------------------------------------------
# Per-URL pipeline
# ---------------------------------------------------------------------------

async def fetch_one_url(
    url: str,
    *,
    use_selenium: bool = True,
    use_gemini: bool = True,
    gemini_model: str = "gemini-2.5-flash",
    second_hop: bool = False,
) -> Dict[str, Any]:
    from scrapers.robust_scraper_v2 import RobustWebScraper

    methods: List[str] = []
    texts: List[str] = []
    title = ""
    final_url = url
    content_type = ""
    http_status: Optional[int] = None
    error: Optional[str] = None
    html_for_gemini = ""
    diagnostics: Dict[str, Any] = {}

    # 1) Robust scraper (HTML + PDF + optional stock Selenium fallback inside)
    try:
        async with RobustWebScraper() as scraper:
            if second_hop:
                result = await scraper.extract_content_with_second_hop(url)
            else:
                result = await scraper.extract_content_from_url(url)
        methods.append("robust_scraper")
        if result.get("diagnostics", {}).get("selenium_fallback_used"):
            methods.append("robust_selenium_fallback")
        status = result.get("status")
        title = result.get("title") or title
        final_url = result.get("final_url") or final_url
        content_type = result.get("content_type") or content_type
        diagnostics["robust"] = {
            "status": status,
            "error": result.get("error"),
            "diag": result.get("diagnostics") or {},
        }
        clean = (result.get("clean_text") or "").strip()
        if clean:
            texts.append(clean)

        # Prefer full HTML body when available (menus etc. that trafilatura drops)
        raw_html = result.get("raw_html_truncated") or ""
        if raw_html:
            html_for_gemini = raw_html
            full = html_to_full_text(raw_html)
            if full:
                texts.append(full)
                methods.append("full_html_body")

        if status == "failed":
            error = result.get("error") or error
            # Try to pull HTTP code from diagnostics if present
            d = result.get("diagnostics") or {}
            if isinstance(d.get("status_code"), int):
                http_status = d["status_code"]
    except Exception as e:
        error = f"robust_scraper_exception: {e}"
        diagnostics["robust_exception"] = str(e)

    # 1b) PDF fallback when robust scraper fails on PDFs (known upstream io bug)
    is_pdf = ".pdf" in url.lower() or "application/pdf" in (content_type or "").lower()
    if is_pdf and len(merge_texts(*texts)) < MIN_TEXT_OK:
        pdf = await asyncio.to_thread(fetch_pdf_text_fallback, url)
        methods.append("pdf_fallback")
        diagnostics["pdf_fallback"] = {"error": pdf.get("error"), "chars": len(pdf.get("text") or "")}
        if pdf.get("text"):
            texts.append(pdf["text"])
            error = None
        elif pdf.get("error"):
            error = pdf["error"]

    merged = merge_texts(*texts)

    # 2) Deep Selenium when short / JS-ish / known hard domains
    needs_deep = use_selenium and (
        len(merged) < MIN_TEXT_GOOD
        or any(
            d in url.lower()
            for d in (
                "dermgpt.com",
                "skinvision.com",
                "dermasensor.com",
                "forus.com",
                "withtandem.com",
                "linkedin.com",
            )
        )
    )
    if needs_deep and not is_pdf:
        deep = await asyncio.to_thread(selenium_deep_extract, url)
        methods.append("selenium_deep")
        diagnostics["selenium_deep"] = {
            k: v for k, v in deep.items() if k != "html"
        }
        if deep.get("html"):
            html_for_gemini = deep["html"] or html_for_gemini
        if deep.get("title"):
            title = title or deep["title"]
        if deep.get("text"):
            texts.append(deep["text"])
            merged = merge_texts(*texts)
        if deep.get("error") and not merged:
            error = deep["error"] or error
            if "selenium_unavailable" in (deep.get("error") or ""):
                diagnostics["wall_hint"] = "selenium_unavailable"

    # 3) Gemini HTML rescue when still thin but we have HTML
    if use_gemini and len(merged) < MIN_TEXT_GOOD and html_for_gemini and ".pdf" not in url.lower():
        g = await asyncio.to_thread(gemini_extract_from_html, html_for_gemini, url, gemini_model)
        methods.append("gemini_html")
        diagnostics["gemini"] = {"error": g.get("error"), "chars": len(g.get("text") or "")}
        if g.get("text"):
            texts.append(g["text"])
            merged = merge_texts(*texts)
        elif g.get("error") and not merged:
            error = error or g["error"]

    merged = merge_texts(*texts)
    wall_cat, wall_detail = classify_wall(
        http_status=http_status,
        text=merged,
        error=error,
        page_html=html_for_gemini,
    )

    # Enough real text wins over transient upstream errors (e.g. robust_scraper
    # UnboundLocalError on json_ld after Selenium already extracted content).
    if len(merged) >= MIN_TEXT_GOOD:
        soft_walls = {
            None,
            "empty_extract",
            "cookies",
            "unknown",
            "network_error",
            "selenium_unavailable",
        }
        if wall_cat in soft_walls or (
            wall_cat == "unknown"
            and error
            and "json_ld" in error
        ):
            status_out = "success"
            wall_cat, wall_detail = None, ""
        elif wall_cat in ("human_verification", "paywall"):
            # Keep as wall even with some text — body may be interstitial only
            status_out = "wall"
        else:
            status_out = "success"
            wall_cat, wall_detail = None, ""
    elif len(merged) >= MIN_TEXT_OK and wall_cat in (None, "empty_extract", "cookies", "unknown"):
        status_out = "success"
        if wall_cat == "cookies" and len(merged) < MIN_TEXT_GOOD:
            status_out = "wall"
        else:
            wall_cat, wall_detail = None, ""
    elif wall_cat:
        status_out = "wall"
    elif merged:
        status_out = "success"
        wall_cat, wall_detail = None, ""
    else:
        status_out = "empty"
        wall_cat = wall_cat or "empty_extract"
        wall_detail = wall_detail or "no text extracted"

    return {
        "url": url,
        "final_url": final_url,
        "title": title,
        "text": merged,
        "text_length": len(merged),
        "status": status_out,
        "fetch_methods": methods,
        "wall_category": wall_cat,
        "wall_detail": wall_detail,
        "content_type": content_type,
        "http_status": http_status,
        "error": error,
        "diagnostics": diagnostics,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    n = 0
    with open(tmp, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    tmp.replace(path)
    return n


def load_done_urls(corpus_path: Path) -> Set[str]:
    done: Set[str] = set()
    if not corpus_path.is_file():
        return done
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            done.add(json.loads(line)["url"])
        except Exception:
            continue
    return done


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> int:
    load_env_file(REPO_ROOT / ".env")
    load_env_file(EVAL_DIR / ".env")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    url_store = collect_all_eval3_urls()
    urls = sorted(url_store.keys())
    if args.only_url:
        urls = [u for u in urls if u == args.only_url]
    if args.smoke:
        # Prefer a mix: HTML homepage + PDF if present
        htmls = [u for u in urls if ".pdf" not in u.lower()]
        pdfs = [u for u in urls if ".pdf" in u.lower()]
        pick = (htmls[:2] + pdfs[:1]) or urls[:3]
        urls = pick[: max(1, args.limit or 3)]
    elif args.limit:
        urls = urls[: args.limit]

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_unique_urls_all": len(url_store),
        "n_urls_this_run": len(urls),
        "urls": [
            {
                "url": u,
                "cards": url_store[u]["sources"],
                "source_kinds": url_store[u]["source_kinds"],
            }
            for u in urls
        ],
    }
    (out_dir / "urls_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Manifest: %d URLs this run (%d total unique in eval-3)", len(urls), len(url_store))

    corpus_path = out_dir / "corpus.jsonl"
    walls_path = out_dir / "walls.jsonl"
    factscore_path = out_dir / "corpus_factscore.jsonl"

    done: Set[str] = set()
    existing_rows: List[Dict[str, Any]] = []
    retry_failed = bool(getattr(args, "retry_failed", False))
    if args.resume and corpus_path.is_file():
        for i, line in enumerate(
            corpus_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning("Skipping corrupt corpus.jsonl line %d: %s", i, e)
                continue
            if retry_failed and row.get("status") != "success":
                continue
            existing_rows.append(row)
        done = {r.get("url", "") for r in existing_rows if r.get("url")}
        logger.info(
            "Resume: %d URLs kept%s",
            len(done),
            " (retrying non-success)" if retry_failed else "",
        )

    use_gemini = not args.no_gemini and bool(gemini_api_key())
    if not args.no_gemini and not gemini_api_key():
        logger.warning("No GEMINI_API_KEY/GOOGLE_API_KEY — Gemini HTML rescue disabled")

    rows: List[Dict[str, Any]] = list(existing_rows)
    walls: List[Dict[str, Any]] = []
    if walls_path.is_file() and args.resume and not retry_failed:
        for line in walls_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                walls.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    for i, url in enumerate(urls, 1):
        if url in done:
            logger.info("[%d/%d] SKIP (resume) %s", i, len(urls), url)
            continue
        logger.info("[%d/%d] FETCH %s", i, len(urls), url)
        try:
            doc = await fetch_one_url(
                url,
                use_selenium=not args.no_selenium,
                use_gemini=use_gemini,
                gemini_model=args.gemini_model,
                second_hop=args.second_hop,
            )
        except Exception as e:
            doc = {
                "url": url,
                "final_url": url,
                "title": "",
                "text": "",
                "text_length": 0,
                "status": "wall",
                "fetch_methods": [],
                "wall_category": "unknown",
                "wall_detail": str(e),
                "content_type": "",
                "http_status": None,
                "error": str(e),
                "diagnostics": {},
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        doc["cards"] = url_store.get(url, {}).get("sources", [])
        doc["source_kinds"] = url_store.get(url, {}).get("source_kinds", [])
        rows.append(doc)

        if doc["status"] != "success" or doc.get("wall_category"):
            walls.append(
                {
                    "url": url,
                    "wall_category": doc.get("wall_category") or "unknown",
                    "wall_detail": doc.get("wall_detail") or doc.get("error") or "",
                    "status": doc.get("status"),
                    "text_length": doc.get("text_length", 0),
                    "fetch_methods": doc.get("fetch_methods"),
                    "cards": doc.get("cards"),
                    "fetched_at": doc.get("fetched_at"),
                }
            )
            logger.warning(
                "  WALL [%s] %s (%s chars)",
                doc.get("wall_category"),
                doc.get("wall_detail"),
                doc.get("text_length"),
            )
        else:
            logger.info(
                "  OK %s chars via %s",
                doc.get("text_length"),
                ",".join(doc.get("fetch_methods") or []),
            )

        # Checkpoint after each URL so long runs are resumable
        write_jsonl(corpus_path, rows)
        write_jsonl(walls_path, walls)
        write_jsonl(
            factscore_path,
            [
                {"title": r["url"], "text": r["text"]}
                for r in rows
                if r.get("status") == "success" and r.get("text")
            ],
        )

    n_ok = sum(1 for r in rows if r.get("status") == "success")
    n_wall = sum(1 for r in rows if r.get("status") == "wall")
    n_empty = sum(1 for r in rows if r.get("status") == "empty")
    summary = {
        "out_dir": str(out_dir),
        "corpus_jsonl": str(corpus_path),
        "corpus_factscore_jsonl": str(factscore_path),
        "walls_jsonl": str(walls_path),
        "urls_manifest": str(out_dir / "urls_manifest.json"),
        "n_docs": len(rows),
        "n_success": n_ok,
        "n_wall": n_wall,
        "n_empty": n_empty,
        "n_walls_log": len(walls),
        "use_gemini": use_gemini,
        "gemini_model": args.gemini_model if use_gemini else None,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    logger.info("Done. success=%d wall=%d empty=%d → %s", n_ok, n_wall, n_empty, out_dir)
    return 0


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Build full-text SourceCheckup corpus for eval-3 cards (no edits to original scrapers)."
    )
    ap.add_argument(
        "--out-dir",
        type=str,
        default=str(DEFAULT_OUT_DIR),
        help=f"Output directory (default: {DEFAULT_OUT_DIR})",
    )
    ap.add_argument("--limit", type=int, default=None, help="Max URLs to fetch this run")
    ap.add_argument("--smoke", action="store_true", help="Fetch a tiny mixed sample (HTML+PDF)")
    ap.add_argument("--resume", action="store_true", help="Skip URLs already in corpus.jsonl")
    ap.add_argument(
        "--retry-failed",
        action="store_true",
        help="With --resume, keep only status=success rows and re-fetch walls/empties",
    )
    ap.add_argument("--only-url", type=str, default=None, help="Fetch a single URL")
    ap.add_argument("--no-selenium", action="store_true", help="Skip deep Selenium pass")
    ap.add_argument("--no-gemini", action="store_true", help="Skip Gemini HTML rescue")
    ap.add_argument(
        "--gemini-model",
        type=str,
        default=os.getenv("GEMINI_MODEL") or "gemini-2.5-flash",
    )
    ap.add_argument(
        "--second-hop",
        action="store_true",
        help="Also run RobustWebScraper second-hop section follow (slower)",
    )
    return ap


def main() -> None:
    args = build_argparser().parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
