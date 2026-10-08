from __future__ import annotations

import hashlib
import socket
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from starlette.requests import Request

from analytics.database import DatabaseConfig
from backend.api.dependencies import get_developer_api_service, get_registry, get_workspace_repository
from backend.core.user_model import UserRecord
from backend.main import app
from backend.repositories.billing_repository import BillingRepository
from backend.repositories.developer_repository import DeveloperRepository
from backend.repositories.dataset_registry_repository import DatasetRegistryRepository
from backend.repositories.user_repository import UserRepository
from backend.repositories.workspace_repository import WorkspaceRepository
from backend.services.billing_service import BillingService
from backend.services.developer_service import DeveloperAPIError, DeveloperAPIService, WebhookService
from backend.services.workspace_service import WorkspaceService


def _request(path: str = "/api/v1/public/workspace") -> Request:
    return Request({
        "type": "http", "method": "GET", "path": path, "headers": [],
        "query_string": b"", "server": ("testserver", 80), "client": ("127.0.0.1", 40000),
    })


@pytest.fixture
def developer_context(tmp_path):
    config = DatabaseConfig("localhost", 3306, "sqlite", "", str(tmp_path / "phase22.sqlite3"))
    users = UserRepository(config)
    users.ensure_schema()
    owner = users.create_user(email="phase22-owner@example.com", name="Developer Owner", password_hash="hash")
    outsider = users.create_user(email="phase22-outsider@example.com", name="Outsider", password_hash="hash")
    workspace_repository = WorkspaceRepository(config)
    workspace_repository.ensure_schema()
    workspace = WorkspaceService(workspace_repository).create_workspace(owner, "Developer workspace")
    registry = DatasetRegistryRepository(config)
    registry.ensure_schema()
    billing_repository = BillingRepository(config)
    billing_repository.ensure_schema()
    billing = BillingService(billing_repository)
    billing.ensure_default_plans()
    billing.get_or_create_workspace_subscription(workspace_id=workspace.id, user_id=owner.id, plan_id="team")
    repository = DeveloperRepository(config)
    repository.ensure_schema()
    api_service = DeveloperAPIService(repository, users, workspace_repository, billing)
    webhook_service = WebhookService(repository, workspace_repository)
    return {
        "config": config, "owner": owner, "outsider": outsider, "workspace": workspace,
        "workspace_repository": workspace_repository, "repository": repository,
        "registry": registry, "api_service": api_service, "webhook_service": webhook_service,
    }


def test_api_key_is_hashed_shown_once_scoped_and_revoked(developer_context):
    service = developer_context["api_service"]
    owner = developer_context["owner"]
    workspace_id = developer_context["workspace"].id
    created = service.create_key(user=owner, workspace_id=workspace_id, name="Read datasets", scopes=["datasets:read"])
    raw_key = created["api_key"]

    assert raw_key.startswith("ask_test_")
    assert created["id"]
    listed = service.list_keys(owner, workspace_id)
    assert "api_key" not in listed[0]
    assert "key_hash" not in listed[0]
    stored = developer_context["repository"].get_api_key(created["id"], workspace_id)
    assert stored["key_hash"] == hashlib.sha256(raw_key.encode()).hexdigest()
    assert raw_key not in str(stored)

    context = service.authenticate(_request(), raw_key)
    with pytest.raises(DeveloperAPIError) as scope_error:
        context.require_scope("analytics:run")
    assert scope_error.value.code == "INSUFFICIENT_SCOPE"

    service.revoke_key(owner, workspace_id, created["id"])
    with pytest.raises(DeveloperAPIError) as revoked:
        service.authenticate(_request(), raw_key)
    assert revoked.value.code == "INVALID_API_KEY"


def test_workspace_rate_limit_cannot_be_bypassed_by_key_rotation(developer_context, monkeypatch):
    import backend.services.developer_service as developer_module

    monkeypatch.setitem(developer_module._RATE_LIMITS, "team", 1)
    service = developer_context["api_service"]
    owner = developer_context["owner"]
    workspace_id = developer_context["workspace"].id
    first = service.create_key(user=owner, workspace_id=workspace_id, name="First", scopes=["workspace:read"])
    second = service.create_key(user=owner, workspace_id=workspace_id, name="Second", scopes=["workspace:read"])
    service.authenticate(_request(), first["api_key"])

    request = _request()
    with pytest.raises(DeveloperAPIError) as limited:
        service.authenticate(request, second["api_key"])

    assert limited.value.status_code == 429
    assert request.state.developer_rate_headers["X-RateLimit-Remaining"] == "0"


def test_webhook_secret_is_encrypted_signed_and_duplicate_event_is_suppressed(developer_context, monkeypatch):
    import backend.services.developer_service as developer_module

    encryption_key = Fernet.generate_key().decode()
    monkeypatch.setattr(developer_module, "settings", replace(developer_module.settings, webhook_encryption_key=encryption_key))
    monkeypatch.setattr(developer_module.socket, "getaddrinfo", lambda host, port, type: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))])
    webhook_service = developer_context["webhook_service"]
    owner = developer_context["owner"]
    workspace_id = developer_context["workspace"].id
    created = webhook_service.create(user=owner, workspace_id=workspace_id, url="https://hooks.example.com/askmydata", description="test", events=["webhook.test"])
    secret = created["secret"]
    record = developer_context["repository"].get_webhook(created["id"], workspace_id)
    decrypted = Fernet(encryption_key.encode()).decrypt(record["secret_ciphertext"].encode()).decode()
    assert decrypted == secret
    assert secret not in str(record)

    class BackgroundQueue:
        def __init__(self):
            self.tasks = []

        def add_task(self, function, *args):
            self.tasks.append((function, args))

    queue = BackgroundQueue()
    assert webhook_service.emit_event(workspace_id, "webhook.test", {"test": True}, queue, event_id="event-once") == 1
    assert webhook_service.emit_event(workspace_id, "webhook.test", {"test": True}, queue, event_id="event-once") == 0
    delivery_id = queue.tasks[0][1][0]
    captured = {}

    class Response:
        status_code = 204

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(developer_module.httpx, "post", fake_post)
    webhook_service.deliver(delivery_id)
    delivery = developer_context["repository"].get_delivery(delivery_id)
    assert delivery["status"] == "succeeded"
    assert captured["headers"]["X-AskMyData-Event"] == "webhook.test"
    assert captured["headers"]["X-AskMyData-Signature"].startswith("t=")
    assert captured["follow_redirects"] is False


def test_webhook_ssrf_validation_rejects_private_addresses():
    with pytest.raises(DeveloperAPIError) as error:
        WebhookService.validate_url("https://127.0.0.1/private")
    assert error.value.code == "WEBHOOK_SSRF_BLOCKED"


def test_public_api_returns_scoped_envelope_and_request_id(developer_context, monkeypatch):
    owner = developer_context["owner"]
    workspace_id = developer_context["workspace"].id
    key = developer_context["api_service"].create_key(user=owner, workspace_id=workspace_id, name="Workspace read", scopes=["workspace:read"])
    monkeypatch.setitem(app.dependency_overrides, get_developer_api_service, lambda: developer_context["api_service"])
    monkeypatch.setitem(app.dependency_overrides, get_workspace_repository, lambda: developer_context["workspace_repository"])
    monkeypatch.setitem(app.dependency_overrides, get_registry, lambda: developer_context["registry"])

    client = TestClient(app)
    denied = client.get("/api/v1/public/datasets", headers={"Authorization": f"Bearer {key['api_key']}"})
    assert denied.status_code == 403
    assert denied.json()["success"] is False
    assert denied.json()["error"]["code"] == "INSUFFICIENT_SCOPE"
    assert denied.json()["request_id"] == denied.headers["X-Request-ID"]

    allowed = client.get("/api/v1/public/workspace", headers={"Authorization": f"Bearer {key['api_key']}"})
    assert allowed.status_code == 200
    assert allowed.json()["success"] is True
    assert allowed.json()["data"]["id"] == workspace_id