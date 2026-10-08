"""Tests for Phase 16 — Post-Launch Monitoring, User Analytics, Feedback & Admin Oversight."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_current_user, get_monitoring_service, get_repository, require_admin_user
from backend.core.user_model import UserRecord
from backend.main import app
from backend.repositories.monitoring_repository import MonitoringRepository
from backend.services.monitoring_service import MonitoringService


@pytest.fixture
def mock_db_config():
    """Mock DatabaseConfig for in-memory monitoring tests."""
    mock = MagicMock()
    mock.database = "askmydata_test"
    return mock


@pytest.fixture
def monitoring_repo(mock_db_config):
    """In-memory simulated repository for testing service logic."""
    events = []
    sessions = []
    errors = []
    feedback = []
    ai_feedback = []
    ai_logs = []

    repo = MagicMock(spec=MonitoringRepository)

    def mock_log_event(user_id, event_type, metadata=None):
        events.append({"user_id": user_id, "event_type": event_type, "metadata": metadata})
        return "evt-123"

    def mock_start_session(user_id, ip_address=None, user_agent=None):
        sessions.append({"user_id": user_id, "ip": ip_address, "agent": user_agent, "active": True})
        return "sess-123"

    def mock_log_error(request_id, user_id, error_category, endpoint, http_status, error_message, metadata=None):
        errors.append({
            "request_id": request_id,
            "user_id": user_id,
            "error_category": error_category,
            "endpoint": endpoint,
            "http_status": http_status,
            "error_message": error_message,
            "metadata": metadata,
        })
        return "err-123"

    def mock_submit_user_feedback(user_id, feedback_type="general", rating=5, comment=None):
        item = {"id": "fb-123", "user_id": user_id, "feedback_type": feedback_type, "rating": rating, "comment": comment}
        feedback.append(item)
        return item

    def mock_submit_ai_message_feedback(message_id, user_id, rating, reason=None, comment=None):
        item = {"id": "aifb-123", "message_id": message_id, "user_id": user_id, "rating": rating, "reason": reason, "comment": comment}
        ai_feedback.append(item)
        return item

    def mock_get_overview_stats(days=30):
        return {
            "total_users": 10,
            "dau": 3,
            "wau": 7,
            "mau": 10,
            "total_datasets": 5,
            "uploaded_datasets_in_period": 2,
            "total_analyses": 15,
            "failed_analyses": 1,
            "total_ai_requests": 20,
            "successful_ai_requests": 19,
            "avg_ai_response_time_ms": 250.0,
            "total_errors": 2,
            "avg_user_rating": 4.8,
            "ai_helpfulness_rate": 95.0,
        }

    repo.log_event.side_effect = mock_log_event
    repo.start_session.side_effect = mock_start_session
    repo.log_error.side_effect = mock_log_error
    repo.submit_user_feedback.side_effect = mock_submit_user_feedback
    repo.submit_ai_message_feedback.side_effect = mock_submit_ai_message_feedback
    repo.get_overview_stats.side_effect = mock_get_overview_stats
    repo.get_time_series_stats.return_value = [{"date": "2026-10-03", "active_users": 3, "analyses": 5, "dataset_uploads": 1}]
    repo.get_recent_errors.return_value = errors
    repo.get_recent_feedback.return_value = feedback
    repo.get_ai_feedback_summary.return_value = ai_feedback
    repo.cleanup_expired_logs.return_value = {"usage_events": 10, "error_logs": 5, "ai_usage_logs": 8, "user_sessions": 4}

    return repo, events, sessions, errors, feedback, ai_feedback, ai_logs


# -----------------------------------------------------------------------------
# 1. USER ANALYTICS & EVENT TRACKING TESTS
# -----------------------------------------------------------------------------

def test_event_tracking_and_sessions(monitoring_repo):
    repo, events, sessions, _, _, _, _ = monitoring_repo
    service = MonitoringService(repo)

    # Track event
    service.track_event("user-1", "dataset_uploaded", {"dataset_id": "ds-1"})
    assert len(events) == 1
    assert events[0]["event_type"] == "dataset_uploaded"
    assert events[0]["user_id"] == "user-1"
    assert events[0]["metadata"]["dataset_id"] == "ds-1"

    # Start session
    sess_id = service.start_user_session("user-1", ip_address="127.0.0.1", user_agent="PytestBrowser")
    assert sess_id == "sess-123"
    assert len(sessions) == 1
    assert sessions[0]["ip"] == "127.0.0.1"


# -----------------------------------------------------------------------------
# 2. USER FEEDBACK & AI MESSAGE FEEDBACK TESTS
# -----------------------------------------------------------------------------

def test_user_feedback_submission(monitoring_repo):
    repo, events, _, _, feedback, ai_feedback, _ = monitoring_repo
    service = MonitoringService(repo)

    # General feedback
    res = service.submit_general_feedback(user_id="user-1", feedback_type="usability", rating=5, comment="Great platform!")
    assert res["rating"] == 5
    assert len(feedback) == 1
    assert feedback[0]["comment"] == "Great platform!"
    assert any(e["event_type"] == "feedback_submitted" for e in events)

    # AI message answer rating
    ai_res = service.submit_message_feedback(message_id="msg-99", user_id="user-1", rating="helpful", reason=None)
    assert ai_res["rating"] == "helpful"
    assert len(ai_feedback) == 1
    assert ai_feedback[0]["message_id"] == "msg-99"


# -----------------------------------------------------------------------------
# 3. ERROR LOGGING & SECRET SANITIZATION TESTS
# -----------------------------------------------------------------------------

def test_error_logging_redacts_sensitive_keys(monitoring_repo):
    repo, _, _, errors, _, _, _ = monitoring_repo
    service = MonitoringService(repo)

    service.capture_error(
        request_id="rid-100",
        user_id="user-1",
        error_category="database",
        endpoint="/api/v1/datasets",
        http_status=500,
        error_message="Connection failure",
        metadata={"password": "supersecretpassword", "safe_field": "123"},
    )

    assert len(errors) == 1
    captured_meta = errors[0]["metadata"]
    assert captured_meta["password"] == "[REDACTED]"
    assert captured_meta["safe_field"] == "123"


# -----------------------------------------------------------------------------
# 4. ADMIN AUTHORIZATION & SECURITY TESTS
# -----------------------------------------------------------------------------

def test_non_admin_user_rejected_from_admin_endpoints():
    """Verify normal users receive 403 Forbidden when calling admin endpoints."""
    normal_user = UserRecord(
        id="user-normal",
        email="normaluser@example.com",
        name="Normal User",
        password_hash="hash",
        is_active=True,
        is_admin=False,
        created_at=None,
        updated_at=None,
        last_login_at=None,
    )

    mock_repo = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: normal_user
    app.dependency_overrides[get_repository] = lambda: mock_repo
    app.dependency_overrides.pop(require_admin_user, None)

    try:
        client = TestClient(app)

        # Non-admin attempting to access admin analytics
        response = client.get("/api/v1/admin/analytics")
        assert response.status_code == 403
        assert response.json()["error"] == "forbidden_access"

        # Non-admin attempting to access detailed health check
        health_resp = client.get("/api/v1/health/detailed")
        assert health_resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_user_granted_access_to_admin_endpoints(monitoring_repo):
    """Verify authorized admins can access dashboard stats and detailed health metrics."""
    repo, _, _, _, _, _, _ = monitoring_repo
    mock_service = MonitoringService(repo)

    admin_user = UserRecord(
        id="user-admin",
        email="goru@rezzai.com",
        name="Admin Goru",
        password_hash="hash",
        is_active=True,
        is_admin=True,
        created_at=None,
        updated_at=None,
        last_login_at=None,
    )

    mock_db_repo = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_admin_user] = lambda: admin_user
    app.dependency_overrides[get_monitoring_service] = lambda: mock_service
    app.dependency_overrides[get_repository] = lambda: mock_db_repo

    try:
        client = TestClient(app)

        # Admin accessing analytics overview
        response = client.get("/api/v1/admin/analytics")
        assert response.status_code == 200
        data = response.json()
        assert "overview" in data
        assert data["overview"]["total_users"] == 10

        # Admin accessing detailed health check
        health_resp = client.get("/api/v1/health/detailed")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert "telemetry" in health_data
        assert health_data["telemetry"]["active_users_24h"] == 3
    finally:
        app.dependency_overrides.clear()


def test_retention_cleanup_job(monitoring_repo):
    repo, _, _, _, _, _, _ = monitoring_repo
    service = MonitoringService(repo)

    res = service.run_retention_cleanup(usage_days=90, error_days=30)
    assert res["usage_events"] == 10
    assert res["error_logs"] == 5
