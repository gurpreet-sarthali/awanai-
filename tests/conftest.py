from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.api.dependencies import get_current_user, reset_dependency_singletons
from backend.core.user_model import UserRecord
from backend.main import app


@pytest.fixture(autouse=True)
def clean_dependencies():
    reset_dependency_singletons()
    yield
    reset_dependency_singletons()


@pytest.fixture
def test_user() -> UserRecord:
    now = datetime.now(UTC)
    return UserRecord(
        id="test-user-0000-0000-0000-000000000001",
        email="tester@example.com",
        name="Test User",
        password_hash="hashed",
        google_id=None,
        profile_picture_url=None,
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )


@pytest.fixture(autouse=True)
def authenticate_tests(request, test_user: UserRecord):
    if "no_auth_mock" in request.keywords:
        yield
        return
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
