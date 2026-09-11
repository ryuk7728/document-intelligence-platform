from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Document Intelligence Platform"
    app_env: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/document_intelligence.db"
    cors_origins: str = "http://localhost:8000"
    allowed_hosts: str = "*"
    max_upload_pages: int = Field(default=3, ge=1, le=3)
    max_upload_size_mb: int = Field(default=15, ge=1, le=50)
    ocr_provider: str = "local"
    llm_provider: str = "not_configured"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    financial_absolute_tolerance: float = Field(default=1.0, ge=0)
    financial_relative_tolerance: float = Field(default=0.0001, ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
