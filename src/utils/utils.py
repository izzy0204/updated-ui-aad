"""
UTILITY FUNCTIONS - COMMON HELPER FUNCTIONS

PURPOSE:
Provides shared utility functions used across multiple modules in the medical AI
model card generator. Includes text processing, validation, content quality 
assessment, and medical domain detection capabilities.

HOW IT WORKS:
- Text cleaning and normalization functions
- URL extraction and validation
- Medical domain detection and categorization
- Content quality assessment and filtering
- Model name and data validation utilities

KEY FUNCTIONS:
- clean_text(): Removes artifacts and normalizes text content
- extract_urls_from_text(): Finds and validates URLs in content
- is_medical_domain(): Identifies medical/healthcare domains
- assess_content_quality(): Evaluates content relevance and quality
- validate_model_name(): Ensures model names meet requirements

USAGE:
from utils import clean_text, is_medical_domain
cleaned = clean_text(raw_content)
is_medical = is_medical_domain(url)
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime


def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize line breaks
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove common artifacts from web scraping
    text = re.sub(r'(Skip to main content|Subscribe|Login|Sign up|Cookie policy)', '', text, flags=re.IGNORECASE)
    
    # Clean up special characters but keep basic punctuation
    text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]\'\"]+', ' ', text)
    
    return text.strip()


def extract_urls_from_text(text: str) -> List[str]:
    """Extract URLs from text content"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:!?]'
    urls = re.findall(url_pattern, text)
    
    # Filter out common false positives
    filtered_urls = []
    for url in urls:
        if not any(exclude in url.lower() for exclude in [
            'javascript:', 'mailto:', 'tel:', '#', 'data:',
            'facebook.com', 'twitter.com', 'linkedin.com'
        ]):
            filtered_urls.append(url)
    
    return list(set(filtered_urls))  # Remove duplicates


def is_valid_model_name(name: str) -> bool:
    """Validate if a string is a reasonable model name"""
    if not name or len(name) < 2:
        return False
    
    # Check for common invalid patterns
    invalid_patterns = [
        r'^[0-9]+$',  # Only numbers
        r'^[^a-zA-Z]*$',  # No letters
        r'test|example|sample|demo|placeholder',  # Test names
    ]
    
    for pattern in invalid_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            return False
    
    return True


def extract_version_from_text(text: str) -> Optional[str]:
    """Extract version information from text"""
    version_patterns = [
        r'version[:\s]+([v]?[\d\.]+[\w\-]*)',
        r'v(\d+\.[\d\.]+[\w\-]*)',
        r'release[:\s]+([v]?[\d\.]+[\w\-]*)',
        r'(\d+\.[\d\.]+[\w\-]*)\s*release',
    ]
    
    for pattern in version_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            version = match.group(1)
            # Clean up version string
            version = re.sub(r'^v', '', version, flags=re.IGNORECASE)
            return version
    
    return None


def extract_dates_from_text(text: str) -> List[str]:
    """Extract dates from text in various formats"""
    date_patterns = [
        r'\b(\d{4}[-/]\d{2}[-/]\d{2})\b',  # YYYY-MM-DD or YYYY/MM/DD
        r'\b(\d{2}[-/]\d{2}[-/]\d{4})\b',  # MM-DD-YYYY or MM/DD/YYYY
        r'\b([A-Za-z]+\s+\d{1,2},?\s+\d{4})\b',  # Month DD, YYYY
        r'\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b',  # DD Month YYYY
        r'\b(\d{4})\b',  # Just year
    ]
    
    dates = []
    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        dates.extend(matches)
    
    return list(set(dates))


def normalize_developer_name(name: str) -> str:
    """Normalize developer/organization names for consistency"""
    if not name:
        return ""
    
    # Remove common suffixes/prefixes
    name = re.sub(r'\b(Inc\.?|Corp\.?|LLC|Ltd\.?|Co\.?|Company)\b', '', name, flags=re.IGNORECASE)
    
    # Clean up whitespace
    name = re.sub(r'\s+', ' ', name.strip())
    
    # Capitalize properly
    if name.islower() or name.isupper():
        name = name.title()
    
    return name


def extract_metrics_keywords(text: str) -> Dict[str, List[str]]:
    """Extract performance metrics and their values from text"""
    metrics = {
        'accuracy': [],
        'precision': [],
        'recall': [],
        'sensitivity': [],
        'specificity': [],
        'auc': [],
        'f1_score': []
    }
    
    # Enhanced patterns to match various metric formats
    metric_patterns = [
        # Standard format: accuracy: 0.95, precision = 90%, etc.
        r'(accuracy|precision|recall|sensitivity|specificity|auc|f1[-_\s]?score)[:\s=]*([0-9]+\.?[0-9]*%?)',
        # Performance format: "achieved 95% accuracy", "accuracy of 0.95"
        r'(?:achieved|reached|obtained|accuracy|precision|recall|sensitivity|specificity|auc|f1)\s+(?:of\s+)?([0-9]+\.?[0-9]*%?)\s*(accuracy|precision|recall|sensitivity|specificity|auc|f1)',
        # Metrics in tables or structured text
        r'(accuracy|precision|recall|sensitivity|specificity|auc|f1)\s*[|\t]\s*([0-9]+\.?[0-9]*%?)',
        # Clinical trial format: "sensitivity: 95.2%"
        r'(sensitivity|specificity|accuracy|precision|recall|auc|f1[-_\s]?score)\s*:\s*([0-9]+\.?[0-9]*%?)'
    ]
    
    text_lower = text.lower()
    
    for pattern in metric_patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        
        for match in matches:
            if len(match) == 2:
                metric_name, value = match
                # Normalize metric name
                normalized_name = metric_name.lower().replace('-', '_').replace(' ', '_')
                if 'f1' in normalized_name:
                    normalized_name = 'f1_score'
                
                if normalized_name in metrics and value:
                    # Clean and validate the value
                    clean_value = re.sub(r'[^\d.]', '', value)
                    if clean_value and float(clean_value) <= 100:  # Reasonable metric range
                        metrics[normalized_name].append(value)
    
    return {k: list(set(v)) for k, v in metrics.items() if v}  # Remove duplicates


def format_timestamp() -> str:
    """Get formatted timestamp for documentation"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text to specified length with suffix"""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def is_medical_domain(url: str) -> bool:
    """Check if URL is from a medical/healthcare domain"""
    medical_domains = [
        'nih.gov', 'cdc.gov', 'fda.gov', 'who.int',
        'mayoclinic.org', 'clevelandclinic.org', 'mskcc.org',
        'hopkinsmedicine.org', 'aad.org', 'jaad.org',
        'pubmed.ncbi.nlm.nih.gov', 'jamanetwork.com',
        'nejm.org', 'thelancet.com', 'bmj.com'
    ]
    
    url_lower = url.lower()
    return any(domain in url_lower for domain in medical_domains)


def extract_dermatology_keywords(text: str) -> List[str]:
    """Extract dermatology-specific keywords from text"""
    derm_keywords = [
        'dermatology', 'skin', 'melanoma', 'lesion', 'dermoscopy',
        'mole', 'cancer', 'carcinoma', 'pigmented', 'nevus',
        'basal cell', 'squamous cell', 'actinic keratosis',
        'psoriasis', 'eczema', 'dermatitis', 'rash',
        'seborrheic keratosis', 'hemangioma', 'solar lentigo',
        'wound', 'scar', 'biopsy', 'diagnosis', 'detection'
    ]
    
    found_keywords = []
    text_lower = text.lower()
    
    for keyword in derm_keywords:
        if keyword in text_lower:
            found_keywords.append(keyword)
    
    return list(set(found_keywords))


def extract_references_from_text(text: str) -> List[Dict[str, str]]:
    """Extract academic references and citations from text"""
    references = []
    
    # DOI pattern
    doi_pattern = r'doi:\s*([10]\.[0-9]+\/[^\s]+)'
    doi_matches = re.findall(doi_pattern, text, re.IGNORECASE)
    
    for doi in doi_matches:
        references.append({
            'type': 'doi',
            'identifier': doi,
            'full_text': f"DOI: {doi}"
        })
    
    # PubMed ID pattern
    pmid_pattern = r'pmid:\s*([0-9]+)'
    pmid_matches = re.findall(pmid_pattern, text, re.IGNORECASE)
    
    for pmid in pmid_matches:
        references.append({
            'type': 'pmid',
            'identifier': pmid,
            'full_text': f"PMID: {pmid}"
        })
    
    # URL pattern for references
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:!?]'
    urls = re.findall(url_pattern, text)
    
    for url in urls:
        if any(domain in url.lower() for domain in ['pubmed', 'arxiv', 'doi.org', 'researchgate', 'scholar.google']):
            references.append({
                'type': 'url',
                'identifier': url,
                'full_text': url
            })
    
    # Citation patterns (Author et al., Year)
    citation_pattern = r'([A-Z][a-zA-Z]+(?:\s+et\s+al\.?)?(?:\s*,\s*[12][0-9]{3}))'
    citation_matches = re.findall(citation_pattern, text)
    
    for citation in citation_matches:
        references.append({
            'type': 'citation',
            'identifier': citation,
            'full_text': citation
        })
    
    return references


def calculate_content_quality_score(content: str) -> float:
    """Calculate a quality score for extracted content (0-1)"""
    if not content:
        return 0.0
    
    score = 0.0
    
    # Length factor (longer content generally better, up to a point)
    length_score = min(len(content) / 1000, 1.0) * 0.3
    score += length_score
    
    # Medical terminology factor
    medical_terms = ['clinical', 'study', 'validation', 'accuracy', 'performance',
                    'evaluation', 'dataset', 'training', 'testing', 'results']
    medical_count = sum(1 for term in medical_terms if term in content.lower())
    medical_score = min(medical_count / len(medical_terms), 1.0) * 0.4
    score += medical_score
    
    # Structure factor (presence of structured information)
    structure_indicators = [':' in content, '=' in content, '%' in content,
                          'http' in content, len(content.split('\n')) > 3]
    structure_score = sum(structure_indicators) / len(structure_indicators) * 0.3
    score += structure_score
    
    return min(score, 1.0)