"""Repository for plan, subscription, billing, and usage tracking."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from analytics.database import DatabaseConfig, connect

_log = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PlanRecord:
    plan_id: str
    name: str
    description: str | None
    price: float
    currency: str
    billing_interval: str
    active: bool
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
    feature_flags: dict[str, bool] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class SubscriptionRecord:
    subscription_id: str
    workspace_id: str
    user_id: str
    plan_id: str
    provider: str
    provider_customer_id: str | None = None
    provider_subscription_id: str | None = None
    status: str = "active"
    start_date: datetime | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    canceled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class UsageRecord:
    usage_id: str
    workspace_id: str
    user_id: str | None
    subscription_id: str | None
    event_type: str
    quantity: int
    metadata_json: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class InvoiceRecord:
    invoice_id: str
    workspace_id: str
    user_id: str
    subscription_id: str | None
    amount: float
    currency: str
    status: str
    provider: str
    invoice_reference: str | None = None
    billing_period_start: datetime | None = None
    billing_period_end: datetime | None = None
    created_at: datetime | None = None


class BillingRepository:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_plans (
                        id TEXT NOT NULL PRIMARY KEY,
                        plan_id TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        description TEXT NULL,
                        price REAL NOT NULL DEFAULT 0,
                        currency TEXT NOT NULL DEFAULT 'USD',
                        billing_interval TEXT NOT NULL DEFAULT 'monthly',
                        active INTEGER NOT NULL DEFAULT 1,
                        max_users INTEGER NULL,
                        max_workspaces INTEGER NULL,
                        max_datasets INTEGER NULL,
                        max_dataset_size_mb INTEGER NULL,
                        max_storage_mb INTEGER NULL,
                        max_analytics_queries INTEGER NULL,
                        max_ai_requests INTEGER NULL,
                        max_reports INTEGER NULL,
                        max_exports INTEGER NULL,
                        max_conversations INTEGER NULL,
                        feature_flags_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_subscriptions (
                        id TEXT NOT NULL PRIMARY KEY,
                        workspace_id TEXT NOT NULL UNIQUE,
                        user_id TEXT NOT NULL,
                        plan_id TEXT NOT NULL,
                        provider TEXT NOT NULL DEFAULT 'mock',
                        provider_customer_id TEXT NULL,
                        provider_subscription_id TEXT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        start_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        current_period_start TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        current_period_end TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                        canceled_at TIMESTAMP NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_usage_events (
                        id TEXT NOT NULL PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        user_id TEXT NULL,
                        subscription_id TEXT NULL,
                        event_type TEXT NOT NULL,
                        quantity INTEGER NOT NULL DEFAULT 1,
                        metadata_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_invoices (
                        id TEXT NOT NULL PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        subscription_id TEXT NULL,
                        amount REAL NOT NULL DEFAULT 0,
                        currency TEXT NOT NULL DEFAULT 'USD',
                        status TEXT NOT NULL DEFAULT 'pending',
                        provider TEXT NOT NULL DEFAULT 'mock',
                        invoice_reference TEXT NULL,
                        billing_period_start TIMESTAMP NULL,
                        billing_period_end TIMESTAMP NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_webhook_events (
                        id TEXT NOT NULL PRIMARY KEY,
                        provider TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        event_id TEXT NOT NULL UNIQUE,
                        payload_json TEXT NOT NULL,
                        processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            else:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_plans (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        plan_id VARCHAR(64) NOT NULL UNIQUE,
                        name VARCHAR(128) NOT NULL,
                        description TEXT NULL,
                        price DECIMAL(10,2) NOT NULL DEFAULT 0,
                        currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                        billing_interval VARCHAR(20) NOT NULL DEFAULT 'monthly',
                        active TINYINT(1) NOT NULL DEFAULT 1,
                        max_users INT NULL,
                        max_workspaces INT NULL,
                        max_datasets INT NULL,
                        max_dataset_size_mb INT NULL,
                        max_storage_mb INT NULL,
                        max_analytics_queries INT NULL,
                        max_ai_requests INT NULL,
                        max_reports INT NULL,
                        max_exports INT NULL,
                        max_conversations INT NULL,
                        feature_flags_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspace_subscriptions (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(64) NOT NULL UNIQUE,
                        user_id VARCHAR(64) NOT NULL,
                        plan_id VARCHAR(64) NOT NULL,
                        provider VARCHAR(32) NOT NULL DEFAULT 'mock',
                        provider_customer_id VARCHAR(128) NULL,
                        provider_subscription_id VARCHAR(128) NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        start_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        current_period_start TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        current_period_end TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        cancel_at_period_end TINYINT(1) NOT NULL DEFAULT 0,
                        canceled_at TIMESTAMP NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_usage_events (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(64) NOT NULL,
                        user_id VARCHAR(64) NULL,
                        subscription_id VARCHAR(64) NULL,
                        event_type VARCHAR(64) NOT NULL,
                        quantity INT NOT NULL DEFAULT 1,
                        metadata_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_billing_usage_workspace (workspace_id),
                        KEY idx_billing_usage_event (event_type),
                        KEY idx_billing_usage_created (created_at)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_invoices (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        workspace_id VARCHAR(64) NOT NULL,
                        user_id VARCHAR(64) NOT NULL,
                        subscription_id VARCHAR(64) NULL,
                        amount DECIMAL(10,2) NOT NULL DEFAULT 0,
                        currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        provider VARCHAR(32) NOT NULL DEFAULT 'mock',
                        invoice_reference VARCHAR(120) NULL,
                        billing_period_start TIMESTAMP NULL,
                        billing_period_end TIMESTAMP NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_billing_invoices_workspace (workspace_id),
                        KEY idx_billing_invoices_status (status)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_webhook_events (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        provider VARCHAR(32) NOT NULL,
                        event_type VARCHAR(64) NOT NULL,
                        event_id VARCHAR(128) NOT NULL UNIQUE,
                        payload_json TEXT NOT NULL,
                        processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_billing_webhook_provider (provider),
                        KEY idx_billing_webhook_event (event_id)
                    )
                    """
                )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def upsert_plan(self, plan: dict[str, Any]) -> PlanRecord:
        plan_id = str(plan["plan_id"])
        connection = connect(self.config)
        if self.config.uses_sqlite:
            query = """
                INSERT INTO billing_plans (
                    id, plan_id, name, description, price, currency, billing_interval,
                    active, max_users, max_workspaces, max_datasets, max_dataset_size_mb,
                    max_storage_mb, max_analytics_queries, max_ai_requests, max_reports,
                    max_exports, max_conversations, feature_flags_json, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT(plan_id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    price = excluded.price,
                    currency = excluded.currency,
                    billing_interval = excluded.billing_interval,
                    active = excluded.active,
                    max_users = excluded.max_users,
                    max_workspaces = excluded.max_workspaces,
                    max_datasets = excluded.max_datasets,
                    max_dataset_size_mb = excluded.max_dataset_size_mb,
                    max_storage_mb = excluded.max_storage_mb,
                    max_analytics_queries = excluded.max_analytics_queries,
                    max_ai_requests = excluded.max_ai_requests,
                    max_reports = excluded.max_reports,
                    max_exports = excluded.max_exports,
                    max_conversations = excluded.max_conversations,
                    feature_flags_json = excluded.feature_flags_json,
                    updated_at = CURRENT_TIMESTAMP
            """
        else:
            query = """
                INSERT INTO billing_plans (
                    id, plan_id, name, description, price, currency, billing_interval,
                    active, max_users, max_workspaces, max_datasets, max_dataset_size_mb,
                    max_storage_mb, max_analytics_queries, max_ai_requests, max_reports,
                    max_exports, max_conversations, feature_flags_json, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    description = VALUES(description),
                    price = VALUES(price),
                    currency = VALUES(currency),
                    billing_interval = VALUES(billing_interval),
                    active = VALUES(active),
                    max_users = VALUES(max_users),
                    max_workspaces = VALUES(max_workspaces),
                    max_datasets = VALUES(max_datasets),
                    max_dataset_size_mb = VALUES(max_dataset_size_mb),
                    max_storage_mb = VALUES(max_storage_mb),
                    max_analytics_queries = VALUES(max_analytics_queries),
                    max_ai_requests = VALUES(max_ai_requests),
                    max_reports = VALUES(max_reports),
                    max_exports = VALUES(max_exports),
                    max_conversations = VALUES(max_conversations),
                    feature_flags_json = VALUES(feature_flags_json),
                    updated_at = CURRENT_TIMESTAMP
            """
        try:
            cursor = connection.cursor()
            cursor.execute(
                query,
                (
                    str(uuid4()),
                    plan_id,
                    plan["name"],
                    plan.get("description"),
                    float(plan.get("price", 0)),
                    plan.get("currency", "USD"),
                    plan.get("billing_interval", "monthly"),
                    int(bool(plan.get("active", True))),
                    plan.get("max_users"),
                    plan.get("max_workspaces"),
                    plan.get("max_datasets"),
                    plan.get("max_dataset_size_mb"),
                    plan.get("max_storage_mb"),
                    plan.get("max_analytics_queries"),
                    plan.get("max_ai_requests"),
                    plan.get("max_reports"),
                    plan.get("max_exports"),
                    plan.get("max_conversations"),
                    json.dumps(plan.get("feature_flags") or {}),
                ),
            )
            connection.commit()
            cursor.close()
            return self.get_plan(plan_id)
        finally:
            connection.close()

    def get_plan(self, plan_id: str) -> PlanRecord | None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM billing_plans WHERE plan_id = %s", (plan_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_plan(row)
        finally:
            connection.close()

    def list_plans(self) -> list[PlanRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM billing_plans ORDER BY price ASC, name ASC")
            rows = cursor.fetchall()
            return [self._row_to_plan(row) for row in rows]
        finally:
            connection.close()

    def get_subscription_for_workspace(self, workspace_id: str) -> SubscriptionRecord | None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM workspace_subscriptions WHERE workspace_id = %s", (workspace_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_subscription(row)
        finally:
            connection.close()

    def get_subscription(self, subscription_id: str) -> SubscriptionRecord | None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM workspace_subscriptions WHERE id = %s", (subscription_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_subscription(row)
        finally:
            connection.close()

    def create_or_update_subscription(self, *, workspace_id: str, user_id: str, plan_id: str, status: str = "active", provider: str = "mock", provider_customer_id: str | None = None, provider_subscription_id: str | None = None) -> SubscriptionRecord:
        existing = self.get_subscription_for_workspace(workspace_id)
        now = datetime.now(timezone.utc)
        if existing:
            connection = connect(self.config)
            try:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE workspace_subscriptions
                    SET plan_id = %s, provider = %s, provider_customer_id = %s, provider_subscription_id = %s,
                        status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE workspace_id = %s
                    """,
                    (plan_id, provider, provider_customer_id, provider_subscription_id, status, workspace_id),
                )
                connection.commit()
                cursor.close()
                return self.get_subscription_for_workspace(workspace_id)  # type: ignore[return-value]
            finally:
                connection.close()

        subscription_id = str(uuid4())
        start_date = now
        current_period_start = now
        current_period_end = now + timedelta(days=30)
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO workspace_subscriptions (
                    id, workspace_id, user_id, plan_id, provider, provider_customer_id,
                    provider_subscription_id, status, start_date, current_period_start,
                    current_period_end, cancel_at_period_end, canceled_at, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, NULL, %s, %s)
                """,
                (
                    subscription_id,
                    workspace_id,
                    user_id,
                    plan_id,
                    provider,
                    provider_customer_id,
                    provider_subscription_id,
                    status,
                    start_date,
                    current_period_start,
                    current_period_end,
                    start_date,
                    start_date,
                ),
            )
            connection.commit()
            cursor.close()
            return self.get_subscription(subscription_id)  # type: ignore[return-value]
        finally:
            connection.close()

    def update_subscription_status(self, workspace_id: str, status: str, cancel_at_period_end: bool = False) -> SubscriptionRecord | None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE workspace_subscriptions
                SET status = %s, cancel_at_period_end = %s, updated_at = CURRENT_TIMESTAMP
                WHERE workspace_id = %s
                """,
                (status, int(cancel_at_period_end), workspace_id),
            )
            connection.commit()
            cursor.close()
            return self.get_subscription_for_workspace(workspace_id)
        finally:
            connection.close()

    def record_usage(self, *, workspace_id: str, user_id: str | None, event_type: str, quantity: int = 1, metadata: dict[str, Any] | None = None, subscription_id: str | None = None) -> UsageRecord:
        usage_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO billing_usage_events (id, workspace_id, user_id, subscription_id, event_type, quantity, metadata_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    usage_id,
                    workspace_id,
                    user_id,
                    subscription_id,
                    event_type,
                    int(max(quantity, 0)),
                    json.dumps(metadata) if metadata else None,
                ),
            )
            connection.commit()
            cursor.close()
            return UsageRecord(
                usage_id=usage_id,
                workspace_id=workspace_id,
                user_id=user_id,
                subscription_id=subscription_id,
                event_type=event_type,
                quantity=max(quantity, 0),
                metadata_json=json.dumps(metadata) if metadata else None,
                created_at=datetime.now(timezone.utc),
            )
        finally:
            connection.close()

    def get_usage_total(self, workspace_id: str, event_type: str) -> int:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM billing_usage_events WHERE workspace_id = %s AND event_type = %s",
                (workspace_id, event_type),
            )
            value = cursor.fetchone()[0]
            return int(value or 0)
        finally:
            connection.close()

    def record_invoice(self, *, workspace_id: str, user_id: str, subscription_id: str | None, amount: float, currency: str, status: str, provider: str, invoice_reference: str | None = None, billing_period_start: datetime | None = None, billing_period_end: datetime | None = None) -> InvoiceRecord:
        invoice_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO billing_invoices (
                    id, workspace_id, user_id, subscription_id, amount, currency, status,
                    provider, invoice_reference, billing_period_start, billing_period_end
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    invoice_id,
                    workspace_id,
                    user_id,
                    subscription_id,
                    float(amount),
                    currency,
                    status,
                    provider,
                    invoice_reference,
                    billing_period_start,
                    billing_period_end,
                ),
            )
            connection.commit()
            cursor.close()
            return InvoiceRecord(
                invoice_id=invoice_id,
                workspace_id=workspace_id,
                user_id=user_id,
                subscription_id=subscription_id,
                amount=float(amount),
                currency=currency,
                status=status,
                provider=provider,
                invoice_reference=invoice_reference,
                billing_period_start=billing_period_start,
                billing_period_end=billing_period_end,
                created_at=datetime.now(timezone.utc),
            )
        finally:
            connection.close()

    def remember_webhook(self, *, provider: str, event_type: str, event_id: str, payload: dict[str, Any]) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO billing_webhook_events (id, provider, event_type, event_id, payload_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (str(uuid4()), provider, event_type, event_id, json.dumps(payload)),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def has_processed_event(self, event_id: str) -> bool:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM billing_webhook_events WHERE event_id = %s", (event_id,))
            return cursor.fetchone() is not None
        finally:
            connection.close()

    def get_admin_overview(self) -> dict[str, Any]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM workspace_subscriptions")
            total_subscribers = int((cursor.fetchone() or (0,))[0])
            cursor.execute("SELECT COUNT(*) FROM workspace_subscriptions WHERE status = 'active'")
            active_subscriptions = int((cursor.fetchone() or (0,))[0])
            cursor.execute("SELECT COUNT(*) FROM billing_plans")
            plans = int((cursor.fetchone() or (0,))[0])
            return {
                "total_subscribers": total_subscribers,
                "active_subscriptions": active_subscriptions,
                "total_plans": plans,
            }
        finally:
            connection.close()

    @staticmethod
    def _row_to_plan(row: Any) -> PlanRecord:
        feature_value = row["feature_flags_json"] if "feature_flags_json" in row.keys() else None
        feature_flags = json.loads(feature_value) if feature_value else {}
        return PlanRecord(
            plan_id=str(row["plan_id"]),
            name=str(row["name"]),
            description=row["description"],
            price=float(row["price"]),
            currency=str(row["currency"]),
            billing_interval=str(row["billing_interval"]),
            active=bool(row["active"]),
            max_users=row["max_users"],
            max_workspaces=row["max_workspaces"],
            max_datasets=row["max_datasets"],
            max_dataset_size_mb=row["max_dataset_size_mb"],
            max_storage_mb=row["max_storage_mb"],
            max_analytics_queries=row["max_analytics_queries"],
            max_ai_requests=row["max_ai_requests"],
            max_reports=row["max_reports"],
            max_exports=row["max_exports"],
            max_conversations=row["max_conversations"],
            feature_flags=feature_flags,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_subscription(row: Any) -> SubscriptionRecord:
        return SubscriptionRecord(
            subscription_id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            user_id=str(row["user_id"]),
            plan_id=str(row["plan_id"]),
            provider=str(row["provider"]),
            provider_customer_id=row["provider_customer_id"],
            provider_subscription_id=row["provider_subscription_id"],
            status=str(row["status"]),
            start_date=row["start_date"],
            current_period_start=row["current_period_start"],
            current_period_end=row["current_period_end"],
            cancel_at_period_end=bool(row["cancel_at_period_end"]),
            canceled_at=row["canceled_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
