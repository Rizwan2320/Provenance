
from __future__ import annotations
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


"""One-time: recover paid-for table descriptions from the existing chunks.json."""
import json
from configurations.config import get_settings
from ingestion.pipeline import table_hash
from ingestion.tables import extract_tables

DOC_ID, FILENAME = "apple10k", "apple_10k_2025.pdf"


def main() -> None:
    s = get_settings()
    old = json.loads((s.processed_dir / DOC_ID / "chunks.json").read_text(encoding="utf-8"))
    by_table = {c["table_id"]: c for c in old if c["content_type"] == "table"}

    tables = extract_tables(s.raw_dir / FILENAME, DOC_ID)  # local, free
    cache = {}
    for t in tables:
        c = by_table.get(t.id)
        if c and c["page_number"] == t.page_number:  # identity sanity check
            cache[table_hash(t)] = {"description": c["content"]}

    path = s.processed_dir / DOC_ID / "table_descriptions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    print(f"Seeded {len(cache)}/{len(tables)} -> {path}")
    print("Not seeded (pipeline will retry):", [
        t.id for t in tables if table_hash(t) not in cache
    ])


if __name__ == "__main__":
    main()