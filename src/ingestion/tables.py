# src/configurations/ingestion/tables.py

from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

import fitz
from anthropic.types import TextBlock

from configurations.schema import Table
from configurations.provider import get_llm_client
from configurations.config import get_settings


def _is_prose_like(data: list[list], max_avg_words: int = 8) -> bool:
    """Real table cells hold short values. Misdetected prose averages many words/cell."""
    cells = [c for row in data for c in row if c is not None and str(c).strip()]
    if not cells:
        return True
    avg_words = sum(len(str(c).split()) for c in cells) / len(cells)
    return avg_words > max_avg_words


def _normalize_table_data(data: list[list]) -> list[list[Optional[str]]]:
    """Normalize extracted table cells to strings or None for empty values."""
    normalized = []
    for row in data:
        if not isinstance(row, (list, tuple)):
            row = [row]
        normalized.append([
            None if cell is None else str(cell).strip() or None
            for cell in row
        ])
    return normalized

def extract_tables(file_path: Path, doc_id: str, version: int = 1) -> list[Table]:
    doc = fitz.open(str(file_path))
    tables = []
    table_index = 0

    for page in doc:
        found: Any = page.find_tables(strategy="lines")
        table_entries = getattr(found, "tables", []) if found is not None else []

        for t in table_entries:
            data = t.extract()
            if not data or len(data) < 2:
                continue

            data = _normalize_table_data(data)
            if not data or len(data) < 2:
                continue
            if not any(any(cell is not None for cell in row) for row in data):
                continue
            if _is_prose_like(data):
                continue

            page_number = getattr(page, "number", None)
            if page_number is None:
                continue

            extraction_confidence = 1.0
            if hasattr(t, "confidence"):
                confidence_value = getattr(t, "confidence")
                if confidence_value is not None:
                    try:
                        extraction_confidence = float(confidence_value)
                    except (TypeError, ValueError):
                        extraction_confidence = 1.0

            bbox_value = getattr(t, "bbox", None)
            if bbox_value is None or len(bbox_value) != 4:
                bbox_value = (0.0, 0.0, 0.0, 0.0)

            tables.append(Table(
                id=f"{doc_id}-v{version}-table{table_index}",
                document_id=doc_id,
                document_version=version,
                page_number=page_number + 1,
                headers=[cell or "" for cell in data[0]],
                rows=data[1:],
                bbox=(float(bbox_value[0]), float(bbox_value[1]), float(bbox_value[2]), float(bbox_value[3])),
                extraction_confidence=extraction_confidence,
            ))
            table_index += 1

    doc.close()
    return tables

def generate_table_description(table: Table) -> str:
    """LLM-generated NL description — enables embedding-based retrieval of table content."""
    settings = get_settings()
    client = get_llm_client()

    prompt = f"""Describe this table in 2-3 sentences. State what it shows and any notable values.

Headers: {table.headers}
Rows: {table.rows[:5]}
Page: {table.page_number}"""

    response = client.messages.create(
        model=settings.llm_model_name,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    # Extract text from response content
    for block in response.content:
        if isinstance(block, TextBlock):
            return block.text.strip()  # type: ignore[attr-defined]
    return ""