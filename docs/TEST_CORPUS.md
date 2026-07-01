# Test Corpus

Documents used for Phase 1 development and evaluation.
Never commit actual PDFs — they may be large or have licensing restrictions.
Commit this manifest instead.

| File                          | Source                   | Quality Class | Pages | Notes                          |
| ----------------------------- | ------------------------ | ------------- | ----- | ------------------------------ |
| attention_is_all_you_need.pdf | arxiv.org/abs/1706.03762 | DIGITAL_TEXT  | 15    | Baseline digital PDF           |
| apple_10k_2025.pdf            | sec.gov EDGAR            | TABLE_HEAVY   | ~80   | Financial tables, multi-column |
| who_global_report.pdf         | who.int/publications     | IMAGE_HEAVY   | ~60   | Dense figures                  |
| archive_historical.pdf        | archive.org              | SCANNED       | ~30   | No text layer, needs OCR       |
| worldbank_mixed.pdf           | documents.worldbank.org  | MIXED         | ~100  | Partial scan                   |
