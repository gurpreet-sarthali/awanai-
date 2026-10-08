"""Read-only database access for API services."""

from __future__ import annotations

from typing import Any

import pandas as pd

from analytics.database import DatabaseConfig, connect
from analytics.loader import EXPECTED_COLUMNS, PLACEMENT_TABLE, load_placement_data
from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID, is_valid_dataset_id
from backend.repositories.dataset_registry_repository import DatasetNotFoundError, DatasetRegistryRepository


class DatabaseRepository:
    def __init__(self, config: DatabaseConfig | None = None, registry: DatasetRegistryRepository | None = None, user_id: str | None = None) -> None:
        self.config = config
        self.registry = registry
        self.user_id = user_id

    def check_connection(self) -> bool:
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        finally:
            connection.close()

    def resolve_table(self, dataset_id: str) -> tuple[str, list[str]]:
        if not is_valid_dataset_id(dataset_id):
            raise DatasetNotFoundError(f"Invalid dataset_id: {dataset_id}")
        if dataset_id == DEMO_PLACEMENT_DATASET_ID:
            return PLACEMENT_TABLE, list(EXPECTED_COLUMNS)
        if dataset_id == DEMO_PLACEMENT_DATASET_ID:
            return PLACEMENT_TABLE, list(EXPECTED_COLUMNS)
        if self.registry is None:
            raise DatasetNotFoundError("Dataset registry is unavailable.")
        if self.user_id is not None:
            record = self.registry.get_dataset_for_user(dataset_id, self.user_id)
        else:
            record = self.registry.get_dataset(dataset_id)
        if record.status != "READY":
            raise DatasetNotFoundError(f"Dataset `{dataset_id}` is not ready.")
        columns = [column.column_name for column in self.registry.get_columns(dataset_id)]
        if not columns:
            raise DatasetNotFoundError(f"Dataset `{dataset_id}` has no column metadata.")
        return record.internal_table_name, columns

    def load_dataframe(self, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> pd.DataFrame:
        if dataset_id == DEMO_PLACEMENT_DATASET_ID and self.registry is None:
            return load_placement_data(self.config)
        table_name, columns = self.resolve_table(dataset_id)
        if dataset_id == DEMO_PLACEMENT_DATASET_ID:
            return load_placement_data(self.config)
        query = "SELECT " + ", ".join(f"`{column}`" for column in columns) + f" FROM `{table_name}`"
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [description[0] for description in cursor.description]
            cursor.close()
            return pd.DataFrame(rows, columns=column_names)
        finally:
            connection.close()

    def schema(self, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> list[dict[str, Any]]:
        if self.registry is not None:
            try:
                columns = self.registry.get_columns(dataset_id)
                if columns:
                    return [
                        {
                            "name": column.column_name,
                            "data_type": column.data_type,
                            "nullable": column.nullable,
                            "primary_key": False,
                            "original_name": column.original_column_name,
                        }
                        for column in columns
                    ]
            except DatasetNotFoundError:
                pass
        table_name, _ = self.resolve_table(dataset_id)
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
                (self._database_name(), table_name),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "name": row["COLUMN_NAME"],
                    "data_type": row["COLUMN_TYPE"],
                    "nullable": row["IS_NULLABLE"] == "YES",
                    "primary_key": row["COLUMN_KEY"] == "PRI",
                    "original_name": row["COLUMN_NAME"],
                }
                for row in rows
            ]
        finally:
            connection.close()

    def sample(self, dataset_id: str, limit: int) -> list[dict[str, Any]]:
        table_name, columns = self.resolve_table(dataset_id)
        connection = connect(self.config)
        try:
            cursor = connection.cursor(dictionary=True)
            column_sql = ", ".join(f"`{column}`" for column in columns)
            cursor.execute(f"SELECT {column_sql} FROM `{table_name}` LIMIT %s", (limit,))
            rows = cursor.fetchall()
            cursor.close()
            return [_json_safe(row) for row in rows]
        finally:
            connection.close()

    def _database_name(self) -> str:
        config = getattr(self, "config", None)
        if config is not None:
            return config.database
        return "askmydata"


def _json_safe(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if value is None or (isinstance(value, float) and pd.isna(value)):
            result[key] = None
        elif hasattr(value, "item"):
            result[key] = value.item()
        else:
            result[key] = value
    return result
