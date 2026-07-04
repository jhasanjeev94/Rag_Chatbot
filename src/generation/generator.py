"""
Generator module for Phase 4 LLM Generation.
Coordinates retrieval context, prompts, and the Groq LLM client to produce answers.
"""
import logging
import re
from typing import List, Dict, Any

from src.generation.llm_client import get_llm_client
from src.generation.prompt_templates import SYSTEM_PROMPT, build_user_prompt
from src.retrieval.retriever import assemble_context

logger = logging.getLogger(__name__)

def generate_answer(query: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, str]:
    """Full generation pipeline: context -> prompt -> LLM -> response.
    
    Steps:
    1. Assemble context from chunks
    2. Build prompt using template
    3. Call Groq LLM
    4. Parse response into structured output
    
    Returns: {
        'answer': str,
        'citation_url': str,
        'last_updated': str
    }
    """
    logger.info("Assembling context for generation...")
    context_str = assemble_context(context_chunks)
    
    logger.info("Building prompt...")
    user_prompt = build_user_prompt(context_str, query)
    
    logger.info("Calling Groq LLM...")
    client = get_llm_client()
    raw_response = client.generate(SYSTEM_PROMPT, user_prompt)
    
    # Parse output
    url_match = re.search(r'(https?://[^\s).]+)', raw_response)
    citation_url = url_match.group(1) if url_match else ""
    
    date_match = re.search(r'Last updated from sources:\s*(.*)', raw_response, flags=re.IGNORECASE)
    last_updated = date_match.group(1).strip() if date_match else ""
    
    # In case the rate limit triggered our fallback error message
    if raw_response.startswith("I'm currently"):
        citation_url = ""
        last_updated = ""
        
    return {
        'answer': raw_response,
        'citation_url': citation_url,
        'last_updated': last_updated
    }
