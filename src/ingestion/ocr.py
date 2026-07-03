# src/rag_portal/ingestion/ocr.py
"""
OCR extraction for SCANNED documents. Separate from extractor.py —
different dependency (system Tesseract binary), different failure mode.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

# ====================== TESSERACT CONFIG ======================
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Optional: Helps with language data
os.environ.setdefault('TESSDATA_PREFIX', r"C:\Program Files\Tesseract-OCR\tessdata")


@dataclass
class OCRPageResult:
    """Page result from OCR processing."""
    page_number: int
    text: str
    confidence: float  # Average word confidence (0-100)


@dataclass
class OCRResult:
    """Complete OCR result for a document."""
    pages: list[OCRPageResult] = field(default_factory=list)


def extract_scanned(file_path: Path, dpi: int = 300) -> OCRResult:
    """
    Renders each PDF page to an image, runs Tesseract, returns text + confidence.
    dpi=300 is Tesseract's documented sweet spot.
    """
    doc = fitz.open(str(file_path))
    pages: list[OCRPageResult] = []

    for i, page in enumerate(doc):
        # Get pixmap and convert to PIL Image
        pix = page.get_pixmap(dpi=dpi)

        # FIXED: size must be a tuple, not a list
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        # OCR
        text = pytesseract.image_to_string(img, lang="eng").strip()

        # Get confidence
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        confidences = [int(c) for c in data["conf"] if int(c) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        pages.append(
            OCRPageResult(
                page_number=i + 1,
                text=text,
                confidence=avg_confidence,
            )
        )

    doc.close()
    return OCRResult(pages=pages)