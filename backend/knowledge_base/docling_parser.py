"""
docling_parser.py — Structured PDF parsing using Docling.

Replaces the flat-text pdf_loader.py for resume and interview experience pipelines.
Returns a DocParsedOutput — a fully structured representation of the document
preserving: sections, headings, tables, figures, and clean text.

Responsibilities:
    - Run DocumentConverter (Docling) on a PDF path
    - Walk the DoclingDocument item tree
    - Extract headings, paragraphs, lists, tables, figures
    - Clean noise (page numbers, repeated headers/footers, empty sections)
    - Normalize unicode, whitespace, bullet characters
    - Return typed DocParsedOutput dataclass

Does NOT touch:
    - ChromaDB
    - LLM calls
    - Chunking logic
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("uvicorn.error")

# ---------------------------------------------------------------------------
# Docling imports — wrapped so the rest of the app stays importable even if
# docling is not yet installed (graceful degradation).
# ---------------------------------------------------------------------------
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    from docling_core.types.doc import DocItemLabel
    _DOCLING_AVAILABLE = True
except ImportError:
    _DOCLING_AVAILABLE = False
    logger.warning(
        "⚠️  docling is not installed. Run: pip install docling\n"
        "   Falling back to pdf_loader.py for resume/interview pipelines."
    )


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DocSection:
    """A logical section of the document (e.g. 'Skills', 'Technical Round 1')."""
    title: str
    content: str
    page_numbers: list[int] = field(default_factory=list)


@dataclass
class DocTable:
    """A table extracted from the document, converted to readable key-value text."""
    section_title: str
    rows: list[dict]          # e.g. [{"Skill": "Python", "Experience": "3 yrs"}]
    readable_text: str        # human-readable multiline representation
    page_number: int


@dataclass
class DocFigure:
    """
    A figure or image found in the document.
    Decorative icons are skipped. Meaningful diagrams get structured metadata.
    """
    section_title: str
    page_number: int
    placeholder: str          # "[IMAGE: decorative icon — skipped]" or "[FIGURE: diagram on page N]"
    figure_present: bool = True
    caption: Optional[str] = None


@dataclass
class DocParsedOutput:
    """
    Complete structured representation of a parsed PDF.

    Fields:
        document_type   -- "Resume" or "Interview Experience"
        document_name   -- original filename
        metadata        -- filename, page_count, document_title
        sections        -- ordered list of content sections
        tables          -- all tables found across the document
        figures         -- all non-trivial image references
        full_text       -- flattened plain-text for LLM metadata extraction (backward-compat)
    """
    document_type: str
    document_name: str
    metadata: dict
    sections: list[DocSection] = field(default_factory=list)
    tables: list[DocTable] = field(default_factory=list)
    figures: list[DocFigure] = field(default_factory=list)
    full_text: str = ""


# ---------------------------------------------------------------------------
# Decorative icon heuristics
# ---------------------------------------------------------------------------

_DECORATIVE_ICON_KEYWORDS = {
    "github", "linkedin", "email", "phone", "twitter",
    "instagram", "facebook", "mailto", "http", "www",
    "location", "address", "mobile", "portfolio",
}


def _is_decorative_icon(caption: str) -> bool:
    """Return True if the image is likely a decorative social/contact icon."""
    text = caption.lower().strip()
    return any(kw in text for kw in _DECORATIVE_ICON_KEYWORDS) or len(text) < 6


# ---------------------------------------------------------------------------
# Text cleaning helpers
# ---------------------------------------------------------------------------

# Matches lines that are purely a page number (e.g. "1", "- 2 -", "Page 3")
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:page\s*)?\d{1,4}\s*$|^[-–—]\s*\d{1,4}\s*[-–—]\s*$",
    re.IGNORECASE,
)

# Bullet character normalisation map
_BULLET_MAP = str.maketrans({
    "\u2022": "-",  # •
    "\u2023": "-",  # ‣
    "\u25e6": "-",  # ◦
    "\u2043": "-",  # ⁃
    "\u204c": "-",  # ⁌
    "\u204d": "-",  # ⁍
    "\uff0d": "-",  # －
})


def _normalize_text(text: str) -> str:
    """
    Clean and normalize a text string:
    - NFC unicode normalization
    - Replace exotic bullet characters with '-'
    - Collapse multiple spaces / blank lines
    - Strip leading/trailing whitespace
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_BULLET_MAP)
    # Collapse multiple spaces (but preserve single newlines for structure)
    text = re.sub(r" {2,}", " ", text)
    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_noise_line(line: str) -> bool:
    """Return True if a line should be discarded (page number, empty, etc.)."""
    stripped = line.strip()
    if not stripped:
        return True
    if _PAGE_NUMBER_RE.match(stripped):
        return True
    return False


# ---------------------------------------------------------------------------
# Table → readable text conversion
# ---------------------------------------------------------------------------

def _table_to_readable(rows: list[dict]) -> str:
    """
    Convert a list of row-dicts to human-readable key-value lines.

    Example:
        [{"Skill": "Python", "Experience": "3 yrs"}]
        → "Skill: Python | Experience: 3 yrs"
    """
    lines = []
    for row in rows:
        parts = [f"{k}: {v}" for k, v in row.items() if v]
        if parts:
            lines.append(" | ".join(parts))
    return "\n".join(lines)


def _extract_table_rows(table_item, doc) -> list[dict]:
    """
    Extract a table as a list of row-dicts using Docling's export API.
    Falls back to an empty list on any error.
    """
    try:
        df = table_item.export_to_dataframe(doc=doc)
        # Use first row as header if it looks like headers
        if df.shape[0] < 1:
            return []
        # Convert to list of dicts; fill NaN with ""
        df = df.fillna("")
        return df.to_dict(orient="records")
    except Exception as exc:
        logger.debug("Table extraction fallback: %s", exc)
        try:
            # Fallback: iterate cells manually
            rows: dict[int, dict] = {}
            for cell in table_item.data.table_cells:
                r = cell.start_row_offset_idx
                c = cell.start_col_offset_idx
                rows.setdefault(r, {})[c] = cell.text
            if not rows:
                return []
            # Sort by row index, build list of dicts with column indices as keys
            max_row = max(rows)
            result = []
            for r in range(max_row + 1):
                result.append({str(c): v for c, v in rows.get(r, {}).items()})
            return result
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Docling converter singleton (avoid reloading models on every file)
# ---------------------------------------------------------------------------

_converter: Optional["DocumentConverter"] = None


def _get_converter() -> "DocumentConverter":
    """Return a singleton DocumentConverter with sensible PDF options."""
    global _converter
    if _converter is None:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False          # OCR handled by pdf_loader fallback
        pipeline_options.do_table_structure = True
        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        logger.info("✅ Docling DocumentConverter initialized.")
    return _converter


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def parse_pdf(
    file_path: str,
    document_type: str = "Unknown",
) -> DocParsedOutput:
    """
    Parse a PDF using Docling and return a fully structured DocParsedOutput.

    Args:
        file_path:      Absolute path to the PDF file.
        document_type:  "Resume" or "Interview Experience" (caller supplies this).

    Returns:
        DocParsedOutput with sections, tables, figures, and full_text.

    Raises:
        ImportError if docling is not installed.
        RuntimeError if conversion fails.
    """
    if not _DOCLING_AVAILABLE:
        raise ImportError(
            "docling is not installed. Run: pip install docling"
        )

    path = Path(file_path)
    filename = path.name
    logger.info("🔍 Docling parsing: %s", filename)

    # ── Convert ──────────────────────────────────────────────────────────────
    try:
        converter = _get_converter()
        result = converter.convert(str(path))
        doc = result.document
    except Exception as exc:
        raise RuntimeError(f"Docling conversion failed for {filename}: {exc}") from exc

    # ── Document-level metadata ───────────────────────────────────────────────
    page_count = len(doc.pages) if hasattr(doc, "pages") else 1
    doc_title = filename  # default
    try:
        # Try to get the title from the first title-labelled item
        for item, _ in doc.iterate_items():
            if hasattr(item, "label") and str(item.label) in (
                "title", "DocItemLabel.TITLE",
            ):
                raw_title = getattr(item, "text", "").strip()
                if raw_title:
                    doc_title = raw_title
                    break
    except Exception:
        pass

    metadata = {
        "filename": filename,
        "page_count": page_count,
        "document_title": doc_title,
    }

    # ── Walk document items ───────────────────────────────────────────────────
    sections: list[DocSection] = []
    tables: list[DocTable] = []
    figures: list[DocFigure] = []

    current_section_title = "Introduction"
    current_content_lines: list[str] = []
    current_pages: list[int] = []
    seen_lines: set[str] = set()   # deduplication across headers/footers

    def _flush_section():
        """Save current_content_lines into a DocSection and reset."""
        nonlocal current_content_lines, current_pages
        content = _normalize_text("\n".join(
            line for line in current_content_lines
            if not _is_noise_line(line)
        ))
        if content:
            sections.append(DocSection(
                title=current_section_title,
                content=content,
                page_numbers=sorted(set(current_pages)),
            ))
        current_content_lines = []
        current_pages = []

    # Iterate document tree depth-first
    try:
        for item, _level in doc.iterate_items():
            label_str = str(getattr(item, "label", ""))
            text = getattr(item, "text", "").strip()
            page_no = 1
            try:
                prov = getattr(item, "prov", None)
                if prov:
                    page_no = prov[0].page_no if isinstance(prov, list) else prov.page_no
            except Exception:
                pass

            # ── Section heading ───────────────────────────────────────────────
            if "SECTION_HEADER" in label_str or "section_header" in label_str:
                _flush_section()
                current_section_title = _normalize_text(text) or current_section_title
                continue

            # ── Title ─────────────────────────────────────────────────────────
            if "TITLE" in label_str and "SECTION" not in label_str:
                # Already captured in doc_title above; skip to avoid duplication
                continue

            # ── Table ─────────────────────────────────────────────────────────
            if "TABLE" in label_str:
                rows = _extract_table_rows(item, doc)
                readable = _table_to_readable(rows)
                if readable:
                    tables.append(DocTable(
                        section_title=current_section_title,
                        rows=rows,
                        readable_text=readable,
                        page_number=page_no,
                    ))
                    # Also inject table text into the current section content
                    current_content_lines.append(readable)
                    current_pages.append(page_no)
                continue

            # ── Figure / Picture ──────────────────────────────────────────────
            if "PICTURE" in label_str or "FIGURE" in label_str:
                caption_text = text or None
                if caption_text and _is_decorative_icon(caption_text):
                    placeholder = "[IMAGE: decorative icon — skipped]"
                    fig_obj = DocFigure(
                        section_title=current_section_title,
                        page_number=page_no,
                        placeholder=placeholder,
                        figure_present=False,
                        caption=None,
                    )
                else:
                    placeholder = f"[FIGURE: diagram on page {page_no}]"
                    fig_obj = DocFigure(
                        section_title=current_section_title,
                        page_number=page_no,
                        placeholder=placeholder,
                        figure_present=True,
                        caption=caption_text,
                    )
                figures.append(fig_obj)
                continue

            # ── Furniture (repeated headers/footers) ──────────────────────────
            # Docling puts repeated page furniture in doc.furniture; skip it.
            if "PAGE_HEADER" in label_str or "PAGE_FOOTER" in label_str:
                continue

            # ── Paragraph / List / Caption / other text ───────────────────────
            if text:
                # Deduplicate repeated lines (common in multi-page headers)
                norm = text.lower().strip()
                if norm in seen_lines:
                    continue
                seen_lines.add(norm)
                current_content_lines.append(text)
                current_pages.append(page_no)

    except Exception as exc:
        logger.warning("⚠️  Error iterating Docling items for %s: %s", filename, exc)

    # Flush the last open section
    _flush_section()

    # ── Remove empty sections ─────────────────────────────────────────────────
    sections = [s for s in sections if s.content.strip()]

    # ── Build full_text (backward-compatible flat string) ─────────────────────
    full_text_parts: list[str] = []
    for section in sections:
        full_text_parts.append(f"[{section.title}]\n{section.content}")
    full_text = _normalize_text("\n\n".join(full_text_parts))

    logger.info(
        "✅ Docling parsed '%s': %d sections, %d tables, %d figures",
        filename, len(sections), len(tables), len(figures),
    )

    return DocParsedOutput(
        document_type=document_type,
        document_name=filename,
        metadata=metadata,
        sections=sections,
        tables=tables,
        figures=figures,
        full_text=full_text,
    )


def docling_available() -> bool:
    """Return True if docling is installed and usable."""
    return _DOCLING_AVAILABLE
