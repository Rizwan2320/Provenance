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

## Confirmed via direct text inspection: page 10 shows inconsistent OCR

spelling of the same proper noun ("Wether" vs "Weiher" four words
apart) and mid-word line-break fractures ("Secreta[ry]", "I n hi[s]").
Both are textbook OCR artifacts, not extraction or detector bugs.
Hypothesis confirmed with evidence, not assumed.

## Fixed: is_image_heavy now gated on text_ratio > SCANNED_THRESHOLD.

Verified: camera_scan_test.pdf (text_ratio=0.00) no longer flags
image_heavy. worldbank_mixed.pdf (text_ratio=1.00, real embedded
images) still correctly flags image_heavy. Both branches of the
detector now validated against real documents.

## ## Phase 1 — OCR confidence threshold, set from real data

What: Bad scan (blurry/angled photo) → confidence=51.2, text unusable garbage.
Good scans → confidence 92.1, 94.3, text readable with minor errors.

Fix: needs_review flag added, threshold=70.0 — set between the two
observed clusters, not guessed. Will refine with more samples in
Phase 1 Day 7 evaluation.

## ## Phase 1 Day 3 — Table detection: two distinct failure modes found

1. TOC false positives: text with page-number columns misdetected as
   tables. Fixed — zero-data-row filter (table has header, no rows
   below it → not a real table).

2. Row/column alignment failure on real financial tables: first-row
   assumed as header is wrong for statements without a clean header
   row; multi-value cells (e.g. "75.4% 73.9% 70.8%") bleed into one
   column instead of three. NOT fixed — this is the row/column
   alignment metric the curriculum requires measuring. Needs real
   measurement against ~10 tables before deciding a fix, not a guess.

## Phase 1 Day 3 — Table detection precision: 67% (8/12), measured

Two cheap filters (zero-data-row, prose-density) removed the majority
of false positives (62→12 tables). Remaining 4 false positives are
TOC entries and prose sentences that structurally resemble tables —
short-ish cells arranged in rows. A third heuristic filter was
considered and rejected: any rule tight enough to catch these would
be tuned against this single document's specific text patterns and
risks rejecting real tables in other documents. Decision: stop
heuristic iteration, log 67% as the measured baseline, revisit only
if Day 7 evaluation shows table precision materially hurting
end-to-end answer quality.

True positives still have a separate, unfixed problem: column bleed
on tables without a clean header row (page 27, 34, 46-51) — logged
separately, needs real fix not a filter.

## Phase 1 Day 3 — Table NL description: silent omission, not hallucination

Initial suspicion: Table 5 (p46) description contained numbers not
seen in truncated rows[:5] inspection — flagged as possible hallucination.
Verified against full raw data: all numbers were real, just in rows[2:5]
which hadn't been inspected. Grounding check cleared it correctly —
false alarm caught before it became a false conclusion.

Real finding underneath: row 6 contains a "Total proceeds/(repayments),
net" figure ($2,032) that differs from the header row's line-item
figure ($5,820) — both are legitimate but represent different things.
Row 6's number is buried in one unparsed bled string. The LLM's
description never surfaced the actual bottom-line total — it silently
omitted rather than invented. This is arguably higher-risk than
hallucination: a confident-sounding, partially-correct summary with
no signal that something's missing.

Decision: table NL descriptions are not yet safe to trust as complete.
Needed before Phase 2 relies on them: send the LLM the FULL row set
(not rows[:5]), and add a lightweight grounding check — verify that
key numeric values appearing in raw rows also appear in the generated
description, flag for review if not.

## Phase 1 Day 3 — Table detection RECALL, not just precision, measured

Manual count of the full Apple 10-K: ~37 real financial tables exist.
Detection found 12 candidates, 7 confirmed real after filtering →
precision 58% (corrected from earlier 67% — one entry misjudged as
borderline was actually a repeated TOC index, same pattern as the
first false positive).

Recall: 7/37 ≈ 19%. This is the dominant problem, not precision.
Three rounds of filtering improved trust in what was found, but never
addressed the ~30 real tables never detected at all — including the
core Income Statement, all Note 7 tax tables, both lease tables, and
RSU activity. Root cause suspected: PyMuPDF's default find_tables()
line-detection heuristic doesn't match dense financial-statement
layouts. Testing alternate strategy parameter before deciding on a
structural fix.

## Phase 1 Day 3 — text-strategy fallback rejected, spike-testing docling

Added lines→text fallback to improve recall (12→69 tables). Result:
catastrophic precision collapse — nearly every prose paragraph on
pages 1-19 misdetected as a table. Root cause: text strategy
fragments words across cell boundaries under justified-text spacing,
defeating the existing prose-density filter (built for the opposite
failure mode — long text in one cell, not short fragments in many).

Decision: reverted to lines-only (validated baseline: 12 candidates,
58% precision, ~19% recall). Heuristic patching has hit diminishing
returns — each fix reopens a different failure mode. Spike-testing
Docling (layout-model-based table detection) as a bounded experiment
before committing to a tool swap.

## Phase 1 Day 3 — Docling spike: rejected

Tested docling as alternative to PyMuPDF for table recall (19% baseline).
Result: crashed with std::bad_alloc on 68/80 pages, took 20 minutes,
and the single table successfully extracted was a false positive
(TOC entry) already correctly filtered by existing PyMuPDF heuristics.

Decision: reject. Not a viable tool on current hardware, and did not
demonstrate better accuracy even on the pages it processed. Reverting
fully to PyMuPDF lines-only baseline. Recall gap (19%) logged as a
known limitation, not fixed — revisit only if Day 7 end-to-end eval
shows table quality materially hurting answer accuracy. At that point,
the right next experiment is likely an LLM-based table verification/
extraction pass on flagged low-confidence pages, not a heavier local tool.

## Phase 1 Day 3 — Table extraction tooling: three approaches tried, all rejected

1. PyMuPDF `text` strategy fallback — reopened prose false positives worse than baseline (69 tables, mostly noise).
2. Docling — crashed (std::bad_alloc, 68/80 pages) due to GPU-oriented vision pipeline on OCR'd digital text.
3. PyMuPDF-Layout — despite being CPU-only and vector-based in principle, fell back to OCR on a small embedded
   image and broke, returning 0 tables (worse than baseline).

Decision: stop tool-shopping. FINAL Day 3 baseline: PyMuPDF lines-only
strategy + zero-row + prose-density filters. Precision 58% (7/12),
recall ~19% (7/~37). Documented, not fixed further. Revisit only with
Day 7 eval evidence that table quality measurably hurts answer
accuracy — and if so, the next real candidate is an LLM-based
verification pass on low-confidence pages, not another local tool.

## Phase 1 Day 3 — Deliberate failure exercises

1. MERGED/BLED CELLS — confirmed, real example: page 27 (products/
   services gross margin). Raw extraction crammed 3 values into one
   cell ('Services 75.4% 73.9% 70.8%'). Structural extraction is
   broken here — the Table object's rows/headers are wrong. However,
   the LLM description step correctly disentangled the values because
   it reasons over meaning, not cell boundaries. Net effect: the
   _structured_ JSON is unreliable for this table, but the _NL
   description_ used for retrieval is accurate. Numeric lookups
   against table.rows directly would be wrong; retrieval via
   description would not.

2. TABLE-AS-IMAGE — NOT TESTED. No confirmed example in current
   corpus. Would need to source or fabricate one (e.g. screenshot a
   table, embed as image in a PDF). Deferred — same principle as the
   MIXED-document gap: don't fabricate a synthetic test when a real
   one hasn't been found yet; pick one up when sourcing Day 4 figure
   test cases, since that's the same detection problem in reverse.

3. MULTI-PAGE SPANNING TABLE — NOT CONFIRMED. No table in the current
   corpus verified to span two PDF pages (all found tables mapped to
   a single page_number). extract_tables() has no cross-page merge
   logic — if one exists in the corpus, it would currently be
   extracted as two unrelated table fragments. Real gap, untested
   because untriggered. Flagged for Day 4 corpus sourcing.

## Phase 1 Day 4 — figures.py: full-page scans misdetected as figures

worldbank_mixed.pdf (a 1990 scanned book with OCR text layer, same
document class as Day 1's archive_historical.pdf) produced 466
"figures" — every page's raster background, duplicated from Day 2's
already-saved page images. Root cause: no upper bound on image area
ratio. Fixed: MAX_IMAGE_AREA_RATIO=0.85 excludes near-full-page images.
Verified: worldbank_mixed.pdf 466→0, who_global_report.pdf unaffected
at 3, apple_10k confirmed still 0 (vector-only charts, no raster
figures at all — see Day 4 vector-chart gap, logged separately).

Pattern worth naming: this is the second time a scanned/OCR'd document
has broken an extraction assumption built for born-digital PDFs
(first: Day 1 detection, now: Day 4 figure extraction). Any future
per-object extraction step should ask "does this behave differently
on a full-page-scan document?" before trusting it on the whole corpus.

## Phase 1 Day 4 — figure description timeouts: resolved

Root cause: images extracted as PNG. PNG's lossless compression
performs poorly on photographic content — a 745x664 photo was 975KB,
producing a base64 payload large enough to consistently time out
through the AgentRouter gateway even at 90s. Isolated via a trivial
100x100 test image (succeeded instantly) before assuming payload
size — confirmed the gateway itself wasn't the problem before
patching blind. Fix: encode as JPEG (quality=85) for the API payload
only — reduced size 665KB→106KB (~6x). All 3 WHO figures now
described successfully and accurately, verified by direct image
comparison — no hallucination, correct color-tint identification.

## Phase 1 Day 5 — heuristic hierarchy fallback: untested

All 4 corpus documents have native PDF outlines — TOC-first path
used exclusively, heuristic fallback (font-size/bold detection,
built and debugged earlier) has never been exercised on real data.
Not fixing blind: no genuinely outline-less document exists in the
corpus yet. Same principle as the SCANNED/MIXED gaps from Days 1-2 —
logged, not fabricated a synthetic test for. Pick up when sourcing
broader corpus documents (a plain-text report or older PDF without
bookmarks would trigger it naturally).

# Phase 1 Day 5 — entity extraction: coreference gap identified

Real finding: "Apple Inc." (17), "Company" (61), and "Registrant" (15)
are almost certainly the same entity, referred to differently across
the document — legal/financial text constantly uses generic backreferences
after naming the subject once. Current normalization only catches
suffix variants of identical strings, not semantic coreference.

Also found: spaCy DATE misfires on non-date phrases ("annual", "Rule
12b-2", "the preceding 12 months") — model overreach, not a text
issue. '®' misclassified as ORGANISATION — filtered via low-value-
entity check.

Decision: coreference resolution is real, unproven-scope work (would
need either a coref model or LLM-assisted merging). Not building
blind. This becomes the natural motivating case for whether Phase 4's
GraphRAG needs cross-mention entity merging — if 61 "Company" mentions
never connect to "Apple Inc." in the graph, that's a measurable,
concrete failure to point to, not a guess.

## Phase 1 Day 6 — table/figure descriptions failing silently after model swap (4-6 → 4-8)

AgentRouter removed claude-opus-4-6; switched to claude-opus-4-8.
All description calls began failing with no visible error. Root
cause: 4-8 has extended thinking enabled by default (4-6 did not,
per AgentRouter's own docs listing reasoning:false for 4-6).
max_tokens=150/200 was entirely consumed by the thinking step before
any answer text was generated — response contained only a ThinkingBlock
with empty thinking text, stop_reason=max_tokens, no TextBlock at all.

Diagnosis took multiple steps because the extraction loop only
printed on a text-block match with no else/logging on miss — a
real response with no usable content failed completely silently.

Fix: max_tokens raised to 1024 in both generate_table_description
and generate_figure_description. Added explicit logging when no
text block is found, so this failure mode is visible next time
rather than requiring step-by-step raw-response inspection again.

## Phase 1 Day 6 — table description: 3/12 tables fail on thinking-token budget

Tables 3, 4, 7 (balance sheet, cash flow, equity — large multi-row
financial statements) consistently exceed max_tokens=2048 during
GLM's thinking phase, even after Claude's identical 4-8 issue was
fixed with the same budget. Confirmed correlated with raw row-data
size, not a fixed threshold — larger financial tables require more
reasoning tokens before producing output.

Decision: not chasing further right now. Claude quota exhausted
(402) mid-investigation; GLM fallback already retried once at higher
budget with no full fix. 9/12 tables have working descriptions,
including 5 of the 7 previously-confirmed real ones. Logged as a
known gap — revisit with a size-aware max_tokens (e.g. scale with
row_chars) once quota resets, or accept this as an honest ingestion
gap for Day 7 eval to reveal if it matters.

## Phase 1 Day 6 — table3 (balance sheet) description: accepted as unresolved

After 2 full retry cycles (including a Claude quota reset) at
max_tokens=2048/timeout=60s, both Claude and GLM consistently time
out generating a description for this table specifically — the
largest in the set. Not pursued further: 11/12 tables have working
descriptions, and burning more quota on the single hardest case has
worse ROI than moving forward. Chunk correctly skips it (no
description = no chunk, by design).

## Phase 1 Day 6 — char_start/char_end: ~38% of chunks span page boundaries

Measured, not guessed: 70 of 183 chunks (Apple 10-K) cross a page
boundary. For these, char_end is scoped to page_number's own text
only — content past that point (from the next page) exists in
chunk.content but isn't represented in the char_start/char_end
range. Verified single-page chunks are exact via direct text-slice
comparison (chunks 15-17 confirmed character-for-character match).

Decision: not building multi-span offsets now — that's schema and
logic complexity with no confirmed need yet. Real trigger: if Day 7
golden-set questions whose answers span this exact 38% fail due to
truncated evidence spans, that's the measured case for it. Until
then, this is a known, bounded, logged limitation — not a silent bug.

## Phase 1 Day 7 — golden dataset: printed page numbers ≠ PDF page indices

First golden example's evidence span assumed printed footer page 29
(from "Apple Inc. | 2025 Form 10-K | 29") equals fitz page index 29.
Wrong — front matter (cover, TOC, forward-looking statement notice)
offsets these by ~3 pages. Also found: the target number (416,161)
recurs on 6 different pages (MD&A, segment tables, income statement,
footnotes) — a bare numeric search is not a reliable anchor on its
own; needs surrounding unique context to disambiguate.

Fix: always locate evidence via find_evidence_span() against real
extracted text, never assume printed page number == array index.
Use distinctive surrounding phrases, not bare numbers, when the
number itself is repeated elsewhere in the document.
