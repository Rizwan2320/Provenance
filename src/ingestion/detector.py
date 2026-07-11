"""
Document quality detector — first gate in the ingestion pipeline.

Classifies every incoming document before any extraction runs.
Routing logic lives here. Extraction strategies live in extractor.py.

Detection order (matters — each check assumes previous passed):
  1. Structural validation → first pipeline gate
  2. Corrupt  → can't open
  3. Encrypted → opens but locked
  4. Digital text / Scanned / Mixed → based on text sampling
  5. Density signals (table-heavy / image-heavy)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from ingestion.validator import validate

import fitz  # PyMuPDF  # type: ignore[reportMissingTypeStubs]

from configurations.schema import DocumentQuality

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Thresholds — named constants, not magic numbers
# ------------------------------------------------------------------
SAMPLE_PAGES            = 5      # pages sampled for quality detection
TEXT_CHARS_PER_PAGE     = 100    # minimum chars to consider a page "has text"
DIGITAL_THRESHOLD       = 0.80   # >= 80% text pages → DIGITAL_TEXT
SCANNED_THRESHOLD       = 0.20   # <= 20% text pages → SCANNED

# Density thresholds
TABLE_DENSITY_THRESHOLD = 0.5    # avg tables/page across sample → table_heavy
IMAGE_AREA_THRESHOLD    = 0.35   # avg fraction of page area as images → image_heavy


@dataclass
class DetectionResult:
    """
    Output of the detector. Immutable record of what was seen.
    Logged to audit trail before any extraction begins.
    """
    quality:           DocumentQuality
    page_count:        int
    text_ratio:        float          # fraction of sampled pages with text
    sample_size:       int            # actual pages sampled
    notes:             str            # human-readable reason for classification
    is_table_heavy:    bool = False
    is_image_heavy:    bool = False
    table_density:     float = 0.0
    image_area_ratio:  float = 0.0
    warnings:          list[str] = field(default_factory=list)


def detect(file_path: Path) -> DetectionResult:
    """
    Classify document quality from file path.
    Never raises — all failures are captured as CORRUPT or ENCRYPTED.
    """
    file_path = Path(file_path)

    # --------------------------------------------------------------
    # Gate 0 — Structural Pipeline Entry Validation
    # --------------------------------------------------------------
    result = validate(file_path)
    if not result.is_valid:
        raise ValueError(f"Rejected: {result.reason}")

    # Proceeding with quality checks if validation passes
    if not file_path.exists():
        return _make_corrupt_result(f"File not found: {file_path}")

    # Gate 1 — can we open it at all?
    try:
        doc = fitz.open(str(file_path))
    except Exception as exc:
        logger.warning("Cannot open document %s: %s", file_path.name, exc)
        return _make_corrupt_result(f"Failed to open: {exc}")

    # Gate 2 — encrypted and locked?
    if doc.is_encrypted:
        unlocked = doc.authenticate("")  # try empty password
        if not unlocked:
            doc.close()
            return DetectionResult(
                quality=DocumentQuality.ENCRYPTED,
                page_count=0,
                text_ratio=0.0,
                sample_size=0,
                notes="Document is encrypted and password-protected.",
                is_table_heavy=False,
                is_image_heavy=False,
                table_density=0.0,
                image_area_ratio=0.0,
            )
        logger.info("Document %s was encrypted but opened with empty password.",
                    file_path.name)

    page_count = len(doc)

    if page_count == 0:
        doc.close()
        return _make_corrupt_result("Document has zero pages.")

    # Gate 3 — sample pages for text + density signals
    sample_size = min(SAMPLE_PAGES, page_count)
    step = max(1, page_count // sample_size)
    page_indices = [i * step for i in range(sample_size)]

    pages_with_text = 0
    table_counts: list[int] = []
    image_ratios: list[float] = []
    warnings: list[str] = []

    for idx in page_indices:
        try:
            page = doc[idx]
            raw_text = cast(Any, page).get_text("text")
            text = raw_text.strip() if isinstance(raw_text, str) else ""
            if len(text) >= TEXT_CHARS_PER_PAGE:
                pages_with_text += 1

            # Table density
            try:
                tables = cast(Any, page).find_tables()
                table_entries = getattr(tables, "tables", []) if tables is not None else []
                if not isinstance(table_entries, list):
                    table_entries = []
                table_counts.append(len(table_entries))
            except Exception:
                table_counts.append(0)

            # Image density — fraction of page area covered by images
            try:
                page_area = page.rect.width * page.rect.height
                images = cast(Any, page).get_image_info()
                covered = 0.0
                if isinstance(images, list):
                    for img in images:
                        if isinstance(img, dict):
                            bbox = img.get("bbox")
                            if (
                                isinstance(bbox, (list, tuple))
                                and len(bbox) == 4
                                and all(isinstance(x, (int, float)) for x in bbox)
                            ):
                                covered += (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                ratio = min(covered / page_area, 1.0) if page_area > 0 else 0.0
                image_ratios.append(ratio)
            except Exception:
                image_ratios.append(0.0)

        except Exception as exc:
            warnings.append(f"Page {idx} sampling failed: {exc}")
            table_counts.append(0)
            image_ratios.append(0.0)

    doc.close()

    text_ratio = pages_with_text / sample_size if sample_size > 0 else 0.0
    avg_table_density = sum(table_counts) / len(table_counts) if table_counts else 0.0
    avg_image_ratio   = sum(image_ratios) / len(image_ratios) if image_ratios else 0.0

    is_table_heavy = avg_table_density >= TABLE_DENSITY_THRESHOLD
    is_image_heavy = (avg_image_ratio >= IMAGE_AREA_THRESHOLD) and (text_ratio > SCANNED_THRESHOLD)

    # Classification — restored to clean 3-way logic
    if text_ratio >= DIGITAL_THRESHOLD:
        quality = DocumentQuality.DIGITAL_TEXT
    elif text_ratio <= SCANNED_THRESHOLD:
        quality = DocumentQuality.SCANNED
    else:
        quality = DocumentQuality.MIXED

    notes = (
        f"{pages_with_text}/{sample_size} sampled pages have text "
        f"(ratio={text_ratio:.2f}) → {quality.value}"
        f"{' | table_heavy' if is_table_heavy else ''}"
        f"{' | image_heavy' if is_image_heavy else ''}"
    )

    if warnings:
        logger.warning("Detection warnings for %s: %s", file_path.name, warnings)

    return DetectionResult(
        quality=quality,
        page_count=page_count,
        text_ratio=text_ratio,
        sample_size=sample_size,
        notes=notes,
        is_table_heavy=is_table_heavy,
        is_image_heavy=is_image_heavy,
        table_density=avg_table_density,
        image_area_ratio=avg_image_ratio,
        warnings=warnings,
    )


def _make_corrupt_result(notes: str) -> DetectionResult:
    """Helper to reduce duplication in early failure paths."""
    return DetectionResult(
        quality=DocumentQuality.CORRUPT,
        page_count=0,
        text_ratio=0.0,
        sample_size=0,
        notes=notes,
        is_table_heavy=False,
        is_image_heavy=False,
        table_density=0.0,
        image_area_ratio=0.0,
    )