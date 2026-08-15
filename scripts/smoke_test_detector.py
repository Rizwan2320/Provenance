import sys
from pathlib import Path
from typing import Any, cast

import fitz

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))



from ingestion.extractor import extract_digital
from ingestion.hierarchy import extract_hierarchy
from ingestion.chunker import chunk_document

file_path = Path("data/raw/apple_10k_2025.pdf")
result = extract_digital(file_path)
pages = [(p.page_number, p.text) for p in result.pages]
headings = extract_hierarchy(file_path, doc_id="apple10k")

chunks = chunk_document(pages, headings, doc_id="apple10k")
print(f"{len(chunks)} chunks created\n")

# Spot-check a chunk we know should land inside Item 1A Risk Factors (starts page 8)
for c in chunks:
    if c.page_number == 9:
        print(f"chunk_index={c.chunk_index} page={c.page_number} tokens={c.token_count}")
        print(f"section_path={c.section_path}")
        print(f"content preview: {c.content[:150]!r}\n")
        break

for c in chunks:
    if c.chunk_index == 17:
        print(f"chunk 17 end:   ...{c.content[-150:]!r}")
    if c.chunk_index == 18:
        print(f"chunk 18 start: {c.content[:150]!r}...")   
## uv run python scripts/smoke_test_detector.py