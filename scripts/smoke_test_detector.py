import sys
from pathlib import Path
from typing import Any, cast

import fitz

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))



from ingestion.hierarchy import extract_hierarchy

headings = extract_hierarchy(Path("data/raw/worldbank_mixed.pdf"), doc_id="worldbank")
for h in headings[:20]:
    print(f"level={h.level} page={h.page_number} title={h.text!r}")
## uv run python scripts/smoke_test_detector.py