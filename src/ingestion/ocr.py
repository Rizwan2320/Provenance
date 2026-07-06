# src/rag_portal/ingestion/ocr.py
"""
OCR extraction for SCANNED documents, plus per-page fallback used
by extractor.py for MIXED documents. Separate from extractor.py —
different dependency (system Tesseract binary), different failure mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

# Windows: point pytesseract at the binary explicitly — it doesn't
# auto-find it like on Linux/Mac.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Global threshold for quality control
OCR_REVIEW_THRESHOLD = 70.0  # below this, flag for human review — set from real data: 51.2 (bad) vs 92-94 (good)


@dataclass
class OCRPageResult:
    page_number: int
    text: str
    confidence: float  # 0-100, Tesseract's mean word confidence
    needs_review: bool = False  # confidence < OCR_REVIEW_THRESHOLD


@dataclass
class OCRResult:
    pages: list[OCRPageResult] = field(default_factory=list)


def _ocr_page(page: fitz.Page, dpi: int = 300) -> tuple[str, float]:
    """
    OCR a single page. Shared by extract_scanned() (whole SCANNED doc)
    and extractor.py's extract_mixed() (one page at a time, on demand).
    dpi=300 is Tesseract's documented accuracy sweet spot.
    """
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    text = pytesseract.image_to_string(img).strip()

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    confidences = [int(c) for c in data["conf"] if int(c) >= 0]  # -1 = no detection
    confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return text, confidence


def extract_scanned(file_path: Path, dpi: int = 300) -> OCRResult:
    """OCRs every page of a fully SCANNED document."""
    doc = fitz.open(str(file_path))
    pages = []

    for i, page in enumerate(doc):
        text, confidence = _ocr_page(page, dpi)
        pages.append(
            OCRPageResult(
                page_number=i + 1,
                text=text,
                confidence=confidence,
                needs_review=confidence < OCR_REVIEW_THRESHOLD,
            )
        )

    doc.close()
    return OCRResult(pages=pages)