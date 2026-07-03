# src/ingestion/extractor.py
"""
Text extraction for DIGITAL_TEXT / MIXED documents.

SCANNED documents are routed to the OCR module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz

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
    Extracts text from DIGITAL_TEXT or MIXED documents using PyMuPDF.
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


def extract(file_path: Path, quality: DocumentQuality) -> ExtractionResult:
    """Main dispatcher — always returns ExtractionResult."""
    if quality in (DocumentQuality.DIGITAL_TEXT, DocumentQuality.MIXED):
        return extract_digital(file_path)

    if quality == DocumentQuality.SCANNED:
        from .ocr import extract_scanned

        ocr_result = extract_scanned(file_path)

        # Convert OCR-specific result to standard ExtractionResult
        pages: list[PageExtraction] = [
            PageExtraction(
                page_number=p.page_number,
                text=p.text,
                char_count=len(p.text),   # or p.char_count if available
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