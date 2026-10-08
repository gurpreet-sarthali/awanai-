from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pandas as pd
import pytest

from analytics.database import DatabaseConfig, connect
from backend.repositories.automation_repository import AutomationRepository
from backend.repositories.billing_repository import BillingRepository
from backend.repositories.dataset_registry_repository import DatasetRegistryRepository
from backend.repositories.user_repository import UserRepository
from backend.repositories.workspace_repository import WorkspaceRepository
from backend.services.automation_service import (
    AutomationError,
    AutomationService,
    compare_profiles,
    next_run_datetime,
    profile_dataframe,
)
from backend.services.billing_service import BillingService
from backend.services.dataset_import_service import DatasetImportService
from backend.services.workspace_service import WorkspaceService


@pytest.fixture
def automation_context(tmp_path):
    config = DatabaseConfig("localhost", 3306, "sqlite", "", str(tmp_path / "phase21.sqlite3"))
    users = UserRepository(config)
    users.ensure_schema()
    owner = users.create_user(email="owner-automation@example.com", name="Owner", password_hash="hash")
    outsider = users.create_user(email="outsider-automation@example.com", name="Outsider", password_hash="hash")

    workspace_repository = WorkspaceRepository(config)
    workspace_repository.ensure_schema()
    workspace = WorkspaceService(workspace_repository).create_workspace(owner, "Automation test")

    registry = DatasetRegistryRepository(config)
    registry.ensure_schema()
    dataset_id = str(uuid4())
    table_name = registry.generate_internal_table_name(dataset_id)
    dataframe = pd.DataFrame(
        {
            "score": [1, 2, 3, 4, 5, 6, 7, 8, 9, 1000],
            "segment": ["A"] * 9 + ["B"],
        }
    )
    registry.create_dataset(
        dataset_id=dataset_id,
        user_id=owner.id,
        dataset_name="Automation data",
        original_filename="automation.csv",
        internal_table_name=table_name,
        storage_reference=None,
        status="READY",
        validation_status="valid",
    )
    imported = DatasetImportService(config).import_dataframe(table_name, dataframe, [(name, name) for name in dataframe.columns])
    registry.replace_columns(dataset_id, imported["columns"])
    WorkspaceService(workspace_repository).share_dataset(workspace.id, owner, dataset_id)

    billing_repository = BillingRepository(config)
    billing_repository.ensure_schema()
    billing = BillingService(billing_repository)
    billing.ensure_default_plans()
    billing.get_or_create_workspace_subscription(workspace_id=workspace.id, user_id=owner.id, plan_id="team")

    repository = AutomationRepository(config)
    repository.ensure_schema()
    service = AutomationService(repository, registry, users, workspace_repository, billing, config)
    return {
        "config": config,
        "owner": owner,
        "outsider": outsider,
        "workspace": workspace,
        "dataset_id": dataset_id,
        "repository": repository,
        "service": service,
        "billing": billing,
    }


def test_schedule_calculation_respects_timezone_and_month_end():
    after = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    result = next_run_datetime("monthly", "09:00", "UTC", after=after, day_of_month=31)
    assert result == datetime(2026, 11, 30, 9, 0, tzinfo=UTC)

    spring_forward = next_run_datetime(
        "daily", "02:30", "America/New_York", after=datetime(2026, 3, 8, 0, 0, tzinfo=UTC)
    )
    assert spring_forward.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).hour == 3


def test_profile_and_snapshot_comparison_are_deterministic():
    first, first_hash = profile_dataframe(pd.DataFrame({"score": [1, 2, 3], "segment": ["A", "A", "B"]}))
    second, second_hash = profile_dataframe(pd.DataFrame({"score": [1, 2, 3, 4], "segment": ["A", "A", "B", "C"]}))
    changes = compare_profiles(first, second)

    assert first_hash == second_hash
    assert changes["row_delta"] == 1
    assert changes["new_categories"] == {"segment": ["C"]}
    numeric, _ = profile_dataframe(pd.DataFrame({"score": [1, 2]}))
    text, _ = profile_dataframe(pd.DataFrame({"score": ["one", "two"]}))
    assert compare_profiles(numeric, text)["type_changes"]["score"] == {"from": "int64", "to": text["schema"][0]["dtype"]}


def test_saved_queries_reject_executable_fields_and_outsiders(automation_context):
    service = automation_context["service"]
    workspace = automation_context["workspace"]
    dataset_id = automation_context["dataset_id"]

    with pytest.raises(AutomationError, match="unsupported fields"):
        service.create_saved_query(
            user=automation_context["owner"], workspace_id=workspace.id, dataset_id=dataset_id,
            title="unsafe", question="run sql", config={"operation": "count", "sql": "DROP TABLE users"},
        )

    with pytest.raises(PermissionError):
        service.create_saved_query(
            user=automation_context["outsider"], workspace_id=workspace.id, dataset_id=dataset_id,
            title="outsider", question="count rows", config={"operation": "count"},
        )


def test_automation_run_is_idempotent_data_grounded_and_records_alert(automation_context):
    service = automation_context["service"]
    repo = automation_context["repository"]
    owner = automation_context["owner"]
    workspace = automation_context["workspace"]
    dataset_id = automation_context["dataset_id"]

    query = service.create_saved_query(
        user=owner,
        workspace_id=workspace.id,
        dataset_id=dataset_id,
        title="Average score",
            question="=2+2",
        config={"operation": "average", "column": "score"},
    )
    automation = service.create_automation(
        user=owner,
        workspace_id=workspace.id,
        query_id=query["id"],
        name="Daily score report",
        frequency="daily",
        run_time="09:00",
        timezone_name="UTC",
        weekday=0,
        day_of_month=1,
        ai_summary=False,
    )
    service.create_alert(
        user=owner,
        workspace_id=workspace.id,
        dataset_id=dataset_id,
        name="Outlier rate",
        alert_type="anomaly",
        metric="outlier_rate:score",
        operator=">",
        threshold=5,
        cooldown_seconds=3600,
    )

    run_id = repo.create_run(automation["id"], "2026-10-04T09:00:00+00:00")
    assert run_id
    assert repo.create_run(automation["id"], "2026-10-04T09:00:00+00:00") is None
    assert service.process_pending_runs() == 1

    run = repo.get_run(run_id)
    assert run["status"] == "completed"
    assert run["result"]["metrics"] == pytest.approx(104.5)
    assert run["result"]["profile"]["rows"] == 10
    assert len(run["result"]["alerts_triggered"]) == 1
    assert len(repo.list_snapshots(workspace.id, dataset_id)) == 1
    assert automation_context["billing"].get_usage_summary(workspace.id)["usage"]["analytics_queries"]["used"] == 1
    csv_report = service.run_report_csv(owner, workspace.id, automation["id"], run_id)
    assert "metrics,104.5" in csv_report
    assert "question,'=2+2" in csv_report


def test_worker_rechecks_workspace_membership_before_execution(automation_context):
    service = automation_context["service"]
    owner = automation_context["owner"]
    workspace = automation_context["workspace"]
    dataset_id = automation_context["dataset_id"]
    query = service.create_saved_query(
        user=owner, workspace_id=workspace.id, dataset_id=dataset_id,
        title="Count", question="Count rows", config={"operation": "count"},
    )
    automation = service.create_automation(
        user=owner, workspace_id=workspace.id, query_id=query["id"], name="Count",
        frequency="weekly", run_time="09:00", timezone_name="UTC", weekday=0,
        day_of_month=1, ai_summary=False,
    )
    automation_context["repository"].update_automation(automation["id"], workspace.id, active=False)
    automation_context["repository"].update_automation(automation["id"], workspace.id, active=True)

    connection = connect(automation_context["config"])
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM workspace_members WHERE workspace_id=%s AND user_id=%s", (workspace.id, owner.id))
        connection.commit()
        cursor.close()
    finally:
        connection.close()

    run_id = automation_context["repository"].create_run(automation["id"], "manual:revoked-permission")
    service.process_pending_runs()
    assert automation_context["repository"].get_run(run_id)["status"] == "failed"
    assert automation_context["repository"].get_run(run_id)["error_code"] == "authorization_changed"


def test_schedule_can_be_edited_and_rescheduled(automation_context):
    service = automation_context["service"]
    owner = automation_context["owner"]
    workspace = automation_context["workspace"]
    dataset_id = automation_context["dataset_id"]
    query = service.create_saved_query(
        user=owner, workspace_id=workspace.id, dataset_id=dataset_id,
        title="Count", question="Count rows", config={"operation": "count"},
    )
    automation = service.create_automation(
        user=owner, workspace_id=workspace.id, query_id=query["id"], name="Daily",
        frequency="daily", run_time="09:00", timezone_name="UTC", weekday=0,
        day_of_month=1, ai_summary=False,
    )

    updated = service.update_automation(
        owner, workspace.id, automation["id"], name="Monthly summary", frequency="monthly",
        run_time="10:30", timezone_name="Europe/London", day_of_month=15,
    )

    assert updated["name"] == "Monthly summary"
    assert updated["frequency"] == "monthly"
    assert updated["run_time"] == "10:30"
    assert updated["timezone"] == "Europe/London"


def test_worker_claim_is_exclusive_and_stale_runs_recover(automation_context):
    repository = automation_context["repository"]
    automation = repository.create_automation(
        user_id=automation_context["owner"].id,
        workspace_id=automation_context["workspace"].id,
        dataset_id=automation_context["dataset_id"],
        saved_query_id="query-id",
        name="Locked schedule",
        frequency="daily",
        run_time="09:00",
        weekday=0,
        day_of_month=1,
        timezone_name="UTC",
        ai_summary=False,
        next_run_at="2099-01-01T00:00:00+00:00",
    )
    run_id = repository.create_run(automation["id"], "manual:exclusive-lock")
    assert repository.claim_run(run_id) is True
    assert repository.claim_run(run_id) is False

    connection = connect(automation_context["config"])
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE automation_runs SET started_at=%s WHERE id=%s", ("2000-01-01T00:00:00+00:00", run_id))
        connection.commit()
        cursor.close()
    finally:
        connection.close()

    assert repository.recover_stale_runs("2026-10-04T00:00:00+00:00") == 1
    assert repository.claim_run(run_id) is True


def test_paused_schedule_cancels_queued_run(automation_context):
    service = automation_context["service"]
    owner = automation_context["owner"]
    workspace = automation_context["workspace"]
    query = service.create_saved_query(
        user=owner, workspace_id=workspace.id, dataset_id=automation_context["dataset_id"],
        title="Count", question="Count rows", config={"operation": "count"},
    )
    automation = service.create_automation(
        user=owner, workspace_id=workspace.id, query_id=query["id"], name="Paused",
        frequency="daily", run_time="09:00", timezone_name="UTC", weekday=0,
        day_of_month=1, ai_summary=False,
    )
    run_id = automation_context["repository"].create_run(automation["id"], "2026-10-04T09:00:00+00:00")
    service.set_active(owner, workspace.id, automation["id"], False)

    service.process_pending_runs()

    run = automation_context["repository"].get_run(run_id)
    assert run["status"] == "canceled"
    assert run["error_code"] == "automation_paused"


def test_automation_api_scopes_queries_to_workspace_membership(automation_context, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api.dependencies import get_automation_service, get_current_user
    from backend.main import app

    monkeypatch.setitem(app.dependency_overrides, get_automation_service, lambda: automation_context["service"])
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: automation_context["owner"])
    client = TestClient(app)
    workspace_id = automation_context["workspace"].id
    dataset_id = automation_context["dataset_id"]
    payload = {
        "workspace_id": workspace_id,
        "dataset_id": dataset_id,
        "title": "Workspace count",
        "question": "How many rows are in this dataset?",
        "config": {"operation": "count"},
    }

    created = client.post("/api/v1/automations/queries", json=payload)
    assert created.status_code == 201
    assert created.json()["config"] == {"operation": "count"}

    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: automation_context["outsider"])
    denied = client.get(f"/api/v1/automations/queries?workspace_id={workspace_id}")
    assert denied.status_code == 403