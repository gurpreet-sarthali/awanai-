"""Import validated CSV data into isolated MySQL tables."""

from __future__ import annotations

from typing import Any

import pandas as pd

from analytics.csv_dataset import infer_mysql_type
from analytics.database import DatabaseConfig, connect
from backend.core.dataset_constants import is_safe_internal_table_name
from backend.repositories.dataset_registry_repository import DatasetColumnRecord


class DatasetImportError(RuntimeError):
    pass


class DatasetImportService:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config

    def import_dataframe(self, table_name: str, dataframe: pd.DataFrame, column_map: list[tuple[str, str]]) -> dict[str, Any]:
        if not is_safe_internal_table_name(table_name) or not table_name.startswith("ds_"):
            raise DatasetImportError("Refusing to import into an unsafe table name.")

        column_defs = []
        records: list[DatasetColumnRecord] = []
        for position, (original, normalized) in enumerate(column_map, start=1):
            mysql_type = infer_mysql_type(dataframe[normalized])
            column_defs.append(f"`{normalized}` {mysql_type}")
            records.append(
                DatasetColumnRecord(
                    column_name=normalized,
                    original_column_name=original,
                    data_type=mysql_type.replace(" NULL", ""),
                    nullable=True,
                    description=None,
                    position=position,
                )
            )

        connection = connect(self.config)
        created = False
        try:
            cursor = connection.cursor()
            cursor.execute(f"CREATE TABLE `{table_name}` ({', '.join(column_defs)})")
            created = True
            columns = [normalized for _, normalized in column_map]
            placeholders = ", ".join(["%s"] * len(columns))
            column_sql = ", ".join(f"`{column}`" for column in columns)
            insert_sql = f"INSERT INTO `{table_name}` ({column_sql}) VALUES ({placeholders})"
            rows = [
                tuple(None if pd.isna(value) else value for value in row)
                for row in dataframe[columns].itertuples(index=False, name=None)
            ]
            if rows:
                cursor.executemany(insert_sql, rows)
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            imported_rows = int(cursor.fetchone()[0])
            connection.commit()
            cursor.close()
            if imported_rows != len(dataframe):
                raise DatasetImportError("Imported row count does not match the validated dataframe.")
            null_counts = {column: int(dataframe[column].isna().sum()) for column in columns}
            return {
                "row_count": imported_rows,
                "column_count": len(columns),
                "columns": records,
                "null_counts": null_counts,
            }
        except Exception as error:
            connection.rollback()
            if created:
                cleanup = connect(self.config)
                try:
                    cleanup_cursor = cleanup.cursor()
                    cleanup_cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                    cleanup.commit()
                    cleanup_cursor.close()
                finally:
                    cleanup.close()
            raise DatasetImportError(str(error)) from error
        finally:
            connection.close()

    def drop_table_if_exists(self, table_name: str) -> None:
        if not is_safe_internal_table_name(table_name) or not table_name.startswith("ds_"):
            return
        connection = connect(self.config)
        try:
            cursor = connection.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
            connection.commit()
            cursor.close()
        finally:
            connection.close()
