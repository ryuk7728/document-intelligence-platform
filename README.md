# Document Intelligence Platform

[![CI](https://github.com/ryuk7728/document-intelligence-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/ryuk7728/document-intelligence-platform/actions/workflows/ci.yml)

An AI Engineer Internship case-study implementation for validating, extracting, reconciling, storing, and displaying information from invoices, balance sheets, profit and loss statements, and cash flow statements.

## Current status

The complete application includes:

- Modular FastAPI application scaffold
- Versioned API routing and health endpoint
- SQLAlchemy persistence foundation
- Environment-based configuration
- PDF/JPG/PNG validation with file-signature, readability, size, and three-page checks
- Native PDF text extraction with OCR fallback for scans and images
- Structured extraction for invoices, balance sheets, profit and loss statements, and cash flow statements
- Page-level source evidence and bounding boxes
- Deterministic financial reconciliation with `PASS`, `FAIL`, and `NOT_APPLICABLE` outcomes
- Optional provider-neutral OpenAI-compatible extraction enrichment
- A CLI and dataset profiling tool
- Automated unit and supplied-sample integration tests
- A responsive upload, history, evidence, validation, and JSON dashboard
- Persistent REST endpoints backed by SQLite locally or PostgreSQL in deployment
- Docker, Render Blueprint, Vercel, and GitHub Actions configuration

The supplied 50-document benchmark processed every file successfully with 39 deterministic validation passes, 11 honest `NOT_APPLICABLE` outcomes, and no validation failures.

## Live application

- Frontend: https://document-intelligence-platform-bice.vercel.app
- Backend API base: https://document-intelligence-platform-gn7s.onrender.com/api/v1
- API documentation: https://document-intelligence-platform-gn7s.onrender.com/docs
- Development approach: [Google Slides](https://docs.google.com/presentation/d/1Ec6sywdyoi3JuIiW2RbvB6bAQoZPVAhkGDm5VCfPlhs/edit?usp=sharing) ([repository copy](presentation/Document_Intelligence_Development_Approach.pptx))

## Repository structure

```text
backend/       FastAPI application, services, models, repositories, and tests
frontend/      HTML templates and static assets
docs/          Architecture and delivery documentation
presentation/  Development-approach slide deck
sample_outputs/ Representative structured JSON responses
samples/       Local sample-document working area
```

## Local setup

From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Open:

- Dashboard: `http://127.0.0.1:8000/`
- Application health: `http://127.0.0.1:8000/api/v1/health`
- Swagger UI: `http://127.0.0.1:8000/docs`

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
```

## Configuration

All configuration is read from environment variables or a local `.env` file. Copy `.env.example` to `.env` and add provider credentials only to the untracked `.env` file. Never commit real credentials.

Process one document from the command line:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m app.cli <file> <document-type> --output sample_outputs\result.json
```

Valid document types are `invoice`, `balance_sheet`, `profit_and_loss`, and `cash_flow_statement`.

See `docs/architecture.md` for the system design, `docs/api.md` for the REST contract, `docs/financial-validation-rules.md` for reconciliation behavior, and `docs/deployment.md` for publishing instructions.
