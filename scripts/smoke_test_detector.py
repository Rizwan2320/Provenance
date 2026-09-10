


import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from pathlib import Path
from ingestion.hierarchy import extract_hierarchy
from ingestion.figures import extract_figures, generate_figure_description
from ingestion.chunker import chunk_figures

file_path = Path("data/raw/who_global_report.pdf")
headings = extract_hierarchy(file_path, doc_id="who")
figures = extract_figures(file_path, doc_id="who")

for f in figures:
    f.description = generate_figure_description(f)

figure_chunks = chunk_figures(figures, doc_id="who", headings=headings)
print(f"{len(figure_chunks)} figure chunks created (of {len(figures)} figures)\n")
for c in figure_chunks:
    print(f"page={c.page_number} section_path={c.section_path}")
    print(f"content: {c.content[:120]!r}\n")
## uv run python scripts/smoke_test_detector.py

## .\.venv\Scripts\Activate.ps1