## Phase 0 — schema.py

Q: We're only defining Document and ExtractionRun now.
The curriculum lists eight entity types for Phase 0.
Why is starting minimal correct despite what the curriculum says?

A: The curriculum's Phase 0 entity list is the target architecture —
it describes what will exist when the system is complete.
The engineering principle is stricter: only build what the next
phase actually requires to function. CanonicalEntity doesn't get
used until Phase 1 Day 5. EvaluationRun isn't needed until Day 7.
Building them today adds fields you haven't reasoned about yet,
relationships you'll get wrong, and complexity with no test
against it. Each entity gets added the day before the code
that needs it. The schema grows with evidence, not with planning.

Q: ExtractionRun has a config_hash field — a sha256 of the strategy
config. Why hash the config instead of just storing it as JSON?

A: Two reasons. First, equality comparison — you want to know if two
runs used identical configs without diffing nested JSON. One string
comparison on the hash answers that. Second, immutability signal —
a hash communicates that the config is fixed at run time. A raw
JSON field tempts you to mutate it later ("just update one field").
The hash makes the config a sealed record. If the config changed,
it's a new run, not an edit to the old one.

Q: frozen=True is set on Document but frozen=False on ExtractionRun.
What's the practical difference and why does each make sense here?

A: frozen=True makes the model immutable after creation — Pydantic
raises an error if you try to set any field. Document is immutable
by design: once a file is uploaded, its record doesn't change.
Updates produce a new Document with an incremented version.
ExtractionRun starts incomplete — you create it when extraction
begins, then update completed_at, chunk_count, and success when
it finishes. It needs to be mutable because it represents a
process in flight, not a completed fact.

Watch for: frozen=True models cannot be used with .model_copy(update={}).
You'll hit this in Phase 1 when you want to "update" a
document record. The correct pattern is creating a new
Document with version+1, not mutating the old one.

## Phase 0 — config.py

Q: Why use pydantic-settings instead of just os.environ or python-dotenv?

A: Three reasons. First, type coercion — os.environ returns strings only.
pydantic-settings automatically converts "50" to int, "true" to bool.
Without this you write int(os.environ["MAX_UPLOAD_SIZE_MB"]) everywhere
and forget it in one place. Second, validation at startup — if
ANTHROPIC_API_KEY is missing, pydantic-settings raises a clear
ValidationError before any code runs. os.environ raises a KeyError
inside whatever function first touches it. Third, documentation —
the Settings class is a single, readable list of every variable
the application requires. New teammates read one file, not the
entire codebase.

Q: Why wrap Settings in an lru_cache singleton instead of instantiating
it at module level like Settings() at the top of config.py?

A: Module-level instantiation reads the .env file the moment config.py
is imported — including during tests. With lru_cache, the Settings
object is created on first call and reused. In tests you can call
get_settings.cache_clear() and monkeypatch env vars before the
next call, giving you a fresh Settings with test values. Module-level
instantiation makes this impossible without reloading the module.
It's a one-line pattern that saves hours of test debugging.

Q: Settings uses extra="ignore" — unknown env vars are silently dropped.
What's the trade-off, and when would extra="forbid" be better?

A: extra="ignore" is safe in production where system-level env vars
(PATH, HOME, TERM, etc.) exist alongside your application vars.
Forbidding them would crash the app on startup. extra="forbid" is
valuable in development — it catches typos like ANTHROPIC_API_KEYS
(note the trailing S) that "ignore" silently drops, leaving you
wondering why calls are failing. The right approach is
extra="forbid" in development, extra="ignore" in production.
We start with "ignore" for simplicity and earn the split when
we have a staging environment in Phase 5.

Watch for: Field(...) means required — no default, no fallback.
If ANTHROPIC_API_KEY is missing from .env, the app
crashes at startup with a clear message. This is correct
behaviour. A missing API key that reaches an LLM call
produces an obscure HTTP 401 deep in a pipeline trace.
Fail fast at the boundary.

## Phase 0 — providers.py

Q: Why a thin wrapper function instead of a full abstract base class
with LLMProvider and EmbeddingProvider interfaces right now?

A: Abstract base classes are earned complexity. They make sense when
you have two concrete implementations you're switching between
at runtime. Right now you have one LLM provider (AgentRouter)
and one embedding model (all-MiniLM-L6-v2). Building a full
interface hierarchy for one implementation means writing twice
the code for zero current benefit. The abstraction gets added
when the second provider arrives — which in this project is
Phase 5 when you containerise and may swap to direct Anthropic.
Until then, a thin wrapper with lru_cache is the right tool.

Q: The embedding model is loaded once and cached. Why does this
matter more for sentence-transformers than for the LLM client?

A: Loading a sentence-transformers model means downloading ~90MB of
weights into memory and initialising the model on CPU or GPU.
That takes 3-8 seconds on first call. If get_embedding_model()
is called without caching — once per chunk, once per query —
you reload the model hundreds of times per pipeline run.
The LLM client is just an HTTP client with an API key — cheap
to initialise. The embedding model is an in-memory neural
network — expensive. Cache accordingly.

Q: Why does the LLM client need a custom base_url and auth_token
in addition to api_key when using AgentRouter?

A: The Anthropic SDK by default points to api.anthropic.com and
authenticates via the x-api-key header. AgentRouter is a
different server that accepts the same request format but at
a different URL. Setting base_url redirects all SDK calls to
AgentRouter's endpoint. The auth_token override handles a quirk
in how some gateway proxies expect the bearer token — without
it, some AgentRouter setups reject requests despite a valid
api_key. Setting both covers both authentication paths.

Watch for: sentence-transformers downloads the model to
~/.cache/huggingface/ on first call. On Windows this
path can exceed the 260-character MAX_PATH limit if
your username is long. If you hit an OSError on first
embed call, set TRANSFORMERS_CACHE=C:\hf_cache in
your .env and add that path to .gitignore.

## Phase 1 — ingestion/detector.py

Q: Why sample pages instead of reading the entire document
to detect quality? What's the engineering trade-off?

A: Reading all pages to detect quality means paying full extraction
cost before you know if extraction is even the right strategy.
On a 500-page scanned document, that's minutes of wasted work
before you discover OCR is needed. Sampling 5-10 pages gives
you a statistically reliable signal at ~2% of the cost.
The trade-off: a document that's DIGITAL_TEXT for 95% of pages
and SCANNED for 5% gets misclassified as DIGITAL_TEXT. That's
the MIXED case — we detect it by checking if text_ratio sits
between two thresholds, not at the extremes. Sampling still
catches this if your sample is large enough. Start with 5 pages,
measure misclassification rate on your golden dataset later,
adjust sample size if it's a real problem. Don't guess upfront.

Q: PyMuPDF opens encrypted PDFs without raising an error —
it just returns empty pages. Why is this a trap and how
do you detect it correctly?

A: This is the silent failure the curriculum warns about.
page.get_text() on an encrypted, locked PDF returns ""
— identical to a scanned page. If you only check for text
presence, an encrypted document looks like a scanned one
and gets queued for OCR, which also returns nothing.
The correct check is doc.is_encrypted AND doc.authenticate("")
failing — authenticate("") tries the empty password. If the
document is encrypted and the empty password doesn't unlock it,
it's genuinely locked. Detect this first, before any page
sampling, and reject with a clear error message.

Q: The detector returns a DetectionResult dataclass, not just
a DocumentQuality enum. Why the extra wrapper?

A: Two reasons. First, the extraction pipeline needs more than
the label — it needs page_count to estimate cost, text_ratio
to decide sample size for OCR, and notes for the audit log.
Returning just the enum loses that context. Second, the
DetectionResult is the first observability hook in the system.
Every document that enters the pipeline produces one record
that says exactly what the detector saw and why it classified
it the way it did. When a document gets misclassified in Phase 1,
this record is what you debug against.

Watch for: PyMuPDF imports as `fitz` not `pymupdf`. This trips
up everyone the first time. `import fitz` is correct
despite installing `pymupdf`.

## Phase 1 — detector.py (correction: density signals)

Q: Why can't DocumentQuality hold "digital text AND table-heavy"
as one enum value, and why is splitting it the right fix
instead of adding a fifth enum value like DIGITAL_TABLE_HEAVY?

A: Enum explosion. Five base states × two density flags = up to
20 combinations if you tried to enumerate every case. Two
independent booleans express the same information with two
fields instead of twenty enum values. The real signal: if two
properties of a thing can vary independently, they don't
belong in the same enum — model them as separate fields.

Watch for: find_tables() runs per sampled page, not the whole
document — keep it that way. Running it on every page
of a 500-page 10-K at detection time defeats the
purpose of sampling.

## Phase 1 — detector.py (second correction: geometry can't see content)

Q: Why can't image_area_ratio + text_ratio distinguish a scanned
text page from a digitally-rasterized chart page?

A: Both produce identical geometry: one image object, near-full
page coverage, near-zero extractable text. The distinguishing
fact — is the image's _content_ text-shaped or chart-shaped —
isn't visible in page layout at all. It only becomes observable
after OCR runs and you inspect confidence/character density.
A heuristic that looks plausible on a whiteboard can still be
structurally incapable of answering the question — that's a
different failure mode than a bug, and harder to catch because
the code runs without error and produces a confident-looking answer.

Watch for: any classification heuristic built on layout/geometry
when the real distinguishing signal is content. Ask:
"does this input space actually contain the information
I'm trying to extract?" before trusting the threshold.

## Phase 1 — detector.py (third correction: density signals are conditional, not universal)

Q: Why does is_image_heavy need to be gated on text_ratio instead of
being computed independently like table_density?

A: image*area_ratio measures "what fraction of the page is covered
by image objects" — it has no concept of \_why* the page is an
image. For a SCANNED page, the entire page being one image object
is the definition of the classification, not new information.
Flagging it image_heavy on top of SCANNED is a tautology — it
tells you nothing you didn't already know. The flag only adds
real signal on a page that DOES have extractable text and ALSO
has a large embedded image alongside it — that's the WHO-report
case (charts next to real text), which is the actual use case
this flag was built for.

Watch for: any derived signal computed from the same underlying
measurement (page geometry, in this case) as another
signal can end up redundant or contradictory with it.
Ask "does this flag add information the primary
classification doesn't already imply?" before trusting it.

## Q: PyMuPDF's get_text("text", sort=True) — what does sort=True

actually do, and why does it fix the multi-column problem?

A: Without it, get_text() returns text in the order objects were
written into the PDF's internal structure — often column 1 top,
column 2 top, column 1 middle, interleaved unpredictably.
sort=True reorders extracted blocks by position (top-to-bottom,
left-to-right) before returning text. It's a built-in solution —
no custom column-detection logic needed. Simplest thing that works.

## Q: Why is OCR a separate file instead of a branch in this one?

A: Different failure modes, different dependencies, different
system requirements (Tesseract binary vs pure Python). Mixing
them means one file has two unrelated reasons to break.

Watch for: sort=True is a heuristic, not perfect column detection.
Complex layouts (3+ columns, sidebars) can still misorder.
Don't fix this until a real document proves it's a problem.

## Q: Why dpi=300 specifically?

A: Tesseract's documented accuracy sweet spot. Below ~250, character
shapes blur and confidence drops. Above ~400, processing time rises
with no accuracy gain — you're feeding it more pixels of the same
information.

## Q: Why image_to_data() in addition to image_to_string()?

A: image_to_string() gives text only — no way to know if OCR guessed
badly. image_to_data() gives per-word confidence, which is the
only signal that tells you whether to trust the output or flag
it for review. Confidence is what makes OCR output usable in a
pipeline instead of a black box.

Watch for: confidence=92.1 with real errors in it ("rime" for "Time").
High confidence ≠ zero errors — it means most words were
readable. Never treat OCR output as ground truth without
this caveat downstream.

## Q: Why check magic bytes instead of trusting the file extension?

A: Extensions are just a filename string — trivially spoofable.
Magic bytes are the actual first bytes PDF readers use to
identify the format. Checking them is the difference between
validating and merely trusting.

## ## Phase 1 Day 4 — figures.py (extraction only)

Q: Why filter by area ratio (3% of page) instead of just extracting
every embedded image object?

A: A page can have dozens of image objects that aren't real figures —
corporate logos, decorative icons, single-pixel spacer images.
Extracting and later paying an LLM to describe all of them wastes
money and pollutes retrieval with junk. Area ratio is a cheap
proxy: real charts/diagrams occupy meaningful page space, logos
don't. Same principle as \_is_prose_like from Day 3 — a structural
heuristic, not a content judgment, applied before the expensive
step (LLM description) runs.

Watch for: get_image_info(xrefs=True) returns the xref needed to
pull actual pixel data via fitz.Pixmap(doc, xref) — without
xrefs=True you only get bbox geometry, not enough to save
the image.

## Phase 1 Day 4 — figures.py (upper bound added)

Q: Why does a "figure" extractor need an upper size bound, not just
a lower one?

A: The lower bound (3%) filters noise — logos, icons. But the same
logic applies symmetrically at the top: an image covering nearly
100% of the page isn't a figure embedded in a page, it IS the page
— the whole background of a scanned document. This surfaced on
worldbank_mixed.pdf, a 1990 scanned book with an OCR text layer
(same document class as archive_historical.pdf from Day 1 — a
recurring pattern worth recognizing across the corpus, not a
one-off). Extracting these as "figures" duplicates what
save_page_images() already saved on Day 2, at 466x the cost.

Watch for: any "extract embedded object" logic on a scanned/OCR'd
document risks re-extracting the whole page as if it were
content. Two independent signals (this and Day 1's
image_heavy gating) both point to the same underlying
fact: scanned documents need different handling throughout
the pipeline, not just at detection time.

## ## Phase 1 Day 5 — hierarchy.py (font-size heading detection)

Q: Why font size relative to the document's own modal size, instead
of a fixed threshold like "anything above 14pt is a heading"?

A: Different documents use wildly different base font sizes — a
10-K might use 9pt body text, a report might use 11pt. A fixed
threshold would misclassify one document's body text as headings
and miss another's real headings entirely. Computing the modal
size per-document first makes the 15% threshold relative and
portable across your whole corpus, not tuned to one file.

Q: Why two passes over the document instead of one?

A: You can't know what counts as "large" until you know the baseline,
and the baseline (modal size) can only be computed by seeing the
whole document first. Same reasoning as the sampling threshold in
detector.py — you need the full picture before classifying parts
of it.

Watch for: this WILL misfire on the Apple 10-K's cover page and
bold-but-not-heading text (e.g. bolded terms mid-paragraph).
Don't fix blind — test first, see what actually breaks.

## Phase 1 Day 5 — hierarchy.py corrected: TOC-first, not heuristic-first

Q: We spent significant effort building a font-size/bold heuristic
before checking get_toc(). What's the actual lesson?

A: Reach for ground truth before building an approximation. PDF's
native outline, when present, IS the document author's real
section structure — not a guess about it. The font-size heuristic
only became necessary the moment we assumed no ground truth
existed, without checking. A quick web search on how established
tools solve this (and a benchmark showing even pymupdf4llm scores
only 0.412 on heading accuracy with pure heuristics) confirmed:
professional parsers check native structure tags FIRST, heuristics
SECOND. Worth the 10 minutes of research before building further.

Watch for: get_toc() being empty doesn't mean the fallback heuristic
is reliable — it's still unvalidated at scale. Test it
against a document with genuinely no outline before
trusting it.

## Phase 1 Day 5 — entities.py (single-document scope, spaCy)

Q: Why build in-document dedup now but defer cross-document merging?

A: They're different problems with different difficulty. In-document:
exact-match on normalized text, cheap, low-risk. Cross-document:
"Apple Inc." in document A and "Apple" in document B need fuzzy
or embedding-based matching to know they're the same entity —
real complexity, unproven need. Building both at once means two
unvalidated things at once. Prove extraction works first.

Q: Why spaCy instead of the LLM client already wired in providers.py?

A: Cost and reliability. LLM entity extraction means an API call per
chunk — real money, and the same gateway-timeout risk we just hit
twice with vision descriptions. spaCy runs locally, free, no
network dependency, with built-in categories that map cleanly to
our EntityType enum. LLM extraction stays an option if spaCy's
accuracy proves insufficient on real text — but that's a
measured decision, not a default.

Watch for: canonical_name picks the FIRST surface form seen, not
necessarily the most complete or formal one — "the
Company" could win over "Apple Inc." if it appears first
in the text. Worth checking on real output before trusting it.

## Phase 1 Day 6 — chunker.py (fixed-size baseline)

Q: Why tiktoken instead of the word-count proxy ("len(text.split())")
used loosely earlier in this session?

A: Chunk size directly determines what fits in an embedding model's
context window — and embedding models count in actual tokens, not
words. A word-count proxy can be off by 30%+ on dense technical or
financial text (lots of numbers, punctuation, multi-token words).
tiktoken is free, local, no API call — same "tried and tested over
invented" principle as choosing get_toc() over a heuristic in Day 5.

Q: Why binary search (bisect_right) for section lookup instead of
scanning the heading list per chunk?

A: With ~100+ headings (Apple's TOC) and hundreds of chunks per
document, a linear scan per chunk is O(n\*m). Sorting headings once
and binary-searching per chunk is O(m log n) — matters once you're
chunking a real corpus, not just one test document.

Watch for: total_chunks is backfilled after the fact via
object.**setattr** because Chunk is frozen and total count
isn't known until all chunks exist. This is a deliberate
exception to immutability — document why if it looks odd
later.

## Phase 1 Day 6 — table/figure chunks (nl_description over rows)

Q: Why skip a table/figure entirely when nl_description is missing,
instead of falling back to raw rows or an empty string?

A: An empty or garbled chunk is worse than a missing one — it either
pollutes retrieval with unranked noise or gets embedded as
near-meaningless content that still competes for retrieval slots.
Skipping is honest: no description means we genuinely can't offer
a reliable retrieval unit for that table/figure yet. This is a
quiet quality gate that surfaces coverage gaps naturally — count
skipped items later as a real metric, not silently absorbed.

## Phase 1 Day 6 — sentence-boundary snapping

Q: Why snap backward to the nearest sentence end instead of forward
to the next one?

A: Snapping forward means every chunk could silently grow past
CHUNK_SIZE_TOKENS, compounding across a long document and making
token budgets unpredictable. Snapping backward keeps chunks at or
under the target size — slightly smaller chunks are a fine
trade-off; unpredictably larger ones are not.

Q: Why does the loop's advance step change (i += max(step, ...))
instead of always advancing by the fixed step?

A: If a chunk got shortened by snapping, advancing by the original
fixed step could skip content or shrink overlap unpredictably.
Advancing based on the chunk's actual length keeps overlap
consistent regardless of where the sentence boundary fell.

Watch for: table/figure chunk text (nl_description output) may not
have clean sentence punctuation the regex expects. Verify
this only affects chunk_document() — chunk_tables() and
chunk_figures() don't use this function at all, so they're
unaffected regardless.

## Phase 1 Day 6 — char_start/char_end: correct for single-page chunks, logged limitation for cross-page

Q: Why not just compute char_end as char_start + len(content) always?

A: content can include tokens from the NEXT page if a chunk's window
crosses a page boundary — that's allowed by design (sliding window
doesn't respect page edges). Using full content length would make
char_end point past the end of page_number's actual text, which
is worse than an honest, narrower, correct value. Cross-page chunks
get a warning logged and char_end scoped to page_number's own text
only — same "log the edge case, don't guess" rule as every other
gap this session.

Watch for: cross-page chunk frequency is currently unmeasured. If
Day 7's golden set shows many real answers straddle page boundaries
this way, that's the measured signal to build proper multi-span
support — not a guess made now.

## Phase 1 Day 7 — golden dataset: smart quotes in extracted text

PDF text extraction preserves typographic (curly) apostrophes/quotes
(’, ‘, “, ”) rather than straight ASCII ones ('). Any hand-typed
search string using straight quotes will silently fail to match real
extracted text containing a possessive or quotation. Always copy the
exact substring from a diagnostic dump rather than retyping it by hand.
