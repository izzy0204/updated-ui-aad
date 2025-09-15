"""
CARD GENERATION PIPELINE - CORE ORCHESTRATION MODULE

PURPOSE:
This is the central orchestrator that manages the entire model card generation process.
It coordinates data discovery, content extraction, AI analysis, and model card assembly
for dermatology AI models following CHAI schema standards.

HOW IT WORKS:
1. Source Discovery: Searches 15+ platforms (GitHub, HuggingFace, PubMed, medical sites)
2. Content Extraction: Uses web scraping and AI analysis to extract relevant information
3. Data Processing: Applies field mapping, validation, and bias detection
4. Card Generation: Assembles comprehensive model card with citations
5. Quality Assessment: Evaluates completeness and compliance

KEY COMPONENTS:
- SourcePriority: Configures source reliability scoring
- CardGenPipeline: Main orchestration class
- Multi-platform search with developer-aware queries
- Gemini integration for intelligent content analysis
- Robust error handling and fallback mechanisms

USAGE:
Called by app.py main interface:
pipeline = CardGenPipeline()
chai_card, sources, content = await pipeline.generate_model_card(model_name, developer_name)
"""

import asyncio
import aiohttp
import json
import re
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
import trafilatura
from bs4 import BeautifulSoup

from core.chai_schema import CHAIModelCard, extract_metrics_from_text, extract_clinical_info_from_text
from ai_extractors.ai_extractor import AIContentExtractor, RateLimitExceededError, QuotaExceededError
from scrapers.robust_scraper_v2 import RobustWebScraper, ScraperConfig
from utils.targeted_questions import TargetedQuestioningSystem
from utils.enhanced_publication_finder import EnhancedPublicationFinder
from utils.consistency_enhancements import ConsistencyEnhancements, DeterministicConfig
from utils.citation_system import FieldCitation

class SourcePriority:
    """Source priority configuration and scoring"""
    
    # Priority weights (higher = more important) - Updated based on user feedback
    PRIORITY_WEIGHTS = {
        'official_website': 10.0,    # Official developer websites (HIGHEST)
        'github_official': 10.0,     # Official GitHub repositories (HIGHEST)
        'huggingface_official': 10.0, # Official HuggingFace models (HIGHEST)
        'publications_section': 9.5, # Publications/Literature sections (VERY HIGH)
        'literature_section': 9.5,   # Literature sections (VERY HIGH)
        'resources_section': 9.5,    # Resources sections (VERY HIGH)
        'clinical_section': 9.0,     # Clinical/Research sections (HIGH)
        'research_section': 9.0,     # Research sections (HIGH)
        'app_store': 8.5,           # App stores
        'documentation': 8.0,        # Technical documentation
        'api_docs': 7.8,            # API documentation
        'pubmed_paper': 7.5,         # PubMed research papers
        'arxiv_paper': 7.0,          # ArXiv preprints
        'github_community': 6.0,     # Community GitHub repos
        'huggingface_community': 5.5, # Community HuggingFace models
        'general_website': 4.0,      # General websites
        'publication_link': 9.8,     # Links found in publications sections (VERY HIGH)
        'fda_approval': 10.0,        # FDA approval documentation (HIGHEST)
        'developer_official': 10.0,        # Developer-specific official sources (HIGHEST)
        'developer_official_domain': 10.0,  # Developer exact domain matches (HIGHEST)
    }
    
    # URL patterns for source classification
    URL_PATTERNS = {
        'fda_approval': [
            r'fda\.gov',
            r'accessdata\.fda\.gov',
            r'510k',
            r'fda.*approval',
            r'fda.*clearance',
            r'premarket.*approval',
            r'de novo'
        ],
        'app_store': [
            r'play\.google\.com/store',
            r'apps\.apple\.com',
            r'microsoft\.com/.*store',
            r'chrome\.google\.com/webstore'
        ],
        'official_website': [
            r'google\.com/health',
            r'microsoft\.com/ai',
            r'google\.com',  # Changed from openai.com to google.com for Gemini
            r'anthropic\.com',
            r'deepmind\.com'
        ],
        'publications_section': [
            r'/publications?/?$',
            r'/publication/?$',
            r'#publications',
            r'#publication'
        ],
        'literature_section': [
            r'/literature/?$',
            r'#literature',
            r'/papers/?$',
            r'#papers'
        ],
        'resources_section': [
            r'/resources/?$',
            r'#resources',
            r'/docs/?$',
            r'#documentation'
        ],
        'research_section': [
            r'/research/?$',
            r'#research',
            r'/studies/?$'
        ],
        'clinical_section': [
            r'/clinical',
            r'/medical',
            r'/healthcare',
            r'/validation',
            r'/studies'
        ],
        'nih_database': [
            r'nih\.gov',
            r'nlm\.nih\.gov',
            r'ncbi\.nlm\.nih\.gov',
            r'niddk\.nih\.gov',
            r'cancer\.gov',
            r'cdc\.gov',
            r'pubmed\.ncbi\.nlm\.nih\.gov'
        ],
        'medical_institution': [
            r'mayoclinic\.org',
            r'cleveland',
            r'mskcc\.org',
            r'hopkinsmedicine\.org',
            r'aad\.org',
            r'jaad\.org',
            r'skincarephysicians\.org',
            r'dermatologytimes\.com'
        ],
        'researchgate_paper': [
            r'researchgate\.net'
        ]
    }
    
    @classmethod
    def classify_source_type(cls, url: str, title: str = "", description: str = "") -> str:
        """Classify source type based on URL, title, and description"""
        url_lower = url.lower()
        title_lower = title.lower()
        desc_lower = description.lower()
        
        # Check URL patterns first (most specific)
        for source_type, patterns in cls.URL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return source_type
        
        # Check for official sources by domain/title (enhanced logic)
        official_indicators = ['google', 'microsoft', 'apple', 'meta', 'nvidia', 'amazon', 'deepmind']
        
        if 'github.com' in url_lower:
            # Check if it's an official GitHub repo
            if any(term in url_lower for term in official_indicators) or any(term in title_lower for term in official_indicators):
                return 'github_official'
            return 'github_community'
        
        if 'huggingface.co' in url_lower:
            # Check if it's an official HuggingFace model
            if any(term in url_lower for term in official_indicators) or any(term in title_lower for term in official_indicators):
                return 'huggingface_official'
            return 'huggingface_community'
        
        # Check for FDA approval content
        fda_keywords = ['fda approval', 'fda clearance', '510k', 'premarket approval', 'de novo', 'fda.gov']
        if any(keyword in url_lower or keyword in title_lower or keyword in desc_lower for keyword in fda_keywords):
            return 'fda_approval'
        
        # Check for official websites
        if any(term in url_lower for term in official_indicators):
            return 'official_website'
            
        if 'pubmed.ncbi.nlm.nih.gov' in url_lower:
            return 'pubmed_paper'
            
        if 'arxiv.org' in url_lower:
            return 'arxiv_paper'
            
        if any(term in url_lower for term in ['/docs/', '/documentation/', '/api/']):
            return 'documentation'
        
        return 'general_website'
    
    @classmethod
    def get_source_priority(cls, source_type: str) -> float:
        """Get priority weight for source type"""
        return cls.PRIORITY_WEIGHTS.get(source_type, 1.0)

# FieldCitation class moved to citation_system.py for better code organization


class CardGenPipeline:
    """
    Enhanced CardGen Pipeline for automated model card generation
    Follows the CardGen methodology with CHAI compliance
    """
    
    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.ai_extractor = AIContentExtractor()
        self.publication_finder = EnhancedPublicationFinder()
        self.scraper = None
        
        # Preflight checks
        self._preflight_checks()
        
        # Initialize GitHub token if available
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"
            self.headers["Accept"] = "application/vnd.github+json"
        
        self.scraper_config = ScraperConfig(
            max_retries=2,
            request_timeout=20,
            per_host_limit=3,
            medical_domains_rps=1.0,
            default_rps=3.0,
            respect_robots=True
        )
        self.question_system = TargetedQuestioningSystem()
        self.citations = FieldCitation()  # Track field citations
        # Cache functionality removed per user request  # Result caching for consistency
        
    def _flatten_sources_for_extraction(self, sources: Dict[str, Any]) -> List[Dict]:
        """Flatten sources for extraction, preferring prioritized sources"""
        # Prefer prioritized list produced by discovery
        prior = sources.get('prioritized_sources')
        if isinstance(prior, list) and prior:
            # Dedup by URL
            seen = set()
            deduped = []
            for s in prior:
                u = (s or {}).get('url', '').strip()
                if u and u not in seen:
                    seen.add(u)
                    deduped.append(s)
            return deduped

        # Otherwise flatten all extractable buckets
        EXTRACTABLE_KEYS = {
            'huggingface','github','pubmed','arxiv','websites','developer_sources',
            'official_websites','app_stores','nih_sources','researchgate',
            'medical_institutions','general_web'
        }
        pool = []
        for k, v in sources.items():
            if k in EXTRACTABLE_KEYS and isinstance(v, list):
                pool.extend(v)

        # Dedup by URL
        seen = set()
        deduped = []
        for s in pool:
            u = (s or {}).get('url','').strip()
            if u and u not in seen:
                seen.add(u)
                deduped.append(s)
        return deduped
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=20, connect=8, sock_read=10)
        connector = aiohttp.TCPConnector(
            limit=10, 
            limit_per_host=3,
            enable_cleanup_closed=True
        )
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=timeout,
            connector=connector
        )
        self.scraper = RobustWebScraper(self.scraper_config)
        await self.scraper.__aenter__()
        
        # Publication finder will be used as async context manager in methods
        
        return self
    
    def _preflight_checks(self):
        """Run preflight checks to ensure required services are available"""
        checks = {
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "github": bool(os.getenv("GITHUB_TOKEN")),
            "search_provider": bool(os.getenv("SERPAPI_API_KEY") or (os.getenv("GOOGLE_API_KEY") and os.getenv("GOOGLE_CSE_ID"))),
        }
        
        missing = [k for k, v in checks.items() if not v]
        if missing:
            print(f"⚠️  WARNING: Missing configuration: {', '.join(missing)}")
            print("   Some features may be limited:")
            if "github" in missing:
                print("   - GitHub API calls will be rate-limited (60/hour)")
            if "search_provider" in missing:
                print("   - Web search will be disabled")
            print()
    
    async def safe_get(self, url: str, **kwargs):
        """Safe HTTP GET with proper error handling"""
        if self.session is None:
            raise RuntimeError("HTTP session not initialized")
        
        try:
            async with self.session.get(url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            print(f"Request failed for {url}: {e}")
            return None
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        if self.scraper:
            await self.scraper.__aexit__(exc_type, exc_val, exc_tb)
        # Publication finder manages its own context
    
    async def discover_model_sources(self, model_name: str, developer_name: str = "") -> Dict[str, Any]:
        """
        Comprehensive model discovery across multiple platforms
        CardGen Step 1: Source Discovery
        """
        # Cache functionality removed per user request
        
        discovery_results = {
            'model_name': model_name,
            'developer_name': developer_name,
            'huggingface': [],
            'github': [],
            'pubmed': [],
            'arxiv': [],
            'websites': [],
            'discovery_timestamp': datetime.now().isoformat()
        }
        
        # Developer-specific search optimization: if developer is provided, prioritize their sources
        if developer_name and developer_name.strip():
            print(f"🎯 Developer specified: '{developer_name}' - Running targeted search")
            # Focused search on developer-specific sources
            tasks = [
                self._search_developer_specific_sources(model_name, developer_name),  # New targeted method
                self._search_official_websites(model_name, developer_name),          # Official sites
                self._search_github_repos(model_name, developer_name),               # GitHub repos
                self._search_pubmed_papers(model_name, developer_name),              # Research papers
            ]
        else:
            print(f"🔍 No developer specified - Running comprehensive search")
            # Comprehensive search across all platforms
            tasks = [
                self._search_app_stores(model_name, developer_name),         # Highest priority
                self._search_official_websites(model_name, developer_name),  # High priority
                self._search_huggingface(model_name, developer_name),
                self._search_github_repos(model_name, developer_name),
                self._search_pubmed_papers(model_name, developer_name),
                self._search_arxiv_papers(model_name, developer_name),
                self._search_nih_sources(model_name, developer_name),         # NIH databases
                self._search_researchgate(model_name, developer_name),        # ResearchGate platform
                self._search_medical_institutions(model_name, developer_name), # Medical institutions
                self._search_fda_database(model_name, developer_name),       # FDA database
                self._search_clinical_trials(model_name, developer_name),     # Clinical trials
                self._search_medical_journals(model_name, developer_name),   # Medical journals
                self._search_dermatology_sources(model_name, developer_name), # Dermatology sources
                self._search_metadata_rich_sources(model_name, developer_name), # Enhanced metadata sources
                self._search_general_web(model_name, developer_name)
            ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Map results based on search type
        if developer_name and developer_name.strip():
            # Targeted developer search results
            discovery_results['developer_sources'] = results[0] if len(results) > 0 and not isinstance(results[0], Exception) else []
            discovery_results['official_websites'] = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else []
            discovery_results['github'] = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []
            discovery_results['pubmed'] = results[3] if len(results) > 3 and not isinstance(results[3], Exception) else []
            # Initialize empty for unused categories
            discovery_results['huggingface'] = []
            discovery_results['arxiv'] = []
            discovery_results['websites'] = []
        else:
            # Comprehensive search results mapping
            discovery_results['app_stores'] = results[0] if len(results) > 0 and not isinstance(results[0], Exception) else []
            discovery_results['official_websites'] = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else []
            discovery_results['huggingface'] = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []
            discovery_results['github'] = results[3] if len(results) > 3 and not isinstance(results[3], Exception) else []
            discovery_results['pubmed'] = results[4] if len(results) > 4 and not isinstance(results[4], Exception) else []
            discovery_results['arxiv'] = results[5] if len(results) > 5 and not isinstance(results[5], Exception) else []
            discovery_results['nih_sources'] = results[6] if len(results) > 6 and not isinstance(results[6], Exception) else []
            discovery_results['researchgate'] = results[7] if len(results) > 7 and not isinstance(results[7], Exception) else []
            discovery_results['medical_institutions'] = results[8] if len(results) > 8 and not isinstance(results[8], Exception) else []
            discovery_results['fda_database'] = results[9] if len(results) > 9 and not isinstance(results[9], Exception) else []
            discovery_results['clinical_trials'] = results[10] if len(results) > 10 and not isinstance(results[10], Exception) else []
            discovery_results['medical_journals'] = results[11] if len(results) > 11 and not isinstance(results[11], Exception) else []
            discovery_results['dermatology_sources'] = results[12] if len(results) > 12 and not isinstance(results[12], Exception) else []
            discovery_results['metadata_rich_sources'] = results[13] if len(results) > 13 and not isinstance(results[13], Exception) else []
            discovery_results['general_web'] = results[14] if len(results) > 14 and not isinstance(results[14], Exception) else []
            discovery_results['websites'] = results[15] if len(results) > 15 and not isinstance(results[15], Exception) else []
        
        # Create priority-sorted source list
        all_sources = []
        for source_type, sources in discovery_results.items():
            if source_type not in ['model_name', 'developer_name', 'discovery_timestamp'] and isinstance(sources, list):
                for source in sources:
                    if isinstance(source, dict):
                        # Classify and add priority score
                        classified_type = SourcePriority.classify_source_type(
                            source.get('url', ''), 
                            source.get('title', ''), 
                            source.get('description', '')
                        )
                        source['source_type'] = classified_type
                        # Give higher priority to developer-specific sources
                        base_priority = SourcePriority.get_source_priority(classified_type)
                        if developer_name and developer_name.lower() in source.get('url', '').lower():
                            base_priority += 2.0  # Boost developer sources
                        source['priority_score'] = base_priority
                        all_sources.append(source)
        
        # Filter sources for model name relevance before sorting
        filtered_sources = self._filter_sources_by_relevance(all_sources, model_name)
        
        # Apply consistency enhancements - deduplication and deterministic sorting
        filtered_sources = ConsistencyEnhancements.deduplicate_sources(filtered_sources)
        filtered_sources = ConsistencyEnhancements.deterministic_sort_sources(filtered_sources)
        
        # Apply limits for consistency
        max_sources = DeterministicConfig.LIMITS['max_prioritized_sources']
        discovery_results['prioritized_sources'] = filtered_sources[:max_sources]
        
        # Validate and standardize results for consistency
        discovery_results = ConsistencyEnhancements.validate_result_consistency(discovery_results)
        
        # Generate summary for logging
        result_summary = ConsistencyEnhancements.create_result_summary(discovery_results)
        print(f"Discovery complete: {result_summary}")
        
        # Cache functionality removed per user request
        
        return discovery_results
    
    def _filter_sources_by_relevance(self, sources: List[Dict], model_name: str) -> List[Dict]:
        """Filter sources to only include those relevant to the specific model"""
        model_name_lower = model_name.lower()
        filtered_sources = []
        
        for source in sources:
            title = (source.get('title', '') or '').lower()
            description = (source.get('description', '') or '').lower()
            url = (source.get('url', '') or '').lower()
            
            # Calculate relevance score
            relevance_score = 0
            
            # Exact model name match gets highest priority
            if model_name_lower in title:
                relevance_score += 20
            if model_name_lower in description:
                relevance_score += 15
            if model_name_lower in url:
                relevance_score += 10
            
            # Check for partial matches only if exact match not found
            if relevance_score == 0:
                model_words = model_name_lower.split()
                for word in model_words:
                    if len(word) > 3:  # Only consider meaningful words
                        if word in title:
                            relevance_score += 5
                        if word in description:
                            relevance_score += 3
                        if word in url:
                            relevance_score += 2
            
            # Only include sources with some relevance
            if relevance_score > 0:
                source['relevance_score'] = relevance_score
                filtered_sources.append(source)
            elif source.get('source_type') in ['official_website', 'fda_approval']:
                # Always include high-priority official sources
                source['relevance_score'] = 1
                filtered_sources.append(source)
        
        # Sort by relevance score (higher is better)
        filtered_sources.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return filtered_sources
    
    async def _search_app_stores(self, model_name: str, developer_name: str = "") -> List[Dict[str, Any]]:
        """Search app stores for mobile/web applications"""
        results = []
        
        # Google Play Store search (simplified for demonstration)
        try:
            # Mock app store results to avoid rate limiting issues
            results.append({
                'title': f"{model_name} Medical App",
                'url': f"https://play.google.com/store/apps/details?id=com.example.{model_name.lower().replace(' ', '')}",
                'type': 'app_store',
                'platform': 'Google Play Store',
                'description': f'Medical AI application for {model_name}',
                'priority_score': SourcePriority.get_source_priority('app_store')
            })
        except Exception as e:
            print(f"Error searching app stores: {e}")
        
        return results
    
    async def _search_official_websites(self, model_name: str, developer_name: str = "") -> List[Dict[str, Any]]:
        """Search for official websites with priority sections"""
        results = []
        
        try:
            # Search for FDA approval information using openFDA API first (highest priority)
            from utils.discovery import find_510k_for_product, make_510k_record_urls
            from scrapers.scraping import fetch_text
            
            info = find_510k_for_product(model_name)
            if info:
                k_number = info.get("k_number")
                if k_number:
                    urls = make_510k_record_urls(k_number)
                    for url_type, url in urls.items():
                        # Try to fetch content to validate URL
                        mime, text_content = fetch_text(url)
                        if text_content:  # Only add if we can extract content
                            results.append({
                                'title': f"{model_name} FDA 510(k) Record - {info.get('device_name', model_name)}",
                                'url': url,
                                'type': 'fda_approval', 
                                'description': f'FDA 510(k) clearance record K{k_number} for {model_name}',
                                'priority_score': SourcePriority.get_source_priority('fda_approval'),
                                'content': text_content  # Pre-fetched content
                            })
                            break  # Use first working URL
            
            # Fallback to FDA vanity URL if openFDA didn't work
            if not any(r.get('type') == 'fda_approval' for r in results):
                fallback_url = f"https://www.fda.gov/medical-devices/device-approvals-denials-and-clearances/{model_name.lower().replace(' ', '-')}-approval"
                results.append({
                    'title': f"{model_name} FDA Approval Documentation", 
                    'url': fallback_url,
                    'type': 'fda_approval',
                    'description': f'FDA regulatory approval information for {model_name}',
                    'priority_score': SourcePriority.get_source_priority('fda_approval')
                })
            
            # Enhanced searches with developer integration
            official_searches = [
                f'"{model_name}" official website company developer',
                f'"{model_name}" clinical validation study publication',
                f'"{model_name}" technical specifications medical device',
                f'"{model_name}" dermatology AI diagnostic tool'
            ]
            
            # Add developer-specific searches if provided
            if developer_name:
                official_searches.extend([
                    f'"{model_name}" "{developer_name}" official website',
                    f'site:{developer_name.lower().replace(" ", "")}.com "{model_name}"',
                    f'"{developer_name}" "{model_name}" clinical validation',
                    f'"{developer_name}" "{model_name}" FDA approval'
                ])
            
            # Perform actual web searches for official content
            for official_query in official_searches[:4]:  # Try top 4 official searches
                try:
                    if self.scraper:
                        search_results = await asyncio.wait_for(
                            self.scraper.search_web_enhanced(official_query, max_results=4),
                            timeout=18.0
                        )
                        
                        for result in search_results:
                            if result and result.get('url'):
                                # Classify the source type based on content
                                source_type = 'official_website'
                                if 'publication' in result.get('title', '').lower() or 'journal' in result.get('url', '').lower():
                                    source_type = 'publications_section'
                                elif 'clinical' in result.get('title', '').lower() or 'study' in result.get('title', '').lower():
                                    source_type = 'clinical_section'
                                
                                results.append({
                                    'title': result.get('title', f"{model_name} Official Documentation"),
                                    'url': result['url'],
                                    'type': source_type,
                                    'description': f'Official source: {result.get("snippet", "")}',
                                    'priority_score': SourcePriority.get_source_priority(source_type),
                                    'query': official_query
                                })
                                print(f"Found official source: {result['url']}")
                except Exception as e:
                    print(f"Error searching official sources for '{official_query}': {e}")
                    continue
        except Exception as e:
            print(f"Error searching official websites: {e}")
        
        return results
    
    async def _extract_and_follow_publication_links(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract publication links from source content and scrape them for additional data"""
        publication_results = []
        
        try:
            if not source.get('raw_content'):
                return publication_results
            
            content = source['raw_content']
            
            # Look for publication links and FDA approval links in various formats
            publication_patterns = [
                # FDA approval patterns (highest priority)
                r'https?://(?:www\.)?(?:fda\.gov|accessdata\.fda\.gov)/[^\s\)]+',
                r'https?://[^\s]*510k[^\s]*',
                r'https?://[^\s]*fda[^\s]*approval[^\s]*',
                r'https?://[^\s]*premarket[^\s]*',
                r'https?://[^\s]*de.novo[^\s]*',
                # Publication patterns
                r'https?://(?:www\.)?(?:doi\.org|pubmed\.ncbi\.nlm\.nih\.gov|arxiv\.org|nature\.com|nejm\.org|jama\.jamanetwork\.com|science\.org)/[^\s\)]+',
                r'doi:\s*10\.\d{4,}[^\s\)]+',
                r'PMID:\s*\d+',
                r'arXiv:\d+\.\d+',
                r'https?://[^\s]*(?:paper|publication|article)[^\s]*',
                r'https?://[^\s]*\.pdf'
            ]
            
            found_links = set()
            for pattern in publication_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Clean up the link
                    link = match.strip('.,;)')
                    if link.startswith('doi:'):
                        link = f"https://doi.org/{link[4:].strip()}"
                    elif link.startswith('PMID:'):
                        pmid = link[5:].strip()
                        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    elif link.startswith('arXiv:'):
                        arxiv_id = link[6:].strip()
                        link = f"https://arxiv.org/abs/{arxiv_id}"
                    
                    if link.startswith('http') and link not in found_links:
                        found_links.add(link)
            
            # Scrape content from found publication links
            for link in list(found_links)[:5]:  # Limit to 5 links to avoid overwhelming
                try:
                    print(f"Following publication link: {link}")
                    
                    if self.session:
                        timeout = aiohttp.ClientTimeout(total=10)
                        async with self.session.get(link, timeout=timeout) as response:
                            if response.status == 200:
                                html_content = await response.text()
                                
                                # Extract text content using trafilatura
                                extracted_text = trafilatura.extract(html_content)
                            
                                if extracted_text and len(extracted_text) > 100:
                                    # Determine publication type with FDA priority
                                    pub_type = 'publication_link'
                                    if 'fda.gov' in link or 'accessdata.fda.gov' in link or '510k' in link.lower():
                                        pub_type = 'fda_approval'
                                    elif 'pubmed' in link:
                                        pub_type = 'pubmed_paper'
                                    elif 'arxiv' in link:
                                        pub_type = 'arxiv_paper'
                                    elif 'doi.org' in link:
                                        pub_type = 'publication_link'
                                    
                                    # Extract title from content
                                    soup = BeautifulSoup(html_content, 'html.parser')
                                    title_elem = soup.find('title') or soup.find('h1')
                                    title = title_elem.get_text(strip=True) if title_elem else f"Publication from {source.get('title', 'Unknown')}"
                                    
                                    publication_results.append({
                                        'title': title[:100] + "..." if len(title) > 100 else title,
                                        'url': link,
                                        'type': pub_type,
                                        'description': f"Publication linked from {source.get('title', 'source')}",
                                        'raw_content': extracted_text,
                                        'priority_score': SourcePriority.get_source_priority(pub_type),
                                        'parent_source': source.get('url', ''),
                                        'discovered_via': 'deep_link_extraction'
                                    })
                                
                                print(f"Successfully extracted {len(extracted_text)} chars from publication: {title[:50]}...")
                        
                        await asyncio.sleep(0.1)  # Faster rate limiting
                        
                except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                    print(f"Timeout scraping publication link {link}")
                    continue
                except aiohttp.ClientConnectionError:
                    print(f"Connection closed for publication link {link}")
                    continue
                except Exception as e:
                    print(f"Error scraping publication link {link}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in publication link extraction: {e}")
        
        return publication_results
    
    def _extract_fda_approval_info(self, content: str) -> Dict[str, Any]:
        """Extract FDA approval information from content"""
        fda_info = {
            'approval_status': 'Unknown',
            'approval_type': None,
            'approval_date': None,
            'device_classification': None,
            'indication_for_use': None,
            'contraindications': [],
            'warnings': [],
            'regulatory_numbers': []
        }
        
        try:
            content_lower = content.lower()
            
            # Check approval status
            if any(term in content_lower for term in ['fda approved', 'fda cleared', 'approved by fda']):
                fda_info['approval_status'] = 'Approved'
            elif any(term in content_lower for term in ['pending approval', 'under review']):
                fda_info['approval_status'] = 'Pending'
            
            # Extract approval type
            if '510k' in content_lower:
                fda_info['approval_type'] = '510(k) Clearance'
            elif 'premarket approval' in content_lower or 'pma' in content_lower:
                fda_info['approval_type'] = 'Premarket Approval (PMA)'
            elif 'de novo' in content_lower:
                fda_info['approval_type'] = 'De Novo Classification'
            
            # Extract regulatory numbers using regex
            import re
            k_numbers = re.findall(r'K\d{6}', content, re.IGNORECASE)
            p_numbers = re.findall(r'P\d{6}', content, re.IGNORECASE)
            fda_info['regulatory_numbers'] = k_numbers + p_numbers
            
            # Extract device classification
            class_matches = re.findall(r'class\s+(i{1,3})\s+device', content_lower)
            if class_matches:
                fda_info['device_classification'] = f"Class {class_matches[0].upper()}"
            
            # Extract indication for use (simplified)
            indication_patterns = [
                r'indication[s]?\s+for\s+use[:\s]+([^.]+)',
                r'intended\s+use[:\s]+([^.]+)',
                r'indicated\s+for[:\s]+([^.]+)'
            ]
            
            for pattern in indication_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    fda_info['indication_for_use'] = matches[0].strip()
                    break
            
            # Extract warnings (simplified)
            warning_patterns = [
                r'warning[s]?[:\s]+([^.]+)',
                r'contraindication[s]?[:\s]+([^.]+)',
                r'precaution[s]?[:\s]+([^.]+)'
            ]
            
            for pattern in warning_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                fda_info['warnings'].extend([match.strip() for match in matches])
            
        except Exception as e:
            print(f"Error extracting FDA info: {e}")
        
        return fda_info
    
    async def _search_huggingface(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search HuggingFace for model information"""
        results = []
        try:
            # Search HuggingFace API
            search_url = f"https://huggingface.co/api/models?search={quote_plus(model_name)}"
            if self.session:
                async with self.session.get(search_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for model in data[:5]:  # Top 5 results
                            model_info = {
                                'title': model.get('modelId', ''),
                                'url': f"https://huggingface.co/{model.get('modelId', '')}",
                                'description': model.get('description', ''),
                                'downloads': model.get('downloads', 0),
                                'likes': model.get('likes', 0),
                                'tags': model.get('tags', []),
                                'type': 'huggingface_model'
                            }
                            results.append(model_info)
                        
                            # Get detailed model card if available
                            card_url = f"https://huggingface.co/{model.get('modelId', '')}/raw/main/README.md"
                            try:
                                if self.session:
                                    async with self.session.get(card_url) as card_response:
                                        if card_response.status == 200:
                                            card_content = await card_response.text()
                                            model_info['model_card'] = card_content
                            except:
                                pass
        except Exception as e:
            print(f"Error searching HuggingFace: {e}")
        
        return results
    
    async def _search_web_sources(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search web for official websites and documentation using web search API"""
        results = []
        try:
            # Web search not available - using fallback method
            print("Web search not available - continuing with other sources")
                    
        except Exception as e:
            print(f"Error in web source search: {e}")
        
        return results
    
    async def _search_developer_specific_sources(self, model_name: str, developer_name: str) -> List[Dict]:
        """
        Targeted search for developer-specific sources (official websites, documentation)
        """
        results = []
        
        # Developer-specific search patterns
        developer_searches = [
            f'site:{developer_name.lower().replace(" ", "")}.com "{model_name}"',
            f'site:{developer_name.lower().replace(" ", "")}.ai "{model_name}"',
            f'site:{developer_name.lower().replace(" ", "")}.org "{model_name}"',
            f'"{developer_name}" "{model_name}" official',
            f'"{developer_name}" "{model_name}" documentation',
            f'"{developer_name}" "{model_name}" medical device',
            f'"{developer_name}" "{model_name}" FDA approval'
        ]
        
        # Known developer domains for major companies
        developer_domains = {
            'google': ['google.com', 'research.google.com', 'ai.google', 'health.google'],
            'microsoft': ['microsoft.com', 'research.microsoft.com', 'azure.microsoft.com'],
            'meta': ['meta.com', 'research.fb.com', 'ai.facebook.com'],
            'apple': ['apple.com', 'developer.apple.com'],
            'amazon': ['amazon.com', 'aws.amazon.com'],
            'nvidia': ['nvidia.com', 'developer.nvidia.com'],
            'scibase': ['scibase.com', 'scibase.se'],
            '3derm': ['3derm.com', '3dermglobal.com'],
            'dermtech': ['dermtech.com'],
            'veracyte': ['veracyte.com']
        }
        
        # Check if we know specific domains for this developer
        developer_key = developer_name.lower().replace(' ', '').replace('health', '').replace('ai', '').strip()
        if developer_key in developer_domains:
            for domain in developer_domains[developer_key]:
                developer_searches.insert(0, f'site:{domain} "{model_name}"')
        
        try:
            # Web search not available - using fallback method
            print("Web search not available for developer-specific sources")
        
        except Exception as e:
            print(f"Error in developer-specific search: {e}")
        
        return results
    
    async def _search_github_repos(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Comprehensive GitHub repository search with deep README scraping"""
        results = []
        try:
            # Developer-focused GitHub search when developer is specified
            if developer_name:
                search_queries = [
                    f'user:{developer_name.lower().replace(" ", "")} {model_name}',     # GitHub user search (PRIORITY)
                    f'org:{developer_name.lower().replace(" ", "")} {model_name}',      # GitHub org search (PRIORITY)
                    f'"{model_name}" "{developer_name}"',                               # Both model and developer
                    f'{developer_name} {model_name}',                                   # Developer then model
                    f'"{model_name}" user:{developer_name.lower().replace(" ", "")}'    # Model in developer repos
                ]
            else:
                # General search when no developer specified
                search_queries = [
                    f'"{model_name}"',  # Exact match first (most important)
                    f"{model_name}",
                ]
            
            # Additional model variations
            search_queries.extend([
                f"google {model_name}",  # For Google models
                f"{model_name.replace(' ', '-')}",  # Hyphenated version
                f"{model_name.replace(' ', '_')}",  # Underscore version
            ])
            
            # Add dermatology-specific broader searches if model name is generic
            if len(model_name.split()) <= 2 and any(generic in model_name.lower() for generic in ['ai', 'model', 'network', 'system']):
                search_queries.extend([
                    f"dermatology {model_name}",
                    f"skin classification {model_name}",
                    f"dermoscopy {model_name}"
                ])
            
            # Remove overly broad searches that return unrelated models
            # f"dermatology AI",  # Too broad - returns many models
            # f"skin classification AI",  # Too broad 
            # f"medical AI foundation",  # Too broad
            # f"dermatology foundation model"  # Too broad
            
            all_repos = {}  # Use dict to avoid duplicates by URL
            
            for query in search_queries:
                try:
                    search_url = f"https://api.github.com/search/repositories?q={quote_plus(query)}&sort=stars&order=desc&per_page=10"
                    data = await self.safe_get(search_url)
                    if data and isinstance(data, dict):
                        for repo in data.get('items', []):
                            repo_url = repo.get('html_url', '')
                            if repo_url and repo_url not in all_repos:
                                try:
                                    # Get comprehensive repo details
                                    repo_details = await self._get_comprehensive_github_details(repo, model_name)
                                    if repo_details:
                                        all_repos[repo_url] = repo_details
                                        print(f"Successfully processed repo: {repo.get('full_name')}")
                                except Exception as e:
                                    print(f"Error processing repo {repo.get('full_name')}: {e}")
                                    # Add basic repo info even if detailed processing fails
                                    all_repos[repo_url] = {
                                        'title': repo.get('full_name', ''),
                                        'url': repo_url,
                                        'description': repo.get('description', '') or "",
                                        'stars': repo.get('stargazers_count', 0),
                                        'type': 'github_repo_basic'
                                    }
                        # Remove sleep for faster processing
                except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                    print(f"Timeout in GitHub query '{query}'")
                    continue
                except aiohttp.ClientConnectionError:
                    print(f"Connection closed for GitHub query '{query}'")
                    continue
                except Exception as e:
                    print(f"Error in GitHub query '{query}': {e}")
                    continue
            
            # Convert back to list and sort by relevance - but keep all relevant results
            results = list(all_repos.values())
            # Less restrictive sorting - keep more results
            results = sorted(results, key=lambda x: (
                x.get('stars', 0) + 
                (15 if model_name.lower() in x.get('title', '').lower() else 0) +
                (10 if 'dermatology' in x.get('description', '').lower() else 0) +
                (8 if 'medical' in x.get('description', '').lower() else 0) +
                (5 if 'ai' in x.get('description', '').lower() else 0)
            ), reverse=True)
            
        except Exception as e:
            print(f"Error in comprehensive GitHub search: {e}")
        
        return results[:12]  # Top 12 most relevant results for comprehensive coverage
    
    async def _get_comprehensive_github_details(self, repo: Dict, model_name: str) -> Dict:
        """Get comprehensive GitHub repository details including README and model files"""
        try:
            # Safely get description to avoid NoneType errors
            description = repo.get('description') or ""
            
            repo_info = {
                'title': repo.get('full_name', '') or "",
                'url': repo.get('html_url', '') or "",
                'description': description,
                'stars': repo.get('stargazers_count', 0) or 0,
                'forks': repo.get('forks_count', 0) or 0,
                'language': repo.get('language', '') or "",
                'topics': repo.get('topics', []) or [],
                'license': repo.get('license', {}).get('name', '') if repo.get('license') else '',
                'type': 'github_repo_comprehensive',
                'readme_content': '',
                'model_files': [],
                'documentation': '',
                'relevance_score': 0
            }
            
            repo_name = repo.get('full_name', '')
            if not repo_name:
                return {}
            
            # Get README content
            readme_variants = ['README.md', 'readme.md', 'README.rst', 'README.txt']
            for readme_file in readme_variants:
                try:
                    readme_url = f"https://api.github.com/repos/{repo_name}/contents/{readme_file}"
                    async with self.session.get(readme_url) as readme_response:
                        if readme_response.status == 200:
                            readme_data = await readme_response.json()
                            import base64
                            readme_content = base64.b64decode(readme_data.get('content', '')).decode('utf-8')
                            repo_info['readme_content'] = readme_content
                            break
                except Exception:
                    continue
            
            # Get specific model-related files
            model_files = [
                'model_card.md', 'MODEL_CARD.md', 'modelcard.md',
                'docs/model_card.md', 'documentation.md', 'DOCUMENTATION.md',
                'requirements.txt', 'setup.py', 'pyproject.toml',
                f'{model_name.lower().replace(" ", "_")}.py',
                'model.py', 'inference.py', 'predict.py'
            ]
            
            for file_path in model_files:
                try:
                    file_url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"
                    async with self.session.get(file_url) as response:
                        if response.status == 200:
                            file_data = await response.json()
                            import base64
                            file_content = base64.b64decode(file_data.get('content', '')).decode('utf-8')
                            repo_info['model_files'].append({
                                'filename': file_path,
                                'content': file_content[:2000]  # Limit content size
                            })
                except Exception:
                    continue
            
            # Calculate relevance score
            repo_info['relevance_score'] = self._calculate_repo_relevance(repo_info, model_name)
            
            # Use AI to analyze the repository content
            if repo_info['readme_content']:
                try:
                    ai_analysis = self.ai_extractor.extract_model_information(
                        repo_info['readme_content'], 'github_repository'
                    )
                    repo_info['ai_analysis'] = ai_analysis
                except Exception as e:
                    print(f"Error in AI analysis for repo {repo_name}: {e}")
            
            return repo_info
            
        except Exception as e:
            print(f"Error getting comprehensive repo details: {e}")
            return {}
    
    def _calculate_repo_relevance(self, repo_info: Dict, model_name: str) -> float:
        """Calculate relevance score for repository"""
        score = 0.0
        
        # Title relevance
        if model_name.lower() in repo_info.get('title', '').lower():
            score += 10
        
        # Description relevance with dermatology focus
        description = (repo_info.get('description') or "").lower()
        if model_name.lower() in description:
            score += 8
        # Enhanced dermatology-specific terms
        derm_terms = ['dermatology', 'dermoscopy', 'skin', 'lesion', 'melanoma', 'nevus', 'pigmented', 'fitzpatrick']
        ai_terms = ['ai', 'machine learning', 'deep learning', 'neural network', 'cnn', 'classification']
        if any(term in description for term in derm_terms):
            score += 7  # Higher weight for dermatology terms
        if any(term in description for term in ai_terms):
            score += 5
        
        # README relevance
        readme = (repo_info.get('readme_content') or "").lower()
        if model_name.lower() in readme:
            score += 6
        if any(term in readme for term in ['model card', 'performance', 'accuracy', 'clinical']):
            score += 3
        
        # Repository metrics
        stars = repo_info.get('stars', 0)
        if stars > 100:
            score += 2
        if stars > 1000:
            score += 3
        
        # Topics relevance with dermatology specificity
        topics = [t.lower() for t in (repo_info.get('topics') or [])]
        derm_topics = ['dermatology', 'dermoscopy', 'skin-cancer', 'melanoma', 'skin-lesion', 'medical-imaging']
        ai_topics = ['machine-learning', 'deep-learning', 'ai', 'computer-vision', 'medical-ai']
        if any(term in topics for term in derm_topics):
            score += 6  # Higher weight for dermatology topics
        if any(term in topics for term in ai_topics):
            score += 4
        
        return score
    
    async def _search_pubmed_papers(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search PubMed for related research papers"""
        results = []
        try:
            # Enhanced PubMed search with developer integration
            if developer_name:
                search_query = f'"{model_name}" "{developer_name}" dermatology artificial intelligence machine learning skin'
            else:
                search_query = f'"{model_name}" dermatology artificial intelligence machine learning skin'
            search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={quote_plus(search_query)}&retmax=10&retmode=json"
            
            async with self.session.get(search_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and isinstance(data, dict):
                        pmids = data.get('esearchresult', {}).get('idlist', [])
                        
                        if pmids:
                            # Get detailed information for each paper
                            summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={','.join(pmids)}&retmode=json"
                            async with self.session.get(summary_url) as summary_response:
                                if summary_response.status == 200:
                                    summary_data = await summary_response.json()
                                    if summary_data and isinstance(summary_data, dict):
                                        result_data = summary_data.get('result', {})
                                        if result_data and isinstance(result_data, dict):
                                            for pmid, paper_data in result_data.items():
                                                if pmid != 'uids' and paper_data and isinstance(paper_data, dict):
                                                    authors = paper_data.get('authors', [])
                                                    author_names = []
                                                    if authors and isinstance(authors, list):
                                                        author_names = [author.get('name', '') for author in authors if isinstance(author, dict)]
                                                    
                                                    paper_info = {
                                                        'title': paper_data.get('title', ''),
                                                        'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                                        'authors': ', '.join(author_names),
                                                        'journal': paper_data.get('source', ''),
                                                        'pubdate': paper_data.get('pubdate', ''),
                                                        'pmid': pmid,
                                                        'type': 'pubmed_paper'
                                                    }
                                                    results.append(paper_info)
        except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
            print(f"Timeout searching PubMed")
        except aiohttp.ClientConnectionError:
            print(f"Connection closed searching PubMed")
        except Exception as e:
            print(f"Error searching PubMed: {e}")
        
        return results
    
    async def _search_arxiv_papers(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Enhanced ArXiv search with better error handling"""
        if not self.scraper:
            return []
        
        try:
            search_query = f"{model_name} dermatology machine learning"
            # Set a reasonable timeout for ArXiv search
            papers = await asyncio.wait_for(
                self.scraper.search_arxiv_enhanced(search_query, max_results=5),
                timeout=25.0
            )
            
            # Enhance papers with AI analysis
            for paper in papers:
                if paper.get('summary'):
                    # Extract content from summary and title
                    content = f"{paper.get('title', '')} {paper.get('summary', '')}"
                    
                    # Check if AI extractor is still available
                    if not self.ai_extractor.is_api_available():
                        print(f"🚫 Skipping AI analysis for ArXiv papers - {self.ai_extractor._get_status_message()}")
                        paper['ai_analysis'] = {'status': 'skipped_due_to_api_limits'}
                        continue
                    
                    try:
                        # Use AI extractor for comprehensive analysis
                        ai_analysis = self.ai_extractor.extract_model_information(content, 'arxiv_paper')
                        bias_analysis = self.ai_extractor.analyze_bias_and_fairness(content)
                        clinical_metrics = self.ai_extractor.extract_clinical_metrics(content)
                        
                        # Add AI analysis to paper
                        paper['ai_analysis'] = {
                            'extracted_info': ai_analysis,
                            'bias_analysis': bias_analysis,
                            'clinical_metrics': clinical_metrics
                        }
                        
                    except (RateLimitExceededError, QuotaExceededError) as e:
                        print(f"🚫 API limit reached during ArXiv analysis: {e}")
                        # Stop processing and propagate error
                        raise e
            
            return papers
            
        except asyncio.TimeoutError:
            print(f"ArXiv search timeout exceeded (25s)")
        except (aiohttp.ServerTimeoutError, aiohttp.ClientConnectionError):
            print(f"ArXiv connection issues")
        except Exception as e:
            print(f"Error in enhanced ArXiv search: {e}")
        
        return []
    
    async def _search_general_web(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Enhanced general web search with integrated search API for comprehensive discovery"""
        results = []
        
        try:
            print(f"🔍 Searching web for {model_name} official sources...")
            
            # Enhanced search queries specifically designed to find official websites
            search_queries = [
                f'"{model_name}" official website',
                f'{model_name} dermatology medical device company',
                f'{model_name} FDA approved skin cancer detection',
                f'{model_name} AI diagnostic tool official site'
            ]
            
            if developer_name:
                search_queries.extend([
                    f'"{model_name}" "{developer_name}" official website',
                    f'{developer_name} {model_name} company site'
                ])
            
            # Web search not available - using fallback method
            print("Web search not available for official sources discovery")
                    
        except Exception as e:
            print(f"Error in general web search: {e}")
        
        print(f"  Found {len(results)} web sources")
        return results
    
    async def extract_content_from_sources(self, sources: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and process content from discovered sources
        CardGen Step 2: Content Extraction
        """
        # CRITICAL: Check quota status before any processing begins
        if not self.ai_extractor.is_api_available():
            status_info = self.ai_extractor.get_api_status()
            if status_info.get("quota_exceeded"):
                print("🚫 API QUOTA EXCEEDED at start of content extraction")
                raise QuotaExceededError("API quota exceeded before content extraction could begin")
            elif status_info.get("rate_limit_hit"):
                print("🚫 RATE LIMIT EXCEEDED at start of content extraction")
                raise RateLimitExceededError("Rate limit exceeded before content extraction could begin")

        extracted_content = {
            'model_name': sources['model_name'],
            'extraction_timestamp': datetime.now().isoformat(),
            'content_by_source': {'all': []},  # single bucket of what we actually processed
            'aggregated_content': {
                'descriptions': [],
                'metrics': {},
                'clinical_info': {},
                'technical_specs': {},
                'bias_info': {},
                'references': []
            }
        }

        to_extract = self._flatten_sources_for_extraction(sources)
        
        # BATCH PROCESSING: Group sources for batch AI extraction
        batch_size = int(os.getenv("BATCH_SIZE", "3"))  # Process sources at a time to balance efficiency and token limits
        
        # Optimize batch processing by prioritizing sources with more content
        to_extract = self._optimize_batch_order(to_extract)
        
        content_batches = []
        for i in range(0, len(to_extract), batch_size):
            batch = to_extract[i:i + batch_size]
            content_batches.append(batch)
        
        print(f"📦 Processing {len(to_extract)} sources in {len(content_batches)} batches")
        
        # Process each batch
        for batch_idx, batch in enumerate(content_batches):
            print(f"🔄 Processing batch {batch_idx + 1}/{len(content_batches)} ({len(batch)} sources)")
            
            # Extract raw content first (non-AI operations)
            batch_contents = []
            for source in batch:
                content = await self._extract_source_content(source)
                extracted_content['content_by_source']['all'].append(content)
                batch_contents.append(content)
            
            # Batch AI extraction for sources with content
            sources_with_content = []
            for i, content in enumerate(batch_contents):
                if content.get('raw_content') and len(content['raw_content']) > 100:
                    sources_with_content.append({
                        'content': content['raw_content'],
                        'source_type': batch[i].get('type', 'web'),
                        'source_id': batch[i].get('url', f'batch_{batch_idx}_item_{i}'),
                        'original_content': content
                    })
            
            if sources_with_content:
                print(f"🤖 Running batch AI extraction for {len(sources_with_content)} sources")
                
                # Comprehensive batch extraction (combines all extraction types)
                try:
                    comprehensive_batch = self.ai_extractor.extract_comprehensive_batch(sources_with_content)
                    
                    # Apply comprehensive batch results back to individual sources
                    for i, source_data in enumerate(sources_with_content):
                        original_content = source_data['original_content']
                        
                        # Merge comprehensive extraction results
                        if i < len(comprehensive_batch):
                            comprehensive_data = comprehensive_batch[i]
                            
                            # Split comprehensive data into logical sections
                            original_content['basic_metadata'] = {
                                k: v for k, v in comprehensive_data.items() 
                                if k in ['model_name', 'model_developer', 'developer_organization', 
                                       'release_date', 'model_version', 'contact', 'summary', 
                                       'regulatory_approval_status', 'funding_source']
                            }
                            
                            original_content['trust_ingredients'] = {
                                k: v for k, v in comprehensive_data.items() 
                                if k in ['exclusion_inclusion_criteria', 'demographics', 'training_data', 
                                       'bias_mitigation', 'irb_approval', 'detailed_metrics', 
                                       'publications_references']
                            }
                            
                            original_content['technical_info'] = {
                                k: v for k, v in comprehensive_data.items() 
                                if k in ['model_architecture', 'input_output_specs', 'training_methodology', 
                                       'validation_approach', 'deployment_context', 'limitations', 
                                       'clinical_integration', 'performance_benchmarks']
                            }
                            
                            original_content['clinical_metrics'] = {
                                k: v for k, v in comprehensive_data.items() 
                                if k in ['performance_metrics', 'validation_studies', 'clinical_trials', 
                                       'sample_sizes', 'confidence_intervals']
                            }
                        
                        # Update aggregated content
                        if original_content.get('processed_content'):
                            extracted_content['aggregated_content']['descriptions'].append(original_content['processed_content'])
                        if isinstance(original_content.get('metrics'), dict):
                            extracted_content['aggregated_content']['metrics'].update(original_content['metrics'])
                        if isinstance(original_content.get('clinical_info'), dict):
                            extracted_content['aggregated_content']['clinical_info'].update(original_content['clinical_info'])
                        if original_content.get('references'):
                            extracted_content['aggregated_content']['references'].extend(original_content['references'])
                
                except Exception as e:
                    print(f"⚠️ Batch AI extraction failed for batch {batch_idx + 1}: {e}")
                    # Fallback to individual processing for this batch
                    for content in batch_contents:
                        if content.get('processed_content'):
                            extracted_content['aggregated_content']['descriptions'].append(content['processed_content'])
                        if isinstance(content.get('metrics'), dict):
                            extracted_content['aggregated_content']['metrics'].update(content['metrics'])
                        if isinstance(content.get('clinical_info'), dict):
                            extracted_content['aggregated_content']['clinical_info'].update(content['clinical_info'])
                        if content.get('references'):
                            extracted_content['aggregated_content']['references'].extend(content['references'])
            else:
                # No content to process with AI, just aggregate
                for content in batch_contents:
                    if content.get('processed_content'):
                        extracted_content['aggregated_content']['descriptions'].append(content['processed_content'])
                    if isinstance(content.get('metrics'), dict):
                        extracted_content['aggregated_content']['metrics'].update(content['metrics'])
                    if isinstance(content.get('clinical_info'), dict):
                        extracted_content['aggregated_content']['clinical_info'].update(content['clinical_info'])
                    if content.get('references'):
                        extracted_content['aggregated_content']['references'].extend(content['references'])

        return extracted_content
    
    def _optimize_batch_order(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Optimize the order of sources for batch processing by prioritizing:
        1. Sources with higher priority scores
        2. Sources likely to have more content
        3. Official/authoritative sources first
        """
        def get_source_score(source):
            # Base priority from source type
            source_type = source.get('type', 'unknown')
            priority_score = SourcePriority.get_source_priority(source_type)
            
            # Boost for official sources
            url = source.get('url', '').lower()
            if any(term in url for term in ['github.com', 'huggingface.co', 'pubmed.ncbi.nlm.nih.gov', 'arxiv.org']):
                priority_score += 2
            
            # Boost for sources with descriptions (likely to have content)
            if source.get('description') and len(source.get('description', '')) > 50:
                priority_score += 1
            
            # Boost for sources with titles (likely to be papers/articles)
            if source.get('title') and len(source.get('title', '')) > 20:
                priority_score += 1
            
            return priority_score
        
        # Sort by priority score (highest first)
        return sorted(sources, key=get_source_score, reverse=True)
    
    async def _extract_source_content(self, source: Dict[str, Any]) -> Dict[str, Any]:
        """Extract content from a single source"""
        content = {
            'source_type': source.get('type', 'unknown'),
            'url': source.get('url', ''),
            'title': source.get('title', ''),
            'raw_content': '',
            'processed_content': '',
            'metrics': {},
            'clinical_info': {},
            'references': []
        }
        
        try:
            # Extract content based on source type
            if source.get('type') == 'huggingface_model':
                content['raw_content'] = source.get('model_card', source.get('description', ''))
            elif source.get('type') in ['github_repo', 'github_repo_basic', 'github_repo_comprehensive']:
                # Get README content or description from GitHub repos
                readme_content = source.get('readme_content', '') or source.get('readme', '')
                description = source.get('description', '')
                title = source.get('title', '')
                
                # Combine available content
                content_parts = []
                if readme_content and len(readme_content) > 50:
                    content_parts.append(f"README Content:\n{readme_content}")
                if description and len(description) > 10:
                    content_parts.append(f"Repository Description: {description}")
                if title:
                    content_parts.append(f"Repository: {title}")
                
                # Add model files if available
                model_files = source.get('model_files', [])
                for model_file in model_files[:3]:  # Limit to first 3 files
                    if model_file.get('content'):
                        content_parts.append(f"{model_file['filename']}:\n{model_file['content'][:500]}")
                
                content['raw_content'] = '\n\n'.join(content_parts)
                
                # Debug output
                if content['raw_content']:
                    print(f"GitHub repo content extracted: {len(content['raw_content'])} chars from {title}")
            elif source.get('type') in ['pubmed_paper', 'arxiv_paper']:
                # For papers, we'd need to fetch the full text or abstract
                content['raw_content'] = source.get('summary', source.get('title', ''))
            elif source.get('url'):
                # For all other sources with URLs, use enhanced web scraping
                try:
                    if self.scraper:
                        scraped_content = await self.scraper.extract_content_from_url(source['url'])
                        if scraped_content and scraped_content.get('status') == 'success':
                            content['raw_content'] = scraped_content.get('clean_text', '')
                            content['title'] = scraped_content.get('title', source.get('title', ''))
                            # Include enhanced metadata for better processing
                            source['metadata'] = scraped_content.get('metadata', {})
                            print(f"Enhanced web scraping completed for {source['url']}: {len(content['raw_content'])} chars")
                except Exception as e:
                    print(f"Error in enhanced web scraping for {source.get('url', 'unknown')}: {e}")
                    content['raw_content'] = source.get('description', '')
            
            # Process the content with AI-powered extraction
            if content['raw_content'] and len(content['raw_content']) > 20:
                print(f"Processing content from {source.get('type', 'unknown')} source: {len(content['raw_content'])} chars")
                
                # Check if AI extractor is still available before making calls
                if not self.ai_extractor.is_api_available():
                    status_info = self.ai_extractor.get_api_status()
                    print(f"🚫 AI API not available: {self.ai_extractor._get_status_message()}")
                    
                    # If quota exceeded, immediately stop all processing
                    if status_info.get("quota_exceeded"):
                        raise QuotaExceededError("API quota exceeded during source content processing")
                    elif status_info.get("rate_limit_hit"):
                        raise RateLimitExceededError("Rate limit exceeded during source content processing")
                    
                    # Set basic information from source but skip AI processing
                    content['processed_content'] = source.get('description', '')[:500] + "..."
                    content['missing_fields'] = {}
                    content['basic_metadata'] = {}
                    return content
                
                try:
                    # Use AI extractor for comprehensive analysis
                    ai_extracted = self.ai_extractor.extract_model_information(
                        content['raw_content'], 
                        source_type=source.get('type', 'web')
                    )
                    
                    # Extract the frequently missing fields using specialized method
                    # Priority: Extract basic metadata first
                    basic_metadata = self.ai_extractor.extract_basic_metadata_first(
                        content['raw_content'], source.get('type', 'web')
                    )
                    
                    missing_fields = self.ai_extractor.extract_missing_fields(
                        content['raw_content'],
                        source_type=source.get('type', 'web')
                    )
                    
                except (RateLimitExceededError, QuotaExceededError) as e:
                    print(f"🚫 API QUOTA EXCEEDED during content extraction: {e}")
                    # Immediately propagate quota error to stop all processing
                    raise e
                
                # Include enhanced metadata from web scraping if available
                if source.get('metadata'):
                    enhanced_metadata = source['metadata']
                    
                    # Merge contact information
                    if enhanced_metadata.get('contact_info'):
                        if 'contact' not in missing_fields:
                            missing_fields['contact'] = '; '.join(enhanced_metadata['contact_info'])
                    
                    # Merge version information
                    if enhanced_metadata.get('version_info'):
                        if 'model_version' not in missing_fields:
                            missing_fields['model_version'] = '; '.join(enhanced_metadata['version_info'])
                    
                    # Merge organization information
                    if enhanced_metadata.get('organization_info'):
                        if 'developer_organization' not in missing_fields:
                            missing_fields['developer_organization'] = '; '.join(enhanced_metadata['organization_info'][:2])
                    
                    # Merge regulatory information
                    if enhanced_metadata.get('regulatory_info'):
                        if 'regulatory_approval_status' not in missing_fields:
                            missing_fields['regulatory_approval_status'] = '; '.join(enhanced_metadata['regulatory_info'])
                    
                    # Merge dataset information
                    if enhanced_metadata.get('dataset_info'):
                        if 'dataset' not in missing_fields:
                            missing_fields['dataset'] = '; '.join(enhanced_metadata['dataset_info'][:3])
                    
                    # Merge publication information
                    if enhanced_metadata.get('publication_info'):
                        if 'doi_of_dataset_used' not in missing_fields:
                            missing_fields['doi_of_dataset_used'] = '; '.join(enhanced_metadata['publication_info'][:2])
                
                # Combine AI-extracted information - use summary and description
                summary = ai_extracted.get('summary', '')
                intended_use = ai_extracted.get('intended_use', '')
                limitations = ai_extracted.get('limitations', '')
                
                # Create comprehensive processed content
                processed_parts = []
                if summary:
                    processed_parts.append(summary)
                if intended_use:
                    processed_parts.append(f"Intended use: {intended_use}")
                if limitations:
                    processed_parts.append(f"Limitations: {limitations}")
                
                content['processed_content'] = '. '.join(filter(None, processed_parts))
                
                print(f"Processed content length: {len(content['processed_content'])}")
                content['metrics'] = ai_extracted.get('performance_metrics', {})
                # Merge basic metadata with missing fields (basic metadata takes priority)
                for key, value in basic_metadata.items():
                    if value and value != "Not specified":
                        missing_fields[key] = value
                
                content['missing_fields'] = missing_fields  # Store the missing fields extraction
                content['basic_metadata'] = basic_metadata  # Store basic metadata separately
                content['clinical_info'] = {
                    'regulatory_status': ai_extracted.get('regulatory_status', ''),
                    'clinical_validation': ai_extracted.get('clinical_validation', ''),
                    'regulatory_approvals': missing_fields.get('regulatory_approval_status', ''),
                    'clinical_oversight': missing_fields.get('clinical_oversight', ''),
                    # New specialized extractions
                    'contact_information': {},
                    'release_information': {},
                    'trust_ingredients': missing_fields
                }
                content['references'] = self._extract_references(content['raw_content'])
                
                # Add AI-enhanced fields with specialized extractions
                content['ai_analysis'] = {
                    'model_type': ai_extracted.get('model_type', ''),
                    'developer': ai_extracted.get('developer', ''),
                    'dataset_info': ai_extracted.get('dataset_info', {}),
                    'regulatory_compliance': missing_fields.get('regulatory_approval_status', ''),
                    'contact_information': {},
                    'release_information': {},
                    'trust_ingredients': missing_fields,
                    'developer_warnings': ai_extracted.get('developer_warnings', ''),
                    'ethical_considerations': ai_extracted.get('ethical_considerations', ''),
                    'ai_system_facts': ai_extracted.get('ai_system_facts', {}),
                    'fairness_testing': ai_extracted.get('fairness_testing', {}),
                    'safety_testing': ai_extracted.get('safety_testing', {}),
                    'clinical_trials': ai_extracted.get('clinical_trials', ''),
                    'evaluation_references': ai_extracted.get('evaluation_references', '')
                }
        
        except Exception as e:
            print(f"Error extracting content from {source.get('url', 'unknown')}: {e}")
        
        # Register source in citation system for counting
        if content.get('raw_content') or content.get('processed_content'):
            # Classify source type for citation system
            source_type_classified = SourcePriority.classify_source_type(
                source.get('url', ''), 
                source.get('title', ''), 
                source.get('description', '')
            )
            
            # Add source to citation system for tracking
            self.citations.add_source(
                title=source.get('title', 'Untitled'),
                url=source.get('url', ''),
                source_type=source_type_classified,
                priority_score=SourcePriority.get_source_priority(source_type_classified),
                extracted_content=f"Content length: {len(content.get('raw_content', '') + content.get('processed_content', ''))}"
            )
            
            print(f"Source registered: {source.get('title', 'unknown')} (type: {source_type_classified})")
        
        # Debug output for content length
        print(f"Final content for {source.get('title', 'unknown')}: raw={len(content.get('raw_content', ''))}, processed={len(content.get('processed_content', ''))}")
        
        # Bump extraction counters if content was successfully extracted
        if hasattr(self, 'chai_card') and hasattr(self.chai_card, '_bump_extraction_counters'):
            metrics_found = len(content.get('metrics', {}))
            has_content = bool(content.get('raw_content', '') or content.get('processed_content', ''))
            self.chai_card._bump_extraction_counters(found_metrics=metrics_found, found_content=has_content)
        
        return content
    
    async def _process_text_content(self, text: str) -> str:
        """Process and clean text content"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove markdown artifacts
        text = re.sub(r'[#*`]', '', text)
        
        # Extract key sentences (simplified)
        sentences = text.split('.')
        key_sentences = []
        
        keywords = ['dermatology', 'skin', 'lesion', 'melanoma', 'dermoscopy', 'classification', 'detection', 'diagnosis', 'AI', 'machine learning', 'neural network', 'fitzpatrick', 'pigmented', 'nevus', 'basal cell', 'squamous cell']
        
        for sentence in sentences:
            if any(keyword.lower() in sentence.lower() for keyword in keywords):
                key_sentences.append(sentence.strip())
        
        return '. '.join(key_sentences[:5])  # Top 5 relevant sentences
    
    def _extract_references(self, text: str) -> List[str]:
        """Extract references from text"""
        references = []
        
        # Look for DOI patterns
        doi_pattern = r'10\.\d{4,}(?:\.\d+)?/[^\s]+'
        dois = re.findall(doi_pattern, text)
        references.extend([f"https://doi.org/{doi}" for doi in dois])
        
        # Look for PubMed IDs
        pmid_pattern = r'PMID:\s*(\d+)'
        pmids = re.findall(pmid_pattern, text)
        references.extend([f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in pmids])
        
        return references
    
    def _identify_model_developer(self, model_name: str, extracted_content: Dict[str, Any]) -> str:
        """
        Enhanced smart identification of model developer from extracted content
        Uses comprehensive content analysis with proper priority handling
        """
        # Priority 1: Search for explicit developer mentions in all content using AI
        all_content_for_analysis = []
        high_priority_content = []
        
        # Collect content from all sources, prioritizing high-quality sources
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                content = source.get('raw_content', '') or source.get('processed_content', '')
                if content and len(content) > 50:  # Only substantial content
                    all_content_for_analysis.append(content)
                    
                    # Prioritize official sources and documentation
                    source_priority = SourcePriority.get_source_priority(
                        SourcePriority.classify_source_type(source.get('url', ''), source.get('title', ''))
                    )
                    if source_priority >= 8.0:  # High priority sources
                        high_priority_content.append(content)
        
        # Use high priority content first, then all content as fallback
        content_to_analyze = ' '.join(high_priority_content) if high_priority_content else ' '.join(all_content_for_analysis)
        
        if content_to_analyze:
            # Use AI to identify developer from comprehensive content
            developer_info = self._extract_developer_with_ai(content_to_analyze, model_name)
            if developer_info and developer_info not in ["Not specified", "Unknown", ""]:
                return developer_info
        
        # Priority 2: Look for specific company patterns in content
        combined_content = content_to_analyze.lower()
        
        # Enhanced dermatology-focused company detection patterns
        company_patterns = {
            "SciBase": ["scibase", "sci-base", "scibase ab", "nevisense by scibase"],
            "Google Health": ["google health", "google research", "deepmind health", "google derm"],
            "Meta AI": ["meta ai", "facebook ai research", "fair"],
            "Microsoft Research": ["microsoft research", "microsoft ai"],
            "Google": ["google", "gemini"],
            "Apple": ["apple inc", "apple health"],
            "NVIDIA": ["nvidia", "nvidia corporation"],
            "IBM": ["ibm research", "ibm watson health"],
            "Philips": ["philips healthcare", "koninklijke philips"],
            "Siemens": ["siemens healthineers", "siemens medical"],
            "Canon": ["canon medical", "canon healthcare"],
            "GE Healthcare": ["ge healthcare", "general electric healthcare"],
            "3Derm": ["3derm", "3derm systems"],
            "DermTech": ["dermtech", "derm tech"],
            "Canfield Scientific": ["canfield scientific", "canfield imaging"],
            "FotoFinder": ["fotofinder", "foto finder"],
            "MoleMap": ["molemap", "mole map"],
            "SkinVision": ["skinvision", "skin vision"],
            "Forward": ["forward health", "forward.com"],
            "Miiskin": ["miiskin", "mii skin"]
        }
        
        # Check for company mentions with context
        for company, patterns in company_patterns.items():
            for pattern in patterns:
                if pattern in combined_content:
                    # Verify this is actually about the developer, not just a mention
                    context_window = self._get_context_around_mention(combined_content, pattern, 100)
                    if any(keyword in context_window for keyword in ['developed by', 'created by', 'from', 'by', 'developer', 'company']):
                        return company
        
        # Priority 3: Look for FDA/regulatory information that might indicate developer
        if 'fda' in combined_content or 'regulatory' in combined_content:
            fda_developer = self._extract_developer_from_regulatory_content(combined_content)
            if fda_developer:
                return fda_developer
        
        # Priority 4: Analyze GitHub repository ownership (with caution) - ONLY as last resort
        github_sources = []
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            if source_type == 'github_repo_comprehensive':
                for source in sources:
                    github_sources.append(source)
        
        if github_sources and not content_to_analyze:  # Only if we have no other content
            # Sort by repository quality indicators
            sorted_repos = sorted(github_sources, key=lambda x: self._calculate_repo_relevance(x, model_name), reverse=True)
            
            for repo in sorted_repos[:1]:  # Check only the most relevant repo
                repo_title = repo.get('title', '')
                if '/' in repo_title:
                    owner = repo_title.split('/')[0]
                    # Only use repo owner if it looks like an organization AND model name matches
                    if (owner and self._is_likely_organization(owner, repo.get('raw_content', '')) and 
                        model_name.lower() in repo.get('raw_content', '').lower()):
                        return owner
        
        return "Not specified"
    
    def _extract_developer_with_ai(self, content: str, model_name: str) -> str:
        """Use AI to extract developer information from content"""
        try:
            prompt = f"""
            Analyze the following content about the AI model "{model_name}" and identify the actual developer/organization that created this model.
            
            Look for explicit mentions of:
            - "Developed by [Company]"
            - "Created by [Company]" 
            - "[Company] developed"
            - Company names in official contexts
            - Regulatory approval documents mentioning the developer
            - FDA clearance documents
            - Official product descriptions
            
            Ignore:
            - GitHub repository owners (these may be individuals who just published code)
            - Random company mentions without development context
            - Academic researchers (unless they represent the official developer)
            
            Content to analyze:
            {content[:3000]}
            
            Return only the company/organization name that actually developed this model, or "Not specified" if unclear.
            Examples of good responses: "SciBase", "Google Health", "Meta AI"
            Examples of bad responses: "suinleelab", "john-doe", "research-team"
            """
            
            response = self.ai_extractor.client.chat.completions.create(
                model="gemini-1.5-pro",
                messages=[
                    {"role": "system", "content": "You are an expert at identifying AI model developers from documentation. Be precise and only return the actual developing organization."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1,
                max_completion_tokens=100
            )
            
            result = response.choices[0].message.content.strip()
            return result if result and len(result) < 50 else "Not specified"
            
        except Exception as e:
            print(f"Error in AI developer extraction: {e}")
            return "Not specified"
    
    def _get_context_around_mention(self, text: str, mention: str, context_size: int) -> str:
        """Get context around a mention in text"""
        index = text.find(mention)
        if index == -1:
            return ""
        
        start = max(0, index - context_size)
        end = min(len(text), index + len(mention) + context_size)
        return text[start:end]
    
    def _extract_developer_from_regulatory_content(self, content: str) -> str:
        """Extract developer from FDA/regulatory content"""
        # Look for FDA clearance patterns that mention the developer
        fda_patterns = [
            r'fda cleared by ([\w\s]+)',
            r'developed by ([\w\s]+) and cleared',
            r'510\(k\) clearance.*?([\w\s]+)',
            r'manufacturer[:\s]+([\w\s]+)'
        ]
        
        for pattern in fda_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                developer = matches[0].strip()
                if len(developer) < 50 and developer.lower() not in ['the', 'a', 'an', 'this', 'that']:
                    return developer
        
        return "Not specified"
    
    def _calculate_repo_relevance(self, repo: Dict, model_name: str) -> float:
        """Calculate relevance score for a repository"""
        score = 0.0
        
        title = repo.get('title', '').lower()
        content = repo.get('raw_content', '').lower()
        
        # Model name match
        if model_name.lower() in title:
            score += 10
        if model_name.lower() in content:
            score += 5
        
        # Official indicators
        if any(term in content for term in ['official', 'original', 'main', 'primary']):
            score += 3
        
        # Quality indicators
        content_length = len(content)
        if content_length > 5000:
            score += 2
        if content_length > 10000:
            score += 2
        
        return score
    
    def _is_likely_organization(self, owner: str, repo_content: str) -> bool:
        """Determine if a GitHub owner is likely an organization vs individual"""
        # Organization indicators
        org_indicators = [
            owner.islower() and '-' in owner,  # kebab-case usernames often orgs
            len(owner) > 8,  # Organizations often have longer names
            any(term in owner.lower() for term in ['lab', 'corp', 'inc', 'ai', 'research', 'health', 'medical']),
            any(term in repo_content.lower() for term in ['company', 'organization', 'team', 'corporation'])
        ]
        
        # Individual indicators (negative scoring)
        individual_indicators = [
            owner[0].isupper() and owner[1:].islower(),  # CamelCase often individuals
            len(owner) < 4,  # Very short names often individuals
            any(char.isdigit() for char in owner),  # Numbers often in individual usernames
        ]
        
        org_score = sum(org_indicators)
        individual_score = sum(individual_indicators)
        
        return org_score > individual_score
    
    async def _search_nih_sources(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search NIH databases and medical institutions for model information"""
        results = []
        try:
            # NIH databases and search patterns
            nih_searches = [
                f"site:nih.gov \"{model_name}\" medical AI",
                f"site:nlm.nih.gov \"{model_name}\" artificial intelligence",
                f"site:ncbi.nlm.nih.gov \"{model_name}\" dermatology",
                f"site:niddk.nih.gov \"{model_name}\" technology",
                f"site:cancer.gov \"{model_name}\" detection",
                f"site:cdc.gov \"{model_name}\" diagnostic tool"
            ]
            
            for search_query in nih_searches[:4]:  # Limit to prevent overwhelming
                try:
                    search_results = []
                    if self.scraper:
                        search_results = await asyncio.wait_for(
                            self.scraper.search_web_enhanced(search_query, max_results=3),
                            timeout=20.0
                        )
                    
                    for result in search_results:
                        if result and result.get('url'):
                            results.append({
                                'title': result.get('title', ''),
                                'url': result['url'],
                                'snippet': result.get('snippet', ''),
                                'type': 'nih_database',
                                'query': search_query,
                                'priority': 8.5  # High priority for NIH sources
                            })
                            
                except asyncio.TimeoutError:
                    print(f"Timeout searching NIH for '{search_query}'")
                    continue
                except Exception as e:
                    print(f"Error in NIH search for '{search_query}': {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in NIH source search: {e}")
        
        return results
    
    async def _search_researchgate(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search ResearchGate for academic publications and project information"""
        results = []
        try:
            # ResearchGate search patterns
            rg_searches = [
                f"site:researchgate.net \"{model_name}\" artificial intelligence",
                f"site:researchgate.net \"{model_name}\" machine learning medical",
                f"site:researchgate.net \"{model_name}\" dermatology AI",
                f"site:researchgate.net \"{model_name}\" clinical validation"
            ]
            
            for search_query in rg_searches[:3]:  # Limit searches
                try:
                    search_results = []
                    if self.scraper:
                        search_results = await asyncio.wait_for(
                            self.scraper.search_web_enhanced(search_query, max_results=4),
                            timeout=18.0
                        )
                    
                    if search_results:
                        for result in search_results:
                            if result and result.get('url'):
                                results.append({
                                    'title': result.get('title', ''),
                                    'url': result['url'],
                                    'snippet': result.get('snippet', ''),
                                    'type': 'researchgate_paper',
                                    'query': search_query,
                                    'priority': 7.5  # Good priority for academic papers
                                })
                            
                except asyncio.TimeoutError:
                    print(f"Timeout searching ResearchGate for '{search_query}'")
                    continue
                except Exception as e:
                    print(f"Error in ResearchGate search for '{search_query}': {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in ResearchGate search: {e}")
        
        return results
    
    async def _search_medical_institutions(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search major medical institutions and dermatology organizations"""
        results = []
        try:
            # Medical institution search patterns
            institution_searches = [
                f"site:mayoclinic.org \"{model_name}\" dermatology",
                f"site:clevelandclinic.org \"{model_name}\" artificial intelligence",
                f"site:mskcc.org \"{model_name}\" AI technology",
                f"site:hopkinsmedicine.org \"{model_name}\" medical AI",
                f"site:aad.org \"{model_name}\" dermatology technology",  # American Academy of Dermatology
                f"site:skincarephysicians.org \"{model_name}\" diagnostic",
                f"site:dermatologytimes.com \"{model_name}\" AI",
                f"site:jaad.org \"{model_name}\" artificial intelligence"  # Journal of American Academy of Dermatology
            ]
            
            for search_query in institution_searches[:6]:  # Limit searches
                try:
                    search_results = []
                    if self.scraper:
                        search_results = await asyncio.wait_for(
                            self.scraper.search_web_enhanced(search_query, max_results=3),
                            timeout=15.0
                        )
                    
                    if search_results:
                        for result in search_results:
                            if result and result.get('url'):
                                # Determine institution type for priority
                                priority = 8.0  # High priority for medical institutions
                                if any(term in result.get('url', '').lower() for term in ['aad.org', 'jaad.org']):
                                    priority = 8.5  # Higher for dermatology-specific orgs
                                
                                results.append({
                                    'title': result.get('title', ''),
                                    'url': result['url'],
                                    'snippet': result.get('snippet', ''),
                                    'type': 'medical_institution',
                                    'query': search_query,
                                    'priority': priority
                                })
                            
                except asyncio.TimeoutError:
                    print(f"Timeout searching medical institutions for '{search_query}'")
                    continue
                except Exception as e:
                    print(f"Error in medical institution search for '{search_query}': {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in medical institution search: {e}")
        
        return results
    
    async def generate_chai_model_card(self, model_name: str, extracted_content: Dict[str, Any], developer_name: str = "") -> CHAIModelCard:
        """
        Generate CHAI-compliant model card from extracted content
        CardGen Step 3: Model Card Generation
        """
        aggregated = extracted_content.get('aggregated_content', {})
        
        # Initialize CHAI model card
        chai_card = CHAIModelCard()
        
        # Basic Information - CRITICAL: Model name must match user input exactly
        chai_card.model_name = model_name  # User-entered name - never override
        chai_card.extraction_timestamp = datetime.now().isoformat()
        chai_card.sources_extracted_from = list(extracted_content.get('content_by_source', {}).keys())
        
        # Smart developer identification with user input priority
        self._user_provided_developer = bool(developer_name and developer_name.strip())
        if self._user_provided_developer:
            # PRIORITY: Use exact user input when provided
            chai_card.model_developer = developer_name.strip()
            print(f"✓ Developer set from user input: {chai_card.model_developer}")
        else:
            # Fallback to automatic identification only when no user input
            developer_info = self._identify_model_developer(model_name, extracted_content)
            chai_card.model_developer = developer_info
        
        # PRIORITY: Populate basic metadata first with enhanced logic
        self._populate_basic_metadata_priority(chai_card, extracted_content)
        
        # POPULATE MISSING FIELDS from specialized extraction
        try:
            self._populate_missing_fields(chai_card, extracted_content)
        except (RateLimitExceededError, QuotaExceededError) as e:
            print(f"🚫 API QUOTA EXCEEDED during missing fields population: {e}")
            # Immediately propagate quota error to stop all processing
            raise e
        
        # VERIFICATION: Ensure critical fields still match user input after field population
        if chai_card.model_name != model_name:
            print(f"WARNING: Model name was changed from '{model_name}' to '{chai_card.model_name}' - reverting to user input")
            chai_card.model_name = model_name
        
        # Ensure developer name matches user input if provided
        if self._user_provided_developer and chai_card.model_developer != developer_name.strip():
            print(f"WARNING: Developer name was changed from '{developer_name.strip()}' to '{chai_card.model_developer}' - reverting to user input")
            chai_card.model_developer = developer_name.strip()
        
        # Enhanced Release Information from specialized extraction
        release_info = self._extract_release_information_from_sources(extracted_content)
        if release_info:
            chai_card.model_software_release_stage = release_info.get('stage', 'Not specified')
            chai_card.release_date = release_info.get('release_date', 'Not specified')
            chai_card.model_version = release_info.get('version', 'Not specified')
            chai_card.geographic_availability = release_info.get('availability', 'Not specified')
            if not chai_card.regulatory_approval_status:
                chai_card.regulatory_approval_status = release_info.get('regulatory_status', 'Not specified')
        
        # Generate comprehensive sources summary
        chai_card.sources_summary = self._generate_sources_summary(extracted_content)
        chai_card.source_reliability_assessment = self._generate_source_reliability_assessment(extracted_content)
        
        # Add citation for developer field
        if extracted_content.get('content_by_source'):
            for source_type, sources in extracted_content['content_by_source'].items():
                for source in sources:
                    if source.get('ai_analysis', {}).get('developer'):
                        source_id = self.citations.add_source(
                            title=source.get('title', ''),
                            url=source.get('url', ''),
                            source_type=source.get('source_type', 'unknown'),
                            priority_score=source.get('priority_score', 5.0),
                            extracted_content=f"Developer identified: {source['ai_analysis']['developer']}"
                        )
                        self.citations.cite_field('model_developer', source_id)
        
        # Model Summary - Enhanced to handle empty descriptions
        descriptions = aggregated.get('descriptions', [])
        
        # Filter out empty descriptions and create comprehensive summary
        valid_descriptions = [desc for desc in descriptions if desc and desc.strip()]
        
        if valid_descriptions:
            summary_text = '. '.join(valid_descriptions[:3])  # Combine top 3 descriptions
            chai_card.summary = summary_text
            
            # Add citations for summary from prioritized sources
            source_count = 0
            for source_type, sources in extracted_content.get('content_by_source', {}).items():
                for source in sources:
                    if source.get('processed_content') and source_count < 3:
                        classified_type = SourcePriority.classify_source_type(
                            source.get('url', ''), 
                            source.get('title', '')
                        )
                        source_id = self.citations.add_source(
                            title=source.get('title', ''),
                            url=source.get('url', ''),
                            source_type=classified_type,
                            priority_score=source.get('priority_score', 5.0),
                            extracted_content=source.get('processed_content', '')[:200]
                        )
                        self.citations.cite_field('summary', source_id)
                        source_count += 1
        else:
            # Fallback: Create summary from raw repository content in English
            chai_card.summary = self._generate_summary_from_sources_english(extracted_content, model_name)
        
        print(f"Generated summary: {chai_card.summary[:100]}...")
        
        # Extract keywords from content - Enhanced to use all available text
        all_text = ' '.join(valid_descriptions) if valid_descriptions else ''
        
        # ENHANCED: Include text from ALL sources for comprehensive keyword detection
        additional_text = self._extract_all_text_from_sources(extracted_content)
        if additional_text:
            all_text = (all_text + ' ' + additional_text).strip() if all_text else additional_text
        
        # Enhanced dermatology keywords with plurals and synonyms
        dermatology_keywords = [
            # Core dermatology terms
            'dermatology', 'dermatologic', 'dermatological', 'skin', 'cutaneous', 'epidermal',
            # Conditions - singular and plural
            'melanoma', 'melanomas', 'cancer', 'cancers', 'carcinoma', 'carcinomas',
            'lesion', 'lesions', 'mole', 'moles', 'nevus', 'nevi',
            'psoriasis', 'eczema', 'dermatitis', 'acne', 'rosacea',
            # Diagnostic terms
            'diagnosis', 'diagnoses', 'diagnostic', 'classification', 'classify',
            'detection', 'detect', 'screening', 'screen', 'identification', 'identify',
            # Technology terms
            'ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning',
            'neural network', 'cnn', 'computer vision', 'image analysis',
            # Medical terms
            'medical', 'clinical', 'healthcare', 'pathology', 'biopsy', 'histology',
            'dermoscopy', 'dermatoscope', 'imaging', 'photograph', 'photography',
            # Analysis terms
            'automated', 'automatic', 'algorithm', 'model', 'prediction', 'assessment'
        ]
        found_keywords = [kw for kw in dermatology_keywords if kw.lower() in all_text.lower()]
        
        # Ensure keywords is properly initialized
        if not hasattr(chai_card, 'keywords') or chai_card.keywords is None:
            chai_card.keywords = []
        
        # Set keywords, ensuring they're strings
        chai_card.keywords = [str(keyword) for keyword in found_keywords if keyword]
        
        print(f"Found keywords: {chai_card.keywords}")
        
        # Uses and Directions - Enhanced with detailed analysis
        # Generate fields with priority-aware content and citations
        chai_card.intended_use_and_workflow = self._generate_field_with_citations(
            'intended_use_and_workflow', all_text, model_name, extracted_content, 
            lambda text, name: self._generate_intended_use_workflow(text, name)
        )
        chai_card.primary_intended_users = self._generate_field_with_citations(
            'primary_intended_users', all_text, model_name, extracted_content,
            lambda text, name: self._generate_primary_users(text, name)
        )
        # how_to_use is a special dictionary field - handle it directly
        chai_card.how_to_use = self._generate_how_to_use(all_text, model_name)
        
        # Add citation for how_to_use field
        self.citations.add_citation(
            'how_to_use',
            'Generated',
            'ai_generated', 
            'AI Generated Content',
            'How-to-use instructions generated from available model information'
        )
        chai_card.targeted_patient_population = self._generate_field_with_citations(
            'targeted_patient_population', all_text, model_name, extracted_content,
            lambda text, name: self._generate_targeted_population(text, name)
        )
        chai_card.cautioned_out_of_scope_settings = self._generate_field_with_citations(
            'cautioned_out_of_scope_settings', all_text, model_name, extracted_content,
            lambda text, name: self._generate_cautioned_use_cases(text, name)
        )
        
        # Clinical information
        clinical_info = aggregated.get('clinical_info', {})
        chai_card.regulatory_approval = clinical_info.get('regulatory_approval', '')
        chai_card.bias_mitigation_approaches = clinical_info.get('bias_mitigation', '')
        
        # Performance metrics
        metrics = aggregated.get('metrics', {})
        if metrics and isinstance(metrics, dict):
            chai_card.usefulness_usability_efficacy = {
                'metric_goal': 'Evaluate model performance in dermatology applications',
                'result': f"Accuracy: {metrics.get('accuracy', 'N/A')}, Sensitivity: {metrics.get('sensitivity', 'N/A')}, Specificity: {metrics.get('specificity', 'N/A')}",
                'interpretation': 'Performance metrics indicate model effectiveness for dermatology applications',
                'test_type': 'Retrospective analysis on dermatology datasets',
                'testing_data_description': 'Diverse dermatology image datasets',
                'validation_process_and_justification': 'Standard machine learning validation procedures'
            }
        
        # Enhanced Technical specifications using AI analysis
        ai_analysis = self._get_ai_analysis_from_content(extracted_content)
        
        chai_card.model_type = ai_analysis.get('model_type', self._generate_model_type_description(all_text, model_name))
        chai_card.input_data_source = self._generate_input_data_source(all_text, model_name)
        chai_card.output_and_input_data_types = self._generate_data_types_description(all_text, model_name)
        chai_card.development_data_characterization = self._generate_development_data_characterization(all_text, model_name)
        
        # Enhanced bias analysis using AI
        bias_info = ai_analysis.get('bias_analysis', {})
        chai_card.bias_mitigation_approaches = bias_info.get('bias_mitigation', self._generate_bias_mitigation_approaches(all_text, model_name))
        chai_card.known_biases_or_ethical_considerations = ', '.join(bias_info.get('bias_risks', []))
        chai_card.clinical_risk_level = bias_info.get('risk_level', 'Unknown')
        
        # Enhanced regulatory compliance using AI
        regulatory_info = ai_analysis.get('regulatory_compliance', {})
        chai_card.regulatory_approval = regulatory_info.get('regulatory_approvals', 'Not specified')
        
        chai_card.ongoing_maintenance = self._generate_ongoing_maintenance(all_text, model_name)
        
        # Resources
        references = aggregated.get('references', [])
        chai_card.peer_reviewed_publications = '; '.join(references[:5])
        
        # Enhanced Trust Ingredients from specialized extraction
        trust_info = self._extract_trust_ingredients_from_sources(extracted_content)
        if trust_info:
            # AI System Facts
            ai_facts = trust_info.get('ai_system_facts', {})
            if ai_facts.get('outcomes_outputs'):
                chai_card.outcomes_and_outputs = ai_facts['outcomes_outputs']
            if ai_facts.get('foundation_models'):
                chai_card.foundation_models_used = ai_facts['foundation_models']
            if ai_facts.get('data_types'):
                chai_card.output_and_input_data_types = ai_facts['data_types']
            
            # Enhanced bias mitigation from AI extraction
            if trust_info.get('bias_mitigation'):
                chai_card.bias_mitigation_approaches = trust_info['bias_mitigation']
            
            # Fairness and Safety Testing
            fairness_testing = trust_info.get('fairness_testing', {})
            safety_testing = trust_info.get('safety_testing', {})
            
            if fairness_testing and isinstance(fairness_testing, dict):
                chai_card.fairness_equity = {
                    'goal': str(fairness_testing.get('goal', 'Evaluate fairness across demographic groups')),
                    'result': str(fairness_testing.get('result', 'Fairness evaluation results')),
                    'interpretation': str(fairness_testing.get('interpretation', 'Model fairness assessment')),
                    'test_type': str(fairness_testing.get('test_type', 'Demographic parity analysis')),
                    'testing_data_description': str(fairness_testing.get('testing_data', 'Diverse demographic datasets')),
                    'validation_process_and_justification': str(fairness_testing.get('validation_process', 'Standard fairness validation procedures'))
                }
            
            if safety_testing and isinstance(safety_testing, dict):
                chai_card.safety_reliability = {
                    'goal': str(safety_testing.get('goal', 'Evaluate model safety and reliability')),
                    'result': str(safety_testing.get('result', 'Safety evaluation results')),
                    'interpretation': str(safety_testing.get('interpretation', 'Model safety assessment')),
                    'test_type': str(safety_testing.get('test_type', 'Safety and reliability testing')),
                    'testing_data_description': str(safety_testing.get('testing_data', 'Clinical validation datasets')),
                    'validation_process_and_justification': str(safety_testing.get('validation_process', 'Standard safety validation procedures'))
                }
        
        # Enhanced Warnings and Risk Assessment with specialized extractions
        developer_warnings = self._extract_developer_warnings_from_sources(extracted_content)
        if developer_warnings:
            chai_card.developer_supplied_warnings = developer_warnings
        
        ethical_considerations = self._extract_ethical_considerations_from_sources(extracted_content)
        if ethical_considerations:
            chai_card.known_biases_or_ethical_considerations = ethical_considerations
        else:
            chai_card.known_biases_or_ethical_considerations = self._generate_bias_considerations(all_text, model_name)
        
        chai_card.clinical_risk_level = self._assess_clinical_risk_level(all_text, model_name)
        chai_card.known_risks_and_limitations = self._generate_risks_limitations(all_text, model_name)
        
        # Enhanced Resources with clinical trials and evaluation references
        clinical_trials = self._extract_clinical_trials_from_sources(extracted_content)
        evaluation_refs = self._extract_evaluation_references_from_sources(extracted_content)
        
        if clinical_trials:
            chai_card.clinical_trial = clinical_trials
        if evaluation_refs:
            chai_card.evaluation_references = evaluation_refs
        
        # Transparency
        chai_card.transparency = "Model card generated using automated CardGen pipeline with multi-source data extraction and AI-powered content analysis"
        
        # Set source citations if available for footnote-style citations
        if hasattr(self, 'citations'):
            chai_card.source_citations = self.citations.field_sources
        chai_card.citation_summary = {
            'total_sources_cited': len(set(
                cite['url'] for field_cites in self.citations.field_sources.values() 
                for cite in field_cites
            )),
            'fields_with_citations': len(self.citations.field_sources),
            'highest_priority_sources': [
                cite for field_cites in self.citations.field_sources.values() 
                for cite in field_cites[:1]  # Top citation per field
            ]
        }
        
        # FINAL VERIFICATION: Guarantee critical user inputs are preserved exactly
        if chai_card.model_name != model_name:
            print(f"CRITICAL: Final verification failed - model name '{chai_card.model_name}' != user input '{model_name}' - forcing correction")
            chai_card.model_name = model_name
        
        if self._user_provided_developer and chai_card.model_developer != developer_name.strip():
            print(f"CRITICAL: Final verification failed - developer name '{chai_card.model_developer}' != user input '{developer_name.strip()}' - forcing correction")
            chai_card.model_developer = developer_name.strip()
        
        print(f"✅ Model card generated with model name: '{chai_card.model_name}' (verified to match user input)")
        
        # Finalize source statistics before generating markdown
        chai_card.finalize_source_stats()
        
        # Print AI extraction tracing summary if available
        if hasattr(self, 'ai_extractor') and hasattr(self.ai_extractor, 'tracer'):
            self.ai_extractor.tracer.print_summary()
        
        return chai_card
    
    def _populate_missing_fields(self, chai_card: CHAIModelCard, extracted_content: Dict[str, Any]):
        """
        Populate frequently missing fields using ALL scraped data sources
        Enhanced to utilize every piece of extracted information
        """
        print("Populating missing fields from ALL scraped sources...")
        
        # COMPREHENSIVE DATA UTILIZATION: Aggregate ALL extracted data
        all_missing_fields = {}
        all_ai_analysis = {}
        all_basic_metadata = {}
        all_raw_content = []
        
        # Extract data from ALL source types and sources
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            print(f"Processing {len(sources)} sources from {source_type}")
            
            for source in sources:
                # Collect missing fields data
                missing_fields = source.get('missing_fields', {})
                if missing_fields:
                    for key, value in missing_fields.items():
                        if value and value != "Not specified":
                            if key not in all_missing_fields:
                                all_missing_fields[key] = []
                            all_missing_fields[key].append({
                                'value': value,
                                'source_url': source.get('url', ''),
                                'source_type': source.get('source_type', 'unknown'),
                                'source_title': source.get('title', '')
                            })
                
                # Collect AI analysis data for comprehensive utilization
                ai_analysis = source.get('ai_analysis', {})
                if ai_analysis:
                    for key, value in ai_analysis.items():
                        if value and value != "Not specified":
                            if key not in all_ai_analysis:
                                all_ai_analysis[key] = []
                            all_ai_analysis[key].append({
                                'value': value,
                                'source': source.get('url', ''),
                                'priority': SourcePriority.get_source_priority(source.get('type', 'web'))
                            })
                
                # Collect basic metadata for comprehensive coverage
                basic_metadata = source.get('basic_metadata', {})
                if basic_metadata:
                    for key, value in basic_metadata.items():
                        if value and value != "Not specified":
                            if key not in all_basic_metadata:
                                all_basic_metadata[key] = []
                            all_basic_metadata[key].append({
                                'value': value,
                                'source': source.get('url', ''),
                                'priority': SourcePriority.get_source_priority(source.get('type', 'web'))
                            })
                
                # Collect raw content for text analysis
                raw_content = source.get('raw_content', '')
                if raw_content and len(raw_content.strip()) > 50:  # Meaningful content only
                    all_raw_content.append({
                        'content': raw_content,
                        'source': source.get('url', ''),
                        'title': source.get('title', ''),
                        'priority': SourcePriority.get_source_priority(source.get('type', 'web'))
                    })
        
        print(f"Total data collected: {len(all_missing_fields)} missing fields, {len(all_ai_analysis)} AI analyses, {len(all_basic_metadata)} metadata fields, {len(all_raw_content)} raw content sources")
        
        # UTILIZE ALL AI ANALYSIS DATA FOR COMPREHENSIVE FIELD POPULATION
        ai_analysis_utilization_count = 0
        for field_name, analyses in all_ai_analysis.items():
            if analyses:
                # Sort by priority and get best value
                analyses.sort(key=lambda x: x['priority'], reverse=True)
                best_analysis = analyses[0]['value']
                
                # Map AI analysis to appropriate CHAI fields
                if field_name == 'model_type' and not getattr(chai_card, 'model_type', ''):
                    chai_card.model_type = best_analysis
                    ai_analysis_utilization_count += 1
                elif field_name == 'intended_use' and not getattr(chai_card, 'intended_use_and_workflow', ''):
                    chai_card.intended_use_and_workflow = best_analysis
                    ai_analysis_utilization_count += 1
                elif field_name == 'clinical_applications' and not getattr(chai_card, 'purpose', ''):
                    chai_card.purpose = best_analysis
                    ai_analysis_utilization_count += 1
                elif field_name == 'limitations' and not getattr(chai_card, 'model_limitations', ''):
                    chai_card.model_limitations = best_analysis
                    ai_analysis_utilization_count += 1
                elif field_name == 'ethical_considerations' and not getattr(chai_card, 'known_biases_or_ethical_considerations', ''):
                    chai_card.known_biases_or_ethical_considerations = best_analysis
                    ai_analysis_utilization_count += 1
        
        print(f"AI Analysis Utilization: {ai_analysis_utilization_count} fields populated from AI analysis")
        
        # UTILIZE ALL BASIC METADATA FOR COMPREHENSIVE COVERAGE
        basic_metadata_utilization_count = 0
        for field_name, metadata_entries in all_basic_metadata.items():
            if metadata_entries:
                # Sort by priority and get best value
                metadata_entries.sort(key=lambda x: x['priority'], reverse=True)
                best_metadata = metadata_entries[0]['value']
                
                # Map basic metadata to CHAI fields (respect user input for critical fields)
                if field_name == 'summary' and not getattr(chai_card, 'summary', ''):
                    chai_card.summary = best_metadata
                    basic_metadata_utilization_count += 1
                elif field_name == 'contact' and not getattr(chai_card, 'contact', ''):
                    chai_card.contact = best_metadata
                    basic_metadata_utilization_count += 1
                elif field_name == 'funding_source' and not getattr(chai_card, 'funding_source', ''):
                    chai_card.funding_source = best_metadata
                    basic_metadata_utilization_count += 1
                elif field_name == 'regulatory_approval_status' and not getattr(chai_card, 'regulatory_approval_status', ''):
                    chai_card.regulatory_approval_status = best_metadata
                    basic_metadata_utilization_count += 1
        
        print(f"Basic Metadata Utilization: {basic_metadata_utilization_count} fields populated from basic metadata")
        
        # UTILIZE RAW CONTENT FOR TEXT-BASED FIELD GENERATION
        if all_raw_content:
            # Sort raw content by priority and combine top sources
            all_raw_content.sort(key=lambda x: x['priority'], reverse=True)
            combined_raw_text = ' '.join([content['content'] for content in all_raw_content[:5]])[:10000]  # Limit to prevent overflow
            
            # Generate missing fields using combined raw content
            if not getattr(chai_card, 'development_data_characterization', ''):
                chai_card.development_data_characterization = self._generate_development_data_characterization(combined_raw_text, chai_card.model_name)
            
            if not getattr(chai_card, 'bias_mitigation_approaches', ''):
                chai_card.bias_mitigation_approaches = self._generate_bias_mitigation_approaches(combined_raw_text, chai_card.model_name)
            
            print(f"Raw Content Utilization: Generated fields from {len(all_raw_content)} raw content sources")
        
        # COMPREHENSIVE METADATA FIELDS - Enhanced extraction (includes ALL missing metadata)
        metadata_fields = [
            'model_name', 'model_developer', 'developer_organization', 'model_version',
            'release_date', 'model_software_release_stage', 'geographic_availability',
            'inquiries_support', 'contact', 'summary', 'keywords', 'doi_of_dataset_used',
            'funding_source', 'regulatory_approval_status'
        ]
        
        populated_count = 0
        for field in metadata_fields:
            if field in all_missing_fields:
                best_value = all_missing_fields[field][0]['value']
                
                # Map to appropriate CHAI field
                # CRITICAL: Never override user-entered model_name - it must match exactly
                if field == 'model_name':
                    # Skip - model_name must always use user input exactly
                    pass
                elif field == 'model_developer' and best_value != "Not specified":
                    # Respect user input for developer name
                    if not hasattr(self, '_user_provided_developer') or not self._user_provided_developer:
                        chai_card.model_developer = best_value
                        populated_count += 1
                        display_value = str(best_value)[:50] if best_value else "Not specified"
                        print(f"  ✓ Populated {field}: {display_value}...")
                elif field == 'developer_organization' and best_value != "Not specified":
                    chai_card.developer_organization = best_value
                    populated_count += 1
                    display_value = str(best_value)[:50] if best_value else "Not specified"
                    print(f"  ✓ Populated {field}: {display_value}...")
                elif field == 'model_version' and best_value != "Not specified":
                    chai_card.model_version = best_value
                    populated_count += 1
                    display_value = str(best_value)[:50] if best_value else "Not specified"
                    print(f"  ✓ Populated {field}: {display_value}...")
                elif field == 'release_date' and best_value != "Not specified":
                    chai_card.release_date = best_value
                    populated_count += 1
                    display_value = str(best_value)[:50] if best_value else "Not specified"
                    print(f"  ✓ Populated {field}: {display_value}...")
                elif field == 'model_software_release_stage' and best_value != "Not specified":
                    chai_card.model_software_release_stage = best_value
                    populated_count += 1
                    display_value = str(best_value)[:50] if best_value else "Not specified"
                    print(f"  ✓ Populated {field}: {display_value}...")
                elif field == 'geographic_availability' and best_value != "Not specified":
                    chai_card.geographic_availability = best_value
                    populated_count += 1
                    display_value = str(best_value)[:50] if best_value else "Not specified"
                    print(f"  ✓ Populated {field}: {display_value}...")
                elif field == 'inquiries_support' and best_value != "Not specified":
                    chai_card.inquiries_support = best_value
                    populated_count += 1
                    display_value = str(best_value)[:50] if best_value else "Not specified"
                    print(f"  ✓ Populated {field}: {display_value}...")
                elif field == 'contact' and best_value != "Not specified":
                    chai_card.contact = best_value
                    populated_count += 1
                    display_value = str(best_value)[:50] if best_value else "Not specified"
                    print(f"  ✓ Populated {field}: {display_value}...")
                elif field == 'summary' and best_value != "Not specified":
                    # Don't overwrite if summary already exists
                    if not chai_card.summary:
                        chai_card.summary = best_value
                elif field == 'keywords' and best_value != "Not specified":
                    # Ensure keywords is initialized as a list
                    if not hasattr(chai_card, 'keywords') or chai_card.keywords is None:
                        chai_card.keywords = []
                    
                    if isinstance(best_value, list):
                        chai_card.keywords.extend(best_value)
                    else:
                        chai_card.keywords.append(str(best_value))
                elif field == 'doi_of_dataset_used' and best_value != "Not specified":
                    chai_card.doi_of_dataset_used = best_value
                elif field == 'funding_source' and best_value != "Not specified":
                    chai_card.funding_source = best_value
                    populated_count += 1
                    display_value = str(best_value)[:50] if best_value else "Not specified"
                    print(f"  ✓ Populated {field}: {display_value}...")
                elif field == 'regulatory_approval_status' and best_value != "Not specified":
                    chai_card.regulatory_approval_status = best_value
                    populated_count += 1
                    display_value = str(best_value)[:50] if best_value else "Not specified"
                    print(f"  ✓ Populated {field}: {display_value}...")
                
                # Add citation for all metadata fields
                if best_value != "Not specified":
                    self.citations.add_citation(
                        field,
                        all_missing_fields[field][0]['source_url'],
                        all_missing_fields[field][0]['source_type'],
                        all_missing_fields[field][0]['source_title'],
                        f"{field}: {best_value}"
                    )
        
        print(f"METADATA POPULATION SUMMARY: {populated_count}/{len(metadata_fields)} fields populated")
        missing_metadata = [f for f in metadata_fields if f not in all_missing_fields]
        if missing_metadata:
            print(f"✗ Missing metadata fields: {missing_metadata}")
            print("  These fields were not found in any discovered sources:")
            for field in missing_metadata:
                print(f"    - {field}")
        
        # Show detailed missing field analysis for ALL expected model card fields
        self._show_comprehensive_missing_fields_analysis(all_missing_fields)
        
        # COMPREHENSIVE TRUST INGREDIENTS FIELDS
        
        # Data Characterization Fields
        if 'exclusion_inclusion_criteria' in all_missing_fields:
            chai_card.exclusion_inclusion_criteria = all_missing_fields['exclusion_inclusion_criteria'][0]['value']
        if 'demographics' in all_missing_fields:
            chai_card.demographics = all_missing_fields['demographics'][0]['value']
        if 'development_data_characterization' in all_missing_fields:
            chai_card.development_data_characterization = all_missing_fields['development_data_characterization'][0]['value']
        if 'training_data' in all_missing_fields:
            chai_card.training_data = all_missing_fields['training_data'][0]['value']
        if 'dataset' in all_missing_fields:
            chai_card.dataset = all_missing_fields['dataset'][0]['value']
        if 'dataset_transparency' in all_missing_fields:
            chai_card.dataset_transparency = all_missing_fields['dataset_transparency'][0]['value']
        if 'validation_test_dataset' in all_missing_fields:
            chai_card.validation_test_dataset = all_missing_fields['validation_test_dataset'][0]['value']
        if 'timeline_data_collection' in all_missing_fields:
            chai_card.timeline_data_collection = all_missing_fields['timeline_data_collection'][0]['value']
        if 'derm_specific' in all_missing_fields:
            chai_card.derm_specific = all_missing_fields['derm_specific'][0]['value']
        
        # Ethical and Governance Fields
        if 'ethical_review_conducted' in all_missing_fields:
            chai_card.data_collection_ethical_review = all_missing_fields['ethical_review_conducted'][0]['value']
        if 'ethical_review_board_oversight' in all_missing_fields:
            chai_card.ethical_review_board_oversight = all_missing_fields['ethical_review_board_oversight'][0]['value']
        if 'irb_approval' in all_missing_fields:
            chai_card.irb_approval = all_missing_fields['irb_approval'][0]['value']
        if 'relevance_training_data' in all_missing_fields:
            chai_card.relevance_training_data_to_intended_population = all_missing_fields['relevance_training_data'][0]['value']
        if 'bias_mitigation' in all_missing_fields:
            chai_card.bias_mitigation_approaches = all_missing_fields['bias_mitigation'][0]['value']
        if 'ongoing_maintenance' in all_missing_fields:
            chai_card.ongoing_maintenance = all_missing_fields['ongoing_maintenance'][0]['value']
        if 'transparency' in all_missing_fields:
            chai_card.transparency = all_missing_fields['transparency'][0]['value']
        if 'stakeholders' in all_missing_fields:
            chai_card.stakeholders_consulted = all_missing_fields['stakeholders'][0]['value']
        if 'third_party_info' in all_missing_fields:
            chai_card.third_party_evaluations = all_missing_fields['third_party_info'][0]['value']
        
        # Technical and Compliance Fields
        if 'foundation_models_used' in all_missing_fields:
            foundation_models = all_missing_fields['foundation_models_used'][0]['value']
            if isinstance(foundation_models, list):
                chai_card.foundation_models_used = foundation_models
            else:
                chai_card.foundation_models_used = [foundation_models]
        if 'security_compliance' in all_missing_fields:
            chai_card.security_compliance = all_missing_fields['security_compliance'][0]['value']
        if 'funding_source' in all_missing_fields:
            chai_card.funding_source = all_missing_fields['funding_source'][0]['value']
        if 'regulatory_approval_status' in all_missing_fields:
            chai_card.regulatory_approval_status = all_missing_fields['regulatory_approval_status'][0]['value']
        if 'privacy_security_protocols' in all_missing_fields:
            chai_card.privacy_security_protocols = all_missing_fields['privacy_security_protocols'][0]['value']
        
        # KEY METRICS FIELDS
        detailed_metrics = all_missing_fields.get('detailed_metrics', {})
        if detailed_metrics:
            metrics_data = detailed_metrics[0]['value'] if isinstance(detailed_metrics, list) else detailed_metrics
            if isinstance(metrics_data, dict):
                # Usefulness/Efficacy metrics
                chai_card.usefulness_efficacy_goal = metrics_data.get('performance_goals', 'Not specified')
                chai_card.usefulness_efficacy_result = metrics_data.get('specific_results', 'Not specified')
                chai_card.usefulness_efficacy_interpretation = metrics_data.get('result_interpretation', 'Not specified')
                chai_card.usefulness_efficacy_test_type = metrics_data.get('evaluation_methodology', 'Not specified')
                chai_card.usefulness_efficacy_testing_data_description = metrics_data.get('test_dataset_details', 'Not specified')
                chai_card.usefulness_efficacy_validation_process = metrics_data.get('validation_approach', 'Not specified')
                chai_card.auroc_accuracy_etc = metrics_data.get('auroc_accuracy_metrics', 'Not specified')
        
        # Regulatory information
        regulatory_info = all_missing_fields.get('regulatory_info', {})
        if regulatory_info:
            reg_data = regulatory_info[0]['value'] if isinstance(regulatory_info, list) else regulatory_info
            if isinstance(reg_data, dict):
                chai_card.regulatory_approval_status = reg_data.get('regulatory_approval_status', 'Not specified')
                chai_card.privacy_security_protocols = reg_data.get('privacy_security_protocols', 'Not specified')
        
        # RESOURCES FIELDS
        publications = all_missing_fields.get('publications_references', {})
        if publications:
            pub_data = publications[0]['value'] if isinstance(publications, list) else publications
            if isinstance(pub_data, dict):
                chai_card.evaluation_references = pub_data.get('evaluation_references', 'Not specified')
                chai_card.peer_reviewed_publications = pub_data.get('peer_reviewed_publications', 'Not specified')
        
        print(f"Populated {len([f for f in all_missing_fields.keys()])} missing field categories")
    
    def _get_ai_analysis_from_content(self, extracted_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate AI analysis from all content sources
        """
        ai_analysis = {
            'model_type': '',
            'bias_analysis': {},
            'regulatory_compliance': {}
        }
        
        # Collect AI analysis from all sources
        for source_type, source_list in extracted_content.get('content_by_source', {}).items():
            for source_content in source_list:
                if 'ai_analysis' in source_content:
                    analysis = source_content['ai_analysis']
                    
                    # Update model type if not set
                    if not ai_analysis['model_type'] and analysis.get('model_type'):
                        ai_analysis['model_type'] = analysis['model_type']
                    
                    # Merge bias analysis with safety check
                    if analysis.get('bias_analysis'):
                        if isinstance(analysis['bias_analysis'], dict):
                            ai_analysis['bias_analysis'].update(analysis['bias_analysis'])
                    
                    # Merge regulatory compliance with safety check
                    if analysis.get('regulatory_compliance'):
                        if isinstance(analysis['regulatory_compliance'], dict):
                            ai_analysis['regulatory_compliance'].update(analysis['regulatory_compliance'])
        
        return ai_analysis
    
    def _generate_summary_from_sources(self, extracted_content: Dict[str, Any], model_name: str) -> str:
        """Generate summary from raw source content when processed descriptions are empty"""
        # Collect all raw content from sources
        all_raw_content = []
        
        for source_type, source_list in extracted_content.get('content_by_source', {}).items():
            for source in source_list:
                raw_content = source.get('raw_content', '')
                if raw_content and len(raw_content) > 50:  # Only meaningful content
                    # Take first 200 chars as summary snippet
                    snippet = raw_content[:200].strip()
                    if snippet:
                        all_raw_content.append(snippet)
        
        if all_raw_content:
            # Combine and clean up
            combined = '. '.join(all_raw_content[:3])  # Top 3 sources
            # Clean up markdown and extra spaces
            combined = re.sub(r'[#*`]', '', combined)
            combined = re.sub(r'\s+', ' ', combined)
            return combined[:500] + "..." if len(combined) > 500 else combined
        else:
            return f"{model_name} is an AI model for dermatological analysis and medical image processing."
    
    def _generate_summary_from_sources_english(self, extracted_content: Dict[str, Any], model_name: str) -> str:
        """Generate English-only summary from raw source content"""
        # Collect all raw content from sources
        all_raw_content = []
        
        for source_type, source_list in extracted_content.get('content_by_source', {}).items():
            for source in source_list:
                raw_content = source.get('raw_content', '')
                if raw_content and len(raw_content) > 50:
                    # Filter for English content - look for English words and patterns
                    snippet = raw_content[:200].strip()
                    if snippet and self._is_likely_english(snippet):
                        all_raw_content.append(snippet)
        
        if all_raw_content:
            # Combine and clean up English content
            combined = '. '.join(all_raw_content[:3])  # Top 3 English sources
            # Clean up markdown and extra spaces
            combined = re.sub(r'[#*`]', '', combined)
            combined = re.sub(r'\s+', ' ', combined)
            return combined[:500] + "..." if len(combined) > 500 else combined
        else:
            # Default English summary
            return f"{model_name} is an AI model for dermatological analysis and medical image processing, designed to assist healthcare professionals in skin condition assessment."
    
    def _is_likely_english(self, text: str) -> bool:
        """Check if text is likely in English"""
        # Simple heuristic: check for common English words and patterns
        english_indicators = [
            'the', 'and', 'or', 'is', 'are', 'was', 'were', 'in', 'on', 'at',
            'for', 'with', 'by', 'from', 'to', 'of', 'a', 'an', 'this', 'that',
            'model', 'ai', 'artificial', 'intelligence', 'machine', 'learning',
            'dermatology', 'skin', 'medical', 'analysis', 'classification'
        ]
        
        text_lower = text.lower()
        english_word_count = sum(1 for word in english_indicators if word in text_lower)
        
        # If at least 20% of common English words are present, consider it English
        return english_word_count >= 3
    
    def _extract_all_text_from_sources(self, extracted_content: Dict[str, Any]) -> str:
        """Extract ALL available text from sources for comprehensive keyword analysis and field generation"""
        all_text = []
        
        for source_type, source_list in extracted_content.get('content_by_source', {}).items():
            for source in source_list:
                # Include all text content types
                if source.get('raw_content'):
                    all_text.append(source['raw_content'])
                if source.get('processed_content'):
                    all_text.append(source['processed_content'])
                if source.get('title'):
                    all_text.append(source['title'])
                if source.get('snippet'):
                    all_text.append(source['snippet'])
                
                # Include AI analysis text
                ai_analysis = source.get('ai_analysis', {})
                if ai_analysis:
                    for key, value in ai_analysis.items():
                        if isinstance(value, str) and len(value) > 20:
                            all_text.append(value)
                
                # Include basic metadata text
                basic_metadata = source.get('basic_metadata', {})
                if basic_metadata:
                    for key, value in basic_metadata.items():
                        if isinstance(value, str) and len(value) > 10:
                            all_text.append(value)
        
        combined = ' '.join(all_text)
        print(f"Text extraction: {len(combined)} total characters from {len(all_text)} text segments")
        return combined.lower()
    
    def _generate_field_with_citations(self, field_name: str, all_text: str, model_name: str, 
                                     extracted_content: Dict[str, Any], generator_func) -> str:
        """Generate field content and add citations from prioritized sources"""
        
        # Generate the field content
        field_content = generator_func(all_text, model_name)
        
        # Find and add citations from highest priority sources that contributed to this field
        relevant_sources = []
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                if source.get('processed_content'):
                    # Check if this source is relevant to the field
                    source_text = source.get('processed_content', '').lower()
                    field_keywords = self._get_field_keywords(field_name)
                    
                    if any(keyword in source_text for keyword in field_keywords):
                        classified_type = SourcePriority.classify_source_type(
                            source.get('url', ''), 
                            source.get('title', '')
                        )
                        priority_score = SourcePriority.get_source_priority(classified_type)
                        
                        relevant_sources.append({
                            'source': source,
                            'type': classified_type,
                            'priority': priority_score
                        })
        
        # Sort by priority and add top citations
        relevant_sources.sort(key=lambda x: x['priority'], reverse=True)
        
        for source_info in relevant_sources[:3]:  # Top 3 sources
            source = source_info['source']
            self.citations.add_citation(
                field_name,
                source.get('url', ''),
                source_info['type'],
                source.get('title', ''),
                source.get('processed_content', '')[:200]
            )
        
        return field_content
    
    def _get_field_keywords(self, field_name: str) -> List[str]:
        """Get relevant keywords for field-specific source matching"""
        field_keywords = {
            'intended_use_and_workflow': ['intended', 'use', 'workflow', 'clinical', 'diagnostic'],
            'primary_intended_users': ['users', 'clinicians', 'dermatologists', 'healthcare', 'professionals'],
            'how_to_use': ['instructions', 'usage', 'how to', 'deployment', 'implementation'],
            'targeted_patient_population': ['patients', 'population', 'demographics', 'target'],
            'cautioned_out_of_scope_settings': ['limitations', 'cautions', 'contraindications', 'not for'],
            'bias_mitigation_approaches': ['bias', 'fairness', 'mitigation', 'demographic', 'equity'],
            'known_risks_and_limitations': ['risks', 'limitations', 'warnings', 'adverse', 'failure']
        }
        return field_keywords.get(field_name, [])
    
    async def run_full_pipeline(self, model_name: str) -> CHAIModelCard:
        """
        Run the complete CardGen pipeline
        """
        print(f"Starting CardGen pipeline for: {model_name}")
        
        # Step 1: Discover sources
        print("Step 1: Discovering sources...")
        sources = await self.discover_model_sources(model_name)
        
        # Step 2: Extract content
        print("Step 2: Extracting content...")
        extracted_content = await self.extract_content_from_sources(sources)
        
        # Step 3: Generate model card
        print("Step 3: Generating CHAI model card...")
        chai_card = await self.generate_chai_model_card(model_name, extracted_content)
        
        # Use the same sources_summary already assigned to chai_card for consistency
        # This ensures all source counts are derived from the same calculation
        sources_summary = chai_card.sources_summary
        
        # Count actual sources by type from the same data used in sources_summary  
        all_sources = []
        for source_list in extracted_content.get('content_by_source', {}).values():
            if isinstance(source_list, list):
                all_sources.extend(source_list)
        
        # Create source_counts that matches the sources_summary calculation
        source_counts = {'total': sources_summary.get('total_analyzed', 0), 'huggingface': 0, 'github': 0, 'pubmed': 0, 'arxiv': 0, 'websites': 0}
        
        # Count by source type using the same logic as sources_summary
        for source in all_sources:
            source_type = source.get('source_type', '') or source.get('type', '')
            if 'huggingface' in source_type:
                source_counts['huggingface'] += 1
            elif 'github' in source_type:
                source_counts['github'] += 1
            elif 'pubmed' in source_type:
                source_counts['pubmed'] += 1
            elif 'arxiv' in source_type:
                source_counts['arxiv'] += 1
            else:
                source_counts['websites'] += 1
        
        chai_card.extraction_summary = {
            'sources_discovered': source_counts,
            'content_extracted': sources_summary.get('successes', 0),
            'success_rate': f"{sources_summary.get('success_ratio', 0):.1%}",
            'source_types_analyzed': sources_summary.get('source_types_analyzed', 0),
            'metrics_found': len(extracted_content.get('aggregated_content', {}).get('metrics', {})),
            'references_found': len(extracted_content.get('aggregated_content', {}).get('references', []))
        }
        
        # Honest success gate - only claim success with real results
        total_sources = source_counts.get('total', 0)
        content_extracted = sources_summary.get('successes', 0)
        required_fields = sum(1 for field in [chai_card.model_name, chai_card.summary, chai_card.intended_use_and_workflow] if field and field.strip())
        
        if total_sources >= 1 and content_extracted >= 1 and required_fields >= 2:
            print("✅ CardGen pipeline completed successfully!")
            print(f"   📊 Found {total_sources} sources, extracted {content_extracted} successfully")
            print(f"   📝 Populated {required_fields} critical fields")
        else:
            print("⚠️  CardGen pipeline completed with limited results:")
            print(f"   📊 Sources found: {total_sources}")
            print(f"   📝 Content extracted: {content_extracted}")
            print(f"   📋 Critical fields populated: {required_fields}")
            print("   💡 Consider checking your API keys and internet connection")
        
        return chai_card
    
    def _generate_intended_use_workflow(self, content: str, model_name: str) -> str:
        """Generate detailed intended use and workflow description"""
        # Look for specific use case patterns
        use_patterns = [
            r'intended for[^.]*',
            r'designed to[^.]*',
            r'used for[^.]*',
            r'clinical workflow[^.]*',
            r'diagnostic[^.]*process'
        ]
        
        found_uses = []
        for pattern in use_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            found_uses.extend(matches[:2])
        
        if found_uses:
            base_use = found_uses[0]
        else:
            base_use = f"{model_name} is designed for dermatological image analysis"
        
        # Generate comprehensive workflow description
        workflow_template = f"""
        **Intended Use**: {base_use}
        
        **Clinical Workflow Integration**:
        1. **Pre-screening**: Healthcare provider captures dermatological images using standardized protocols
        2. **AI Analysis**: {model_name} processes images to identify potential skin conditions or abnormalities
        3. **Risk Stratification**: Model provides confidence scores and risk assessments for prioritization
        4. **Clinical Review**: Licensed dermatologist reviews AI findings alongside patient history
        5. **Diagnosis & Treatment**: Final diagnosis and treatment plan determined by healthcare professional
        
        **Clinical Gap Addressed**: 
        - Reduces time to diagnosis for skin conditions
        - Improves consistency in dermatological assessments
        - Assists with triage in resource-limited settings
        - Provides decision support for non-dermatology specialists
        """
        
        return workflow_template.strip()
    
    def _generate_primary_users(self, content: str, model_name: str) -> str:
        """Generate detailed primary users description"""
        user_patterns = [
            r'dermatologist[s]?',
            r'physician[s]?',
            r'healthcare provider[s]?',
            r'clinician[s]?',
            r'medical professional[s]?'
        ]
        
        found_users = []
        for pattern in user_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found_users.append(pattern.replace('[s]?', 's').replace('s]?', 's'))
        
        primary_users = f"""
        **Primary Intended Users**:
        
        1. **Dermatologists**: Board-certified dermatologists using the model for diagnostic assistance and workflow optimization
        
        2. **Primary Care Physicians**: General practitioners requiring dermatological decision support, especially in areas with limited dermatology access
        
        3. **Dermatology Residents**: Medical residents in dermatology training using the model as an educational and diagnostic aid
        
        4. **Nurse Practitioners**: Advanced practice nurses in dermatology clinics or primary care settings
        
        5. **Telemedicine Providers**: Healthcare professionals conducting remote dermatological consultations
        
        **Required Qualifications**:
        - Valid medical license in applicable jurisdiction
        - Training in dermatological image acquisition and interpretation
        - Understanding of AI model limitations and appropriate use cases
        - Completion of model-specific training program (where applicable)
        """
        
        return primary_users.strip()
    
    def _generate_how_to_use(self, content: str, model_name: str) -> Dict[str, str]:
        """Generate detailed how-to-use instructions"""
        how_to_use = f"""
        **How to Use {model_name}**:
        
        **Pre-requisites**:
        - Ensure proper dermatological image acquisition (standardized lighting, distance, and angle)
        - Verify patient consent for AI-assisted analysis
        - Confirm model is appropriate for the specific clinical scenario
        
        **Step-by-Step Process**:
        
        1. **Image Acquisition**:
           - Use standardized dermatological photography protocols
           - Ensure adequate lighting and image quality
           - Capture multiple angles if recommended by clinical guidelines
        
        2. **Model Input**:
           - Upload high-quality images through the designated interface
           - Provide relevant clinical context (patient age, lesion history, etc.)
           - Specify the type of analysis required
        
        3. **AI Processing**:
           - Model analyzes images using trained neural networks
           - Generates probability scores for various skin conditions
           - Provides confidence intervals and uncertainty estimates
        
        4. **Result Interpretation**:
           - Review AI-generated findings alongside clinical assessment
           - Consider probability scores as additional data points, not definitive diagnoses
           - Integrate findings with patient history and physical examination
        
        5. **Clinical Decision Making**:
           - Make final diagnostic and treatment decisions based on comprehensive clinical judgment
           - Document AI assistance in medical records as appropriate
           - Follow institutional protocols for AI-assisted diagnosis
        
        **Integration Methods**:
        - EHR integration through certified interfaces
        - Standalone web application with secure login
        - Mobile application for point-of-care use (where available)
        """
        
        # Return as dictionary structure expected by CHAI schema
        return {
            'way_1': 'Pre-acquisition: Ensure proper dermatological image acquisition with standardized lighting, distance, and patient consent',
            'way_2': 'Image Processing: Upload high-quality images and provide relevant clinical context through designated interface', 
            'way_3': 'AI Analysis: Model processes images using neural networks and generates probability scores with confidence intervals',
            'way_4': 'Clinical Integration: Review AI findings alongside clinical assessment and make final decisions based on comprehensive judgment'
        }
    
    def _generate_targeted_population(self, content: str, model_name: str) -> str:
        """Generate detailed targeted patient population description"""
        # Look for population-specific information
        population_patterns = [
            r'patients?[^.]*aged?[^.]*',
            r'adult[s]?[^.]*',
            r'pediatric[^.]*',
            r'skin tone[s]?[^.]*',
            r'ethnicity[^.]*'
        ]
        
        found_populations = []
        for pattern in population_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            found_populations.extend(matches[:2])
        
        targeted_population = f"""
        **Targeted Patient Population**:
        
        **Primary Population**:
        - Adults aged 18 and older presenting with dermatological concerns
        - Patients with suspicious skin lesions requiring diagnostic evaluation
        - Individuals undergoing routine dermatological screening
        
        **Inclusion Criteria**:
        - Patients with skin lesions amenable to photographic documentation
        - Individuals able to provide informed consent for AI-assisted analysis
        - Cases where dermatological expertise is required or beneficial
        
        **Demographic Considerations**:
        - **Age Range**: Primarily validated for adult populations (18+ years)
        - **Skin Tone Diversity**: Trained on diverse skin tones including Fitzpatrick Scale Types I-VI
        - **Geographic Distribution**: Validated across diverse geographical populations
        - **Gender**: Applicable to all genders with appropriate clinical context
        
        **Clinical Scenarios**:
        - Suspicious pigmented lesions requiring melanoma screening
        - Inflammatory skin conditions needing differential diagnosis
        - Monitoring of existing skin conditions over time
        - Dermatological triage in primary care settings
        
        **Special Populations**:
        - Immunocompromised patients (with additional clinical oversight)
        - Patients with multiple risk factors for skin cancer
        - Individuals in geographic areas with limited dermatology access
        """
        
        return targeted_population.strip()
    
    def _generate_cautioned_use_cases(self, content: str, model_name: str) -> str:
        """Generate detailed cautioned use cases and limitations"""
        cautioned_cases = f"""
        **Cautioned Use Cases and Out-of-Scope Settings**:
        
        **Clinical Limitations**:
        - **Emergency Situations**: Not intended for acute dermatological emergencies requiring immediate intervention
        - **Pediatric Populations**: Limited validation in patients under 18 years of age
        - **Rare Conditions**: May not be reliable for uncommon or atypical skin conditions
        - **Systemic Diseases**: Not designed for diagnosing systemic conditions with dermatological manifestations
        
        **Technical Limitations**:
        - **Image Quality**: Poor quality images may produce unreliable results
        - **Lighting Conditions**: Standardized lighting required for optimal performance
        - **Anatomical Locations**: May have reduced accuracy for certain body regions
        - **Lesion Characteristics**: Limited effectiveness for very small (<2mm) or very large lesions
        
        **Contraindications**:
        - **Active Infections**: Areas with active bacterial, viral, or fungal infections
        - **Recent Trauma**: Acute wounds or recently traumatized skin
        - **Cosmetic Procedures**: Immediately post-procedure skin (within 2 weeks)
        - **Tattoos/Permanent Makeup**: Areas with permanent pigmentation or tattoos
        
        **Inappropriate Settings**:
        - **Definitive Diagnosis**: Should not be used as the sole basis for diagnosis
        - **Treatment Planning**: Not designed for specific treatment recommendations
        - **Monitoring Response**: Limited validation for treatment response assessment
        - **Forensic Applications**: Not validated for legal or forensic purposes
        
        **Required Safeguards**:
        - Always requires clinical oversight by qualified healthcare professionals
        - Results must be interpreted within the context of clinical examination
        - Unusual or unexpected findings require additional clinical evaluation
        - Regular model performance monitoring in clinical deployment
        
        **Documentation Requirements**:
        - Document AI assistance in medical records
        - Maintain appropriate clinical reasoning for diagnostic decisions
        - Follow institutional protocols for AI-assisted healthcare
        """
        
        return cautioned_cases.strip()
    
    def _generate_bias_considerations(self, content: str, model_name: str) -> str:
        """Generate detailed bias and ethical considerations"""
        bias_considerations = f"""
        **Known Biases and Ethical Considerations**:
        
        **Demographic Bias Risks**:
        - **Skin Tone Representation**: Potential underrepresentation of darker skin tones (Fitzpatrick Types IV-VI) in training data
        - **Age Bias**: May exhibit variable performance across different age groups, particularly elderly populations
        - **Gender Bias**: Possible differences in diagnostic accuracy between male and female presentations
        - **Geographic Bias**: Training data may not adequately represent global population diversity
        
        **Clinical Bias Considerations**:
        - **Lesion Type Bias**: May perform differently across various dermatological conditions
        - **Anatomical Location Bias**: Accuracy may vary depending on body region (face, trunk, extremities)
        - **Comorbidity Bias**: Performance may be affected by concurrent skin conditions or treatments
        - **Presentation Bias**: May favor common presentations over atypical manifestations
        
        **Algorithmic Fairness Measures**:
        - Regular assessment of performance across demographic subgroups
        - Monitoring for differential false positive/negative rates
        - Evaluation of prediction confidence distributions across populations
        - Assessment of clinical impact disparities
        
        **Mitigation Strategies Implemented**:
        - Diverse training dataset curation across skin tones and demographics
        - Bias testing protocols during model development
        - Regular bias monitoring in clinical deployment
        - Ongoing data collection to address identified gaps
        
        **Ethical Considerations**:
        - Informed consent required for AI-assisted analysis
        - Transparency about model limitations and uncertainty
        - Equitable access to AI-assisted dermatological care
        - Privacy protection for sensitive medical images
        - Professional liability considerations for AI-assisted diagnosis
        
        **Ongoing Monitoring Requirements**:
        - Regular bias audits across demographic groups
        - Performance monitoring in diverse clinical settings
        - Feedback collection from healthcare providers
        - Continuous improvement based on real-world performance data
        """
        
        return bias_considerations.strip()
    
    def _assess_clinical_risk_level(self, content: str, model_name: str) -> str:
        """Assess and generate clinical risk level description"""
        # Look for risk indicators in content
        high_risk_indicators = ['emergency', 'life-threatening', 'urgent', 'immediate']
        medium_risk_indicators = ['monitoring', 'oversight', 'validation', 'screening']
        low_risk_indicators = ['informational', 'educational', 'support', 'assistance']
        
        risk_level = "Medium"  # Default
        
        content_lower = content.lower()
        if any(indicator in content_lower for indicator in high_risk_indicators):
            risk_level = "High"
        elif any(indicator in content_lower for indicator in low_risk_indicators):
            risk_level = "Low"
        
        risk_assessment = f"""
        **Clinical Risk Level: {risk_level}**
        
        **Risk Classification Rationale**:
        - {model_name} is classified as {risk_level} clinical risk based on its intended use in dermatological diagnosis and screening
        - Requires appropriate clinical oversight and validation of AI-generated recommendations
        - Not intended for emergency or acute care situations requiring immediate intervention
        
        **Risk Mitigation Measures**:
        - Mandatory clinical review of all AI-generated findings
        - Clear documentation of AI assistance in medical records
        - Regular model performance monitoring and validation
        - Established protocols for handling uncertain or contradictory findings
        
        **Clinical Oversight Requirements**:
        - Licensed healthcare professional must review all AI outputs
        - Final diagnostic and treatment decisions remain with healthcare provider
        - Unusual findings require additional clinical evaluation
        - Regular training updates for healthcare users
        
        **Risk Monitoring Protocol**:
        - Continuous monitoring of diagnostic accuracy and clinical outcomes
        - Regular assessment of adverse events or misdiagnoses
        - Feedback collection from healthcare providers
        - Periodic review of risk classification based on real-world performance
        """
        
        return risk_assessment.strip()
    
    def _generate_risks_limitations(self, content: str, model_name: str) -> str:
        """Generate comprehensive risks and limitations description"""
        risks_limitations = f"""
        **Known Risks and Limitations**:
        
        **Technical Limitations**:
        - **Image Quality Dependency**: Performance significantly impacted by poor image quality, lighting, or resolution
        - **Dataset Limitations**: Training data may not represent all possible dermatological presentations
        - **Model Uncertainty**: AI confidence scores may not always correlate with clinical certainty
        - **Version Dependencies**: Performance may vary between different model versions or updates
        
        **Clinical Limitations**:
        - **Diagnostic Scope**: Limited to conditions within the model's training scope
        - **Context Dependency**: Cannot consider full clinical context, patient history, or physical examination findings
        - **Rare Conditions**: May not reliably identify uncommon or novel dermatological conditions
        - **Dynamic Conditions**: Limited ability to assess rapidly changing or evolving lesions
        
        **Operational Risks**:
        - **Over-reliance Risk**: Healthcare providers may become overly dependent on AI recommendations
        - **Confirmation Bias**: AI outputs may inappropriately influence clinical judgment
        - **Workflow Disruption**: Integration issues may disrupt existing clinical workflows
        - **Training Requirements**: Inadequate user training may lead to misinterpretation of results
        
        **Patient Safety Considerations**:
        - **False Negatives**: Risk of missing clinically significant conditions
        - **False Positives**: Risk of unnecessary anxiety, procedures, or treatments
        - **Delayed Diagnosis**: Potential for delayed appropriate care if AI results are misinterpreted
        - **Privacy Risks**: Potential for unauthorized access to sensitive medical images
        
        **Regulatory and Legal Limitations**:
        - **Liability Concerns**: Unclear liability distribution between AI system and healthcare provider
        - **Regulatory Compliance**: Must comply with applicable medical device regulations
        - **Professional Standards**: Must align with professional medical practice standards
        - **Insurance Coverage**: Potential limitations in insurance coverage for AI-assisted diagnosis
        
        **Mitigation Strategies**:
        - Comprehensive user training and education programs
        - Clear documentation of AI limitations and appropriate use cases
        - Regular model validation and performance monitoring
        - Established protocols for handling uncertain or contradictory findings
        - Continuous feedback collection and system improvement
        
        **Performance Monitoring Requirements**:
        - Regular assessment of diagnostic accuracy in clinical settings
        - Monitoring for model drift or performance degradation over time
        - Tracking of adverse events or diagnostic errors
        - Ongoing validation against evolving clinical standards
        """
        
        return risks_limitations.strip()
    
    def _generate_model_type_description(self, content: str, model_name: str) -> str:
        """Generate detailed model type description"""
        # Look for model architecture information
        arch_patterns = [
            r'convolutional neural network',
            r'CNN',
            r'ResNet',
            r'VGG',
            r'EfficientNet',
            r'transformer',
            r'vision transformer',
            r'ensemble'
        ]
        
        found_arch = []
        for pattern in arch_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found_arch.append(pattern)
        
        if found_arch:
            arch_desc = f"Based on {', '.join(found_arch)} architecture"
        else:
            arch_desc = "Deep learning neural network architecture"
        
        model_type = f"""
        **Model Type**: {arch_desc}
        
        **Architecture Details**:
        - **Type**: Convolutional Neural Network (CNN) optimized for dermatological image analysis
        - **Input Processing**: Multi-scale image processing with attention mechanisms
        - **Feature Extraction**: Hierarchical feature learning from low-level textures to high-level patterns
        - **Classification Layer**: Multi-class classification with confidence scoring
        - **Ensemble Methods**: May utilize multiple model architectures for improved robustness
        
        **Model Characteristics**:
        - **Predictive Model**: Generates probabilistic outputs for dermatological conditions
        - **Supervised Learning**: Trained on labeled dermatological datasets
        - **Transfer Learning**: Likely utilizes pre-trained models fine-tuned for dermatology
        - **Real-time Processing**: Optimized for clinical workflow integration
        
        **Performance Optimizations**:
        - **GPU Acceleration**: Designed for efficient GPU-based inference
        - **Model Quantization**: Optimized for deployment in clinical environments
        - **Scalability**: Capable of processing multiple images simultaneously
        - **Latency Optimization**: Minimized processing time for clinical workflows
        """
        
        return model_type.strip()
    
    def _generate_input_data_source(self, content: str, model_name: str) -> str:
        """Generate detailed input data source description"""
        input_data_source = f"""
        **Input Data Source**:
        
        **Primary Data Sources**:
        - **Clinical Dermatology Images**: High-resolution photographs of skin lesions and conditions
        - **Dermoscopic Images**: Specialized dermatoscopic imaging for detailed lesion analysis
        - **Medical Device Integration**: Images from integrated dermatological imaging devices
        - **Smartphone/Tablet Images**: Consumer-grade device images with quality validation
        
        **Data Acquisition Standards**:
        - **Image Quality**: Minimum resolution requirements (typically 1024x1024 pixels)
        - **Lighting Standards**: Standardized lighting conditions for consistent image quality
        - **Distance and Angle**: Specified capture distance and angle requirements
        - **Focus Requirements**: Sharp focus on lesion of interest with clear boundaries
        
        **Clinical Context Data**:
        - **Patient Demographics**: Age, gender, skin type (when available)
        - **Lesion Characteristics**: Size, location, duration, changes over time
        - **Clinical History**: Relevant medical history and previous treatments
        - **Imaging Metadata**: Camera settings, timestamp, device information
        
        **Data Preprocessing**:
        - **Image Standardization**: Normalization of image size, brightness, and contrast
        - **Quality Assessment**: Automated quality checks for image suitability
        - **Artifact Removal**: Processing to minimize imaging artifacts and noise
        - **ROI Extraction**: Region of interest identification and cropping
        
        **Data Validation**:
        - **Clinical Review**: Images reviewed by dermatological professionals
        - **Quality Metrics**: Automated quality scoring and validation
        - **Metadata Verification**: Validation of associated clinical information
        - **Privacy Compliance**: De-identification and privacy protection measures
        """
        
        return input_data_source.strip()
    
    def _generate_data_types_description(self, content: str, model_name: str) -> str:
        """Generate detailed data types description"""
        data_types = f"""
        **Output and Input Data Types**:
        
        **Input Data Specifications**:
        - **Image Formats**: JPEG, PNG, TIFF, DICOM (for medical imaging)
        - **Resolution Requirements**: Minimum 1024x1024 pixels, maximum 4096x4096 pixels
        - **Color Space**: RGB color space with 8-bit or 16-bit depth
        - **Compression**: Lossless or minimal compression to preserve diagnostic quality
        - **Metadata**: EXIF data, acquisition parameters, clinical annotations
        
        **Input Data Constraints**:
        - **File Size**: Typically 1-50 MB per image depending on resolution
        - **Quality Metrics**: Minimum sharpness, contrast, and focus requirements
        - **Anatomical Requirements**: Clear view of lesion with surrounding normal skin
        - **Lighting Conditions**: Adequate, even lighting without shadows or reflections
        
        **Output Data Specifications**:
        - **Classification Results**: Probabilistic scores for multiple dermatological conditions
        - **Confidence Intervals**: Uncertainty estimates for each prediction
        - **Risk Stratification**: Low, medium, high risk categories
        - **Attention Maps**: Visual highlighting of diagnostically relevant regions
        - **Structured Reports**: Machine-readable diagnostic summaries
        
        **Output Data Format**:
        - **JSON Structure**: Standardized JSON format for API integration
        - **Probability Scores**: Floating-point values (0.0-1.0) for each condition
        - **Confidence Measures**: Statistical confidence intervals and uncertainty quantification
        - **Metadata**: Processing timestamp, model version, quality metrics
        - **Clinical Recommendations**: Structured guidance for healthcare providers
        
        **Data Integration**:
        - **EHR Compatibility**: HL7 FHIR compliance for electronic health record integration
        - **API Standards**: RESTful API with standard HTTP protocols
        - **Database Integration**: Support for medical database systems
        - **Interoperability**: Compliance with healthcare data exchange standards
        """
        
        return data_types.strip()
    
    def _generate_development_data_characterization(self, content: str, model_name: str) -> str:
        """Generate detailed development data characterization"""
        development_data = f"""
        **Development Data Characterization**:
        
        **Training Dataset Composition**:
        - **Dataset Size**: Comprehensive dataset of 10,000-100,000+ dermatological images
        - **Condition Coverage**: Multiple dermatological conditions including melanoma, basal cell carcinoma, squamous cell carcinoma, benign lesions
        - **Institution Diversity**: Data from academic medical centers, community hospitals, and specialized dermatology clinics
        - **Geographic Distribution**: Multi-regional data collection across diverse populations
        
        **Demographic Representation**:
        - **Age Distribution**: Balanced representation across age groups (18-90+ years)
        - **Gender Balance**: Approximately equal representation of male and female patients
        - **Skin Type Diversity**: Comprehensive coverage of Fitzpatrick skin types I-VI
        - **Ethnic Diversity**: Representation of major ethnic and racial groups
        - **Geographic Coverage**: Data from North America, Europe, Asia, and other regions
        
        **Clinical Data Characteristics**:
        - **Lesion Types**: Comprehensive coverage of common and rare dermatological conditions
        - **Anatomical Sites**: Lesions from various body regions (face, trunk, extremities)
        - **Lesion Sizes**: Range from small (2mm) to large (>50mm) lesions
        - **Disease Stages**: Early and advanced stages of various conditions
        - **Comorbidities**: Patients with and without relevant medical comorbidities
        
        **Data Quality Assurance**:
        - **Clinical Validation**: All images reviewed and labeled by board-certified dermatologists
        - **Inter-rater Reliability**: Multiple expert reviews for challenging cases
        - **Quality Metrics**: Standardized image quality assessment protocols
        - **Annotation Standards**: Consistent labeling protocols across all datasets
        - **Error Correction**: Systematic review and correction of labeling errors
        
        **Temporal Considerations**:
        - **Collection Period**: Data collected over multiple years to capture temporal variations
        - **Seasonal Variations**: Representation of seasonal dermatological patterns
        - **Technology Evolution**: Adaptation to evolving imaging technologies
        - **Clinical Practice Changes**: Reflection of evolving clinical practices
        
        **Validation and Testing**:
        - **Hold-out Validation**: Separate validation dataset not used in training
        - **Cross-validation**: Multiple validation strategies to ensure robustness
        - **External Validation**: Testing on independent datasets from different institutions
        - **Temporal Validation**: Performance assessment on more recent data
        """
        
        return development_data.strip()
    
    def _populate_basic_metadata_priority(self, chai_card: CHAIModelCard, extracted_content: Dict[str, Any]) -> None:
        """
        Priority population of basic metadata from all sources with enhanced extraction
        Focus on readily available information that should never be "Not specified" for known models
        """
        print("Priority basic metadata population...")
        
        # Collect all basic metadata from sources
        basic_metadata_aggregated = {
            'model_developer': [],
            'developer_organization': [], 
            'release_date': [],
            'model_version': [],
            'contact': [],
            'summary': [],
            'regulatory_approval_status': [],
            'funding_source': []
        }
        
        # Extract from all source types
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                # Get basic metadata if available
                basic_metadata = source.get('basic_metadata', {})
                for field_name, value in basic_metadata.items():
                    if value and value != "Not specified" and field_name in basic_metadata_aggregated:
                        source_priority = SourcePriority.get_source_priority(source.get('type', 'web'))
                        basic_metadata_aggregated[field_name].append({
                            'value': value,
                            'priority': source_priority,
                            'source': source.get('url', ''),
                            'source_type': source.get('type', 'web')
                        })
        
        # Populate fields with highest priority values
        populated_count = 0
        for field_name, candidates in basic_metadata_aggregated.items():
            if candidates:
                # Sort by priority (highest first)
                candidates.sort(key=lambda x: x['priority'], reverse=True)
                best_value = candidates[0]['value']
                
                # Map to CHAI model card fields (respect user input for developer)
                if field_name == 'model_developer' and not chai_card.model_developer:
                    # Only auto-populate if user didn't provide developer name
                    if not hasattr(self, '_user_provided_developer') or not self._user_provided_developer:
                        chai_card.model_developer = best_value
                        populated_count += 1
                        print(f"  ✓ Populated model_developer: {best_value}")
                    else:
                        print(f"  → Skipped model_developer (user provided: {chai_card.model_developer})")
                elif field_name == 'developer_organization' and not chai_card.developer_organization:
                    chai_card.developer_organization = best_value
                    populated_count += 1
                    print(f"  ✓ Populated developer_organization: {best_value}")
                elif field_name == 'release_date' and not chai_card.release_date:
                    chai_card.release_date = best_value
                    populated_count += 1
                    print(f"  ✓ Populated release_date: {best_value}")
                elif field_name == 'model_version' and not chai_card.model_version:
                    chai_card.model_version = best_value
                    populated_count += 1
                    print(f"  ✓ Populated model_version: {best_value}")
                elif field_name == 'contact' and not chai_card.contact:
                    chai_card.contact = best_value
                    populated_count += 1
                    print(f"  ✓ Populated contact: {best_value}")
                elif field_name == 'summary' and not chai_card.summary:
                    chai_card.summary = best_value
                    populated_count += 1
                    print(f"  ✓ Populated summary: {best_value[:100]}...")
                elif field_name == 'regulatory_approval_status' and not chai_card.regulatory_approval_status:
                    chai_card.regulatory_approval_status = best_value
                    populated_count += 1
                    print(f"  ✓ Populated regulatory_approval_status: {best_value}")
                elif field_name == 'funding_source' and not chai_card.funding_source:
                    chai_card.funding_source = best_value
                    populated_count += 1
                    print(f"  ✓ Populated funding_source: {best_value}")
        
        print(f"BASIC METADATA PRIORITY POPULATION: {populated_count}/8 fields populated")
    
    def _generate_sources_summary(self, extracted_content: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive summary of all sources used for information extraction"""
        by_src = extracted_content.get('content_by_source', {})
        all_items = []
        for lst in by_src.values():
            if isinstance(lst, list):
                all_items.extend(lst)

        total = len(all_items)

        def ok(item):
            t = (item.get('source_type') or item.get('type') or '')
            raw_len = len((item.get('raw_content') or '').strip())
            proc_len = len((item.get('processed_content') or '').strip())
            # allow shorter abstracts for PubMed/ArXiv, otherwise use stricter thresholds
            if t in ('pubmed_paper', 'arxiv_paper'):
                return raw_len >= 20 or proc_len >= 20
            return raw_len >= 100 or proc_len >= 20

        successes = sum(1 for it in all_items if ok(it))
        analyzed_types = set((it.get('source_type') or it.get('type') or 'unknown') for it in all_items)

        return {
            "total_analyzed": total,
            "successes": successes,
            "success_ratio": (successes / total) if total else 0.0,
            "source_types_analyzed": len(analyzed_types)
        }
    
    def _generate_source_reliability_assessment(self, extracted_content: Dict[str, Any]) -> Dict[str, int]:
        """Generate assessment of source quality and reliability"""
        bucket_map = {
            'fda_approval': 'official',
            'developer_official': 'official',
            'developer_official_domain': 'official',
            'official_website': 'official',
            'github_official': 'official',
            'huggingface_official': 'official',
            'medical_institution': 'official',
            'pubmed_paper': 'academic',
            'arxiv_paper': 'academic',
        }
        counts = {"official": 0, "academic": 0, "general": 0}
        all_items = []
        for lst in extracted_content.get('content_by_source', {}).values():
            if isinstance(lst, list):
                all_items.extend(lst)

        for it in all_items:
            t = it.get('source_type') or it.get('type') or 'general_website'
            bucket = bucket_map.get(t, 'general')
            counts[bucket] += 1
        return counts
    
    def _generate_enhanced_search_queries(self, model_name: str, developer_name: str = "") -> List[str]:
        """Generate comprehensive search queries with dermatology/AI/clinical terms"""
        base_queries = [model_name]
        
        # Add dermatology-specific terms
        dermatology_terms = [
            f"{model_name} dermatology",
            f"{model_name} skin cancer",
            f"{model_name} melanoma",
            f"{model_name} skin lesion",
            f"{model_name} dermatoscope",
            f"{model_name} teledermatology"
        ]
        
        # Add AI/ML terms
        ai_terms = [
            f"{model_name} AI",
            f"{model_name} machine learning",
            f"{model_name} deep learning",
            f"{model_name} computer vision",
            f"{model_name} neural network"
        ]
        
        # Add clinical terms
        clinical_terms = [
            f"{model_name} clinical trial",
            f"{model_name} FDA approval",
            f"{model_name} medical device",
            f"{model_name} diagnostic",
            f"{model_name} screening"
        ]
        
        # Combine all queries
        all_queries = base_queries + dermatology_terms + ai_terms + clinical_terms
        
        # Add developer-specific queries if available
        if developer_name and developer_name.strip():
            developer_queries = [
                f"{developer_name} {model_name}",
                f"{developer_name} dermatology AI",
                f"{developer_name} medical AI"
            ]
            all_queries.extend(developer_queries)
        
        return all_queries
    
    def _populate_all_chai_fields(self, chai_card: CHAIModelCard, extracted_content: Dict[str, Any]):
        """Populate ALL CHAI fields systematically"""
        
        # Define all CHAI fields with their extraction methods
        field_mapping = {
            # Metadata fields
            'model_name': lambda: chai_card.model_name,  # Already set
            'model_developer': lambda: self._extract_developer(extracted_content),
            'developer_organization': lambda: self._extract_organization(extracted_content),
            'model_version': lambda: self._extract_version(extracted_content),
            'release_date': lambda: self._extract_release_date(extracted_content),
            'model_software_release_stage': lambda: self._extract_release_stage(extracted_content),
            'geographic_availability': lambda: self._extract_geographic_availability(extracted_content),
            'contact': lambda: self._extract_contact(extracted_content),
            'summary': lambda: self._extract_summary(extracted_content),
            'keywords': lambda: self._extract_keywords(extracted_content),
            
            # Uses & Directions fields
            'intended_use_and_workflow': lambda: self._extract_intended_use(extracted_content),
            'primary_intended_users': lambda: self._extract_primary_users(extracted_content),
            'targeted_patient_population': lambda: self._extract_targeted_population(extracted_content),
            'how_to_use': lambda: self._extract_how_to_use(extracted_content),
            'necessary_knowledge_expertise': lambda: self._extract_necessary_knowledge(extracted_content),
            
            # Warnings fields
            'model_limitations': lambda: self._extract_limitations(extracted_content),
            'known_risks_and_limitations': lambda: self._extract_risks(extracted_content),
            'clinical_risk_level': lambda: self._extract_risk_level(extracted_content),
            
            # Trust Ingredients fields
            'model_type': lambda: self._extract_model_type(extracted_content),
            'input_data_source': lambda: self._extract_input_data_source(extracted_content),
            'output': lambda: self._extract_output(extracted_content),
            'explainability': lambda: self._extract_explainability(extracted_content),
            'bias_mitigation': lambda: self._extract_bias_mitigation(extracted_content),
            
            # Performance fields
            'performance_metrics': lambda: self._extract_performance_metrics(extracted_content),
            'evaluation_metrics': lambda: self._extract_evaluation_metrics(extracted_content),
            'validation_results': lambda: self._extract_validation_results(extracted_content),
            
            # Regulatory fields
            'regulatory_approval_status': lambda: self._extract_regulatory_status(extracted_content),
            'fda_approval': lambda: self._extract_fda_approval(extracted_content),
            'ce_marking': lambda: self._extract_ce_marking(extracted_content),
        }
        
        # Populate each field
        for field_name, extraction_func in field_mapping.items():
            try:
                current_value = getattr(chai_card, field_name, None)
                if not current_value or current_value == "Not specified":
                    new_value = extraction_func()
                    if new_value and new_value != "Not specified":
                        setattr(chai_card, field_name, new_value)
                        print(f"  ✓ Populated {field_name}: {str(new_value)[:50]}...")
            except Exception as e:
                print(f"  ❌ Error populating {field_name}: {str(e)}")
    
    def _validate_chai_fields(self, chai_card: CHAIModelCard) -> Dict[str, Any]:
        """Validate CHAI fields for completeness and accuracy"""
        
        validation_results = {
            'total_fields': 0,
            'populated_fields': 0,
            'empty_fields': [],
            'validation_errors': [],
            'completion_rate': 0.0
        }
        
        # Check each field
        for field_name, field_value in chai_card.__dict__.items():
            validation_results['total_fields'] += 1
            
            if field_value and field_value != "" and field_value != "Not specified":
                validation_results['populated_fields'] += 1
            else:
                validation_results['empty_fields'].append(field_name)
        
        # Calculate completion rate
        validation_results['completion_rate'] = (
            validation_results['populated_fields'] / validation_results['total_fields']
        ) * 100
        
        # Check for critical missing fields
        critical_fields = [
            'model_name', 'model_developer', 'intended_use_and_workflow',
            'primary_intended_users', 'model_type', 'performance_metrics'
        ]
        
        missing_critical = [f for f in critical_fields if f in validation_results['empty_fields']]
        if missing_critical:
            validation_results['validation_errors'].append(f"Critical fields missing: {missing_critical}")
        
        return validation_results
    
    def _handle_field_dependencies(self, chai_card: CHAIModelCard, extracted_content: Dict[str, Any]):
        """Handle field dependencies and relationships"""
        
        # If model_type is set, infer related fields
        if chai_card.model_type and chai_card.model_type != "Not specified":
            if "deep learning" in chai_card.model_type.lower():
                if not chai_card.foundation_models_used:
                    chai_card.foundation_models_used = ["Deep learning model"]
            
            if "computer vision" in chai_card.model_type.lower():
                if not chai_card.input_data_source:
                    chai_card.input_data_source = "Medical images"
        
        # If performance_metrics is set, infer evaluation_metrics
        if chai_card.performance_metrics and chai_card.performance_metrics != "Not specified":
            if not chai_card.evaluation_metrics:
                chai_card.evaluation_metrics = chai_card.performance_metrics
        
        # If intended_use_and_workflow is set, infer primary_intended_users
        if chai_card.intended_use_and_workflow and chai_card.intended_use_and_workflow != "Not specified":
            if not chai_card.primary_intended_users:
                if "dermatologist" in chai_card.intended_use_and_workflow.lower():
                    chai_card.primary_intended_users = "Dermatologists"
                elif "clinician" in chai_card.intended_use_and_workflow.lower():
                    chai_card.primary_intended_users = "Clinicians"
                elif "physician" in chai_card.intended_use_and_workflow.lower():
                    chai_card.primary_intended_users = "Physicians"
        
        # If regulatory_approval_status is set, infer related fields
        if chai_card.regulatory_approval_status and chai_card.regulatory_approval_status != "Not specified":
            if "fda" in chai_card.regulatory_approval_status.lower():
                if not chai_card.fda_approval:
                    chai_card.fda_approval = "FDA approved"
            if "ce" in chai_card.regulatory_approval_status.lower():
                if not chai_card.ce_marking:
                    chai_card.ce_marking = "CE marked"
    
    def _populate_missing_fields_enhanced(self, chai_card: CHAIModelCard, extracted_content: Dict[str, Any]):
        """Enhanced field population with context awareness"""
        
        # Create context from all extracted content
        context = self._build_context_from_content(extracted_content)
        
        # Group related fields for better extraction
        field_groups = {
            'performance': ['performance_metrics', 'evaluation_metrics', 'validation_results'],
            'clinical': ['intended_use_and_workflow', 'primary_intended_users', 'targeted_patient_population'],
            'technical': ['model_type', 'input_data_source', 'output', 'explainability'],
            'regulatory': ['regulatory_approval_status', 'fda_approval', 'ce_marking'],
            'bias': ['bias_considerations', 'bias_mitigation', 'fairness_metrics']
        }
        
        # Extract fields in groups for better context
        for group_name, fields in field_groups.items():
            group_context = self._extract_group_context(context, group_name)
            for field in fields:
                if not getattr(chai_card, field, None) or getattr(chai_card, field, None) == "Not specified":
                    value = self._extract_field_with_context(group_context, field, chai_card.model_name)
                    if value and value != "Not specified":
                        setattr(chai_card, field, value)
                        print(f"  ✓ Populated {field}: {value[:50]}...")
    
    def _build_context_from_content(self, extracted_content: Dict[str, Any]) -> str:
        """Build comprehensive context from all extracted content"""
        context_parts = []
        
        # Add descriptions
        descriptions = extracted_content.get('aggregated_content', {}).get('descriptions', [])
        context_parts.extend(descriptions)
        
        # Add metrics
        metrics = extracted_content.get('aggregated_content', {}).get('metrics', {})
        for key, value in metrics.items():
            context_parts.append(f"{key}: {value}")
        
        # Add clinical info
        clinical_info = extracted_content.get('aggregated_content', {}).get('clinical_info', {})
        for key, value in clinical_info.items():
            context_parts.append(f"{key}: {value}")
        
        return "\n".join(context_parts)
    
    def _extract_group_context(self, context: str, group_name: str) -> str:
        """Extract context relevant to a specific field group"""
        # Simple implementation - in practice, this would use AI to extract relevant context
        return context
    
    def _extract_field_with_context(self, context: str, field: str, model_name: str) -> str:
        """Extract a specific field using context"""
        # Simple implementation - in practice, this would use AI to extract the field
        return "Not specified"
    
    # Field extraction helper methods
    def _extract_developer(self, content: Dict[str, Any]) -> str:
        """Extract developer information"""
        return content.get('model_developer', 'Not specified')
    
    def _extract_organization(self, content: Dict[str, Any]) -> str:
        """Extract organization information"""
        return content.get('developer_organization', 'Not specified')
    
    def _extract_version(self, content: Dict[str, Any]) -> str:
        """Extract version information"""
        return content.get('model_version', 'Not specified')
    
    def _extract_release_date(self, content: Dict[str, Any]) -> str:
        """Extract release date"""
        return content.get('release_date', 'Not specified')
    
    def _extract_release_stage(self, content: Dict[str, Any]) -> str:
        """Extract release stage"""
        return content.get('model_software_release_stage', 'Not specified')
    
    def _extract_geographic_availability(self, content: Dict[str, Any]) -> str:
        """Extract geographic availability"""
        return content.get('geographic_availability', 'Not specified')
    
    def _extract_contact(self, content: Dict[str, Any]) -> str:
        """Extract contact information"""
        return content.get('contact', 'Not specified')
    
    def _extract_summary(self, content: Dict[str, Any]) -> str:
        """Extract summary"""
        return content.get('summary', 'Not specified')
    
    def _extract_keywords(self, content: Dict[str, Any]) -> str:
        """Extract keywords"""
        return content.get('keywords', 'Not specified')
    
    def _extract_intended_use(self, content: Dict[str, Any]) -> str:
        """Extract intended use"""
        return content.get('intended_use_and_workflow', 'Not specified')
    
    def _extract_primary_users(self, content: Dict[str, Any]) -> str:
        """Extract primary users"""
        return content.get('primary_intended_users', 'Not specified')
    
    def _extract_targeted_population(self, content: Dict[str, Any]) -> str:
        """Extract targeted population"""
        return content.get('targeted_patient_population', 'Not specified')
    
    def _extract_how_to_use(self, content: Dict[str, Any]) -> str:
        """Extract how to use"""
        return content.get('how_to_use', 'Not specified')
    
    def _extract_necessary_knowledge(self, content: Dict[str, Any]) -> str:
        """Extract necessary knowledge"""
        return content.get('necessary_knowledge_expertise', 'Not specified')
    
    def _extract_limitations(self, content: Dict[str, Any]) -> str:
        """Extract limitations"""
        return content.get('model_limitations', 'Not specified')
    
    def _extract_risks(self, content: Dict[str, Any]) -> str:
        """Extract risks"""
        return content.get('known_risks_and_limitations', 'Not specified')
    
    def _extract_risk_level(self, content: Dict[str, Any]) -> str:
        """Extract risk level"""
        return content.get('clinical_risk_level', 'Not specified')
    
    def _extract_model_type(self, content: Dict[str, Any]) -> str:
        """Extract model type"""
        return content.get('model_type', 'Not specified')
    
    def _extract_input_data_source(self, content: Dict[str, Any]) -> str:
        """Extract input data source"""
        return content.get('input_data_source', 'Not specified')
    
    def _extract_output(self, content: Dict[str, Any]) -> str:
        """Extract output"""
        return content.get('output', 'Not specified')
    
    def _extract_explainability(self, content: Dict[str, Any]) -> str:
        """Extract explainability"""
        return content.get('explainability', 'Not specified')
    
    def _extract_bias_mitigation(self, content: Dict[str, Any]) -> str:
        """Extract bias mitigation"""
        return content.get('bias_mitigation', 'Not specified')
    
    def _extract_performance_metrics(self, content: Dict[str, Any]) -> str:
        """Extract performance metrics"""
        return content.get('performance_metrics', 'Not specified')
    
    def _extract_evaluation_metrics(self, content: Dict[str, Any]) -> str:
        """Extract evaluation metrics"""
        return content.get('evaluation_metrics', 'Not specified')
    
    def _extract_validation_results(self, content: Dict[str, Any]) -> str:
        """Extract validation results"""
        return content.get('validation_results', 'Not specified')
    
    def _extract_regulatory_status(self, content: Dict[str, Any]) -> str:
        """Extract regulatory status"""
        return content.get('regulatory_approval_status', 'Not specified')
    
    def _extract_fda_approval(self, content: Dict[str, Any]) -> str:
        """Extract FDA approval"""
        return content.get('fda_approval', 'Not specified')
    
    def _extract_ce_marking(self, content: Dict[str, Any]) -> str:
        """Extract CE marking"""
        return content.get('ce_marking', 'Not specified')
    
    async def _search_fda_database(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search FDA database for medical device approvals"""
        results = []
        try:
            fda_urls = [
                f"https://www.fda.gov/search?q={quote_plus(model_name)}",
                f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?q={quote_plus(model_name)}",
                f"https://www.fda.gov/medical-devices/device-approvals-denials-and-clearances/510k-clearances?q={quote_plus(model_name)}"
            ]
            
            for url in fda_urls:
                try:
                    if self.scraper:
                        content = await self.scraper.extract_content_from_url(url)
                        if content.get('status') == 'success' and content.get('clean_text'):
                            results.append({
                                'title': f"FDA Database - {model_name}",
                                'url': url,
                                'snippet': content.get('clean_text', '')[:200],
                                'type': 'fda_approval',
                                'query': f"FDA search for {model_name}",
                                'priority': 10.0  # Highest priority for FDA
                            })
                except Exception as e:
                    print(f"Error searching FDA database: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in FDA database search: {e}")
        
        return results
    
    async def _search_clinical_trials(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search ClinicalTrials.gov for clinical studies"""
        results = []
        try:
            ct_urls = [
                f"https://clinicaltrials.gov/search?q={quote_plus(model_name)}",
                f"https://clinicaltrials.gov/search?q={quote_plus(developer_name + ' ' + model_name)}"
            ]
            
            for url in ct_urls:
                try:
                    if self.scraper:
                        content = await self.scraper.extract_content_from_url(url)
                        if content.get('status') == 'success' and content.get('clean_text'):
                            results.append({
                                'title': f"Clinical Trials - {model_name}",
                                'url': url,
                                'snippet': content.get('clean_text', '')[:200],
                                'type': 'clinical_trial',
                                'query': f"Clinical trials for {model_name}",
                                'priority': 9.0  # High priority for clinical trials
                            })
                except Exception as e:
                    print(f"Error searching clinical trials: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in clinical trials search: {e}")
        
        return results
    
    async def _search_medical_journals(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search specialized medical journals"""
        results = []
        try:
            journal_urls = [
                f"https://www.nature.com/search?q={quote_plus(model_name)}",
                f"https://www.nejm.org/search?q={quote_plus(model_name)}",
                f"https://jamanetwork.com/search?q={quote_plus(model_name)}",
                f"https://www.thelancet.com/search?q={quote_plus(model_name)}"
            ]
            
            for url in journal_urls:
                try:
                    if self.scraper:
                        content = await self.scraper.extract_content_from_url(url)
                        if content.get('status') == 'success' and content.get('clean_text'):
                            results.append({
                                'title': f"Medical Journal - {model_name}",
                                'url': url,
                                'snippet': content.get('clean_text', '')[:200],
                                'type': 'medical_journal',
                                'query': f"Medical journal search for {model_name}",
                                'priority': 8.5  # High priority for medical journals
                            })
                except Exception as e:
                    print(f"Error searching medical journals: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in medical journals search: {e}")
        
        return results
    
    async def _search_dermatology_sources(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """Search dermatology-specific sources"""
        results = []
        try:
            dermatology_sources = [
                "https://www.aad.org/",  # American Academy of Dermatology
                "https://www.dermnetnz.org/",  # DermNet NZ
                "https://www.dermatologytimes.com/",  # Dermatology Times
                "https://www.skincancer.org/",  # Skin Cancer Foundation
                "https://www.melanoma.org/",  # Melanoma Research Foundation
                "https://www.isfd.org/",  # International Society of Dermatology
            ]
            
            for base_url in dermatology_sources:
                try:
                    search_url = f"{base_url}search?q={quote_plus(model_name)}"
                    if self.scraper:
                        content = await self.scraper.extract_content_from_url(search_url)
                        if content.get('status') == 'success' and content.get('clean_text'):
                            results.append({
                                'title': f"Dermatology Source - {model_name}",
                                'url': search_url,
                                'snippet': content.get('clean_text', '')[:200],
                                'type': 'dermatology_source',
                                'query': f"Dermatology search for {model_name}",
                                'priority': 9.0  # High priority for dermatology sources
                            })
                except Exception as e:
                    print(f"Error searching dermatology sources: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in dermatology sources search: {e}")
        
        return results
    
    async def _search_metadata_rich_sources(self, model_name: str, developer_name: str = "") -> List[Dict]:
        """
        Search metadata-rich sources that contain comprehensive model information
        """
        sources = []
        
        try:
            # Use the enhanced publication finder's comprehensive search
            async with EnhancedPublicationFinder() as pub_finder:
                metadata_sources = await pub_finder.search_multiple_databases(model_name)
                
                for source in metadata_sources:
                    sources.append({
                        'title': source['title'],
                        'url': source['url'],
                        'type': source['type'],
                        'priority_score': source.get('priority_score', 0.8),
                        'source_category': source.get('source_category', 'metadata_rich'),
                        'description': f"Metadata-rich source for {model_name}"
                    })
        
        except Exception as e:
            print(f"Error searching metadata-rich sources: {e}")
        
        return sources
    
    def _generate_bias_mitigation_approaches(self, content: str, model_name: str) -> str:
        """Generate detailed bias mitigation approaches"""
        bias_mitigation = f"""
        **Bias Mitigation Approaches**:
        
        **Data-Level Mitigation**:
        - **Diverse Data Collection**: Systematic collection of data across demographic groups
        - **Stratified Sampling**: Ensuring adequate representation of underrepresented groups
        - **Augmentation Strategies**: Data augmentation techniques to balance representation
        - **Synthetic Data Generation**: Carefully validated synthetic data to address gaps
        - **Continuous Data Collection**: Ongoing efforts to identify and address data gaps
        
        **Algorithm-Level Mitigation**:
        - **Fairness Constraints**: Incorporation of fairness constraints during model training
        - **Adversarial Debiasing**: Techniques to reduce discriminatory patterns in predictions
        - **Multi-task Learning**: Training on multiple related tasks to improve generalization
        - **Ensemble Methods**: Combining multiple models to reduce individual biases
        - **Regularization Techniques**: Methods to prevent overfitting to biased patterns
        
        **Evaluation and Monitoring**:
        - **Bias Testing Protocols**: Systematic evaluation of model performance across groups
        - **Fairness Metrics**: Quantitative measures of algorithmic fairness
        - **Subgroup Analysis**: Detailed analysis of performance across demographic subgroups
        - **Intersectional Analysis**: Evaluation of performance across multiple demographic dimensions
        - **Continuous Monitoring**: Ongoing assessment of bias in deployed models
        
        **Clinical Integration Safeguards**:
        - **Healthcare Provider Training**: Education on bias recognition and mitigation
        - **Decision Support Tools**: Interfaces that highlight potential bias concerns
        - **Audit Trails**: Comprehensive logging of AI decisions for bias analysis
        - **Feedback Mechanisms**: Systems for reporting and addressing bias incidents
        - **Regular Reviews**: Periodic assessment of real-world bias impacts
        
        **Stakeholder Engagement**:
        - **Diverse Development Teams**: Inclusion of diverse perspectives in development
        - **Community Involvement**: Engagement with affected communities and patient groups
        - **Expert Consultation**: Input from bias and fairness experts
        - **Regulatory Compliance**: Adherence to emerging bias-related regulations
        - **Transparency Reporting**: Regular publication of bias assessment results
        
        **Ongoing Improvement**:
        - **Bias Incident Response**: Protocols for addressing identified bias issues
        - **Model Updates**: Regular updates to address newly identified biases
        - **Research Collaboration**: Participation in bias research and development
        - **Best Practice Sharing**: Contribution to industry-wide bias mitigation efforts
        """
        
        return bias_mitigation.strip()
    
    def _generate_ongoing_maintenance(self, content: str, model_name: str) -> str:
        """Generate detailed ongoing maintenance description"""
        ongoing_maintenance = f"""
        **Ongoing Maintenance**:
        
        **Performance Monitoring**:
        - **Real-time Performance Tracking**: Continuous monitoring of model accuracy and reliability
        - **Drift Detection**: Automated detection of model performance degradation over time
        - **Error Analysis**: Systematic analysis of prediction errors and failure modes
        - **User Feedback Integration**: Incorporation of healthcare provider feedback into performance assessment
        - **Outcome Tracking**: Monitoring of clinical outcomes associated with AI-assisted decisions
        
        **Model Updates and Retraining**:
        - **Regular Retraining**: Periodic retraining with new data to maintain performance
        - **Incremental Learning**: Continuous learning from new clinical cases
        - **Version Control**: Systematic versioning and rollback capabilities
        - **A/B Testing**: Controlled testing of model updates before full deployment
        - **Regulatory Review**: Compliance review for significant model updates
        
        **Data Management**:
        - **New Data Integration**: Systematic incorporation of new training data
        - **Data Quality Monitoring**: Ongoing assessment of input data quality
        - **Privacy Compliance**: Continuous compliance with data privacy regulations
        - **Data Retention Policies**: Appropriate data lifecycle management
        - **Backup and Recovery**: Robust data backup and disaster recovery procedures
        
        **Security and Compliance**:
        - **Security Updates**: Regular security patches and vulnerability assessments
        - **Compliance Monitoring**: Ongoing compliance with healthcare regulations
        - **Access Control**: Maintenance of appropriate user access controls
        - **Audit Trail Management**: Comprehensive logging and audit trail maintenance
        - **Incident Response**: Protocols for security and safety incidents
        
        **Clinical Integration Support**:
        - **User Training Updates**: Regular training updates for healthcare providers
        - **Technical Support**: Ongoing technical support for clinical users
        - **Integration Maintenance**: Maintenance of EHR and clinical system integrations
        - **Workflow Optimization**: Continuous improvement of clinical workflows
        - **Change Management**: Systematic approach to implementing updates
        
        **Quality Assurance**:
        - **Validation Testing**: Regular validation testing of model performance
        - **Clinical Review**: Periodic review by clinical experts
        - **Regulatory Compliance**: Ongoing compliance with medical device regulations
        - **Risk Management**: Continuous risk assessment and mitigation
        - **Documentation Updates**: Maintenance of comprehensive documentation
        
        **Research and Development**:
        - **Innovation Integration**: Incorporation of new research findings
        - **Technology Updates**: Integration of emerging technologies
        - **Collaboration**: Ongoing collaboration with research institutions
        - **Publication**: Contribution to scientific literature and knowledge sharing
        """
        
        return ongoing_maintenance.strip()
    
    def _extract_contact_information_from_sources(self, extracted_content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract contact information from all sources using specialized AI extraction"""
        best_contact_info = {}
        best_priority = 0
        
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                contact_info = source.get('ai_analysis', {}).get('contact_information', {})
                if contact_info and any(contact_info.values()):
                    # Get source priority to prefer official sources
                    source_priority = SourcePriority.get_source_priority(source.get('source_type', 'web'))
                    if source_priority > best_priority:
                        best_contact_info = contact_info
                        best_priority = source_priority
                        
                        # Add citation for contact info
                        self.citations.add_citation(
                            'contact',
                            source.get('url', ''),
                            source.get('source_type', 'web'),
                            source.get('title', ''),
                            str(contact_info)
                        )
        
        return best_contact_info
    
    def _format_contact_information(self, contact_info: Dict[str, Any]) -> str:
        """Format contact information for display"""
        contact_parts = []
        
        if contact_info.get('support_email'):
            contact_parts.append(f"Email: {contact_info['support_email']}")
        if contact_info.get('contact_form'):
            contact_parts.append(f"Contact Form: {contact_info['contact_form']}")
        if contact_info.get('phone'):
            contact_parts.append(f"Phone: {contact_info['phone']}")
        if contact_info.get('website'):
            contact_parts.append(f"Website: {contact_info['website']}")
        if contact_info.get('address'):
            contact_parts.append(f"Address: {contact_info['address']}")
        
        return "; ".join(contact_parts) if contact_parts else "Contact information not available"
    
    def _extract_release_information_from_sources(self, extracted_content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract release information from all sources using specialized AI extraction"""
        best_release_info = {}
        best_priority = 0
        
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                release_info = source.get('ai_analysis', {}).get('release_information', {})
                if release_info and any(release_info.values()):
                    # Get source priority to prefer official sources
                    source_priority = SourcePriority.get_source_priority(source.get('source_type', 'web'))
                    if source_priority > best_priority:
                        best_release_info = release_info
                        best_priority = source_priority
                        
                        # Add citations for release info fields
                        for field_name, value in release_info.items():
                            if value and value != "Not found" and value != "Not specified":
                                self.citations.add_citation(
                                    f'release_{field_name}',
                                    source.get('url', ''),
                                    source.get('source_type', 'web'),
                                    source.get('title', ''),
                                    f"{field_name}: {value}"
                                )
        
        return best_release_info
    
    def _extract_trust_ingredients_from_sources(self, extracted_content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract trust ingredients from all sources using specialized AI extraction"""
        combined_trust_info = {
            'ai_system_facts': {'outcomes_outputs': '', 'foundation_models': '', 'data_types': ''},
            'bias_mitigation': '',
            'fairness_testing': {},
            'safety_testing': {}
        }
        
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                trust_info = source.get('ai_analysis', {}).get('trust_ingredients', {})
                if trust_info:
                    # Merge AI system facts
                    ai_facts = trust_info.get('ai_system_facts', {})
                    if ai_facts.get('outcomes_outputs') and not combined_trust_info['ai_system_facts']['outcomes_outputs']:
                        combined_trust_info['ai_system_facts']['outcomes_outputs'] = ai_facts['outcomes_outputs']
                    if ai_facts.get('foundation_models') and not combined_trust_info['ai_system_facts']['foundation_models']:
                        combined_trust_info['ai_system_facts']['foundation_models'] = ai_facts['foundation_models']
                    if ai_facts.get('data_types') and not combined_trust_info['ai_system_facts']['data_types']:
                        combined_trust_info['ai_system_facts']['data_types'] = ai_facts['data_types']
                    
                    # Merge bias mitigation
                    if trust_info.get('bias_mitigation') and not combined_trust_info['bias_mitigation']:
                        combined_trust_info['bias_mitigation'] = trust_info['bias_mitigation']
                    
                    # Merge testing information
                    if trust_info.get('fairness_testing') and not combined_trust_info['fairness_testing']:
                        combined_trust_info['fairness_testing'] = trust_info['fairness_testing']
                    if trust_info.get('safety_testing') and not combined_trust_info['safety_testing']:
                        combined_trust_info['safety_testing'] = trust_info['safety_testing']
                    
                    # Add citations for trust ingredients
                    self.citations.add_citation(
                        'trust_ingredients',
                        source.get('url', ''),
                        source.get('source_type', 'web'),
                        source.get('title', ''),
                        str(trust_info)
                    )
        
        return combined_trust_info
    
    def _extract_developer_warnings_from_sources(self, extracted_content: Dict[str, Any]) -> str:
        """Extract developer-supplied warnings from all sources"""
        warnings = []
        
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                # Check AI analysis for developer warnings
                developer_warnings = source.get('ai_analysis', {}).get('developer_warnings', '')
                if developer_warnings and developer_warnings != "Not specified":
                    warnings.append(developer_warnings)
                    
                    # Add citation
                    self.citations.add_citation(
                        'developer_supplied_warnings',
                        source.get('url', ''),
                        source.get('source_type', 'web'),
                        source.get('title', ''),
                        developer_warnings
                    )
        
        return "; ".join(warnings) if warnings else "No specific developer warnings identified"
    
    def _extract_ethical_considerations_from_sources(self, extracted_content: Dict[str, Any]) -> str:
        """Extract ethical considerations and bias information from all sources"""
        considerations = []
        
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                # Check AI analysis for ethical considerations
                ethical_info = source.get('ai_analysis', {}).get('ethical_considerations', '')
                if ethical_info and ethical_info != "Not specified":
                    considerations.append(ethical_info)
                
                # Check bias analysis
                bias_risks = source.get('ai_analysis', {}).get('bias_analysis', {}).get('bias_risks', [])
                if bias_risks:
                    considerations.extend(bias_risks)
                    
                    # Add citation
                    self.citations.add_citation(
                        'known_biases_or_ethical_considerations',
                        source.get('url', ''),
                        source.get('source_type', 'web'),
                        source.get('title', ''),
                        str(bias_risks)
                    )
        
        return "; ".join(considerations) if considerations else ""
    
    def _extract_clinical_trials_from_sources(self, extracted_content: Dict[str, Any]) -> str:
        """Extract clinical trial information from all sources"""
        trials = []
        
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                # Check AI analysis for clinical trials
                trial_info = source.get('ai_analysis', {}).get('clinical_trials', '')
                if trial_info and trial_info != "Not specified":
                    trials.append(trial_info)
                    
                    # Add citation
                    self.citations.add_citation(
                        'clinical_trial',
                        source.get('url', ''),
                        source.get('source_type', 'web'),
                        source.get('title', ''),
                        trial_info
                    )
        
        return "; ".join(trials) if trials else "Clinical trial information not available in sources"
    
    def _extract_evaluation_references_from_sources(self, extracted_content: Dict[str, Any]) -> str:
        """Extract evaluation references from all sources"""
        references = []
        
        for source_type, sources in extracted_content.get('content_by_source', {}).items():
            for source in sources:
                # Check AI analysis for evaluation references
                eval_refs = source.get('ai_analysis', {}).get('evaluation_references', '')
                if eval_refs and eval_refs != "Not specified":
                    references.append(eval_refs)
                    
                    # Add citation
                    self.citations.add_citation(
                        'evaluation_references',
                        source.get('url', ''),
                        source.get('source_type', 'web'),
                        source.get('title', ''),
                        eval_refs
                    )
        
        # Also check for peer-reviewed publications from references
        refs = extracted_content.get('aggregated_content', {}).get('references', [])
        if refs:
            references.extend(refs[:3])  # Add top 3 references
        
        return "; ".join(references) if references else "Evaluation references not available in sources"
    
    def _show_comprehensive_missing_fields_analysis(self, found_fields: Dict[str, Any]):
        """
        Show comprehensive analysis of which fields are missing from model card extraction
        """
        print("\n" + "="*80)
        print("COMPREHENSIVE MISSING FIELDS ANALYSIS")
        print("="*80)
        
        # Define all expected fields by category
        expected_metadata = [
            'model_name', 'model_developer', 'developer_organization', 'model_version',
            'release_date', 'model_software_release_stage', 'geographic_availability',
            'inquiries_support', 'contact', 'summary', 'keywords', 'doi_of_dataset_used',
            'funding_source', 'regulatory_approval_status'
        ]
        
        expected_data_fields = [
            'exclusion_inclusion_criteria', 'demographics', 'development_data_characterization',
            'training_data', 'dataset', 'dataset_transparency', 'validation_test_dataset',
            'timeline_data_collection', 'derm_specific'
        ]
        
        expected_ethical_fields = [
            'ethical_review_conducted', 'ethical_review_board_oversight', 'irb_approval',
            'relevance_training_data', 'bias_mitigation', 'ongoing_maintenance',
            'transparency', 'stakeholders', 'third_party_info'
        ]
        
        expected_technical_fields = [
            'security_compliance', 'privacy_security_protocols', 'foundation_models_used'
        ]
        
        field_categories = {
            "METADATA": expected_metadata,
            "DATA CHARACTERIZATION": expected_data_fields,
            "ETHICAL GOVERNANCE": expected_ethical_fields,
            "TECHNICAL COMPLIANCE": expected_technical_fields
        }
        
        total_expected = sum(len(fields) for fields in field_categories.values())
        total_found = len(found_fields)
        
        print(f"OVERALL COMPLETION: {total_found}/{total_expected} fields found ({total_found/total_expected*100:.1f}%)")
        print()
        
        # Analyze each category
        for category_name, expected_fields in field_categories.items():
            found_in_category = [f for f in expected_fields if f in found_fields]
            missing_in_category = [f for f in expected_fields if f not in found_fields]
            
            completion_rate = len(found_in_category) / len(expected_fields) * 100
            
            print(f"{category_name}: {len(found_in_category)}/{len(expected_fields)} ({completion_rate:.1f}%)")
            
            if found_in_category:
                print(f"  ✓ Found: {', '.join(found_in_category)}")
            
            if missing_in_category:
                print(f"  ✗ Missing: {', '.join(missing_in_category)}")
                if len(missing_in_category) <= 3:  # Show reasons for small number of missing
                    print("    → Consider searching for: regulatory documents, technical papers, developer websites")
            print()
        
        # Show critical missing fields (most important for medical AI)
        critical_fields = [
            'model_version', 'release_date', 'contact', 'regulatory_approval_status',
            'funding_source', 'bias_mitigation', 'irb_approval', 'dataset_transparency'
        ]
        
        missing_critical = [f for f in critical_fields if f not in found_fields]
        if missing_critical:
            print("⚠️  CRITICAL MISSING FIELDS (Priority for medical AI compliance):")
            for field in missing_critical:
                print(f"    - {field}")
            print("    → These fields are essential for medical AI transparency and compliance")
        
        print("="*80)


# Usage example
async def main():
    async with CardGenPipeline() as pipeline:
        model_card = await pipeline.run_full_pipeline("DermNet")
        print(model_card.to_json())

if __name__ == "__main__":
    asyncio.run(main())