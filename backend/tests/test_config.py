import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_supported_page_limit_is_capped_at_three() -> None:
    with pytest.raises(ValidationError):
        Settings(max_upload_pages=4)


def test_cors_origins_are_parsed() -> None:
    settings = Settings(cors_origins="https://frontend.example, http://localhost:8000")
    assert settings.cors_origin_list == [
        "https://frontend.example",
        "http://localhost:8000",
    ]


def test_allowed_hosts_are_parsed() -> None:
    settings = Settings(allowed_hosts="example.com, api.example.com")
    assert settings.allowed_host_list == ["example.com", "api.example.com"]
