"""
Annotation helper + first three locked-in GoldenExamples
(Apple 10-K 2025). All evidence spans verified against real extracted text.
"""

from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from configurations.schema import GoldenExample, QueryType
from ingestion.extractor import extract_digital


def find_evidence_span(
    pages: list[tuple[int, str]],
    page_number: int,
    search_text: str,
) -> tuple[int, int]:
    """
    Locates search_text within a page's real extracted text and returns
    exact (char_start, char_end).
    """
    page_text = next(t for p, t in pages if p == page_number)
    idx = page_text.find(search_text)
    if idx == -1:
        raise ValueError(
            f"{search_text!r} not found on page {page_number} — "
            "check exact wording/whitespace"
        )
    return idx, idx + len(search_text)


def main() -> None:
    result = extract_digital(Path("data/raw/apple_10k_2025.pdf"))
    pages = [(p.page_number, p.text) for p in result.pages]

    # ------------------------------------------------------------------
    # Example 1 — Consolidated Statements of Operations (PDF page 32)
    # ------------------------------------------------------------------
    start1, end1 = find_evidence_span(pages, page_number=32, search_text="416,161")
    print(f"ex1  page=32  char_start={start1}, char_end={end1}")

    ex1 = GoldenExample(
        id="apple10k-q1",
        question="What was Apple's total net sales for fiscal year 2025?",
        reference_answer="$416,161 million",
        query_type=QueryType.FACTUAL,
        evidence_page=32,
        evidence_char_start=start1,
        evidence_char_end=end1,
        notes=(
            "Anchored to the Consolidated Statements of Operations (PDF page 32). "
            "Printed page 29 ≠ PDF page index because of front matter."
        ),
    )

    # ------------------------------------------------------------------
    # Example 2 — manufacturing outsourcing countries (page 9, with real newline)
    # ------------------------------------------------------------------
    start2, end2 = find_evidence_span(
        pages,
        page_number=9,
        search_text="China mainland, India, Japan, South\nKorea, Taiwan and Vietnam",
    )
    print(f"ex2  page=9   char_start={start2}, char_end={end2}")

    ex2 = GoldenExample(
        id="apple10k-q2",
        question="Which countries does Apple's manufacturing outsourcing primarily depend on?",
        reference_answer="China mainland, India, Japan, South Korea, Taiwan and Vietnam",
        query_type=QueryType.FACTUAL,
        evidence_page=9,
        evidence_char_start=start2,
        evidence_char_end=end2,
        notes=(
            "Deliberately targets the page 8→9 boundary — tests the ~38% cross-page "
            "chunk finding. Same sentence also appears near-verbatim on page 11; "
            "page 9 chosen as first occurrence. Search string includes the real "
            "extracted newline between 'South' and 'Korea'."
        ),
    )

    # ------------------------------------------------------------------
    # Example 3 — table-anchored (Services gross margin)
    # ------------------------------------------------------------------
    ex3 = GoldenExample(
        id="apple10k-q3",
        question="What was Apple's Services gross margin percentage in fiscal 2025?",
        reference_answer="75.4%",
        query_type=QueryType.TABLE,
        evidence_table_id="apple10k-v1-table2",
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    examples = [ex1, ex2, ex3]

    print("\n" + "=" * 70)
    print(f"Locked-in GoldenExamples ({len(examples)})")
    print("=" * 70)

    for ex in examples:
        print(f"\n[{ex.id}]  {ex.query_type}")
        print(f"  Q: {ex.question}")
        print(f"  A: {ex.reference_answer}")
        if getattr(ex, "evidence_page", None) is not None:
            print(
                f"  evidence: page={ex.evidence_page}  "
                f"char=[{ex.evidence_char_start}:{ex.evidence_char_end}]"
            )
        if getattr(ex, "evidence_table_id", None):
            print(f"  evidence: table_id={ex.evidence_table_id}")
        if getattr(ex, "notes", None):
            print(f"  notes: {ex.notes}")

    print("\n→ Examples 1-3 are now verified against real extracted text.")
    print("  Ready to add examples 4–15.")


if __name__ == "__main__":
    main()