"""Monitoring, User Analytics, Error Tracking, and Feedback Service."""

from __future__ import annotations

import logging
from typing import Any

from backend.repositories.monitoring_repository import MonitoringRepository

_log = logging.getLogger(__name__)


class MonitoringService:
    def __init__(self, repository: MonitoringRepository) -> None:
        self.repository = repository

    def ensure_schema(self) -> None:
        self.repository.ensure_schema()

    def track_event(self, user_id: str | None, event_type: str, metadata: dict[str, Any] | None = None) -> str:
        """Record a user activity event without raising exceptions."""
        try:
            return self.repository.log_event(user_id=user_id, event_type=event_type, metadata=metadata)
        except Exception as err:
            _log.warning("MonitoringService track_event error: %s", err)
            return ""

    def start_user_session(self, user_id: str, ip_address: str | None = None, user_agent: str | None = None) -> str:
        """Start a user tracking session."""
        try:
            session_id = self.repository.start_session(user_id=user_id, ip_address=ip_address, user_agent=user_agent)
            self.track_event(user_id=user_id, event_type="session_started", metadata={"session_id": session_id})
            return session_id
        except Exception as err:
            _log.warning("MonitoringService start_user_session error: %s", err)
            return ""

    def end_user_session(self, session_id: str, user_id: str | None = None) -> None:
        """End a user tracking session."""
        try:
            self.repository.end_session(session_id=session_id)
            if user_id:
                self.track_event(user_id=user_id, event_type="session_ended", metadata={"session_id": session_id})
        except Exception as err:
            _log.warning("MonitoringService end_user_session error: %s", err)

    def log_ai_request(
        self,
        *,
        user_id: str | None,
        request_type: str = "intent_generation",
        model_name: str = "gemini-2.5-flash",
        status: str = "success",
        response_time_ms: float = 0.0,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        error_message: str | None = None,
    ) -> str:
        """Log safe AI request metadata."""
        try:
            return self.repository.log_ai_usage(
                user_id=user_id,
                request_type=request_type,
                model_name=model_name,
                status=status,
                response_time_ms=response_time_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                error_message=error_message,
            )
        except Exception as err:
            _log.warning("MonitoringService log_ai_request error: %s", err)
            return ""

    def capture_error(
        self,
        *,
        request_id: str | None = None,
        user_id: str | None = None,
        error_category: str = "backend",
        endpoint: str = "unknown",
        http_status: int = 500,
        error_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Safely capture and persist an application error."""
        try:
            # Strip secrets from metadata if present
            safe_metadata = {}
            if metadata:
                for k, v in metadata.items():
                    if k.lower() in ("password", "secret", "token", "key", "authorization", "raw_csv"):
                        safe_metadata[k] = "[REDACTED]"
                    else:
                        safe_metadata[k] = str(v)[:256]

            return self.repository.log_error(
                request_id=request_id,
                user_id=user_id,
                error_category=error_category,
                endpoint=endpoint,
                http_status=http_status,
                error_message=error_message,
                metadata=safe_metadata,
            )
        except Exception as err:
            _log.warning("MonitoringService capture_error failed: %s", err)
            return ""

    def submit_general_feedback(
        self,
        *,
        user_id: str,
        feedback_type: str = "general",
        rating: int = 5,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Process user feedback submission."""
        result = self.repository.submit_user_feedback(
            user_id=user_id,
            feedback_type=feedback_type,
            rating=rating,
            comment=comment,
        )
        self.track_event(
            user_id=user_id,
            event_type="feedback_submitted",
            metadata={"feedback_type": feedback_type, "rating": rating},
        )
        return result

    def submit_message_feedback(
        self,
        *,
        message_id: str,
        user_id: str,
        rating: str,
        reason: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Process AI answer message feedback."""
        return self.repository.submit_ai_message_feedback(
            message_id=message_id,
            user_id=user_id,
            rating=rating,
            reason=reason,
            comment=comment,
        )

    def get_admin_dashboard_data(self, days: int = 30) -> dict[str, Any]:
        """Gather aggregated metrics for the admin dashboard."""
        overview = self.repository.get_overview_stats(days=days)
        time_series = self.repository.get_time_series_stats(days=days)
        recent_errors = self.repository.get_recent_errors(limit=25)
        recent_feedback = self.repository.get_recent_feedback(limit=25)
        recent_ai_feedback = self.repository.get_ai_feedback_summary(limit=25)

        return {
            "overview": overview,
            "time_series": time_series,
            "errors": recent_errors,
            "feedback": recent_feedback,
            "ai_feedback": recent_ai_feedback,
        }

    def run_retention_cleanup(self, usage_days: int = 90, error_days: int = 30) -> dict[str, int]:
        """Cleanup expired logs according to data retention policy."""
        return self.repository.cleanup_expired_logs(usage_days=usage_days, error_days=error_days)
