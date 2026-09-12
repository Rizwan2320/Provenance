"""
Test: Chunk-ID stability vs Evidence-span stability
when the chunker is tuned (CHUNK_SIZE_TOKENS changes).

This demonstrates why evidence spans (page + char_start/char_end)
are more robust ground-truth references than raw chunk IDs.
"""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ingestion.hierarchy import extract_hierarchy
from ingestion.chunker import chunk_document
from ingestion.extractor import extract_digital
import ingestion.chunker as chunker_module


def main():
    result = extract_digital(Path("data/raw/apple_10k_2025.pdf"))
    pages = [(p.page_number, p.text) for p in result.pages]
    headings = extract_hierarchy(Path("data/raw/apple_10k_2025.pdf"), doc_id="apple10k")

    # ------------------------------------------------------------------
    # 1. Chunk-ID approach — does "chunk 17" still mean the same thing?
    # ------------------------------------------------------------------
    print("=" * 70)
    print("CHUNK-ID STABILITY TEST")
    print("=" * 70)

    # Run with current default (400)
    original_size = chunker_module.CHUNK_SIZE_TOKENS
    print(f"\nRunning with CHUNK_SIZE_TOKENS = {original_size}")
    chunks_v1 = chunk_document(pages, headings, doc_id="apple10k")

    # Temporarily change to 350 and re-run
    chunker_module.CHUNK_SIZE_TOKENS = 350
    print(f"Running with CHUNK_SIZE_TOKENS = {chunker_module.CHUNK_SIZE_TOKENS}")
    chunks_v2 = chunk_document(pages, headings, doc_id="apple10k")

    # Restore original value
    chunker_module.CHUNK_SIZE_TOKENS = original_size

    print(f"\nTotal chunks (size=400): {len(chunks_v1)}")
    print(f"Total chunks (size=350): {len(chunks_v2)}")

    print(f"\nchunk 17 (size=400) starts with:")
    print(f"  {chunks_v1[17].content[:90]!r}")

    print(f"\nchunk 17 (size=350) starts with:")
    print(f"  {chunks_v2[17].content[:90]!r}")

    print("\n→ Chunk IDs are unstable. Changing CHUNK_SIZE_TOKENS reshuffles")
    print("  what 'chunk 17' points to. Any ground-truth that stores only a")
    print("  chunk_id becomes invalid after a routine chunker tuning.")

    # ------------------------------------------------------------------
    # 2. Evidence-span approach — does page + char_start/char_end stay stable?
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EVIDENCE-SPAN STABILITY TEST")
    print("=" * 70)

    # Pick a real span from the size=400 run (chunk 17)
    ref_chunk = chunks_v1[17]
    page_num = ref_chunk.page_number
    char_start = ref_chunk.char_start
    char_end = ref_chunk.char_end

    page_text = next(t for p, t in pages if p == page_num)

    print(f"\nReference taken from chunks_v1[17]:")
    print(f"  page        = {page_num}")
    print(f"  char_start  = {char_start}")
    print(f"  char_end    = {char_end}")

    extracted = page_text[char_start:char_end]
    print(f"\nText at that span (from original page text):")
    print(f"  {extracted[:90]!r}")

    print(f"\nSame span still extracts correctly after we changed CHUNK_SIZE_TOKENS:")
    print(f"  {page_text[char_start:char_start+90]!r}")

    print("\n→ Evidence spans (page + char_start/char_end) are independent of")
    print("  chunking parameters. They remain valid even when the chunker is")
    print("  retuned, because they point into the stable page text itself.")

    # ------------------------------------------------------------------
    # 3. Quick sanity: char offsets still line up with content
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CHAR OFFSET SANITY (chunks 15-17, size=400)")
    print("=" * 70)

    for c in chunks_v1[15:18]:
        page_text = next(t for p, t in pages if p == c.page_number)
        extracted = page_text[c.char_start:c.char_end]

        print(f"\nchunk {c.chunk_index}: page={c.page_number}  "
              f"char_start={c.char_start}  char_end={c.char_end}")
        print(f"  extracted : {extracted[:70]!r}")
        print(f"  content   : {c.content[:70]!r}")
        print(f"  ends with : {c.content[-50:]!r}")


if __name__ == "__main__":
    main()