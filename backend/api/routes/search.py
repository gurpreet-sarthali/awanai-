from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status

from backend.api.dependencies import get_current_user, get_search_service
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.schemas.search import (
    DatasetCatalogDetail,
    DatasetCatalogList,
    DatasetDescriptionRequest,
    DatasetTagsResponse,
    DatasetVersionsResponse,
    CatalogSchemaResponse,
    FavoriteRequest,
    RecentItemsResponse,
    SearchHistoryResponse,
    SearchResponse,
    SuggestionResponse,
    TagRequest,
)
from backend.services.search_service import SearchFilters, SearchPermissionError, SearchService


search_router = APIRouter(prefix="/search", tags=["search"])
catalog_router = APIRouter(prefix="/catalog", tags=["dataset catalog"])


def _filters(
    workspace_id: str | None = None,
    file_type: str | None = None,
    status_value: str | None = None,
    source_type: str | None = None,
    tags: str | None = None,
    favorite: bool | None = None,
    min_rows: int | None = None,
    max_rows: int | None = None,
    min_columns: int | None = None,
    max_columns: int | None = None,
    min_quality: float | None = None,
    max_quality: float | None = None,
    shared: bool | None = None,
) -> SearchFilters:
    return SearchFilters(
        workspace_id=workspace_id,
        file_type=file_type,
        status=status_value,
        source_type=source_type,
        tags=tuple(tag.strip().lower() for tag in (tags or "").split(",") if tag.strip()),
        favorite=favorite,
        min_rows=min_rows,
        max_rows=max_rows,
        min_columns=min_columns,
        max_columns=max_columns,
        min_quality=min_quality,
        max_quality=max_quality,
        shared=shared,
    )


def _handle_error(error: Exception) -> AppError:
    if isinstance(error, SearchPermissionError):
        return AppError(404, "resource_not_found", "Resource was not found.")
    if isinstance(error, ValueError):
        return AppError(400, "invalid_search_request", str(error))
    return AppError(503, "search_unavailable", "Search is temporarily unavailable.")


@search_router.get("", response_model=SearchResponse)
def global_search(
    q: str = Query(default="", max_length=512),
    type: str | None = Query(default=None, max_length=32),
    workspace_id: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="relevance", max_length=32),
    file_type: str | None = Query(default=None, max_length=32),
    status_value: str | None = Query(default=None, alias="status", max_length=32),
    source_type: str | None = Query(default=None, max_length=32),
    tags: str | None = Query(default=None, max_length=512),
    favorite: bool | None = None,
    shared: bool | None = None,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.global_search(
            user=user,
            query=q,
            resource_type=type,
            filters=_filters(workspace_id=workspace_id, file_type=file_type, status_value=status_value, source_type=source_type, tags=tags, favorite=favorite, shared=shared),
            sort=sort,
            page=page,
            limit=limit,
        )
    except Exception as error:
        raise _handle_error(error) from error


@search_router.get("/suggestions", response_model=SuggestionResponse)
def suggestions(
    q: str = Query(default="", max_length=128),
    workspace_id: str | None = Query(default=None, max_length=128),
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.suggestions(user=user, query=q, workspace_id=workspace_id)
    except Exception as error:
        raise _handle_error(error) from error


@search_router.get("/history", response_model=SearchHistoryResponse)
def search_history(
    limit: int = Query(default=20, ge=1, le=100),
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    return {"history": service.search_history(user, limit)}


@search_router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_search_history(
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> None:
    service.clear_search_history(user)


@search_router.get("/recent", response_model=RecentItemsResponse)
def recent_items(
    limit: int = Query(default=20, ge=1, le=100),
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    return {"items": service.recent_items(user, limit)}


@search_router.post("/recent", status_code=status.HTTP_204_NO_CONTENT)
def record_recent(
    payload: FavoriteRequest,
    title: str = Query(min_length=1, max_length=255),
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> None:
    try:
        service.record_recent(user=user, resource_type=payload.resource_type, resource_id=payload.resource_id, title=title, workspace_id=payload.workspace_id)
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.get("/datasets", response_model=DatasetCatalogList)
def catalog_datasets(
    q: str = Query(default="", max_length=512),
    workspace_id: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="updated_desc", max_length=32),
    file_type: str | None = Query(default=None, max_length=32),
    status_value: str | None = Query(default=None, alias="status", max_length=32),
    source_type: str | None = Query(default=None, max_length=32),
    tags: str | None = Query(default=None, max_length=512),
    favorite: bool | None = None,
    shared: bool | None = None,
    min_rows: int | None = Query(default=None, ge=0),
    max_rows: int | None = Query(default=None, ge=0),
    min_columns: int | None = Query(default=None, ge=0),
    max_columns: int | None = Query(default=None, ge=0),
    min_quality: float | None = Query(default=None, ge=0, le=100),
    max_quality: float | None = Query(default=None, ge=0, le=100),
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.catalog_datasets(
            user=user,
            query=q,
            filters=_filters(
                workspace_id=workspace_id,
                file_type=file_type,
                status_value=status_value,
                source_type=source_type,
                tags=tags,
                favorite=favorite,
                min_rows=min_rows,
                max_rows=max_rows,
                min_columns=min_columns,
                max_columns=max_columns,
                min_quality=min_quality,
                max_quality=max_quality,
                shared=shared,
            ),
            sort=sort,
            page=page,
            limit=limit,
        )
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.get("/datasets/{dataset_id}", response_model=DatasetCatalogDetail)
def catalog_dataset_detail(
    dataset_id: str,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.dataset_detail(user, dataset_id)
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.patch("/datasets/{dataset_id}", response_model=DatasetCatalogDetail)
def update_dataset_catalog_metadata(
    dataset_id: str,
    payload: DatasetDescriptionRequest,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.update_dataset_metadata(user=user, dataset_id=dataset_id, payload=payload.model_dump(exclude_unset=True))
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.get("/datasets/{dataset_id}/schema", response_model=CatalogSchemaResponse)
def catalog_dataset_schema(
    dataset_id: str,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.dataset_schema(user, dataset_id)
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.get("/datasets/{dataset_id}/versions", response_model=DatasetVersionsResponse)
def catalog_dataset_versions(
    dataset_id: str,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.dataset_versions(user, dataset_id)
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.get("/datasets/{dataset_id}/tags", response_model=DatasetTagsResponse)
def catalog_dataset_tags(
    dataset_id: str,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.tags(user, dataset_id)
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.post("/datasets/{dataset_id}/tags", response_model=DatasetTagsResponse)
def add_catalog_dataset_tag(
    dataset_id: str,
    payload: TagRequest,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.add_tag(user=user, dataset_id=dataset_id, tag=payload.tag)
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.delete("/datasets/{dataset_id}/tags/{tag}", response_model=DatasetTagsResponse)
def delete_catalog_dataset_tag(
    dataset_id: str,
    tag: str,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    try:
        return service.remove_tag(user=user, dataset_id=dataset_id, tag=tag)
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.post("/favorites", status_code=status.HTTP_204_NO_CONTENT)
def favorite_resource(
    payload: FavoriteRequest,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> None:
    try:
        service.set_favorite(user=user, resource_type=payload.resource_type, resource_id=payload.resource_id, workspace_id=payload.workspace_id)
    except Exception as error:
        raise _handle_error(error) from error


@catalog_router.delete("/favorites/{resource_type}/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def unfavorite_resource(
    resource_type: str,
    resource_id: str,
    user: UserRecord = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> None:
    service.remove_favorite(user=user, resource_type=resource_type, resource_id=resource_id)
