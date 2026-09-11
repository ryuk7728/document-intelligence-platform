from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import init_database
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_database()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API for financial-document extraction and validation.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=1000)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
    application.include_router(api_router, prefix="/api/v1")
    project_root = Path(__file__).resolve().parents[2]
    frontend_root = project_root / "frontend"
    templates = Jinja2Templates(directory=str(frontend_root / "templates"))
    application.mount("/static", StaticFiles(directory=str(frontend_root / "static")), name="static")

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request=request, name="dashboard.html")

    @application.get("/config.js", response_class=PlainTextResponse, include_in_schema=False)
    async def local_frontend_config() -> PlainTextResponse:
        return PlainTextResponse(
            'window.RUNTIME_CONFIG = Object.freeze({ API_BASE_URL: "" });\n',
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        message = errors[0].get("msg", "The request is invalid.") if errors else "The request is invalid."
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "INVALID_REQUEST", "message": message}},
        )
    return application


app = create_app()
