from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ResourceType = Literal["dataset", "column", "conversation", "saved_query", "report", "workspace", "analytics_result"]


class SearchResult(BaseModel):
    id: str
    type: ResourceType
    title: str
    description: str | None = None
    workspace_id: str | None = None
    workspace_name: str | None = None
    dataset_id: str | None = None
    dataset_name: str | None = None
    updated_at: str | None = None
    score: float = 0
    matched_fields: list[str] = Field(default_factory=list)
    favorite: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: dict[str, list[SearchResult]]
    total: int
    page: int
    limit: int


class SuggestionResponse(BaseModel):
    query: str
    suggestions: dict[str, list[SearchResult]]
    recent_searches: list[str]


class SearchHistoryItem(BaseModel):
    id: str
    query: str
    workspace_id: str | None = None
    created_at: str


class SearchHistoryResponse(BaseModel):
    history: list[SearchHistoryItem]


class RecentItemsResponse(BaseModel):
    items: list[SearchResult]


class DatasetCatalogItem(BaseModel):
    dataset_id: str
    dataset_name: str
    filename: str
    description: str | None = None
    owner_id: str | None = None
    workspace_ids: list[str] = Field(default_factory=list)
    source_type: str
    file_format: str | None = None
    rows: int
    columns: int
    quality_score: float | None = None
    status: str
    validation_status: str
    version: str
    tags: list[str] = Field(default_factory=list)
    favorite: bool = False
    is_builtin: bool = False
    sharing_status: str
    created_at: str
    updated_at: str
    last_analyzed_at: str | None = None


class DatasetCatalogList(BaseModel):
    datasets: list[DatasetCatalogItem]
    total: int
    page: int
    limit: int


class DatasetCatalogDetail(DatasetCatalogItem):
    google_drive_folder_id: str | None = None
    file_size: int | None = None


class CatalogSchemaColumn(BaseModel):
    column_name: str
    original_column_name: str
    data_type: str
    nullable: bool
    description: str | None = None
    position: int
    unique_count: int | None = None
    missing_count: int | None = None
    statistics: dict[str, Any] | None = None


class CatalogSchemaResponse(BaseModel):
    dataset_id: str
    columns: list[CatalogSchemaColumn]


class DatasetVersionItem(BaseModel):
    dataset_id: str
    version: str
    row_count: int
    column_count: int
    created_at: str
    source: str


class DatasetVersionsResponse(BaseModel):
    versions: list[DatasetVersionItem]


class DatasetTagsResponse(BaseModel):
    dataset_id: str
    tags: list[str]


class TagRequest(BaseModel):
    tag: str = Field(min_length=1, max_length=64)


class DatasetDescriptionRequest(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    source_type: str | None = Field(default=None, max_length=32)
    file_format: str | None = Field(default=None, max_length=32)
    quality_score: float | None = Field(default=None, ge=0, le=100)


class FavoriteRequest(BaseModel):
    resource_type: ResourceType
    resource_id: str = Field(min_length=1, max_length=128)
    workspace_id: str | None = Field(default=None, max_length=128)
