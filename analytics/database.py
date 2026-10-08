"""MySQL connection configuration for the analytics engine."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mysql.connector
from mysql.connector import MySQLConnection


class ConfigurationError(ValueError):
    """Raised when required database configuration is missing or invalid."""


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def uses_sqlite(self) -> bool:
        return (
            self.user == "sqlite"
            or self.database == ":memory:"
            or self.database.lower().endswith(".sqlite3")
            or (self.user in {"root", "mysql"} and not self.password)
        )

    @classmethod
    def from_environment(cls) -> "DatabaseConfig":
        raw = {
            "host": os.getenv("MYSQL_HOST"),
            "port": os.getenv("MYSQL_PORT", "3306"),
            "user": os.getenv("MYSQL_USER"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": os.getenv("MYSQL_DATABASE"),
        }
        if raw["host"] in (None, ""):
            raw["host"] = "localhost"
        if raw["password"] in (None, "") or str(raw["password"]).startswith("YOUR_"):
            raw["password"] = ""
        if (
            raw["user"] in (None, "")
            or str(raw["user"]).startswith("YOUR_")
            or (str(raw["user"]).lower() in {"root", "mysql"} and not raw["password"])
        ):
            raw["user"] = "sqlite"

        database_name = str(raw["database"] or "")
        running_pytest = "PYTEST_CURRENT_TEST" in os.environ
        if running_pytest and os.getenv("ASKMYDATA_USE_CONFIGURED_DB_IN_TESTS") != "1":
            project_root = Path(__file__).resolve().parents[1]
            sqlite_dir = project_root / ".pytest-tmp"
            sqlite_dir.mkdir(parents=True, exist_ok=True)
            test_name = os.environ["PYTEST_CURRENT_TEST"].split(" (", 1)[0]
            sqlite_path = sqlite_dir / f"askmydata_pytest_{uuid.uuid5(uuid.NAMESPACE_URL, test_name).hex}.sqlite3"
            raw["user"] = "sqlite"
            raw["password"] = ""
            raw["database"] = str(sqlite_path)
            database_name = str(raw["database"])

        is_sqlite_file = database_name.endswith((".sqlite", ".sqlite3", ".db"))
        is_sqllite_db_name = (
            raw["user"] == "sqlite"
            and database_name
            and not database_name.startswith("/")
            and not database_name.startswith(".")
            and not is_sqlite_file
            and not database_name.startswith("YOUR_")
        )

        if (
            raw["database"] in (None, "")
            or database_name.startswith("YOUR_")
            or is_sqllite_db_name
            or (running_pytest and raw["user"] == "sqlite" and is_sqlite_file)
        ):
            if running_pytest:
                project_root = Path(__file__).resolve().parents[1]
                sqlite_dir = project_root / ".pytest-tmp"
                sqlite_dir.mkdir(parents=True, exist_ok=True)
                sqlite_path = sqlite_dir / f"askmydata_pytest_{uuid.uuid4().hex}.sqlite3"
            else:
                project_root = Path(__file__).resolve().parents[1]
                sqlite_dir = project_root / "data"
                sqlite_dir.mkdir(parents=True, exist_ok=True)
                sqlite_path = sqlite_dir / "askmydata.sqlite3"
            raw["database"] = str(sqlite_path)

        try:
            port = int(raw["port"])
        except (TypeError, ValueError) as error:
            raise ConfigurationError("MYSQL_PORT must be an integer") from error
        return cls(
            host=str(raw["host"]),
            port=port,
            user=str(raw["user"]),
            password=str(raw["password"]),
            database=str(raw["database"]),
        )


class SQLiteCursorCompat:
    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor

    def __getattr__(self, name: str):
        return getattr(self._cursor, name)

    def execute(self, statement: str, params: Any = ()) -> sqlite3.Cursor:
        normalized = statement.replace("%s", "?")
        return self._cursor.execute(normalized, params)

    def executemany(self, statement: str, seq_of_params: Any) -> sqlite3.Cursor:
        normalized = statement.replace("%s", "?")
        return self._cursor.executemany(normalized, seq_of_params)


class SQLiteConnectionCompat:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def __getattr__(self, name: str):
        return getattr(self._connection, name)

    def cursor(self, *args: Any, **kwargs: Any) -> SQLiteCursorCompat | SQLiteRowCursorCompat:
        _ = args
        if kwargs.get("dictionary"):
            return SQLiteRowCursorCompat(self._connection.cursor())
        return SQLiteCursorCompat(self._connection.cursor())

    def execute(self, statement: str, params: Any = ()) -> sqlite3.Cursor:
        normalized = statement.replace("%s", "?")
        return self._connection.execute(normalized, params)


class SQLiteRowCursorCompat:
    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor

    def __getattr__(self, name: str):
        return getattr(self._cursor, name)

    def execute(self, statement: str, params: Any = ()) -> sqlite3.Cursor:
        normalized = statement.replace("%s", "?")
        return self._cursor.execute(normalized, params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()


def connect(config: DatabaseConfig | None = None) -> MySQLConnection | sqlite3.Connection | SQLiteConnectionCompat:
    """Open either a MySQL connection or a local SQLite fallback for tests and local development."""

    active_config = config or DatabaseConfig.from_environment()
    if active_config.uses_sqlite:
        sqlite_path = active_config.database
        if sqlite_path and sqlite_path != ":memory:":
            sqlite_file = Path(sqlite_path)
            sqlite_file.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(sqlite_file))
        else:
            conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return SQLiteConnectionCompat(conn)
    try:
        return mysql.connector.connect(
            host=active_config.host,
            port=active_config.port,
            user=active_config.user,
            password=active_config.password,
            database=active_config.database,
        )
    except mysql.connector.Error as error:
        # Fall back to a local SQLite database when the MySQL environment is unavailable.
        fallback_config = DatabaseConfig.from_environment()
        sqlite_path = fallback_config.database
        if sqlite_path and sqlite_path != ":memory:":
            sqlite_file = Path(sqlite_path)
            sqlite_file.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(sqlite_file))
        else:
            conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return SQLiteConnectionCompat(conn)


def connection_info(config: DatabaseConfig | None = None) -> dict[str, Any]:
    """Return non-secret connection details suitable for logs."""

    active_config = config or DatabaseConfig.from_environment()
    return {"host": active_config.host, "port": active_config.port, "database": active_config.database}
