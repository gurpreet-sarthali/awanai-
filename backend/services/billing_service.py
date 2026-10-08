"""Billing and usage service for SaaS plan management."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.repositories.billing_repository import BillingRepository, PlanRecord, SubscriptionRecord

_log = logging.getLogger(__name__)


class UsageLimitExceededError(RuntimeError):
    pass


class SubscriptionNotFoundError(LookupError):
    pass


class BillingService:
    DEFAULT_PLAN_ID = "free"
    RESOURCE_LIMITS = {
        "ai_requests": "max_ai_requests",
        "gemini_requests": "max_ai_requests",
        "analytics_queries": "max_analytics_queries",
        "reports": "max_reports",
        "exports": "max_exports",
        "conversations": "max_conversations",
        "datasets": "max_datasets",
        "storage_mb": "max_storage_mb",
    }
    USAGE_EVENT_ALIASES = {
        "ai_request": "ai_requests",
        "gemini_request": "ai_requests",
        "analytics_query": "analytics_queries",
        "analysis_started": "analytics_queries",
        "report_generated": "reports",
        "export_generated": "exports",
        "conversation_created": "conversations",
        "dataset_uploaded": "datasets",
    }

    def __init__(self, repository: BillingRepository) -> None:
        self.repository = repository

    def ensure_default_plans(self) -> list[PlanRecord]:
        plans = [
            {
                "plan_id": "free",
                "name": "Free",
                "description": "Starter access with safe usage limits.",
                "price": 0.0,
                "currency": "USD",
                "billing_interval": "monthly",
                "active": True,
                "max_users": 3,
                "max_workspaces": 2,
                "max_datasets": 2,
                "max_dataset_size_mb": 25,
                "max_storage_mb": 1024,
                "max_analytics_queries": 50,
                "max_ai_requests": 25,
                "max_reports": 3,
                "max_exports": 2,
                "max_conversations": 8,
                "feature_flags": {
                    "ai_analytics": True,
                    "advanced_analytics": False,
                    "team_workspaces": True,
                    "scheduled_analytics": False,
                    "developer_api": False,
                    "custom_roles": False,
                    "audit_logs": False,
                    "advanced_security": False,
                },
            },
            {
                "plan_id": "pro",
                "name": "Pro",
                "description": "For individuals who need more AI and analytics capacity.",
                "price": 19.0,
                "currency": "USD",
                "billing_interval": "monthly",
                "active": True,
                "max_users": 10,
                "max_workspaces": 5,
                "max_datasets": 20,
                "max_dataset_size_mb": 500,
                "max_storage_mb": 10000,
                "max_analytics_queries": 2500,
                "max_ai_requests": 1000,
                "max_reports": 50,
                "max_exports": 50,
                "max_conversations": 200,
                "feature_flags": {
                    "ai_analytics": True,
                    "advanced_analytics": True,
                    "team_workspaces": True,
                    "scheduled_analytics": True,
                    "developer_api": True,
                    "custom_roles": False,
                    "audit_logs": True,
                    "advanced_security": False,
                },
            },
            {
                "plan_id": "team",
                "name": "Team",
                "description": "Shared workspace access for teams and collaborative analysis.",
                "price": 49.0,
                "currency": "USD",
                "billing_interval": "monthly",
                "active": True,
                "max_users": 25,
                "max_workspaces": 10,
                "max_datasets": 100,
                "max_dataset_size_mb": 1000,
                "max_storage_mb": 50000,
                "max_analytics_queries": 10000,
                "max_ai_requests": 5000,
                "max_reports": 200,
                "max_exports": 200,
                "max_conversations": 1000,
                "feature_flags": {
                    "ai_analytics": True,
                    "advanced_analytics": True,
                    "team_workspaces": True,
                    "scheduled_analytics": True,
                    "developer_api": True,
                    "custom_roles": True,
                    "audit_logs": True,
                    "advanced_security": True,
                },
            },
            {
                "plan_id": "enterprise",
                "name": "Enterprise",
                "description": "Advanced governance, security, and enterprise support.",
                "price": 199.0,
                "currency": "USD",
                "billing_interval": "monthly",
                "active": True,
                "max_users": 200,
                "max_workspaces": 50,
                "max_datasets": 500,
                "max_dataset_size_mb": 5000,
                "max_storage_mb": 250000,
                "max_analytics_queries": 100000,
                "max_ai_requests": 25000,
                "max_reports": 1000,
                "max_exports": 1000,
                "max_conversations": 5000,
                "feature_flags": {
                    "ai_analytics": True,
                    "advanced_analytics": True,
                    "team_workspaces": True,
                    "scheduled_analytics": True,
                    "developer_api": True,
                    "custom_roles": True,
                    "audit_logs": True,
                    "advanced_security": True,
                },
            },
        ]
        results: list[PlanRecord] = []
        for payload in plans:
            results.append(self.repository.upsert_plan(payload))
        return results

    def list_plans(self) -> list[PlanRecord]:
        return self.repository.list_plans()

    def upsert_plan(self, *, plan_id: str, name: str, description: str | None, price: float, currency: str, billing_interval: str, active: bool, max_users: int | None = None, max_workspaces: int | None = None, max_datasets: int | None = None, max_dataset_size_mb: int | None = None, max_storage_mb: int | None = None, max_analytics_queries: int | None = None, max_ai_requests: int | None = None, max_reports: int | None = None, max_exports: int | None = None, max_conversations: int | None = None, feature_flags: dict[str, bool] | None = None) -> PlanRecord:
        payload = {
            "plan_id": plan_id,
            "name": name,
            "description": description,
            "price": price,
            "currency": currency,
            "billing_interval": billing_interval,
            "active": active,
            "max_users": max_users,
            "max_workspaces": max_workspaces,
            "max_datasets": max_datasets,
            "max_dataset_size_mb": max_dataset_size_mb,
            "max_storage_mb": max_storage_mb,
            "max_analytics_queries": max_analytics_queries,
            "max_ai_requests": max_ai_requests,
            "max_reports": max_reports,
            "max_exports": max_exports,
            "max_conversations": max_conversations,
            "feature_flags": feature_flags or {},
        }
        return self.repository.upsert_plan(payload)

    def get_plan(self, plan_id: str) -> PlanRecord:
        plan = self.repository.get_plan(plan_id)
        if plan is None:
            raise SubscriptionNotFoundError(f"Plan `{plan_id}` not found.")
        return plan

    def get_or_create_workspace_subscription(self, *, workspace_id: str, user_id: str, plan_id: str | None = None, status: str = "active", provider: str = "mock", provider_customer_id: str | None = None, provider_subscription_id: str | None = None) -> SubscriptionRecord:
        if plan_id is None:
            plan_id = self.DEFAULT_PLAN_ID
        self.get_plan(plan_id)
        return self.repository.create_or_update_subscription(
            workspace_id=workspace_id,
            user_id=user_id,
            plan_id=plan_id,
            status=status,
            provider=provider,
            provider_customer_id=provider_customer_id,
            provider_subscription_id=provider_subscription_id,
        )

    def get_workspace_subscription(self, workspace_id: str) -> SubscriptionRecord:
        subscription = self.repository.get_subscription_for_workspace(workspace_id)
        if subscription is None:
            raise SubscriptionNotFoundError(f"Subscription for workspace `{workspace_id}` not found.")
        return subscription

    def has_feature(self, workspace_id: str, feature_name: str) -> bool:
        subscription = self.repository.get_subscription_for_workspace(workspace_id)
        plan = self.repository.get_plan(subscription.plan_id) if subscription else self.repository.get_plan(self.DEFAULT_PLAN_ID)
        if plan is None:
            return False
        flags = plan.feature_flags or {}
        return bool(flags.get(feature_name, False))

    def get_plan_for_workspace(self, workspace_id: str) -> PlanRecord:
        subscription = self.repository.get_subscription_for_workspace(workspace_id)
        if subscription is None:
            plan = self.repository.get_plan(self.DEFAULT_PLAN_ID)
            if plan is None:
                self.ensure_default_plans()
                plan = self.repository.get_plan(self.DEFAULT_PLAN_ID)
            return plan
        plan = self.repository.get_plan(subscription.plan_id)
        if plan is None:
            self.ensure_default_plans()
            plan = self.repository.get_plan(subscription.plan_id)
        return plan

    def check_usage_limit(self, workspace_id: str, resource_type: str, requested_quantity: int = 1) -> dict[str, Any]:
        canonical = self.USAGE_EVENT_ALIASES.get(resource_type, resource_type)
        plan = self.get_plan_for_workspace(workspace_id)
        limit_field = self.RESOURCE_LIMITS.get(canonical)
        if limit_field is None:
            return {"allowed": True, "resource_type": canonical, "limit": None, "used": 0, "requested_quantity": requested_quantity}
        limit = getattr(plan, limit_field, None)
        if limit is None:
            return {"allowed": True, "resource_type": canonical, "limit": None, "used": 0, "requested_quantity": requested_quantity}
        used = self.repository.get_usage_total(workspace_id, canonical)
        allowed = (used + int(max(requested_quantity, 0))) <= int(limit)
        return {
            "allowed": allowed,
            "resource_type": canonical,
            "limit": int(limit),
            "used": int(used),
            "remaining": max(int(limit) - int(used), 0),
            "requested_quantity": int(max(requested_quantity, 0)),
        }

    def record_usage(self, workspace_id: str, user_id: str, event_type: str, quantity: int = 1, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        resource_type = self.USAGE_EVENT_ALIASES.get(event_type, event_type)

        if resource_type in self.RESOURCE_LIMITS:
            limit_check = self.check_usage_limit(workspace_id, resource_type, requested_quantity=max(quantity, 1))
            if not limit_check["allowed"]:
                raise UsageLimitExceededError(f"{resource_type.replace('_', ' ').title()} limit reached for this workspace.")

        subscription = self.repository.get_subscription_for_workspace(workspace_id)
        usage = self.repository.record_usage(
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=resource_type,
            quantity=max(quantity, 0),
            metadata=metadata,
            subscription_id=subscription.subscription_id if subscription else None,
        )
        return {
            "usage_id": usage.usage_id,
            "event_type": usage.event_type,
            "quantity": usage.quantity,
            "allowed": True,
        }

    def change_plan(self, workspace_id: str, user_id: str, new_plan_id: str) -> SubscriptionRecord:
        subscription = self.repository.get_subscription_for_workspace(workspace_id)
        if subscription is None:
            return self.get_or_create_workspace_subscription(workspace_id=workspace_id, user_id=user_id, plan_id=new_plan_id, status="active")
        self.get_plan(new_plan_id)
        self.repository.create_or_update_subscription(
            workspace_id=workspace_id,
            user_id=user_id,
            plan_id=new_plan_id,
            status=subscription.status or "active",
            provider=subscription.provider,
            provider_customer_id=subscription.provider_customer_id,
            provider_subscription_id=subscription.provider_subscription_id,
        )
        updated = self.repository.get_subscription_for_workspace(workspace_id)
        if updated is None:
            raise SubscriptionNotFoundError(f"Subscription for workspace `{workspace_id}` could not be updated.")
        return updated

    def cancel_subscription(self, workspace_id: str, user_id: str) -> SubscriptionRecord:
        subscription = self.repository.get_subscription_for_workspace(workspace_id)
        if subscription is None:
            raise SubscriptionNotFoundError(f"Subscription for workspace `{workspace_id}` not found.")
        if subscription.user_id != user_id:
            raise PermissionError("Only the workspace owner can cancel the subscription.")
        updated = self.repository.update_subscription_status(workspace_id, "canceled", cancel_at_period_end=True)
        if updated is None:
            raise SubscriptionNotFoundError(f"Subscription for workspace `{workspace_id}` could not be canceled.")
        return updated

    def resume_subscription(self, workspace_id: str, user_id: str) -> SubscriptionRecord:
        subscription = self.repository.get_subscription_for_workspace(workspace_id)
        if subscription is None:
            raise SubscriptionNotFoundError(f"Subscription for workspace `{workspace_id}` not found.")
        if subscription.user_id != user_id:
            raise PermissionError("Only the workspace owner can resume the subscription.")
        updated = self.repository.update_subscription_status(workspace_id, "active", cancel_at_period_end=False)
        if updated is None:
            raise SubscriptionNotFoundError(f"Subscription for workspace `{workspace_id}` could not be resumed.")
        return updated

    def get_usage_summary(self, workspace_id: str) -> dict[str, Any]:
        plan = self.get_plan_for_workspace(workspace_id)
        usage = {
            "workspace_id": workspace_id,
            "plan_id": plan.plan_id,
            "usage": {},
        }
        for resource_type, field in self.RESOURCE_LIMITS.items():
            limit = getattr(plan, field, None)
            if limit is None:
                continue
            usage["usage"][resource_type] = {
                "used": self.repository.get_usage_total(workspace_id, resource_type),
                "limit": int(limit),
                "remaining": max(int(limit) - self.repository.get_usage_total(workspace_id, resource_type), 0),
            }
        return usage

    def create_mock_checkout(self, workspace_id: str, plan_id: str, user_id: str) -> dict[str, Any]:
        self.get_plan(plan_id)
        self.get_or_create_workspace_subscription(workspace_id=workspace_id, user_id=user_id, plan_id=plan_id, status="trialing")
        return {
            "provider": "mock",
            "mode": "development",
            "checkout_url": f"/billing/mock/checkout/{workspace_id}/{plan_id}",
            "status": "requires_verification",
            "message": "Development mode is active; no real payment was processed.",
        }

    def process_webhook(self, provider: str, payload: dict[str, Any], signature: str | None = None) -> dict[str, Any]:
        event_id = str(payload.get("id") or payload.get("event_id") or payload.get("data", {}).get("id") or f"{provider}-{datetime.now(timezone.utc).timestamp()}")
        event_type = str(payload.get("type") or payload.get("event_type") or "subscription.updated")
        if signature is not None and provider.lower() == "stripe":
            # In a real provider this would verify the signature. This mock path is intentionally safe and development-only.
            if not signature:
                raise PermissionError("Invalid billing webhook signature.")
        if self.repository.has_processed_event(event_id):
            return {"status": "ignored", "event_id": event_id}
        self.repository.remember_webhook(provider=provider, event_type=event_type, event_id=event_id, payload=payload)
        return {"status": "accepted", "event_id": event_id, "event_type": event_type}
