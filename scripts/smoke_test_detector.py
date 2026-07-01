# scripts/smoke_test_detector.py
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ingestion.detector import detect

# Replace with any PDF you have locally
result = detect(Path("data/raw/camera_scan_test.pdf"))

print(f"Quality    : {result.quality}")
print(f"Pages      : {result.page_count}")
print(f"Text ratio : {result.text_ratio:.2f}")
print(f"Notes      : {result.notes}")
if result.warnings:
    print(f"Warnings   : {result.warnings}")