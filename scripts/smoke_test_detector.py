import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


from ingestion.extractor import save_page_images



paths = save_page_images(Path("data/raw/attention_is_all_you_need.pdf"), "test_doc_1")
print(f"{len(paths)} images saved")
print(paths[0])