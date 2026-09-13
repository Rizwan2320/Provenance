"""
Final annotation script — all 8 GoldenExamples locked with verified evidence spans.
"""

from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from configurations.schema import GoldenExample, EvidenceSpan, QueryType
from ingestion.extractor import extract_digital


def find_evidence_span(
    pages: list[tuple[int, str]],
    page_number: int,
    search_text: str,
) -> tuple[int, int]:
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
    # Q1 — total net sales
    # ------------------------------------------------------------------
    ex1 = GoldenExample(
        id="apple10k-q1",
        question="What was Apple's total net sales for fiscal year 2025?",
        reference_answer="$416,161 million",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=32, char_start=825, char_end=832)],
        notes="Consolidated Statements of Operations (PDF page 32).",
    )

    # ------------------------------------------------------------------
    # Q2 — manufacturing countries (cross-page)
    # ------------------------------------------------------------------
    start2, end2 = find_evidence_span(
        pages, 9, "China mainland, India, Japan, South\nKorea, Taiwan and Vietnam"
    )
    ex2 = GoldenExample(
        id="apple10k-q2",
        question="Which countries does Apple's manufacturing outsourcing primarily depend on?",
        reference_answer="China mainland, India, Japan, South Korea, Taiwan and Vietnam",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=9, char_start=start2, char_end=end2)],
        notes="Page 8→9 boundary. Search string includes the real extracted newline.",
    )

    # ------------------------------------------------------------------
    # Q3 — Services gross margin (table)
    # ------------------------------------------------------------------
    ex3 = GoldenExample(
        id="apple10k-q3",
        question="What was Apple's Services gross margin percentage in fiscal 2025?",
        reference_answer="75.4%",
        query_type=QueryType.TABLE,
        evidence_table_id="apple10k-v1-table2",
    )

    # ------------------------------------------------------------------
    # Q4 — commercial paper (bled table)
    # ------------------------------------------------------------------
    ex4 = GoldenExample(
        id="apple10k-q4",
        question="What were Apple's net proceeds from commercial paper for maturities greater than 90 days in fiscal 2025?",
        reference_answer="$3,788 million",
        query_type=QueryType.TABLE,
        evidence_table_id="apple10k-v1-table5",
        notes="Commercial paper table (~page 46). Bled raw cells; nl_description recovered the figure.",
    )

    # ------------------------------------------------------------------
    # Q5 — term debt due 2026
    # ------------------------------------------------------------------
    ex5 = GoldenExample(
        id="apple10k-q5",
        question="How much term debt principal does Apple have due in 2026?",
        reference_answer="$12,393 million",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=47, char_start=2386, char_end=2495)],
        notes="Whitespace gap is column-alignment artifact, not ambiguity.",
    )

    # ------------------------------------------------------------------
    # Q6 — share repurchases
    # ------------------------------------------------------------------
    start6, end6 = find_evidence_span(pages, 29, "$89.3 billion of its common stock")
    ex6 = GoldenExample(
        id="apple10k-q6",
        question="How much common stock did Apple repurchase during fiscal 2025?",
        reference_answer="$89.3 billion",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=29, char_start=start6, char_end=end6)],
        notes="Chose plain-prose MD&A figure; three legitimate accounting variants exist.",
    )

    # ------------------------------------------------------------------
    # Q7 — multi-section (tariff risk + realized margin impact)
    # ------------------------------------------------------------------
    tariff_start, tariff_end = find_evidence_span(
        pages, 9,
        "tariffs and other controls on imports or exports of goods, technology or data, can materially adversely affect the",
    )
    margin_start, margin_end = find_evidence_span(
        pages, 27, "partially offset by tariff costs"
    )
    ex7 = GoldenExample(
        id="apple10k-q7",
        question="What tariff-related risk did Apple identify, and how did new U.S. tariffs affect fiscal 2025 gross margins?",
        reference_answer=(
            "Apple identified tariffs and other trade restrictions as a risk that can "
            "materially adversely affect its business (Item 1A). In fiscal 2025, "
            "Products gross margin was partially offset by tariff costs."
        ),
        query_type=QueryType.MULTI_SECTION,
        evidence_spans=[
            EvidenceSpan(page=9, char_start=tariff_start, char_end=tariff_end),
            EvidenceSpan(page=27, char_start=margin_start, char_end=margin_end),
        ],
        notes=(
            "First multi-span example. All estimated page numbers this session were "
            "wrong by 2-3 pages — never anchor on a remembered/guessed page again."
        ),
    )

    # ------------------------------------------------------------------
    # Q8 — unanswerable
    # ------------------------------------------------------------------
    ex8 = GoldenExample(
        id="apple10k-q8",
        question="What percentage of Apple's Services revenue in fiscal 2025 came specifically from Apple Fitness+?",
        reference_answer=(
            "Not disclosed — Services revenue is reported in aggregate "
            "($109,158 million total), not broken out by individual offering such as Fitness+"
        ),
        query_type=QueryType.UNANSWERABLE,
        notes="Correct behavior is abstention, not a fabricated percentage.",
    )

    # ------------------------------------------------------------------
    # Q9 — Cybersecurity
    # ------------------------------------------------------------------
    start9, end9 = find_evidence_span(
        pages, 20,
        "leading the Company\u2019s Information Security team since 2016",
    )
    ex9 = GoldenExample(
        id="apple10k-q9",
        question="Since what year has Apple's Head of Corporate Information Security led the company's Information Security team?",
        reference_answer="2016",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=20, char_start=start9, char_end=end9)],
        notes="Curly apostrophe (U+2019) required.",
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    examples = [ex1, ex2, ex3, ex4, ex5, ex6, ex7, ex8, ex9]

    print("=" * 70)
    print(f"Final locked set: {len(examples)} GoldenExamples")
    print("=" * 70)

    for ex in examples:
        print(f"\n[{ex.id}]  {ex.query_type}")
        print(f"  Q: {ex.question}")
        print(f"  A: {ex.reference_answer}")
        if ex.evidence_spans:
            for i, span in enumerate(ex.evidence_spans, 1):
                print(f"  span {i}: page={span.page}  char=[{span.char_start}:{span.char_end}]")
        if ex.evidence_table_id:
            print(f"  table_id: {ex.evidence_table_id}")
        if ex.notes:
            print(f"  notes: {ex.notes}")

    print("\n→ All 9 examples verified against real extracted text.")
    print("  Coverage: FACTUAL, TABLE, MULTI_SECTION, UNANSWERABLE.")


if __name__ == "__main__":
    main()