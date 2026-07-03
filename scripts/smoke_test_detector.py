import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


from ingestion.ocr import extract_scanned


result = extract_scanned(Path("data/raw/camera_scan_test.pdf"))
for p in result.pages:
    print(f"Page {p.page_number} | confidence={p.confidence:.1f}")
    print(p.text[:300])