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
