"""
ENHANCED PUBLICATION FINDER - ACADEMIC RESEARCH DISCOVERY

PURPOSE:
Comprehensive academic publication discovery system for medical AI models.
Searches across multiple databases and repositories to find research papers,
technical documentation, and validation studies.

HOW IT WORKS:
1. Multi-database search (PubMed, ArXiv, Google Scholar, bioRxiv)
2. Advanced query construction with medical terminology
3. Developer-aware searches for author-specific papers
4. Content extraction and relevance scoring
5. Citation metadata collection and validation

SUPPORTED DATABASES:
- PubMed: Medical and healthcare research
- ArXiv: Computer science and AI preprints  
- Google Scholar: Broad academic coverage
- bioRxiv: Biology and medical preprints
- IEEE Xplore: Technical and engineering papers
- NCBI databases: Medical research repositories

SEARCH STRATEGIES:
- Model-specific queries with medical terminology
- Author/developer-based searches
- Institution-based research discovery
- Citation network exploration
- Reference backtracking

USAGE:
async with EnhancedPublicationFinder() as finder:
    papers = await finder.search_all_databases(model_name, developer_name)
"""

import asyncio
import aiohttp
import json
import re
from typing import Dict, List, Any, Optional
from urllib.parse import quote_plus
import sys
import os
from pathlib import Path

# Add src directory to path for imports
current_dir = Path(__file__).parent
src_dir = current_dir.parent
sys.path.insert(0, str(src_dir))

from ai_extractors.ai_extractor import AIContentExtractor
import os
import random

class EnhancedPublicationFinder:
    """
    Advanced publication discovery system for medical AI models
    Searches across PubMed, ArXiv, Google Scholar, and bioRxiv
    """

    def __init__(self):
        self.ai_extractor = AIContentExtractor()
        self.session = None
        self.ncbi_email = os.getenv("NCBI_EMAIL", "modelcard@example.com")
        self.ncbi_api_key = os.getenv("NCBI_API_KEY")

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
                        # Respect Retry-After header if present
                        ra = r.headers.get("Retry-After")
                        if ra:
                            try:
                                delay = float(ra)
                            except ValueError:
                                delay = None
                        else:
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

    async def _get(self, url: str, **kw) -> Optional[aiohttp.ClientResponse]:
        return await self._request("GET", url, **kw)

    async def _get_json(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        tries: int = 3,
        backoff_base: float = 0.8,
        retry_for: tuple = (408, 429, 500, 502, 503, 504),
    ) -> Optional[Dict[str, Any]]:
        if self.session is None:
            raise RuntimeError("HTTP session is not initialized (use `async with EnhancedPublicationFinder()`)")
        last_exc = None
        for attempt in range(tries):
            try:
                async with self.session.request("GET", url, params=params, headers=headers) as r:
                    if r.status == 200:
                        try:
                            return await r.json()
                        except Exception as e:
                            print(f"JSON parse error for {url}: {e}")
                            return None
                    if r.status in retry_for and attempt < tries - 1:
                        ra = r.headers.get("Retry-After")
                        if ra:
                            try:
                                delay = float(ra)
                            except ValueError:
                                delay = None
                        else:
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


    async def _get_text(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        tries: int = 3,
        backoff_base: float = 0.8,
        retry_for: tuple = (408, 429, 500, 502, 503, 504),
    ) -> Optional[str]:
        if self.session is None:
            raise RuntimeError("HTTP session is not initialized (use `async with EnhancedPublicationFinder()`)")
        last_exc = None
        for attempt in range(tries):
            try:
                async with self.session.request("GET", url, params=params, headers=headers) as r:
                    if r.status == 200:
                        try:
                            return await r.text()
                        except Exception as e:
                            print(f"Text read error for {url}: {e}")
                            return None
                    if r.status in retry_for and attempt < tries - 1:
                        ra = r.headers.get("Retry-After")
                        if ra:
                            try:
                                delay = float(ra)
                            except ValueError:
                                delay = None
                        else:
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



    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=25, connect=10, sock_read=15)
        connector = aiohttp.TCPConnector(limit=8, limit_per_host=3, enable_cleanup_closed=True)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ModelCardGenerator/1.0)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def comprehensive_publication_search(self, model_name: str) -> List[Dict[str, Any]]:
        all_publications = []
        search_tasks = [
            self._search_pubmed_comprehensive(model_name),
            self._search_arxiv_comprehensive(model_name),
            self._search_biorxiv(model_name),
            self._search_medrxiv(model_name),
            self._search_nature_medicine(model_name),
            self._search_jama_dermatology(model_name)
        ]
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        for result in results:
            if not isinstance(result, Exception) and isinstance(result, list):
                all_publications.extend(result)
        unique_pubs = self._deduplicate_publications(all_publications)
        prioritized_pubs = sorted(unique_pubs, key=lambda x: x.get('relevance_score', 0), reverse=True)
        return prioritized_pubs[:15]

    async def _search_pubmed_comprehensive(self, model_name: str) -> List[Dict[str, Any]]:
        publications = []
        search_queries = [
            f"{model_name} dermatology artificial intelligence validation",
            f"{model_name} skin cancer machine learning clinical",
            f"{model_name} dermoscopy deep learning accuracy",
            f"artificial intelligence dermatology {model_name} FDA",
            f"machine learning skin classification {model_name}",
            f"deep learning melanoma detection {model_name}",
            f"computer vision dermatology {model_name} performance",
            f"clinical validation {model_name} dermatology AI"
        ]
        for query in search_queries:
            try:
                base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                params = f"db=pubmed&term={quote_plus(query)}&retmax=10&retmode=json&tool=cardgen&email={quote_plus(self.ncbi_email)}"
                if self.ncbi_api_key:
                    params += f"&api_key={self.ncbi_api_key}"
                search_url = f"{base}?{params}"

                # Use retrying GET
                search_data = await self._get_json(search_url)
                pmids: List[str] = []
                if search_data:
                    pmids = search_data.get('esearchresult', {}).get('idlist', []) or []

                if pmids:
                    base_f = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                    ids = ','.join(pmids)
                    params_f = f"db=pubmed&id={ids}&retmode=xml&tool=cardgen&email={quote_plus(self.ncbi_email)}"
                    if self.ncbi_api_key:
                        params_f += f"&api_key={self.ncbi_api_key}"
                    fetch_url = f"{base_f}?{params_f}"

                    xml_content = await self._get_text(fetch_url)
                    if xml_content:
                        papers = self._parse_pubmed_xml_detailed(xml_content, model_name)
                        publications.extend(papers)

            except Exception as e:
                print(f"Error in PubMed search for '{query}': {e}")
                continue
        return publications

    def _parse_pubmed_xml_detailed(self, xml_content: str, model_name: str) -> List[Dict[str, Any]]:
        from xml.etree import ElementTree as ET
        publications = []
        try:
            root = ET.fromstring(xml_content)
            for article in root.findall('.//PubmedArticle'):
                try:
                    pmid_elem = article.find('.//PMID')
                    pmid = pmid_elem.text if pmid_elem is not None else ''
                    title_elem = article.find('.//ArticleTitle')
                    title = title_elem.text if title_elem is not None else ''
                    abstract_sections = []
                    for abstract_elem in article.findall('.//AbstractText'):
                        if abstract_elem is not None and abstract_elem.text:
                            label = abstract_elem.get('Label', '')
                            text = abstract_elem.text
                            abstract_sections.append(f"{label}: {text}" if label else text)
                    full_abstract = ' '.join(abstract_sections)
                    authors_info = []
                    for author_elem in article.findall('.//Author'):
                        fname = author_elem.find('.//ForeName')
                        lname = author_elem.find('.//LastName')
                        affiliation = author_elem.find('.//AffiliationInfo/Affiliation')
                        if fname is not None and lname is not None:
                            author_name = f"{fname.text} {lname.text}"
                            if affiliation is not None and affiliation.text:
                                author_name += f" ({affiliation.text})"
                            authors_info.append(author_name)
                    journal_elem = article.find('.//Journal/Title')
                    journal = journal_elem.text if journal_elem is not None else ''
                    doi = ''
                    for id_elem in article.findall('.//ArticleId'):
                        if id_elem.get('IdType') == 'doi':
                            doi = id_elem.text
                            break
                    keywords = []
                    for keyword_elem in article.findall('.//Keyword'):
                        if keyword_elem is not None and keyword_elem.text:
                            keywords.append(keyword_elem.text)
                    mesh_terms = []
                    for mesh_elem in article.findall('.//DescriptorName'):
                        if mesh_elem is not None and mesh_elem.text:
                            mesh_terms.append(mesh_elem.text)
                    if title and pmid and full_abstract:
                        content_for_analysis = f"{title} {full_abstract}"
                        ai_analysis = self.ai_extractor.extract_model_information(
                            content_for_analysis, 'pubmed_publication'
                        )
                        publication = {
                            'title': title,
                            'authors': authors_info,
                            'journal': journal,
                            'abstract': full_abstract,
                            'pmid': pmid,
                            'doi': doi,
                            'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                            'doi_url': f"https://doi.org/{doi}" if doi else '',
                            'keywords': keywords,
                            'mesh_terms': mesh_terms,
                            'type': 'pubmed_publication',
                            'ai_analysis': ai_analysis,
                            'extracted_content': content_for_analysis,
                            'relevance_score': self._calculate_publication_relevance(
                                title, full_abstract, keywords, mesh_terms, model_name
                            )
                        }
                        publications.append(publication)
                except Exception as e:
                    print(f"Error parsing individual PubMed article: {e}")
                    continue
        except Exception as e:
            print(f"Error parsing PubMed XML: {e}")
        return publications

    async def _search_crossref_journal(
        self,
        model_name: str,
        journal_title: str,
        rows: int = 8,
        years_back: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Query Crossref for papers in a specific journal that match the model name and derm keywords.
        Returns our standard publication dicts.
        """
        publications: List[Dict[str, Any]] = []

        # Build a focused query to improve relevance
        query = f'{model_name} dermatology OR "skin" OR melanoma OR dermoscopy OR "computer vision" OR "deep learning"'

        # Rough date filter (YYYY-MM-DD). We'll use Jan 1 of (current_year - years_back).
        from datetime import datetime
        from_year = max(1900, datetime.utcnow().year - years_back)
        from_pub_date = f"{from_year}-01-01"

        params = {
            "query": query,
            "rows": str(rows),
            "sort": "score",
            "order": "desc",
            "select": "DOI,title,author,container-title,issued,URL,abstract",
            # Crossref filter format: key:value,key:value
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
                    given = a.get("given") or ""
                    family = a.get("family") or ""
                    name = (given + " " + family).strip()
                    if name:
                        authors.append(name)

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
                doi = it.get("DOI") or ""
                doi_url = f"https://doi.org/{doi}" if doi else ""

                # abstract is often JATS/XML-ish; strip tags if present
                abstract_raw = it.get("abstract") or ""
                abstract = re.sub(r"<[^>]+>", " ", abstract_raw).strip() if abstract_raw else ""

                # Simple AI gating + shared budget
                content_for_analysis = f"{title} {abstract}"
                kw = ("dermatology", "skin", "melanoma", "dermoscop", "clinical", model_name.lower())
                should_analyze = any(k in content_for_analysis.lower() for k in kw)
                ai_analysis: Dict[str, Any] = {}
                if should_analyze and getattr(self, "_ai_budget", 0) < 6:
                    ai_analysis = self.ai_extractor.extract_model_information(
                        content_for_analysis, 'crossref_publication'
                    )
                    self._ai_budget = getattr(self, "_ai_budget", 0) + 1

                pub: Dict[str, Any] = {
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "journal": journal_title,
                    "pmid": "",  # not applicable here
                    "doi": doi,
                    "url": url_item or doi_url,
                    "doi_url": doi_url,
                    "published_date": published_date,
                    "categories": [],  # Crossref subject categories are inconsistent; omit
                    "type": "crossref_publication",
                    "ai_analysis": ai_analysis,
                    "extracted_content": content_for_analysis,
                    "relevance_score": self._calculate_publication_relevance(
                        title, abstract, [], [], model_name
                    ),
                }
                publications.append(pub)
            except Exception as e:
                print(f"Crossref parse error: {e}")
                continue

        return publications

    async def _search_biorxiv(self, model_name: str) -> List[Dict[str, Any]]:
        # bioRxiv via Crossref (preprints)
        return await self._search_crossref_journal(model_name, "bioRxiv", rows=8, years_back=10)

    async def _search_nature_medicine(self, model_name: str) -> List[Dict[str, Any]]:
        # Nature Medicine via Crossref
        return await self._search_crossref_journal(model_name, "Nature Medicine", rows=6, years_back=10)


    async def _search_jama_dermatology(self, model_name: str) -> List[Dict[str, Any]]:
        # JAMA Dermatology via Crossref
        return await self._search_crossref_journal(model_name, "JAMA Dermatology", rows=6, years_back=10)


    async def _search_medrxiv(self, model_name: str) -> List[Dict[str, Any]]:
        # medRxiv via Crossref (preprints)
        return await self._search_crossref_journal(model_name, "medRxiv", rows=8, years_back=10)


    def _calculate_publication_relevance(self, title: str, abstract: str, keywords: List[str], 
                                       mesh_terms: List[str], model_name: str) -> float:
        score = 0.0
        title_lower = title.lower()
        if model_name.lower() in title_lower:
            score += 15
        if any(term in title_lower for term in ['dermatology', 'skin', 'melanoma']):
            score += 10
        if any(term in title_lower for term in ['ai', 'artificial intelligence', 'machine learning', 'deep learning']):
            score += 8
        if any(term in title_lower for term in ['clinical', 'validation', 'performance']):
            score += 6
        abstract_lower = abstract.lower()
        if model_name.lower() in abstract_lower:
            score += 10
        if any(term in abstract_lower for term in ['accuracy', 'sensitivity', 'specificity', 'auc']):
            score += 5
        if any(term in abstract_lower for term in ['fda', 'regulatory', 'approval']):
            score += 8
        if any(term in abstract_lower for term in ['bias', 'fairness', 'ethics']):
            score += 4
        all_terms = [term.lower() for term in keywords + mesh_terms]
        if any('dermatology' in term for term in all_terms):
            score += 5
        if any('artificial intelligence' in term or 'machine learning' in term for term in all_terms):
            score += 4
        return score

    def _deduplicate_publications(self, publications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen_pmids = set()
        seen_dois = set()
        seen_titles = set()
        unique_pubs = []
        for pub in publications:
            pmid = pub.get('pmid', '')
            if pmid:
                if pmid in seen_pmids:
                    continue
                seen_pmids.add(pmid)
            doi = pub.get('doi', '')
            if doi:
                if doi in seen_dois:
                    continue
                seen_dois.add(doi)
            title = pub.get('title', '').lower()
            if title:
                title_words = set(title.split())
                is_duplicate = False
                for seen_title in seen_titles:
                    seen_words = set(seen_title.split())
                    denom = max(len(title_words), len(seen_words)) or 1
                    if len(title_words.intersection(seen_words)) / denom > 0.8:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    seen_titles.add(title)
                    unique_pubs.append(pub)
            else:
                unique_pubs.append(pub)
        return unique_pubs

    async def search_multiple_databases(self, model_name: str) -> List[Dict[str, Any]]:
        """Search multiple databases for comprehensive publication discovery"""
        return await self.comprehensive_publication_search(model_name)


    async def _search_arxiv_comprehensive(self, model_name: str) -> List[Dict[str, Any]]:
        publications = []
        try:
            search_queries = [
                f"{model_name} dermatology computer vision",
                f"{model_name} medical imaging deep learning",
                f"skin cancer detection {model_name}",
                f"dermatology AI {model_name}"
            ]
            for query in search_queries:
                try:
                    search_url = f"http://export.arxiv.org/api/query?search_query=all:{quote_plus(query)}&start=0&max_results=8"
                    xml_content = await self._get_text(search_url)
                    if xml_content:
                        papers = self._parse_arxiv_xml(xml_content, model_name)
                        publications.extend(papers)
                        
                except Exception as e:
                    print(f"Error in ArXiv search for '{query}': {e}")
                    continue
        except Exception as e:
            print(f"Error in ArXiv comprehensive search: {e}")
        return publications

    def _parse_arxiv_xml(self, xml_content: str, model_name: str) -> List[Dict[str, Any]]:
        from xml.etree import ElementTree as ET
        publications = []
        try:
            root = ET.fromstring(xml_content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('.//atom:entry', ns):
                try:
                    title_elem = entry.find('atom:title', ns)
                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else ''
                    summary_elem = entry.find('atom:summary', ns)
                    summary = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ''
                    authors = []
                    for author_elem in entry.findall('atom:author', ns):
                        name_elem = author_elem.find('atom:name', ns)
                        if name_elem is not None:
                            authors.append(name_elem.text)
                    # Robust link selection
                    pdf_url = ''
                    abstract_url = ''
                    for link_elem in entry.findall('atom:link', ns):
                        href = link_elem.get('href', '')
                        rel  = link_elem.get('rel', '')
                        typ  = link_elem.get('type', '')
                        if not pdf_url and (typ == 'application/pdf' or href.endswith('.pdf') or '/pdf/' in href):
                            pdf_url = href
                        if not abstract_url and (rel == 'alternate' and 'arxiv.org/abs/' in href):
                            abstract_url = href
                    if not abstract_url and pdf_url and 'arxiv.org/pdf/' in pdf_url:
                        abs_id = pdf_url.split('/pdf/')[-1].replace('.pdf', '')
                        abstract_url = f"https://arxiv.org/abs/{abs_id}"
                    published_elem = entry.find('atom:published', ns)
                    published = published_elem.text if published_elem is not None else ''
                    categories = []
                    for cat_elem in entry.findall('atom:category', ns):
                        term = cat_elem.get('term', '')
                        if term:
                            categories.append(term)
                    if title and summary:
                        content_for_analysis = f"{title} {summary}"
                        ai_analysis = self.ai_extractor.extract_model_information(
                            content_for_analysis, 'arxiv_publication'
                        )
                        publication = {
                            'title': title,
                            'authors': authors,
                            'abstract': summary,
                            'pdf_url': pdf_url,
                            'url': abstract_url,
                            'published_date': published,
                            'categories': categories,
                            'type': 'arxiv_publication',
                            'ai_analysis': ai_analysis,
                            'extracted_content': content_for_analysis,
                            'relevance_score': self._calculate_publication_relevance(
                                title, summary, [], categories, model_name
                            )
                        }
                        publications.append(publication)
                except Exception as e:
                    print(f"Error parsing ArXiv entry: {e}")
                    continue
        except Exception as e:
            print(f"Error parsing ArXiv XML: {e}")
        return publications
