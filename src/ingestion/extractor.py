# src/ingestion/extractor.py
"""
Text extraction for DIGITAL_TEXT / MIXED / SCANNED documents.

Performs page-by-page routing for MIXED documents to balance 
digital text extraction and OCR performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz

from configurations.config import get_settings
from ingestion.detector import TEXT_CHARS_PER_PAGE
from ingestion.ocr import _ocr_page, extract_scanned
from configurations.schema import DocumentQuality


@dataclass
class PageExtraction:
    """Standard page extraction result used across the ingestion pipeline."""
    page_number: int
    text: str
    char_count: int


@dataclass
class ExtractionResult:
    """Unified result type returned by the extractor."""
    pages: list[PageExtraction] = field(default_factory=list)
    total_chars: int = 0


def extract_digital(file_path: Path) -> ExtractionResult:
    """
    Extracts text from DIGITAL_TEXT documents using PyMuPDF.
    """
    doc = fitz.open(str(file_path))
    pages: list[PageExtraction] = []

    for i, page in enumerate(doc):
        text = page.get_text("text", sort=True).strip()
        pages.append(
            PageExtraction(
                page_number=i + 1,
                text=text,
                char_count=len(text),
            )
        )

    doc.close()

    return ExtractionResult(
        pages=pages,
        total_chars=sum(p.char_count for p in pages),
    )


def extract_mixed(file_path: Path) -> ExtractionResult:
    """Per-page: use real text if present, OCR only the pages that lack it."""
    doc = fitz.open(str(file_path))
    pages: list[PageExtraction] = []

    for i, page in enumerate(doc):
        text = page.get_text("text", sort=True).strip()
        
        # Fall back to OCR if the native text layer is missing or insufficient
        if len(text) < TEXT_CHARS_PER_PAGE:
            text, _ = _ocr_page(page)
            text = text.strip()

        pages.append(
            PageExtraction(
                page_number=i + 1,
                text=text,
                char_count=len(text),
            )
        )

    doc.close()

    return ExtractionResult(
        pages=pages,
        total_chars=sum(p.char_count for p in pages),
    )


def extract(file_path: Path, doc_id: str, quality: DocumentQuality) -> ExtractionResult:
    """Main dispatcher — routes processing based on document quality metrics."""
    # Save page images for all document types
    save_page_images(file_path, doc_id)

    if quality == DocumentQuality.DIGITAL_TEXT:
        return extract_digital(file_path)

    if quality == DocumentQuality.MIXED:
        return extract_mixed(file_path)

    if quality == DocumentQuality.SCANNED:
        ocr_result = extract_scanned(file_path)

        # Convert OCR-specific result to standard ExtractionResult structure
        pages = [
            PageExtraction(
                page_number=p.page_number,
                text=p.text.strip(),
                char_count=len(p.text.strip()),
            )
            for p in ocr_result.pages
        ]

        return ExtractionResult(
            pages=pages,
            total_chars=sum(p.char_count for p in pages),
        )

    raise ValueError(
        f"extractor.py received unexpected quality: {quality}. "
        "Check the document quality detector upstream."
    )


def save_page_images(file_path: Path, doc_id: str) -> list[str]:
    """One image per page. Returns list of saved paths."""
    settings = get_settings()
    out_dir = settings.page_images_dir / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(file_path))
    paths: list[str] = []

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)  # 150 is enough for viewing, not OCR
        out_path = out_dir / f"page_{i+1}.png"
        pix.save(str(out_path))
        paths.append(str(out_path))

    doc.close()
    return paths
