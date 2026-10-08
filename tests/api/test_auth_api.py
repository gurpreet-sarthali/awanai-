"""
Phase 10 — Authentication & Authorization API tests.

These tests use in-memory stubs so no database connection is required.
The conftest.py autouse fixture normally overrides get_current_user, but
auth-route tests need to control that fixture themselves.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    get_auth_service,
    get_current_user,
    get_dataset_access,
    get_dataset_management_service,
    get_registry,
)
from backend.core.user_model import UserRecord
from backend.main import app
from backend.repositories.dataset_registry_repository import DatasetNotFoundError, DatasetRecord
from backend.repositories.user_repository import UserConflictError, UserNotFoundError
from backend.services.auth_service import AuthenticationError, AuthService
from backend.services.dataset_access_service import DatasetAccessError, DatasetAccessService
from backend.services.dataset_management_service import DatasetManagementError, DatasetManagementService


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_user(user_id: str = "u1", email: str = "a@example.com", name: str = "Alice") -> UserRecord:
    now = datetime.now(UTC)
    return UserRecord(
        id=user_id,
        email=email,
        name=name,
        password_hash="hashed",
        google_id=None,
        profile_picture_url=None,
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )


def _make_dataset(dataset_id: str, user_id: str, status: str = "READY") -> DatasetRecord:
    now = datetime.now(UTC)
    return DatasetRecord(
        dataset_id=dataset_id,
        user_id=user_id,
        dataset_name="Test dataset",
        original_filename="test.csv",
        internal_table_name=f"ds_{dataset_id[:12]}",
        storage_reference=None,
        row_count=10,
        column_count=3,
        status=status,
        is_builtin=False,
        validation_status="valid",
        error_message=None,
        created_at=now,
        updated_at=now,
    )


class _FakeAuthService:
    """Minimal AuthService stub for route-level tests."""

    def __init__(self, user: UserRecord | None = None, token: str = "good-token") -> None:
        self._user = user or _make_user()
        self._token = token

    def register(self, *, email: str, name: str, password: str) -> tuple[UserRecord, str]:
        if email == "taken@example.com":
            raise AuthenticationError("A user with this email already exists.")
        return self._user, self._token

    def login(self, *, email: str, password: str) -> tuple[UserRecord, str]:
        if password == "wrongpassword":
            raise AuthenticationError("Invalid email or password.")
        return self._user, self._token

    def resolve_token(self, token: str) -> UserRecord:
        if token != self._token:
            raise AuthenticationError("Invalid or expired authentication token.")
        return self._user

    def google_login_url(self) -> str:
        raise AuthenticationError("Google OAuth is not configured.")


class _RegistryStub:
    def __init__(self) -> None:
        self.datasets: dict[str, DatasetRecord] = {}

    def list_datasets_for_user(self, user_id: str, include_deleted: bool = False) -> list[DatasetRecord]:
        return [r for r in self.datasets.values() if r.user_id == user_id]

    def get_dataset_for_user(self, dataset_id: str, user_id: str) -> DatasetRecord:
        r = self.datasets.get(dataset_id)
        if r is None or r.user_id != user_id:
            raise DatasetNotFoundError(dataset_id)
        return r

    def get_dataset(self, dataset_id: str) -> DatasetRecord:
        r = self.datasets.get(dataset_id)
        if r is None:
            raise DatasetNotFoundError(dataset_id)
        return r

    def get_columns(self, dataset_id: str) -> list:
        return []


# ─── Fixture helpers ───────────────────────────────────────────────────────────

@pytest.fixture()
def user_a() -> UserRecord:
    return _make_user("user-a", "a@example.com", "Alice")


@pytest.fixture()
def user_b() -> UserRecord:
    return _make_user("user-b", "b@example.com", "Bob")


@pytest.fixture()
def auth_client(user_a: UserRecord):
    """TestClient authenticated as user_a; overrides autouse conftest fixture."""
    fake_auth = _FakeAuthService(user=user_a)
    app.dependency_overrides[get_auth_service] = lambda: fake_auth
    app.dependency_overrides[get_current_user] = lambda: user_a
    yield TestClient(app)
    app.dependency_overrides.pop(get_auth_service, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def unauth_client():
    """TestClient with NO authenticated user — verifies 401 responses."""
    def _raise():
        from backend.exceptions.handlers import AppError
        raise AppError(401, "authentication_required", "Authentication is required.")

    app.dependency_overrides[get_current_user] = _raise
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_current_user, None)


# ─── Auth endpoint tests ───────────────────────────────────────────────────────

class TestAuthRegister:
    def test_register_success(self):
        fake = _FakeAuthService()
        app.dependency_overrides[get_auth_service] = lambda: fake
        client = TestClient(app)
        resp = client.post("/api/v1/auth/register", json={"email": "new@example.com", "name": "New User", "password": "password123"})
        app.dependency_overrides.pop(get_auth_service, None)
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["user"]["email"] == "a@example.com"

    def test_register_duplicate_email_returns_400(self):
        fake = _FakeAuthService()
        app.dependency_overrides[get_auth_service] = lambda: fake
        client = TestClient(app)
        resp = client.post("/api/v1/auth/register", json={"email": "taken@example.com", "name": "Dupe", "password": "password123"})
        app.dependency_overrides.pop(get_auth_service, None)
        assert resp.status_code == 400
        assert resp.json()["error"] == "registration_failed"

    def test_register_short_password_returns_422(self):
        fake = _FakeAuthService()
        app.dependency_overrides[get_auth_service] = lambda: fake
        client = TestClient(app)
        resp = client.post("/api/v1/auth/register", json={"email": "x@y.com", "name": "X", "password": "short"})
        app.dependency_overrides.pop(get_auth_service, None)
        assert resp.status_code == 422

    def test_register_invalid_email_returns_422(self):
        fake = _FakeAuthService()
        app.dependency_overrides[get_auth_service] = lambda: fake
        client = TestClient(app)
        resp = client.post("/api/v1/auth/register", json={"email": "not-an-email", "name": "X", "password": "password123"})
        app.dependency_overrides.pop(get_auth_service, None)
        assert resp.status_code == 422


class TestAuthLogin:
    def test_login_success(self):
        fake = _FakeAuthService()
        app.dependency_overrides[get_auth_service] = lambda: fake
        client = TestClient(app)
        resp = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "correct"})
        app.dependency_overrides.pop(get_auth_service, None)
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password_returns_401(self):
        fake = _FakeAuthService()
        app.dependency_overrides[get_auth_service] = lambda: fake
        client = TestClient(app)
        resp = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrongpassword"})
        app.dependency_overrides.pop(get_auth_service, None)
        assert resp.status_code == 401
        assert resp.json()["error"] == "authentication_failed"

    def test_login_rate_limit_blocks_repeated_failures(self, monkeypatch):
        from backend.api.routes import auth as auth_routes
        from backend.services.rate_limiter import LoginAttemptLimiter

        fake = _FakeAuthService()
        monkeypatch.setitem(app.dependency_overrides, get_auth_service, lambda: fake)
        monkeypatch.setattr(auth_routes, "_login_attempt_limiter", LoginAttemptLimiter(max_attempts=1))
        client = TestClient(app)

        first = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrongpassword"})
        second = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrongpassword"})

        assert first.status_code == 401
        assert second.status_code == 429
        assert second.json()["error"] == "login_rate_limit"

    def test_login_does_not_expose_password_hash(self):
        fake = _FakeAuthService()
        app.dependency_overrides[get_auth_service] = lambda: fake
        client = TestClient(app)
        resp = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "correct"})
        app.dependency_overrides.pop(get_auth_service, None)
        assert "password_hash" not in resp.text
        assert "password" not in resp.json().get("user", {})


class TestAuthMe:
    def test_me_returns_current_user(self, auth_client, user_a):
        resp = auth_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == user_a.email
        assert body["id"] == user_a.id

    def test_me_does_not_expose_password_hash(self, auth_client):
        resp = auth_client.get("/api/v1/auth/me")
        assert "password_hash" not in resp.text

    def test_me_unauthenticated_returns_401(self, unauth_client):
        resp = unauth_client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestAuthLogout:
    def test_logout_returns_success(self, auth_client):
        resp = auth_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_logout_requires_auth(self, unauth_client):
        resp = unauth_client.post("/api/v1/auth/logout")
        assert resp.status_code == 401


class TestGoogleAuthStatus:
    def test_google_status_unconfigured(self, auth_client):
        resp = auth_client.get("/api/v1/auth/google/status")
        assert resp.status_code == 200
        assert resp.json()["configured"] is False


# ─── Dataset ownership tests ───────────────────────────────────────────────────

class TestDatasetOwnership:
    def _management_stub(self, user: UserRecord, registry: _RegistryStub, raise_on_get: str | None = None) -> DatasetManagementService:
        access = DatasetAccessService(registry, user)

        class _Stub(DatasetManagementService):
            def __init__(self) -> None:
                pass

            def list_datasets(self) -> list[dict]:
                return [{"dataset_id": r.dataset_id, "dataset_name": r.dataset_name, "filename": r.original_filename, "original_filename": r.original_filename, "row_count": r.row_count, "column_count": r.column_count, "status": r.status, "is_builtin": r.is_builtin, "created_at": r.created_at.isoformat()} for r in access.list_accessible()]

            def get_dataset(self, dataset_id: str) -> dict:
                try:
                    r = access.require_dataset(dataset_id)
                except DatasetAccessError as e:
                    raise DatasetManagementError(str(e)) from e
                return {"dataset_id": r.dataset_id, "dataset_name": r.dataset_name, "filename": r.original_filename, "rows": r.row_count, "columns": r.column_count, "status": r.status, "is_builtin": r.is_builtin, "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(), "validation": {}}

        return _Stub()

    def test_user_sees_only_own_datasets(self, user_a, user_b):
        registry = _RegistryStub()
        ds_a = _make_dataset("aaaa-1111-aaaa-1111-aaaaaaaaaaaa", user_a.id)
        ds_b = _make_dataset("bbbb-2222-bbbb-2222-bbbbbbbbbbbb", user_b.id)
        registry.datasets[ds_a.dataset_id] = ds_a
        registry.datasets[ds_b.dataset_id] = ds_b

        mgmt_a = self._management_stub(user_a, registry)
        mgmt_b = self._management_stub(user_b, registry)

        ids_a = {item["dataset_id"] for item in mgmt_a.list_datasets()}
        ids_b = {item["dataset_id"] for item in mgmt_b.list_datasets()}

        assert ds_a.dataset_id in ids_a
        assert ds_b.dataset_id not in ids_a
        assert ds_b.dataset_id in ids_b
        assert ds_a.dataset_id not in ids_b

    def test_user_cannot_access_other_users_dataset(self, user_a, user_b):
        registry = _RegistryStub()
        ds_b = _make_dataset("bbbb-2222-bbbb-2222-bbbbbbbbbbbb", user_b.id)
        registry.datasets[ds_b.dataset_id] = ds_b

        mgmt_a = self._management_stub(user_a, registry)
        with pytest.raises(DatasetManagementError):
            mgmt_a.get_dataset(ds_b.dataset_id)

    def test_datasets_api_returns_only_owned_datasets(self, user_a, user_b):
        registry = _RegistryStub()
        ds_a = _make_dataset("aaaa-1111-aaaa-1111-aaaaaaaaaaaa", user_a.id)
        ds_b = _make_dataset("bbbb-2222-bbbb-2222-bbbbbbbbbbbb", user_b.id)
        registry.datasets[ds_a.dataset_id] = ds_a
        registry.datasets[ds_b.dataset_id] = ds_b

        access_a = DatasetAccessService(registry, user_a)
        mgmt_a = self._management_stub(user_a, registry)
        app.dependency_overrides[get_current_user] = lambda: user_a
        app.dependency_overrides[get_dataset_management_service] = lambda: mgmt_a
        client = TestClient(app)
        resp = client.get("/api/v1/datasets")
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_dataset_management_service, None)

        assert resp.status_code == 200
        returned_ids = {d["dataset_id"] for d in resp.json()["datasets"]}
        assert ds_a.dataset_id in returned_ids
        assert ds_b.dataset_id not in returned_ids

    def test_get_dataset_returns_404_for_other_users_dataset(self, user_a, user_b):
        registry = _RegistryStub()
        ds_b = _make_dataset("bbbb-2222-bbbb-2222-bbbbbbbbbbbb", user_b.id)
        registry.datasets[ds_b.dataset_id] = ds_b

        mgmt_a = self._management_stub(user_a, registry)
        app.dependency_overrides[get_current_user] = lambda: user_a
        app.dependency_overrides[get_dataset_management_service] = lambda: mgmt_a
        client = TestClient(app)
        resp = client.get(f"/api/v1/datasets/{ds_b.dataset_id}")
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_dataset_management_service, None)

        assert resp.status_code == 404

    def test_unauthenticated_dataset_list_returns_401(self, unauth_client):
        resp = unauth_client.get("/api/v1/datasets")
        assert resp.status_code == 401

    def test_unauthenticated_dataset_upload_returns_401(self, unauth_client):
        import io
        resp = unauth_client.post(
            "/api/v1/datasets/upload",
            files={"file": ("test.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
        )
        assert resp.status_code == 401


class TestAnalyticsOwnership:
    def test_analytics_requires_authentication(self, unauth_client):
        resp = unauth_client.get("/api/v1/analytics/summary")
        assert resp.status_code == 401

    def test_analytics_run_requires_authentication(self, unauth_client):
        resp = unauth_client.post("/api/v1/analytics/run", json={"operation": "overview"})
        assert resp.status_code == 401


class TestVisualizationOwnership:
    def test_visualization_requires_authentication(self, unauth_client):
        resp = unauth_client.post("/api/v1/visualizations/generate", json={"chart_type": "bar", "analysis_operation": "placement_by_internship"})
        assert resp.status_code == 401


class TestNLSQLOwnership:
    def test_nlsql_validate_requires_authentication(self, unauth_client):
        resp = unauth_client.post("/api/v1/nlsql/validate", json={"question": "How many rows?", "dataset_id": "demo-placement"})
        assert resp.status_code == 401

    def test_nlsql_execute_requires_authentication(self, unauth_client):
        resp = unauth_client.post("/api/v1/nlsql/execute", json={"plan": {}, "dataset_id": "demo-placement"})
        assert resp.status_code == 401
