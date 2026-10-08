"""Phase 14 — Production hardening tests.

Tests: config validation, rate limiter, security headers, auth service.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest


# ─── Config validation ────────────────────────────────────────────────────────

class TestConfigValidation:
    def test_dev_default_jwt_warns_not_raises_in_dev(self, monkeypatch, caplog):
        """Dev default JWT key should log a warning, not crash, in development."""
        import logging
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("JWT_SECRET_KEY", "dev-only-change-me")
        import importlib
        import backend.core.config as cfg
        importlib.reload(cfg)
        with caplog.at_level(logging.WARNING, logger="backend.core.config"):
            cfg.settings.validate_production_secrets()
        assert any("dev default" in r.message.lower() or "never use" in r.message.lower() for r in caplog.records), \
            "Expected a warning about dev JWT secret"

    def test_production_with_dev_jwt_raises(self, monkeypatch):
        """Production env with dev JWT key must raise RuntimeError."""
        # Build AppSettings directly instead of reloading the module
        # (module reload would trigger validate_production_secrets at module level,
        #  which would raise outside the pytest.raises context).
        import backend.core.config as cfg
        prod_settings = cfg.AppSettings(
            app_env="production",
            jwt_secret_key="dev-only-change-me",
            is_active=True,  # not a real field — just using dataclass directly
        ) if False else cfg.AppSettings.__new__(cfg.AppSettings)
        # Use dataclasses to build it properly
        import dataclasses
        prod_settings = dataclasses.replace(
            cfg.AppSettings.from_environment(),
            app_env="production",
            jwt_secret_key="dev-only-change-me",
        )
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            prod_settings.validate_production_secrets()

    def test_production_with_strong_jwt_passes(self, monkeypatch):
        """Production env with a strong JWT secret should pass validation."""
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "a" * 64)
        monkeypatch.setenv("OAUTH_STATE_SECRET", "b" * 64)
        import importlib
        import backend.core.config as cfg
        importlib.reload(cfg)
        cfg.settings.validate_production_secrets()


# ─── Rate limiter ─────────────────────────────────────────────────────────────

class TestAIRateLimiter:
    def test_global_per_minute_limit(self):
        """Global per-minute limit should fire when user_id=None (bypasses per-user check)."""
        from backend.services.rate_limiter import AIRateLimiter, AIRateLimitError
        limiter = AIRateLimiter(per_minute=3, per_day=100)
        for _ in range(3):
            limiter.check(user_id=None)  # Use None so only global counter is tested
        with pytest.raises(AIRateLimitError):
            limiter.check(user_id=None)


class TestLoginAttemptLimiter:
    def test_blocks_after_configured_failed_attempts(self):
        from backend.services.rate_limiter import AIRateLimitError, LoginAttemptLimiter

        limiter = LoginAttemptLimiter(max_attempts=2, window_seconds=60)
        limiter.check("alice@example.com:127.0.0.1")
        limiter.record_failure("alice@example.com:127.0.0.1")
        limiter.check("alice@example.com:127.0.0.1")
        limiter.record_failure("alice@example.com:127.0.0.1")

        with pytest.raises(AIRateLimitError, match="Too many failed sign-in attempts"):
            limiter.check("alice@example.com:127.0.0.1")

    def test_identity_storage_is_bounded(self):
        from backend.services.rate_limiter import LoginAttemptLimiter

        limiter = LoginAttemptLimiter(max_attempts=5, max_identities=1)
        limiter.record_failure("first@example.com:127.0.0.1")
        limiter.record_failure("second@example.com:127.0.0.1")

        assert len(limiter._failures) == 1

    def test_different_users_independent_limits(self):
        """Two users should not affect each other's per-user counters."""
        from backend.services.rate_limiter import AIRateLimiter, AIRateLimitError
        limiter = AIRateLimiter(per_minute=10, per_day=100)
        for _ in range(4):
            limiter.check(user_id="user-a")
        # user-b should still get their own quota
        limiter.check(user_id="user-b")

    def test_no_user_id_only_global_limit(self):
        from backend.services.rate_limiter import AIRateLimiter, AIRateLimitError
        limiter = AIRateLimiter(per_minute=5, per_day=100)
        for _ in range(5):
            limiter.check(user_id=None)
        with pytest.raises(AIRateLimitError):
            limiter.check(user_id=None)


# ─── OAuth CSRF state ────────────────────────────────────────────────────────

class TestOAuthCsrfState:
    def _make_service(self):
        from backend.repositories.user_repository import UserRepository
        repo = MagicMock(spec=UserRepository)
        from backend.services.auth_service import AuthService
        return AuthService(repo)

    def test_valid_state_passes(self):
        svc = self._make_service()
        state = svc._generate_oauth_state()
        svc.validate_oauth_state(state)

    def test_tampered_state_raises(self):
        from backend.services.auth_service import AuthenticationError
        svc = self._make_service()
        state = svc._generate_oauth_state()
        tampered = state[:-4] + "xxxx"
        with pytest.raises(AuthenticationError):
            svc.validate_oauth_state(tampered)

    def test_expired_state_raises(self):
        from backend.services.auth_service import AuthenticationError
        import hashlib, hmac, secrets
        svc = self._make_service()
        from backend.core.config import settings
        nonce = secrets.token_urlsafe(16)
        old_ts = str(int(time.time()) - 700)
        payload = f"{nonce}.{old_ts}"
        sig = hmac.new(settings.oauth_state_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        old_state = f"{payload}.{sig}"
        with pytest.raises(AuthenticationError, match="expired"):
            svc.validate_oauth_state(old_state, max_age_seconds=600)

    def test_malformed_state_raises(self):
        from backend.services.auth_service import AuthenticationError
        svc = self._make_service()
        with pytest.raises(AuthenticationError):
            svc.validate_oauth_state("not-a-valid-state")

    def test_callback_rejects_invalid_state_before_google_request(self, monkeypatch):
        from dataclasses import replace
        from unittest.mock import MagicMock

        import httpx
        import backend.services.auth_service as auth_module
        from backend.services.auth_service import AuthenticationError

        svc = self._make_service()
        monkeypatch.setattr(
            auth_module,
            "settings",
            replace(
                auth_module.settings,
                google_client_id="test-client",
                google_client_secret="test-secret",
                google_redirect_uri="http://localhost:5173/auth/google/callback",
            ),
        )
        google_request = MagicMock()
        monkeypatch.setattr(httpx, "post", google_request)

        with pytest.raises(AuthenticationError, match="OAuth state"):
            svc.handle_google_callback("authorization-code", "invalid-state")

        google_request.assert_not_called()


# ─── Security headers ────────────────────────────────────────────────────────

class TestSecurityHeaders:
    def test_security_headers_present(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "X-Request-ID" in response.headers

    def test_request_id_echoed(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/health", headers={"X-Request-ID": "test-123"})
        assert response.headers.get("X-Request-ID") == "test-123"
