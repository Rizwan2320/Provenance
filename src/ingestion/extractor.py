# src/ingestion/extractor.py
"""
Text extraction for DIGITAL_TEXT / MIXED documents.
SCANNED routes to ocr.py (separate file — different dependency, different problem).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz

from configurations.schema import DocumentQuality


@dataclass
class PageExtraction:
    page_number: int
    text: str
    char_count: int


@dataclass
class ExtractionResult:
    pages: list[PageExtraction] = field(default_factory=list)
    total_chars: int = 0


def extract_digital(file_path: Path) -> ExtractionResult:
    """
    Extracts text from a DIGITAL_TEXT or MIXED document.
    sort=True handles multi-column reading order — no custom logic needed.
    """
    doc = fitz.open(str(file_path))
    pages = []

    for i, page in enumerate(doc):
        text = page.get_text("text", sort=True).strip()
        pages.append(PageExtraction(page_number=i + 1, text=text, char_count=len(text)))

    doc.close()
    return ExtractionResult(pages=pages, total_chars=sum(p.char_count for p in pages))


def extract(file_path: Path, quality: DocumentQuality) -> ExtractionResult:
    """Dispatcher — routes by detector's classification."""
    if quality in (DocumentQuality.DIGITAL_TEXT, DocumentQuality.MIXED):
        return extract_digital(file_path)
    if quality == DocumentQuality.SCANNED:
        raise NotImplementedError("SCANNED routes to ocr.py — build next.")
    raise ValueError(f"extractor.py should never receive {quality} — check detector gate.")