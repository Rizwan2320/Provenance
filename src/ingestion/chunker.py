# src/ingestion/chunker.py
"""
Text chunking — fixed-size baseline. Curriculum's own starting point
before comparing against recursive/semantic strategies. Attaches real
section_path from Day 5 hierarchy, not empty placeholders.
"""

from __future__ import annotations
from bisect import bisect_right

import tiktoken

from configurations.schema import Chunk, ContentType,Table, Figure
from ingestion.hierarchy import Heading

CHUNK_SIZE_TOKENS = 400   # curriculum baseline starting point
CHUNK_OVERLAP_TOKENS = 50

_encoding = tiktoken.get_encoding("cl100k_base")  # tokenizer choice — see LEARNINGS.md


def _build_section_lookup(headings: list[Heading]) -> list[tuple[int, list[str]]]:
    """
    Turns a flat heading list into (page, ancestor_path) breakpoints,
    sorted by page, so any page number can be mapped to its section path
    via binary search — O(log n), not a scan per chunk.
    """
    if not headings:
        return []

    sorted_headings = sorted(headings, key=lambda h: h.page_number)
    breakpoints = []
    stack: list[Heading] = []  # tracks current ancestor chain by level

    for h in sorted_headings:
        stack = [s for s in stack if s.level < h.level]
        stack.append(h)
        path = [s.text for s in stack]
        breakpoints.append((h.page_number, path))

    return breakpoints


def _section_path_for_page(page: int, breakpoints: list[tuple[int, list[str]]]) -> list[str]:
    if not breakpoints:
        return []
    pages = [bp[0] for bp in breakpoints]
    idx = bisect_right(pages, page) - 1
    if idx < 0:
        return []
    return breakpoints[idx][1]


def chunk_document(
    pages: list[tuple[int, str]],  # (page_number, text) — from extractor.py output
    headings: list[Heading],
    doc_id: str,
    version: int = 1,
) -> list[Chunk]:
    """
    Fixed-size token chunking with overlap. Section path attached per
    chunk based on which page it falls on.
    """
    breakpoints = _build_section_lookup(headings)

    # Flatten to (page_number, token) stream so chunk boundaries can
    # cross page breaks without losing which page each token came from.
    token_stream: list[tuple[int, int]] = []  # (page_number, token_id)
    for page_num, text in pages:
        tokens = _encoding.encode(text)
        token_stream.extend((page_num, t) for t in tokens)

    chunks = []
    i = 0
    chunk_index = 0
    step = CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS

    while i < len(token_stream):
        window = token_stream[i : i + CHUNK_SIZE_TOKENS]
        if not window:
            break

        token_ids = [t for _, t in window]
        content = _encoding.decode(token_ids)
        page_number = window[0][0]  # chunk's page = first token's page

        chunks.append(Chunk(
            id=f"{doc_id}-v{version}-chunk{chunk_index}",
            document_id=doc_id,
            document_version=version,
            chunk_index=chunk_index,
            total_chunks=-1,  # backfilled below
            content=content,
            content_type=ContentType.TEXT,
            token_count=len(token_ids),
            page_number=page_number,
            section_path=_section_path_for_page(page_number, breakpoints),
        ))
        chunk_index += 1
        i += step

    for c in chunks:
        object.__setattr__(c, "total_chunks", len(chunks))  # frozen model — set once, post-hoc

    return chunks
 


def chunk_tables(tables: list[Table], doc_id: str, headings: list, version: int = 1) -> list[Chunk]:
    """
    One chunk per table, content = nl_description (not raw rows).
    Rationale: bled-cell tables (Day 3) have corrupted structured data;
    the LLM description reads through that correctly — validated on
    page 27's products/services table.
    """
    breakpoints = _build_section_lookup(headings)
    chunks = []

    for i, t in enumerate(tables):
        if not t.nl_description:
            continue  # no description = not retrievable, skip rather than chunk empty content

        chunks.append(Chunk(
            id=f"{doc_id}-v{version}-tablechunk{i}",
            document_id=doc_id,
            document_version=version,
            chunk_index=i,
            total_chunks=-1,
            content=t.nl_description,
            content_type=ContentType.TABLE,
            token_count=len(_encoding.encode(t.nl_description)),
            page_number=t.page_number,
            section_path=_section_path_for_page(t.page_number, breakpoints),
            table_id=t.id,
        ))

    for c in chunks:
        object.__setattr__(c, "total_chunks", len(chunks))
    return chunks


def chunk_figures(figures: list[Figure], doc_id: str, headings: list[Heading], version: int = 1) -> list[Chunk]:
    """One chunk per figure, content = vision-generated description. Mirrors chunk_tables()."""
    breakpoints = _build_section_lookup(headings)
    chunks = []

    for i, f in enumerate(figures):
        if not f.description:
            continue  # no description = not retrievable, same rule as tables

        chunks.append(Chunk(
            id=f"{doc_id}-v{version}-figchunk{i}",
            document_id=doc_id,
            document_version=version,
            chunk_index=i,
            total_chunks=-1,
            content=f.description,
            content_type=ContentType.FIGURE,
            token_count=len(_encoding.encode(f.description)),
            page_number=f.page_number,
            section_path=_section_path_for_page(f.page_number, breakpoints),
            figure_id=f.id,
        ))

    for c in chunks:
        object.__setattr__(c, "total_chunks", len(chunks))
    return chunks        