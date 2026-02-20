"""
pdf_service.py
─────────────────────────────────────────────────────────────────────────────
Handles PDF ingestion pipeline:
  1. Extract text per-page using pypdf (preserves page numbers)
  2. Split text into overlapping chunks using LangChain's splitter
  3. Attach metadata (page number, best-effort section heading) to each chunk
  4. Hand chunks to chroma_service for embedding + storage

Page numbers are extracted by iterating pages individually so each chunk
knows which page it came from. Section headings are detected heuristically
(short all-caps or title-case lines at the start of a chunk).
"""

import io
import hashlib
import re
from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from services.chroma_service import store_chunks, leaflet_exists
from errors import ChatbotError, ErrorCode
from observability import get_logger, track_latency, metrics

log = get_logger("pdf_service")

MAX_PDF_BYTES = 20 * 1024 * 1024  # 20 MB hard limit
CHUNK_SIZE    = 1200  # larger chunks = better context for Hebrew + complex questions
CHUNK_OVERLAP = 200


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_pages(pdf_bytes: bytes) -> list[dict]:
    """
    Extract text from each page individually.
    Returns: [{"page": int (1-based), "text": str}, ...]
    Raises ChatbotError if no text could be extracted.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append({"page": i, "text": text})

    if not pages:
        raise ChatbotError(
            ErrorCode.PDF_NO_TEXT,
            detail="pypdf found no extractable text in any page.",
        )
    return pages


# ── Section heading detection ─────────────────────────────────────────────────

def _detect_section(text: str) -> str | None:
    """
    Heuristic: the first non-empty line of a chunk is treated as a section
    heading if it is:
      • Short (≤ 60 chars)
      • Either all-uppercase OR title-cased with no trailing punctuation
      • Does not end with a period (i.e. not a sentence)

    Returns the heading string or None.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None
    candidate = lines[0]
    if len(candidate) > 60:
        return None
    if candidate.endswith("."):
        return None
    if candidate.isupper() or re.match(r'^[A-Z][a-z]', candidate):
        return candidate
    return None


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_pages(pages: list[dict]) -> list[dict]:
    """
    Split document into overlapping chunks while preserving page metadata.

    Strategy: chunk the full document text but track page boundaries so
    each chunk knows which page it came from. This avoids splitting related
    content (like a definition and its explanation) across chunk boundaries
    just because they happen to be on different pages.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    # Build a map of character offset → page number
    full_text = ""
    page_boundaries = []  # list of (start_char, end_char, page_num)
    for page_info in pages:
        start = len(full_text)
        full_text += page_info["text"] + "\n\n"
        end = len(full_text)
        page_boundaries.append((start, end, page_info["page"]))

    raw_chunks = splitter.split_text(full_text)

    def get_page(chunk_text: str) -> int:
        """Find which page a chunk belongs to by matching text position."""
        pos = full_text.find(chunk_text[:80])
        if pos == -1:
            return pages[0]["page"]
        for start, end, page_num in page_boundaries:
            if start <= pos < end:
                return page_num
        return pages[-1]["page"]

    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        chunks.append({
            "chunk_index": i,
            "page":        get_page(chunk_text),
            "section":     _detect_section(chunk_text),
            "text":        chunk_text,
        })

    return chunks


# ── Public entry point ────────────────────────────────────────────────────────

async def process_pdf(pdf_bytes: bytes, filename: str) -> dict:
    """
    Full ingestion pipeline for a single PDF.
    Returns {"leaflet_id": str, "page_count": int}.
    Re-uploading the same file is a no-op (idempotent).

    Raises ChatbotError on validation or processing failures.
    """
    # ── Validate ─────────────────────────────────────────────────────────────
    if not pdf_bytes:
        raise ChatbotError(ErrorCode.PDF_EMPTY)
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ChatbotError(ErrorCode.PDF_TOO_LARGE, detail=f"Size: {len(pdf_bytes)} bytes")

    # ── Stable ID via content hash ────────────────────────────────────────────
    leaflet_id = hashlib.sha256(pdf_bytes).hexdigest()[:16]

    # Always get page count regardless of whether already indexed
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)

    if leaflet_exists(leaflet_id):
        log.info("PDF already indexed, skipping", extra={"leaflet_id": leaflet_id, "pdf_filename": filename})
        return {"leaflet_id": leaflet_id, "page_count": page_count}

    log.info("Starting PDF ingestion", extra={"leaflet_id": leaflet_id, "pdf_filename": filename})

    # ── Extract → chunk → store ───────────────────────────────────────────────
    with track_latency(log, "pdf_extract", {"leaflet_id": leaflet_id}):
        pages = _extract_pages(pdf_bytes)

    with track_latency(log, "pdf_chunk", {"leaflet_id": leaflet_id}):
        chunks = _chunk_pages(pages)

    with track_latency(log, "pdf_embed_store", {"leaflet_id": leaflet_id}):
        await store_chunks(leaflet_id, chunks)

    metrics.record_pdf_upload()
    log.info(
        "PDF ingestion complete",
        extra={
            "leaflet_id": leaflet_id,
            "pdf_filename": filename,
            "pages":      len(pages),
            "chunks":     len(chunks),
        },
    )
    return {"leaflet_id": leaflet_id, "page_count": page_count}