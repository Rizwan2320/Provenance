# src/rag_portal/ingestion/validator.py
"""File validation — runs before any extraction touches the file."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF can double as a magic-byte check for PDFs

from configurations.config import get_settings

PDF_MAGIC = b"%PDF-"


@dataclass
class ValidationResult:
    is_valid: bool
    reason: str = ""


def validate(file_path: Path) -> ValidationResult:
    settings = get_settings()

    if not file_path.exists():
        return ValidationResult(False, "File does not exist")

    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb == 0:
        return ValidationResult(False, "File is empty")
    if size_mb > settings.max_upload_size_mb:
        return ValidationResult(False, f"File is {size_mb:.1f}MB, max is {settings.max_upload_size_mb}MB")

    with open(file_path, "rb") as f:
        header = f.read(5)
    if header != PDF_MAGIC:
        return ValidationResult(False, "File is not a valid PDF (magic bytes mismatch)")

    return ValidationResult(True)