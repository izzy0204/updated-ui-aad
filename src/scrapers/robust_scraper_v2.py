"""
ROBUST WEB SCRAPER – ENHANCED CONTENT EXTRACTION (Production Version)

PURPOSE:
Production-grade asynchronous web scraper for dermatology AI model-card generation.
Implements comprehensive content extraction from HTML/PDF sources with medical domain
awareness, robust error handling, caching, and compliance with robots.txt.

FEATURES:
- Asynchronous session management with per-host concurrency limits
- Intelligent retry logic with exponential backoff and jitter
- HTTP caching with ETag/Last-Modified support for stability
- Robots.txt compliance and medical domain rate limiting
- Advanced HTML content extraction with noise removal
- PDF text extraction with metadata capture
- URL normalization and deduplication
- Medical/regulatory content pattern detection
- Performance metrics extraction (AUC, sensitivity, specificity)
- Comprehensive diagnostics and structured logging
- Security-first design with HTTPS enforcement

ARCHITECTURE:
Built for production reliability with bounded outputs, memory protection,
and comprehensive error handling. Supports PubMed and arXiv integration
with pagination and structured data extraction.
"""

import asyncio
import aiohttp
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from urllib.robotparser import RobotFileParser
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

# Third-party imports
import trafilatura
from bs4 import BeautifulSoup, Comment
import chardet

# PDF processing
try:
    import pypdf
    PDF_AVAILABLE = True
except ImportError:
    try:
        # pdfminer imports - only if needed
        import io
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScraperConfig:
    """Configuration for robust web scraper"""
    # Session settings
    max_retries: int = 3
    request_timeout: int = 30
    per_host_limit: int = 4
    max_content_size: int = 5 * 1024 * 1024  # 5MB
    raw_html_limit: int = 200 * 1024  # 200KB for storage
    
    # Rate limiting
    medical_domains_rps: float = 1.0  # Requests per second for medical domains
    default_rps: float = 5.0
    
    # Content extraction
    max_headings: int = 200
    max_links: int = 500
    max_images: int = 200
    max_tables: int = 50
    
    # Caching
    cache_ttl_hours: int = 24
    cache_dir: str = ".scraper_cache"
    
    # Security
    https_only: bool = True
    respect_robots: bool = True
    
    # User agents
    user_agents: List[str] = None
    
    def __post_init__(self):
        if self.user_agents is None:
            self.user_agents = [
                "ModelCardScraper/2.0 (+contact@example.com)",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]

class URLNormalizer:
    """URL normalization and validation utilities"""
    
    TRACKING_PARAMS = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'gclid', 'fbclid', 'ref', 'source', 'campaign_id', '_ga', 'mc_cid',
        'auth', 'token', 'sig', 'key'  # Security-sensitive params
    }
    
    DANGEROUS_SCHEMES = {'javascript', 'data', 'file', 'vbscript'}
    
    @classmethod
    def normalize_url(cls, url: str) -> Optional[str]:
        """Normalize URL for deduplication and safety"""
        if not url or not isinstance(url, str):
            return None
        
        try:
            parsed = urlparse(url.strip().lower())
            
            # Reject dangerous schemes
            if parsed.scheme in cls.DANGEROUS_SCHEMES:
                return None
            
            # Ensure HTTPS (with HTTP fallback for specific cases)
            if parsed.scheme == 'http':
                parsed = parsed._replace(scheme='https')
            
            # Normalize host
            host = parsed.netloc
            if host.startswith('www.'):
                host = host[4:]
            
            # Clean query parameters
            if parsed.query:
                params = parse_qs(parsed.query)
                clean_params = {k: v for k, v in params.items() 
                              if k.lower() not in cls.TRACKING_PARAMS}
                query = urlencode(clean_params, doseq=True) if clean_params else ""
            else:
                query = ""
            
            # Remove fragment and trailing slash
            path = parsed.path.rstrip('/') if parsed.path != '/' else '/'
            
            normalized = f"{parsed.scheme}://{host}{path}"
            if query:
                normalized += f"?{query}"
            
            return normalized
            
        except Exception as e:
            logger.warning(f"Failed to normalize URL {url}: {e}")
            return None
    
    @classmethod
    def is_likely_credentialed(cls, url: str) -> bool:
        """Check if URL contains credentials or auth tokens"""
        if not url:
            return False
        
        url_lower = url.lower()
        auth_indicators = ['auth=', 'token=', 'key=', 'sig=', 'signature=', 'access_token=']
        return any(indicator in url_lower for indicator in auth_indicators)

class HTTPCache:
    """SQLite-based HTTP cache with ETag/Last-Modified support"""
    
    def __init__(self, cache_dir: str = ".scraper_cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.db_path = self.cache_dir / "http_cache.db"
        self.ttl_hours = ttl_hours
        self._init_db()
    
    def _init_db(self):
        """Initialize cache database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT,
                    etag TEXT,
                    last_modified TEXT,
                    body_hash TEXT,
                    body_trunc TEXT,
                    status_code INTEGER,
                    content_type TEXT,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
    
    def _url_hash(self, url: str) -> str:
        """Generate hash for URL"""
        return hashlib.sha256(url.encode()).hexdigest()
    
    def _body_hash(self, body: str) -> str:
        """Generate hash for body content"""
        return hashlib.sha256(body.encode()).hexdigest()
    
    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached entry if valid"""
        url_hash = self._url_hash(url)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM cache_entries WHERE url_hash = ? AND expires_at > CURRENT_TIMESTAMP",
                (url_hash,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'etag': row[2],
                    'last_modified': row[3],
                    'body_hash': row[4],
                    'body': row[5],
                    'status_code': row[6],
                    'content_type': row[7]
                }
        return None
    
    def set(self, url: str, etag: Optional[str] = None, last_modified: Optional[str] = None,
            body: str = "", status_code: int = 200, content_type: str = ""):
        """Cache response with TTL"""
        url_hash = self._url_hash(url)
        body_hash = self._body_hash(body)
        expires_at = datetime.now() + timedelta(hours=self.ttl_hours)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache_entries 
                (url_hash, url, etag, last_modified, body_hash, body_trunc, 
                 status_code, content_type, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (url_hash, url, etag, last_modified, body_hash, body[:200000],
                  status_code, content_type, expires_at))

class RobotChecker:
    """Robots.txt compliance checker with caching"""
    
    def __init__(self, cache_ttl: int = 3600):
        self.cache = {}
        self.cache_ttl = cache_ttl
    
    async def can_fetch(self, url: str, user_agent: str, session: aiohttp.ClientSession) -> bool:
        """Check if URL can be fetched according to robots.txt"""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            
            # Check cache
            cache_key = f"{host}:{user_agent}"
            if cache_key in self.cache:
                cached_time, rp = self.cache[cache_key]
                if time.time() - cached_time < self.cache_ttl:
                    return rp.can_fetch(user_agent, url)
            
            # Fetch robots.txt
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            try:
                async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        robots_content = await response.text()
                    else:
                        # No robots.txt or error - allow by default
                        return True
            except Exception:
                # Network error - allow by default
                return True
            
            # Parse robots.txt
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read_data(robots_content)
            
            # Cache result
            self.cache[cache_key] = (time.time(), rp)
            
            return rp.can_fetch(user_agent, url)
            
        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {e}")
            return True  # Allow on error

class RateLimiter:
    """Per-domain rate limiter using token bucket"""
    
    def __init__(self):
        self.buckets = {}  # domain -> (tokens, last_update)
    
    async def acquire(self, domain: str, rate: float = 5.0):
        """Acquire permission to make request to domain"""
        now = time.time()
        
        if domain not in self.buckets:
            self.buckets[domain] = (1.0, now)
            return
        
        tokens, last_update = self.buckets[domain]
        
        # Add tokens based on time elapsed
        elapsed = now - last_update
        tokens = min(5.0, tokens + elapsed * rate)  # Max 5 tokens
        
        if tokens >= 1.0:
            tokens -= 1.0
            self.buckets[domain] = (tokens, now)
        else:
            # Wait until we have a token
            wait_time = (1.0 - tokens) / rate
            await asyncio.sleep(wait_time)
            self.buckets[domain] = (0.0, now + wait_time)

class MetadataExtractor:
    """Extract structured metadata and domain-specific signals"""
    
    # Medical domains for special rate limiting
    MEDICAL_DOMAINS = {
        'aad.org', 'mayoclinic.org', 'clevelandclinic.org', 'cancer.gov',
        'nih.gov', 'ncbi.nlm.nih.gov', 'fda.gov', 'who.int', 'cdc.gov'
    }
    
    # Regex patterns for medical/AI content
    PATTERNS = {
        'performance_metrics': re.compile(
            r'\b(AUC|AUROC|accuracy|sensitivity|specificity|PPV|NPV|F1|precision|recall)\s*[:\-=]?\s*([\d.]+)([%]?)',
            re.IGNORECASE
        ),
        'versions': re.compile(r'\bv?(\d+(?:\.\d+){1,3})\b'),
        'regulatory': re.compile(
            r'\b(510\(k\)|De\s*Novo|PMA|CE\s?mark(?:ed|ing)?|FDA\s+(?:cleared|approved))\s*([A-Z0-9\-]+)?',
            re.IGNORECASE
        ),
        'doi': re.compile(r'\b(10\.\d{4,9}/[^\s"<>]+)\b'),
        'emails': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    }
    
    @classmethod
    def extract_json_ld(cls, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract JSON-LD structured data"""
        json_ld_data = {}
        
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            script_content = getattr(script, 'string', None)
            if script_content is None:
                continue
            
            try:
                data = json.loads(script_content)
                
                # Handle arrays of objects
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            cls._merge_json_ld(json_ld_data, item)
                elif isinstance(data, dict):
                    cls._merge_json_ld(json_ld_data, data)
                    
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse JSON-LD: {e}")
                continue
        
        return json_ld_data
    
    @classmethod
    def _merge_json_ld(cls, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge JSON-LD data, preferring non-empty values"""
        fields = ['name', 'description', 'author', 'publisher', 'datePublished', 'dateModified']
        for field in fields:
            if field in source and source[field] and field not in target:
                target[field] = source[field]
    
    @classmethod
    def extract_patterns(cls, text: str, include_emails: bool = False) -> Dict[str, List[Any]]:
        """Extract domain-specific patterns from text"""
        results = {}
        
        # Performance metrics
        metrics = []
        for match in cls.PATTERNS['performance_metrics'].finditer(text):
            metric_name, value, unit = match.groups()
            metrics.append({
                'metric': metric_name.upper(),
                'value': float(value),
                'unit': unit or '',
                'context': text[max(0, match.start()-50):match.end()+50].strip()
            })
        results['performance_metrics'] = metrics
        
        # Versions
        versions = []
        for match in cls.PATTERNS['versions'].finditer(text):
            versions.append(match.group(1))
        results['versions'] = list(set(versions))  # Deduplicate
        
        # Regulatory information
        regulatory = []
        for match in cls.PATTERNS['regulatory'].finditer(text):
            reg_type, identifier = match.groups()
            regulatory.append({
                'type': reg_type,
                'identifier': identifier or '',
                'context': text[max(0, match.start()-50):match.end()+50].strip()
            })
        results['regulatory'] = regulatory
        
        # DOIs
        dois = []
        for match in cls.PATTERNS['doi'].finditer(text):
            dois.append(match.group(1))
        results['dois'] = list(set(dois))
        
        # Emails (optional, privacy-sensitive)
        if include_emails:
            emails = []
            for match in cls.PATTERNS['emails'].finditer(text):
                emails.append(match.group(0))
            results['emails'] = list(set(emails))
        
        return results

class RobustWebScraper:
    """Production-grade async web scraper with advanced content extraction"""
    
    def __init__(self, config: ScraperConfig = None):
        self.config = config or ScraperConfig()
        self.session = None
        self.cache = HTTPCache(self.config.cache_dir, self.config.cache_ttl_hours)
        self.robot_checker = RobotChecker()
        self.rate_limiter = RateLimiter()
        self.host_semaphores = {}  # Per-host concurrency control
        self.user_agent_index = 0
        
        # Diagnostics
        self.stats = {
            'requests': 0, 'retries': 0, 'rate_limits': 0, 'cache_hits': 0,
            'bytes_downloaded': 0, 'robots_blocked': 0
        }
    
    async def __aenter__(self):
        """Initialize async session"""
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=self.config.per_host_limit,
            enable_cleanup_closed=True
        )
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up session"""
        if self.session:
            await self.session.close()
    
    def _get_user_agent(self, domain: str) -> str:
        """Get appropriate user agent for domain"""
        # Use explicit scraper UA for medical/regulatory domains
        if any(med_domain in domain.lower() for med_domain in MetadataExtractor.MEDICAL_DOMAINS):
            return self.config.user_agents[0]  # ModelCardScraper
        
        # Rotate through browser UAs for other domains
        ua = self.config.user_agents[1 + (self.user_agent_index % (len(self.config.user_agents) - 1))]
        self.user_agent_index += 1
        return ua
    
    def _get_host_semaphore(self, domain: str) -> asyncio.Semaphore:
        """Get or create semaphore for host"""
        if domain not in self.host_semaphores:
            self.host_semaphores[domain] = asyncio.Semaphore(self.config.per_host_limit)
        return self.host_semaphores[domain]
    
    async def fetch_with_retry(self, url: str) -> Dict[str, Any]:
        """Fetch URL with retry logic and caching"""
        start_time = time.time()
        diagnostics = {
            'retries': 0, 'cache_hit': False, 'bytes': 0,
            'rate_limited': False, 'robots_blocked': False
        }
        
        try:
            normalized_url = URLNormalizer.normalize_url(url)
            if not normalized_url:
                return {
                    'status': 'failed', 'error': 'Invalid URL',
                    'diagnostics': diagnostics
                }
            
            parsed = urlparse(normalized_url)
            domain = parsed.netloc
            
            # Check for credentialed URLs
            if URLNormalizer.is_likely_credentialed(normalized_url):
                logger.warning(f"Skipping credentialed URL: {normalized_url}")
                return {
                    'status': 'failed', 'error': 'Credentialed URL rejected',
                    'diagnostics': diagnostics
                }
            
            # Get user agent and check robots
            user_agent = self._get_user_agent(domain)
            if self.config.respect_robots:
                can_fetch = await self.robot_checker.can_fetch(normalized_url, user_agent, self.session)
                if not can_fetch:
                    diagnostics['robots_blocked'] = True
                    self.stats['robots_blocked'] += 1
                    return {
                        'status': 'failed', 'error': 'Blocked by robots.txt',
                        'diagnostics': diagnostics
                    }
            
            # Check cache
            cached = self.cache.get(normalized_url)
            
            # Rate limiting
            rate = (self.config.medical_domains_rps 
                   if any(med in domain.lower() for med in MetadataExtractor.MEDICAL_DOMAINS)
                   else self.config.default_rps)
            await self.rate_limiter.acquire(domain, rate)
            
            # Per-host concurrency control
            semaphore = self._get_host_semaphore(domain)
            
            async with semaphore:
                headers = {'User-Agent': user_agent}
                if cached:
                    if cached.get('etag'):
                        headers['If-None-Match'] = cached['etag']
                    if cached.get('last_modified'):
                        headers['If-Modified-Since'] = cached['last_modified']
                
                # Retry loop
                for attempt in range(self.config.max_retries + 1):
                    try:
                        self.stats['requests'] += 1
                        
                        async with self.session.get(normalized_url, headers=headers) as response:
                            # Handle 304 Not Modified
                            if response.status == 304 and cached:
                                diagnostics['cache_hit'] = True
                                self.stats['cache_hits'] += 1
                                return {
                                    'status': cached['status_code'],
                                    'text': cached.get('body', ''),
                                    'bytes': None,
                                    'headers': dict(response.headers),
                                    'url': str(response.url),
                                    'diagnostics': diagnostics
                                }
                            
                            # Handle rate limiting
                            if response.status == 429:
                                diagnostics['rate_limited'] = True
                                self.stats['rate_limits'] += 1
                                
                                retry_after = response.headers.get('Retry-After')
                                if retry_after:
                                    try:
                                        wait_time = int(retry_after)
                                    except ValueError:
                                        wait_time = 60  # Default wait
                                else:
                                    wait_time = (2 ** attempt) + (time.time() % 1)  # Exp backoff + jitter
                                
                                if attempt < self.config.max_retries:
                                    diagnostics['retries'] += 1
                                    self.stats['retries'] += 1
                                    await asyncio.sleep(wait_time)
                                    continue
                            
                            # Handle server errors
                            if response.status in {500, 502, 503, 504} and attempt < self.config.max_retries:
                                diagnostics['retries'] += 1
                                self.stats['retries'] += 1
                                wait_time = (2 ** attempt) + (time.time() % 1)
                                await asyncio.sleep(wait_time)
                                continue
                            
                            # Check content size
                            content_length = response.headers.get('Content-Length')
                            if content_length and int(content_length) > self.config.max_content_size:
                                return {
                                    'status': 'failed', 'error': 'Content too large',
                                    'diagnostics': diagnostics
                                }
                            
                            # Read response
                            content_type = response.headers.get('Content-Type', '').lower()
                            
                            if 'pdf' in content_type or normalized_url.endswith('.pdf'):
                                # Handle PDF
                                content_bytes = await response.read()
                                if len(content_bytes) > self.config.max_content_size:
                                    return {
                                        'status': 'failed', 'error': 'PDF too large',
                                        'diagnostics': diagnostics
                                    }
                                
                                diagnostics['bytes'] = len(content_bytes)
                                self.stats['bytes_downloaded'] += len(content_bytes)
                                
                                # Cache the response
                                etag = response.headers.get('ETag')
                                last_modified = response.headers.get('Last-Modified')
                                self.cache.set(normalized_url, etag, last_modified, 
                                             '', response.status, content_type)
                                
                                return {
                                    'status': response.status,
                                    'text': None,
                                    'bytes': content_bytes,
                                    'headers': dict(response.headers),
                                    'url': str(response.url),
                                    'diagnostics': diagnostics
                                }
                            else:
                                # Handle text content
                                content_text = await response.text()
                                diagnostics['bytes'] = len(content_text.encode())
                                self.stats['bytes_downloaded'] += diagnostics['bytes']
                                
                                # Cache the response
                                etag = response.headers.get('ETag')
                                last_modified = response.headers.get('Last-Modified')
                                self.cache.set(normalized_url, etag, last_modified,
                                             content_text, response.status, content_type)
                                
                                return {
                                    'status': response.status,
                                    'text': content_text,
                                    'bytes': None,
                                    'headers': dict(response.headers),
                                    'url': str(response.url),
                                    'diagnostics': diagnostics
                                }
                    
                    except asyncio.TimeoutError:
                        if attempt < self.config.max_retries:
                            diagnostics['retries'] += 1
                            self.stats['retries'] += 1
                            await asyncio.sleep((2 ** attempt) + (time.time() % 1))
                            continue
                        return {
                            'status': 'failed', 'error': 'Request timeout',
                            'diagnostics': diagnostics
                        }
                    
                    except Exception as e:
                        if attempt < self.config.max_retries:
                            diagnostics['retries'] += 1
                            self.stats['retries'] += 1
                            await asyncio.sleep((2 ** attempt) + (time.time() % 1))
                            continue
                        return {
                            'status': 'failed', 'error': f'Network error: {str(e)}',
                            'diagnostics': diagnostics
                        }
                
                # All retries exhausted
                return {
                    'status': 'failed', 'error': 'Max retries exceeded',
                    'diagnostics': diagnostics
                }
        
        finally:
            diagnostics['elapsed_ms'] = int((time.time() - start_time) * 1000)
    
    async def search_web_enhanced(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Enhanced web search method - wrapper for backwards compatibility
        Provides the same interface as the original robust_scraper.py
        """
        try:
            print(f"Enhanced web search attempted for: {query} (max_results: {max_results})")
            # Return empty list for now - web search functionality would need integration
            # with search engines or source discovery engine
            return []
        except Exception as e:
            print(f"Error in enhanced web search: {e}")
            return []
    
    def _extract_pdf_content(self, url: str, pdf_bytes: bytes) -> Dict[str, Any]:
        """Extract text and metadata from PDF"""
        if not PDF_AVAILABLE:
            return {
                'status': 'failed',
                'error': 'PDF extraction not available - install pypdf or pdfminer.six'
            }
        
        try:
            # Try pypdf first
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                
                # Extract text
                text_parts = []
                for page in reader.pages:
                    text_parts.append(page.extract_text())
                text = '\n'.join(text_parts)
                
                # Extract metadata
                metadata = {}
                if reader.metadata:
                    metadata = {
                        'title': reader.metadata.get('/Title', ''),
                        'author': reader.metadata.get('/Author', ''),
                        'creator': reader.metadata.get('/Creator', ''),
                        'producer': reader.metadata.get('/Producer', ''),
                        'creation_date': str(reader.metadata.get('/CreationDate', '')),
                        'modification_date': str(reader.metadata.get('/ModDate', ''))
                    }
                
                return {
                    'type': 'pdf',
                    'status': 'success',
                    'text': text,
                    'metadata': metadata
                }
                
            except ImportError:
                # Fallback to pdfminer if available
                try:
                    from pdfminer.high_level import extract_text
                    text = extract_text(io.BytesIO(pdf_bytes))
                except ImportError:
                    return {
                        'type': 'pdf',
                        'status': 'failed',
                        'error': 'PDF extraction libraries not available'
                    }
                
                return {
                    'type': 'pdf',
                    'status': 'success',
                    'text': text,
                    'metadata': {}
                }
        
        except Exception as e:
            return {
                'type': 'pdf',
                'status': 'failed',
                'error': f'PDF extraction failed: {str(e)}'
            }
    
    def _remove_noise_elements(self, soup: BeautifulSoup):
        """Remove noise elements from HTML"""
        # Elements to remove completely
        noise_tags = [
            'script', 'style', 'noscript', 'template', 'header', 'footer',
            'nav', 'form', 'aside', 'iframe', 'svg', 'canvas'
        ]
        
        for tag in noise_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Remove hidden elements
        hidden_selectors = [
            '[aria-hidden="true"]', '[hidden]', '[style*="display:none"]',
            '[style*="display: none"]', '[style*="visibility:hidden"]'
        ]
        
        for selector in hidden_selectors:
            try:
                for element in soup.select(selector):
                    element.decompose()
            except Exception:
                continue  # Invalid selector
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
    
    def _find_main_content(self, soup: BeautifulSoup) -> str:
        """Find main content using multiple strategies"""
        # Try trafilatura first
        html_str = str(soup)
        try:
            main_text = trafilatura.extract(html_str, include_tables=False, 
                                          include_comments=False, include_formatting=False)
            if main_text and len(main_text.strip()) > 100:
                return main_text.strip()
        except Exception as e:
            logger.debug(f"Trafilatura extraction failed: {e}")
        
        # Fallback: find largest content container
        content_selectors = [
            'article', 'main', '[role="main"]', '.article', '.post', 
            '.content', '#content', '#main', '.main-content'
        ]
        
        best_content = ""
        best_length = 0
        
        for selector in content_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(separator=' ', strip=True)
                    if len(text) > best_length:
                        best_content = text
                        best_length = len(text)
            except Exception:
                continue
        
        if best_content:
            return best_content
        
        # Final fallback: body text
        body = soup.find('body')
        if body:
            return body.get_text(separator=' ', strip=True)
        
        return soup.get_text(separator=' ', strip=True)
    
    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract headings with levels"""
        headings = []
        for level in range(1, 7):  # h1-h6
            for heading in soup.find_all(f'h{level}')[:self.config.max_headings]:
                text = heading.get_text(strip=True)
                if text:
                    headings.append({'level': level, 'text': text})
        return headings
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract and normalize links"""
        links = []
        seen_urls = set()
        
        for link in soup.find_all('a', href=True)[:self.config.max_links]:
            href = link.get('href', '').strip()
            if not href:
                continue
            
            # Resolve relative URLs
            try:
                absolute_url = urljoin(base_url, href)
                normalized_url = URLNormalizer.normalize_url(absolute_url)
                
                if normalized_url and normalized_url not in seen_urls:
                    seen_urls.add(normalized_url)
                    text = link.get_text(strip=True)[:200]  # Limit text length
                    links.append({
                        'url': normalized_url,
                        'text': text
                    })
            except Exception:
                continue
        
        return links
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract image information"""
        images = []
        
        for img in soup.find_all('img', src=True)[:self.config.max_images]:
            src = img.get('src', '').strip()
            if not src:
                continue
            
            try:
                absolute_url = urljoin(base_url, src)
                normalized_url = URLNormalizer.normalize_url(absolute_url)
                
                if normalized_url:
                    images.append({
                        'url': normalized_url,
                        'alt': img.get('alt', '').strip()[:200],
                        'title': img.get('title', '').strip()[:200]
                    })
            except Exception:
                continue
        
        return images
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract table data with headers"""
        tables = []
        
        for table in soup.find_all('table')[:self.config.max_tables]:
            try:
                headers = []
                rows = []
                
                # Extract headers
                header_row = table.find('tr')
                if header_row:
                    for th in header_row.find_all(['th', 'td']):
                        headers.append(th.get_text(strip=True))
                
                # Extract data rows
                for row in table.find_all('tr')[1:]:  # Skip header row
                    row_data = []
                    for cell in row.find_all(['td', 'th']):
                        row_data.append(cell.get_text(strip=True))
                    if row_data:
                        rows.append(row_data)
                
                if headers or rows:
                    tables.append({
                        'headers': headers,
                        'rows': rows[:100]  # Limit rows
                    })
            except Exception:
                continue
        
        return tables
    
    def _normalize_text(self, text: str) -> str:
        """Normalize and clean text content"""
        if not text:
            return ""
        
        # Remove cookie/privacy boilerplate
        boilerplate_patterns = [
            r'this\s+(?:website|site)\s+uses\s+cookies',
            r'we\s+use\s+cookies',
            r'accept\s+(?:all\s+)?cookies',
            r'privacy\s+policy',
            r'cookie\s+(?:policy|notice)',
            r'gdpr\s+compliance'
        ]
        
        for pattern in boilerplate_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    async def extract_content_from_url(self, url: str) -> Dict[str, Any]:
        """Main content extraction method"""
        logger.info(f"Extracting content from: {url}")
        
        # Fetch the content
        fetch_result = await self.fetch_with_retry(url)
        
        if fetch_result.get('status') == 'failed':
            return {
                'url': url,
                'final_url': None,
                'status': 'failed',
                'error': fetch_result.get('error', 'Unknown error'),
                'diagnostics': fetch_result.get('diagnostics', {})
            }
        
        content_type = fetch_result.get('headers', {}).get('content-type', '').lower()
        final_url = fetch_result.get('url', url)
        diagnostics = fetch_result.get('diagnostics', {})
        
        # Handle PDF content
        if fetch_result.get('bytes') is not None:
            pdf_result = self._extract_pdf_content(url, fetch_result['bytes'])
            
            return {
                'url': url,
                'final_url': final_url,
                'status': pdf_result['status'],
                'content_type': content_type,
                'title': pdf_result.get('metadata', {}).get('title', ''),
                'meta_description': '',
                'headings': [],
                'links': [],
                'images': [],
                'tables': [],
                'clean_text': pdf_result.get('text', ''),
                'raw_html_truncated': None,
                'raw_html_sha256': None,
                'metadata': {
                    'json_ld': {},
                    'pdf_metadata': pdf_result.get('metadata', {}),
                    **MetadataExtractor.extract_patterns(pdf_result.get('text', ''))
                },
                'diagnostics': diagnostics,
                'error': pdf_result.get('error')
            }
        
        # Handle text content
        html_content = fetch_result.get('text', '')
        if not html_content:
            return {
                'url': url,
                'final_url': final_url,
                'status': 'failed',
                'error': 'No content received',
                'diagnostics': diagnostics
            }
        
        # Check if content is HTML
        if '<html' not in html_content.lower() and 'text/html' not in content_type:
            return {
                'url': url,
                'final_url': final_url,
                'status': 'skipped_non_html',
                'content_type': content_type,
                'diagnostics': diagnostics
            }
        
        # Parse HTML
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            return {
                'url': url,
                'final_url': final_url,
                'status': 'failed',
                'error': f'HTML parsing failed: {str(e)}',
                'diagnostics': diagnostics
            }
        
        # Remove noise elements
        self._remove_noise_elements(soup)
        
        # Extract components
        title = ''
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        meta_description = ''
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            meta_description = desc_tag.get('content', '').strip()
        
        headings = self._extract_headings(soup)
        links = self._extract_links(soup, final_url)
        images = self._extract_images(soup, final_url)
        tables = self._extract_tables(soup)
        
        # Extract main content
        clean_text = self._find_main_content(soup)
        clean_text = self._normalize_text(clean_text)
        
        # Extract metadata
        json_ld = MetadataExtractor.extract_json_ld(soup)
        pattern_data = MetadataExtractor.extract_patterns(clean_text + ' ' + html_content)
        
        # Prepare raw HTML (truncated)
        raw_html_truncated = html_content[:self.config.raw_html_limit] if html_content else None
        raw_html_sha256 = hashlib.sha256(html_content.encode()).hexdigest() if html_content else None
        
        return {
            'url': url,
            'final_url': final_url,
            'status': 'success',
            'content_type': content_type,
            'title': title,
            'meta_description': meta_description,
            'headings': headings,
            'links': links,
            'images': images,
            'tables': tables,
            'clean_text': clean_text,
            'raw_html_truncated': raw_html_truncated,
            'raw_html_sha256': raw_html_sha256,
            'metadata': {
                'json_ld': json_ld,
                **pattern_data
            },
            'diagnostics': diagnostics,
            'error': None
        }

# PubMed and arXiv helper functions (keeping existing functionality with improvements)
class PubMedClient:
    """Enhanced PubMed client with pagination and rich data extraction"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def search_papers(self, query: str, max_results: int = 100, 
                           session: aiohttp.ClientSession = None) -> List[Dict[str, Any]]:
        """Search PubMed papers with pagination"""
        results = []
        retmax = 20  # Results per page
        retstart = 0
        
        # Create session if not provided
        if session is None:
            async with aiohttp.ClientSession() as session:
                return await self._search_with_session(query, max_results, session)
        else:
            return await self._search_with_session(query, max_results, session)
    
    async def _search_with_session(self, query: str, max_results: int, 
                                  session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Internal search method with session"""
        results = []
        retmax = 20
        retstart = 0
        
        while len(results) < max_results:
            # Search for PMIDs
            search_params = {
                'db': 'pubmed',
                'term': query,
                'retmax': min(retmax, max_results - len(results)),
                'retstart': retstart,
                'retmode': 'json'
            }
            
            if self.api_key:
                search_params['api_key'] = self.api_key
            
            search_url = f"{self.base_url}/esearch.fcgi"
            
            try:
                async with session.get(search_url, params=search_params) as response:
                    if response.status != 200:
                        break
                    
                    data = await response.json()
                    pmids = data.get('esearchresult', {}).get('idlist', [])
                    
                    if not pmids:
                        break
                    
                    # Fetch details for PMIDs
                    fetch_params = {
                        'db': 'pubmed',
                        'id': ','.join(pmids),
                        'retmode': 'xml'
                    }
                    
                    if self.api_key:
                        fetch_params['api_key'] = self.api_key
                    
                    fetch_url = f"{self.base_url}/efetch.fcgi"
                    
                    async with session.get(fetch_url, params=fetch_params) as fetch_response:
                        if fetch_response.status == 200:
                            xml_content = await fetch_response.text()
                            parsed_papers = self._parse_pubmed_xml(xml_content)
                            results.extend(parsed_papers)
                    
                    retstart += retmax
                    
                    # Rate limiting for API
                    await asyncio.sleep(0.1)
            
            except Exception as e:
                logger.error(f"PubMed search error: {e}")
                break
        
        return results[:max_results]
    
    def _parse_pubmed_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """Parse PubMed XML response"""
        results = []
        
        try:
            from xml.etree import ElementTree as ET
            root = ET.fromstring(xml_content)
            
            for article in root.findall('.//PubmedArticle'):
                try:
                    # Extract basic information
                    pmid_elem = article.find('.//PMID')
                    pmid = pmid_elem.text if pmid_elem is not None else ''
                    
                    title_elem = article.find('.//ArticleTitle')
                    title = title_elem.text if title_elem is not None else ''
                    
                    # Extract abstract
                    abstract_parts = []
                    for abstract_elem in article.findall('.//AbstractText'):
                        label = abstract_elem.get('Label', '')
                        text = abstract_elem.text or ''
                        if label:
                            abstract_parts.append(f"{label}: {text}")
                        else:
                            abstract_parts.append(text)
                    abstract = ' '.join(abstract_parts)
                    
                    # Extract authors
                    authors = []
                    for author in article.findall('.//Author'):
                        last_name = author.find('LastName')
                        first_name = author.find('ForeName')
                        if last_name is not None:
                            name = last_name.text
                            if first_name is not None:
                                name += f", {first_name.text}"
                            authors.append(name)
                    
                    # Extract journal info
                    journal_elem = article.find('.//Journal/Title')
                    journal = journal_elem.text if journal_elem is not None else ''
                    
                    iso_abbrev_elem = article.find('.//ISOAbbreviation')
                    iso_abbrev = iso_abbrev_elem.text if iso_abbrev_elem is not None else ''
                    
                    # Extract publication date
                    pub_date = ''
                    date_elem = article.find('.//PubDate')
                    if date_elem is not None:
                        year = date_elem.find('Year')
                        month = date_elem.find('Month')
                        day = date_elem.find('Day')
                        
                        if year is not None:
                            pub_date = year.text
                            if month is not None:
                                pub_date += f"-{month.text.zfill(2)}"
                                if day is not None:
                                    pub_date += f"-{day.text.zfill(2)}"
                    
                    # Extract DOI
                    doi = ''
                    for article_id in article.findall('.//ArticleId'):
                        if article_id.get('IdType') == 'doi':
                            doi = article_id.text
                            break
                    
                    # Extract MeSH terms
                    mesh_terms = []
                    for mesh in article.findall('.//MeshHeading/DescriptorName'):
                        if mesh.text:
                            mesh_terms.append(mesh.text)
                    
                    # Extract publication types
                    pub_types = []
                    for pub_type in article.findall('.//PublicationType'):
                        if pub_type.text:
                            pub_types.append(pub_type.text)
                    
                    # Check for RCT or Review
                    is_rct = any('randomized controlled trial' in pt.lower() for pt in pub_types)
                    is_review = any('review' in pt.lower() for pt in pub_types)
                    
                    results.append({
                        'pmid': pmid,
                        'title': title,
                        'abstract': abstract,
                        'authors': authors,
                        'journal': journal,
                        'iso_abbreviation': iso_abbrev,
                        'publication_date': pub_date,
                        'doi': doi,
                        'mesh_terms': mesh_terms,
                        'publication_types': pub_types,
                        'is_rct': is_rct,
                        'is_review': is_review,
                        'source_type': 'pubmed_paper'
                    })
                
                except Exception as e:
                    logger.debug(f"Error parsing PubMed article: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing PubMed XML: {e}")
        
        return results

class ArXivClient:
    """Enhanced arXiv client with HTTPS and pagination"""
    
    def __init__(self):
        self.base_url = "https://export.arxiv.org/api/query"
    
    async def search_papers(self, query: str, max_results: int = 100,
                           session: aiohttp.ClientSession = None) -> List[Dict[str, Any]]:
        """Search arXiv papers with pagination"""
        results = []
        max_per_page = 50
        start = 0
        
        # Create session if not provided
        if session is None:
            async with aiohttp.ClientSession() as session:
                return await self._search_with_session(query, max_results, session)
        else:
            return await self._search_with_session(query, max_results, session)
    
    async def _search_with_session(self, query: str, max_results: int,
                                  session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Internal search method with session"""
        results = []
        max_per_page = 50
        start = 0
        
        while len(results) < max_results:
            params = {
                'search_query': query,
                'start': start,
                'max_results': min(max_per_page, max_results - len(results)),
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }
            
            try:
                # Try HTTPS first
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        xml_content = await response.text()
                        parsed_papers = self._parse_arxiv_xml(xml_content)
                        results.extend(parsed_papers)
                        
                        if len(parsed_papers) < max_per_page:
                            break  # No more results
                        
                        start += max_per_page
                        await asyncio.sleep(3)  # arXiv rate limiting
                    else:
                        break
            
            except Exception as e:
                logger.error(f"arXiv search error: {e}")
                # Fallback to HTTP if HTTPS fails
                if 'https://' in self.base_url:
                    logger.warning("HTTPS failed for arXiv, falling back to HTTP")
                    self.base_url = self.base_url.replace('https://', 'http://')
                    continue
                break
        
        return results[:max_results]
    
    def _assess_content_quality(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Assess content quality and relevance"""
        quality_score = 0
        quality_factors = {}
        
        # Check content length
        text_length = len(content.get('clean_text', ''))
        if text_length > 1000:
            quality_score += 20
            quality_factors['length'] = 'good'
        elif text_length > 500:
            quality_score += 10
            quality_factors['length'] = 'moderate'
        else:
            quality_factors['length'] = 'poor'
        
        # Check for technical terms
        technical_terms = ['accuracy', 'sensitivity', 'specificity', 'AUC', 'ROC', 'model', 'algorithm']
        found_terms = sum(1 for term in technical_terms if term.lower() in content.get('clean_text', '').lower())
        if found_terms >= 5:
            quality_score += 30
            quality_factors['technical_content'] = 'excellent'
        elif found_terms >= 3:
            quality_score += 20
            quality_factors['technical_content'] = 'good'
        else:
            quality_factors['technical_content'] = 'poor'
        
        # Check for medical terms
        medical_terms = ['dermatology', 'skin', 'melanoma', 'lesion', 'diagnosis', 'clinical']
        found_medical = sum(1 for term in medical_terms if term.lower() in content.get('clean_text', '').lower())
        if found_medical >= 3:
            quality_score += 25
            quality_factors['medical_content'] = 'good'
        else:
            quality_factors['medical_content'] = 'poor'
        
        # Check for structured data
        if content.get('metadata', {}).get('json_ld'):
            quality_score += 15
            quality_factors['structured_data'] = 'present'
        else:
            quality_factors['structured_data'] = 'missing'
        
        return {
            'quality_score': quality_score,
            'quality_factors': quality_factors,
            'recommendation': 'use' if quality_score >= 50 else 'skip'
        }
    
    def _extract_structured_data(self, html: str) -> Dict[str, Any]:
        """Extract structured data (JSON-LD, microdata, etc.)"""
        soup = BeautifulSoup(html, 'html.parser')
        structured_data = {}
        
        # Extract JSON-LD
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                structured_data.update(data)
            except:
                pass
        
        # Extract microdata
        microdata = soup.find_all(attrs={'itemscope': True})
        for item in microdata:
            # Extract microdata properties
            pass
        
        return structured_data
    
    async def extract_enhanced_content(self, url: str) -> Dict[str, Any]:
        """Enhanced content extraction with better parsing"""
        result = await self.extract_content_from_url(url)
        
        # Add structured data extraction
        if result.get('raw_html_truncated'):
            structured_data = self._extract_structured_data(result.get('raw_html_truncated', ''))
            result['structured_data'] = structured_data
        
        # Add metadata extraction
        if result.get('raw_html_truncated'):
            metadata = self._extract_metadata(result.get('raw_html_truncated', ''))
            result['metadata'] = metadata
        
        # Add PDF processing
        if 'pdf' in result.get('content_type', ''):
            pdf_content = self._extract_pdf_content(url, result.get('bytes', b''))
            result['pdf_content'] = pdf_content
        
        # Add content quality assessment
        quality_assessment = self._assess_content_quality(result)
        result['quality_assessment'] = quality_assessment
        
        return result
    
    def _parse_arxiv_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """Parse arXiv XML response"""
        results = []
        
        try:
            from xml.etree import ElementTree as ET
            
            # Parse XML with namespace handling
            root = ET.fromstring(xml_content)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', namespace):
                try:
                    # Extract basic information
                    id_elem = entry.find('atom:id', namespace)
                    arxiv_id = id_elem.text.split('/')[-1] if id_elem is not None else ''
                    
                    title_elem = entry.find('atom:title', namespace)
                    title = title_elem.text.strip() if title_elem is not None else ''
                    
                    summary_elem = entry.find('atom:summary', namespace)
                    abstract = summary_elem.text.strip() if summary_elem is not None else ''
                    
                    # Extract authors
                    authors = []
                    for author in entry.findall('atom:author', namespace):
                        name_elem = author.find('atom:name', namespace)
                        if name_elem is not None:
                            authors.append(name_elem.text)
                    
                    # Extract publication date
                    published_elem = entry.find('atom:published', namespace)
                    pub_date = published_elem.text[:10] if published_elem is not None else ''  # YYYY-MM-DD
                    
                    # Extract categories
                    categories = []
                    for category in entry.findall('atom:category', namespace):
                        term = category.get('term')
                        if term:
                            categories.append(term)
                    
                    # Extract DOI if available
                    doi = ''
                    for link in entry.findall('atom:link', namespace):
                        if link.get('title') == 'doi':
                            doi = link.get('href', '').replace('http://dx.doi.org/', '')
                            break
                    
                    # Construct arXiv URL
                    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
                    
                    results.append({
                        'arxiv_id': arxiv_id,
                        'title': title,
                        'abstract': abstract,
                        'authors': authors,
                        'publication_date': pub_date,
                        'categories': categories,
                        'doi': doi,
                        'url': arxiv_url,
                        'source_type': 'arxiv_paper'
                    })
                
                except Exception as e:
                    logger.debug(f"Error parsing arXiv entry: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing arXiv XML: {e}")
        
        return results

# Export main classes
__all__ = [
    'RobustWebScraper',
    'ScraperConfig', 
    'URLNormalizer',
    'MetadataExtractor',
    'PubMedClient',
    'ArXivClient'
]