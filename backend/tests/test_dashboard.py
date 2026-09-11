from fastapi.testclient import TestClient

from app.main import create_app


def test_dashboard_and_static_assets_are_served(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'dashboard.db').as_posix()}")

    with TestClient(create_app()) as client:
        dashboard = client.get("/")
        stylesheet = client.get("/static/styles.css")
        javascript = client.get("/static/app.js")
        config = client.get("/config.js")

    assert dashboard.status_code == 200
    assert "Document Intelligence Workbench" in dashboard.text
    assert 'id="upload-form"' in dashboard.text
    assert stylesheet.status_code == 200
    assert "--accent: #f2b84b" in stylesheet.text
    assert javascript.status_code == 200
    assert 'api("/api/v1/documents?limit=25")' in javascript.text
    assert "`${apiBase}${path}`" in javascript.text
    assert config.status_code == 200
    assert 'API_BASE_URL: ""' in config.text
