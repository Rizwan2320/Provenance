"""
Diagnose apple10k-q1: where does the gold chunk rank, which chunks actually
contain the answer string, and is the answer inside the part of each chunk
the embedding model can see?

Q1 values hardcoded from golden_set.py on purpose: avoids guessing an
import path for data/evaluation/. Facts, not fixes — changes nothing.
"""

from __future__ import annotations
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


import numpy as np

from configurations.config import get_settings
from configurations.provider import embed_texts, get_embedding_model
from retrieval.index import build_index

DOC_ID = "apple10k"
FILENAME = "apple_10k_2025.pdf"
QUERY = "What was Apple's total net sales for fiscal year 2025?"
ANSWER = "416,161"
GOLD_PAGE, GOLD_START, GOLD_END = 32, 825, 832  # apple10k-q1 evidence span


def main() -> None:
    settings = get_settings()
    index = build_index(settings.raw_dir / FILENAME, doc_id=DOC_ID)
    model = get_embedding_model()
    tok = model.tokenizer
    # max_seq_length is typed as int | None; treat missing value as "no truncation"
    limit: int = model.max_seq_length if model.max_seq_length is not None else sys.maxsize

    def wordpieces(text: str) -> int:
        return len(tok(text, add_special_tokens=True, truncation=False)["input_ids"])

    q = np.array(embed_texts([QUERY])[0], dtype=np.float32)
    sims = (index.vectors @ q) / (np.linalg.norm(index.vectors, axis=1) * np.linalg.norm(q))
    order = np.argsort(-sims)
    rank_of = {index.chunks[i].id: r + 1 for r, i in enumerate(order)}
    score_of = {c.id: float(sims[i]) for i, c in enumerate(index.chunks)}

    # 1. Model input limit vs. chunk size
    lengths = [wordpieces(c.content) for c in index.chunks]
    over = sum(1 for n in lengths if n > limit)
    print(f"Embedding model max_seq_length = {limit if limit != sys.maxsize else None} wordpieces")
    print(f"Chunks exceeding it: {over}/{len(lengths)}  (median length: {int(np.median(lengths))})\n")

    # 2. Gold chunk
    gold = [
        c
        for c in index.chunks
        if c.page_number == GOLD_PAGE
        and c.char_start is not None
        and c.char_end is not None
        and c.char_start <= GOLD_START
        and c.char_end >= GOLD_END
    ]
    print("GOLD CHUNK(S) — cover page 32, chars 825-832:")
    for c in gold:
        print(f"  {c.id}: rank={rank_of[c.id]}/{len(index.chunks)}  score={score_of[c.id]:.4f}")
    print()

    # 3. Every chunk containing the answer string
    containing = sorted((c for c in index.chunks if ANSWER in c.content), key=lambda c: rank_of[c.id])
    print(f"CHUNKS CONTAINING {ANSWER!r} ({len(containing)} total), by rank:")
    for c in containing:
        wp_pos = wordpieces(c.content[: c.content.index(ANSWER)])
        visible = "INSIDE embedded window" if wp_pos < limit else "TRUNCATED — never embedded"
        print(
            f"  rank={rank_of[c.id]:>3}  score={score_of[c.id]:.4f}  page={c.page_number:>2}  "
            f"type={c.content_type.value:<5}  answer at wordpiece ~{wp_pos}  [{visible}]"
        )


if __name__ == "__main__":
    main()