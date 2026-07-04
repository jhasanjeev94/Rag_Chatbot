"""
CLI Orchestrator for the Document Ingestion Pipeline.

Runs the complete end-to-end pipeline:
1. Scrape: Fetch HTML from configured URLs
2. Parse: Extract structured text and metadata
3. Chunk: Section-aware text splitting
4. Embed: Generate BGE embeddings and store in ChromaDB
"""

import logging
import sys
from pathlib import Path

# Add project root to sys.path so we can run this directly
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.scraper import scrape_all
from src.ingestion.parser import parse_all
from src.ingestion.chunker import chunk_all
from src.ingestion.embedder import embed_and_store
from src.config import CHROMA_COLLECTION_NAME

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("ingest_pipeline")
    
    logger.info("Starting Document Ingestion Pipeline...")
    
    try:
        logger.info("=== Phase 2.1: Scraping ===")
        html_map = scrape_all()
        if not html_map:
            logger.error("No HTML content scraped. Aborting pipeline.")
            sys.exit(1)
            
        logger.info("=== Phase 2.2: Parsing ===")
        documents = parse_all(html_map)
        if not documents:
            logger.error("No documents parsed. Aborting pipeline.")
            sys.exit(1)
            
        logger.info("=== Phase 2.3: Chunking ===")
        all_chunks = chunk_all(documents)
        if not all_chunks:
            logger.error("No chunks generated. Aborting pipeline.")
            sys.exit(1)
            
        logger.info(f"=== Phase 2.4: Embedding & Storing ({len(all_chunks)} chunks) ===")
        embed_and_store(all_chunks, CHROMA_COLLECTION_NAME)
        
        logger.info("Document Ingestion Pipeline completed successfully! 🎉")
        
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
