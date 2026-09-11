# Phase 2 Document Intelligence Acceptance Criteria

Phase 2 is complete when all of the following are true:

- PDF, JPG, and PNG inputs are checked by file signature, readability, configured size, and the three-page limit.
- Native PDF text is used when available and OCR is used for scanned PDFs and images.
- All four user-selected document types produce schema-valid structured JSON.
- Extracted fields retain source text, page number, and bounding-box evidence when available.
- Invoice line items and financial-statement rows are represented as structured collections.
- Balance sheet, profit and loss, cash flow, and invoice calculations are performed deterministically.
- Missing or unreliable values are not invented and yield `NOT_APPLICABLE` checks where necessary.
- An optional language-model enrichment layer is configurable without coupling the core pipeline to one provider.
- Representative JSON outputs exist for all four document types.
- Unit tests and integration tests against the supplied samples pass.
- Every file in the supplied 50-document dataset processes without an unhandled error.

