from collections import Counter
import sys
from pathlib import Path
import fitz
import json
from collections import Counter

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
from ingestion.figures import extract_figures


for doc_name in ["apple_10k_2025.pdf", "who_global_report.pdf", "worldbank_mixed.pdf"]:
    figures = extract_figures(Path(f"data/raw/{doc_name}"), doc_id=doc_name.replace(".pdf",""))
    print(f"{doc_name}: {len(figures)} figures")
## uv run python scripts/smoke_test_detector.py