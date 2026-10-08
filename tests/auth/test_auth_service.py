import pytest

from backend.core.config import settings
from backend.repositories.user_repository import UserNotFoundError, UserRepository
from backend.services.auth_service import AuthenticationError, AuthService


class InMemoryUserRepository:
    SYSTEM_USER_ID = UserRepository.SYSTEM_USER_ID

    def __init__(self) -> None:
        self.users = {}

    def create_user(self, *, email: str, name: str, password_hash: str | None, google_id: str | None = None, profile_picture_url: str | None = None):
        from backend.core.user_model import UserRecord
        from datetime import UTC, datetime

        if email in {user.email for user in self.users.values()}:
            from backend.repositories.user_repository import UserConflictError

            raise UserConflictError("duplicate")
        user_id = f"user-{len(self.users) + 1}"
        now = datetime.now(UTC)
        user = UserRecord(
            id=user_id,
            email=email.lower().strip(),
            name=name,
            password_hash=password_hash,
            google_id=google_id,
            profile_picture_url=profile_picture_url,
            is_active=True,
            created_at=now,
            updated_at=now,
            last_login_at=None,
        )
        self.users[user_id] = user
        return user

    def get_by_email(self, email: str):
        for user in self.users.values():
            if user.email == email.lower().strip():
                return user
        raise UserNotFoundError(email)

    def get_by_id(self, user_id: str):
        if user_id not in self.users:
            raise UserNotFoundError(user_id)
        return self.users[user_id]

    def touch_login(self, user_id: str) -> None:
        return None


def test_register_login_and_token_roundtrip():
    service = AuthService(InMemoryUserRepository())
    user, token = service.register(email="alice@example.com", name="Alice", password="password123")
    assert user.email == "alice@example.com"
    resolved = service.resolve_token(token)
    assert resolved.id == user.id
    _, login_token = service.login(email="alice@example.com", password="password123")
    assert service.resolve_token(login_token).email == "alice@example.com"


def test_duplicate_registration_rejected():
    service = AuthService(InMemoryUserRepository())
    service.register(email="alice@example.com", name="Alice", password="password123")
    with pytest.raises(AuthenticationError):
        service.register(email="alice@example.com", name="Alice Again", password="password123")


def test_invalid_login_rejected():
    service = AuthService(InMemoryUserRepository())
    service.register(email="alice@example.com", name="Alice", password="password123")
    with pytest.raises(AuthenticationError):
        service.login(email="alice@example.com", password="wrong-password")
