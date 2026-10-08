from typing import Any

from pydantic import Field

from .common import APIModel
from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID


class ManagedDatasetSummary(APIModel):
    dataset_id: str
    dataset_name: str
    filename: str
    original_filename: str
    row_count: int
    column_count: int
    status: str
    is_builtin: bool
    created_at: str


class ManagedDatasetList(APIModel):
    datasets: list[ManagedDatasetSummary]


class ManagedDatasetDetail(APIModel):
    dataset_id: str
    dataset_name: str
    filename: str
    rows: int
    columns: int
    status: str
    is_builtin: bool
    created_at: str
    updated_at: str
    validation: dict[str, Any]


class ManagedDatasetColumn(APIModel):
    column_name: str
    original_column_name: str
    data_type: str
    nullable: bool
    description: str | None = None
    position: int


class ManagedDatasetSchema(APIModel):
    dataset_id: str
    dataset_name: str
    columns: list[ManagedDatasetColumn]


class ManagedDatasetPreview(APIModel):
    dataset_id: str
    dataset_name: str
    limit: int
    rows: list[dict[str, Any]]


class DatasetUploadResponse(APIModel):
    dataset_id: str
    filename: str
    dataset_name: str
    rows: int
    columns: int
    missing_values: dict[str, int]
    duplicate_rows: int
    cleaning: dict[str, Any]
    warnings: list[str]
    status: str


class DatasetDeleteResponse(APIModel):
    dataset_id: str
    status: str


class DatasetUploadForm(APIModel):
    dataset_name: str | None = Field(default=None, max_length=255)
