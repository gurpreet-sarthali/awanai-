from analytics.loader import PLACEMENT_TABLE, dataframe_shape
from analytics.validation import validate_data
from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID

from backend.repositories.database_repository import DatabaseRepository


class DatasetService:
    def __init__(self, repository: DatabaseRepository) -> None:
        self.repository = repository

    def summary(self, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> dict[str, object]:
        dataframe = self.repository.load_dataframe(dataset_id)
        validation = validate_data(dataframe) if dataset_id == DEMO_PLACEMENT_DATASET_ID else {"missing_values": {str(column): int(value) for column, value in dataframe.isna().sum().items() if int(value) > 0}, "warnings": []}
        shape = dataframe_shape(dataframe)
        table_name, _ = self.repository.resolve_table(dataset_id)
        return {
            "dataset_id": dataset_id,
            "table": table_name if dataset_id != DEMO_PLACEMENT_DATASET_ID else PLACEMENT_TABLE,
            "rows": shape["row_count"],
            "columns": shape["column_count"],
            "missing_values": validation["missing_values"],
            "available_columns": list(dataframe.columns),
            "warnings": validation.get("warnings", []),
        }

    def schema(self, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> dict[str, object]:
        table_name, _ = self.repository.resolve_table(dataset_id)
        return {"dataset_id": dataset_id, "table": table_name, "columns": self.repository.schema(dataset_id)}

    def sample(self, limit: int, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> dict[str, object]:
        table_name, _ = self.repository.resolve_table(dataset_id)
        return {"dataset_id": dataset_id, "table": table_name, "rows": self.repository.sample(dataset_id, limit)}
