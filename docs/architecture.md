# Document Intelligence Platform Architecture

## Objective

Build a deployed application that validates financial-document uploads, extracts every meaningful visible value, performs evidence-backed financial checks, persists results, and exposes those results through a dashboard and REST API.

## Scope

Supported document categories are invoice, balance sheet, profit and loss statement, and cash flow statement. The user supplies the document type; automatic classification is intentionally outside scope. Inputs are PDF, JPG, or PNG files with a maximum of three pages.

## Processing flow

```text
Browser or API client
        |
        v
Upload validation
type, integrity, size, page count
        |
        v
Text layer extraction -----> OCR fallback for scanned pages
        |                              |
        +--------------+---------------+
                       v
Provider-neutral structured extraction
fields, tables, page evidence, nulls for missing values
                       |
                       v
Deterministic financial validation
formula, operands, calculated value, reported value, variance, status
                       |
                       v
Persistent document-result repository
                       |
              +--------+--------+
              v                 v
        REST API             Dashboard
```

## Components

- **API routes:** Multipart processing, latest-result lookup by document name, document listing, and health checking.
- **Document validation service:** Safe filename handling, MIME/signature validation, readability, corruption, size, and page-count checks.
- **OCR service:** Native PDF text first, with image OCR only where required.
- **Extraction service:** A provider adapter that returns a schema-constrained result without inventing unreadable values.
- **Financial validation service:** Deterministic Python calculations independent of the language model.
- **Repository:** SQLAlchemy persistence with SQLite locally and a deployment database URL in production.
- **Frontend:** Server-rendered HTML with focused JavaScript for uploads, dashboard navigation, validation display, and raw JSON.

## Foundational decisions

- FastAPI supplies validation, OpenAPI documentation, and a small deployment footprint.
- SQLAlchemy separates persistence logic from the database engine selected for deployment.
- Provider adapters keep OCR and LLM choices configurable through environment variables.
- Extracted values retain source text and page evidence when available.
- Financial calculations do not rely on model-generated arithmetic.
- Real credentials are loaded only from environment variables.

## Structured result boundary

Every successful processing response will contain:

- Document name and supplied document type
- Processing status and file-validation result
- Complete extracted fields and tables
- Evidence for important values
- Financial validation checks and overall validation status
- OCR use, timestamps, and processing duration

Invalid or failed requests will use a consistent error envelope with a stable code and safe user-facing message.

## Phase 2 implementation decisions

- PyMuPDF extracts native PDF text and rasterizes scanned pages; RapidOCR provides the local OCR fallback.
- Local, provider-neutral rules are the dependable baseline. An optional OpenAI-compatible adapter can enrich extraction when deployment credentials are configured.
- Currency and statement calculations use configurable absolute and relative tolerances.
- Scalar fields, comparative-period mappings, line items, financial rows, tables, and page evidence have explicit schema models.
- Ambiguous OCR does not become a false arithmetic claim: a check is `NOT_APPLICABLE` when its inputs cannot support a reliable decision.
