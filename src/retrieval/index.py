"""
Brute-force cosine retrieval over the cached, embedded chunk pool.

One index for text + table + figure chunks together — content_type is
kept as metadata on each chunk, not split into separate indexes. See
LEARNINGS.md for why this is plain numpy rather than a vector DB or a
similarity library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from configurations.provider import embed_texts
from configurations.schema import Chunk
from ingestion.pipeline import run_pipeline


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float


@dataclass
class ChunkIndex:
    """
    Chunks and their embeddings in matched order. Rebuilding this per
    process is cheap once ingestion has already run — it's just two
    JSON reads via run_pipeline()'s cache-hit path, zero LLM calls.
    """
    chunks: list[Chunk]
    vectors: np.ndarray  # shape (n_chunks, embedding_dim)


def build_index(file_path: Path, doc_id: str, version: int = 1) -> ChunkIndex:
    """Loads (or builds, on first call) chunks + embeddings for one document."""
    chunks, embeddings = run_pipeline(file_path, doc_id=doc_id, version=version)
    vectors = np.array([embeddings[c.id] for c in chunks], dtype=np.float32)
    return ChunkIndex(chunks=chunks, vectors=vectors)


def retrieve(
    query: str,
    index: ChunkIndex,
    top_k: int = 5,
    security_context: dict | None = None,  # no-op stub — see Phase 0 reconciliation
) -> list[RetrievedChunk]:
    """
    Embeds the query and returns the top_k chunks by cosine similarity,
    ranked across all content types together.
    """
    query_vector = np.array(embed_texts([query])[0], dtype=np.float32)

    chunk_norms = np.linalg.norm(index.vectors, axis=1)
    query_norm = np.linalg.norm(query_vector)
    # Guard divide-by-zero — shouldn't happen with real embeddings, but
    # a silent NaN here would be a miserable thing to debug downstream.
    chunk_norms = np.where(chunk_norms == 0, 1e-10, chunk_norms)
    query_norm = query_norm if query_norm != 0 else 1e-10

    similarities = (index.vectors @ query_vector) / (chunk_norms * query_norm)
    top_indices = np.argsort(-similarities)[:top_k]

    return [
        RetrievedChunk(chunk=index.chunks[i], score=float(similarities[i]))
        for i in top_indices
    ]