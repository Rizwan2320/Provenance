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

## Section hierarchy: PDF native outline (TOC) vs visual heuristic

Chose TOC-first (fitz.get_toc()), heuristic (font-size/bold detection)
as fallback only. Cost: heuristic path remains unvalidated — no
outline-less document in corpus yet. Benefit: ground-truth structure
when available; avoided the accuracy ceiling even mature tools hit
(pymupdf4llm benchmarks at 0.412 heading accuracy on pure heuristics).
Validated 4/4 real corpus documents via TOC path.

## Entity extraction: local spaCy vs LLM-based extraction

Chose spaCy (free, local, no network call) over LLM extraction. Cost:
no semantic coreference — "Company," "Registrant," "Apple Inc." stay
as separate entities despite referring to the same thing (logged in
FAILURES.md as a concrete Phase 4 test case). Benefit: zero per-call
cost, zero gateway-timeout risk — already hit twice with vision calls
this phase. Revisit if Phase 4 graph quality is measurably hurt by
the coreference gap.

## Table extraction tooling: heuristic baseline vs heavier tools

Tested and rejected three alternatives: text-strategy fallback
(69 false positives, worse than baseline), Docling (crashed on this
hardware — std::bad_alloc, 20min runtime, GPU-oriented pipeline),
PyMuPDF-Layout (OCR fallback broke on a trivial embedded image, 0
tables found). Accepted baseline: PyMuPDF lines-only + structural
filters, 58% precision / ~19% recall. Cost: real, measured recall
gap on dense financial tables without ruled lines. Benefit: fast,
reliable, zero crash risk, zero new heavy dependencies. Revisit only
with Day 7 eval evidence that table quality hurts answer accuracy.

## LLM provider: AgentRouter gateway vs direct Anthropic API

Using AgentRouter (free credit) instead of direct Anthropic due to
budget constraints. Cost: document content routes through non-
Anthropic infrastructure (acceptable for test/portfolio corpus, NOT
for real sensitive data); gateway latency variance directly caused
the vision-description timeout investigation (Day 4). Benefit: full
Claude Opus access at zero cost during learning phase. Revisit when
direct API budget exists — architecture already supports this as a
one-line config change (providers.py design intent, Phase 0).

## LLM provider: Claude-only vs Claude-with-GLM-fallback

AgentRouter introduced twice-daily quota batches for Claude/GPT
(402 error when exhausted). Added GLM as an automatic fallback via
OpenAI-compatible client — different SDK, different endpoint shape,
not a simple model-string swap. Cost: GLM's description quality is
unverified against our accuracy bar (Claude was spot-checked, GLM
is not yet). Benefit: pipeline keeps running through quota exhaustion
windows instead of blocking for hours.

## Ground truth anchoring: chunk-ID vs. evidence-span

Tested directly: re-ran chunk_document() with CHUNK_SIZE_TOKENS
changed from 400→350 (a realistic, ordinary tuning change). chunk 17
pointed to completely different content between runs — proving
chunk-ID references silently invalidate on any chunker change, with
no error to signal it. The same page+char_start/char_end reference
extracted identical text before and after, because it points into
the stable source page text, not a chunking artifact.

Decision: evidence-span (page + char_start/char_end) is the correct
ground-truth anchor for Day 7's golden set, confirmed empirically
on our own pipeline rather than accepted on v6's stated authority.
Cost: doesn't yet handle the ~38% of chunks spanning page boundaries
(logged separately in FAILURES.md) — evidence spans are more robust
to chunker changes, not yet complete for cross-page content.

## Golden dataset ground truth: multi-span evidence vs. single-span

Extended GoldenExample from three flat fields (page/char_start/char_end)
to evidence_spans: list[EvidenceSpan] when Q7 (multi-section synthesis)
proved a single span structurally couldn't represent an answer requiring
two separate document locations. Cost: broke and required migrating
5 already-locked examples (Q1,Q2,Q5,Q6,Q9) to the new shape. Benefit:
schema now correctly generalizes to any number of evidence locations
instead of hardcoding "exactly one" and hitting the same wall on the
next multi-section question. Chose list-of-one over "optional second
span" specifically to avoid a future third special case.

## Golden dataset scope: 9 examples on one document vs. broader corpus

Built golden set against Apple's 10-K only, not all 5 corpus documents.
Reasoning: concentrating examples on the one document with the deepest
validation history (known table bleeds, known cross-page chunks, known
hierarchy) lets each question deliberately test a real, already-found
edge case. Spreading thin across 5 documents would test generalization
instead — a different, real, but separate question, deferred until
the minimal single-document workflow is proven against a working baseline.
