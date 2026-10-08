from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from backend.schemas.common import APIModel


class PlanResponse(APIModel):
    plan_id: str
    name: str
    description: str | None = None
    price: float
    currency: str = "USD"
    billing_interval: str = "monthly"
    active: bool = True
    max_users: int | None = None
    max_workspaces: int | None = None
    max_datasets: int | None = None
    max_dataset_size_mb: int | None = None
    max_storage_mb: int | None = None
    max_analytics_queries: int | None = None
    max_ai_requests: int | None = None
    max_reports: int | None = None
    max_exports: int | None = None
    max_conversations: int | None = None
    feature_flags: dict[str, bool] = Field(default_factory=dict)


class SubscriptionResponse(APIModel):
    subscription_id: str
    workspace_id: str
    user_id: str
    plan_id: str
    provider: str = "mock"
    status: str
    cancel_at_period_end: bool = False
    current_period_start: str | None = None
    current_period_end: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UsageLimitResponse(APIModel):
    allowed: bool
    resource_type: str
    limit: int | None = None
    used: int = 0
    remaining: int = 0
    requested_quantity: int = 1


class BillingUsageResponse(APIModel):
    workspace_id: str
    plan_id: str
    usage: dict[str, dict[str, Any]]


class CheckoutResponse(APIModel):
    provider: str
    mode: str
    checkout_url: str
    status: str
    message: str


class BillingWebhookRequest(APIModel):
    provider: Literal["stripe", "razorpay", "mock"] = "mock"
    event_type: str | None = None
    event_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None


class BillingOverviewResponse(APIModel):
    total_subscribers: int
    active_subscriptions: int
    total_plans: int
