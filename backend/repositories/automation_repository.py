"""Persistence for saved analytics, schedules, execution history, snapshots, and alerts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from analytics.database import DatabaseConfig, connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str, allow_nan=False)


class AutomationRepository:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                statements = [
                    """CREATE TABLE IF NOT EXISTS saved_analytics_queries (
                        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                        dataset_id TEXT NOT NULL, title TEXT NOT NULL, question TEXT NOT NULL,
                        config_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
                    """CREATE TABLE IF NOT EXISTS analytics_automations (
                        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                        dataset_id TEXT NOT NULL, saved_query_id TEXT NOT NULL, name TEXT NOT NULL,
                        frequency TEXT NOT NULL, run_time TEXT NOT NULL, weekday INTEGER NOT NULL DEFAULT 0,
                        day_of_month INTEGER NOT NULL DEFAULT 1, timezone TEXT NOT NULL,
                        ai_summary INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
                        next_run_at TEXT NOT NULL, last_run_at TEXT NULL, last_status TEXT NULL,
                        failure_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
                    """CREATE TABLE IF NOT EXISTS automation_runs (
                        id TEXT PRIMARY KEY, automation_id TEXT NOT NULL, scheduled_for TEXT NOT NULL,
                        status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0, available_at TEXT NOT NULL,
                        started_at TEXT NULL, completed_at TEXT NULL, execution_time_ms INTEGER NULL,
                        error_code TEXT NULL, result_json TEXT NULL, created_at TEXT NOT NULL,
                        UNIQUE (automation_id, scheduled_for))""",
                    """CREATE TABLE IF NOT EXISTS dataset_snapshots (
                        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                        dataset_id TEXT NOT NULL, schema_hash TEXT NOT NULL, row_count INTEGER NOT NULL,
                        profile_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
                    """CREATE TABLE IF NOT EXISTS analytics_alerts (
                        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                        dataset_id TEXT NOT NULL, name TEXT NOT NULL, alert_type TEXT NOT NULL,
                        metric TEXT NOT NULL, operator TEXT NOT NULL, threshold REAL NOT NULL,
                        config_json TEXT NOT NULL DEFAULT '{}', active INTEGER NOT NULL DEFAULT 1,
                        cooldown_seconds INTEGER NOT NULL DEFAULT 3600, last_triggered_at TEXT NULL,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
                    """CREATE TABLE IF NOT EXISTS automation_alert_events (
                        id TEXT PRIMARY KEY, alert_id TEXT NOT NULL, snapshot_id TEXT NOT NULL,
                        triggered_at TEXT NOT NULL, result_json TEXT NOT NULL,
                        UNIQUE (alert_id, snapshot_id))""",
                    """CREATE TABLE IF NOT EXISTS automation_worker_locks (
                        automation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, acquired_at TEXT NOT NULL)""",
                ]
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_saved_queries_workspace ON saved_analytics_queries(workspace_id, dataset_id)",
                    "CREATE INDEX IF NOT EXISTS idx_automations_due ON analytics_automations(active, next_run_at)",
                    "CREATE INDEX IF NOT EXISTS idx_automations_workspace ON analytics_automations(workspace_id, active)",
                    "CREATE INDEX IF NOT EXISTS idx_runs_pending ON automation_runs(status, available_at)",
                    "CREATE INDEX IF NOT EXISTS idx_runs_automation ON automation_runs(automation_id, created_at)",
                    "CREATE INDEX IF NOT EXISTS idx_snapshots_dataset ON dataset_snapshots(workspace_id, dataset_id, created_at)",
                    "CREATE INDEX IF NOT EXISTS idx_alerts_dataset ON analytics_alerts(workspace_id, dataset_id, active)",
                ]
            else:
                statements = [
                    """CREATE TABLE IF NOT EXISTS saved_analytics_queries (
                        id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(64) NOT NULL, workspace_id VARCHAR(64) NOT NULL,
                        dataset_id VARCHAR(64) NOT NULL, title VARCHAR(255) NOT NULL, question VARCHAR(1000) NOT NULL,
                        config_json TEXT NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'active',
                        created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
                        KEY idx_saved_queries_workspace (workspace_id, dataset_id))""",
                    """CREATE TABLE IF NOT EXISTS analytics_automations (
                        id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(64) NOT NULL, workspace_id VARCHAR(64) NOT NULL,
                        dataset_id VARCHAR(64) NOT NULL, saved_query_id VARCHAR(64) NOT NULL, name VARCHAR(255) NOT NULL,
                        frequency VARCHAR(16) NOT NULL, run_time VARCHAR(5) NOT NULL, weekday TINYINT NOT NULL DEFAULT 0,
                        day_of_month TINYINT NOT NULL DEFAULT 1, timezone VARCHAR(64) NOT NULL,
                        ai_summary TINYINT(1) NOT NULL DEFAULT 0, active TINYINT(1) NOT NULL DEFAULT 1,
                        next_run_at VARCHAR(40) NOT NULL, last_run_at VARCHAR(40) NULL, last_status VARCHAR(20) NULL,
                        failure_count INT NOT NULL DEFAULT 0, created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
                        KEY idx_automations_due (active, next_run_at), KEY idx_automations_workspace (workspace_id, active))""",
                    """CREATE TABLE IF NOT EXISTS automation_runs (
                        id VARCHAR(64) PRIMARY KEY, automation_id VARCHAR(64) NOT NULL, scheduled_for VARCHAR(80) NOT NULL,
                        status VARCHAR(20) NOT NULL, attempt INT NOT NULL DEFAULT 0, available_at VARCHAR(40) NOT NULL,
                        started_at VARCHAR(40) NULL, completed_at VARCHAR(40) NULL, execution_time_ms INT NULL,
                        error_code VARCHAR(64) NULL, result_json LONGTEXT NULL, created_at VARCHAR(40) NOT NULL,
                        UNIQUE KEY uq_automation_scheduled_run (automation_id, scheduled_for),
                        KEY idx_runs_pending (status, available_at), KEY idx_runs_automation (automation_id, created_at))""",
                    """CREATE TABLE IF NOT EXISTS dataset_snapshots (
                        id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(64) NOT NULL, workspace_id VARCHAR(64) NOT NULL,
                        dataset_id VARCHAR(64) NOT NULL, schema_hash VARCHAR(64) NOT NULL, row_count BIGINT NOT NULL,
                        profile_json LONGTEXT NOT NULL, created_at VARCHAR(40) NOT NULL,
                        KEY idx_snapshots_dataset (workspace_id, dataset_id, created_at))""",
                    """CREATE TABLE IF NOT EXISTS analytics_alerts (
                        id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(64) NOT NULL, workspace_id VARCHAR(64) NOT NULL,
                        dataset_id VARCHAR(64) NOT NULL, name VARCHAR(255) NOT NULL, alert_type VARCHAR(20) NOT NULL,
                        metric VARCHAR(128) NOT NULL, operator VARCHAR(32) NOT NULL, threshold DOUBLE NOT NULL,
                        config_json TEXT NOT NULL, active TINYINT(1) NOT NULL DEFAULT 1,
                        cooldown_seconds INT NOT NULL DEFAULT 3600, last_triggered_at VARCHAR(40) NULL,
                        created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL,
                        KEY idx_alerts_dataset (workspace_id, dataset_id, active))""",
                    """CREATE TABLE IF NOT EXISTS automation_alert_events (
                        id VARCHAR(64) PRIMARY KEY, alert_id VARCHAR(64) NOT NULL, snapshot_id VARCHAR(64) NOT NULL,
                        triggered_at VARCHAR(40) NOT NULL, result_json TEXT NOT NULL,
                        UNIQUE KEY uq_alert_snapshot (alert_id, snapshot_id))""",
                    """CREATE TABLE IF NOT EXISTS automation_worker_locks (
                        automation_id VARCHAR(64) PRIMARY KEY, run_id VARCHAR(64) NOT NULL,
                        acquired_at VARCHAR(40) NOT NULL)""",
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

    def _execute(self, statement: str, params: tuple[Any, ...] = (), *, fetch: str | None = None) -> Any:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(statement, params)
            if fetch == "one":
                row = cursor.fetchone()
                result = self._row_dict(cursor, row) if row else None
            elif fetch == "all":
                result = [self._row_dict(cursor, row) for row in cursor.fetchall()]
            else:
                result = cursor.rowcount
            connection.commit()
            cursor.close()
            return result
        finally:
            connection.close()

    @staticmethod
    def _row_dict(cursor: Any, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return row
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        return dict(zip((item[0] for item in cursor.description), row))

    @staticmethod
    def _decode(record: dict[str, Any] | None, json_fields: tuple[str, ...]) -> dict[str, Any] | None:
        if record is None:
            return None
        decoded = dict(record)
        for key in json_fields:
            value = decoded.get(key)
            decoded[key.removesuffix("_json")] = json.loads(value) if value else {}
        return decoded

    def create_saved_query(self, *, user_id: str, workspace_id: str, dataset_id: str, title: str, question: str, config: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        query_id = str(uuid4())
        self._execute(
            "INSERT INTO saved_analytics_queries (id,user_id,workspace_id,dataset_id,title,question,config_json,status,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,'active',%s,%s)",
            (query_id, user_id, workspace_id, dataset_id, title, question, _json(config), now, now),
        )
        return self.get_saved_query(query_id, workspace_id)

    def get_saved_query(self, query_id: str, workspace_id: str) -> dict[str, Any] | None:
        record = self._execute("SELECT * FROM saved_analytics_queries WHERE id=%s AND workspace_id=%s", (query_id, workspace_id), fetch="one")
        return self._decode(record, ("config_json",))

    def list_saved_queries(self, workspace_id: str) -> list[dict[str, Any]]:
        records = self._execute("SELECT * FROM saved_analytics_queries WHERE workspace_id=%s AND status='active' ORDER BY updated_at DESC", (workspace_id,), fetch="all")
        return [self._decode(record, ("config_json",)) for record in records]

    def create_automation(self, *, user_id: str, workspace_id: str, dataset_id: str, saved_query_id: str, name: str, frequency: str, run_time: str, weekday: int, day_of_month: int, timezone_name: str, ai_summary: bool, next_run_at: str) -> dict[str, Any]:
        now = _now()
        automation_id = str(uuid4())
        self._execute(
            """INSERT INTO analytics_automations
            (id,user_id,workspace_id,dataset_id,saved_query_id,name,frequency,run_time,weekday,day_of_month,timezone,ai_summary,active,next_run_at,created_at,updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s)""",
            (automation_id, user_id, workspace_id, dataset_id, saved_query_id, name, frequency, run_time, weekday, day_of_month, timezone_name, int(ai_summary), next_run_at, now, now),
        )
        return self.get_automation(automation_id, workspace_id)

    def get_automation(self, automation_id: str, workspace_id: str) -> dict[str, Any] | None:
        return self._execute("SELECT * FROM analytics_automations WHERE id=%s AND workspace_id=%s", (automation_id, workspace_id), fetch="one")

    def get_automation_by_id(self, automation_id: str) -> dict[str, Any] | None:
        return self._execute("SELECT * FROM analytics_automations WHERE id=%s", (automation_id,), fetch="one")

    def list_automations(self, workspace_id: str) -> list[dict[str, Any]]:
        return self._execute("SELECT * FROM analytics_automations WHERE workspace_id=%s ORDER BY created_at DESC", (workspace_id,), fetch="all")

    def update_automation(self, automation_id: str, workspace_id: str, *, active: bool | None = None, next_run_at: str | None = None, last_run_at: str | None = None, last_status: str | None = None, failure_count: int | None = None, name: str | None = None, frequency: str | None = None, run_time: str | None = None, weekday: int | None = None, day_of_month: int | None = None, timezone_name: str | None = None, ai_summary: bool | None = None, saved_query_id: str | None = None, dataset_id: str | None = None) -> None:
        fields = {
            "active": active, "next_run_at": next_run_at, "last_run_at": last_run_at,
            "last_status": last_status, "failure_count": failure_count, "name": name,
            "frequency": frequency, "run_time": run_time, "weekday": weekday,
            "day_of_month": day_of_month, "timezone": timezone_name,
            "ai_summary": int(ai_summary) if ai_summary is not None else None,
            "saved_query_id": saved_query_id, "dataset_id": dataset_id, "updated_at": _now(),
        }
        values = [(key, value) for key, value in fields.items() if value is not None]
        assignments = ",".join(f"{key}=%s" for key, _ in values)
        self._execute(f"UPDATE analytics_automations SET {assignments} WHERE id=%s AND workspace_id=%s", tuple(value for _, value in values) + (automation_id, workspace_id))

    def delete_automation(self, automation_id: str, workspace_id: str) -> None:
        self._execute("DELETE FROM automation_runs WHERE automation_id=%s", (automation_id,))
        self._execute("DELETE FROM analytics_automations WHERE id=%s AND workspace_id=%s", (automation_id, workspace_id))

    def list_due_automations(self, now: str, limit: int = 50) -> list[dict[str, Any]]:
        return self._execute("SELECT * FROM analytics_automations WHERE active=1 AND next_run_at<=%s ORDER BY next_run_at LIMIT %s", (now, limit), fetch="all")

    def create_run(self, automation_id: str, scheduled_for: str, *, available_at: str | None = None) -> str | None:
        run_id = str(uuid4())
        now = _now()
        sql = "INSERT IGNORE INTO automation_runs (id,automation_id,scheduled_for,status,attempt,available_at,created_at) VALUES (%s,%s,%s,'pending',0,%s,%s)" if not self.config.uses_sqlite else "INSERT OR IGNORE INTO automation_runs (id,automation_id,scheduled_for,status,attempt,available_at,created_at) VALUES (%s,%s,%s,'pending',0,%s,%s)"
        inserted = self._execute(sql, (run_id, automation_id, scheduled_for, available_at or now, now))
        return run_id if inserted == 1 else None

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        record = self._execute("SELECT * FROM automation_runs WHERE id=%s", (run_id,), fetch="one")
        return self._decode(record, ("result_json",))

    def list_runs(self, automation_id: str, limit: int = 50) -> list[dict[str, Any]]:
        records = self._execute("SELECT * FROM automation_runs WHERE automation_id=%s ORDER BY created_at DESC LIMIT %s", (automation_id, limit), fetch="all")
        return [self._decode(record, ("result_json",)) for record in records]

    def list_pending_runs(self, now: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._execute("SELECT * FROM automation_runs WHERE status='pending' AND available_at<=%s ORDER BY created_at LIMIT %s", (now, limit), fetch="all")

    def claim_run(self, run_id: str) -> bool:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT automation_id FROM automation_runs WHERE id=%s AND status='pending'", (run_id,))
            row = cursor.fetchone()
            if not row:
                return False
            automation_id = row[0]
            insert_sql = "INSERT IGNORE INTO automation_worker_locks (automation_id,run_id,acquired_at) VALUES (%s,%s,%s)" if not self.config.uses_sqlite else "INSERT OR IGNORE INTO automation_worker_locks (automation_id,run_id,acquired_at) VALUES (%s,%s,%s)"
            cursor.execute(insert_sql, (automation_id, run_id, _now()))
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            cursor.execute("UPDATE automation_runs SET status='running',started_at=%s WHERE id=%s AND status='pending'", (_now(), run_id))
            if cursor.rowcount != 1:
                cursor.execute("DELETE FROM automation_worker_locks WHERE automation_id=%s AND run_id=%s", (automation_id, run_id))
                connection.commit()
                return False
            connection.commit()
            return True
        finally:
            connection.close()

    def retry_run(self, run_id: str, attempt: int, available_at: str, error_code: str) -> None:
        self._execute("UPDATE automation_runs SET status='pending',attempt=%s,available_at=%s,error_code=%s,started_at=NULL WHERE id=%s", (attempt, available_at, error_code, run_id))
        self._execute("DELETE FROM automation_worker_locks WHERE run_id=%s", (run_id,))

    def finish_run(self, run_id: str, automation_id: str, workspace_id: str, *, status: str, result: dict[str, Any] | None = None, error_code: str | None = None, execution_time_ms: int = 0, failure_count: int = 0) -> None:
        now = _now()
        self._execute("UPDATE automation_runs SET status=%s,completed_at=%s,execution_time_ms=%s,error_code=%s,result_json=%s WHERE id=%s", (status, now, execution_time_ms, error_code, _json(result) if result is not None else None, run_id))
        self._execute("DELETE FROM automation_worker_locks WHERE run_id=%s", (run_id,))
        self.update_automation(automation_id, workspace_id, last_run_at=now, last_status=status, failure_count=failure_count)

    def recover_stale_runs(self, cutoff: str) -> int:
        stale = self._execute("SELECT id FROM automation_runs WHERE status='running' AND started_at<=%s", (cutoff,), fetch="all")
        for record in stale:
            self._execute("UPDATE automation_runs SET status='pending',available_at=%s,error_code='worker_recovered',started_at=NULL WHERE id=%s AND status='running'", (_now(), record["id"]))
            self._execute("DELETE FROM automation_worker_locks WHERE run_id=%s", (record["id"],))
        return len(stale)

    def create_snapshot(self, *, user_id: str, workspace_id: str, dataset_id: str, schema_hash: str, row_count: int, profile: dict[str, Any]) -> dict[str, Any]:
        snapshot_id = str(uuid4())
        created_at = _now()
        self._execute("INSERT INTO dataset_snapshots (id,user_id,workspace_id,dataset_id,schema_hash,row_count,profile_json,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (snapshot_id, user_id, workspace_id, dataset_id, schema_hash, row_count, _json(profile), created_at))
        return {"id": snapshot_id, "user_id": user_id, "workspace_id": workspace_id, "dataset_id": dataset_id, "schema_hash": schema_hash, "row_count": row_count, "profile": profile, "created_at": created_at}

    def latest_snapshot(self, workspace_id: str, dataset_id: str) -> dict[str, Any] | None:
        record = self._execute("SELECT * FROM dataset_snapshots WHERE workspace_id=%s AND dataset_id=%s ORDER BY created_at DESC LIMIT 1", (workspace_id, dataset_id), fetch="one")
        return self._decode(record, ("profile_json",))

    def list_snapshots(self, workspace_id: str, dataset_id: str, limit: int = 50) -> list[dict[str, Any]]:
        records = self._execute("SELECT * FROM dataset_snapshots WHERE workspace_id=%s AND dataset_id=%s ORDER BY created_at DESC LIMIT %s", (workspace_id, dataset_id, limit), fetch="all")
        return [self._decode(record, ("profile_json",)) for record in records]

    def create_alert(self, *, user_id: str, workspace_id: str, dataset_id: str, name: str, alert_type: str, metric: str, operator: str, threshold: float, config: dict[str, Any], cooldown_seconds: int) -> dict[str, Any]:
        alert_id = str(uuid4())
        now = _now()
        self._execute("INSERT INTO analytics_alerts (id,user_id,workspace_id,dataset_id,name,alert_type,metric,operator,threshold,config_json,active,cooldown_seconds,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s)", (alert_id, user_id, workspace_id, dataset_id, name, alert_type, metric, operator, threshold, _json(config), cooldown_seconds, now, now))
        return self.get_alert(alert_id, workspace_id)

    def get_alert(self, alert_id: str, workspace_id: str) -> dict[str, Any] | None:
        return self._decode(self._execute("SELECT * FROM analytics_alerts WHERE id=%s AND workspace_id=%s", (alert_id, workspace_id), fetch="one"), ("config_json",))

    def list_alerts(self, workspace_id: str, dataset_id: str | None = None) -> list[dict[str, Any]]:
        if dataset_id:
            records = self._execute("SELECT * FROM analytics_alerts WHERE workspace_id=%s AND dataset_id=%s ORDER BY created_at DESC", (workspace_id, dataset_id), fetch="all")
        else:
            records = self._execute("SELECT * FROM analytics_alerts WHERE workspace_id=%s ORDER BY created_at DESC", (workspace_id,), fetch="all")
        return [self._decode(record, ("config_json",)) for record in records]

    def update_alert_active(self, alert_id: str, workspace_id: str, active: bool) -> None:
        self._execute("UPDATE analytics_alerts SET active=%s,updated_at=%s WHERE id=%s AND workspace_id=%s", (int(active), _now(), alert_id, workspace_id))

    def delete_alert(self, alert_id: str, workspace_id: str) -> None:
        self._execute("DELETE FROM analytics_alerts WHERE id=%s AND workspace_id=%s", (alert_id, workspace_id))

    def list_active_alerts(self, workspace_id: str, dataset_id: str) -> list[dict[str, Any]]:
        records = self._execute("SELECT * FROM analytics_alerts WHERE workspace_id=%s AND dataset_id=%s AND active=1", (workspace_id, dataset_id), fetch="all")
        return [self._decode(record, ("config_json",)) for record in records]

    def create_alert_event(self, alert_id: str, snapshot_id: str, result: dict[str, Any]) -> bool:
        event_id = str(uuid4())
        sql = "INSERT IGNORE INTO automation_alert_events (id,alert_id,snapshot_id,triggered_at,result_json) VALUES (%s,%s,%s,%s,%s)" if not self.config.uses_sqlite else "INSERT OR IGNORE INTO automation_alert_events (id,alert_id,snapshot_id,triggered_at,result_json) VALUES (%s,%s,%s,%s,%s)"
        return self._execute(sql, (event_id, alert_id, snapshot_id, _now(), _json(result))) == 1

    def set_alert_triggered(self, alert_id: str, workspace_id: str, triggered_at: str) -> None:
        self._execute("UPDATE analytics_alerts SET last_triggered_at=%s,updated_at=%s WHERE id=%s AND workspace_id=%s", (triggered_at, triggered_at, alert_id, workspace_id))

    def admin_overview(self, workspace_id: str | None = None) -> dict[str, int | float]:
        where = " WHERE workspace_id=%s" if workspace_id else ""
        params = (workspace_id,) if workspace_id else ()
        automation_count = self._execute(f"SELECT COUNT(*) AS count FROM analytics_automations{where}", params, fetch="one")
        active_count = self._execute(f"SELECT COUNT(*) AS count FROM analytics_automations{where}{' AND' if where else ' WHERE'} active=1", params, fetch="one")
        run_filter = " WHERE automation_id IN (SELECT id FROM analytics_automations WHERE workspace_id=%s)" if workspace_id else ""
        run_params = (workspace_id,) if workspace_id else ()
        completed = self._execute(f"SELECT COUNT(*) AS count FROM automation_runs{run_filter}{' AND' if run_filter else ' WHERE'} status='completed'", run_params, fetch="one")
        failed = self._execute(f"SELECT COUNT(*) AS count FROM automation_runs{run_filter}{' AND' if run_filter else ' WHERE'} status='failed'", run_params, fetch="one")
        latency = self._execute(f"SELECT AVG(execution_time_ms) AS average FROM automation_runs{run_filter}{' AND' if run_filter else ' WHERE'} status='completed'", run_params, fetch="one")
        return {
            "total_automations": int(automation_count["count"]),
            "active_automations": int(active_count["count"]),
            "successful_runs": int(completed["count"]),
            "failed_runs": int(failed["count"]),
            "average_execution_time_ms": float(latency["average"] or 0),
        }

    def admin_runs(self, *, workspace_id: str | None = None, status: str | None = None, since: str | None = None, until: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []
        if workspace_id:
            filters.append("a.workspace_id=%s")
            params.append(workspace_id)
        if status:
            filters.append("r.status=%s")
            params.append(status)
        if since:
            filters.append("r.created_at >= %s")
            params.append(since)
        if until:
            filters.append("r.created_at <= %s")
            params.append(until)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        params.append(max(1, min(limit, 500)))
        return self._execute(
            """SELECT r.id,r.automation_id,a.workspace_id,a.dataset_id,a.name AS automation_name,
            r.status,r.attempt,r.error_code,r.execution_time_ms,r.started_at,r.completed_at,r.created_at
            FROM automation_runs r JOIN analytics_automations a ON a.id=r.automation_id""" + where + " ORDER BY r.created_at DESC LIMIT %s",
            tuple(params), fetch="all",
        )