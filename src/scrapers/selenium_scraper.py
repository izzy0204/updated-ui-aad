"""
Selenium-based Web Scraper for JavaScript-Rendered Content

This module provides Selenium-based scraping capabilities for pages that require
JavaScript execution. It works in conjunction with Beautiful Soup for static content
and provides enhanced extraction for dynamic web pages.

Features:
- Headless Chrome/Firefox browser automation
- Smart detection of JavaScript-rendered content
- Fallback to static scraping when possible
- Enhanced content extraction with Beautiful Soup
- Support for waiting for dynamic content to load
- Screenshot capture for debugging
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
from pathlib import Path

from bs4 import BeautifulSoup, Comment
import trafilatura

logger = logging.getLogger(__name__)

# Try to import Selenium components
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        WebDriverException,
        NoSuchElementException
    )
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not available. Install with: pip install selenium webdriver-manager")


class SeleniumScraper:
    """
    Selenium-based scraper for JavaScript-rendered content.
    Uses Beautiful Soup for parsing the rendered HTML.
    """
    
    def __init__(
        self,
        browser: str = "chrome",
        headless: bool = True,
        wait_timeout: int = 10,
        page_load_timeout: int = 30,
        implicit_wait: int = 5
    ):
        """
        Initialize Selenium scraper.
        
        Args:
            browser: Browser to use ('chrome' or 'firefox')
            headless: Run browser in headless mode
            wait_timeout: Timeout for explicit waits (seconds)
            page_load_timeout: Maximum time to wait for page load (seconds)
            implicit_wait: Implicit wait time for elements (seconds)
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium is not available. Install with: pip install selenium webdriver-manager"
            )
        
        self.browser = browser.lower()
        self.headless = headless
        self.wait_timeout = wait_timeout
        self.page_load_timeout = page_load_timeout
        self.implicit_wait = implicit_wait
        self.driver = None
        
    def _create_driver(self) -> webdriver.Remote:
        """Create and configure a Selenium WebDriver instance."""
        if self.browser == "chrome":
            options = ChromeOptions()
            if self.headless:
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            except Exception as e:
                logger.error(f"Failed to create Chrome driver: {e}")
                raise
        
        elif self.browser == "firefox":
            options = FirefoxOptions()
            if self.headless:
                options.add_argument("--headless")
            options.set_preference("general.useragent.override", 
                                 "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            try:
                service = Service(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=options)
            except Exception as e:
                logger.error(f"Failed to create Firefox driver: {e}")
                raise
        else:
            raise ValueError(f"Unsupported browser: {self.browser}")
        
        driver.set_page_load_timeout(self.page_load_timeout)
        driver.implicitly_wait(self.implicit_wait)
        return driver
    
    def __enter__(self):
        """Context manager entry."""
        self.driver = self._create_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
        return False
    
    def _wait_for_content(
        self,
        min_content_length: int = 500,
        max_wait: int = 10
    ) -> bool:
        """
        Wait for page content to load (check for minimum text length).
        
        Args:
            min_content_length: Minimum expected content length
            max_wait: Maximum time to wait (seconds)
        
        Returns:
            True if content loaded, False otherwise
        """
        try:
            wait = WebDriverWait(self.driver, max_wait)
            
            # Wait for body to be present
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Wait for content to be substantial
            def content_loaded(driver):
                body = driver.find_element(By.TAG_NAME, "body")
                text = body.text.strip()
                return len(text) >= min_content_length
            
            wait.until(content_loaded)
            return True
        except TimeoutException:
            logger.warning(f"Content did not load within {max_wait} seconds")
            return False
        except Exception as e:
            logger.warning(f"Error waiting for content: {e}")
            return False
    
    def _detect_js_indicators(self, html: str) -> bool:
        """
        Detect if page likely requires JavaScript.
        
        Args:
            html: Raw HTML content
        
        Returns:
            True if JavaScript is likely required
        """
        indicators = [
            '<noscript>',
            'Enable JavaScript',
            'JavaScript is required',
            'Please enable JavaScript',
            'react-root',
            'ng-app',
            'data-reactroot',
            '__NEXT_DATA__',
            'window.__INITIAL_STATE__',
            'application/json" id="__NEXT_DATA__',
        ]
        
        html_lower = html.lower()
        for indicator in indicators:
            if indicator.lower() in html_lower:
                return True
        
        # Check if body is mostly empty
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.find('body')
        if body:
            body_text = body.get_text(strip=True)
            if len(body_text) < 200:  # Very little content suggests JS rendering
                return True
        
        return False
    
    def scrape_url(
        self,
        url: str,
        wait_for_content: bool = True,
        scroll_to_load: bool = True,
        max_scrolls: int = 3
    ) -> Dict[str, Any]:
        """
        Scrape a URL using Selenium and parse with Beautiful Soup.
        
        Args:
            url: URL to scrape
            wait_for_content: Wait for content to load
            scroll_to_load: Scroll page to trigger lazy loading
            max_scrolls: Maximum number of scroll operations
        
        Returns:
            Dictionary with extracted content and metadata
        """
        if not self.driver:
            raise RuntimeError("Driver not initialized. Use context manager or call start()")
        
        result = {
            'url': url,
            'status': 'failed',
            'content_type': 'text/html',
            'title': '',
            'meta_description': '',
            'clean_text': '',
            'headings': [],
            'links': [],
            'images': [],
            'tables': [],
            'metadata': {},
            'diagnostics': {
                'selenium_used': True,
                'js_rendered': False,
                'wait_time': 0,
                'scroll_count': 0
            }
        }
        
        try:
            start_time = time.time()
            
            # Navigate to URL
            logger.info(f"Navigating to {url} with Selenium")
            self.driver.get(url)
            
            # Wait for content if requested
            if wait_for_content:
                wait_start = time.time()
                content_loaded = self._wait_for_content()
                result['diagnostics']['wait_time'] = time.time() - wait_start
                result['diagnostics']['js_rendered'] = content_loaded
            
            # Scroll to trigger lazy loading
            if scroll_to_load:
                scroll_count = 0
                for i in range(max_scrolls):
                    try:
                        # Scroll down
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)  # Wait for content to load
                        scroll_count += 1
                    except Exception:
                        break
                result['diagnostics']['scroll_count'] = scroll_count
            
            # Get page source
            html = self.driver.page_source
            
            # Check if JavaScript was needed
            if self._detect_js_indicators(html):
                result['diagnostics']['js_rendered'] = True
            
            # Parse with Beautiful Soup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove noise elements
            self._remove_noise_elements(soup)
            
            # Extract metadata
            title_tag = soup.find('title')
            if title_tag:
                result['title'] = title_tag.get_text(strip=True)
            
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                result['meta_description'] = meta_desc.get('content', '').strip()
            
            # Extract main content using trafilatura
            main_text = trafilatura.extract(html, url=url, include_tables=False, 
                                          include_comments=False, include_formatting=False)
            if main_text and len(main_text.strip()) > 100:
                result['clean_text'] = main_text.strip()
            else:
                # Fallback to Beautiful Soup extraction
                result['clean_text'] = self._extract_main_content(soup)
            
            # Extract structured data
            result['headings'] = self._extract_headings(soup)
            result['links'] = self._extract_links(soup, url)
            result['images'] = self._extract_images(soup, url)
            result['tables'] = self._extract_tables(soup)
            
            # Extract JSON-LD and other metadata
            result['metadata'] = self._extract_metadata(soup)
            
            result['status'] = 'success'
            result['diagnostics']['elapsed_time'] = time.time() - start_time
            
            logger.info(f"Successfully scraped {url} with Selenium ({len(result['clean_text'])} chars)")
            
        except TimeoutException as e:
            result['error'] = f"Page load timeout: {str(e)}"
            logger.error(f"Timeout scraping {url}: {e}")
        except WebDriverException as e:
            result['error'] = f"WebDriver error: {str(e)}"
            logger.error(f"WebDriver error scraping {url}: {e}")
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"
            logger.error(f"Error scraping {url}: {e}")
        
        return result
    
    def _remove_noise_elements(self, soup: BeautifulSoup):
        """Remove noise elements from HTML (same as robust_scraper_v2)."""
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
                continue
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content using multiple strategies."""
        # Try semantic HTML5 elements first
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
        
        # Fallback to body text
        body = soup.find('body')
        if body:
            return body.get_text(separator=' ', strip=True)
        
        return soup.get_text(separator=' ', strip=True)
    
    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract headings with levels."""
        headings = []
        for level in range(1, 7):  # h1-h6
            for heading in soup.find_all(f'h{level}')[:50]:
                text = heading.get_text(strip=True)
                if text:
                    headings.append({'level': level, 'text': text})
        return headings
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract and normalize links."""
        from urllib.parse import urljoin
        
        links = []
        seen_urls = set()
        
        for link in soup.find_all('a', href=True)[:200]:
            href = link.get('href', '').strip()
            if not href:
                continue
            
            try:
                absolute_url = urljoin(base_url, href)
                if absolute_url not in seen_urls:
                    seen_urls.add(absolute_url)
                    text = link.get_text(strip=True)[:200]
                    links.append({
                        'url': absolute_url,
                        'text': text
                    })
            except Exception:
                continue
        
        return links
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract image information."""
        from urllib.parse import urljoin
        
        images = []
        
        for img in soup.find_all('img', src=True)[:100]:
            src = img.get('src', '').strip()
            if not src:
                continue
            
            try:
                absolute_url = urljoin(base_url, src)
                images.append({
                    'url': absolute_url,
                    'alt': img.get('alt', '').strip()[:200],
                    'title': img.get('title', '').strip()[:200]
                })
            except Exception:
                continue
        
        return images
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract table data with headers."""
        tables = []
        
        for table in soup.find_all('table')[:20]:
            try:
                headers = []
                rows = []
                
                # Extract headers
                header_row = table.find('tr')
                if header_row:
                    for th in header_row.find_all(['th', 'td']):
                        headers.append(th.get_text(strip=True))
                
                # Extract data rows
                for row in table.find_all('tr')[1:]:
                    row_data = []
                    for cell in row.find_all(['td', 'th']):
                        row_data.append(cell.get_text(strip=True))
                    if row_data:
                        rows.append(row_data)
                
                if headers or rows:
                    tables.append({
                        'headers': headers,
                        'rows': rows[:50]  # Limit rows
                    })
            except Exception:
                continue
        
        return tables
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract metadata including JSON-LD."""
        metadata = {}
        
        # Extract JSON-LD
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        json_ld_data = {}
        
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            json_ld_data.update(item)
                elif isinstance(data, dict):
                    json_ld_data.update(data)
            except Exception:
                continue
        
        if json_ld_data:
            metadata['json_ld'] = json_ld_data
        
        # Extract Open Graph tags
        og_tags = {}
        for meta in soup.find_all('meta', property=lambda x: x and x.startswith('og:')):
            prop = meta.get('property', '').replace('og:', '')
            content = meta.get('content', '')
            if prop and content:
                og_tags[prop] = content
        
        if og_tags:
            metadata['open_graph'] = og_tags
        
        # Extract Twitter Card tags
        twitter_tags = {}
        for meta in soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')}):
            name = meta.get('name', '').replace('twitter:', '')
            content = meta.get('content', '')
            if name and content:
                twitter_tags[name] = content
        
        if twitter_tags:
            metadata['twitter_card'] = twitter_tags
        
        return metadata


def needs_selenium(html: str, url: str = "") -> bool:
    """
    Determine if a URL likely needs Selenium for proper content extraction.
    
    Args:
        html: Initial HTML content (may be incomplete)
        url: URL being scraped
    
    Returns:
        True if Selenium is recommended
    """
    if not SELENIUM_AVAILABLE:
        return False
    
    scraper = SeleniumScraper()
    return scraper._detect_js_indicators(html)


async def scrape_with_selenium(
    url: str,
    browser: str = "chrome",
    headless: bool = True,
    wait_for_content: bool = True
) -> Dict[str, Any]:
    """
    Async wrapper for Selenium scraping.
    
    Args:
        url: URL to scrape
        browser: Browser to use ('chrome' or 'firefox')
        headless: Run in headless mode
        wait_for_content: Wait for content to load
    
    Returns:
        Dictionary with extracted content
    """
    if not SELENIUM_AVAILABLE:
        return {
            'url': url,
            'status': 'failed',
            'error': 'Selenium not available'
        }
    
    def _scrape():
        with SeleniumScraper(browser=browser, headless=headless) as scraper:
            return scraper.scrape_url(url, wait_for_content=wait_for_content)
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _scrape)


__all__ = [
    'SeleniumScraper',
    'needs_selenium',
    'scrape_with_selenium',
    'SELENIUM_AVAILABLE'
]

