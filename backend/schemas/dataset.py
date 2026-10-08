from typing import Any

from .common import APIModel
from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID


class DatasetSummary(APIModel):
    dataset_id: str = DEMO_PLACEMENT_DATASET_ID
    table: str
    rows: int
    columns: int
    missing_values: dict[str, int]
    available_columns: list[str]
    warnings: list[str]


class DatasetColumn(APIModel):
    name: str
    data_type: str
    nullable: bool
    primary_key: bool


class DatasetSchema(APIModel):
    dataset_id: str = DEMO_PLACEMENT_DATASET_ID
    table: str
    columns: list[DatasetColumn]


class DatasetSample(APIModel):
    dataset_id: str = DEMO_PLACEMENT_DATASET_ID
    table: str
    rows: list[dict[str, Any]]