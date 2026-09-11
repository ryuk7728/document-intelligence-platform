# Phase 2 Document Intelligence Results

## Status

Phase 2 passed its acceptance gate on 11 September 2026.

## Delivered

- PDF/JPG/PNG validation, corruption checks, size limits, and a three-page maximum
- Native PDF text extraction with RapidOCR fallback for scanned pages and images
- Typed schemas for fields, evidence, invoice items, financial rows, tables, validations, and metadata
- Invoice, balance sheet, profit and loss, and cash flow extraction services
- Deterministic financial checks with formula, operands, calculated value, reported value, variance, and status
- Conservative OCR handling that returns `NOT_APPLICABLE` rather than making an unsupported arithmetic decision
- Optional OpenAI-compatible enrichment behind environment configuration; the verified baseline requires no provider credential
- Single-document CLI and full-dataset profiling command
- Representative JSON results in `sample_outputs/`

## Verification results

| Check | Result |
|---|---|
| Automated test suite | PASS - 26 tests |
| Supplied dataset processing | PASS - 50/50 documents |
| Processing failures | PASS - 0 |
| Deterministic validation | 39 PASS, 11 NOT_APPLICABLE, 0 FAIL |
| Invoice set | 20/20 processed; 13 PASS, 7 NOT_APPLICABLE |
| Balance sheet set | 10/10 processed; 10 PASS |
| Profit and loss set | 10/10 processed; 10 PASS |
| Cash flow set | 10/10 processed; 6 PASS, 4 NOT_APPLICABLE |
| OCR coverage | 49/50 documents used OCR; one PDF used its native text layer |
| Mean local processing time | 5,396 ms per document on the verification machine |

The 11 `NOT_APPLICABLE` outcomes are not processing failures. They occur when the source document omits a required reconciliation value or OCR cannot provide every operand reliably. The full OCR/native text blocks are preserved even when a canonical field cannot be safely populated.

## Reproducible commands

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe backend\scripts\profile_dataset.py "samples\dataset\New Dataset" --output "work\phase2\dataset-profile-final.json"
```

## Known non-blocking notes

- The test run emits two upstream deprecation warnings from the current FastAPI/Starlette test-client dependency combination; all tests pass.
- The supplied dataset and generated benchmark report stay untracked so sample data is not accidentally published.
- Deployment credentials for optional model enrichment have not been configured; local OCR and deterministic rules are the tested baseline.

