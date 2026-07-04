"""
Groq API Client wrapper for Phase 4 LLM Generation.
Handles API communication, timeouts, and rate limits (backoff).
"""
import logging
import time
from typing import Optional

from groq import Groq
from groq import APIError, RateLimitError

from src.config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

logger = logging.getLogger(__name__)

class GroqLLMClient:
    """Wrapper around Groq API for LLM generation.
    
    Groq Limits (llama-3.3-70b-versatile):
    - 30 requests per minute
    - 1000 requests per day
    - 12000 tokens per minute
    - 100,000 tokens per day
    """
    
    def __init__(self):
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY is missing. LLM generation will fail.")
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = LLM_MODEL
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS
        self.max_retries = 3

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompt to Groq API and return generated text, handling rate limits."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        retry_delay = 2.0  # start with 2 seconds backoff
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                return response.choices[0].message.content.strip()
                
            except RateLimitError as e:
                logger.warning(f"Groq RateLimitError on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries:
                    # If we exhausted retries, it might be the daily limit or prolonged exhaustion
                    logger.error("Exhausted all retries for Groq API rate limits.")
                    return "I'm currently experiencing high traffic and reached my daily request limit. Please try again later."
                
                # Exponential backoff
                logger.info(f"Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
                retry_delay *= 2
                
            except APIError as e:
                logger.error(f"Groq APIError: {e}")
                return "I encountered an error communicating with my language model. Please try again."
            except Exception as e:
                logger.exception(f"Unexpected error in LLM generation: {e}")
                return "An unexpected error occurred while generating the response."
                
        return "I'm currently unable to answer due to API limits. Please try again later."

# Global instance for reuse
_client: Optional[GroqLLMClient] = None

def get_llm_client() -> GroqLLMClient:
    global _client
    if _client is None:
        _client = GroqLLMClient()
    return _client
