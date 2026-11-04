from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


"""
Retrieval-only evaluation of the 9 golden examples. Zero LLM calls: reads the
cached index and embeds 9 questions locally.

METRICS (fixed before any result existed; do not change after seeing output):
  strict:      text spans - a chunk hits a span if >=50% of the span's characters
               lie inside that single chunk. Chunk positions come from the joined
               page text, so cross-page chunks are measured correctly.
               table questions - a retrieved chunk with table_id == evidence_table_id.
               Multi-span questions need EVERY span hit within the top-k.
  containment: every key string appears (whitespace-collapsed, case-folded) in the
               union of the top-k chunks. Keys are hand-written below.
  first=NOT IN INDEX: the evidence is absent from the whole index. That is an
               ingestion problem, not a retrieval problem.

MY PREDICTIONS (fill in BEFORE running; never edit afterwards):
  strict hit@5      : _ / 8
  containment hit@5 : _ / 8
  worst question    : ______
"""

from configurations.config import get_settings
from configurations.schema import QueryType
from ingestion.extractor import extract_digital
from retrieval.index import build_index, retrieve


DOC_ID = "apple10k"
FILENAME = "apple_10k_2025.pdf"
KS = (1, 3, 5)
MIN_SPAN_FRACTION = 0.5

# Hand-written from text seen in chunks.json. No curly apostrophes on purpose:
# typing one by hand is how Day 7 went wrong three times.
KEYS: dict[str, list[str]] = {
    "apple10k-q1": ["416,161"],
    "apple10k-q2": ["China mainland, India, Japan, South Korea, Taiwan and Vietnam"],
    "apple10k-q3": ["75.4%"],
    "apple10k-q4": ["3,788"],
    "apple10k-q5": ["12,393"],
    "apple10k-q6": ["$89.3 billion"],
    "apple10k-q7": ["new tariffs were announced", "partially offset by tariff costs"],
    "apple10k-q9": ["Information Security team since 2016"],
}


def _load_golden_examples(evaluation_dir: Path):
    """Load GOLDEN_EXAMPLES without relying on sys.path (keeps the linter happy)."""
    path = evaluation_dir / "golden_set.py"
    if not path.is_file():
        raise FileNotFoundError(
            f"golden_set.py not found at {path}. "
            "Expected location: data/evaluation/golden_set.py"
        )
    spec = importlib.util.spec_from_file_location("golden_set", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GOLDEN_EXAMPLES


def norm(s: str) -> str:
    return " ".join(s.split()).casefold()


def main() -> None:
    settings = get_settings()
    file_path = settings.raw_dir / FILENAME

    GOLDEN_EXAMPLES = _load_golden_examples(settings.evaluation_dir)

    pages = extract_digital(file_path).pages
    G = "".join(p.text for p in pages)
    page_start: dict[int, int] = {}
    off = 0
    for p in pages:
        page_start[p.page_number] = off
        off += len(p.text)

    index = build_index(file_path, doc_id=DOC_ID)  # cache hit: zero LLM calls
    text_chunks = [c for c in index.chunks if c.content_type.value == "text"]

    ranges: dict[str, tuple[int, int]] = {}
    pos = 0
    for c in text_chunks:
        at = G.find(c.content, pos)
        if at != -1:
            ranges[c.id] = (at, at + len(c.content))
            pos = at
    print(f"Index: {len(index.chunks)} chunks | text chunks located: {len(ranges)}/{len(text_chunks)}")
    if len(ranges) != len(text_chunks):
        print("  WARNING: unlocated text chunks, strict numbers are approximate")

    normed = {c.id: norm(c.content) for c in index.chunks}

    def strict(ex, top) -> tuple[int, int]:
        if ex.evidence_table_id:
            return int(any(c.table_id == ex.evidence_table_id for c in top)), 1
        covered = 0
        for sp in ex.evidence_spans:
            a = page_start[sp.page] + sp.char_start
            b = page_start[sp.page] + sp.char_end
            need = MIN_SPAN_FRACTION * (b - a)
            for c in top:
                r = ranges.get(c.id)
                if r and min(b, r[1]) - max(a, r[0]) >= need:
                    covered += 1
                    break
        return covered, len(ex.evidence_spans)

    def contain(ex, top) -> tuple[int, int]:
        keys = KEYS[ex.id]
        blob = "\x00".join(normed[c.id] for c in top)
        return sum(norm(k) in blob for k in keys), len(keys)

    def first_rank(fn, ex, ranked):
        for k in range(1, len(ranked) + 1):
            got, need = fn(ex, [r.chunk for r in ranked[:k]])
            if got == need:
                return k
        return None

    def fmt(t: tuple[int, int]) -> str:
        return f"{t[0]}/{t[1]}"

    answerable = [e for e in GOLDEN_EXAMPLES if e.query_type != QueryType.UNANSWERABLE]
    tallies = {k: [0, 0] for k in KS}  # [strict, containment]
    print()

    for ex in GOLDEN_EXAMPLES:
        ranked = retrieve(ex.question, index, top_k=len(index.chunks))

        if ex.query_type == QueryType.UNANSWERABLE:
            t = ranked[0]
            print(
                f"{ex.id}  UNANSWERABLE  top-1 score={t.score:.4f} p{t.chunk.page_number} "
                f"{t.chunk.content_type.value}: {t.chunk.content[:90]!r}\n"
            )
            continue

        tops = {k: [r.chunk for r in ranked[:k]] for k in KS}
        s = {k: strict(ex, tops[k]) for k in KS}
        c = {k: contain(ex, tops[k]) for k in KS}
        for k in KS:
            tallies[k][0] += s[k][0] == s[k][1]
            tallies[k][1] += c[k][0] == c[k][1]

        sr = first_rank(strict, ex, ranked)
        cr = first_rank(contain, ex, ranked)
        print(
            f"{ex.id}  {ex.query_type.value:<13} "
            f"strict@1/3/5: {fmt(s[1])} {fmt(s[3])} {fmt(s[5])} "
            f"first={sr if sr is not None else 'NOT IN INDEX'}  |  "
            f"contain@1/3/5: {fmt(c[1])} {fmt(c[3])} {fmt(c[5])} "
            f"first={cr if cr is not None else 'NOT IN INDEX'}"
        )
        for i, r in enumerate(ranked[:3], 1):
            print(
                f"      #{i} {r.score:.3f} p{r.chunk.page_number:<2} "
                f"{r.chunk.content_type.value:<5} {r.chunk.id}"
            )
        print()

    n = len(answerable)
    print(f"ANSWERABLE QUESTIONS: {n}")
    for k in KS:
        print(f"  hit@{k}:  strict {tallies[k][0]}/{n}   containment {tallies[k][1]}/{n}")


if __name__ == "__main__":
    main()