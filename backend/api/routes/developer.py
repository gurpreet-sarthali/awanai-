from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request

from backend.api.dependencies import (
    build_ai_service_for_user,
    get_current_user,
    get_developer_api_service,
    get_public_api_context,
    get_registry,
    get_webhook_service,
    get_workspace_repository,
)
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.repositories.dataset_registry_repository import DatasetNotFoundError, DatasetRegistryRepository
from backend.repositories.database_repository import DatabaseRepository
from backend.repositories.workspace_repository import WorkspaceRepository
from backend.schemas.analytics import AnalyticsRequest
from backend.schemas.developer import APIKeyCreateRequest, APIKeyRotateRequest, PublicQuestionRequest, WebhookCreateRequest, WebhookUpdateRequest
from backend.services.analytics_service import AnalyticsService, InvalidAnalyticsOperation
from backend.services.billing_service import UsageLimitExceededError
from backend.services.dataset_access_service import DatasetAccessError, DatasetAccessService
from backend.services.developer_service import DeveloperAPIContext, DeveloperAPIError, DeveloperAPIService, WebhookService
from backend.services.rate_limiter import AIRateLimitError


developer_router = APIRouter(prefix="/developer", tags=["developer API management"])
public_router = APIRouter(prefix="/public", tags=["public developer API"])


def _raise_developer_error(error: Exception) -> None:
    if isinstance(error, AppError):
        raise error
    if isinstance(error, DeveloperAPIError):
        raise AppError(error.status_code, error.code, error.message) from error
    if isinstance(error, UsageLimitExceededError):
        raise AppError(429, "USAGE_LIMIT_REACHED", str(error)) from error
    if isinstance(error, DatasetAccessError):
        raise AppError(404, "DATASET_NOT_FOUND", "Dataset was not found or is not accessible to this workspace.") from error
    if isinstance(error, (DatasetNotFoundError, InvalidAnalyticsOperation)):
        raise AppError(404 if isinstance(error, DatasetNotFoundError) else 422, "INVALID_ANALYTICS_REQUEST", str(error)) from error
    if isinstance(error, AIRateLimitError):
        raise AppError(429, "RATE_LIMITED", "The AI request limit has been reached.") from error
    if isinstance(error, PermissionError):
        raise AppError(403, "FORBIDDEN", "Workspace permission is required for this operation.") from error
    raise AppError(500, "DEVELOPER_API_ERROR", "The developer API operation could not be completed.") from error


def _management_access(service: DeveloperAPIService, user: UserRecord, workspace_id: str) -> None:
    service._require_key_admin(workspace_id, user)


@developer_router.get("/api-keys")
def list_api_keys(
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: DeveloperAPIService = Depends(get_developer_api_service),
) -> dict[str, Any]:
    try:
        return {"keys": service.list_keys(user, workspace_id)}
    except Exception as error:
        _raise_developer_error(error)


@developer_router.post("/api-keys", status_code=201)
def create_api_key(
    payload: APIKeyCreateRequest,
    background_tasks: BackgroundTasks,
    user: UserRecord = Depends(get_current_user),
    service: DeveloperAPIService = Depends(get_developer_api_service),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, Any]:
    try:
        result = service.create_key(user=user, **payload.model_dump())
        webhook_service.emit_event(payload.workspace_id, "security.event", {"action": "api_key_created", "api_key_id": result["id"], "scopes": result["scopes"]}, background_tasks)
        return {"success": True, **result, "notice": "Copy this key now. It cannot be retrieved again."}
    except Exception as error:
        _raise_developer_error(error)


@developer_router.post("/api-keys/{key_id}/revoke")
def revoke_api_key(
    key_id: str,
    background_tasks: BackgroundTasks,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    service: DeveloperAPIService = Depends(get_developer_api_service),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, bool]:
    try:
        service.revoke_key(user, workspace_id, key_id)
        webhook_service.emit_event(workspace_id, "security.event", {"action": "api_key_revoked", "api_key_id": key_id}, background_tasks)
        return {"revoked": True}
    except Exception as error:
        _raise_developer_error(error)


@developer_router.post("/api-keys/{key_id}/rotate")
def rotate_api_key(
    key_id: str,
    payload: APIKeyRotateRequest,
    user: UserRecord = Depends(get_current_user),
    service: DeveloperAPIService = Depends(get_developer_api_service),
) -> dict[str, Any]:
    try:
        return {"success": True, **service.rotate_key(user, payload.workspace_id, key_id, payload.grace_seconds), "notice": "Copy the replacement key now. It cannot be retrieved again."}
    except Exception as error:
        _raise_developer_error(error)


@developer_router.get("/usage")
def get_developer_usage(
    workspace_id: str = Query(min_length=1, max_length=64),
    since: datetime | None = None,
    user: UserRecord = Depends(get_current_user),
    service: DeveloperAPIService = Depends(get_developer_api_service),
) -> dict[str, Any]:
    lower_bound = since or datetime.now(timezone.utc) - timedelta(days=30)
    try:
        return service.usage(user, workspace_id, lower_bound.isoformat())
    except Exception as error:
        _raise_developer_error(error)


@developer_router.get("/webhooks")
def list_webhooks(
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    developer_service: DeveloperAPIService = Depends(get_developer_api_service),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, Any]:
    try:
        _management_access(developer_service, user, workspace_id)
        return {"webhooks": webhook_service.list(workspace_id)}
    except Exception as error:
        _raise_developer_error(error)


@developer_router.post("/webhooks", status_code=201)
def create_webhook(
    payload: WebhookCreateRequest,
    user: UserRecord = Depends(get_current_user),
    developer_service: DeveloperAPIService = Depends(get_developer_api_service),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, Any]:
    try:
        _management_access(developer_service, user, payload.workspace_id)
        return {"success": True, **webhook_service.create(user=user, **payload.model_dump()), "notice": "Copy this signing secret now. It cannot be retrieved again."}
    except Exception as error:
        _raise_developer_error(error)


@developer_router.patch("/webhooks/{webhook_id}")
def update_webhook(
    webhook_id: str,
    payload: WebhookUpdateRequest,
    user: UserRecord = Depends(get_current_user),
    developer_service: DeveloperAPIService = Depends(get_developer_api_service),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, Any]:
    try:
        _management_access(developer_service, user, payload.workspace_id)
        updates = payload.model_dump(exclude={"workspace_id"}, exclude_unset=True)
        return webhook_service.update(user=user, workspace_id=payload.workspace_id, webhook_id=webhook_id, **updates)
    except Exception as error:
        _raise_developer_error(error)


@developer_router.delete("/webhooks/{webhook_id}")
def delete_webhook(
    webhook_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    developer_service: DeveloperAPIService = Depends(get_developer_api_service),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, bool]:
    try:
        _management_access(developer_service, user, workspace_id)
        webhook_service.delete(user, workspace_id, webhook_id)
        return {"deleted": True}
    except Exception as error:
        _raise_developer_error(error)


@developer_router.post("/webhooks/{webhook_id}/rotate-secret")
def rotate_webhook_secret(
    webhook_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    developer_service: DeveloperAPIService = Depends(get_developer_api_service),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, Any]:
    try:
        _management_access(developer_service, user, workspace_id)
        return {"success": True, **webhook_service.rotate_secret(user, workspace_id, webhook_id), "notice": "Copy this signing secret now. It cannot be retrieved again."}
    except Exception as error:
        _raise_developer_error(error)


@developer_router.post("/webhooks/{webhook_id}/test", status_code=202)
def test_webhook(
    webhook_id: str,
    background_tasks: BackgroundTasks,
    workspace_id: str = Query(min_length=1, max_length=64),
    user: UserRecord = Depends(get_current_user),
    developer_service: DeveloperAPIService = Depends(get_developer_api_service),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, Any]:
    try:
        _management_access(developer_service, user, workspace_id)
        if webhook_service.repository.get_webhook(webhook_id, workspace_id) is None:
            raise DeveloperAPIError(404, "WEBHOOK_NOT_FOUND", "Webhook was not found.")
        count = webhook_service.emit_event(workspace_id, "webhook.test", {"test": True}, background_tasks, event_id=f"test-{uuid4()}")
        return {"queued_deliveries": count, "test_event": True}
    except Exception as error:
        _raise_developer_error(error)


@developer_router.get("/webhooks/{webhook_id}/deliveries")
def webhook_deliveries(
    webhook_id: str,
    workspace_id: str = Query(min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    user: UserRecord = Depends(get_current_user),
    developer_service: DeveloperAPIService = Depends(get_developer_api_service),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> dict[str, Any]:
    try:
        _management_access(developer_service, user, workspace_id)
        return {"deliveries": webhook_service.list_deliveries(workspace_id, webhook_id, limit)}
    except Exception as error:
        _raise_developer_error(error)


def _scope(context: DeveloperAPIContext, scope: str) -> None:
    try:
        context.require_scope(scope)
    except DeveloperAPIError as error:
        _raise_developer_error(error)


def _envelope(request: Request, data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "request_id": getattr(request.state, "request_id", "")}


def _accessible_dataset(context: DeveloperAPIContext, dataset_id: str, registry: DatasetRegistryRepository, workspaces: WorkspaceRepository):
    access = DatasetAccessService(registry, context.user, workspaces)
    record = access.can_use_for_analytics(dataset_id)
    if not record.is_builtin and workspaces.get_shared_dataset(context.workspace_id, dataset_id) is None:
        raise DatasetAccessError("Dataset is not accessible in this workspace.")
    return record


def _dataset_metadata(record: Any) -> dict[str, Any]:
    def iso(value: Any) -> str | None:
        return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)
    return {
        "dataset_id": record.dataset_id,
        "dataset_name": record.dataset_name,
        "original_filename": record.original_filename,
        "row_count": record.row_count,
        "column_count": record.column_count,
        "status": record.status,
        "validation_status": record.validation_status,
        "is_builtin": record.is_builtin,
        "created_at": iso(record.created_at),
        "updated_at": iso(record.updated_at),
    }


@public_router.get("/datasets")
def public_list_datasets(
    request: Request,
    context: DeveloperAPIContext = Depends(get_public_api_context),
    registry: DatasetRegistryRepository = Depends(get_registry),
    workspaces: WorkspaceRepository = Depends(get_workspace_repository),
) -> dict[str, Any]:
    try:
        _scope(context, "datasets:read")
        access = DatasetAccessService(registry, context.user, workspaces)
        records = [record for record in access.list_accessible() if record.is_builtin or workspaces.get_shared_dataset(context.workspace_id, record.dataset_id)]
        return _envelope(request, {"datasets": [_dataset_metadata(record) for record in records]})
    except Exception as error:
        _raise_developer_error(error)


@public_router.get("/datasets/{dataset_id}")
def public_get_dataset(
    dataset_id: str,
    request: Request,
    context: DeveloperAPIContext = Depends(get_public_api_context),
    registry: DatasetRegistryRepository = Depends(get_registry),
    workspaces: WorkspaceRepository = Depends(get_workspace_repository),
) -> dict[str, Any]:
    try:
        _scope(context, "datasets:read")
        record = _accessible_dataset(context, dataset_id, registry, workspaces)
        return _envelope(request, _dataset_metadata(record))
    except Exception as error:
        _raise_developer_error(error)


@public_router.get("/workspace")
def public_get_workspace(
    request: Request,
    context: DeveloperAPIContext = Depends(get_public_api_context),
    workspaces: WorkspaceRepository = Depends(get_workspace_repository),
) -> dict[str, Any]:
    try:
        _scope(context, "workspace:read")
        record = workspaces.get_workspace(context.workspace_id)
        return _envelope(request, {"id": record.id, "name": record.name, "role": context.role})
    except Exception as error:
        _raise_developer_error(error)


@public_router.post("/analytics/query")
def public_analytics_query(
    payload: AnalyticsRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    context: DeveloperAPIContext = Depends(get_public_api_context),
    registry: DatasetRegistryRepository = Depends(get_registry),
    workspaces: WorkspaceRepository = Depends(get_workspace_repository),
    webhook_service: WebhookService = Depends(get_webhook_service),
    api_service: DeveloperAPIService = Depends(get_developer_api_service),
) -> dict[str, Any]:
    try:
        _scope(context, "analytics:run")
        _accessible_dataset(context, payload.dataset_id, registry, workspaces)
        usage = api_service.billing.check_usage_limit(context.workspace_id, "analytics_queries", 1)
        if not usage["allowed"]:
            raise DeveloperAPIError(429, "USAGE_LIMIT_REACHED", "Workspace analytics usage limit has been reached.")
        result = AnalyticsService(DatabaseRepository(registry.config, registry=registry)).run_operation(
            payload.operation, dataset_id=payload.dataset_id, column=payload.column, group_by=payload.group_by,
        )
        api_service.billing.record_usage(context.workspace_id, context.user.id, "analytics_query")
        webhook_service.emit_event(context.workspace_id, "analytics.completed", {"dataset_id": payload.dataset_id, "operation": payload.operation, "api_key_id": context.api_key_id}, background_tasks)
        return _envelope(request, {"operation": payload.operation, "dataset_id": payload.dataset_id, "result": result})
    except Exception as error:
        _raise_developer_error(error)


@public_router.post("/analytics/question")
def public_analytics_question(
    payload: PublicQuestionRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    context: DeveloperAPIContext = Depends(get_public_api_context),
    registry: DatasetRegistryRepository = Depends(get_registry),
    workspaces: WorkspaceRepository = Depends(get_workspace_repository),
    webhook_service: WebhookService = Depends(get_webhook_service),
    api_service: DeveloperAPIService = Depends(get_developer_api_service),
) -> dict[str, Any]:
    try:
        _scope(context, "analytics:question")
        _accessible_dataset(context, payload.dataset_id, registry, workspaces)
        for resource in ("analytics_queries", "ai_requests"):
            usage = api_service.billing.check_usage_limit(context.workspace_id, resource, 1)
            if not usage["allowed"]:
                raise DeveloperAPIError(429, "USAGE_LIMIT_REACHED", f"Workspace {resource} limit has been reached.")
        ai_service = build_ai_service_for_user(context.user, registry, workspaces)
        response = ai_service.analyze(payload.question, payload.dataset_id, user_id=context.user.id)
        api_service.billing.record_usage(context.workspace_id, context.user.id, "analytics_query")
        api_service.billing.record_usage(context.workspace_id, context.user.id, "ai_request")
        webhook_service.emit_event(context.workspace_id, "analytics.completed", {"dataset_id": payload.dataset_id, "operation": response.analysis.get("operation"), "api_key_id": context.api_key_id}, background_tasks)
        return _envelope(request, response.model_dump(mode="json"))
    except Exception as error:
        _raise_developer_error(error)