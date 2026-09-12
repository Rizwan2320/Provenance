import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ingestion.hierarchy import extract_hierarchy
from ingestion.chunker import chunk_document
from ingestion.extractor import extract_digital


result = extract_digital(Path("data/raw/apple_10k_2025.pdf"))
pages = [(p.page_number, p.text) for p in result.pages]
headings = extract_hierarchy(Path("data/raw/apple_10k_2025.pdf"), doc_id="apple10k")

chunks = chunk_document(pages, headings, doc_id="apple10k")

print("=== char_start / char_end sanity check (chunks 15-17) ===\n")
for c in chunks[15:18]:
    page_text = next(t for p, t in pages if p == c.page_number)
    extracted = page_text[c.char_start:c.char_end]

    print(f"chunk {c.chunk_index}: page={c.page_number}  char_start={c.char_start}  char_end={c.char_end}")
    print(f"  extracted from page text : {extracted[:70]!r}")
    print(f"  actual chunk content     : {c.content[:70]!r}")
    print(f"  ends with                : {c.content[-60:]!r}")
    print()

## uv run python scripts/smoke_test_detector.py

## .\.venv\Scripts\Activate.ps1        