# ADR-001: Split DocumentQuality from Content-Density Signals

## Context

DocumentQuality originally included IMAGE_HEAVY and TABLE_HEAVY as enum
values alongside DIGITAL_TEXT, SCANNED, MIXED, ENCRYPTED, CORRUPT.
These two groups answer different questions:

- Text-layer state: can I extract text without OCR? (mutually exclusive)
- Content density: how much of the page is tables/images? (independent)

A real document — e.g. a financial 10-K — can be DIGITAL_TEXT (perfect
text layer) AND table-heavy (dense tabular data) simultaneously. A single
enum cannot represent both. Whichever check ran last would silently
overwrite the other classification.

## Decision

DocumentQuality keeps only the mutually-exclusive text-layer states:
DIGITAL_TEXT, SCANNED, MIXED, ENCRYPTED, CORRUPT.

Content density becomes two independent boolean fields on
DetectionResult: is_table_heavy, is_image_heavy. Computed via
PyMuPDF's built-in page.find_tables() and page.get_image_info() —
no new dependency required.

## Consequences

- A document can be correctly described as both DIGITAL_TEXT and
  table_heavy — both facts survive.
- Extraction strategy selection in extractor.py can branch on text-layer
  state AND density independently (e.g. "digital + table-heavy" routes
  to a table-aware parser; "scanned + table-heavy" routes to OCR with
  table reconstruction).

* Schema is slightly less compact — two booleans instead of one enum
  value. Acceptable trade-off for correctness.
