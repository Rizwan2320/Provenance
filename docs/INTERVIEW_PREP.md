## Data Modelling for Production ML Systems

Question:
"Walk me through how you'd design the data model for a production
RAG system from scratch. What entities do you define and why?"

Why they're asking:
Senior AI engineers think in systems — IDs, lifecycles, failure modes.
They want to see if you designed upfront or discovered the hard way.
A candidate who can explain why chunk IDs encode document versions
has clearly built something real.

Weak answer:
"I'd have a documents table with id, content, and metadata, and
store embeddings in a vector database keyed by document id. Chunks
would be rows with a foreign key back to documents."

Strong answer:
"I defined the schema before writing any pipeline code — eight core
entities covering documents, chunks, extraction runs, embedding runs,
entities, evaluation runs, golden examples, and audit events.

The non-obvious decision was version-encoding chunk IDs: format is
{doc_uuid}-v{version}-{chunk_index}. When a document is updated, all
derived chunk IDs change automatically. This means re-indexing never
silently overwrites old chunks in the vector store, you can roll back
by pointing queries at the old index version, and you can tell exactly
which extraction and embedding run produced any given chunk.

I also separated ExtractionRun from EmbeddingRun as distinct entities
because they fail and change independently — swapping embedding models
shouldn't invalidate extraction results. This let me track costs
separately per component, which became the cost waterfall chart in
production.

[YOUR: Add one specific thing you discovered when implementing this
that you wouldn't have predicted from reading about it]"

## Configuration & Secrets Management in Production AI Systems

Question:
"How do you manage configuration and secrets across local development,
CI, and production in an AI system that calls multiple external
providers?"

Why they're asking:
Misconfigured secrets are a top-5 production incident cause.
They want to see if you've thought about the full lifecycle —
not just "I use .env files."

Weak answer:
"I use a .env file for API keys and load them with python-dotenv.
In production I set environment variables on the server."

Strong answer:
"I use pydantic-settings with a typed Settings class as the single
source of truth. Required fields use Field(...) with no default —
missing keys crash at startup with a clear ValidationError, not
silently mid-pipeline when an LLM call hits a 401.

Local dev reads from .env. CI injects secrets as environment
variables from GitHub Actions secrets — the Settings class adapts
automatically because pydantic-settings reads env vars before
the .env file. Production uses [YOUR: secrets manager choice —
Vault, Doppler, AWS Secrets Manager].

I pin every model version explicitly in Settings —
never 'claude-sonnet-4' but 'claude-sonnet-4-20250514'. Provider
model behaviour changes between versions. Pinning means a model
update is a deliberate config change with a commit, not a
surprise behaviour shift.

The lru_cache singleton means tests can call
get_settings.cache_clear() and inject test values without
reloading modules. [YOUR: add one thing that broke in practice
and how this design caught it]"

## Provider Abstraction in AI Systems

Question:
"How do you structure LLM provider access in a production system
to avoid vendor lock-in, and where do you draw the abstraction
boundary?"

Why they're asking:
Every production AI system eventually switches models or providers —
cost, quality, availability. They want to see if you've thought
about the blast radius of that change before it happens.

Weak answer:
"I'd create an abstract base class with methods like generate()
and embed(), then implement it for each provider. That way I can
swap providers by changing the implementation."

Strong answer:
"I draw the abstraction boundary based on current need, not
anticipated need. With one provider, a thin wrapper function
cached with lru_cache gives you the same swap-ability as a full
abstract class — provider change means one config update, nothing
else. I added the abstract interface only when a second provider
arrived and I needed runtime selection between them.

The non-obvious decision was separating the client from the
model name. The client handles authentication and routing —
in our case pointing to AgentRouter instead of Anthropic directly
via base_url override. The model name lives in config. Changing
the model is a config change. Changing the provider is a
client change. They fail and evolve independently so they
live separately.

[YOUR: add what actually broke when you first called the
AgentRouter endpoint and how you debugged it]"

## Routing & Classification in ML Pipelines

Question:
"How do you handle heterogeneous document types in a RAG ingestion
pipeline where some documents have text layers and others are scanned
images? Walk me through the decision points."

Why they're asking:
Silent failures are the most dangerous failures in ML pipelines.
They want to know if you've thought about the cases where the
system appears to work but produces garbage output.

Weak answer:
"I'd run OCR on all documents to handle both cases, then extract
text from the OCR output."

Strong answer:
"Running OCR on everything sounds safe but it's the wrong default.
OCR on a digital PDF introduces transcription errors that didn't
exist in the source — you're actively degrading quality on documents
that have a perfect text layer.

I built a detector that runs before any extraction. It checks
for corruption and encryption first — both produce silent empty
output if you don't check for them explicitly. Encrypted PDFs in
particular look identical to scanned PDFs when you only check for
text presence. Then it samples pages spread evenly across the
document — not just the first N pages, because cover pages and
tables of contents are often image-heavy even in digital documents.

The thresholds — 80% text pages for DIGITAL_TEXT, 20% for SCANNED
— are starting points, not ground truth. They get tuned against
the golden dataset in the evaluation phase.

[YOUR: add your actual text_ratio distribution across your test
corpus and what threshold you settled on after measuring]"

## Schema Design — Orthogonal vs Conflated State

Question:
"Tell me about a time you found a design flaw in a data model
before it caused a production bug. How did you spot it?"

Why they're asking:
This is a system-design-judgment question disguised as a
behavioral one. They want evidence you read your own schemas
critically instead of just shipping them.

Strong answer:
"I'd modeled document quality as a single enum — DIGITAL_TEXT,
SCANNED, MIXED, IMAGE_HEAVY, TABLE_HEAVY. Before writing the
detector logic, I realized two of those values weren't mutually
exclusive with the others — a financial filing can have a perfect
text layer and be table-heavy at the same time. A single enum
forces you to pick one truth and silently lose the other.

I split it: DocumentQuality keeps only the mutually-exclusive
text-layer states. Table and image density became independent
boolean signals computed separately. The test was simple — for
any two properties, can they vary independently? If yes, they
don't belong in the same enum.

[YOUR: add what you found when you ran this against the 5-document
corpus — which one actually triggered both flags at once]"

## Feature Engineering — When a Heuristic Can't See What It Needs

Question:
"Tell me about a classification heuristic you built that seemed
reasonable but turned out to be fundamentally unable to solve the
problem. How did you catch it?"

Why they're asking:
Distinguishing "this code has a bug" from "this approach can't work
no matter how you tune it" is a senior-level diagnostic skill.
They want evidence you check whether your features can even contain
the signal you're asking them to discriminate.

Strong answer:
"I wanted to distinguish scanned text pages from digitally-rasterized
image pages at document-detection time, using image area coverage
and text ratio as signals. I caught the problem before shipping it:
both cases produce identical page geometry — one image, full-page
coverage, zero extractable text. The signal I needed — is the image
content text-shaped or chart-shaped — doesn't exist in layout data
at all, only in pixel content, which you only get after running OCR.

Rather than build a fragile geometric proxy, I deferred the decision
to extraction time, gated on OCR confidence — a real measured signal
instead of a guessed one. [YOUR: add the actual OCR confidence
distribution you saw once Phase 1 OCR ran, and whether you ended
up needing the vision-captioning fallback at all]"## Feature Engineering — When a Heuristic Can't See What It Needs

Question:
"Tell me about a classification heuristic you built that seemed
reasonable but turned out to be fundamentally unable to solve the
problem. How did you catch it?"

Why they're asking:
Distinguishing "this code has a bug" from "this approach can't work
no matter how you tune it" is a senior-level diagnostic skill.
They want evidence you check whether your features can even contain
the signal you're asking them to discriminate.

Strong answer:
"I wanted to distinguish scanned text pages from digitally-rasterized
image pages at document-detection time, using image area coverage
and text ratio as signals. I caught the problem before shipping it:
both cases produce identical page geometry — one image, full-page
coverage, zero extractable text. The signal I needed — is the image
content text-shaped or chart-shaped — doesn't exist in layout data
at all, only in pixel content, which you only get after running OCR.

Rather than build a fragile geometric proxy, I deferred the decision
to extraction time, gated on OCR confidence — a real measured signal
instead of a guessed one. [YOUR: add the actual OCR confidence
distribution you saw once Phase 1 OCR ran, and whether you ended
up needing the vision-captioning fallback at all]"

## Debugging — When Test Data Hides the Bug You're Looking For

Question:
"Tell me about a time your test data gave you a false sense of
confidence — where you thought you'd covered a case but actually
hadn't."

Why they're asking:
This tests whether you verify assumptions about test data itself,
not just your code. A lot of production bugs ship because "we tested
that case" turns out to mean "we tested a document we assumed had
that property."

Strong answer:
"I built a document quality detector and picked one test document
per quality class — including a 'scanned' document from Internet
Archive to test the no-text-layer path. Every document, including
that one, classified as having a full text layer. I didn't assume
my detector was right and move on — I checked the actual extracted
text and found OCR artifacts, confirming Archive.org bakes an
invisible OCR text layer into scanned PDF derivatives for
searchability. The document was visually scanned but not
text-layer-empty — two different properties I'd conflated when
picking test data.

That meant my 'scanned' code path had zero real test coverage
despite appearing covered. I sourced a genuine no-text-layer
document — a camera photo converted directly to PDF, no OCR step
— to actually exercise that branch.

[YOUR: add what you found when you ran the real scanned doc through —
did the SCANNED branch work correctly on first try, or did testing
it for real surface a new bug?]"

## Signal Redundancy in Multi-Signal Classification Systems

Question:
"You're computing several independent signals from the same raw
input. How do you make sure they're actually adding information
rather than just restating each other?"

Why they're asking:
Feature engineering interviews probe whether you understand that
two metrics derived from the same underlying data can be correlated
to the point of redundancy — even when they look like separate
boolean flags in your schema.

Strong answer:
"I had two density flags — table_heavy and image_heavy — computed
from page geometry. Testing against a real single-page camera scan
exposed that image_heavy fired as True on a page with zero embedded
images, just printed text. The cause: the whole scanned page IS one
image object at ~100% coverage — that's the SCANNED classification's
entire premise, so flagging image_heavy on top of it is circular,
not additive information.

The fix was gating image_heavy on text_ratio exceeding the SCANNED
threshold — the flag only fires when there's a real text layer
AND a large embedded image alongside it, which is the actual case
it's meant to catch.

[YOUR: add whether table_heavy showed the same redundancy issue
when you checked it, or whether that one was genuinely independent]"
