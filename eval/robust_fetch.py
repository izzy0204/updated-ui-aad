"""
Shared, bot-resistant URL-fetching helper for the eval pipeline.

Both `eval/SourceCheckup/utils.py::extract_contents_from_url` (used by
`run_custom_factscore_ui_cards.py` to build FactScore corpora) and
`run_sourcecheckup_batch.py`'s own `fetch_html_text` used a bare
`requests.get` with no, or minimal ("Mozilla/5.0" only), headers. Several
vendor sites (e.g. dermasensor.com) reject that outright with HTTP 403,
which silently degrades scores (the citation gets marked UNSUPPORTED because
the source could never be fetched, not because it doesn't support the
claim).

This module adds two tiers, mirroring what the main app's
`src/scrapers/robust_scraper_v2.py` already does for the live pipeline:
  1. A realistic desktop-browser header set for a plain `requests` fetch.
  2. A headless-Chrome (Selenium) fallback, used only when the plain fetch
     fails or returns too little text.
"""

from __future__ import annotations

import atexit
import re
import tempfile
import os

import requests
from bs4 import BeautifulSoup

try:
    from readability import Document
    _HAVE_READABILITY = True
except ImportError:
    _HAVE_READABILITY = False

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",  # no "br": requests can't decode Brotli without an extra package
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

REQUEST_TIMEOUT = 30
MIN_TEXT_LEN_FOR_SUCCESS = 200


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _html_to_text(html: str) -> str:
    if _HAVE_READABILITY:
        try:
            html = Document(html).summary()
        except Exception:
            pass
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return _clean(soup.get_text(separator="\n"))


def is_pdf_url(url: str) -> bool:
    return ".pdf" in url.lower()


def _fetch_pdf_via_requests(url: str) -> str:
    from pdfminer.high_level import extract_text

    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name
    try:
        return _clean(extract_text(tmp_path))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _fetch_html_via_requests(url: str) -> str:
    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return _html_to_text(resp.text)


_selenium_driver = None


def _get_selenium_driver():
    global _selenium_driver
    if _selenium_driver is not None:
        return _selenium_driver

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"user-agent={BROWSER_HEADERS['User-Agent']}")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    _selenium_driver = driver
    return driver


def _fetch_html_via_selenium(url: str) -> str:
    import time

    driver = _get_selenium_driver()
    driver.get(url)
    time.sleep(1.5)  # let obvious client-side rendering settle
    return _html_to_text(driver.page_source)


def close_selenium_driver() -> None:
    global _selenium_driver
    if _selenium_driver is not None:
        try:
            _selenium_driver.quit()
        except Exception:
            pass
        _selenium_driver = None


atexit.register(close_selenium_driver)


def fetch_url_text(url: str) -> str:
    """
    Fetch a URL's visible text. HTML pages try a plain, browser-headered
    request first and fall back to headless Chrome (Selenium) only if that
    fails or returns suspiciously little text (a common sign of a bot block
    or a JS-rendered page). PDFs are extracted directly; Selenium doesn't
    apply to them.
    """
    if is_pdf_url(url):
        return _fetch_pdf_via_requests(url)

    try:
        text = _fetch_html_via_requests(url)
        if len(text) >= MIN_TEXT_LEN_FOR_SUCCESS:
            return text
    except Exception:
        text = ""

    try:
        selenium_text = _fetch_html_via_selenium(url)
        if len(selenium_text) > len(text):
            return selenium_text
    except Exception:
        pass

    return text
