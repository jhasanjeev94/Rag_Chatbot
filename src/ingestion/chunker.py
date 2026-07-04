"""
Chunker module for the Document Ingestion Pipeline.

Implements section-aware chunking for parsed mutual fund documents:
1. Splits text on '## ' section headers (preserving semantic boundaries)
2. Merges small adjacent sections to avoid micro-fragments
3. Sub-splits large sections (mainly FAQs) using RecursiveCharacterTextSplitter
4. Prepends scheme context to every chunk for retrieval clarity
5. Attaches rich metadata to each chunk
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)

# Minimum size for a standalone chunk; smaller sections get merged with neighbors
_MIN_CHUNK_SIZE = 100


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------

def _split_into_sections(text: str) -> List[Tuple[str, str]]:
    """Split structured text on '## ' headers.

    Args:
        text: The full structured text from the parser.

    Returns:
        List of (section_title, section_body) tuples.
        The first element captures everything before the first '## ' header
        (the scheme overview / preamble).
    """
    sections: List[Tuple[str, str]] = []

    # Split on '## ' at the start of a line
    parts = re.split(r"\n## ", text)

    for i, part in enumerate(parts):
        if i == 0:
            # Preamble — everything before the first ## header
            # Contains the '# Scheme Name' heading and overview lines
            title = "Overview"
            body = part.strip()
        else:
            # First line is the section title, rest is body
            lines = part.split("\n", 1)
            title = lines[0].strip()
            body = lines[1].strip() if len(lines) > 1 else ""

        if body:
            sections.append((title, body))

    return sections


# ---------------------------------------------------------------------------
# Section merging (combine small adjacent sections)
# ---------------------------------------------------------------------------

def _merge_small_sections(
    sections: List[Tuple[str, str]],
    min_size: int = _MIN_CHUNK_SIZE,
    max_merged_size: int = 500,
) -> List[Tuple[str, str]]:
    """Merge small adjacent sections into combined chunks.

    Sections smaller than `min_size` are merged with their next neighbor.
    Merging stops when the combined size would exceed `max_merged_size`.

    Args:
        sections: List of (title, body) tuples.
        min_size: Sections below this size are candidates for merging.
        max_merged_size: Maximum size of a merged chunk.

    Returns:
        List of (combined_title, combined_body) tuples.
    """
    if not sections:
        return []

    merged: List[Tuple[str, str]] = []
    buffer_titles: List[str] = []
    buffer_bodies: List[str] = []
    buffer_size = 0

    for title, body in sections:
        body_len = len(body)

        # If adding this section would exceed the max, flush the buffer first
        if buffer_size > 0 and buffer_size + body_len > max_merged_size:
            merged.append((
                " | ".join(buffer_titles),
                "\n\n".join(buffer_bodies),
            ))
            buffer_titles = []
            buffer_bodies = []
            buffer_size = 0

        buffer_titles.append(title)
        buffer_bodies.append(body)
        buffer_size += body_len

        # If the buffer is large enough to stand alone, flush it
        if buffer_size >= min_size:
            merged.append((
                " | ".join(buffer_titles),
                "\n\n".join(buffer_bodies),
            ))
            buffer_titles = []
            buffer_bodies = []
            buffer_size = 0

    # Flush any remaining buffer
    if buffer_bodies:
        if merged:
            # Append to the last merged chunk if the remainder is tiny
            last_title, last_body = merged[-1]
            merged[-1] = (
                last_title + " | " + " | ".join(buffer_titles),
                last_body + "\n\n" + "\n\n".join(buffer_bodies),
            )
        else:
            merged.append((
                " | ".join(buffer_titles),
                "\n\n".join(buffer_bodies),
            ))

    return merged


# ---------------------------------------------------------------------------
# Sub-splitting large sections (FAQs, long descriptions)
# ---------------------------------------------------------------------------

def _subsplit_large_section(
    title: str,
    body: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Tuple[str, str]]:
    """Sub-split a section that exceeds chunk_size.

    Uses FAQ-aware separators so Q/A pairs stay together whenever possible.

    Args:
        title: Section title (e.g. "Frequently Asked Questions").
        body: Section body text.
        chunk_size: Maximum chunk size in characters.
        chunk_overlap: Overlap between sub-chunks.

    Returns:
        List of (sub_title, sub_body) tuples.
    """
    # FAQ-aware separators: try to split on Q/A boundaries first
    separators = ["\nQ: ", "\n\n", "\n", ". ", " "]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        keep_separator=True,
        strip_whitespace=True,
    )

    sub_chunks = splitter.split_text(body)

    results: List[Tuple[str, str]] = []
    for i, chunk_text in enumerate(sub_chunks, 1):
        sub_title = f"{title} (Part {i}/{len(sub_chunks)})" if len(sub_chunks) > 1 else title
        results.append((sub_title, chunk_text.strip()))

    return results


# ---------------------------------------------------------------------------
# Context header builder
# ---------------------------------------------------------------------------

def _build_context_header(document: Dict[str, Any]) -> str:
    """Build a context header to prepend to each chunk.

    This ensures the retriever always knows which fund a chunk belongs to,
    even when the chunk body doesn't mention the scheme name.

    Example:
        "Scheme: HDFC Large Cap Fund Direct Growth | Equity / Large Cap | Very High Risk"
    """
    parts = [f"Scheme: {document.get('scheme_name', 'Unknown')}"]

    asset_type = document.get("asset_type", "")
    category = document.get("category", "")
    if asset_type and category:
        parts.append(f"{asset_type} / {category}")
    elif asset_type:
        parts.append(asset_type)

    risk = document.get("risk_level", "")
    if risk:
        parts.append(risk)

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_document(
    document: Dict[str, Any],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Section-aware chunking for a parsed mutual fund document.

    Strategy:
        1. Split text on '## ' section headers
        2. Merge small sections (< 100 chars) with neighbors
        3. Sub-split large sections (> chunk_size) with FAQ-aware splitter
        4. Prepend scheme context header to every chunk
        5. Attach metadata: scheme_name, source_url, chunk_index, section, scrape_date

    Args:
        document: Parsed document dict from parser.parse_html().
        chunk_size: Max chunk size in chars. Defaults to config.CHUNK_SIZE.
        chunk_overlap: Overlap between sub-chunks. Defaults to config.CHUNK_OVERLAP.

    Returns:
        List of chunk dicts, each containing:
        - content (str): The chunk text with context header
        - metadata (dict): scheme_name, source_url, chunk_index, section,
                           scrape_date, category, asset_type, risk_level
    """
    if chunk_size is None:
        chunk_size = CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = CHUNK_OVERLAP

    text = document.get("text", "")
    if not text:
        logger.warning("Empty text in document for %s", document.get("scheme_name", "?"))
        return []

    context_header = _build_context_header(document)

    # Step 1: Split into sections
    sections = _split_into_sections(text)
    logger.debug(
        "Split %s into %d sections",
        document.get("scheme_name", "?"), len(sections),
    )

    # Step 2: Merge small adjacent sections
    merged = _merge_small_sections(sections, min_size=_MIN_CHUNK_SIZE, max_merged_size=chunk_size)
    logger.debug(
        "Merged into %d section groups", len(merged),
    )

    # Step 3: Sub-split any sections that still exceed chunk_size
    final_sections: List[Tuple[str, str]] = []
    for title, body in merged:
        if len(body) > chunk_size:
            sub_chunks = _subsplit_large_section(title, body, chunk_size, chunk_overlap)
            final_sections.extend(sub_chunks)
        else:
            final_sections.append((title, body))

    # Step 4 & 5: Build final chunks with context header and metadata
    chunks: List[Dict[str, Any]] = []
    for idx, (section_title, section_body) in enumerate(final_sections):
        # Prepend context header
        chunk_content = f"{context_header}\n\n{section_body}"

        chunk = {
            "content": chunk_content,
            "metadata": {
                "scheme_name": document.get("scheme_name", ""),
                "source_url": document.get("source_url", ""),
                "chunk_index": idx,
                "section": section_title,
                "scrape_date": document.get("scrape_date", ""),
                "category": document.get("category", ""),
                "asset_type": document.get("asset_type", ""),
                "risk_level": document.get("risk_level", ""),
            },
        }
        chunks.append(chunk)

    logger.info(
        "Chunked %s into %d chunks (avg %d chars)",
        document.get("scheme_name", "?"),
        len(chunks),
        sum(len(c["content"]) for c in chunks) // max(len(chunks), 1),
    )

    return chunks


def chunk_all(documents: List[Dict[str, Any]],
              chunk_size: Optional[int] = None,
              chunk_overlap: Optional[int] = None) -> List[Dict[str, Any]]:
    """Chunk all parsed documents.

    Args:
        documents: List of parsed document dicts from parser.parse_all().
        chunk_size: Max chunk size in chars. Defaults to config.CHUNK_SIZE.
        chunk_overlap: Overlap between sub-chunks. Defaults to config.CHUNK_OVERLAP.

    Returns:
        Flat list of all chunks from all documents.
    """
    all_chunks: List[Dict[str, Any]] = []

    for doc in documents:
        chunks = chunk_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        all_chunks.extend(chunks)

    logger.info(
        "Total: %d chunks from %d documents (avg %.0f chars/chunk)",
        len(all_chunks),
        len(documents),
        sum(len(c["content"]) for c in all_chunks) / max(len(all_chunks), 1),
    )

    return all_chunks


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from src.ingestion.scraper import scrape_all
    from src.ingestion.parser import parse_all

    logger.info("Step 1: Scraping...")
    html_map = scrape_all()

    logger.info("Step 2: Parsing...")
    documents = parse_all(html_map)

    logger.info("Step 3: Chunking...")
    all_chunks = chunk_all(documents)

    print("\n" + "=" * 70)
    print(f"CHUNKING SUMMARY — {len(all_chunks)} total chunks")
    print("=" * 70)

    current_scheme = ""
    for chunk in all_chunks:
        scheme = chunk["metadata"]["scheme_name"]
        if scheme != current_scheme:
            current_scheme = scheme
            print(f"\n{'─' * 70}")
            print(f"  {scheme}")
            print(f"{'─' * 70}")

        section = chunk["metadata"]["section"]
        content_len = len(chunk["content"])
        preview = chunk["content"].split("\n\n", 1)[-1][:80].replace("\n", " ")
        print(f"  [{chunk['metadata']['chunk_index']:2d}] ({content_len:4d} chars) [{section}]")
        print(f"       {preview}...")
