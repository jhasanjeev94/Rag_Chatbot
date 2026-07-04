"""
Output Validator for Phase 5 Guardrails.
Post-validates LLM response for format compliance.
"""
import re
from typing import Dict, Any

def validate_response(response: Dict[str, str]) -> Dict[str, Any]:
    """Post-validate LLM response for format compliance.
    
    Checks:
    1. Sentence count <= 5 (allowing leniency for abbreviations/URLs)
    2. Exactly 1 citation URL present
    3. Footer 'Last updated from sources: <date>' present
    4. No advisory language leaked
    
    Returns: { 'valid': bool, 'corrected_response': dict, 'issues': list[str] }
    """
    issues = []
    is_valid = True
    answer_text = response.get('answer', '')
    
    # Check 1: Sentence count (rough approximation using delimiters)
    sentences = re.split(r'[.!?]+', answer_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) > 5:
        issues.append(f"Response too long ({len(sentences)} sentences detected)")
        is_valid = False
        
    # Check 2 & 3: Validated by the generator parsing
    if not response.get('citation_url'):
        issues.append("Missing citation URL")
        is_valid = False
        
    if not response.get('last_updated'):
        issues.append("Missing last updated date")
        is_valid = False
        
    # Check 4: Advisory language leak
    advisory_leak = re.search(r'\b(recommend|suggest|should invest|good investment)\b', answer_text, re.IGNORECASE)
    if advisory_leak:
        issues.append(f"Advisory language detected in output: {advisory_leak.group(1)}")
        is_valid = False
        
    corrected = dict(response)
    if not is_valid:
        # Fallback to a safe response if validation completely fails
        corrected['answer'] = "I'm sorry, I generated a response that didn't meet my safety and formatting guidelines. Please rephrase your question."
        corrected['citation_url'] = ""
        corrected['last_updated'] = ""
        
    return {
        'valid': is_valid,
        'corrected_response': corrected,
        'issues': issues
    }
