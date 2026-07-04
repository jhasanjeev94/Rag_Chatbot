"""
Retriever module for Phase 3.
Embeds user queries and retrieves relevant chunks from ChromaDB.
"""
import logging
from typing import List, Dict, Any
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import (
    CHROMA_PERSIST_DIR, 
    CHROMA_COLLECTION_NAME, 
    EMBEDDING_MODEL, 
    RETRIEVAL_TOP_K, 
    RETRIEVAL_SCORE_THRESHOLD
)

logger = logging.getLogger(__name__)

# Global instances for reuse to avoid reloading the model on every query
_model = None
_collection = None

def _get_model():
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model

def _get_collection():
    global _collection
    if _collection is None:
        logger.info(f"Connecting to ChromaDB at: {CHROMA_PERSIST_DIR}")
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        _collection = client.get_collection(name=CHROMA_COLLECTION_NAME)
    return _collection

def retrieve(query: str, top_k: int = RETRIEVAL_TOP_K, score_threshold: float = RETRIEVAL_SCORE_THRESHOLD) -> List[Dict[str, Any]]:
    """Embed user query and return top-k relevant chunks."""
    model = _get_model()
    collection = _get_collection()
    
    # Prepend BGE query prefix
    prefixed_query = f"Represent this sentence for searching relevant passages: {query}"
    
    # Generate embedding
    query_embedding = model.encode(prefixed_query, show_progress_bar=False).tolist()
    
    # Query ChromaDB
    # Note: ChromaDB with cosine similarity returns distances (1 - cosine_similarity).
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )
    
    retrieved_chunks = []
    
    if not results['documents'] or not results['documents'][0]:
        return retrieved_chunks
        
    for i in range(len(results['documents'][0])):
        content = results['documents'][0][i]
        metadata = results['metadatas'][0][i]
        distance = results['distances'][0][i]
        
        # Convert distance to similarity score
        similarity_score = 1.0 - distance
        
        if similarity_score >= score_threshold:
            retrieved_chunks.append({
                'content': content,
                'metadata': metadata,
                'score': similarity_score
            })
            
    return retrieved_chunks

def assemble_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into structured context for LLM prompt."""
    if not chunks:
        return "No relevant context found."
        
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk['metadata']
        scheme_name = meta.get('scheme_name', 'Unknown Source')
        source_url = meta.get('source_url', 'Unknown URL')
        
        header = f"--- Context Chunk {i} (Source: {scheme_name} | URL: {source_url}) ---"
        content = chunk['content']
        
        context_parts.append(f"{header}\n{content}")
        
    return "\n\n".join(context_parts)
