# data/evaluation/golden_set.py
"""
The 9 locked golden examples for apple_10k_2025.pdf.
Built and evidence-verified in Phase 1 Day 7. Do not overwrite this
file with test scripts — it is a permanent artifact, not scratch space.
"""

from configurations.schema import GoldenExample, EvidenceSpan, QueryType

GOLDEN_EXAMPLES: list[GoldenExample] = [

    GoldenExample(
        id="apple10k-q1",
        question="What was Apple's total net sales for fiscal year 2025?",
        reference_answer="$416,161 million",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=32, char_start=825, char_end=832)],
        notes="Consolidated Statements of Operations (PDF page 32). Printed page 29 != PDF index.",
    ),

    GoldenExample(
        id="apple10k-q2",
        question="Which countries does Apple's manufacturing outsourcing primarily depend on?",
        reference_answer="China mainland, India, Japan, South Korea, Taiwan and Vietnam",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=9, char_start=1003, char_end=1064)],
        notes="Page 8->9 boundary. Search string includes the real extracted newline.",
    ),

    GoldenExample(
        id="apple10k-q3",
        question="What was Apple's Services gross margin percentage in fiscal 2025?",
        reference_answer="75.4%",
        query_type=QueryType.TABLE,
        evidence_table_id="apple10k-v1-table2",
    ),

    GoldenExample(
        id="apple10k-q4",
        question="What were Apple's net proceeds from commercial paper for maturities greater than 90 days in fiscal 2025?",
        reference_answer="$3,788 million",
        query_type=QueryType.TABLE,
        evidence_table_id="apple10k-v1-table5",
        notes="Commercial paper table (~page 46). Bled raw cells; nl_description recovered the figure.",
    ),

    GoldenExample(
        id="apple10k-q5",
        question="How much term debt principal does Apple have due in 2026?",
        reference_answer="$12,393 million",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=47, char_start=2386, char_end=2495)],
        notes="Whitespace gap is column-alignment artifact, not ambiguity.",
    ),

    GoldenExample(
        id="apple10k-q6",
        question="How much common stock did Apple repurchase during fiscal 2025?",
        reference_answer="$89.3 billion",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=29, char_start=612, char_end=645)],
        notes="Chose plain-prose MD&A figure; three legitimate accounting variants exist ($89.3B narrative, $90,052M equity-statement, $90,711M cash-flow).",
    ),

    GoldenExample(
        id="apple10k-q7",
        question="What tariff-related risk did Apple identify, and how did new U.S. tariffs affect fiscal 2025 gross margins?",
        reference_answer="Apple identified tariffs and other trade restrictions as a risk that can materially adversely affect its business (Item 1A). In fiscal 2025, Products gross margin was partially offset by tariff costs.",
        query_type=QueryType.MULTI_SECTION,
        evidence_spans=[
            EvidenceSpan(page=9, char_start=1184, char_end=1298),
            EvidenceSpan(page=27, char_start=1106, char_end=1138),
        ],
        notes="First multi-span example. All estimated page numbers this session were wrong by 2-3 pages vs. real content.",
    ),

    GoldenExample(
        id="apple10k-q8",
        question="What percentage of Apple's Services revenue in fiscal 2025 came specifically from Apple Fitness+?",
        reference_answer="Not disclosed - Services revenue is reported in aggregate ($109,158 million total), not broken out by individual offering such as Fitness+",
        query_type=QueryType.UNANSWERABLE,
        notes="Correct behavior is abstention, not a fabricated percentage.",
    ),

    GoldenExample(
        id="apple10k-q9",
        question="Since what year has Apple's Head of Corporate Information Security led the company's Information Security team?",
        reference_answer="2016",
        query_type=QueryType.FACTUAL,
        evidence_spans=[EvidenceSpan(page=20, char_start=2426, char_end=2484)],
        notes="Curly apostrophe (U+2019) required - straight ASCII apostrophe does not match extracted text.",
    ),

]