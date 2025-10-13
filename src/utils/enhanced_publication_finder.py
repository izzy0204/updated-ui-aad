"""
ENHANCED PUBLICATION FINDER (Crossref + ArXiv only)

PURPOSE
- Find high-signal publications about medical/dermatology AI models without API keys.
- ArXiv (preprints) + Crossref (journal-specific queries for precision).

USAGE
async with EnhancedPublicationFinder() as finder:
    papers = await finder.comprehensive_publication_search(model_name)
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from typing import Dict, List, Any, Optional
from urllib.parse import quote_plus
from datetime import datetime

import aiohttp

from utils.net import new_session  # centralized, certifi CA, proxy-aware
from ai_extractors.ai_extractor import AIContentExtractor


class EnhancedPublicationFinder:
    """
    Publication discovery for medical AI models using:
      - ArXiv (broad CS/AI preprints)
      - Crossref with journal filters for precision:
          * bioRxiv (preprints in biology/medicine)
          * medRxiv (preprints in medicine)
          * Nature Medicine (clinical)
          * JAMA Dermatology (dermatology)
    """

    def __init__(self):
        self.ai_extractor = AIContentExtractor()
        self.session: Optional[aiohttp.ClientSession] = None
        # simple per-run AI analysis budget to avoid overcalling
        self._ai_budget = 0
        self._ai_budget_cap = 6

    # ---------------- HTTP helpers (retrying) ----------------

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        tries: int = 3,
        backoff_base: float = 0.8,
        retry_for: tuple = (408, 429, 500, 502, 503, 504),
    ) -> Optional[aiohttp.ClientResponse]:
        if self.session is None:
            raise RuntimeError("HTTP session is not initialized (use `async with EnhancedPublicationFinder()`)")
        last_exc = None
        for attempt in range(tries):
            try:
                async with self.session.request(method, url, params=params, headers=headers) as r:
                    if r.status == 200:
                        return r
                    if r.status in retry_for and attempt < tries - 1:
                        ra = r.headers.get("Retry-After")
                        try:
                            delay = float(ra) if ra else None
                        except ValueError:
                            delay = None
                        if delay is None:
                            delay = backoff_base * (2 ** attempt) + random.uniform(0.05, 0.25)
                        await asyncio.sleep(delay)
                        continue
                    print(f"HTTP {r.status} for {url}")
                    return None
            except (aiohttp.ClientConnectionError, aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
                last_exc = e
                if attempt < tries - 1:
                    delay = backoff_base * (2 ** attempt) + random.uniform(0.05, 0.25)
                    await asyncio.sleep(delay)
                    continue
                print(f"HTTP error for {url}: {e} (final attempt).")
                return None
            except aiohttp.ClientError as e:
                print(f"Client error for {url}: {e}")
                return None
        if last_exc:
            print(f"Request failed for {url}: {last_exc}")
        return None

    async def _get_json(self, url: str, **kw) -> Optional[Dict[str, Any]]:
        r = await self._request("GET", url, **kw)
        if not r:
            return None
        try:
            return await r.json()
        except Exception as e:
            print(f"JSON parse error for {url}: {e}")
            return None

    async def _get_text(self, url: str, **kw) -> Optional[str]:
        r = await self._request("GET", url, **kw)
        if not r:
            return None
        try:
            return await r.text()
        except Exception as e:
            print(f"Text read error for {url}: {e}")
            return None

    # ---------------- context manager ----------------

    async def __aenter__(self):
        # Use the shared session factory for consistent SSL/proxy/timeouts
        # We still pass lightweight headers appropriate for these APIs.
        self.session = await new_session().__aenter__()  # enter the async context of new_session
        # Attach API-specific defaults
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ModelCardGenerator/1.0)",
            "Accept": "application/json, text/xml, */*;q=0.8",
        })
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await new_session().__aexit__(exc_type, exc_val, exc_tb)  # close via the same context manager

    # ---------------- top-level searches ----------------

    async def comprehensive_publication_search(self, model_name: str) -> List[Dict[str, Any]]:
        """ArXiv + Crossref (journal-filtered). Returns up to ~15 top items."""
        all_publications: List[Dict[str, Any]] = []
        tasks = [
            self._search_arxiv_comprehensive(model_name),
            self._search_crossref_journal(model_name, "bioRxiv", rows=8, years_back=10),
            self._search_crossref_journal(model_name, "medRxiv", rows=8, years_back=10),
            self._search_crossref_journal(model_name, "Nature Medicine", rows=6, years_back=10),
            self._search_crossref_journal(model_name, "JAMA Dermatology", rows=6, years_back=10),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if not isinstance(r, Exception) and isinstance(r, list):
                all_publications.extend(r)

        unique = self._deduplicate_publications(all_publications)
        prioritized = sorted(unique, key=lambda x: x.get("relevance_score", 0), reverse=True)
        return prioritized[:15]

    async def search_multiple_databases(self, model_name: str) -> List[Dict[str, Any]]:
        """Alias for compatibility."""
        return await self.comprehensive_publication_search(model_name)

    # ---------------- Crossref (journal-filtered) ----------------

    async def _search_crossref_journal(
        self,
        model_name: str,
        journal_title: str,
        rows: int = 8,
        years_back: int = 10,
    ) -> List[Dict[str, Any]]:
        publications: List[Dict[str, Any]] = []

        # Focused query improves relevance
        query = f'{model_name} dermatology OR "skin" OR melanoma OR dermoscopy OR "computer vision" OR "deep learning"'

        # Date filter (YYYY-01-01 from {current_year - years_back})
        from_year = max(1900, datetime.utcnow().year - years_back)
        from_pub_date = f"{from_year}-01-01"

        params = {
            "query": query,
            "rows": str(rows),
            "sort": "score",
            "order": "desc",
            "select": "DOI,title,author,container-title,issued,URL,abstract",
            "filter": f"from-pub-date:{from_pub_date},container-title:{journal_title}",
        }
        url = "https://api.crossref.org/works"

        data = await self._get_json(url, params=params)
        if not data:
            return publications

        items = (data.get("message") or {}).get("items") or []
        for it in items:
            try:
                title_list = it.get("title") or []
                title = title_list[0].strip() if title_list else ""
                if not title:
                    continue

                # authors
                authors = []
                for a in it.get("author") or []:
                    given = (a.get("given") or "").strip()
                    family = (a.get("family") or "").strip()
                    nm = (f"{given} {family}").strip()
                    if nm:
                        authors.append(nm)

                # issued date
                issued = it.get("issued", {})
                date_parts = (issued.get("date-parts") or [[None, None, None]])[0]
                year = str(date_parts[0]) if len(date_parts) > 0 and date_parts[0] else ""
                try:
                    month = f"-{int(date_parts[1]):02d}" if len(date_parts) > 1 and date_parts[1] and str(date_parts[1]).isdigit() else ""
                except (ValueError, TypeError):
                    month = ""
                try:
                    day = f"-{int(date_parts[2]):02d}" if len(date_parts) > 2 and date_parts[2] and str(date_parts[2]).isdigit() else ""
                except (ValueError, TypeError):
                    day = ""
                published_date = f"{year}{month}{day}"

                url_item = it.get("URL") or ""
                doi = (it.get("DOI") or "").strip()
                doi_url = f"https://doi.org/{doi}" if doi else ""

                # abstract (strip tags)
                abstract_raw = it.get("abstract") or ""
                abstract = re.sub(r"<[^>]+>", " ", abstract_raw).strip() if abstract_raw else ""

                content_for_analysis = f"{title} {abstract}".strip()

                # quick relevance gate + budget
                kw = ("dermatology", "skin", "melanoma", "dermoscop", "clinical", model_name.lower())
                should_analyze = content_for_analysis and any(k in content_for_analysis.lower() for k in kw)

                ai_analysis: Dict[str, Any] = {}
                if should_analyze and self._ai_budget < self._ai_budget_cap:
                    ai_analysis = self.ai_extractor.extract_model_information(
                        content_for_analysis, "crossref_publication"
                    )
                    self._ai_budget += 1

                pub: Dict[str, Any] = {
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "journal": journal_title,
                    "pmid": "",
                    "doi": doi,
                    "url": url_item or doi_url,
                    "doi_url": doi_url,
                    "published_date": published_date,
                    "categories": [],
                    "type": "crossref_publication",
                    "ai_analysis": ai_analysis,
                    "extracted_content": content_for_analysis,
                    "relevance_score": self._calculate_publication_relevance(title, abstract, [], [], model_name),
                }
                publications.append(pub)
            except Exception as e:
                print(f"Crossref parse error: {e}")
                continue

        return publications

    # ---------------- ArXiv ----------------

    async def _search_arxiv_comprehensive(self, model_name: str) -> List[Dict[str, Any]]:
        publications: List[Dict[str, Any]] = []
        queries = [
            f"{model_name} dermatology computer vision",
            f"{model_name} medical imaging deep learning",
            f"skin cancer detection {model_name}",
            f"dermatology AI {model_name}",
        ]
        for q in queries:
            try:
                # HTTPS required; some networks fail on http
                url = f"https://export.arxiv.org/api/query?search_query=all:{quote_plus(q)}&start=0&max_results=8"
                xml_content = await self._get_text(url)
                if xml_content:
                    publications.extend(self._parse_arxiv_xml(xml_content, model_name))
            except Exception as e:
                print(f"Error in ArXiv search for '{q}': {e}")
                continue
        return publications

    def _parse_arxiv_xml(self, xml_content: str, model_name: str) -> List[Dict[str, Any]]:
        from xml.etree import ElementTree as ET
        pubs: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_content)
            ns = {"atom": "https://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns):
                try:
                    title_elem = entry.find("atom:title", ns)
                    title = (title_elem.text or "").strip() if title_elem is not None else ""
                    summary_elem = entry.find("atom:summary", ns)
                    summary = (summary_elem.text or "").strip() if summary_elem is not None else ""
                    authors = []
                    for author_elem in entry.findall("atom:author", ns):
                        name_elem = author_elem.find("atom:name", ns)
                        if name_elem is not None and name_elem.text:
                            authors.append(name_elem.text.strip())

                    # links
                    pdf_url = ""
                    abstract_url = ""
                    for link_elem in entry.findall("atom:link", ns):
                        href = link_elem.get("href", "") or ""
                        rel = link_elem.get("rel", "") or ""
                        typ = link_elem.get("type", "") or ""
                        if not pdf_url and (typ == "application/pdf" or href.endswith(".pdf") or "/pdf/" in href):
                            pdf_url = href
                        if not abstract_url and (rel == "alternate" and "arxiv.org/abs/" in href):
                            abstract_url = href
                    if not abstract_url and pdf_url and "arxiv.org/pdf/" in pdf_url:
                        abs_id = pdf_url.split("/pdf/")[-1].replace(".pdf", "")
                        abstract_url = f"https://arxiv.org/abs/{abs_id}"

                    published_elem = entry.find("atom:published", ns)
                    published = published_elem.text.strip() if published_elem is not None and published_elem.text else ""

                    categories = []
                    for cat in entry.findall("atom:category", ns):
                        term = cat.get("term", "")
                        if term:
                            categories.append(term)

                    if title and summary:
                        content_for_analysis = f"{title} {summary}"
                        ai_analysis: Dict[str, Any] = {}
                        # budgeted analysis on arxiv too
                        kw = ("dermatology", "skin", "melanoma", "dermoscop", "clinical", model_name.lower())
                        if any(k in content_for_analysis.lower() for k in kw) and self._ai_budget < self._ai_budget_cap:
                            ai_analysis = self.ai_extractor.extract_model_information(
                                content_for_analysis, "arxiv_publication"
                            )
                            self._ai_budget += 1

                        pubs.append(
                            {
                                "title": title,
                                "authors": authors,
                                "abstract": summary,
                                "pdf_url": pdf_url,
                                "url": abstract_url,
                                "published_date": published,
                                "categories": categories,
                                "type": "arxiv_publication",
                                "ai_analysis": ai_analysis,
                                "extracted_content": content_for_analysis,
                                "relevance_score": self._calculate_publication_relevance(
                                    title, summary, [], categories, model_name
                                ),
                            }
                        )
                except Exception as e:
                    print(f"Error parsing ArXiv entry: {e}")
                    continue
        except Exception as e:
            print(f"Error parsing ArXiv XML: {e}")
        return pubs

    # ---------------- utilities ----------------

    def _calculate_publication_relevance(
        self, title: str, abstract: str, keywords: List[str], mesh_terms: List[str], model_name: str
    ) -> float:
        score = 0.0
        t = title.lower()
        a = abstract.lower()
        if model_name.lower() in t:
            score += 15
        if any(w in t for w in ["dermatology", "skin", "melanoma"]):
            score += 10
        if any(w in t for w in ["ai", "artificial intelligence", "machine learning", "deep learning"]):
            score += 8
        if any(w in t for w in ["clinical", "validation", "performance"]):
            score += 6
        if model_name.lower() in a:
            score += 10
        if any(w in a for w in ["accuracy", "sensitivity", "specificity", "auc"]):
            score += 5
        if any(w in a for w in ["fda", "regulatory", "approval"]):
            score += 8
        if any(w in a for w in ["bias", "fairness", "ethics"]):
            score += 4
        all_terms = [term.lower() for term in keywords + mesh_terms]
        if any("dermatology" in term for term in all_terms):
            score += 5
        if any(("artificial intelligence" in term) or ("machine learning" in term) for term in all_terms):
            score += 4
        return score

    def _deduplicate_publications(self, pubs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen_dois = set()
        seen_titles = set()
        unique: List[Dict[str, Any]] = []
        for p in pubs:
            doi = (p.get("doi") or "").lower()
            if doi:
                if doi in seen_dois:
                    continue
                seen_dois.add(doi)
            title = (p.get("title") or "").lower().strip()
            if title:
                # fuzzy-ish overlap via word-intersection ratio
                tw = set(title.split())
                dup = False
                for st in seen_titles:
                    sw = set(st.split())
                    denom = max(len(tw), len(sw)) or 1
                    if len(tw & sw) / denom > 0.8:
                        dup = True
                        break
                if dup:
                    continue
                seen_titles.add(title)
            unique.append(p)
        return unique
