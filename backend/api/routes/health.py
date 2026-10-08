import os
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_monitoring_service, get_repository, require_admin_user
from backend.core.config import settings
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.repositories.database_repository import DatabaseRepository
from backend.schemas.common import DatabaseHealthResponse, HealthResponse
from backend.services.monitoring_service import MonitoringService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse, summary="Check API health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="AskMyData API")


@router.get("/database", response_model=DatabaseHealthResponse, summary="Check database reachability")
def database_health(repository: DatabaseRepository = Depends(get_repository)) -> DatabaseHealthResponse:
    try:
        repository.check_connection()
    except Exception as error:
        raise AppError(503, "database_unavailable", "The database service is unavailable.") from error
    return DatabaseHealthResponse(status="ok", database="reachable")


@router.get("/system", summary="Full system health check (all components)")
def system_health(repository: DatabaseRepository = Depends(get_repository)) -> dict:
    """Returns a detailed status report for all system components."""
    report: dict = {
        "status": "ok",
        "app_env": settings.app_env,
        "version": "1.0.0",
        "checks": {},
    }

    # Database
    try:
        t0 = time.perf_counter()
        repository.check_connection()
        report["checks"]["database"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
    except Exception as exc:
        report["checks"]["database"] = {"status": "error", "detail": str(exc)}
        report["status"] = "degraded"

    # Gemini API key
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key and gemini_key not in ("your_api_key_here", "YOUR_GEMINI_API_KEY_HERE"):
        report["checks"]["gemini"] = {"status": "configured"}
    else:
        report["checks"]["gemini"] = {"status": "not_configured"}
        report["status"] = "degraded"

    # Google OAuth
    if settings.google_client_id and settings.google_client_secret:
        report["checks"]["google_oauth"] = {"status": "configured"}
    else:
        report["checks"]["google_oauth"] = {"status": "not_configured"}

    # Upload directory
    upload_dir = Path(settings.dataset_uploads_dir)
    if upload_dir.exists() and os.access(upload_dir, os.W_OK):
        report["checks"]["upload_dir"] = {"status": "ok", "path": str(upload_dir.resolve())}
    else:
        report["checks"]["upload_dir"] = {"status": "not_writable", "path": str(upload_dir.resolve())}
        report["status"] = "degraded"

    return report


@router.get("/detailed", summary="Admin-only detailed system telemetry and metrics")
def detailed_system_health(
    admin_user: UserRecord = Depends(require_admin_user),
    repository: DatabaseRepository = Depends(get_repository),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict:
    """Admin-only detailed system health metrics including error rates, active sessions, and database latency."""
    base_report = system_health(repository)
    overview_stats = monitoring_service.repository.get_overview_stats(days=1)
    
    base_report["telemetry"] = {
        "active_users_24h": overview_stats["dau"],
        "total_requests_24h": overview_stats["total_ai_requests"],
        "error_count_24h": overview_stats["total_errors"],
        "avg_ai_latency_ms": overview_stats["avg_ai_response_time_ms"],
        "ai_helpfulness_rate": overview_stats["ai_helpfulness_rate"],
        "retention_policy": {
            "usage_log_retention_days": settings.usage_log_retention_days,
            "error_log_retention_days": settings.error_log_retention_days,
        },
    }
    return base_report