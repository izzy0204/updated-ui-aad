"""
CONSISTENCY ENHANCEMENT SYSTEM

PURPOSE:
Provides additional mechanisms to ensure consistent scraping results
across multiple runs with identical inputs. Addresses various sources
of inconsistency in the web scraping and content extraction process.

HOW IT WORKS:
1. Deterministic source ordering with multiple sort criteria
2. Result stabilization through hash-based content validation
3. Timeout and retry standardization across all methods
4. Content fingerprinting for detecting duplicate information
5. Consistent user-agent and header management

KEY FEATURES:
- Multi-level deterministic sorting
- Content deduplication and fingerprinting
- Standardized network timeouts and retries
- Consistent error handling patterns
- Result validation and integrity checking
"""

import hashlib
import json
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urlparse
import re

class ConsistencyEnhancements:
    """
    Additional utilities for ensuring consistent scraping results
    """
    
    @staticmethod
    def create_content_fingerprint(content: str) -> str:
        """
        Create a consistent fingerprint for content to detect duplicates
        """
        # Normalize content for fingerprinting
        normalized = re.sub(r'\s+', ' ', content.lower().strip())
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        
        # Create hash
        return hashlib.md5(normalized.encode()).hexdigest()[:12]
    
    @staticmethod
    def deduplicate_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate sources based on URL and content similarity
        """
        seen_urls: Set[str] = set()
        seen_fingerprints: Set[str] = set()
        deduplicated = []
        
        for source in sources:
            url = source.get('url', '')
            content = source.get('description', '') + source.get('title', '')
            
            # Normalize URL for comparison
            normalized_url = ConsistencyEnhancements.normalize_url(url)
            
            # Create content fingerprint
            fingerprint = ConsistencyEnhancements.create_content_fingerprint(content)
            
            # Skip if we've seen this URL or very similar content
            if normalized_url in seen_urls or fingerprint in seen_fingerprints:
                continue
            
            seen_urls.add(normalized_url)
            seen_fingerprints.add(fingerprint)
            deduplicated.append(source)
        
        return deduplicated
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Normalize URL for consistent comparison
        """
        if not url:
            return ""
        
        try:
            parsed = urlparse(url.lower().strip())
            
            # Remove common tracking parameters
            query_parts = []
            if parsed.query:
                params = parsed.query.split('&')
                for param in params:
                    # Skip common tracking parameters
                    if not any(tracker in param.lower() for tracker in [
                        'utm_', 'fbclid', 'gclid', '_ga', '_gac', 'mc_', 'ref=', 'source='
                    ]):
                        query_parts.append(param)
            
            # Rebuild normalized URL
            normalized_query = '&'.join(sorted(query_parts)) if query_parts else ""
            normalized_path = parsed.path.rstrip('/') or '/'
            
            normalized = f"{parsed.scheme}://{parsed.netloc}{normalized_path}"
            if normalized_query:
                normalized += f"?{normalized_query}"
            
            return normalized
            
        except Exception:
            return url.lower().strip()
    
    @staticmethod
    def deterministic_sort_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply deterministic multi-level sorting to ensure consistent ordering
        """
        return sorted(sources, key=lambda x: (
            -(x.get('priority_score', 0)),      # Highest priority first
            x.get('source_type', 'zzz'),        # Source type alphabetically  
            -(len(x.get('description', ''))),    # Longer descriptions first
            x.get('url', ''),                    # URL alphabetically
            x.get('title', '')                   # Title alphabetically
        ))
    
    @staticmethod
    def standardize_source_metadata(source: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize source metadata for consistency
        """
        standardized = source.copy()
        
        # Ensure all required fields exist
        standardized.setdefault('title', '')
        standardized.setdefault('url', '')
        standardized.setdefault('description', '')
        standardized.setdefault('priority_score', 5.0)
        standardized.setdefault('source_type', 'unknown')
        
        # Normalize text fields
        if standardized['title']:
            standardized['title'] = re.sub(r'\s+', ' ', standardized['title'].strip())
        
        if standardized['description']:
            standardized['description'] = re.sub(r'\s+', ' ', standardized['description'].strip())
        
        # Ensure priority score is numeric
        try:
            standardized['priority_score'] = float(standardized['priority_score'])
        except (ValueError, TypeError):
            standardized['priority_score'] = 5.0
        
        return standardized
    
    @staticmethod
    def validate_result_consistency(results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and ensure result structure consistency
        """
        validated = {
            'model_name': results.get('model_name', ''),
            'developer_name': results.get('developer_name', ''),
            'discovery_timestamp': results.get('discovery_timestamp', ''),
            'huggingface': [],
            'github': [],
            'pubmed': [],
            'arxiv': [],
            'websites': [],
            'prioritized_sources': []
        }
        
        # Process each source category
        for category in ['huggingface', 'github', 'pubmed', 'arxiv', 'websites']:
            sources = results.get(category, [])
            if isinstance(sources, list):
                # Standardize each source and deduplicate
                standardized = [
                    ConsistencyEnhancements.standardize_source_metadata(source) 
                    for source in sources if isinstance(source, dict)
                ]
                deduplicated = ConsistencyEnhancements.deduplicate_sources(standardized)
                validated[category] = ConsistencyEnhancements.deterministic_sort_sources(deduplicated)
        
        # Handle prioritized sources
        prioritized = results.get('prioritized_sources', [])
        if isinstance(prioritized, list):
            standardized = [
                ConsistencyEnhancements.standardize_source_metadata(source) 
                for source in prioritized if isinstance(source, dict)
            ]
            deduplicated = ConsistencyEnhancements.deduplicate_sources(standardized)
            validated['prioritized_sources'] = ConsistencyEnhancements.deterministic_sort_sources(deduplicated)
        
        return validated
    
    @staticmethod
    def create_result_summary(results: Dict[str, Any]) -> str:
        """
        Create a summary of results for logging and debugging
        """
        total_sources = 0
        category_counts = {}
        
        for category in ['huggingface', 'github', 'pubmed', 'arxiv', 'websites']:
            count = len(results.get(category, []))
            category_counts[category] = count
            total_sources += count
        
        prioritized_count = len(results.get('prioritized_sources', []))
        
        summary_lines = [
            f"Model: {results.get('model_name', 'Unknown')}",
            f"Developer: {results.get('developer_name', 'Not specified')}",
            f"Total sources: {total_sources}",
            f"Prioritized: {prioritized_count}",
            "Categories: " + ", ".join([f"{k}={v}" for k, v in category_counts.items() if v > 0])
        ]
        
        return " | ".join(summary_lines)

class DeterministicConfig:
    """
    Configuration for deterministic behavior across all scraping operations
    """
    
    # Standard timeouts for all operations
    TIMEOUTS = {
        'connect': 8.0,
        'read': 15.0,
        'total': 25.0
    }
    
    # Standard retry configuration
    RETRY_CONFIG = {
        'max_attempts': 3,
        'base_delay': 0.5,
        'max_delay': 5.0,
        'backoff_factor': 2.0
    }
    
    # Standard headers for all requests
    STANDARD_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    # Source processing limits for consistency
    LIMITS = {
        'max_sources_per_category': 15,
        'max_total_sources': 50,
        'max_prioritized_sources': 20,
        'max_content_length': 10000,  # chars
        'min_content_length': 20      # chars
    }