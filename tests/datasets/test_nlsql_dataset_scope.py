import pandas as pd

from backend.ai.nlsql.query_manager import QueryManager
from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID


class ScopedRepository:
    def __init__(self) -> None:
        self.frames = {
            DEMO_PLACEMENT_DATASET_ID: pd.DataFrame({"CGPA": [8.0, 7.0], "Placement": ["Yes", "No"]}),
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa": pd.DataFrame({"sales": [100.0, 200.0], "region": ["North", "South"]}),
        }

    def resolve_table(self, dataset_id: str):
        frame = self.frames[dataset_id]
        return f"table_{dataset_id[:8]}", list(frame.columns)

    def load_dataframe(self, dataset_id: str):
        return self.frames[dataset_id].copy()

    def schema(self, dataset_id: str):
        return [{"name": column, "data_type": "double", "nullable": True, "primary_key": False} for column in self.frames[dataset_id].columns]

    def _database_name(self):
        return "askmydata"


def test_schema_context_changes_with_dataset_id():
    repository = ScopedRepository()
    manager = QueryManager(repository)
    placement_schema = manager.schema(DEMO_PLACEMENT_DATASET_ID)
    sales_schema = manager.schema("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert "CGPA" in placement_schema.column_names
    assert "sales" in sales_schema.column_names
    assert placement_schema.table != sales_schema.table
