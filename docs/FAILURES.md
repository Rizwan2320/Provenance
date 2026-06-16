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
