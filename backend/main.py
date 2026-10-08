"""FastAPI application entry point for AskMyData Phase 16 (Monitoring, Analytics & Feedback)."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.dependencies import get_monitoring_service
from backend.api.routes import admin, ai, analytics, auth, automations, billing, chat, dataset, datasets, developer, feedback, health, nlsql, visualization, workspaces
from backend.core.config import settings
from backend.core.logging import configure_logging
from backend.exceptions.handlers import AppError, app_error_handler, unexpected_error_handler, validation_error_handler

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AskMyData API",
    version="1.0.0",
    description="AI-powered Natural Language Data Analytics Platform API.",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

results_directory = Path(__file__).resolve().parents[1] / "visualization" / "results"
results_directory.mkdir(parents=True, exist_ok=True)
app.mount("/api/v1/visualizations/files", StaticFiles(directory=results_directory), name="visualization-files")

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(dataset.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(visualization.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(nlsql.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(workspaces.invitations_router, prefix="/api/v1")
app.include_router(workspaces.notifications_router, prefix="/api/v1")
app.include_router(automations.router, prefix="/api/v1")
app.include_router(automations.snapshots_router, prefix="/api/v1")
app.include_router(developer.developer_router, prefix="/api/v1")
app.include_router(developer.public_router, prefix="/api/v1")
app.include_router(feedback.router)
app.include_router(billing.router)
app.include_router(admin.router)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


@app.middleware("http")
async def request_logging_and_security(request: Request, call_next):
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = correlation_id
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000

    logger.info(
        "api_request method=%s path=%s status=%s duration_ms=%.2f rid=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        correlation_id,
    )

    # Safely track error status codes in error_logs
    if response.status_code >= 400 and not request.url.path.startswith("/api/v1/health"):
        try:
            ms = get_monitoring_service()
            category = (
                "authentication" if "/auth" in request.url.path
                else "ai" if "/ai" in request.url.path or "/nlsql" in request.url.path
                else "dataset" if "/dataset" in request.url.path
                else "backend"
            )
            ms.capture_error(
                request_id=correlation_id,
                user_id=None,
                error_category=category,
                endpoint=request.url.path,
                http_status=response.status_code,
                error_message=f"HTTP {response.status_code} on {request.method} {request.url.path}",
                metadata={"duration_ms": duration_ms},
            )
        except Exception:
            pass

    response.headers["X-Request-ID"] = correlation_id
    if request.url.path.startswith("/api/v1/public/"):
        for header, value in getattr(request.state, "developer_rate_headers", {}).items():
            response.headers[header] = value
        try:
            developer_service = getattr(request.state, "developer_api_service", None)
            if developer_service is None:
                from backend.api.dependencies import get_developer_api_service
                developer_service = get_developer_api_service()
            developer_service.record_request(request, response.status_code, int(duration_ms), correlation_id)
        except Exception:
            logger.warning("developer_api_usage_logging_failed rid=%s", correlation_id)
    for header, value in _SECURITY_HEADERS.items():
        response.headers[header] = value
    return response