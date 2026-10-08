"""Secure orchestration for scheduled, data-grounded analytics workflows."""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
import json
import logging
import math
import time
from datetime import datetime, time as local_time, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import numpy as np

from analytics.csv_dataset import inspect_csv_dataframe
from analytics.database import DatabaseConfig
from backend.ai.nlsql.query_errors import SQLValidationError
from backend.core.config import settings
from backend.core.user_model import UserRecord
from backend.repositories.automation_repository import AutomationRepository
from backend.repositories.billing_repository import BillingRepository
from backend.repositories.database_repository import DatabaseRepository
from backend.repositories.dataset_registry_repository import DatasetRegistryRepository
from backend.repositories.user_repository import UserRepository
from backend.repositories.workspace_repository import WorkspaceRepository
from backend.services.analytics_service import ALLOWED_OPERATIONS, AnalyticsService
from backend.services.billing_service import BillingService, UsageLimitExceededError
from backend.services.dataset_access_service import DatasetAccessError, DatasetAccessService
from backend.services.gemini_service import GeminiService
from backend.services.rate_limiter import AIRateLimiter
from backend.services.workspace_service import RolePermissions, WorkspaceService


ALLOWED_OPERATORS = {">", "<", ">=", "<=", "=", "!=", "percentage_change", "percentage_point_change"}
SCHEDULE_FREQUENCIES = {"daily", "weekly", "monthly"}
MAX_JOB_ATTEMPTS = 3
_log = logging.getLogger(__name__)


class AutomationError(ValueError):
    pass


def next_run_datetime(
    frequency: str,
    run_time: str,
    timezone_name: str,
    *,
    after: datetime | None = None,
    weekday: int = 0,
    day_of_month: int = 1,
) -> datetime:
    if frequency not in SCHEDULE_FREQUENCIES:
        raise AutomationError("Frequency must be daily, weekly, or monthly.")
    try:
        zone = ZoneInfo(timezone_name)
        parsed_time = local_time.fromisoformat(run_time)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise AutomationError("A valid timezone and local run time are required.") from error
    if parsed_time.tzinfo is not None or not 0 <= weekday <= 6 or not 1 <= day_of_month <= 31:
        raise AutomationError("Invalid schedule time, weekday, or day of month.")

    now = after or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local_now = now.astimezone(zone)
    target_date = local_now.date()
    if frequency == "weekly":
        target_date += timedelta(days=(weekday - target_date.weekday()) % 7)
    elif frequency == "monthly":
        target_date = target_date.replace(day=min(day_of_month, calendar.monthrange(target_date.year, target_date.month)[1]))

    candidate = datetime.combine(target_date, parsed_time, tzinfo=zone)
    if candidate <= local_now:
        if frequency == "daily":
            target_date += timedelta(days=1)
        elif frequency == "weekly":
            target_date += timedelta(days=7)
        else:
            year, month = target_date.year, target_date.month + 1
            if month == 13:
                year, month = year + 1, 1
            target_date = target_date.replace(year=year, month=month, day=min(day_of_month, calendar.monthrange(year, month)[1]))
        candidate = datetime.combine(target_date, parsed_time, tzinfo=zone)

    # Move a nonexistent spring-forward wall time to the first valid local minute.
    round_trip = candidate.astimezone(timezone.utc).astimezone(zone)
    while round_trip.replace(tzinfo=None) < candidate.replace(tzinfo=None):
        candidate += timedelta(minutes=1)
        round_trip = candidate.astimezone(timezone.utc).astimezone(zone)
    return round_trip.astimezone(timezone.utc)


def profile_dataframe(dataframe: pd.DataFrame) -> tuple[dict[str, Any], str]:
    inspection = inspect_csv_dataframe(dataframe)
    numeric_stats: dict[str, dict[str, Any]] = {}
    categorical_distributions: dict[str, list[dict[str, Any]]] = {}
    for column in dataframe.columns:
        series = dataframe[column]
        name = str(column)
        if pd.api.types.is_numeric_dtype(series):
            values = pd.to_numeric(series, errors="coerce").dropna()
            values = values[values.map(math.isfinite)]
            if values.empty:
                continue
            q1, q3 = values.quantile(0.25), values.quantile(0.75)
            iqr = q3 - q1
            outliers = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum()) if iqr else 0
            numeric_stats[name] = {
                "min": float(values.min()),
                "max": float(values.max()),
                "mean": float(values.mean()),
                "median": float(values.median()),
                "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                "non_null": int(len(values)),
                "outlier_count_iqr": outliers,
                "outlier_rate_iqr": float(outliers / len(values)),
            }
        else:
            counts = series.astype("string").fillna("<missing>").value_counts(dropna=False).head(20)
            categorical_distributions[name] = [{"value": str(value), "count": int(count)} for value, count in counts.items()]

    missing_total = sum(inspection["missing_values"].values())
    cell_count = max(len(dataframe) * len(dataframe.columns), 1)
    profile = {
        **inspection,
        "missing_percent": float(missing_total * 100 / cell_count),
        "numeric_stats": numeric_stats,
        "categorical_distributions": categorical_distributions,
        "schema": [{"name": str(column), "dtype": str(dataframe[column].dtype)} for column in dataframe.columns],
    }
    schema_hash = hashlib.sha256(json.dumps(profile["schema"], sort_keys=True).encode()).hexdigest()
    return profile, schema_hash


def compare_profiles(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {"first_snapshot": True, "schema_changed": False, "row_delta": None, "new_categories": {}}
    previous_schema = {item["name"]: item.get("dtype") for item in previous.get("schema", [])}
    current_schema = {item["name"]: item.get("dtype") for item in current.get("schema", [])}
    changed_types = {
        name: {"from": previous_schema[name], "to": current_schema[name]}
        for name in previous_schema.keys() & current_schema.keys()
        if previous_schema[name] != current_schema[name]
    }
    new_categories: dict[str, list[str]] = {}
    old_distributions = previous.get("categorical_distributions", {})
    for column, values in current.get("categorical_distributions", {}).items():
        old_values = {item["value"] for item in old_distributions.get(column, [])}
        found = [item["value"] for item in values if item["value"] not in old_values and item["value"] != "<missing>"]
        if found:
            new_categories[column] = found
    previous_missing = float(previous.get("missing_percent", 0))
    return {
        "first_snapshot": False,
        "schema_changed": previous_schema.keys() != current_schema.keys() or bool(changed_types),
        "new_columns": sorted(current_schema.keys() - previous_schema.keys()),
        "removed_columns": sorted(previous_schema.keys() - current_schema.keys()),
        "type_changes": changed_types,
        "row_delta": int(current["rows"]) - int(previous.get("rows", 0)),
        "missing_percent_delta": float(current.get("missing_percent", 0)) - previous_missing,
        "new_categories": new_categories,
    }


def _metric_value(profile: dict[str, Any], metric: str, previous: dict[str, Any] | None = None) -> float | None:
    metrics: dict[str, float] = {
        "row_count": float(profile.get("rows", 0)),
        "column_count": float(profile.get("columns", 0)),
        "duplicate_rows": float(profile.get("duplicate_rows", 0)),
        "missing_percent": float(profile.get("missing_percent", 0)),
    }
    if metric == "placement_rate":
        placement = profile.get("placement_rate")
        return float(placement) if placement is not None else None
    if metric.startswith("mean:"):
        stats = profile.get("numeric_stats", {}).get(metric.partition(":")[2])
        return float(stats["mean"]) if stats else None
    if metric.startswith("outlier_rate:"):
        stats = profile.get("numeric_stats", {}).get(metric.partition(":")[2])
        return float(stats["outlier_rate_iqr"] * 100) if stats else None
    if metric.startswith("percentage_change:") or metric.startswith("percentage_point_change:"):
        base_metric = metric.partition(":")[2]
        if not previous:
            return None
        current_value = _metric_value(profile, base_metric)
        previous_value = _metric_value(previous, base_metric)
        if current_value is None or previous_value is None:
            return None
        difference = current_value - previous_value
        if metric.startswith("percentage_point_change:"):
            return difference
        if previous_value == 0:
            return None
        return difference / abs(previous_value) * 100
    return metrics.get(metric)


def _matches(value: float, operator: str, threshold: float) -> bool:
    if operator in {"percentage_change", "percentage_point_change"}:
        return abs(value) >= abs(threshold)
    return {
        ">": value > threshold,
        "<": value < threshold,
        ">=": value >= threshold,
        "<=": value <= threshold,
        "=": value == threshold,
        "!=": value != threshold,
    }[operator]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class AutomationService:
    def __init__(
        self,
        repository: AutomationRepository,
        registry: DatasetRegistryRepository,
        users: UserRepository,
        workspaces: WorkspaceRepository,
        billing: BillingService,
        config: DatabaseConfig,
        gemini: GeminiService | None = None,
        rate_limiter: AIRateLimiter | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.users = users
        self.workspaces = workspaces
        self.billing = billing
        self.config = config
        self.gemini = gemini or GeminiService(model=settings.gemini_model)
        self.rate_limiter = rate_limiter or AIRateLimiter(settings.ai_max_requests_per_minute, settings.ai_max_requests_per_day)

    def authorize(self, workspace_id: str, user: UserRecord, *, write: bool) -> str:
        role = WorkspaceService(self.workspaces)._require_role(workspace_id, user, min_role=RolePermissions.VIEWER)
        if write and not RolePermissions.can_analyze(role):
            raise PermissionError("Workspace analyst permission is required to manage automations.")
        return role

    def validate_dataset(self, dataset_id: str, user: UserRecord, workspace_id: str) -> None:
        access = DatasetAccessService(self.registry, user, self.workspaces)
        access.can_use_for_analytics(dataset_id)
        record = self.registry.get_dataset(dataset_id)
        if not record.is_builtin and not self.workspaces.get_shared_dataset(workspace_id, dataset_id):
            raise DatasetAccessError("Dataset is not accessible in this workspace.")

    def validate_config(self, dataset_id: str, user: UserRecord, config: dict[str, Any]) -> dict[str, Any]:
        allowed_fields = {"operation", "column", "group_by", "limit"}
        if not isinstance(config, dict) or set(config) - allowed_fields:
            raise AutomationError("Analytics config contains unsupported fields.")
        operation = config.get("operation")
        if operation not in ALLOWED_OPERATIONS:
            raise AutomationError("Analytics operation is not supported.")
        normalized = {"operation": operation}
        for key in ("column", "group_by"):
            value = config.get(key)
            if value is not None:
                if not isinstance(value, str) or len(value) > 128:
                    raise AutomationError(f"{key} must be a column name.")
                normalized[key] = value
        if "limit" in config:
            limit = config["limit"]
            if not isinstance(limit, int) or not 1 <= limit <= settings.max_result_rows:
                raise AutomationError("Limit must be within the configured result row limit.")
            normalized["limit"] = limit
        database = DatabaseRepository(self.config, registry=self.registry)
        dataframe = database.load_dataframe(dataset_id)
        if normalized.get("column") and normalized["column"] not in dataframe.columns:
            raise AutomationError("Analytics column is not present in this dataset.")
        if normalized.get("group_by") and normalized["group_by"] not in dataframe.columns:
            raise AutomationError("Grouping column is not present in this dataset.")
        if operation in {"average", "minimum", "maximum", "sum", "group_average", "value_counts"} and not normalized.get("column"):
            raise AutomationError("This operation requires a metric column.")
        if operation == "group_average" and not normalized.get("group_by"):
            raise AutomationError("Group average requires a grouping column.")
        return normalized

    def create_saved_query(self, *, user: UserRecord, workspace_id: str, dataset_id: str, title: str, question: str, config: dict[str, Any]) -> dict[str, Any]:
        self.authorize(workspace_id, user, write=True)
        self.validate_dataset(dataset_id, user, workspace_id)
        safe_config = self.validate_config(dataset_id, user, config)
        result = self.repository.create_saved_query(user_id=user.id, workspace_id=workspace_id, dataset_id=dataset_id, title=title.strip(), question=question.strip(), config=safe_config)
        self._audit(workspace_id, user.id, "saved_query_created", {"query_id": result["id"], "dataset_id": dataset_id})
        return result

    def list_saved_queries(self, user: UserRecord, workspace_id: str) -> list[dict[str, Any]]:
        self.authorize(workspace_id, user, write=False)
        return self.repository.list_saved_queries(workspace_id)

    def create_automation(self, *, user: UserRecord, workspace_id: str, query_id: str, name: str, frequency: str, run_time: str, timezone_name: str, weekday: int, day_of_month: int, ai_summary: bool) -> dict[str, Any]:
        self.authorize(workspace_id, user, write=True)
        query = self.repository.get_saved_query(query_id, workspace_id)
        if query is None:
            raise AutomationError("Saved query was not found in this workspace.")
        self.validate_dataset(query["dataset_id"], user, workspace_id)
        next_run = next_run_datetime(frequency, run_time, timezone_name, weekday=weekday, day_of_month=day_of_month)
        result = self.repository.create_automation(
            user_id=user.id, workspace_id=workspace_id, dataset_id=query["dataset_id"], saved_query_id=query_id,
            name=name.strip(), frequency=frequency, run_time=run_time, weekday=weekday,
            day_of_month=day_of_month, timezone_name=timezone_name, ai_summary=ai_summary,
            next_run_at=next_run.isoformat(),
        )
        self._audit(workspace_id, user.id, "automation_created", {"automation_id": result["id"], "dataset_id": result["dataset_id"]})
        return result

    def list_automations(self, user: UserRecord, workspace_id: str) -> list[dict[str, Any]]:
        self.authorize(workspace_id, user, write=False)
        return self.repository.list_automations(workspace_id)

    def get_automation(self, user: UserRecord, workspace_id: str, automation_id: str) -> dict[str, Any]:
        self.authorize(workspace_id, user, write=False)
        automation = self.repository.get_automation(automation_id, workspace_id)
        if automation is None:
            raise AutomationError("Automation was not found.")
        return automation

    def set_active(self, user: UserRecord, workspace_id: str, automation_id: str, active: bool) -> dict[str, Any]:
        self.authorize(workspace_id, user, write=True)
        automation = self.get_automation(user, workspace_id, automation_id)
        next_run = None
        if active:
            next_run = next_run_datetime(automation["frequency"], automation["run_time"], automation["timezone"], weekday=int(automation["weekday"]), day_of_month=int(automation["day_of_month"])).isoformat()
        self.repository.update_automation(automation_id, workspace_id, active=active, next_run_at=next_run)
        self._audit(workspace_id, user.id, "automation_resumed" if active else "automation_paused", {"automation_id": automation_id})
        return self.get_automation(user, workspace_id, automation_id)

    def update_automation(self, user: UserRecord, workspace_id: str, automation_id: str, **updates: Any) -> dict[str, Any]:
        self.authorize(workspace_id, user, write=True)
        existing = self.get_automation(user, workspace_id, automation_id)
        query_id = updates.get("saved_query_id") or existing["saved_query_id"]
        query = self.repository.get_saved_query(query_id, workspace_id)
        if query is None:
            raise AutomationError("Saved query was not found in this workspace.")
        self.validate_dataset(query["dataset_id"], user, workspace_id)
        frequency = updates.get("frequency") or existing["frequency"]
        run_time = updates.get("run_time") or existing["run_time"]
        timezone_name = updates.get("timezone_name") or existing["timezone"]
        weekday = updates.get("weekday") if updates.get("weekday") is not None else int(existing["weekday"])
        day_of_month = updates.get("day_of_month") if updates.get("day_of_month") is not None else int(existing["day_of_month"])
        active = updates.get("active") if updates.get("active") is not None else bool(existing["active"])
        next_run = next_run_datetime(frequency, run_time, timezone_name, weekday=weekday, day_of_month=day_of_month) if active else None
        self.repository.update_automation(
            automation_id, workspace_id,
            active=active,
            next_run_at=next_run.isoformat() if next_run else None,
            name=updates.get("name"), frequency=frequency if "frequency" in updates else None,
            run_time=run_time if "run_time" in updates else None,
            timezone_name=timezone_name if "timezone_name" in updates else None,
            weekday=weekday if "weekday" in updates else None,
            day_of_month=day_of_month if "day_of_month" in updates else None,
            ai_summary=updates.get("ai_summary"), saved_query_id=query_id,
            dataset_id=query["dataset_id"],
        )
        self._audit(workspace_id, user.id, "automation_updated", {"automation_id": automation_id})
        return self.get_automation(user, workspace_id, automation_id)

    def delete_automation(self, user: UserRecord, workspace_id: str, automation_id: str) -> None:
        self.authorize(workspace_id, user, write=True)
        self.get_automation(user, workspace_id, automation_id)
        self.repository.delete_automation(automation_id, workspace_id)
        self._audit(workspace_id, user.id, "automation_deleted", {"automation_id": automation_id})

    def run_now(self, user: UserRecord, workspace_id: str, automation_id: str) -> dict[str, Any]:
        automation = self.get_automation(user, workspace_id, automation_id)
        self.authorize(workspace_id, user, write=True)
        run_id = self.repository.create_run(automation_id, f"manual:{datetime.now(timezone.utc).isoformat()}:{time.time_ns()}")
        if not run_id:
            raise AutomationError("Unable to enqueue this run.")
        self._audit(workspace_id, user.id, "automation_manual_run_requested", {"automation_id": automation_id, "run_id": run_id})
        return self.repository.get_run(run_id)

    def list_runs(self, user: UserRecord, workspace_id: str, automation_id: str) -> list[dict[str, Any]]:
        self.get_automation(user, workspace_id, automation_id)
        return self.repository.list_runs(automation_id)

    def run_report_csv(self, user: UserRecord, workspace_id: str, automation_id: str, run_id: str) -> str:
        self.get_automation(user, workspace_id, automation_id)
        run = self.repository.get_run(run_id)
        if run is None or run["automation_id"] != automation_id:
            raise AutomationError("Automation run was not found.")
        if run["status"] != "completed" or not run.get("result"):
            raise AutomationError("A completed report is not available for this run.")

        def flatten(value: Any, prefix: str = "") -> list[tuple[str, str]]:
            if isinstance(value, dict):
                rows: list[tuple[str, str]] = []
                for key, item in value.items():
                    rows.extend(flatten(item, f"{prefix}.{key}" if prefix else str(key)))
                return rows
            if isinstance(value, list):
                if all(not isinstance(item, (dict, list)) for item in value):
                    return [(prefix, json.dumps(value, ensure_ascii=True))]
                rows = []
                for index, item in enumerate(value):
                    rows.extend(flatten(item, f"{prefix}[{index}]"))
                return rows
            text = "" if value is None else str(value)
            if text.lstrip()[:1] in {"=", "+", "-", "@"}:
                text = "'" + text
            return [(prefix, text)]

        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(("metric", "value"))
        for key, value in flatten(run["result"]):
            safe_key = "'" + key if key.lstrip()[:1] in {"=", "+", "-", "@"} else key
            writer.writerow((safe_key, value))
        return buffer.getvalue()

    def create_alert(self, *, user: UserRecord, workspace_id: str, dataset_id: str, name: str, alert_type: str, metric: str, operator: str, threshold: float, cooldown_seconds: int) -> dict[str, Any]:
        self.authorize(workspace_id, user, write=True)
        self.validate_dataset(dataset_id, user, workspace_id)
        if alert_type not in {"threshold", "anomaly"}:
            raise AutomationError("Alert type must be threshold or anomaly.")
        if operator not in ALLOWED_OPERATORS:
            raise AutomationError("Alert operator is unsupported.")
        if not math.isfinite(threshold) or not 0 <= cooldown_seconds <= 604800:
            raise AutomationError("Threshold or cooldown is invalid.")
        if not self._metric_allowed(dataset_id, user, metric, alert_type):
            raise AutomationError("Alert metric is not available for this dataset.")
        alert = self.repository.create_alert(user_id=user.id, workspace_id=workspace_id, dataset_id=dataset_id, name=name.strip(), alert_type=alert_type, metric=metric, operator=operator, threshold=threshold, config={}, cooldown_seconds=cooldown_seconds)
        self._audit(workspace_id, user.id, "alert_created", {"alert_id": alert["id"], "dataset_id": dataset_id})
        return alert

    def list_alerts(self, user: UserRecord, workspace_id: str, dataset_id: str | None = None) -> list[dict[str, Any]]:
        self.authorize(workspace_id, user, write=False)
        return self.repository.list_alerts(workspace_id, dataset_id)

    def set_alert_active(self, user: UserRecord, workspace_id: str, alert_id: str, active: bool) -> dict[str, Any]:
        self.authorize(workspace_id, user, write=True)
        if self.repository.get_alert(alert_id, workspace_id) is None:
            raise AutomationError("Alert was not found.")
        self.repository.update_alert_active(alert_id, workspace_id, active)
        self._audit(workspace_id, user.id, "alert_updated", {"alert_id": alert_id, "active": active})
        return self.repository.get_alert(alert_id, workspace_id)

    def delete_alert(self, user: UserRecord, workspace_id: str, alert_id: str) -> None:
        self.authorize(workspace_id, user, write=True)
        if self.repository.get_alert(alert_id, workspace_id) is None:
            raise AutomationError("Alert was not found.")
        self.repository.delete_alert(alert_id, workspace_id)
        self._audit(workspace_id, user.id, "alert_deleted", {"alert_id": alert_id})

    def list_snapshots(self, user: UserRecord, workspace_id: str, dataset_id: str) -> list[dict[str, Any]]:
        self.authorize(workspace_id, user, write=False)
        self.validate_dataset(dataset_id, user, workspace_id)
        return self.repository.list_snapshots(workspace_id, dataset_id)

    def enqueue_due_automations(self, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        due = self.repository.list_due_automations(current.isoformat())
        queued = 0
        for automation in due:
            scheduled_for = str(automation["next_run_at"])
            next_run = next_run_datetime(
                automation["frequency"], automation["run_time"], automation["timezone"],
                after=current, weekday=int(automation["weekday"]), day_of_month=int(automation["day_of_month"]),
            )
            run_id = self.repository.create_run(automation["id"], scheduled_for)
            if run_id:
                queued += 1
                self.repository.update_automation(automation["id"], automation["workspace_id"], next_run_at=next_run.isoformat())
        return queued

    def process_pending_runs(self, limit: int = 20) -> int:
        self.repository.recover_stale_runs((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
        pending = self.repository.list_pending_runs(datetime.now(timezone.utc).isoformat(), limit)
        processed = 0
        for run in pending:
            if not self.repository.claim_run(run["id"]):
                continue
            processed += 1
            self._execute_run(run)
        return processed

    def _execute_run(self, run: dict[str, Any]) -> None:
        started = time.perf_counter()
        automation = self.repository.get_automation_by_id(run["automation_id"])
        if automation is None:
            self.repository.finish_run(run["id"], run["automation_id"], "", status="failed", error_code="automation_missing")
            return
        try:
            if not automation["active"] and not str(run["scheduled_for"]).startswith("manual:"):
                self.repository.finish_run(run["id"], automation["id"], automation["workspace_id"], status="canceled", error_code="automation_paused")
                return
            user = self.users.get_by_id(automation["user_id"])
            self._check_run_context(automation, user)
            saved = self.repository.get_saved_query(automation["saved_query_id"], automation["workspace_id"])
            if saved is None or saved["dataset_id"] != automation["dataset_id"]:
                raise AutomationError("saved_query_unavailable")

            self._consume_usage(automation, user, "analytics_queries")
            if automation["ai_summary"]:
                self._check_usage(automation["workspace_id"], "ai_requests")

            data_repository = DatabaseRepository(self.config, registry=self.registry)
            dataframe = data_repository.load_dataframe(automation["dataset_id"])
            result = AnalyticsService(data_repository).run_operation(
                saved["config"]["operation"], dataset_id=automation["dataset_id"],
                column=saved["config"].get("column"), group_by=saved["config"].get("group_by"),
            )
            if isinstance(result, list) and saved["config"].get("limit"):
                result = result[: saved["config"]["limit"]]
            previous_record = self.repository.latest_snapshot(automation["workspace_id"], automation["dataset_id"])
            previous_profile = previous_record.get("profile") if previous_record else None
            profile, schema_hash = profile_dataframe(dataframe)
            if "Placement" in dataframe.columns:
                try:
                    placement_rate = AnalyticsService(data_repository).run_operation("overall_placement_rate", dataset_id=automation["dataset_id"])
                    profile["placement_rate"] = float(placement_rate)
                except Exception:
                    pass
            changes = compare_profiles(previous_profile, profile)
            snapshot = self.repository.create_snapshot(
                user_id=user.id, workspace_id=automation["workspace_id"], dataset_id=automation["dataset_id"],
                schema_hash=schema_hash, row_count=len(dataframe), profile=profile,
            )
            alerts_triggered = self._evaluate_alerts(automation, snapshot, profile, previous_profile)
            report: dict[str, Any] = {
                "question": saved["question"], "operation": saved["config"]["operation"],
                "metrics": _json_safe(result), "profile": profile, "changes": changes,
                "alerts_triggered": alerts_triggered, "snapshot_id": snapshot["id"],
                "anomaly_note": "IQR outliers are statistical flags and do not confirm a business problem or cause.",
            }
            if automation["ai_summary"]:
                self.rate_limiter.check(user_id=user.id)
                explanation = self.gemini.explain(saved["question"], saved["config"]["operation"], result, ["All reported values were calculated by the analytics engine."])
                report["ai_summary"] = explanation.answer
                report["ai_insights"] = explanation.insights
                self.billing.record_usage(automation["workspace_id"], user.id, "ai_request")

            self.billing.record_usage(automation["workspace_id"], user.id, "report_generated")
            self._notify(user.id, "Scheduled analytics report is ready", "A scheduled analytics report is available in your workspace automation history.", dedupe_key=f"run:{run['id']}:report")
            if changes.get("schema_changed"):
                self._notify(user.id, "Dataset schema changed", "The dataset schema differs from its previous snapshot. Review the automation history for details.", dedupe_key=f"run:{run['id']}:schema")
            self._audit(automation["workspace_id"], user.id, "automation_run_completed", {"automation_id": automation["id"], "run_id": run["id"], "snapshot_id": snapshot["id"]})
            self.repository.finish_run(run["id"], automation["id"], automation["workspace_id"], status="completed", result=report, execution_time_ms=int((time.perf_counter() - started) * 1000), failure_count=0)
        except Exception as error:
            error_code = self._safe_error_code(error)
            _log.exception("automation_run_failed automation_id=%s run_id=%s error_type=%s", automation["id"], run["id"], type(error).__name__)
            attempt = int(run.get("attempt", 0)) + 1
            permanent = isinstance(error, (PermissionError, DatasetAccessError, AutomationError, UsageLimitExceededError, LookupError, ValueError))
            if not permanent and attempt < MAX_JOB_ATTEMPTS:
                retry_at = datetime.now(timezone.utc) + timedelta(seconds=30 * (2 ** (attempt - 1)))
                self.repository.retry_run(run["id"], attempt, retry_at.isoformat(), error_code)
                self.repository.update_automation(automation["id"], automation["workspace_id"], last_status="retrying", failure_count=attempt)
                return
            self.repository.finish_run(run["id"], automation["id"], automation["workspace_id"], status="failed", error_code=error_code, execution_time_ms=int((time.perf_counter() - started) * 1000), failure_count=attempt)
            self._notify(automation["user_id"], "Scheduled analytics failed", "A scheduled analytics run failed. Review its safe error code in automation history.", dedupe_key=f"run:{run['id']}:failure")
            self._audit(automation["workspace_id"], automation["user_id"], "automation_run_failed", {"automation_id": automation["id"], "run_id": run["id"], "error_code": error_code})

    def _check_run_context(self, automation: dict[str, Any], user: UserRecord) -> None:
        role = self.authorize(automation["workspace_id"], user, write=True)
        if not RolePermissions.can_analyze(role):
            raise PermissionError("workspace_permission_changed")
        self.validate_dataset(automation["dataset_id"], user, automation["workspace_id"])
        subscription = self.billing.repository.get_subscription_for_workspace(automation["workspace_id"])
        if subscription and subscription.status not in {"active", "trialing"}:
            raise PermissionError("subscription_inactive")
        if not self.billing.has_feature(automation["workspace_id"], "scheduled_analytics"):
            raise PermissionError("feature_not_entitled")
        self._check_usage(automation["workspace_id"], "analytics_queries")
        self._check_usage(automation["workspace_id"], "reports")

    def _check_usage(self, workspace_id: str, resource: str) -> None:
        result = self.billing.check_usage_limit(workspace_id, resource, 1)
        if not result["allowed"]:
            raise UsageLimitExceededError(f"{resource}_limit_reached")

    def _consume_usage(self, automation: dict[str, Any], user: UserRecord, resource: str) -> None:
        self._check_usage(automation["workspace_id"], resource)
        self.billing.record_usage(automation["workspace_id"], user.id, "analytics_query")

    def _metric_allowed(self, dataset_id: str, user: UserRecord, metric: str, alert_type: str) -> bool:
        if metric in {"row_count", "column_count", "duplicate_rows", "missing_percent"}:
            return alert_type == "threshold"
        dataframe = DatabaseRepository(self.config, registry=self.registry).load_dataframe(dataset_id)
        if metric == "placement_rate":
            return alert_type == "threshold" and "Placement" in dataframe.columns
        if metric.startswith("percentage_change:") or metric.startswith("percentage_point_change:"):
            return alert_type == "threshold" and self._metric_allowed(dataset_id, user, metric.partition(":")[2], "threshold")
        prefix, separator, column = metric.partition(":")
        if not separator or column not in dataframe.columns or not pd.api.types.is_numeric_dtype(dataframe[column]):
            return False
        return (alert_type == "anomaly" and prefix == "outlier_rate") or (alert_type == "threshold" and prefix == "mean")

    def _evaluate_alerts(self, automation: dict[str, Any], snapshot: dict[str, Any], profile: dict[str, Any], previous: dict[str, Any] | None) -> list[dict[str, Any]]:
        triggered = []
        for alert in self.repository.list_active_alerts(automation["workspace_id"], automation["dataset_id"]):
            metric = alert["metric"]
            operator = alert["operator"]
            measured_metric = metric
            if operator == "percentage_change":
                measured_metric = f"percentage_change:{metric}"
            elif operator == "percentage_point_change":
                measured_metric = f"percentage_point_change:{metric}"
            value = _metric_value(profile, measured_metric, previous)
            if value is None or not _matches(float(value), alert["operator"], float(alert["threshold"])):
                continue
            last_triggered = alert.get("last_triggered_at")
            if last_triggered:
                try:
                    last = datetime.fromisoformat(str(last_triggered).replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - last < timedelta(seconds=int(alert["cooldown_seconds"])):
                        continue
                except ValueError:
                    pass
            detail = {"alert_id": alert["id"], "name": alert["name"], "metric": alert["metric"], "value": value, "threshold": alert["threshold"], "severity": "WARNING"}
            if not self.repository.create_alert_event(alert["id"], snapshot["id"], detail):
                continue
            now = datetime.now(timezone.utc).isoformat()
            self.repository.set_alert_triggered(alert["id"], automation["workspace_id"], now)
            self._notify(alert["user_id"], "Analytics alert triggered", f"Alert '{alert['name']}' was triggered. Review the current snapshot in your workspace.", dedupe_key=f"alert:{alert['id']}:{snapshot['id']}")
            triggered.append(detail)
            self._audit(automation["workspace_id"], automation["user_id"], "alert_triggered", {"alert_id": alert["id"], "snapshot_id": snapshot["id"], "severity": "WARNING"})
        return triggered

    def _notify(self, user_id: str, title: str, message: str, *, dedupe_key: str) -> None:
        notification_id = str(uuid5(NAMESPACE_URL, dedupe_key))
        self.workspaces.create_notification(user_id, title, message, notification_id=notification_id)

    def _audit(self, workspace_id: str, user_id: str, event_type: str, metadata: dict[str, Any]) -> None:
        self.workspaces.log_activity(workspace_id, user_id, event_type, metadata)

    @staticmethod
    def _safe_error_code(error: Exception) -> str:
        if isinstance(error, UsageLimitExceededError):
            return "usage_limit_reached"
        if isinstance(error, (PermissionError, DatasetAccessError)):
            return "authorization_changed"
        if isinstance(error, AutomationError):
            return "automation_configuration_invalid"
        return "analytics_execution_failed"