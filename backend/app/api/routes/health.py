from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.database import database_ping
from app.schemas.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    if not database_ping():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "DATABASE_UNAVAILABLE", "message": "Database health check failed."},
        )
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        database="ok",
    )

