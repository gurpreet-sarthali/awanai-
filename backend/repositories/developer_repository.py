"""Persistence for developer API keys, outbound webhooks, and API telemetry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from analytics.database import DatabaseConfig, connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeveloperRepository:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                statements = [
                    """CREATE TABLE IF NOT EXISTS developer_api_keys (
                        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                        name TEXT NOT NULL, key_prefix TEXT NOT NULL, key_hash TEXT NOT NULL UNIQUE,
                        scopes_json TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NULL,
                        last_used_at TEXT NULL, revoked_at TEXT NULL, rotated_from_id TEXT NULL)""",
                    """CREATE TABLE IF NOT EXISTS developer_webhooks (
                        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                        url TEXT NOT NULL, description TEXT NULL, secret_ciphertext TEXT NOT NULL,
                        events_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                        last_delivery_at TEXT NULL, failure_count INTEGER NOT NULL DEFAULT 0)""",
                    """CREATE TABLE IF NOT EXISTS developer_webhook_deliveries (
                        id TEXT PRIMARY KEY, webhook_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                        event_id TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
                        status TEXT NOT NULL, response_code INTEGER NULL, duration_ms INTEGER NULL,
                        attempt_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                        completed_at TEXT NULL, last_error_code TEXT NULL,
                        UNIQUE (webhook_id, event_id))""",
                    """CREATE TABLE IF NOT EXISTS developer_api_usage_events (
                        id TEXT PRIMARY KEY, api_key_id TEXT NULL, user_id TEXT NULL,
                        workspace_id TEXT NULL, endpoint TEXT NOT NULL, method TEXT NOT NULL,
                        http_status INTEGER NOT NULL, response_time_ms INTEGER NOT NULL,
                        request_id TEXT NOT NULL, created_at TEXT NOT NULL)""",
                    """CREATE TABLE IF NOT EXISTS developer_api_rate_buckets (
                        bucket_key TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, api_key_id TEXT NOT NULL,
                        endpoint_class TEXT NOT NULL, window_start TEXT NOT NULL,
                        request_count INTEGER NOT NULL DEFAULT 0)""",
                ]
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_dev_keys_workspace ON developer_api_keys(workspace_id, revoked_at)",
                    "CREATE INDEX IF NOT EXISTS idx_dev_keys_prefix ON developer_api_keys(key_prefix)",
                    "CREATE INDEX IF NOT EXISTS idx_dev_webhooks_workspace ON developer_webhooks(workspace_id, active)",
                    "CREATE INDEX IF NOT EXISTS idx_dev_deliveries_webhook ON developer_webhook_deliveries(webhook_id, created_at)",
                    "CREATE INDEX IF NOT EXISTS idx_dev_usage_workspace ON developer_api_usage_events(workspace_id, created_at)",
                    "CREATE INDEX IF NOT EXISTS idx_dev_usage_key ON developer_api_usage_events(api_key_id, created_at)",
                ]
            else:
                statements = [
                    """CREATE TABLE IF NOT EXISTS developer_api_keys (
                        id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(64) NOT NULL, workspace_id VARCHAR(64) NOT NULL,
                        name VARCHAR(128) NOT NULL, key_prefix VARCHAR(32) NOT NULL, key_hash CHAR(64) NOT NULL UNIQUE,
                        scopes_json TEXT NOT NULL, created_at VARCHAR(40) NOT NULL, expires_at VARCHAR(40) NULL,
                        last_used_at VARCHAR(40) NULL, revoked_at VARCHAR(40) NULL, rotated_from_id VARCHAR(64) NULL,
                        KEY idx_dev_keys_workspace (workspace_id, revoked_at), KEY idx_dev_keys_prefix (key_prefix))""",
                    """CREATE TABLE IF NOT EXISTS developer_webhooks (
                        id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(64) NOT NULL, workspace_id VARCHAR(64) NOT NULL,
                        url VARCHAR(2048) NOT NULL, description VARCHAR(255) NULL, secret_ciphertext TEXT NOT NULL,
                        events_json TEXT NOT NULL, active TINYINT(1) NOT NULL DEFAULT 1,
                        created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
                        last_delivery_at VARCHAR(40) NULL, failure_count INT NOT NULL DEFAULT 0,
                        KEY idx_dev_webhooks_workspace (workspace_id, active))""",
                    """CREATE TABLE IF NOT EXISTS developer_webhook_deliveries (
                        id VARCHAR(64) PRIMARY KEY, webhook_id VARCHAR(64) NOT NULL, workspace_id VARCHAR(64) NOT NULL,
                        event_id VARCHAR(64) NOT NULL, event_type VARCHAR(64) NOT NULL, payload_json LONGTEXT NOT NULL,
                        status VARCHAR(20) NOT NULL, response_code INT NULL, duration_ms INT NULL,
                        attempt_count INT NOT NULL DEFAULT 0, created_at VARCHAR(40) NOT NULL,
                        completed_at VARCHAR(40) NULL, last_error_code VARCHAR(64) NULL,
                        UNIQUE KEY uq_dev_delivery (webhook_id, event_id), KEY idx_dev_deliveries_webhook (webhook_id, created_at))""",
                    """CREATE TABLE IF NOT EXISTS developer_api_usage_events (
                        id VARCHAR(64) PRIMARY KEY, api_key_id VARCHAR(64) NULL, user_id VARCHAR(64) NULL,
                        workspace_id VARCHAR(64) NULL, endpoint VARCHAR(255) NOT NULL, method VARCHAR(10) NOT NULL,
                        http_status INT NOT NULL, response_time_ms INT NOT NULL, request_id VARCHAR(64) NOT NULL,
                        created_at VARCHAR(40) NOT NULL,
                        KEY idx_dev_usage_workspace (workspace_id, created_at), KEY idx_dev_usage_key (api_key_id, created_at))""",
                    """CREATE TABLE IF NOT EXISTS developer_api_rate_buckets (
                        bucket_key VARCHAR(255) PRIMARY KEY, workspace_id VARCHAR(64) NOT NULL,
                        api_key_id VARCHAR(64) NOT NULL, endpoint_class VARCHAR(32) NOT NULL,
                        window_start VARCHAR(40) NOT NULL, request_count INT NOT NULL DEFAULT 0)""",
                ]
                indexes = []
            for statement in statements:
                cursor.execute(statement)
            for statement in indexes:
                cursor.execute(statement)
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    @staticmethod
    def _row_dict(cursor: Any, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return row
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        return dict(zip((item[0] for item in cursor.description), row))

    def _execute(self, sql: str, params: tuple[Any, ...] = (), fetch: str | None = None) -> Any:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(sql, params)
            if fetch == "one":
                row = cursor.fetchone()
                value = self._row_dict(cursor, row) if row else None
            elif fetch == "all":
                value = [self._row_dict(cursor, row) for row in cursor.fetchall()]
            else:
                value = cursor.rowcount
            connection.commit()
            cursor.close()
            return value
        finally:
            connection.close()

    @staticmethod
    def _decode_json(record: dict[str, Any] | None, field: str, output_name: str) -> dict[str, Any] | None:
        if record is None:
            return None
        decoded = dict(record)
        decoded[output_name] = json.loads(decoded.pop(field) or "[]")
        return decoded

    def create_api_key(self, *, user_id: str, workspace_id: str, name: str, key_prefix: str, key_hash: str, scopes: list[str], expires_at: str | None, rotated_from_id: str | None = None) -> dict[str, Any]:
        key_id = str(uuid4())
        now = _now()
        self._execute(
            "INSERT INTO developer_api_keys (id,user_id,workspace_id,name,key_prefix,key_hash,scopes_json,created_at,expires_at,rotated_from_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (key_id, user_id, workspace_id, name, key_prefix, key_hash, json.dumps(scopes), now, expires_at, rotated_from_id),
        )
        return self.get_api_key(key_id, workspace_id)

    def find_api_keys_by_prefix(self, key_prefix: str) -> list[dict[str, Any]]:
        records = self._execute("SELECT * FROM developer_api_keys WHERE key_prefix=%s AND revoked_at IS NULL", (key_prefix,), "all")
        return [self._decode_json(record, "scopes_json", "scopes") for record in records]

    def get_api_key(self, key_id: str, workspace_id: str) -> dict[str, Any] | None:
        return self._decode_json(self._execute("SELECT * FROM developer_api_keys WHERE id=%s AND workspace_id=%s", (key_id, workspace_id), "one"), "scopes_json", "scopes")

    def list_api_keys(self, workspace_id: str) -> list[dict[str, Any]]:
        records = self._execute("SELECT id,user_id,workspace_id,name,key_prefix,scopes_json,created_at,expires_at,last_used_at,revoked_at,rotated_from_id FROM developer_api_keys WHERE workspace_id=%s ORDER BY created_at DESC", (workspace_id,), "all")
        return [self._decode_json(record, "scopes_json", "scopes") for record in records]

    def set_key_last_used(self, key_id: str, timestamp: str) -> None:
        self._execute("UPDATE developer_api_keys SET last_used_at=%s WHERE id=%s AND revoked_at IS NULL", (timestamp, key_id))

    def revoke_api_key(self, key_id: str, workspace_id: str, timestamp: str | None = None) -> None:
        self._execute("UPDATE developer_api_keys SET revoked_at=%s WHERE id=%s AND workspace_id=%s AND revoked_at IS NULL", (timestamp or _now(), key_id, workspace_id))

    def set_key_expiry(self, key_id: str, workspace_id: str, expires_at: str) -> None:
        self._execute("UPDATE developer_api_keys SET expires_at=%s WHERE id=%s AND workspace_id=%s AND revoked_at IS NULL", (expires_at, key_id, workspace_id))

    def create_webhook(self, *, user_id: str, workspace_id: str, url: str, description: str | None, secret_ciphertext: str, events: list[str]) -> dict[str, Any]:
        webhook_id = str(uuid4())
        now = _now()
        self._execute("INSERT INTO developer_webhooks (id,user_id,workspace_id,url,description,secret_ciphertext,events_json,active,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s,%s)", (webhook_id, user_id, workspace_id, url, description, secret_ciphertext, json.dumps(events), now, now))
        return self.get_webhook(webhook_id, workspace_id)

    def get_webhook(self, webhook_id: str, workspace_id: str) -> dict[str, Any] | None:
        return self._decode_json(self._execute("SELECT * FROM developer_webhooks WHERE id=%s AND workspace_id=%s", (webhook_id, workspace_id), "one"), "events_json", "events")

    def list_webhooks(self, workspace_id: str) -> list[dict[str, Any]]:
        records = self._execute("SELECT id,user_id,workspace_id,url,description,events_json,active,created_at,updated_at,last_delivery_at,failure_count FROM developer_webhooks WHERE workspace_id=%s ORDER BY created_at DESC", (workspace_id,), "all")
        return [self._decode_json(record, "events_json", "events") for record in records]

    def list_active_webhooks(self, workspace_id: str, event_type: str) -> list[dict[str, Any]]:
        records = self._execute("SELECT * FROM developer_webhooks WHERE workspace_id=%s AND active=1", (workspace_id,), "all")
        return [decoded for record in records if event_type in (decoded := self._decode_json(record, "events_json", "events"))["events"]]

    def update_webhook(self, webhook_id: str, workspace_id: str, *, url: str | None = None, description: str | None = None, events: list[str] | None = None, active: bool | None = None, secret_ciphertext: str | None = None) -> None:
        fields = {"url": url, "description": description, "events_json": json.dumps(events) if events is not None else None, "active": int(active) if active is not None else None, "secret_ciphertext": secret_ciphertext, "updated_at": _now()}
        values = [(key, value) for key, value in fields.items() if value is not None]
        assignments = ",".join(f"{key}=%s" for key, _ in values)
        self._execute(f"UPDATE developer_webhooks SET {assignments} WHERE id=%s AND workspace_id=%s", tuple(value for _, value in values) + (webhook_id, workspace_id))

    def delete_webhook(self, webhook_id: str, workspace_id: str) -> None:
        self._execute("DELETE FROM developer_webhook_deliveries WHERE webhook_id=%s", (webhook_id,))
        self._execute("DELETE FROM developer_webhooks WHERE id=%s AND workspace_id=%s", (webhook_id, workspace_id))

    def create_delivery(self, *, webhook_id: str, workspace_id: str, event_id: str, event_type: str, payload: dict[str, Any]) -> str | None:
        delivery_id = str(uuid4())
        now = _now()
        sql = "INSERT IGNORE INTO developer_webhook_deliveries (id,webhook_id,workspace_id,event_id,event_type,payload_json,status,created_at) VALUES (%s,%s,%s,%s,%s,%s,'pending',%s)" if not self.config.uses_sqlite else "INSERT OR IGNORE INTO developer_webhook_deliveries (id,webhook_id,workspace_id,event_id,event_type,payload_json,status,created_at) VALUES (%s,%s,%s,%s,%s,%s,'pending',%s)"
        inserted = self._execute(sql, (delivery_id, webhook_id, workspace_id, event_id, event_type, json.dumps(payload, separators=(",", ":"), default=str), now))
        if inserted == 1:
            return delivery_id
        return None

    def get_delivery(self, delivery_id: str) -> dict[str, Any] | None:
        record = self._execute("SELECT * FROM developer_webhook_deliveries WHERE id=%s", (delivery_id,), "one")
        if record:
            record["payload"] = json.loads(record.pop("payload_json"))
        return record

    def list_deliveries(self, webhook_id: str, workspace_id: str, limit: int = 50) -> list[dict[str, Any]]:
        records = self._execute("SELECT id,webhook_id,workspace_id,event_id,event_type,status,response_code,duration_ms,attempt_count,created_at,completed_at,last_error_code FROM developer_webhook_deliveries WHERE webhook_id=%s AND workspace_id=%s ORDER BY created_at DESC LIMIT %s", (webhook_id, workspace_id, limit), "all")
        return records

    def finish_delivery(self, delivery_id: str, *, status: str, response_code: int | None, duration_ms: int, attempt_count: int, last_error_code: str | None) -> None:
        now = _now()
        self._execute("UPDATE developer_webhook_deliveries SET status=%s,response_code=%s,duration_ms=%s,attempt_count=%s,completed_at=%s,last_error_code=%s WHERE id=%s", (status, response_code, duration_ms, attempt_count, now, last_error_code, delivery_id))
        self._execute("UPDATE developer_webhooks SET last_delivery_at=%s,failure_count=CASE WHEN %s='succeeded' THEN 0 ELSE failure_count+1 END WHERE id=(SELECT webhook_id FROM developer_webhook_deliveries WHERE id=%s)", (now, status, delivery_id))

    def increment_rate_bucket(self, *, bucket_key: str, workspace_id: str, api_key_id: str, endpoint_class: str, window_start: str) -> int:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                cursor.execute(
                    "INSERT INTO developer_api_rate_buckets (bucket_key,workspace_id,api_key_id,endpoint_class,window_start,request_count) VALUES (%s,%s,%s,%s,%s,1) ON CONFLICT(bucket_key) DO UPDATE SET request_count=request_count+1",
                    (bucket_key, workspace_id, api_key_id, endpoint_class, window_start),
                )
            else:
                cursor.execute(
                    "INSERT INTO developer_api_rate_buckets (bucket_key,workspace_id,api_key_id,endpoint_class,window_start,request_count) VALUES (%s,%s,%s,%s,%s,1) ON DUPLICATE KEY UPDATE request_count=request_count+1",
                    (bucket_key, workspace_id, api_key_id, endpoint_class, window_start),
                )
            cursor.execute("SELECT request_count FROM developer_api_rate_buckets WHERE bucket_key=%s", (bucket_key,))
            count = int(cursor.fetchone()[0])
            connection.commit()
            cursor.close()
            return count
        finally:
            connection.close()

    def record_api_usage(self, *, api_key_id: str | None, user_id: str | None, workspace_id: str | None, endpoint: str, method: str, http_status: int, response_time_ms: int, request_id: str) -> None:
        self._execute("INSERT INTO developer_api_usage_events (id,api_key_id,user_id,workspace_id,endpoint,method,http_status,response_time_ms,request_id,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (str(uuid4()), api_key_id, user_id, workspace_id, endpoint[:255], method[:10], http_status, response_time_ms, request_id, _now()))

    def usage_summary(self, workspace_id: str, since: str) -> dict[str, Any]:
        return self._execute("SELECT COUNT(*) AS request_count,COALESCE(SUM(CASE WHEN http_status>=400 THEN 1 ELSE 0 END),0) AS error_count,COALESCE(AVG(response_time_ms),0) AS average_response_time_ms FROM developer_api_usage_events WHERE workspace_id=%s AND created_at>=%s", (workspace_id, since), "one")