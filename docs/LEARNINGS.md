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
