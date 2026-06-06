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
