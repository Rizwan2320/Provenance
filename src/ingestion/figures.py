# src/configurations/ingestion/figures.py
"""Figure/image extraction. Detection + crop only — no LLM yet, see Day 4 step 2."""

from __future__ import annotations
from pathlib import Path

import fitz

from configurations.schema import Figure
from configurations.config import get_settings

# Filters out logos/icons — real charts and diagrams are meaningfully sized.
MIN_IMAGE_AREA_RATIO = 0.03   # below this: logo/icon noise
MAX_IMAGE_AREA_RATIO = 0.85   # image must cover at least 3% of page area


def extract_figures(file_path: Path, doc_id: str, version: int = 1) -> list[Figure]:
    settings = get_settings()
    out_dir = settings.page_images_dir.parent / "figures" / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(file_path))
    figures = []
    fig_index = 0

    for page in doc:
        page_area = page.rect.width * page.rect.height
        images = page.get_image_info(xrefs=True)

        for img in images:
            bbox = img["bbox"]
            img_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            if page_area == 0:
                continue
            ratio = img_area / page_area
            if ratio < MIN_IMAGE_AREA_RATIO or ratio > MAX_IMAGE_AREA_RATIO:
                continue

            xref = img["xref"]
            try:
                pix = fitz.Pixmap(doc, xref)

                # Force conversion to RGB (handles CMYK, RGBA, etc.)
                if pix.colorspace is None:          # Grayscale
                    pix = fitz.Pixmap(fitz.csGRAY, pix)
                elif pix.colorspace.name != "DeviceRGB":
                    pix = fitz.Pixmap(fitz.csRGB, pix)

            except ValueError:
                # Some xrefs (masks, inline images, etc.) can't be extracted
                continue

            # Ensure we have a valid pixmap before saving
            if pix is None:
                continue

            page_num = page.number if page.number is not None else 0

            out_path = out_dir / f"fig{fig_index}_page{page_num + 1}.png"
            pix.save(str(out_path))

            figures.append(
                Figure(
                    id=f"{doc_id}-v{version}-fig{fig_index}",
                    document_id=doc_id,
                    document_version=version,
                    page_number=page_num + 1,
                    bbox=tuple(bbox),
                    image_path=str(out_path),
                )
            )
            fig_index += 1

    doc.close()
    return figures