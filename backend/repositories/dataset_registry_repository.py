"""MySQL-backed dataset registry metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from analytics.database import DatabaseConfig, connect
from backend.core.dataset_constants import (
    DEMO_PLACEMENT_DATASET_ID,
    DEMO_PLACEMENT_NAME,
    DEMO_PLACEMENT_TABLE,
    is_safe_internal_table_name,
    is_valid_dataset_id,
)


class DatasetNotFoundError(LookupError):
    pass


class DatasetRegistryError(RuntimeError):
    pass


@dataclass(frozen=True, kw_only=True)
class DatasetRecord:
    dataset_id: str
    user_id: str | None
    dataset_name: str
    original_filename: str
    internal_table_name: str
    storage_reference: str | None
    google_drive_folder_id: str | None = None
    file_size: int | None = None
    row_count: int
    column_count: int
    status: str
    is_builtin: bool
    validation_status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DatasetColumnRecord:
    column_name: str
    original_column_name: str
    data_type: str
    nullable: bool
    description: str | None
    position: int


class DatasetRegistryRepository:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if self.config.uses_sqlite:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS datasets (
                        dataset_id TEXT NOT NULL PRIMARY KEY,
                        user_id TEXT NULL,
                        dataset_name TEXT NOT NULL,
                        original_filename TEXT NOT NULL,
                        internal_table_name TEXT NOT NULL UNIQUE,
                        storage_reference TEXT NULL,
                        google_drive_folder_id TEXT NULL,
                        file_size INTEGER NULL,
                        row_count INTEGER NOT NULL DEFAULT 0,
                        column_count INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL,
                        is_builtin INTEGER NOT NULL DEFAULT 0,
                        validation_status TEXT NOT NULL DEFAULT 'unknown',
                        error_message TEXT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dataset_columns (
                        dataset_id TEXT NOT NULL,
                        column_name TEXT NOT NULL,
                        original_column_name TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        nullable INTEGER NOT NULL DEFAULT 1,
                        description TEXT NULL,
                        position INTEGER NOT NULL,
                        PRIMARY KEY (dataset_id, column_name)
                    )
                    """
                )
                existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(datasets)").fetchall()}
                for column_name, column_type in (
                    ("user_id", "TEXT NULL"),
                    ("google_drive_folder_id", "TEXT NULL"),
                    ("file_size", "INTEGER NULL"),
                ):
                    if column_name not in existing_columns:
                        cursor.execute(f"ALTER TABLE datasets ADD COLUMN {column_name} {column_type}")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_datasets_user_id ON datasets(user_id)")
                connection.commit()
                cursor.close()
                self._seed_demo_dataset()
                return
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id VARCHAR(64) NOT NULL PRIMARY KEY,
                    dataset_name VARCHAR(255) NOT NULL,
                    original_filename VARCHAR(255) NOT NULL,
                    internal_table_name VARCHAR(64) NOT NULL,
                    storage_reference VARCHAR(255) NULL,
                    row_count INT NOT NULL DEFAULT 0,
                    column_count INT NOT NULL DEFAULT 0,
                    status VARCHAR(32) NOT NULL,
                    is_builtin TINYINT(1) NOT NULL DEFAULT 0,
                    validation_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
                    error_message TEXT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_datasets_internal_table (internal_table_name)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_columns (
                    dataset_id VARCHAR(64) NOT NULL,
                    column_name VARCHAR(128) NOT NULL,
                    original_column_name VARCHAR(255) NOT NULL,
                    data_type VARCHAR(64) NOT NULL,
                    nullable TINYINT(1) NOT NULL DEFAULT 1,
                    description VARCHAR(255) NULL,
                    position INT NOT NULL,
                    PRIMARY KEY (dataset_id, column_name)
                )
                """
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()
            
        # Migrate schema
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'datasets' AND COLUMN_NAME = 'google_drive_folder_id'
                """,
                (self.config.database,),
            )
            if int(cursor.fetchone()[0]) == 0:
                cursor.execute("ALTER TABLE datasets ADD COLUMN google_drive_folder_id VARCHAR(255) NULL AFTER storage_reference")
                cursor.execute("ALTER TABLE datasets ADD COLUMN file_size BIGINT NULL AFTER google_drive_folder_id")
                connection.commit()
            cursor.close()
        finally:
            connection.close()
            
        self._seed_demo_dataset()

    def _seed_demo_dataset(self) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM datasets WHERE dataset_id = %s", (DEMO_PLACEMENT_DATASET_ID,))
            if cursor.fetchone():
                cursor.close()
                return
            row_count = 0
            column_count = 0
            try:
                cursor.execute("SELECT COUNT(*) FROM placement")
                row_count = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    """,
                    (self.config.database, DEMO_PLACEMENT_TABLE),
                )
                column_count = int(cursor.fetchone()[0])
            except Exception:
                pass
            cursor.execute(
                """
                INSERT INTO datasets (
                    dataset_id, dataset_name, original_filename, internal_table_name,
                    storage_reference, row_count, column_count, status, is_builtin, validation_status
                ) VALUES (%s, %s, %s, %s, NULL, %s, %s, 'READY', 1, 'valid')
                """,
                (DEMO_PLACEMENT_DATASET_ID, DEMO_PLACEMENT_NAME, "placement.csv", DEMO_PLACEMENT_TABLE, row_count, column_count),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def generate_dataset_id(self) -> str:
        return str(uuid4())

    def generate_internal_table_name(self, dataset_id: str) -> str:
        return f"ds_{dataset_id.replace('-', '')[:12]}"

    def create_dataset(
        self,
        *,
        dataset_id: str,
        user_id: str,
        dataset_name: str,
        original_filename: str,
        internal_table_name: str,
        storage_reference: str | None,
        google_drive_folder_id: str | None = None,
        file_size: int | None = None,
        status: str,
        validation_status: str,
    ) -> None:
        if not is_valid_dataset_id(dataset_id) or not is_safe_internal_table_name(internal_table_name):
            raise DatasetRegistryError("Invalid dataset identifiers.")
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO datasets (
                    dataset_id, user_id, dataset_name, original_filename, internal_table_name,
                    storage_reference, google_drive_folder_id, file_size, status, validation_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (dataset_id, user_id, dataset_name, original_filename, internal_table_name, storage_reference, google_drive_folder_id, file_size, status, validation_status),
            )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def update_dataset(
        self,
        dataset_id: str,
        *,
        status: str | None = None,
        row_count: int | None = None,
        column_count: int | None = None,
        validation_status: str | None = None,
        error_message: str | None = None,
        dataset_name: str | None = None,
    ) -> None:
        fields: list[str] = []
        values: list[Any] = []
        for name, value in (
            ("status", status),
            ("row_count", row_count),
            ("column_count", column_count),
            ("validation_status", validation_status),
            ("error_message", error_message),
            ("dataset_name", dataset_name),
        ):
            if value is not None:
                fields.append(f"{name} = %s")
                values.append(value)
        if not fields:
            return
        values.append(dataset_id)
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(f"UPDATE datasets SET {', '.join(fields)} WHERE dataset_id = %s", tuple(values))
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def replace_columns(self, dataset_id: str, columns: list[DatasetColumnRecord]) -> None:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM dataset_columns WHERE dataset_id = %s", (dataset_id,))
            for column in columns:
                cursor.execute(
                    """
                    INSERT INTO dataset_columns (
                        dataset_id, column_name, original_column_name, data_type, nullable, description, position
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        dataset_id,
                        column.column_name,
                        column.original_column_name,
                        column.data_type,
                        int(column.nullable),
                        column.description,
                        column.position,
                    ),
                )
            connection.commit()
            cursor.close()
        finally:
            connection.close()

    def get_dataset(self, dataset_id: str) -> DatasetRecord:
        if not is_valid_dataset_id(dataset_id):
            raise DatasetNotFoundError(f"Unknown dataset_id: {dataset_id}")
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM datasets WHERE dataset_id = %s", (dataset_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row or row["status"] == "DELETED":
                raise DatasetNotFoundError(f"Dataset not found: {dataset_id}")
            return _record_from_row(row)
        finally:
            connection.close()

    def list_datasets(self, include_deleted: bool = False) -> list[DatasetRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            if include_deleted:
                cursor.execute("SELECT * FROM datasets ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT * FROM datasets WHERE status <> 'DELETED' ORDER BY created_at DESC")
            rows = cursor.fetchall()
            cursor.close()
            return [_record_from_row(row) for row in rows]
        finally:
            connection.close()

    def get_columns(self, dataset_id: str) -> list[DatasetColumnRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM dataset_columns WHERE dataset_id = %s ORDER BY position ASC",
                (dataset_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            if rows:
                return [
                    DatasetColumnRecord(
                        column_name=row["column_name"],
                        original_column_name=row["original_column_name"],
                        data_type=row["data_type"],
                        nullable=bool(row["nullable"]),
                        description=row["description"],
                        position=int(row["position"]),
                    )
                    for row in rows
                ]
        finally:
            connection.close()

        # Built-in placement fallback from information_schema when columns not seeded.
        dataset = self.get_dataset(dataset_id)
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, ORDINAL_POSITION
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
                """,
                (self.config.database, dataset.internal_table_name),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                DatasetColumnRecord(
                    column_name=row["COLUMN_NAME"],
                    original_column_name=row["COLUMN_NAME"],
                    data_type=row["COLUMN_TYPE"],
                    nullable=row["IS_NULLABLE"] == "YES",
                    description=None,
                    position=int(row["ORDINAL_POSITION"]),
                )
                for row in rows
            ]
        finally:
            connection.close()

    def get_dataset_for_user(self, dataset_id: str, user_id: str) -> DatasetRecord:
        record = self.get_dataset(dataset_id)
        if record.is_builtin and record.user_id is None:
            return record
        if record.user_id != user_id:
            raise DatasetNotFoundError(f"Dataset not found: {dataset_id}")
        return record

    def list_datasets_for_user(self, user_id: str, include_deleted: bool = False) -> list[DatasetRecord]:
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            status_clause = "" if include_deleted else "AND status <> 'DELETED'"
            cursor.execute(
                f"""
                SELECT * FROM datasets
                WHERE (user_id = %s OR (is_builtin = 1 AND user_id IS NULL))
                {status_clause}
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [_record_from_row(row) for row in rows]
        finally:
            connection.close()

    def delete_dataset_for_user(self, dataset_id: str, user_id: str) -> DatasetRecord:
        dataset = self.get_dataset_for_user(dataset_id, user_id)
        if dataset.is_builtin:
            raise DatasetRegistryError("Built-in demo datasets cannot be deleted.")
        return self._delete_dataset_record(dataset)

    def delete_dataset(self, dataset_id: str) -> DatasetRecord:
        dataset = self.get_dataset(dataset_id)
        if dataset.is_builtin:
            raise DatasetRegistryError("Built-in demo datasets cannot be deleted.")
        return self._delete_dataset_record(dataset)

    def _delete_dataset_record(self, dataset: DatasetRecord) -> DatasetRecord:
        self.update_dataset(dataset.dataset_id, status="DELETING")
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            if is_safe_internal_table_name(dataset.internal_table_name) and dataset.internal_table_name.startswith("ds_"):
                cursor.execute(f"DROP TABLE IF EXISTS `{dataset.internal_table_name}`")
            cursor.execute("DELETE FROM dataset_columns WHERE dataset_id = %s", (dataset.dataset_id,))
            cursor.execute("DELETE FROM datasets WHERE dataset_id = %s", (dataset.dataset_id,))
            connection.commit()
            cursor.close()
        finally:
            connection.close()
        return dataset


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            try:
                from datetime import datetime as dt
                return dt.strptime(value, "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
    from datetime import timezone
    return datetime.now(timezone.utc)


def _record_from_row(row: Any) -> DatasetRecord:
    if not isinstance(row, dict):
        row = {key: row[key] for key in row.keys()}
    return DatasetRecord(
        dataset_id=row["dataset_id"],
        user_id=row.get("user_id"),
        dataset_name=row["dataset_name"],
        original_filename=row["original_filename"],
        internal_table_name=row["internal_table_name"],
        storage_reference=row.get("storage_reference"),
        google_drive_folder_id=row.get("google_drive_folder_id"),
        file_size=row.get("file_size"),
        row_count=int(row["row_count"]),
        column_count=int(row["column_count"]),
        status=row["status"],
        is_builtin=bool(row["is_builtin"]),
        validation_status=row["validation_status"],
        error_message=row.get("error_message"),
        created_at=_parse_datetime(row.get("created_at")),
        updated_at=_parse_datetime(row.get("updated_at")),
    )
