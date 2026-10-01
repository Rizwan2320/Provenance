"""
Single orchestration entrypoint: raw PDF -> cached, embedded chunks.

Rule: if data/processed/{doc_id}/chunks.json exists, it is trusted and
loaded instead of recomputed. Table/figure description generation costs
real LLM quota and the underlying document doesn't change between runs
at this stage of the project. Delete the cache directory manually to
force a full recompute, or pass force=True.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from configurations.config import get_settings
from configurations.provider import embed_texts
from configurations.schema import Chunk

from ingestion.detector import detect
from ingestion.extractor import extract
from ingestion.hierarchy import extract_hierarchy
from ingestion.tables import extract_tables, generate_table_description
from ingestion.figures import extract_figures, generate_figure_description
from ingestion.chunker import chunk_document, chunk_tables, chunk_figures

logger = logging.getLogger(__name__)


def _chunks_path(doc_id: str) -> Path:
    return get_settings().processed_dir / doc_id / "chunks.json"


def _embeddings_path(doc_id: str) -> Path:
    return get_settings().processed_dir / doc_id / "embeddings.json"


def _load_cached(doc_id: str) -> tuple[list[Chunk], dict[str, list[float]]] | None:
    chunks_path = _chunks_path(doc_id)
    embeddings_path = _embeddings_path(doc_id)
    if not (chunks_path.exists() and embeddings_path.exists()):
        return None

    chunks = [Chunk.model_validate(c) for c in json.loads(chunks_path.read_text(encoding="utf-8"))]
    embeddings = json.loads(embeddings_path.read_text(encoding="utf-8"))

    logger.info("Loaded %d cached chunks for %s — skipping full pipeline.", len(chunks), doc_id)
    return chunks, embeddings


def _save_cache(doc_id: str, chunks: list[Chunk], embeddings: dict[str, list[float]]) -> None:
    chunks_path = _chunks_path(doc_id)
    chunks_path.parent.mkdir(parents=True, exist_ok=True)

    chunks_path.write_text(
        json.dumps([c.model_dump(mode="json") for c in chunks], indent=2),
        encoding="utf-8",
    )
    _embeddings_path(doc_id).write_text(json.dumps(embeddings), encoding="utf-8")

    logger.info("Cached %d chunks + embeddings for %s at %s", len(chunks), doc_id, chunks_path.parent)


def run_pipeline(
    file_path: Path,
    doc_id: str,
    version: int = 1,
    force: bool = False,
) -> tuple[list[Chunk], dict[str, list[float]]]:
    """
    Full ingestion pipeline for one document. Returns (chunks, embeddings),
    where embeddings is {chunk.id: vector} — kept separate from Chunk
    itself since an embedding is the output of one embedding-model run,
    not an intrinsic property of the chunk. See LEARNINGS.md.
    """
    if not force:
        cached = _load_cached(doc_id)
        if cached is not None:
            return cached

    logger.info("No cache found for %s — running full pipeline. This will call the LLM.", doc_id)

    # 1. Quality detection
    detection = detect(file_path)
    logger.info("Detected %s: %s", doc_id, detection.notes)

    # 2. Text extraction — routes internally on detection.quality
    extraction_result = extract(file_path, doc_id, detection.quality)
    pages: list[tuple[int, str]] = [(p.page_number, p.text) for p in extraction_result.pages]

    # 3. Section hierarchy — TOC-first, ground truth when present
    headings = extract_hierarchy(file_path, doc_id)

    # 4. Tables — extraction is free, descriptions cost LLM calls
    tables = extract_tables(file_path, doc_id, version=version)
    for table in tables:
        table.nl_description = generate_table_description(table)
        if table.nl_description is None:
            logger.warning("No description for %s — will be skipped at chunking (known gap for table3).", table.id)

    # 5. Figures — same pattern, no GLM fallback on this path yet (see FAILURES.md)
    figures = extract_figures(file_path, doc_id, version=version)
    for figure in figures:
        figure.description = generate_figure_description(figure)
        if figure.description is None:
            logger.warning("No description for %s — will be skipped at chunking.", figure.id)

    # 6. Chunk all three content types into one flat pool
    text_chunks = chunk_document(pages, headings, doc_id, version=version)
    table_chunks = chunk_tables(tables, doc_id, headings, version=version)
    figure_chunks = chunk_figures(figures, doc_id, headings, version=version)
    all_chunks = text_chunks + table_chunks + figure_chunks

    logger.info(
        "%s: %d text + %d table + %d figure = %d total chunks",
        doc_id, len(text_chunks), len(table_chunks), len(figure_chunks), len(all_chunks),
    )

    # 7. Embed everything in one batch call
    vectors = embed_texts([c.content for c in all_chunks])
    embeddings = {c.id: v for c, v in zip(all_chunks, vectors)}

    _save_cache(doc_id, all_chunks, embeddings)
    return all_chunks, embeddings