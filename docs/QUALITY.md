# QUALITY.md — Ingestion Pipeline Baseline (end of Phase 1, Day 5)

## Document quality detection

Validated on 6 documents across DIGITAL_TEXT, SCANNED, MIXED — all
confirmed via real evidence (direct text inspection, OCR fingerprints),
not assumption. No known false classifications in current corpus.

## OCR

Good scans: 92-94% confidence. Bad scan (deliberate): 51.2%.
needs_review threshold: 70.0 — set from this real data spread, not guessed.

## Table extraction

Precision: 58% (7/12 candidates real, measured on Apple 10-K).
Recall: ~19% (7 of ~37 real tables found).
Three tool alternatives tested and rejected — see TRADEOFFS.md.
Known gap: dense financial tables without ruled lines are largely
invisible to current detection.

## Figure extraction

Raster figures: validated 0/3/0 across three document quality classes.
Descriptions: 3/3 accurate on manual verification against source images.
Known gap: vector-drawn charts (e.g. Apple's stock performance graph)
undetectable by current raster-only method.

## Section hierarchy

4/4 corpus documents resolved via native PDF outline (ground truth).
Heuristic fallback built, zero real-world validation — no outline-
less document in corpus yet.

## Entity extraction

116 canonical entities from Apple 10-K sample (in-document dedup only).
Known gap: no cross-mention coreference — "Company," "Registrant,"
"Apple Inc." remain separate entities. Concrete Phase 4 test case.

## Overall

No end-to-end retrieval quality measurement yet. All numbers above
are component-level, measured in isolation. Day 7 golden dataset +
RAGAS is the first point where "is this good enough" gets a real,
end-to-end answer rather than a per-stage guess.

## Golden dataset (minimal, Day 7 checkpoint)

9 examples, single document (Apple 10-K), all evidence-verified against
real extracted text — zero guessed spans, several caught and corrected
mid-construction (page-index mismatches, curly-quote mismatches, bare-
number disambiguation). Coverage: FACTUAL (5), TABLE (2), MULTI_SECTION
(1), UNANSWERABLE (1). Deliberately targets known fragile points:
Q2/Q7 hit the measured 38% cross-page-chunk boundary; Q4 hits the Day 3
bled-cell table; Q1/Q5/Q6/Q9 each surfaced a real page-indexing or
text-matching gotcha during construction, now documented in LEARNINGS.md.

Known limitation: 9 examples cannot support statistically meaningful
per-category metrics — this set answers "does the pipeline work at
all," not "how well." Full 100+ example set with splits remains deferred
per the original engineering-grade-first decision.
