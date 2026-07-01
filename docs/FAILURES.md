# FAILURES.md

> Every failure is logged here before it's fixed.
> Pattern: What broke → Why → How fixed → What it taught.

---

## Phase 0 — Baseline

No failures during Phase 0.
Both providers initialised successfully on first smoke test run.

Noted for Phase 1:

- Groq-style rate limits may appear on AgentRouter under heavy
  contextual chunking load. If 429s appear, log here first.
- HuggingFace anonymous download rate limit is a risk if model
  cache is cleared and re-downloaded repeatedly in CI.

## Phase 1 — detector.py: false assumption about test corpus

What broke: All 5 test documents classified DIGITAL_TEXT, including
archive_historical.pdf, which was selected specifically to represent
the SCANNED case.

Why: Internet Archive's PDF derivatives embed an invisible OCR text
layer on top of scanned page images. The document is visually scanned
but has a real, extractable text layer — text_ratio=1.00 is the
correct output, not a bug. "Originated from a scan" and "has no text
layer" are different properties; the test corpus conflated them.

Fix: Detector logic is unchanged — it correctly answers "is OCR
needed," not "was this scanned." Need a genuine no-text-layer
document (camera photo → PDF via img2pdf, no OCR step) to actually
exercise the SCANNED branch, which has zero verified passes so far.

What it taught: A test document chosen by provenance ("this came
from a scan") doesn't guarantee the property under test ("has no
text layer"). Verify the actual property, not the source's reputation
for having that property.

Confirmed via direct text inspection: page 10 shows inconsistent OCR
spelling of the same proper noun ("Wether" vs "Weiher" four words
apart) and mid-word line-break fractures ("Secreta[ry]", "I n hi[s]").
Both are textbook OCR artifacts, not extraction or detector bugs.
Hypothesis confirmed with evidence, not assumed.

Fixed: is_image_heavy now gated on text_ratio > SCANNED_THRESHOLD.
Verified: camera_scan_test.pdf (text_ratio=0.00) no longer flags
image_heavy. worldbank_mixed.pdf (text_ratio=1.00, real embedded
images) still correctly flags image_heavy. Both branches of the
detector now validated against real documents.
