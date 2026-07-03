import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ingestion.detector import detect
from ingestion.extractor import extract


result = detect(Path("data/raw/attention_is_all_you_need.pdf"))
extraction = extract(Path("data/raw/attention_is_all_you_need.pdf"), result.quality)
print(f"Pages extracted: {len(extraction.pages)}")
print(f"Total chars: {extraction.total_chars}")
print(f"Page 1 preview:\n{extraction.pages[4].text[:400]}")