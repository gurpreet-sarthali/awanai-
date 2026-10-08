"""Phase 11 — Chat API tests."""

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user
from backend.core.chat_model import ConversationRecord
from backend.main import app

@pytest.fixture()
def unauth_client():
    def _raise():
        from backend.exceptions.handlers import AppError
        raise AppError(401, "authentication_required", "Authentication is required.")

    app.dependency_overrides[get_current_user] = _raise
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_current_user, None)

def test_unauthenticated_chat_endpoints_return_401(unauth_client: TestClient):
    assert unauth_client.get("/api/v1/conversations").status_code == 401
    assert unauth_client.post("/api/v1/conversations", json={"dataset_id": "test"}).status_code == 401
    assert unauth_client.get("/api/v1/conversations/conv-1").status_code == 401
    assert unauth_client.patch("/api/v1/conversations/conv-1", json={"title": "test"}).status_code == 401
    assert unauth_client.delete("/api/v1/conversations/conv-1").status_code == 401
    assert unauth_client.post("/api/v1/conversations/conv-1/messages", json={"question": "test"}).status_code == 401


@pytest.fixture()
def mock_user_a():
    from backend.core.user_model import UserRecord
    from datetime import datetime, UTC
    return UserRecord(
        id="user-a",
        email="a@example.com",
        name="User A",
        password_hash=None,
        google_id=None,
        profile_picture_url=None,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_login_at=None,
    )

@pytest.fixture()
def mock_user_b():
    from backend.core.user_model import UserRecord
    from datetime import datetime, UTC
    return UserRecord(
        id="user-b",
        email="b@example.com",
        name="User B",
        password_hash=None,
        google_id=None,
        profile_picture_url=None,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_login_at=None,
    )

@pytest.fixture()
def client_a(mock_user_a):
    app.dependency_overrides[get_current_user] = lambda: mock_user_a
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture()
def client_b(mock_user_b):
    app.dependency_overrides[get_current_user] = lambda: mock_user_b
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_current_user, None)

class FakeChatService:
    def __init__(self):
        self.convs = {}
        self.msgs = []

    def create_conversation(self, user_id, title, dataset_id=None):
        from datetime import datetime, UTC
        now = datetime.now(UTC)
        conv = ConversationRecord(id="c1", user_id=user_id, dataset_id=dataset_id, title=title, created_at=now, updated_at=now)
        self.convs["c1"] = conv
        return conv

    def get_conversation_for_user(self, conversation_id, user_id):
        from backend.services.chat_service import ChatServiceError
        conv = self.convs.get(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ChatServiceError("Not found")
        return conv

    def list_conversations(self, user_id, limit=50, offset=0):
        return [c for c in self.convs.values() if c.user_id == user_id]

    def rename_conversation(self, conversation_id, user_id, title):
        from datetime import datetime, UTC
        conv = self.get_conversation_for_user(conversation_id, user_id)
        import dataclasses
        new_conv = dataclasses.replace(conv, title=title, updated_at=datetime.now(UTC))
        self.convs[conversation_id] = new_conv
        return new_conv

    def delete_conversation(self, conversation_id, user_id):
        self.get_conversation_for_user(conversation_id, user_id)
        del self.convs[conversation_id]

    def get_messages(self, conversation_id, user_id, limit=100, offset=0):
        self.get_conversation_for_user(conversation_id, user_id)
        return []

@pytest.fixture(autouse=True)
def mock_chat_service():
    from backend.api.dependencies import get_chat_service
    fake = FakeChatService()
    app.dependency_overrides[get_chat_service] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_chat_service, None)

@pytest.fixture()
def client():
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.pop(get_current_user, None)

def test_conversation_crud_and_isolation(client, mock_user_a, mock_user_b):
    # User A creates a conversation
    app.dependency_overrides[get_current_user] = lambda: mock_user_a
    resp = client.post("/api/v1/conversations", json={})
    assert resp.status_code == 200
    conv_a = resp.json()
    conv_id = conv_a["id"]
    assert conv_a["title"] == "New Conversation"

    # User B should not see User A's conversation
    app.dependency_overrides[get_current_user] = lambda: mock_user_b
    assert client.get(f"/api/v1/conversations/{conv_id}").status_code == 404
    
    # User B should have an empty list
    resp_b = client.get("/api/v1/conversations")
    assert resp_b.status_code == 200
    assert len(resp_b.json()) == 0

    # User A renames the conversation
    app.dependency_overrides[get_current_user] = lambda: mock_user_a
    resp = client.patch(f"/api/v1/conversations/{conv_id}", json={"title": "My Analysis"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "My Analysis"

    # User B tries to rename
    app.dependency_overrides[get_current_user] = lambda: mock_user_b
    assert client.patch(f"/api/v1/conversations/{conv_id}", json={"title": "Hacked"}).status_code == 404

    # User A lists their conversations
    app.dependency_overrides[get_current_user] = lambda: mock_user_a
    resp = client.get("/api/v1/conversations")
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "My Analysis"

    # User B tries to delete
    app.dependency_overrides[get_current_user] = lambda: mock_user_b
    assert client.delete(f"/api/v1/conversations/{conv_id}").status_code == 404

    # User A deletes
    app.dependency_overrides[get_current_user] = lambda: mock_user_a
    assert client.delete(f"/api/v1/conversations/{conv_id}").status_code == 200

    # Now it's gone for User A
    assert client.get(f"/api/v1/conversations/{conv_id}").status_code == 404
