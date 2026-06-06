# src/rag_portal/schema.py
"""
Canonical data model — Phase 0 baseline.

ID convention (established here, followed everywhere):
  Documents : UUID4
  Chunks    : {doc_uuid}-v{version_int}-{chunk_index}  ← version-encoded
  All runs  : UUID4

Addition policy:
  Entities are added here the day before the phase that needs them.
  Do not add an entity speculatively.

  Phase 1 Day 1  → Page, Chunk, ContentType
  Phase 1 Day 5  → CanonicalEntity, EntityMention
  Phase 1 Day 7  → GoldenExample, EvaluationRun
  Phase 2        → IndexVersion
  Phase 4        → GraphNode, GraphEdge
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DocumentType(str, Enum):
    PDF        = "pdf"
    DOCX       = "docx"
    HTML       = "html"
    PLAIN_TEXT = "plain_text"


class DocumentQuality(str, Enum):
    DIGITAL_TEXT = "digital_text"  # has extractable text layer
    SCANNED      = "scanned"       # image-only, needs OCR
    MIXED        = "mixed"         # some pages text, some scanned
    IMAGE_HEAVY  = "image_heavy"
    TABLE_HEAVY  = "table_heavy"
    ENCRYPTED    = "encrypted"     # reject with clear error
    CORRUPT      = "corrupt"       # reject with clear error


# ---------------------------------------------------------------------------
# Document — the only entity Phase 1 Day 1 needs
# ---------------------------------------------------------------------------

class Document(BaseModel):
    """
    Represents one uploaded file at one version.
    Immutable after creation. Updates produce a new Document
    with version incremented — never mutate the existing record.
    """
    id:               UUID          = Field(default_factory=uuid4)
    version:          int           = Field(default=1, ge=1)
    tenant_id:        UUID
    filename:         str
    doc_type:         DocumentType
    quality:          DocumentQuality
    raw_path:         str           # data/raw/{tenant_id}/{uuid}/{filename}
    uploaded_at:      datetime      = Field(default_factory=datetime.utcnow)
    is_active:        bool          = Field(default=True)

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# ExtractionRun — records what the pipeline did to a document
# ---------------------------------------------------------------------------

def _hash_config(config: dict) -> str:
    """Deterministic sha256 of a config dict. Order-independent."""
    serialised = json.dumps(config, sort_keys=True)
    return hashlib.sha256(serialised.encode()).hexdigest()


class ExtractionRun(BaseModel):
    """
    One extraction pass over one document version.
    Mutable — created at start, updated at completion.

    Separate from EmbeddingRun (added Phase 1 Day 6):
    changing the embedding model does not invalidate extraction results.
    """
    id:               UUID          = Field(default_factory=uuid4)
    document_id:      UUID
    document_version: int
    strategy:         str           # e.g. "layout_aware", "fast_text", "ocr_paddle"
    config_hash:      str           # sha256 — sealed record of exact config used
    started_at:       datetime      = Field(default_factory=datetime.utcnow)
    completed_at:     Optional[datetime] = None
    chunk_count:      Optional[int]      = None
    cost_usd:         Optional[float]    = Field(default=None, ge=0.0)
    success:          bool               = Field(default=False)

    model_config = {"frozen": False}

    @classmethod
    def start(
        cls,
        document: Document,
        strategy: str,
        config: dict,
    ) -> ExtractionRun:
        """
        Factory method — creates a run at the moment extraction begins.
        Usage:
            run = ExtractionRun.start(doc, "layout_aware", config_dict)
        """
        return cls(
            document_id=document.id,
            document_version=document.version,
            strategy=strategy,
            config_hash=_hash_config(config),
        )

    def complete(self, chunk_count: int, cost_usd: float) -> None:
        """Call this when extraction finishes successfully."""
        self.completed_at = datetime.utcnow()
        self.chunk_count  = chunk_count
        self.cost_usd     = cost_usd
        self.success      = True

    def fail(self) -> None:
        """Call this when extraction fails."""
        self.completed_at = datetime.utcnow()
        self.success      = False