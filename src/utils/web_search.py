"""
Web Search Module for AI Model Card Generator

This module provides web search functionality using various search engines
and APIs to discover official websites, documentation, and relevant sources
for dermatology AI models.

Supported search providers:
- Google Custom Search API
- Bing Search API
- DuckDuckGo (via unofficial API)
- SerpAPI
"""

import asyncio
import aiohttp
import os
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import quote_plus, urlparse
import time

logger = logging.getLogger(__name__)

class WebSearchProvider:
    """Base class for web search providers"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'ModelCardGenerator/1.0 (+https://github.com/your-repo)'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for results - to be implemented by subclasses"""
        raise NotImplementedError

# Google Custom Search and Bing Search providers removed - no API keys available

class DuckDuckGoProvider(WebSearchProvider):
    """DuckDuckGo search provider (using HTML scraping)"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://html.duckduckgo.com/html/"
    
    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search using DuckDuckGo HTML interface"""
        results = []
        
        params = {
            'q': query,
            'kl': 'us-en'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        try:
            async with self.session.get(self.base_url, params=params, headers=headers) as response:
                if response.status == 200:
                    html_content = await response.text()
                    
                    # Parse HTML to extract search results
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Find result links
                    result_links = soup.find_all('a', class_='result__a')
                    
                    for i, link in enumerate(result_links[:max_results]):
                        title = link.get_text(strip=True)
                        url = link.get('href', '')
                        
                        # Find snippet (next sibling with class result__snippet)
                        snippet_elem = link.find_next_sibling(class_='result__snippet')
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                        
                        if title and url:
                            results.append({
                                'title': title,
                                'url': url,
                                'snippet': snippet,
                                'source': 'duckduckgo',
                                'rank': i + 1
                            })
        
        except Exception as e:
            logger.error(f"Error in DuckDuckGo search: {e}")
        
        return results[:max_results]

# SerpAPI provider removed - no API key available

class WebSearchManager:
    """Main web search manager that coordinates multiple providers"""
    
    def __init__(self):
        self.providers = []
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available search providers based on environment variables"""
        
        # Check if web search is enabled
        web_search_enabled = os.getenv('WEB_SEARCH_ENABLED', 'true').lower() == 'true'
        if not web_search_enabled:
            logger.info("Web search is disabled via WEB_SEARCH_ENABLED environment variable")
            return
        
        # Google Custom Search and Bing Search removed - no API keys available
        
        # SerpAPI removed - no API key available
        
        # DuckDuckGo (always available as fallback)
        self.providers.append(DuckDuckGoProvider())
        logger.info("DuckDuckGo provider initialized")
        
        logger.info(f"Initialized {len(self.providers)} search providers")
    
    async def search(self, query: str, max_results: int = 10, 
                    provider_preference: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search using available providers
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            provider_preference: Preferred provider name ('google', 'bing', 'duckduckgo', 'serpapi')
        
        Returns:
            List of search results
        """
        if not self.providers:
            logger.warning("No search providers available")
            return []
        
        # Use preferred provider if specified
        if provider_preference:
            preferred_provider = None
            for provider in self.providers:
                if provider_preference.lower() in provider.__class__.__name__.lower():
                    preferred_provider = provider
                    break
            
            if preferred_provider:
                async with preferred_provider as provider:
                    return await provider.search(query, max_results)
        
        # Try providers in order of preference
        all_results = []
        
        for provider in self.providers:
            try:
                async with provider as p:
                    results = await p.search(query, max_results)
                    all_results.extend(results)
                    
                    if len(all_results) >= max_results:
                        break
                        
            except Exception as e:
                logger.error(f"Error with provider {provider.__class__.__name__}: {e}")
                continue
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_results = []
        
        for result in all_results:
            url = result.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
                
                if len(unique_results) >= max_results:
                    break
        
        return unique_results[:max_results]
    
    def is_available(self) -> bool:
        """Check if any search providers are available"""
        return len(self.providers) > 0
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names"""
        return [provider.__class__.__name__ for provider in self.providers]

# Global search manager instance
_search_manager = None

def get_search_manager() -> WebSearchManager:
    """Get the global search manager instance"""
    global _search_manager
    if _search_manager is None:
        _search_manager = WebSearchManager()
    return _search_manager

async def web_search(query: str, max_results: int = 10, 
                    provider_preference: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Convenience function for web search
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
        provider_preference: Preferred provider name
    
    Returns:
        List of search results
    """
    manager = get_search_manager()
    return await manager.search(query, max_results, provider_preference)

def is_web_search_available() -> bool:
    """Check if web search is available"""
    manager = get_search_manager()
    return manager.is_available()

def get_web_search_providers() -> List[str]:
    """Get list of available search providers"""
    manager = get_search_manager()
    return manager.get_available_providers()

# Export main functions
__all__ = [
    'web_search',
    'is_web_search_available',
    'get_web_search_providers',
    'WebSearchManager',
    'DuckDuckGoProvider'
]
