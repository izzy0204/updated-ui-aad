"""
UTILITY FUNCTIONS - COMMON HELPER FUNCTIONS

PURPOSE:
Provides shared utility functions used across multiple modules in the medical AI
model card generator. Includes text processing, validation, content quality 
assessment, and medical domain detection capabilities.

HOW IT WORKS:
- Text cleaning and normalization functions
- Medical domain detection and categorization
- Performance metrics extraction
- Academic reference extraction

KEY FUNCTIONS:
- clean_text(): Removes artifacts and normalizes text content
- is_medical_domain(): Identifies medical/healthcare domains
- extract_metrics_keywords(): Extracts performance metrics from text
- extract_references_from_text(): Extracts academic references and citations

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

