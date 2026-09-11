# REST API

Interactive OpenAPI documentation is available at `/docs` on the backend.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Service and database health |
| `POST` | `/api/v1/documents/process` | Upload, extract, validate, and persist a document |
| `GET` | `/api/v1/documents` | Paginated processed-document history |
| `GET` | `/api/v1/documents/{id}` | Complete stored result by record ID |
| `GET` | `/api/v1/documents/latest/{name}` | Latest stored result for a filename |

## Processing request

Send `multipart/form-data` with:

- `document_type`: `invoice`, `balance_sheet`, `profit_and_loss`, or `cash_flow_statement`
- `file`: PDF, JPG, JPEG, or PNG; no more than three pages and 15 MB by default

Example:

```bash
curl -X POST "http://localhost:8000/api/v1/documents/process" \
  -F "document_type=invoice" \
  -F "file=@invoice.jpg"
```

A successful response contains the database record ID and timestamp plus the complete processing result. Invalid requests use a stable error envelope:

```json
{
  "error": {
    "code": "UNSUPPORTED_FILE_TYPE",
    "message": "Only PDF, JPG, and PNG documents are supported."
  }
}
```

Financial mismatches do not make the request fail. They appear as `validation.overall_status = "FAIL"` in a successfully persisted processing result.
