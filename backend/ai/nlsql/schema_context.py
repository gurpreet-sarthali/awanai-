from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID
from backend.repositories.database_repository import DatabaseRepository


@dataclass(frozen=True)
class SchemaContext:
    database: str
    table: str
    dataset_id: str
    columns: tuple[dict[str, Any], ...]
    categorical_values: dict[str, tuple[str, ...]]

    @property
    def column_names(self) -> set[str]:
        return {str(column["name"]) for column in self.columns}

    def description(self) -> str:
        lines = [f"DATABASE: {self.database}", f"TABLE: {self.table}", f"DATASET_ID: {self.dataset_id}"]
        for column in self.columns:
            key = " PRIMARY KEY" if column.get("primary_key") else ""
            lines.append(f"COLUMN: {column['name']} | TYPE: {column['data_type']} | NULLABLE: {column['nullable']}{key} | DESCRIPTION: Needs confirmation")
            values = self.categorical_values.get(str(column["name"]))
            if values:
                lines.append(f"ALLOWED VALUES: {', '.join(values)}")
        return "\n".join(lines)


def load_schema_context(repository: DatabaseRepository, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> SchemaContext:
    columns = repository.schema(dataset_id)
    dataframe = repository.load_dataframe(dataset_id)
    categorical: dict[str, tuple[str, ...]] = {}
    for column in dataframe.columns:
        unique = dataframe[column].dropna().unique()
        if len(unique) <= 20:
            categorical[str(column)] = tuple(sorted(str(value) for value in unique))
    table_name, _ = repository.resolve_table(dataset_id)
    database = repository._database_name()
    return SchemaContext(
        database=database,
        table=table_name,
        dataset_id=dataset_id,
        columns=tuple(columns),
        categorical_values=categorical,
    )
