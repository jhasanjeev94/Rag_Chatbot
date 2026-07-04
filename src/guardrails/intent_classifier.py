"""
Intent Classifier for Phase 5 Guardrails.
Classifies if query is advisory, performance, or factual based on keywords.
"""
import re
from typing import Dict, Any

ADVISORY_KEYWORDS = [
    r'\bshould i\b', r'\brecommend\b', r'\bbetter\b', r'\bsuggest\b',
    r'\bwhich fund\b', r'\bworth investing\b', r'\bgood fund\b', r'\badvice\b'
]

PERFORMANCE_KEYWORDS = [
    r'\breturns\b', r'\bperformance\b', r'\bcagr\b', r'\bnav prediction\b',
    r'\bhow much profit\b', r'\bbetter performing\b'
]

OUT_OF_SCOPE_KEYWORDS = [
    r'\baxis\b', r'\bsbi\b', r'\bicici\b', r'\bnippon\b', r'\bkotak\b' # competitor funds
]

def classify_intent(query: str) -> Dict[str, Any]:
    """Classify if query is advisory, performance, or factual."""
    query_lower = query.lower()
    
    # Check Performance
    for kw in PERFORMANCE_KEYWORDS:
        if re.search(kw, query_lower):
            return {
                'intent': 'performance',
                'confidence': 1.0,
                'refusal_response': "I cannot compare fund performance or calculate returns. You can view the official factsheets at groww.in for performance details."
            }
            
    # Check Advisory
    for kw in ADVISORY_KEYWORDS:
        if re.search(kw, query_lower):
            return {
                'intent': 'advisory',
                'confidence': 1.0,
                'refusal_response': "I'm a facts-only assistant and cannot provide investment advice or recommendations. For investment guidance, please visit [AMFI Investor Education](https://www.amfiindia.com/investor-corner/knowledge-center.html)."
            }
            
    # Check Out-of-scope (Basic check for other fund houses)
    for kw in OUT_OF_SCOPE_KEYWORDS:
        if re.search(kw, query_lower):
            return {
                'intent': 'out_of_scope',
                'confidence': 1.0,
                'refusal_response': "I currently cover only HDFC Mutual Fund schemes (Large Cap, Mid Cap, Small Cap, Gold ETF FoF, Silver ETF FoF). Please ask about one of these schemes."
            }
            
    return {
        'intent': 'factual',
        'confidence': 1.0,
        'refusal_response': None
    }
