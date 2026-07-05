import sys
from pathlib import Path
import fitz


repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from ingestion.detector import TEXT_CHARS_PER_PAGE
from ingestion.ocr import _ocr_page    


# Use any real digital PDF
doc = fitz.open("data/raw/attention_is_all_you_need.pdf")
page = doc[0]

real_text = page.get_text("text", sort=True).strip()
print(f"Real text length: {len(real_text)}")  # should be well above threshold

# Now simulate what extract_mixed does when text is missing
fake_empty = ""
if len(fake_empty) < TEXT_CHARS_PER_PAGE:
    ocr_text, conf = _ocr_page(page)
    print(f"OCR fallback fired. Confidence: {conf:.1f}")
    print(ocr_text[:200])

## uv run python scripts/smoke_test_detector.py