import sys
from pathlib import Path
import fitz
import json

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


from ingestion.tables import extract_tables, generate_table_description

tables = extract_tables(Path("data/raw/apple_10k_2025.pdf"), doc_id="apple10k")
for t in tables:
    desc = generate_table_description(t)
    print(f"[{t.id}] page={t.page_number}\n{desc}\n")
## uv run python scripts/smoke_test_detector.py