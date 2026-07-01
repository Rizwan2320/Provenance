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
