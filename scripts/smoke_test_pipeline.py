"""
First end-to-end run of run_pipeline() against the real Apple 10-K.

Makes live LLM calls on first run (up to 12 table description calls,
0 figure calls expected for this document — see below). After success,
chunks.json + embeddings.json are cached under data/processed/apple10k/;
rerunning this script should skip the LLM entirely.

DOC_ID must stay exactly "apple10k" — golden_set.py references table
IDs built from this string (e.g. "apple10k-v1-table2"). Changing it
breaks every TABLE-type golden example.
"""
from __future__ import annotations
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


import logging
from configurations.config import get_settings
from ingestion.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DOC_ID = "apple10k"          # must match golden_set.py — do not change
VERSION = 1
FILENAME = "apple_10k_2025.pdf"


def main() -> None:
    settings = get_settings()
    file_path = settings.raw_dir / FILENAME

    if not file_path.exists():
        print(f"FAIL: expected file at {file_path}, not found.")
        print("Fix FILENAME/raw_dir before continuing — don't guess past this point.")
        sys.exit(1)

    print(f"Running pipeline on {file_path} (doc_id={DOC_ID!r})...")
    print("First run: expect live LLM calls, can take a few minutes.\n")

    chunks, embeddings = run_pipeline(file_path, doc_id=DOC_ID, version=VERSION)

    by_type: dict[str, int] = {}
    for c in chunks:
        by_type[c.content_type.value] = by_type.get(c.content_type.value, 0) + 1

    table_chunks = [c for c in chunks if c.content_type.value == "table"]
    figure_chunks = [c for c in chunks if c.content_type.value == "figure"]
    text_count = by_type.get("text", 0)

    print("=" * 60)
    print(f"TOTAL CHUNKS: {len(chunks)}  (by type: {by_type})")
    print()
    print(f"TEXT CHUNKS: {text_count}")
    print("  Prior measurement (Day 6): 183. Should be in this neighborhood —")
    print("  large deviation means extraction or hierarchy changed something.")
    print()
    print(f"TABLE CHUNKS: {len(table_chunks)}")
    print("  Expected: 11 of 12 candidates (table3 known to fail description, see FAILURES.md)")
    if any(c.table_id and "table3" in c.table_id for c in table_chunks):
        print("  NOTE: table3 got a description this run — gap may be resolved, or model/quota changed.")
    else:
        print("  OK: table3 absent, as expected.")
    print()
    print(f"FIGURE CHUNKS: {len(figure_chunks)}")
    print("  Expected: 0 for this document — Apple's charts are vector-drawn,")
    print("  invisible to the current raster-only extractor (logged gap, not a bug).")
    print()

    dims = {len(v) for v in embeddings.values()}
    print(f"EMBEDDING DIMS SEEN: {dims}  (settings expects {settings.embedding_dimension})")
    if dims != {settings.embedding_dimension}:
        print("  WARNING: dimension mismatch — check embedding_model_name in .env")

    print()
    print(f"Cache written to: {settings.processed_dir / DOC_ID}")
    print("Run this script again now — it should log 'Loaded cached chunks' and make zero LLM calls.")
    print("=" * 60)


if __name__ == "__main__":
    main()