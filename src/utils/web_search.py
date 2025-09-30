"""
Web Search Module for AI Model Card Generator

This module provides web search functionality using DuckDuckGo to discover 
official websites, documentation, and relevant sources for dermatology AI models.
"""

import asyncio
import aiohttp
import os
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

async def web_search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Simple web search using DuckDuckGo HTML interface
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
    
    Returns:
        List of search results
    """
    results = []
    
    params = {
        'q': query,
        'kl': 'us-en'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers=headers
        ) as session:
            async with session.get("https://html.duckduckgo.com/html/", params=params) as response:
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
        logger.error(f"Error in web search: {e}")
    
    return results[:max_results]

def is_web_search_available() -> bool:
    """Check if web search is available"""
    return True

def get_web_search_providers() -> List[str]:
    """Get list of available search providers"""
    return ['duckduckgo']

# Export main functions
__all__ = [
    'web_search',
    'is_web_search_available',
    'get_web_search_providers'
]
