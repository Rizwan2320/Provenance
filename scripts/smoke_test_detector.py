from collections import Counter
import sys
from pathlib import Path
from tkinter import Image
import fitz
import json
from collections import Counter

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from PIL import Image
from ingestion.figures import extract_figures, generate_figure_description



figures = extract_figures(Path("data/raw/who_global_report.pdf"), doc_id="who")
for f in figures:
    desc = generate_figure_description(f)
    if desc is None:
        print(f"[{f.id}] page={f.page_number} — FAILED\n")
    else:
        print(f"[{f.id}] page={f.page_number}\n{desc}\n")
## uv run python scripts/smoke_test_detector.py