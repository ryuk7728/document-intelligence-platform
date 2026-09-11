from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_reports_service_and_database_status(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "health.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Document Intelligence Platform",
        "version": "0.1.0",
        "database": "ok",
    }


def test_swagger_is_available(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "swagger.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    with TestClient(create_app()) as client:
        response = client.get("/docs")

    assert response.status_code == 200
    assert "Swagger UI" in response.text

