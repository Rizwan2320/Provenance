"""
First real test of retrieval: does a known question surface the chunk
that actually contains its answer? Uses one golden question with a
known page/content_type as a sanity check — not the full eval (file 5).
"""
from __future__ import annotations
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))



from configurations.config import get_settings
from retrieval.index import build_index, retrieve

DOC_ID = "apple10k"
FILENAME = "apple_10k_2025.pdf"

# apple10k-q1: answer is on page 32, "$416,161 million" total net sales
TEST_QUERY = "What was Apple's total net sales for fiscal year 2025?"


def main() -> None:
    settings = get_settings()
    file_path = settings.raw_dir / FILENAME

    index = build_index(file_path, doc_id=DOC_ID)
    print(f"Index built: {len(index.chunks)} chunks, vectors shape {index.vectors.shape}\n")

    results = retrieve(TEST_QUERY, index, top_k=5)

    print(f"Query: {TEST_QUERY!r}\n")
    for rank, r in enumerate(results, start=1):
        print(f"#{rank}  score={r.score:.4f}  page={r.chunk.page_number}  "
              f"type={r.chunk.content_type.value}  id={r.chunk.id}")
        print(f"    {r.chunk.content[:150]!r}")
        print()

    print("Expected: page 32 should appear near the top — it contains")
    print("'Total net sales $416,161' in the Consolidated Statements of Operations.")


if __name__ == "__main__":
    main()