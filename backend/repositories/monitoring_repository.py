"""Monitoring, Analytics, Error Tracking, and Feedback Repository."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from analytics.database import DatabaseConfig, connect

_log = logging.getLogger(__name__)


class MonitoringRepository:
    """Repository managing tables for activity events, sessions, AI usage, error tracking, and feedback."""

    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        """Create monitoring and feedback tables if they do not exist."""
        try:
            connection = connect(self.config)
        except Exception as err:
            _log.warning("MonitoringRepository: DB connection failed in ensure_schema: %s", err)
            return
        try:
            cursor = connection.cursor()

            if self.config.uses_sqlite:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS usage_events (
                        id TEXT NOT NULL PRIMARY KEY,
                        user_id TEXT NULL,
                        event_type TEXT NOT NULL,
                        metadata_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id TEXT NOT NULL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        ended_at TIMESTAMP NULL,
                        duration_seconds INTEGER NULL,
                        ip_address TEXT NULL,
                        user_agent TEXT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_usage_logs (
                        id TEXT NOT NULL PRIMARY KEY,
                        user_id TEXT NULL,
                        request_type TEXT NOT NULL DEFAULT 'intent_generation',
                        model_name TEXT NOT NULL DEFAULT 'gemini-2.5-flash',
                        status TEXT NOT NULL DEFAULT 'success',
                        response_time_ms REAL NOT NULL DEFAULT 0.0,
                        prompt_tokens INTEGER NULL,
                        completion_tokens INTEGER NULL,
                        total_tokens INTEGER NULL,
                        error_message TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS error_logs (
                        id TEXT NOT NULL PRIMARY KEY,
                        request_id TEXT NULL,
                        user_id TEXT NULL,
                        error_category TEXT NOT NULL,
                        endpoint TEXT NOT NULL,
                        http_status INTEGER NOT NULL DEFAULT 500,
                        error_message TEXT NOT NULL,
                        metadata_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id TEXT NOT NULL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        feedback_type TEXT NOT NULL DEFAULT 'general',
                        rating INTEGER NOT NULL DEFAULT 5,
                        comment TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_message_feedback (
                        id TEXT NOT NULL PRIMARY KEY,
                        message_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        rating TEXT NOT NULL,
                        reason TEXT NULL,
                        comment TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            else:
                # 1. Usage Events
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS usage_events (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        user_id VARCHAR(64) NULL,
                        event_type VARCHAR(64) NOT NULL,
                        metadata_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_usage_user (user_id),
                        KEY idx_usage_type (event_type),
                        KEY idx_usage_created (created_at)
                    )
                    """
                )

                # 2. User Sessions
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        ended_at TIMESTAMP NULL,
                        duration_seconds INT NULL,
                        ip_address VARCHAR(45) NULL,
                        user_agent VARCHAR(255) NULL,
                        KEY idx_sessions_user (user_id),
                        KEY idx_sessions_started (started_at)
                    )
                    """
                )

                # 3. AI Usage Logs
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_usage_logs (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        user_id VARCHAR(64) NULL,
                        request_type VARCHAR(64) NOT NULL DEFAULT 'intent_generation',
                        model_name VARCHAR(64) NOT NULL DEFAULT 'gemini-2.5-flash',
                        status VARCHAR(32) NOT NULL DEFAULT 'success',
                        response_time_ms FLOAT NOT NULL DEFAULT 0.0,
                        prompt_tokens INT NULL,
                        completion_tokens INT NULL,
                        total_tokens INT NULL,
                        error_message VARCHAR(512) NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_ai_user (user_id),
                        KEY idx_ai_status (status),
                        KEY idx_ai_type (request_type),
                        KEY idx_ai_created (created_at)
                    )
                    """
                )

                # 4. Error Logs
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS error_logs (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        request_id VARCHAR(64) NULL,
                        user_id VARCHAR(64) NULL,
                        error_category VARCHAR(64) NOT NULL,
                        endpoint VARCHAR(255) NOT NULL,
                        http_status INT NOT NULL DEFAULT 500,
                        error_message VARCHAR(1024) NOT NULL,
                        metadata_json TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_errors_category (error_category),
                        KEY idx_errors_status (http_status),
                        KEY idx_errors_created (created_at)
                    )
                    """
                )

                # 5. User General Feedback
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        feedback_type VARCHAR(32) NOT NULL DEFAULT 'general',
                        rating INT NOT NULL DEFAULT 5,
                        comment TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_feedback_user (user_id),
                        KEY idx_feedback_type (feedback_type),
                        KEY idx_feedback_rating (rating),
                        KEY idx_feedback_created (created_at)
                    )
                    """
                )

                # 6. AI Message Answer Feedback
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ai_message_feedback (
                        id VARCHAR(64) NOT NULL PRIMARY KEY,
                        message_id VARCHAR(64) NOT NULL,
                        user_id VARCHAR(64) NOT NULL,
                        rating VARCHAR(16) NOT NULL,
                        reason VARCHAR(64) NULL,
                        comment TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_ai_fb_msg (message_id),
                        KEY idx_ai_fb_user (user_id),
                        KEY idx_ai_fb_rating (rating),
                        KEY idx_ai_fb_created (created_at)
                    )
                    """
                )

            connection.commit()
            cursor.close()
        finally:
            connection.close()

    # -------------------------------------------------------------------------
    # WRITE OPERATIONS
    # -------------------------------------------------------------------------

    def log_event(self, user_id: str | None, event_type: str, metadata: dict[str, Any] | None = None) -> str:
        event_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO usage_events (id, user_id, event_type, metadata_json)
                VALUES (%s, %s, %s, %s)
                """,
                (event_id, user_id, event_type, json.dumps(metadata) if metadata else None),
            )
            connection.commit()
            cursor.close()
            return event_id
        except Exception as err:
            _log.warning("Failed to log event %s: %s", event_type, err)
            return event_id
        finally:
            connection.close()

    def start_session(self, user_id: str, ip_address: str | None = None, user_agent: str | None = None) -> str:
        session_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO user_sessions (id, user_id, ip_address, user_agent)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, user_id, ip_address, (user_agent[:255] if user_agent else None)),
            )
            connection.commit()
            cursor.close()
            return session_id
        except Exception as err:
            _log.warning("Failed to start session for user %s: %s", user_id, err)
            return session_id
        finally:
            connection.close()

    def end_session(self, session_id: str) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                cursor.execute(
                    """
                    UPDATE user_sessions
                    SET ended_at = CURRENT_TIMESTAMP,
                        duration_seconds = CAST((strftime('%s', 'now') - strftime('%s', started_at)) AS INTEGER)
                    WHERE id = ? AND ended_at IS NULL
                    """,
                    (session_id,),
                )
            else:
                cursor.execute(
                    """
                    UPDATE user_sessions
                    SET ended_at = CURRENT_TIMESTAMP,
                        duration_seconds = TIMESTAMPDIFF(SECOND, started_at, CURRENT_TIMESTAMP)
                    WHERE id = %s AND ended_at IS NULL
                    """,
                    (session_id,),
                )
            connection.commit()
            cursor.close()
        except Exception as err:
            _log.warning("Failed to end session %s: %s", session_id, err)
        finally:
            connection.close()

    def log_ai_usage(
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
        log_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO ai_usage_logs
                (id, user_id, request_type, model_name, status, response_time_ms, prompt_tokens, completion_tokens, total_tokens, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    log_id,
                    user_id,
                    request_type,
                    model_name,
                    status,
                    response_time_ms,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    error_message[:512] if error_message else None,
                ),
            )
            connection.commit()
            cursor.close()
            return log_id
        except Exception as err:
            _log.warning("Failed to log AI usage: %s", err)
            return log_id
        finally:
            connection.close()

    def log_error(
        self,
        *,
        request_id: str | None,
        user_id: str | None,
        error_category: str,
        endpoint: str,
        http_status: int = 500,
        error_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        error_id = str(uuid4())
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO error_logs
                (id, request_id, user_id, error_category, endpoint, http_status, error_message, metadata_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    error_id,
                    request_id,
                    user_id,
                    error_category,
                    endpoint[:255],
                    http_status,
                    error_message[:1024],
                    json.dumps(metadata) if metadata else None,
                ),
            )
            connection.commit()
            cursor.close()
            return error_id
        except Exception as err:
            _log.warning("Failed to log error: %s", err)
            return error_id
        finally:
            connection.close()

    def submit_user_feedback(
        self,
        *,
        user_id: str,
        feedback_type: str = "general",
        rating: int = 5,
        comment: str | None = None,
    ) -> dict[str, Any]:
        feedback_id = str(uuid4())
        rating_clamped = max(1, min(5, rating))
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO user_feedback (id, user_id, feedback_type, rating, comment)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (feedback_id, user_id, feedback_type, rating_clamped, comment),
            )
            connection.commit()
            cursor.close()
            return {
                "id": feedback_id,
                "user_id": user_id,
                "feedback_type": feedback_type,
                "rating": rating_clamped,
                "comment": comment,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            connection.close()

    def submit_ai_message_feedback(
        self,
        *,
        message_id: str,
        user_id: str,
        rating: str,  # 'helpful' or 'not_helpful'
        reason: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        fb_id = str(uuid4())
        rating_clean = "helpful" if rating in ("helpful", "positive", "1", "true", "up") else "not_helpful"
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO ai_message_feedback (id, message_id, user_id, rating, reason, comment)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (fb_id, message_id, user_id, rating_clean, reason, comment),
            )
            connection.commit()
            cursor.close()
            return {
                "id": fb_id,
                "message_id": message_id,
                "user_id": user_id,
                "rating": rating_clean,
                "reason": reason,
                "comment": comment,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            connection.close()

    # -------------------------------------------------------------------------
    # DATA RETENTION CLEANUP
    # -------------------------------------------------------------------------

    def cleanup_expired_logs(self, usage_days: int = 90, error_days: int = 30) -> dict[str, int]:
        connection = connect(self.config)
        deleted = {"usage_events": 0, "error_logs": 0, "ai_usage_logs": 0, "user_sessions": 0}
        try:
            cursor = connection.cursor()

            # Clean usage events
            cursor.execute("DELETE FROM usage_events WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)", (usage_days,))
            deleted["usage_events"] = cursor.rowcount

            # Clean error logs
            cursor.execute("DELETE FROM error_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)", (error_days,))
            deleted["error_logs"] = cursor.rowcount

            # Clean old AI usage logs
            cursor.execute("DELETE FROM ai_usage_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)", (usage_days,))
            deleted["ai_usage_logs"] = cursor.rowcount

            # Clean old ended sessions
            cursor.execute("DELETE FROM user_sessions WHERE ended_at IS NOT NULL AND started_at < DATE_SUB(NOW(), INTERVAL %s DAY)", (usage_days,))
            deleted["user_sessions"] = cursor.rowcount

            connection.commit()
            cursor.close()
            return deleted
        finally:
            connection.close()

    # -------------------------------------------------------------------------
    # READ / ADMIN DASHBOARD STATS
    # -------------------------------------------------------------------------

    def get_overview_stats(self, days: int = 30) -> dict[str, Any]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)

            # Users
            cursor.execute("SELECT COUNT(*) AS total_users FROM users WHERE is_active = 1")
            total_users = cursor.fetchone()["total_users"]

            cursor.execute("SELECT COUNT(DISTINCT user_id) AS dau FROM user_sessions WHERE started_at >= DATE_SUB(NOW(), INTERVAL 1 DAY)")
            dau = cursor.fetchone()["dau"] or 0

            cursor.execute("SELECT COUNT(DISTINCT user_id) AS wau FROM user_sessions WHERE started_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)")
            wau = cursor.fetchone()["wau"] or 0

            cursor.execute("SELECT COUNT(DISTINCT user_id) AS mau FROM user_sessions WHERE started_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)")
            mau = cursor.fetchone()["mau"] or 0

            # Datasets
            cursor.execute("SELECT COUNT(*) AS total_datasets FROM datasets WHERE status = 'active'")
            total_datasets = cursor.fetchone()["total_datasets"]

            cursor.execute("SELECT COUNT(*) AS uploaded_datasets FROM usage_events WHERE event_type = 'dataset_uploaded' AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)", (days,))
            uploaded_datasets = cursor.fetchone()["uploaded_datasets"]

            # Analyses
            cursor.execute("SELECT COUNT(*) AS total_analyses FROM usage_events WHERE event_type IN ('analysis_completed', 'analysis_started') AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)", (days,))
            total_analyses = cursor.fetchone()["total_analyses"]

            cursor.execute("SELECT COUNT(*) AS failed_analyses FROM usage_events WHERE event_type = 'analysis_failed' AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)", (days,))
            failed_analyses = cursor.fetchone()["failed_analyses"]

            # AI
            cursor.execute("SELECT COUNT(*) AS total_ai, AVG(response_time_ms) AS avg_time, SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_ai FROM ai_usage_logs WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)", (days,))
            ai_row = cursor.fetchone()
            total_ai = ai_row["total_ai"] or 0
            avg_ai_time = round(ai_row["avg_time"] or 0.0, 2)
            success_ai = ai_row["success_ai"] or 0

            # Errors
            cursor.execute("SELECT COUNT(*) AS total_errors FROM error_logs WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)", (days,))
            total_errors = cursor.fetchone()["total_errors"]

            # Feedback
            cursor.execute("SELECT AVG(rating) AS avg_rating, COUNT(*) AS count_fb FROM user_feedback WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)", (days,))
            fb_row = cursor.fetchone()
            avg_rating = round(fb_row["avg_rating"] or 0.0, 1)

            cursor.execute("SELECT COUNT(*) AS total_rated, SUM(CASE WHEN rating = 'helpful' THEN 1 ELSE 0 END) AS helpful FROM ai_message_feedback WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)", (days,))
            ai_fb = cursor.fetchone()
            total_rated = ai_fb["total_rated"] or 0
            helpful_rated = ai_fb["helpful"] or 0
            ai_helpfulness_rate = round((helpful_rated / total_rated * 100), 1) if total_rated > 0 else 100.0

            cursor.close()
            return {
                "total_users": total_users,
                "dau": dau,
                "wau": wau,
                "mau": mau,
                "total_datasets": total_datasets,
                "uploaded_datasets_in_period": uploaded_datasets,
                "total_analyses": total_analyses,
                "failed_analyses": failed_analyses,
                "total_ai_requests": total_ai,
                "successful_ai_requests": success_ai,
                "avg_ai_response_time_ms": avg_ai_time,
                "total_errors": total_errors,
                "avg_user_rating": avg_rating,
                "ai_helpfulness_rate": ai_helpfulness_rate,
            }
        finally:
            connection.close()

    def get_time_series_stats(self, days: int = 30) -> list[dict[str, Any]]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT
                    DATE(created_at) AS date_str,
                    COUNT(DISTINCT user_id) AS active_users,
                    SUM(CASE WHEN event_type = 'analysis_completed' THEN 1 ELSE 0 END) AS analyses,
                    SUM(CASE WHEN event_type = 'dataset_uploaded' THEN 1 ELSE 0 END) AS dataset_uploads
                FROM usage_events
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at) ASC
                """,
                (days,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "date": str(r["date_str"]),
                    "active_users": r["active_users"] or 0,
                    "analyses": r["analyses"] or 0,
                    "dataset_uploads": r["dataset_uploads"] or 0,
                }
                for r in rows
            ]
        finally:
            connection.close()

    def get_recent_errors(self, limit: int = 50) -> list[dict[str, Any]]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, request_id, user_id, error_category, endpoint, http_status, error_message, created_at
                FROM error_logs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "id": r["id"],
                    "request_id": r["request_id"],
                    "user_id": r["user_id"],
                    "error_category": r["error_category"],
                    "endpoint": r["endpoint"],
                    "http_status": r["http_status"],
                    "error_message": r["error_message"],
                    "created_at": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else str(r["created_at"]),
                }
                for r in rows
            ]
        finally:
            connection.close()

    def get_recent_feedback(self, limit: int = 50) -> list[dict[str, Any]]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT f.id, f.user_id, u.email, f.feedback_type, f.rating, f.comment, f.created_at
                FROM user_feedback f
                LEFT JOIN users u ON f.user_id = u.id
                ORDER BY f.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "user_email": r["email"] or "anonymous",
                    "feedback_type": r["feedback_type"],
                    "rating": r["rating"],
                    "comment": r["comment"],
                    "created_at": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else str(r["created_at"]),
                }
                for r in rows
            ]
        finally:
            connection.close()

    def get_ai_feedback_summary(self, limit: int = 50) -> list[dict[str, Any]]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT f.id, f.message_id, f.user_id, u.email, f.rating, f.reason, f.comment, f.created_at
                FROM ai_message_feedback f
                LEFT JOIN users u ON f.user_id = u.id
                ORDER BY f.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "id": r["id"],
                    "message_id": r["message_id"],
                    "user_id": r["user_id"],
                    "user_email": r["email"] or "anonymous",
                    "rating": r["rating"],
                    "reason": r["reason"],
                    "comment": r["comment"],
                    "created_at": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else str(r["created_at"]),
                }
                for r in rows
            ]
        finally:
            connection.close()
