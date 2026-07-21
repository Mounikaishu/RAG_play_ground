"""
docling_chunker.py — Section-aware chunking for Docling-parsed documents.

Replaces the blind word-count chunking (chunker.py) for resume and interview
experience pipelines. Each chunk knows which section it came from, what page
it was on, and what type of document it belongs to.

Responsibilities:
    - Accept a DocParsedOutput
    - Produce list[DocChunk] — one or more chunks per section
    - Include each table's readable_text as its own dedicated chunk
    - Delegate oversized sections to chunk_text_with_overlap() (existing chunker)
    - Carry section_title and page_number on every chunk for richer retrieval

Does NOT touch:
    - ChromaDB
    - LLM calls
    - Docling (that's docling_parser.py's job)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from chunker import chunk_text_with_overlap
from knowledge_base.docling_parser import DocParsedOutput, DocTable

logger = logging.getLogger("uvicorn.error")

# Max words in a section before we apply overlap-chunking to it.
# Below this threshold the whole section becomes a single chunk.
_SECTION_CHUNK_THRESHOLD = 400  # words


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class DocChunk:
    """
    A single text chunk ready for embedding and ChromaDB storage.

    Fields:
        text            -- the chunk text to embed
        section_title   -- which section of the document this came from
        page_number     -- which page the content was on (first page for multi-page sections)
        chunk_index     -- global chunk counter within this document
        document_type   -- "Resume" or "Interview Experience"
        source_file     -- original PDF filename
        chunk_source    -- "section", "table", or "figure"
    """
    text: str
    section_title: str
    page_number: int
    chunk_index: int
    document_type: str
    source_file: str
    chunk_source: str = "section"   # "section" | "table" | "figure"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _word_count(text: str) -> int:
    return len(text.split())


def _normalize_section_title(raw_title: str, doc_type: str) -> str:
    """Normalize raw section title into standard section categories."""
    t = raw_title.lower().strip()

    if "resume" in doc_type.lower():
        if any(k in t for k in ["summary", "about me", "objective", "profile"]):
            return "Summary"
        if any(k in t for k in ["education", "academic", "degree", "qualification"]):
            return "Education"
        if any(k in t for k in ["skill", "technolog", "proficiency", "expertise", "competenc"]):
            return "Skills"
        if any(k in t for k in ["experience", "work history", "employment", "internship"]):
            return "Experience"
        if any(k in t for k in ["project", "portfolio"]):
            return "Projects"
        if any(k in t for k in ["certifi", "license", "course"]):
            return "Certifications"
        if any(k in t for k in ["achievement", "award", "honor", "publication"]):
            return "Achievements"

    if "interview" in doc_type.lower():
        if any(k in t for k in ["overview", "introduction", "company info", "about"]):
            return "Company Overview"
        if any(k in t for k in ["eligib", "criteria", "requirement"]):
            return "Eligibility"
        if any(k in t for k in ["online assessment", "oa", "coding test"]):
            return "Online Assessment"
        if any(k in t for k in ["technical", "dsa", "coding round", "system design"]):
            return "Technical Round"
        if any(k in t for k in ["hr", "behavioral", "managerial"]):
            return "HR Round"
        if any(k in t for k in ["question", "problem", "asked"]):
            return "Questions Asked"
        if any(k in t for k in ["tip", "advice", "suggestion", "strategy"]):
            return "Tips"
        if any(k in t for k in ["resource", "reference", "link"]):
            return "Resources"

    return raw_title.strip().title() or "Section"


def _chunk_section(
    section_text: str,
    section_title: str,
    page_number: int,
    document_type: str,
    source_file: str,
    start_index: int,
    chunk_size: int = 400,
    overlap: int = 80,
) -> list[DocChunk]:
    """
    Turn one section's text into one or more DocChunks.

    If the section is short enough, it becomes a single chunk.
    If it is long, chunk_text_with_overlap() splits it further.
    Every sub-chunk is prefixed with the section title so the LLM
    always knows the context even when the chunk is retrieved in isolation.
    """
    chunks: list[DocChunk] = []

    norm_title = _normalize_section_title(section_title, document_type)

    if _word_count(section_text) <= _SECTION_CHUNK_THRESHOLD:
        # Short section → single chunk (prefix with heading for context)
        text = f"[{norm_title}]\n{section_text}".strip()
        chunks.append(DocChunk(
            text=text,
            section_title=norm_title,
            page_number=page_number,
            chunk_index=start_index,
            document_type=document_type,
            source_file=source_file,
            chunk_source="section",
        ))
    else:
        # Long section → split with overlap, prefix each sub-chunk
        sub_chunks = chunk_text_with_overlap(
            section_text, chunk_size=chunk_size, overlap=overlap
        )
        for i, sub in enumerate(sub_chunks):
            text = f"[{norm_title}]\n{sub}".strip()
            chunks.append(DocChunk(
                text=text,
                section_title=norm_title,
                page_number=page_number,
                chunk_index=start_index + i,
                document_type=document_type,
                source_file=source_file,
                chunk_source="section",
            ))

    return chunks


def _chunk_table(
    table: DocTable,
    document_type: str,
    source_file: str,
    chunk_index: int,
) -> DocChunk:
    """
    Convert a DocTable into a single DocChunk using its readable_text.
    Tables are small enough to always be a single chunk.
    """
    text = f"[{table.section_title} — Table]\n{table.readable_text}".strip()
    return DocChunk(
        text=text,
        section_title=table.section_title,
        page_number=table.page_number,
        chunk_index=chunk_index,
        document_type=document_type,
        source_file=source_file,
        chunk_source="table",
    )


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def chunk_parsed_document(
    parsed: DocParsedOutput,
    chunk_size: int = 400,
    overlap: int = 80,
) -> list[DocChunk]:
    """
    Convert a DocParsedOutput into an ordered list of DocChunks.

    Strategy:
        1. Process sections in document order.
        2. For each section, split into sub-chunks if needed.
        3. Tables that are NOT already embedded in a section's text get their own chunk.
        4. Figures with meaningful placeholders get their own small chunk.
        5. All chunk_index values are globally unique within the document.

    Args:
        parsed:     The structured output from docling_parser.parse_pdf().
        chunk_size: Max words per sub-chunk (when splitting large sections).
        overlap:    Overlap words between adjacent sub-chunks.

    Returns:
        list[DocChunk] — ordered, globally indexed, metadata-rich chunks.
    """
    chunks: list[DocChunk] = []
    idx = 0

    if not parsed.sections and not parsed.tables:
        # Edge case: Docling found nothing structured — fall back to full_text
        if parsed.full_text.strip():
            logger.warning(
                "⚠️  No sections found by Docling for '%s'. Using full_text fallback.",
                parsed.document_name,
            )
            sub_chunks = chunk_text_with_overlap(
                parsed.full_text, chunk_size=chunk_size, overlap=overlap
            )
            for i, sub in enumerate(sub_chunks):
                chunks.append(DocChunk(
                    text=sub,
                    section_title="Document",
                    page_number=1,
                    chunk_index=i,
                    document_type=parsed.document_type,
                    source_file=parsed.document_name,
                    chunk_source="section",
                ))
        return chunks

    # Track which tables have been "seen" via section content injection.
    # Tables whose readable_text is already inside a section's content are
    # skipped here to avoid duplication.
    injected_table_texts: set[str] = set()
    for section in parsed.sections:
        injected_table_texts.update(
            table.readable_text
            for table in parsed.tables
            if table.readable_text and table.readable_text in section.content
        )

    # ── Process sections ──────────────────────────────────────────────────────
    for section in parsed.sections:
        if not section.content.strip():
            continue

        page_no = section.page_numbers[0] if section.page_numbers else 1
        new_chunks = _chunk_section(
            section_text=section.content,
            section_title=section.title,
            page_number=page_no,
            document_type=parsed.document_type,
            source_file=parsed.document_name,
            start_index=idx,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        chunks.extend(new_chunks)
        idx += len(new_chunks)

    # ── Process standalone tables ─────────────────────────────────────────────
    for table in parsed.tables:
        if not table.readable_text:
            continue
        # Skip if already injected into section content
        if table.readable_text in injected_table_texts:
            continue
        chunk = _chunk_table(
            table=table,
            document_type=parsed.document_type,
            source_file=parsed.document_name,
            chunk_index=idx,
        )
        chunks.append(chunk)
        idx += 1

    # ── Process meaningful figures ────────────────────────────────────────────
    for fig in parsed.figures:
        if "[FIGURE:" in fig.placeholder:  # skip decorative icon placeholders
            text = f"[{fig.section_title} — Figure]\n{fig.placeholder}".strip()
            chunks.append(DocChunk(
                text=text,
                section_title=fig.section_title,
                page_number=fig.page_number,
                chunk_index=idx,
                document_type=parsed.document_type,
                source_file=parsed.document_name,
                chunk_source="figure",
            ))
            idx += 1

    logger.info(
        "✅ Chunked '%s': %d total chunks from %d sections + %d tables + %d figures",
        parsed.document_name,
        len(chunks),
        len(parsed.sections),
        len(parsed.tables),
        len(parsed.figures),
    )

    return chunks
