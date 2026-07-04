"""
Embedder module for the Document Ingestion Pipeline.

Embeds chunked documents using BAAI/bge-small-en-v1.5 and stores them
in a ChromaDB persistent vector store.
"""

import logging
import re
from typing import List, Dict, Any
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

def _generate_slug(text: str) -> str:
    """Generate a clean slug from a string (e.g., scheme name)."""
    if not text:
        return "unknown"
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')

def embed_and_store(chunks: List[Dict[str, Any]], collection_name: str) -> None:
    """Embed chunks using BGE and upsert to ChromaDB.
    
    Strategy:
    - Initialize SentenceTransformer with the configured embedding model (BGE)
    - Create/get ChromaDB persistent collection with cosine similarity
    - Generate deterministic chunk IDs: {scheme_slug}_{chunk_index}
    - Upsert all chunks in a single batch
    - Store: embedding, document text, and full metadata per chunk
    
    Args:
        chunks: List of chunk dicts from chunker.py
        collection_name: Name of the ChromaDB collection to use
    """
    if not chunks:
        logger.warning("No chunks provided to embed_and_store.")
        return

    logger.info(f"Initializing embedding model: {EMBEDDING_MODEL}")
    # Initialize SentenceTransformer
    # Note: BGE models do not need a prefix for document embeddings.
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Prepare ChromaDB
    logger.info(f"Connecting to ChromaDB at: {CHROMA_PERSIST_DIR}")
    # Ensure directory exists
    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    
    # Create or get collection
    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    
    # Prepare data for upsert
    ids = []
    documents = []
    metadatas = []
    
    logger.info(f"Embedding {len(chunks)} chunks...")
    
    # Extract texts for batch embedding
    texts_to_embed = [chunk["content"] for chunk in chunks]
    
    # Generate embeddings (batch generation)
    embeddings = model.encode(texts_to_embed, show_progress_bar=False)
    
    # Ensure embeddings are list of floats for chromadb
    embeddings_list = [emb.tolist() for emb in embeddings]
    
    for idx, chunk in enumerate(chunks):
        metadata = chunk.get("metadata", {})
        # Remove None values from metadata as ChromaDB doesn't accept them
        clean_metadata = {k: v for k, v in metadata.items() if v is not None}
        
        scheme_name = clean_metadata.get("scheme_name", f"doc_{idx}")
        chunk_index = clean_metadata.get("chunk_index", idx)
        
        scheme_slug = _generate_slug(scheme_name)
        chunk_id = f"{scheme_slug}_{chunk_index}"
        
        ids.append(chunk_id)
        documents.append(chunk["content"])
        metadatas.append(clean_metadata)
        
    logger.info(f"Upserting {len(ids)} chunks to collection '{collection_name}'...")
    
    # Upsert to ChromaDB
    collection.upsert(
        ids=ids,
        embeddings=embeddings_list,
        documents=documents,
        metadatas=metadatas
    )
    
    logger.info(f"Successfully upserted chunks to ChromaDB. Total chunks in collection: {collection.count()}")


if __name__ == "__main__":
    # Test script running chunker + embedder together
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    try:
        from src.ingestion.scraper import scrape_all
        from src.ingestion.parser import parse_all
        from src.ingestion.chunker import chunk_all
        from src.config import CHROMA_COLLECTION_NAME
        
        logger.info("Step 1: Scraping...")
        html_map = scrape_all()
        
        logger.info("Step 2: Parsing...")
        documents = parse_all(html_map)
        
        logger.info("Step 3: Chunking...")
        all_chunks = chunk_all(documents)
        
        logger.info(f"Step 4: Embedding and Storing ({len(all_chunks)} chunks)...")
        embed_and_store(all_chunks, CHROMA_COLLECTION_NAME)
    except ImportError as e:
        logger.warning(f"Could not run full pipeline test: {e}")
