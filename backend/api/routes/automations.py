from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from backend.api.dependencies import get_automation_service, get_current_user, require_admin_user
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.schemas.automation import ActiveUpdate, AlertCreate, AutomationCreate, AutomationUpdate, SavedAnalyticsQueryCreate
from backend.services.automation_service import AutomationError, AutomationService
from backend.services.dataset_access_service import DatasetAccessError


router = APIRouter(prefix="/automations", tags=["automations"])
snapshots_router = APIRouter(prefix="/datasets", tags=["dataset snapshots"])


def _raise_api_error(error: Exception) -> None:
    if isinstance(error, DatasetAccessError):
        raise AppError(404, "dataset_not_found", "Dataset was not found or is not available in this workspace.") from error
    if isinstance(error, PermissionError):
        raise AppError(403, "automation_forbidden", str(error)) from error
    if isinstance(error, AutomationError):
        status = 404 if "not found" in str(error).lower() else 400
        raise AppError(status, "invalid_automation_request", str(error)) from error
    if isinstance(error, (ValueError, LookupError)):
        raise AppError(400, "invalid_automation_request", str(error)) from error
    raise AppError(500, "automation_error", "An automation operation could not be completed.") from error


@router.get("/queries")
def list_saved_queries(
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> list[dict[str, Any]]:
    try:
        return service.list_saved_queries(user, workspace_id)
    except Exception as error:
        _raise_api_error(error)


@router.post("/queries", status_code=201)
def create_saved_query(
    payload: SavedAnalyticsQueryCreate,
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    try:
        return service.create_saved_query(user=user, **payload.model_dump())
    except Exception as error:
        _raise_api_error(error)


@router.get("/alerts")
def list_alerts(
    workspace_id: str = Query(min_length=1, max_length=64),
    dataset_id: str | None = Query(default=None, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> list[dict[str, Any]]:
    try:
        return service.list_alerts(user, workspace_id, dataset_id)
    except Exception as error:
        _raise_api_error(error)


@router.get("")
def list_automations(
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> list[dict[str, Any]]:
    try:
        return service.list_automations(user, workspace_id)
    except Exception as error:
        _raise_api_error(error)


@router.post("", status_code=201)
def create_automation(
    payload: AutomationCreate,
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    try:
        return service.create_automation(
            user=user,
            workspace_id=payload.workspace_id,
            query_id=payload.saved_query_id,
            name=payload.name,
            frequency=payload.frequency,
            run_time=payload.run_time,
            timezone_name=payload.timezone,
            weekday=payload.weekday,
            day_of_month=payload.day_of_month,
            ai_summary=payload.ai_summary,
        )
    except Exception as error:
        _raise_api_error(error)


@router.get("/{automation_id}")
def get_automation(
    automation_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    try:
        return service.get_automation(user, workspace_id, automation_id)
    except Exception as error:
        _raise_api_error(error)


@router.patch("/{automation_id}")
def update_automation(
    automation_id: str,
    payload: AutomationUpdate,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    try:
        fields = payload.model_dump(exclude={"workspace_id"}, exclude_unset=True)
        if set(fields) == {"active"}:
            return service.set_active(user, workspace_id, automation_id, fields["active"])
        fields["timezone_name"] = fields.pop("timezone", None)
        return service.update_automation(user, workspace_id, automation_id, **fields)
    except Exception as error:
        _raise_api_error(error)


@router.delete("/{automation_id}")
def delete_automation(
    automation_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, bool]:
    try:
        service.delete_automation(user, workspace_id, automation_id)
        return {"deleted": True}
    except Exception as error:
        _raise_api_error(error)


@router.post("/{automation_id}/run", status_code=202)
def run_automation(
    automation_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    try:
        return service.run_now(user, workspace_id, automation_id)
    except Exception as error:
        _raise_api_error(error)


@router.get("/{automation_id}/runs")
def list_automation_runs(
    automation_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> list[dict[str, Any]]:
    try:
        return service.list_runs(user, workspace_id, automation_id)
    except Exception as error:
        _raise_api_error(error)


@router.get("/{automation_id}/runs/{run_id}/report.csv", response_class=PlainTextResponse)
def download_run_report(
    automation_id: str,
    run_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> PlainTextResponse:
    try:
        content = service.run_report_csv(user, workspace_id, automation_id, run_id)
        return PlainTextResponse(content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="automation-{automation_id}-run-{run_id}.csv"'})
    except Exception as error:
        _raise_api_error(error)


@router.post("/alerts", status_code=201)
def create_alert(
    payload: AlertCreate,
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    try:
        return service.create_alert(user=user, **payload.model_dump())
    except Exception as error:
        _raise_api_error(error)


@router.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: str,
    payload: ActiveUpdate,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    try:
        return service.set_alert_active(user, workspace_id, alert_id, payload.active)
    except Exception as error:
        _raise_api_error(error)


@router.delete("/alerts/{alert_id}")
def delete_alert(
    alert_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, bool]:
    try:
        service.delete_alert(user, workspace_id, alert_id)
        return {"deleted": True}
    except Exception as error:
        _raise_api_error(error)


@snapshots_router.get("/{dataset_id}/snapshots")
def list_dataset_snapshots(
    dataset_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: AutomationService = Depends(get_automation_service),
) -> list[dict[str, Any]]:
    try:
        return service.list_snapshots(user, workspace_id, dataset_id)
    except Exception as error:
        _raise_api_error(error)


@router.get("/admin/overview")
def automation_admin_overview(
    workspace_id: str | None = Query(default=None, max_length=64),
    admin: UserRecord = Depends(require_admin_user),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    _ = admin
    return service.repository.admin_overview(workspace_id)


@router.get("/admin/runs")
def automation_admin_runs(
    workspace_id: str | None = Query(default=None, max_length=64),
    status: str | None = Query(default=None, pattern="^(pending|running|completed|failed|canceled)$"),
    since: str | None = Query(default=None, max_length=40),
    until: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=100, ge=1, le=500),
    admin: UserRecord = Depends(require_admin_user),
    service: AutomationService = Depends(get_automation_service),
) -> list[dict[str, Any]]:
    _ = admin
    return service.repository.admin_runs(workspace_id=workspace_id, status=status, since=since, until=until, limit=limit)