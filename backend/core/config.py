"""Environment-based API configuration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from analytics.database import ConfigurationError, DatabaseConfig

load_dotenv()

_log = logging.getLogger(__name__)
_DEV_DEFAULTS = frozenset({"dev-only-change-me", "dev-only-change-me-in-production", "change-me-in-production", ""})  


@dataclass(frozen=True)
class AppSettings:
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    gemini_model: str = "gemini-2.5-flash"
    ai_max_requests_per_minute: int = 10
    ai_max_requests_per_day: int = 100
    max_result_rows: int = 1000
    max_query_length: int = 10000
    query_timeout_seconds: int = 30
    max_upload_size_mb: int = 25
    max_csv_rows: int = 200_000
    max_csv_columns: int = 200
    dataset_preview_limit: int = 20
    dataset_uploads_dir: str = "data/uploads"
    jwt_secret_key: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    # OAuth CSRF state secret (must be set in production)
    oauth_state_secret: str = "dev-oauth-state-secret"
    # Maximum login attempts before lockout (0 = disabled)
    max_login_attempts: int = 5
    # Data Retention (Phase 16)
    usage_log_retention_days: int = 90
    error_log_retention_days: int = 30
    # Billing / Usage Limits (Phase 20)
    payment_provider: str = "mock"
    payment_api_key: str = ""
    payment_webhook_secret: str = ""
    payment_public_key: str = ""
    webhook_encryption_key: str = ""
    # Designated Admin Emails
    admin_emails: tuple[str, ...] = ("goru@rezzai.com", "admin@askmydata.local")

    def validate_production_secrets(self) -> None:
        """Raise or warn loudly if insecure secrets are used outside development."""
        if self.app_env == "production":
            if self.jwt_secret_key in _DEV_DEFAULTS:
                raise RuntimeError(
                    "FATAL: JWT_SECRET_KEY is still the dev default. "
                    "Set a strong secret in .env before starting in production."
                )
            if self.oauth_state_secret in _DEV_DEFAULTS or self.oauth_state_secret == "dev-oauth-state-secret":
                raise RuntimeError(
                    "FATAL: OAUTH_STATE_SECRET is not configured. "
                    "Set a strong secret in .env before starting in production."
                )
            if self.max_login_attempts <= 0:
                raise RuntimeError("FATAL: MAX_LOGIN_ATTEMPTS must be positive in production.")
            if len(self.jwt_secret_key) < 32:
                _log.warning("JWT_SECRET_KEY is very short (%d chars). Use at least 32 random chars.", len(self.jwt_secret_key))
        elif self.jwt_secret_key in _DEV_DEFAULTS:
            _log.warning("JWT_SECRET_KEY is using the dev default — never use this in production!")

    @classmethod
    def from_environment(cls) -> "AppSettings":
        raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            cors_origins=origins or ("http://localhost:5173", "http://127.0.0.1:5173"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            ai_max_requests_per_minute=int(os.getenv("AI_MAX_REQUESTS_PER_MINUTE", "10")),
            ai_max_requests_per_day=int(os.getenv("AI_MAX_REQUESTS_PER_DAY", "100")),
            max_result_rows=int(os.getenv("MAX_RESULT_ROWS", "1000")),
            max_query_length=int(os.getenv("MAX_QUERY_LENGTH", "10000")),
            query_timeout_seconds=int(os.getenv("QUERY_TIMEOUT_SECONDS", "30")),
            max_upload_size_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "25")),
            max_csv_rows=int(os.getenv("MAX_CSV_ROWS", "200000")),
            max_csv_columns=int(os.getenv("MAX_CSV_COLUMNS", "200")),
            dataset_preview_limit=int(os.getenv("DATASET_PREVIEW_LIMIT", "20")),
            dataset_uploads_dir=os.getenv("DATASET_UPLOADS_DIR", "data/uploads"),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", "dev-only-change-me"),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
            oauth_state_secret=os.getenv("OAUTH_STATE_SECRET", "dev-oauth-state-secret"),
            max_login_attempts=int(os.getenv("MAX_LOGIN_ATTEMPTS", "5")),
            usage_log_retention_days=int(os.getenv("USAGE_LOG_RETENTION_DAYS", "90")),
            error_log_retention_days=int(os.getenv("ERROR_LOG_RETENTION_DAYS", "30")),
            payment_provider=os.getenv("PAYMENT_PROVIDER", "mock"),
            payment_api_key=os.getenv("PAYMENT_API_KEY", ""),
            payment_webhook_secret=os.getenv("PAYMENT_WEBHOOK_SECRET", ""),
            payment_public_key=os.getenv("PAYMENT_PUBLIC_KEY", ""),
            webhook_encryption_key=os.getenv("WEBHOOK_ENCRYPTION_KEY", ""),
            admin_emails=tuple(
                email.strip().lower()
                for email in os.getenv("ADMIN_EMAILS", "goru@rezzai.com,admin@askmydata.local").split(",")
                if email.strip()
            ),
        )

    def database_config(self) -> DatabaseConfig:
        return DatabaseConfig.from_environment()


settings = AppSettings.from_environment()
settings.validate_production_secrets()