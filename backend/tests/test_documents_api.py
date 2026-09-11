from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


DATASET = Path(__file__).parents[2] / "samples" / "dataset" / "New Dataset"


def test_document_api_returns_consistent_errors(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'errors.db').as_posix()}")

    with TestClient(create_app()) as client:
        invalid_type = client.post(
            "/api/v1/documents/process",
            data={"document_type": "unknown"},
            files={"file": ("document.txt", b"not a document", "text/plain")},
        )
        unsupported = client.post(
            "/api/v1/documents/process",
            data={"document_type": "invoice"},
            files={"file": ("document.txt", b"not a document", "text/plain")},
        )
        missing = client.get("/api/v1/documents/99999")

    assert invalid_type.status_code == 422
    assert invalid_type.json()["error"]["code"] == "INVALID_REQUEST"
    assert unsupported.status_code == 422
    assert unsupported.json() == {
        "error": {
            "code": "UNSUPPORTED_FILE_TYPE",
            "message": "Only PDF, JPG, and PNG documents are supported.",
        }
    }
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


@pytest.mark.integration
def test_process_list_retrieve_and_latest_document(tmp_path, monkeypatch) -> None:
    if not DATASET.exists():
        pytest.skip("Case-study sample dataset is not available.")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'documents.db').as_posix()}")
    sample = DATASET / "Invoices" / "batch1-1109.jpg"

    with TestClient(create_app()) as client:
        with sample.open("rb") as stream:
            processed = client.post(
                "/api/v1/documents/process",
                data={"document_type": "invoice"},
                files={"file": (sample.name, stream, "image/jpeg")},
            )
        listing = client.get("/api/v1/documents")
        record_id = processed.json()["id"]
        retrieved = client.get(f"/api/v1/documents/{record_id}")
        latest = client.get(f"/api/v1/documents/latest/{sample.name}")

    assert processed.status_code == 200
    assert processed.json()["result"]["processing_status"] == "PASS"
    assert processed.json()["result"]["validation"]["overall_status"] == "PASS"
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == record_id
    assert retrieved.json() == processed.json()
    assert latest.json() == processed.json()

