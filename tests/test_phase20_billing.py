from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from analytics.database import DatabaseConfig
from backend.services.billing_service import BillingService, UsageLimitExceededError


@pytest.fixture
def billing_service():
    config = DatabaseConfig.from_environment()
    from backend.repositories.billing_repository import BillingRepository

    repo = BillingRepository(config)
    repo.ensure_schema()
    service = BillingService(repo)
    service.ensure_default_plans()
    return service


def test_default_free_plan_and_entitlements(billing_service):
    plans = billing_service.list_plans()
    free_plan = next(plan for plan in plans if plan.name.lower() == "free")
    assert free_plan.active is True
    assert free_plan.max_ai_requests > 0
    assert free_plan.max_datasets > 0

    result = billing_service.get_or_create_workspace_subscription(
        workspace_id="ws-free-01",
        user_id="user-001",
        plan_id=free_plan.plan_id,
        status="active",
    )

    assert result.plan_id == free_plan.plan_id
    assert billing_service.has_feature("ws-free-01", "team_workspaces") is True
    assert billing_service.has_feature("ws-free-01", "advanced_analytics") is False


def test_usage_limits_and_overage(billing_service):
    billing_service.upsert_plan(
        plan_id="plan-test-limited",
        name="Limited Test Plan",
        description="Small test plan",
        price=0,
        currency="USD",
        billing_interval="monthly",
        active=True,
        max_users=5,
        max_workspaces=2,
        max_datasets=2,
        max_dataset_size_mb=100,
        max_storage_mb=500,
        max_analytics_queries=2,
        max_ai_requests=2,
        max_reports=1,
        max_exports=1,
        max_conversations=10,
        feature_flags={"advanced_analytics": True, "team_workspaces": False},
    )
    billing_service.get_or_create_workspace_subscription(
        workspace_id="ws-limited-01",
        user_id="user-002",
        plan_id="plan-test-limited",
        status="active",
    )

    assert billing_service.check_usage_limit("ws-limited-01", "ai_requests", 1)["allowed"] is True
    billing_service.record_usage("ws-limited-01", "user-002", "ai_request", quantity=1)
    assert billing_service.check_usage_limit("ws-limited-01", "ai_requests", 1)["allowed"] is True
    billing_service.record_usage("ws-limited-01", "user-002", "ai_request", quantity=1)

    with pytest.raises(UsageLimitExceededError):
        billing_service.record_usage("ws-limited-01", "user-002", "ai_request", quantity=1)


def test_subscription_upgrade_and_cancellation_flow(billing_service):
    pro_plan = billing_service.upsert_plan(
        plan_id="plan-pro",
        name="Pro",
        description="Pro plan",
        price=19,
        currency="USD",
        billing_interval="monthly",
        active=True,
        max_users=10,
        max_workspaces=5,
        max_datasets=20,
        max_dataset_size_mb=500,
        max_storage_mb=5000,
        max_analytics_queries=2500,
        max_ai_requests=1000,
        max_reports=50,
        max_exports=50,
        max_conversations=50,
        feature_flags={"advanced_analytics": True, "team_workspaces": True},
    )

    sub = billing_service.get_or_create_workspace_subscription(
        workspace_id="ws-upgrade-01",
        user_id="user-003",
        plan_id="plan-pro",
        status="active",
    )

    updated = billing_service.change_plan("ws-upgrade-01", "user-003", "plan-pro")
    assert updated.plan_id == pro_plan.plan_id

    canceled = billing_service.cancel_subscription("ws-upgrade-01", "user-003")
    assert canceled.status in {"canceled", "cancel_at_period_end"}

    resumed = billing_service.resume_subscription("ws-upgrade-01", "user-003")
    assert resumed.status == "active"
