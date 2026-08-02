# src/configurations/ingestion/hierarchy.py
"""
Section hierarchy extraction. PDF's native outline (bookmarks) is
ground truth when present — no guessing needed. Font-size/bold
heuristic is a fallback only for documents without one.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import fitz

from ingestion.tables import extract_tables


@dataclass
class Heading:
    text: str
    page_number: int
    level: int
    source: str = "toc"  # "toc" (authoritative) or "heuristic" (best-effort fallback)


def _extract_from_toc(file_path: Path) -> list[Heading]:
    doc = fitz.open(str(file_path))
    toc = doc.get_toc()
    doc.close()
    return [Heading(text=title, page_number=page, level=level, source="toc")
            for level, title, page in toc]


def _bbox_overlaps(span_bbox: tuple, table_bbox: tuple) -> bool:
    sx0, sy0, sx1, sy1 = span_bbox
    tx0, ty0, tx1, ty1 = table_bbox
    return not (sx1 < tx0 or sx0 > tx1 or sy1 < ty0 or sy0 > ty1)


def _page_blocks(page: fitz.Page) -> list[dict[str, Any]]:
    page_text = cast(dict[str, Any], page.get_text("dict"))
    return cast(list[dict[str, Any]], page_text.get("blocks", []))


def _extract_via_heuristic(file_path: Path, doc_id: str = "temp") -> list[Heading]:
    """Fallback only — used when the document has no embedded outline."""
    doc = fitz.open(str(file_path))

    table_bboxes_by_page: dict[int, list[tuple]] = {}
    for t in extract_tables(file_path, doc_id=doc_id):
        table_bboxes_by_page.setdefault(t.page_number, []).append(t.bbox)

    size_counts: dict[float, int] = {}
    for page in doc:
        for block in _page_blocks(page):
            for line in cast(list[dict[str, Any]], block.get("lines", [])):
                for span in cast(list[dict[str, Any]], line.get("spans", [])):
                    size = round(cast(float, span["size"]), 1)
                    size_counts[size] = size_counts.get(size, 0) + len(cast(str, span["text"]))

    if not size_counts:
        doc.close()
        return []

    body_size = max(size_counts.items(), key=lambda item: item[1])[0]
    candidates = []

    for page in doc:
        page_number = (page.number or 0) + 1
        page_tables = table_bboxes_by_page.get(page_number, [])
        for block in _page_blocks(page):
            for line in cast(list[dict[str, Any]], block.get("lines", [])):
                for span in cast(list[dict[str, Any]], line.get("spans", [])):
                    text = cast(str, span["text"]).strip()
                    if not text or any(_bbox_overlaps(cast(tuple, span["bbox"]), tb) for tb in page_tables):
                        continue
                    size = round(cast(float, span["size"]), 1)
                    is_bold = bool(cast(int, span["flags"]) & 16)
                    is_larger = size > body_size * 1.15
                    is_bold_same_size = is_bold and abs(size - body_size) < 0.5
                    if is_larger or is_bold_same_size:
                        candidates.append(Heading(text=text, page_number=page_number,
                                                    level=0, source="heuristic"))
    doc.close()
    return candidates


def extract_hierarchy(file_path: Path, doc_id: str = "temp") -> list[Heading]:
    """TOC first. Heuristic fallback only when no outline exists."""
    toc_headings = _extract_from_toc(file_path)
    if toc_headings:
        return toc_headings
    return _extract_via_heuristic(file_path, doc_id=doc_id)