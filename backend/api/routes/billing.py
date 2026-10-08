from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import get_billing_service, get_current_user, get_workspace_service, require_admin_user
from backend.core.user_model import UserRecord
from backend.schemas.billing import BillingOverviewResponse, BillingUsageResponse, BillingWebhookRequest, CheckoutResponse, PlanResponse, SubscriptionResponse, UsageLimitResponse
from backend.services.billing_service import UsageLimitExceededError
from backend.services.workspace_service import RolePermissions

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _serialize_plan(plan: Any) -> PlanResponse:
    return PlanResponse(
        plan_id=plan.plan_id,
        name=plan.name,
        description=plan.description,
        price=float(plan.price),
        currency=plan.currency,
        billing_interval=plan.billing_interval,
        active=bool(plan.active),
        max_users=plan.max_users,
        max_workspaces=plan.max_workspaces,
        max_datasets=plan.max_datasets,
        max_dataset_size_mb=plan.max_dataset_size_mb,
        max_storage_mb=plan.max_storage_mb,
        max_analytics_queries=plan.max_analytics_queries,
        max_ai_requests=plan.max_ai_requests,
        max_reports=plan.max_reports,
        max_exports=plan.max_exports,
        max_conversations=plan.max_conversations,
        feature_flags=plan.feature_flags or {},
    )


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(service=Depends(get_billing_service)) -> list[PlanResponse]:
    return [_serialize_plan(plan) for plan in service.list_plans()]


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    workspace_id: str = Query(...),
    current_user: UserRecord = Depends(get_current_user),
    service=Depends(get_billing_service),
    workspace_service=Depends(get_workspace_service),
) -> SubscriptionResponse:
    workspace_service._require_role(workspace_id, current_user, min_role=RolePermissions.ADMIN)
    subscription = service.repository.get_subscription_for_workspace(workspace_id)
    if subscription is None:
        return SubscriptionResponse(
            subscription_id="",
            workspace_id=workspace_id,
            user_id=current_user.id,
            plan_id=service.DEFAULT_PLAN_ID,
            provider="mock",
            status="active",
            cancel_at_period_end=False,
            current_period_start=None,
            current_period_end=None,
            created_at=None,
            updated_at=None,
        )
    return SubscriptionResponse(
        subscription_id=subscription.subscription_id,
        workspace_id=subscription.workspace_id,
        user_id=subscription.user_id,
        plan_id=subscription.plan_id,
        provider=subscription.provider,
        status=subscription.status,
        cancel_at_period_end=subscription.cancel_at_period_end,
        current_period_start=subscription.current_period_start.isoformat() if subscription.current_period_start else None,
        current_period_end=subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        created_at=subscription.created_at.isoformat() if subscription.created_at else None,
        updated_at=subscription.updated_at.isoformat() if subscription.updated_at else None,
    )


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    workspace_id: str,
    plan_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service=Depends(get_billing_service),
    workspace_service=Depends(get_workspace_service),
) -> CheckoutResponse:
    workspace_service._require_role(workspace_id, current_user, min_role=RolePermissions.ADMIN)
    result = service.create_mock_checkout(workspace_id, plan_id, current_user.id)
    return CheckoutResponse(**result)


@router.post("/change-plan", response_model=SubscriptionResponse)
def change_plan(
    workspace_id: str,
    plan_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service=Depends(get_billing_service),
    workspace_service=Depends(get_workspace_service),
) -> SubscriptionResponse:
    workspace_service._require_role(workspace_id, current_user, min_role=RolePermissions.ADMIN)
    sub = service.change_plan(workspace_id, current_user.id, plan_id)
    return SubscriptionResponse(
        subscription_id=sub.subscription_id,
        workspace_id=sub.workspace_id,
        user_id=sub.user_id,
        plan_id=sub.plan_id,
        provider=sub.provider,
        status=sub.status,
        cancel_at_period_end=sub.cancel_at_period_end,
        current_period_start=sub.current_period_start.isoformat() if sub.current_period_start else None,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
        created_at=sub.created_at.isoformat() if sub.created_at else None,
        updated_at=sub.updated_at.isoformat() if sub.updated_at else None,
    )


@router.post("/cancel", response_model=SubscriptionResponse)
def cancel_subscription(
    workspace_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service=Depends(get_billing_service),
    workspace_service=Depends(get_workspace_service),
) -> SubscriptionResponse:
    workspace_service._require_role(workspace_id, current_user, min_role=RolePermissions.ADMIN)
    sub = service.cancel_subscription(workspace_id, current_user.id)
    return SubscriptionResponse(
        subscription_id=sub.subscription_id,
        workspace_id=sub.workspace_id,
        user_id=sub.user_id,
        plan_id=sub.plan_id,
        provider=sub.provider,
        status=sub.status,
        cancel_at_period_end=sub.cancel_at_period_end,
        current_period_start=sub.current_period_start.isoformat() if sub.current_period_start else None,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
        created_at=sub.created_at.isoformat() if sub.created_at else None,
        updated_at=sub.updated_at.isoformat() if sub.updated_at else None,
    )


@router.post("/resume", response_model=SubscriptionResponse)
def resume_subscription(
    workspace_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service=Depends(get_billing_service),
    workspace_service=Depends(get_workspace_service),
) -> SubscriptionResponse:
    workspace_service._require_role(workspace_id, current_user, min_role=RolePermissions.ADMIN)
    sub = service.resume_subscription(workspace_id, current_user.id)
    return SubscriptionResponse(
        subscription_id=sub.subscription_id,
        workspace_id=sub.workspace_id,
        user_id=sub.user_id,
        plan_id=sub.plan_id,
        provider=sub.provider,
        status=sub.status,
        cancel_at_period_end=sub.cancel_at_period_end,
        current_period_start=sub.current_period_start.isoformat() if sub.current_period_start else None,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
        created_at=sub.created_at.isoformat() if sub.created_at else None,
        updated_at=sub.updated_at.isoformat() if sub.updated_at else None,
    )


@router.get("/usage", response_model=BillingUsageResponse)
def get_usage(
    workspace_id: str = Query(...),
    current_user: UserRecord = Depends(get_current_user),
    service=Depends(get_billing_service),
    workspace_service=Depends(get_workspace_service),
) -> BillingUsageResponse:
    workspace_service._require_role(workspace_id, current_user, min_role=RolePermissions.VIEWER)
    summary = service.get_usage_summary(workspace_id)
    return BillingUsageResponse(workspace_id=workspace_id, plan_id=summary["plan_id"], usage=summary["usage"])


@router.get("/features", response_model=dict[str, bool])
def list_features(
    workspace_id: str = Query(...),
    current_user: UserRecord = Depends(get_current_user),
    service=Depends(get_billing_service),
    workspace_service=Depends(get_workspace_service),
) -> dict[str, bool]:
    workspace_service._require_role(workspace_id, current_user, min_role=RolePermissions.VIEWER)
    plan = service.get_plan_for_workspace(workspace_id)
    return plan.feature_flags or {}


@router.get("/check-limit", response_model=UsageLimitResponse)
def check_limit(
    workspace_id: str = Query(...),
    resource_type: str = Query(...),
    requested_quantity: int = Query(default=1, ge=1),
    current_user: UserRecord = Depends(get_current_user),
    service=Depends(get_billing_service),
    workspace_service=Depends(get_workspace_service),
) -> UsageLimitResponse:
    workspace_service._require_role(workspace_id, current_user, min_role=RolePermissions.VIEWER)
    result = service.check_usage_limit(workspace_id, resource_type, requested_quantity)
    return UsageLimitResponse(**result)


@router.post("/webhooks/{provider}")
def handle_webhook(provider: str, payload: BillingWebhookRequest, service=Depends(get_billing_service)) -> dict[str, Any]:
    if not payload.event_id:
        raise HTTPException(status_code=400, detail="Webhook event_id is required.")
    result = service.process_webhook(provider, payload.payload or {}, payload.signature)
    return {"status": result["status"], "event_id": result["event_id"], "event_type": result["event_type"]}


@router.get("/admin/overview", response_model=BillingOverviewResponse)
def admin_overview(admin_user: UserRecord = Depends(require_admin_user), service=Depends(get_billing_service)) -> BillingOverviewResponse:
    overview = service.repository.get_admin_overview()
    return BillingOverviewResponse(**overview)


@router.get("/admin/subscriptions")
def admin_subscriptions(admin_user: UserRecord = Depends(require_admin_user), service=Depends(get_billing_service)) -> list[dict[str, Any]]:
    subscriptions = service.repository.list_plans()
    return [{"plan_id": plan.plan_id, "name": plan.name, "active": plan.active} for plan in subscriptions]


@router.post("/record-usage")
def record_usage(
    workspace_id: str,
    user_id: str,
    event_type: str,
    quantity: int = 1,
    current_user: UserRecord = Depends(get_current_user),
    service=Depends(get_billing_service),
    workspace_service=Depends(get_workspace_service),
) -> dict[str, Any]:
    workspace_service._require_role(workspace_id, current_user, min_role=RolePermissions.VIEWER)
    try:
        return service.record_usage(workspace_id, user_id, event_type, quantity=quantity)
    except UsageLimitExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
