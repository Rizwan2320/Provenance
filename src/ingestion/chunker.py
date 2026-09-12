"""
Text chunking — fixed-size baseline. Curriculum's own starting point
before comparing against recursive/semantic strategies. Attaches real
section_path from Day 5 hierarchy, not empty placeholders.
Also wires char_start / char_end (page-local offsets) for evidence spans.
"""

from __future__ import annotations
from bisect import bisect_right
import logging
import re

import tiktoken

from configurations.schema import Chunk, ContentType, Table, Figure
from ingestion.hierarchy import Heading

logger = logging.getLogger(__name__)

CHUNK_SIZE_TOKENS = 400   # curriculum baseline starting point
CHUNK_OVERLAP_TOKENS = 50

_encoding = tiktoken.get_encoding("cl100k_base")  # tokenizer choice — see LEARNINGS.md
_SENTENCE_END = re.compile(r'[.!?]\s')


def _snap_to_sentence_boundary(token_ids: list[int], target_end: int) -> tuple[list[int], str]:
    """
    Snap a proposed token cut to the latest sentence-ending punctuation.

    Returns (snapped_token_ids, snapped_text) so we never rely on
    encode/decode length matching the original token stream.
    This avoids the common tiktoken off-by-a-few-tokens problem that
    left residual text after the intended sentence boundary.
    """
    decoded = _encoding.decode(token_ids[:target_end])
    matches = list(_SENTENCE_END.finditer(decoded))

    if not matches:
        return token_ids[:target_end], decoded

    last_match_end = matches[-1].end()
    snapped_text = decoded[:last_match_end]
    snapped_token_ids = _encoding.encode(snapped_text)
    return snapped_token_ids, snapped_text


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
    Fixed-size token chunking with overlap.
    Section path + page-local char_start/char_end attached per chunk.
    """
    breakpoints = _build_section_lookup(headings)

    # Per-page token lists — needed to compute char offsets relative to
    # each page's own text, not a meaningless global position.
    page_tokens: dict[int, list[int]] = {}
    for page_num, text in pages:
        page_tokens[page_num] = _encoding.encode(text)

    # Flat stream: (page_number, token_id, local_index_within_that_page's_tokens)
    token_stream: list[tuple[int, int, int]] = []
    for page_num, tokens in page_tokens.items():
        token_stream.extend((page_num, t, i) for i, t in enumerate(tokens))

    chunks = []
    i = 0
    chunk_index = 0
    step = CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS

    while i < len(token_stream):
        raw_window = token_stream[i : i + CHUNK_SIZE_TOKENS]
        if not raw_window:
            break

        page_number = raw_window[0][0]
        local_start = raw_window[0][2]

        # Sentence-boundary snapping
        token_ids = [t for _, t, _ in raw_window]
        if i + CHUNK_SIZE_TOKENS < len(token_stream):
            token_ids, content = _snap_to_sentence_boundary(token_ids, len(token_ids))
            # Reconstruct the corresponding window slice (may be shorter)
            window = raw_window[:len(token_ids)]
        else:
            content = _encoding.decode(token_ids)
            window = raw_window

        # char_start: offset into page_number's own text where this chunk begins
        char_start = len(_encoding.decode(page_tokens[page_number][:local_start]))

        # Tokens in this window that actually belong to page_number (contiguous prefix)
        same_page_run = [t for p, t, _ in window if p == page_number]
        char_end = char_start + len(_encoding.decode(same_page_run))

        if len(same_page_run) < len(window):
            logger.warning(
                "Chunk %s spans pages %s->%s; char_end reflects page %s only.",
                chunk_index, page_number, window[-1][0], page_number,
            )

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
            char_start=char_start,
            char_end=char_end,
            section_path=_section_path_for_page(page_number, breakpoints),
        ))
        chunk_index += 1
        i += max(step, len(token_ids) - CHUNK_OVERLAP_TOKENS)

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
            char_start=0,
            char_end=len(t.nl_description),
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
            char_start=0,
            char_end=len(f.description),
            section_path=_section_path_for_page(f.page_number, breakpoints),
            figure_id=f.id,
        ))

    for c in chunks:
        object.__setattr__(c, "total_chunks", len(chunks))
    return chunks