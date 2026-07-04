"""
Unified entry point for Phase 5 Guardrails.
"""
from typing import Dict, Any

from src.guardrails.pii_detector import detect_pii
from src.guardrails.intent_classifier import classify_intent
from src.guardrails.output_validator import validate_response

def screen_query(query: str) -> Dict[str, Any]:
    """Unified pre-generation query screening."""
    
    # 1. Check PII
    pii_result = detect_pii(query)
    if pii_result['has_pii']:
        return {
            'allowed': False,
            'reason': 'PII detected',
            'refusal_response': "I don't collect or process personal information like PAN, Aadhaar, or account numbers. Please ask a factual question about HDFC Mutual Fund schemes."
        }
        
    # 2. Check Intent
    intent_result = classify_intent(query)
    if intent_result['intent'] != 'factual':
        return {
            'allowed': False,
            'reason': f"Intent blocked: {intent_result['intent']}",
            'refusal_response': intent_result['refusal_response']
        }
        
    # Query is safe
    return {
        'allowed': True,
        'reason': None,
        'refusal_response': None
    }
