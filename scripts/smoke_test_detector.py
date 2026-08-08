import sys
from pathlib import Path
from typing import Any, cast

import fitz

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))



from ingestion.extractor import extract_digital
from ingestion.entities import extract_entities

result = extract_digital(Path("data/raw/apple_10k_2025.pdf"))
full_text = "\n".join(p.text for p in result.pages[:10])  # first 10 pages, keep it fast

entities = extract_entities(full_text, doc_id="apple10k")
print(f"{len(entities)} canonical entities found\n")
for e in sorted(entities, key=lambda x: -x.mention_count)[:20]:
    print(f"type={e.entity_type.value} count={e.mention_count} name={e.canonical_name!r} aliases={e.aliases[:3]}")
## uv run python scripts/smoke_test_detector.py