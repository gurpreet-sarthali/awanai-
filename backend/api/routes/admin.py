"""API routes for administrator platform monitoring, usage analytics, and system oversight."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_monitoring_service, get_workspace_service, require_admin_user
from backend.core.user_model import UserRecord
from backend.schemas.monitoring import AdminCleanupRequest
from backend.services.monitoring_service import MonitoringService
from backend.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/analytics")
def get_admin_analytics_overview(
    days: int = Query(default=30, ge=1, le=365),
    admin_user: UserRecord = Depends(require_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    """Get complete admin monitoring analytics overview data for dashboard."""
    return monitoring_service.get_admin_dashboard_data(days=days)


@router.get("/users/stats")
def get_user_stats(
    days: int = Query(default=30, ge=1, le=365),
    admin_user: UserRecord = Depends(require_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    """Get detailed user session & activity statistics."""
    overview = monitoring_service.repository.get_overview_stats(days=days)
    time_series = monitoring_service.repository.get_time_series_stats(days=days)
    return {
        "dau": overview["dau"],
        "wau": overview["wau"],
        "mau": overview["mau"],
        "total_users": overview["total_users"],
        "user_trends": [{"date": r["date"], "active_users": r["active_users"]} for r in time_series],
    }


@router.get("/datasets/stats")
def get_dataset_stats(
    days: int = Query(default=30, ge=1, le=365),
    admin_user: UserRecord = Depends(require_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    """Get dataset upload, deletion, and usage analytics."""
    overview = monitoring_service.repository.get_overview_stats(days=days)
    time_series = monitoring_service.repository.get_time_series_stats(days=days)
    return {
        "total_datasets": overview["total_datasets"],
        "uploaded_in_period": overview["uploaded_datasets_in_period"],
        "dataset_trends": [{"date": r["date"], "uploads": r["dataset_uploads"]} for r in time_series],
    }


@router.get("/ai/stats")
def get_ai_stats(
    days: int = Query(default=30, ge=1, le=365),
    admin_user: UserRecord = Depends(require_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    """Get Gemini AI usage, execution timing, and response helpfulness stats."""
    overview = monitoring_service.repository.get_overview_stats(days=days)
    recent_ai_feedback = monitoring_service.repository.get_ai_feedback_summary(limit=50)
    return {
        "total_ai_requests": overview["total_ai_requests"],
        "successful_ai_requests": overview["successful_ai_requests"],
        "avg_ai_response_time_ms": overview["avg_ai_response_time_ms"],
        "ai_helpfulness_rate": overview["ai_helpfulness_rate"],
        "recent_ai_ratings": recent_ai_feedback,
    }


@router.get("/errors")
def get_error_logs(
    limit: int = Query(default=50, ge=1, le=200),
    admin_user: UserRecord = Depends(require_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> list[dict[str, Any]]:
    """Retrieve recent application error logs."""
    return monitoring_service.repository.get_recent_errors(limit=limit)


@router.get("/feedback")
def get_user_feedback(
    limit: int = Query(default=50, ge=1, le=200),
    admin_user: UserRecord = Depends(require_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> list[dict[str, Any]]:
    """Retrieve recent user feedback submissions."""
    return monitoring_service.repository.get_recent_feedback(limit=limit)


@router.get("/workspace-roles")
def get_workspace_role_capabilities(
    admin_user: UserRecord = Depends(require_admin_user),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, Any]:
    """Expose Phase 19 enterprise workspace role capabilities used by admin tooling."""
    return workspace_service.get_role_capabilities()


@router.get("/workspaces/{workspace_id}/security-events")
def get_workspace_security_events(
    workspace_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    admin_user: UserRecord = Depends(require_admin_user),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> list[dict[str, Any]]:
    """Return security and collaboration events for a workspace as an audit trail."""
    events = workspace_service.list_workspace_audit_logs(workspace_id, admin_user, limit=limit)
    return [
        {
            "id": event.id,
            "workspace_id": event.workspace_id,
            "user_id": event.user_id,
            "event_type": event.event_type,
            "metadata": event.metadata_json,
            "created_at": event.created_at.isoformat(),
            "user_name": event.user_name,
        }
        for event in events
    ]


@router.post("/retention/cleanup")
def trigger_retention_cleanup(
    payload: AdminCleanupRequest,
    admin_user: UserRecord = Depends(require_admin_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    """Trigger manual data retention log cleanup."""
    deleted_counts = monitoring_service.run_retention_cleanup(
        usage_days=payload.usage_retention_days,
        error_days=payload.error_retention_days,
    )
    return {"status": "success", "deleted": deleted_counts}
