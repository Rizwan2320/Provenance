"""
Index coverage check — is every non-whitespace character of every page inside
at least one text chunk? Free: re-extracts page text locally, zero LLM calls.

Prediction (written before running): holes exist, every hole follows a chunk
with token_count < 350, and none follows a chunk with token_count >= 350.
"""

from __future__ import annotations
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


from bisect import bisect_right

from configurations.config import get_settings
from ingestion.extractor import extract_digital
from retrieval.index import build_index

DOC_ID = "apple10k"
FILENAME = "apple_10k_2025.pdf"
STEP = 350  # CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS in chunker.py


def main() -> None:
    settings = get_settings()
    file_path = settings.raw_dir / FILENAME

    # evaluation_dir is added to sys.path at runtime, so static checkers
    # cannot resolve the module — suppress the false positive.
    sys.path.insert(0, str(settings.evaluation_dir.resolve()))
    from golden_set import GOLDEN_EXAMPLES  # type: ignore[import-not-found]

    # Page texts joined the same way the chunker streams tokens (no separators)
    pages = extract_digital(file_path).pages
    G = "".join(p.text for p in pages)
    page_start: dict[int, int] = {}
    offset = 0
    for p in pages:
        page_start[p.page_number] = offset
        offset += len(p.text)
    bounds = [(page_start[p.page_number], p.page_number) for p in pages]
    bound_starts = [b[0] for b in bounds]

    def page_at(pos: int) -> int:
        return bounds[max(0, bisect_right(bound_starts, pos) - 1)][1]

    index = build_index(file_path, doc_id=DOC_ID)  # cache hit: no LLM calls
    text_chunks = [c for c in index.chunks if c.content_type.value == "text"]

    # Locate each chunk's content in the page text (chunks are in order)
    located, unlocated, pos = [], 0, 0
    for c in text_chunks:
        at = G.find(c.content, pos)
        if at == -1:
            unlocated += 1
            continue
        located.append((at, at + len(c.content), c))
        pos = at

    merged: list[list[int]] = []
    for s, e, _ in sorted(located, key=lambda t: t[0]):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    edges = [0] + [x for m in merged for x in m] + [len(G)]
    holes = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)
             if G[edges[i]:edges[i + 1]].strip()]
    end_to_chunk = {e: c for _, e, c in located}
    lost = sum(b - a for a, b in holes)

    print(f"Text chunks located in page text: {len(located)}/{len(text_chunks)} "
          f"(unlocated: {unlocated} — if >0, results are approximate)")
    print(f"Page text: {len(G):,} chars | holes: {len(holes)} | "
          f"chars in holes: {lost:,} ({lost / len(G):.1%})\n")

    print("LARGEST HOLES")
    for a, b in sorted(holes, key=lambda h: h[1] - h[0], reverse=True)[:10]:
        prev = end_to_chunk.get(a)
        prev_txt = f"after chunk{prev.chunk_index} (token_count={prev.token_count})" if prev else "leading"
        print(f"  page {page_at(a):>2} @{a - page_start[page_at(a)]:>5}  {b - a:>5} chars  "
              f"{prev_txt}  starts: {G[a:a + 50]!r}")

    short_before = full_before = 0
    for a, _ in holes:
        prev = end_to_chunk.get(a)
        if prev is None:
            continue
        if prev.token_count < STEP:
            short_before += 1
        else:
            full_before += 1
    print(f"\nHoles after chunks with token_count < {STEP}: {short_before} | "
          f"after chunks >= {STEP}: {full_before}  (mechanism predicts the second is 0)")
    print(f"Text chunks with token_count < {STEP}: "
          f"{sum(c.token_count < STEP for c in text_chunks)}/{len(text_chunks)}")

    print("\nGOLDEN EVIDENCE SPANS")
    for ex in GOLDEN_EXAMPLES:
        for sp in ex.evidence_spans:
            a = page_start[sp.page] + sp.char_start
            b = page_start[sp.page] + sp.char_end
            one = any(s <= a and e >= b for s, e, _ in located)
            union = any(m0 <= a and m1 >= b for m0, m1 in merged)
            touch = any(s < b and e > a for s, e, _ in located)
            status = ("inside one chunk" if one else
                      "split across chunks (text fully indexed)" if union else
                      "PARTLY IN A HOLE" if touch else "IN A HOLE — NOT INDEXED")
            print(f"  {ex.id}  p{sp.page} [{sp.char_start}-{sp.char_end}]  {status}")


if __name__ == "__main__":
    main()