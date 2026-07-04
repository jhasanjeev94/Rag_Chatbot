"""
PII Detector for Phase 5 Guardrails.
Uses regex to detect common PII patterns in user queries.
"""
import re
from typing import Dict, List, Any

# Regex patterns for common PII
PII_PATTERNS = {
    'PAN': r'\b[A-Z]{5}[0-9]{4}[A-Z]\b',
    'Aadhaar': r'\b\d{4}\s?\d{4}\s?\d{4}\b',
    'Phone': r'\b(?:\+91|91)?\s?[6-9]\d{9}\b',
    'Email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'Account Number': r'\b\d{11,18}\b' # Indian bank accounts are typically 11-18 digits
}

def detect_pii(query: str) -> Dict[str, Any]:
    """Scan query for PII patterns."""
    found_pii_types = []
    
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, query, flags=re.IGNORECASE):
            found_pii_types.append(pii_type)
            
    return {
        'has_pii': len(found_pii_types) > 0,
        'pii_types': found_pii_types
    }
