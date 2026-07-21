"""
PDF loader — PDF-only input with text extraction and OCR for embedded/page images.
"""

import io
import logging
from typing import Union

import fitz  # pymupdf
from pypdf import PdfReader

from config import GEMINI_API_KEY

logger = logging.getLogger("uvicorn.error")

PDF_MAGIC = b"%PDF"
MIN_PAGE_TEXT_FOR_OCR = 40


class PdfValidationError(ValueError):
    """Raised when uploaded content is not a valid PDF."""


def validate_pdf_bytes(data: bytes, filename: str = "") -> None:
    """Reject non-PDF or empty/corrupt PDF input."""
    if not data:
        raise PdfValidationError("Empty file. Only PDF uploads are accepted.")

    if not data.startswith(PDF_MAGIC):
        label = filename or "file"
        raise PdfValidationError(
            f"'{label}' is not a PDF. Only PDF format is accepted — other file types are rejected."
        )

    if len(data) < 100:
        raise PdfValidationError("PDF file is too small or corrupted.")


def _ocr_with_pytesseract(image_bytes: bytes) -> str:
    """OCR image bytes using Tesseract when installed."""
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as exc:
        logger.debug("pytesseract OCR unavailable: %s", exc)
        return ""


def _ocr_with_gemini(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """OCR image bytes using Gemini vision when an API key is configured."""
    if not GEMINI_API_KEY:
        return ""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                "Extract all readable text from this image. Return only the extracted text, preserving layout where possible.",
            ],
        )
        return (response.text or "").strip()
    except Exception as exc:
        logger.warning("Gemini OCR failed: %s", exc)
        return ""


def _ocr_image(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Run OCR with local Tesseract first, then Gemini fallback."""
    text = _ocr_with_pytesseract(image_bytes)
    if len(text) >= 10:
        return text
    return _ocr_with_gemini(image_bytes, mime_type=mime_type)


def _open_pdf_document(path_or_bytes: Union[str, bytes]) -> fitz.Document:
    if isinstance(path_or_bytes, bytes):
        validate_pdf_bytes(path_or_bytes)
        return fitz.open(stream=path_or_bytes, filetype="pdf")
    return fitz.open(path_or_bytes)


def _extract_pypdf_text(path_or_bytes: Union[str, bytes]) -> str:
    if isinstance(path_or_bytes, bytes):
        reader = PdfReader(io.BytesIO(path_or_bytes))
    else:
        reader = PdfReader(path_or_bytes)

    parts = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if page_text:
            parts.append(f"[Page {index}]\n{page_text}")
    return "\n\n".join(parts)


def _extract_image_and_scan_text(doc: fitz.Document) -> str:
    """Extract text from embedded images and OCR sparse pages."""
    parts = []

    for page_index, page in enumerate(doc, start=1):
        page_text = (page.get_text("text") or "").strip()

        for image_index, image_info in enumerate(page.get_images(full=True), start=1):
            xref = image_info[0]
            try:
                extracted = doc.extract_image(xref)
                image_bytes = extracted["image"]
                mime_type = f"image/{extracted.get('ext', 'png')}"
                ocr_text = _ocr_image(image_bytes, mime_type=mime_type)
                if ocr_text:
                    parts.append(f"[Page {page_index} Image {image_index}]\n{ocr_text}")
            except Exception as exc:
                logger.debug("Failed to OCR embedded image on page %s: %s", page_index, exc)

        if len(page_text) < MIN_PAGE_TEXT_FOR_OCR:
            try:
                pixmap = page.get_pixmap(dpi=200)
                png_bytes = pixmap.tobytes("png")
                ocr_text = _ocr_image(png_bytes, mime_type="image/png")
                if ocr_text:
                    parts.append(f"[Page {page_index} Scan]\n{ocr_text}")
            except Exception as exc:
                logger.debug("Failed to OCR scanned page %s: %s", page_index, exc)

    return "\n\n".join(parts)


def load_pdf(path_or_bytes: Union[str, bytes]) -> str:
    """
    Load a PDF and return combined text from:
    1. Native PDF text layers (pypdf)
    2. OCR of embedded images
    3. OCR of image-only/scanned pages
    """
    if isinstance(path_or_bytes, bytes):
        validate_pdf_bytes(path_or_bytes)

    try:
        native_text = _extract_pypdf_text(path_or_bytes)
    except Exception as exc:
        logger.warning("pypdf native text extraction failed: %s. Falling back to fitz.", exc)
        native_text = ""

    try:
        doc = _open_pdf_document(path_or_bytes)
        try:
            scanned_text = _extract_image_and_scan_text(doc)
        finally:
            doc.close()
    except PdfValidationError:
        raise
    except Exception as exc:
        logger.warning("Image OCR pass failed, using native PDF text only: %s", exc)
        scanned_text = ""

    sections = [section for section in (native_text, scanned_text) if section.strip()]
    combined = "\n\n".join(sections).strip()

    if not combined:
        raise PdfValidationError(
            "Could not extract any text from the PDF. Ensure the PDF contains readable text or scannable images."
        )

    return combined
