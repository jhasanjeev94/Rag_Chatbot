"""
Configuration module for Mutual Fund FAQ Assistant.

Loads environment variables from .env file and exposes them as typed constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / ".env"

if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Try .env.example as fallback for defaults (minus secrets)
    _env_example = _project_root / ".env.example"
    if _env_example.exists():
        load_dotenv(_env_example)

# --- LLM Provider (Groq) ---
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# --- Embedding Model ---
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# --- Vector Store ---
CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/vectorstore")
CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "hdfc_mf_corpus")

# --- Retrieval ---
RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "5"))
RETRIEVAL_SCORE_THRESHOLD: float = float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", "0.3"))

# --- LLM ---
LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "200"))

# --- Ingestion ---
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))

# --- Corpus URLs ---
CORPUS_URLS: list[str] = [
    "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth",
    "https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth",
]
