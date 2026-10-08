"""Permission-aware search and dataset catalog service."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.core.user_model import UserRecord
from backend.repositories.automation_repository import AutomationRepository
from backend.repositories.chat_repository import ChatRepository
from backend.repositories.dataset_registry_repository import DatasetRecord, DatasetRegistryRepository
from backend.repositories.search_repository import CatalogMetadataRecord, SearchRepository
from backend.repositories.workspace_repository import WorkspaceRepository
from backend.services.dataset_access_service import DatasetAccessError, DatasetAccessService
from backend.services.workspace_service import RolePermissions


class SearchPermissionError(PermissionError):
    pass


@dataclass(frozen=True, kw_only=True)
class SearchFilters:
    workspace_id: str | None = None
    file_type: str | None = None
    status: str | None = None
    source_type: str | None = None
    tags: tuple[str, ...] = ()
    favorite: bool | None = None
    min_rows: int | None = None
    max_rows: int | None = None
    min_columns: int | None = None
    max_columns: int | None = None
    min_quality: float | None = None
    max_quality: float | None = None
    shared: bool | None = None


class SearchService:
    def __init__(
        self,
        *,
        repository: SearchRepository,
        registry: DatasetRegistryRepository,
        workspaces: WorkspaceRepository,
        chat: ChatRepository,
        automation: AutomationRepository,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.workspaces = workspaces
        self.chat = chat
        self.automation = automation

    def global_search(
        self,
        *,
        user: UserRecord,
        query: str,
        resource_type: str | None = None,
        filters: SearchFilters | None = None,
        sort: str = "relevance",
        page: int = 1,
        limit: int = 20,
        record_history: bool = True,
    ) -> dict[str, Any]:
        filters = filters or SearchFilters()
        normalized_type = resource_type.strip().lower() if resource_type else None
        tokens = _tokens(query)
        if record_history and query.strip():
            self.repository.record_search(user_id=user.id, query=query, workspace_id=filters.workspace_id)

        items: list[dict[str, Any]] = []
        allowed = {normalized_type} if normalized_type else {"dataset", "column", "conversation", "saved_query", "workspace", "analytics_result", "report"}
        if "dataset" in allowed or "column" in allowed:
            dataset_items, column_items = self._dataset_and_column_results(user, tokens, filters)
            if "dataset" in allowed:
                items.extend(dataset_items)
            if "column" in allowed:
                items.extend(column_items)
        if "workspace" in allowed:
            items.extend(self._workspace_results(user, tokens, filters))
        if "conversation" in allowed:
            items.extend(self._conversation_results(user, tokens, filters))
        if "saved_query" in allowed:
            items.extend(self._saved_query_results(user, tokens, filters))
        if "analytics_result" in allowed or "report" in allowed:
            analytics_results = self._analytics_result_results(user, tokens, filters)
            if "analytics_result" in allowed:
                items.extend(analytics_results)
            # Reports are represented only when an analysis result looks report-like.
            if "report" in allowed:
                items.extend([{**item, "type": "report"} for item in analytics_results if "report" in item["title"].lower()])

        if tokens:
            items = [item for item in items if item["score"] > 0]
        items = _dedupe(items)
        items = self._sort_results(items, sort)
        total = len(items)
        start = (max(page, 1) - 1) * limit
        end = start + limit
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in items[start:end]:
            grouped.setdefault(f"{item['type']}s", []).append(item)
        for key in ("datasets", "columns", "conversations", "saved_querys", "reports", "workspaces", "analytics_results"):
            grouped.setdefault(key, [])
        if "saved_querys" in grouped:
            grouped["saved_queries"] = grouped.pop("saved_querys")
        return {"query": query, "results": grouped, "total": total, "page": page, "limit": limit}

    def suggestions(self, *, user: UserRecord, query: str, workspace_id: str | None = None, limit: int = 5) -> dict[str, Any]:
        response = self.global_search(
            user=user,
            query=query,
            filters=SearchFilters(workspace_id=workspace_id),
            sort="relevance",
            page=1,
            limit=max(1, min(limit, 10)),
            record_history=False,
        )
        history = [row["search_query"] for row in self.repository.list_search_history(user.id, limit=5)]
        return {"query": query, "suggestions": response["results"], "recent_searches": history}

    def catalog_datasets(
        self,
        *,
        user: UserRecord,
        query: str = "",
        filters: SearchFilters | None = None,
        sort: str = "updated_desc",
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        filters = filters or SearchFilters()
        items = [self._catalog_item(user, dataset, filters) for dataset in self._accessible_datasets(user)]
        items = [item for item in items if self._dataset_filter(item, filters)]
        tokens = _tokens(query)
        if tokens:
            scored = []
            for item in items:
                score, matched = _score(tokens, {
                    "name": item["dataset_name"],
                    "filename": item["filename"],
                    "description": item.get("description") or "",
                    "tags": " ".join(item.get("tags", [])),
                })
                if score > 0:
                    scored.append({**item, "_score": score, "_matched": matched})
            items = scored
        items = self._sort_catalog(items, sort)
        total = len(items)
        start = (max(page, 1) - 1) * limit
        return {"datasets": items[start:start + limit], "total": total, "page": page, "limit": limit}

    def dataset_detail(self, user: UserRecord, dataset_id: str) -> dict[str, Any]:
        dataset = self._require_dataset(user, dataset_id)
        item = self._catalog_item(user, dataset, SearchFilters())
        return {
            **item,
            "google_drive_folder_id": dataset.google_drive_folder_id,
            "file_size": dataset.file_size,
        }

    def dataset_schema(self, user: UserRecord, dataset_id: str) -> dict[str, Any]:
        self._require_dataset(user, dataset_id)
        columns = self.registry.get_columns(dataset_id)
        return {
            "dataset_id": dataset_id,
            "columns": [
                {
                    "column_name": column.column_name,
                    "original_column_name": column.original_column_name,
                    "data_type": column.data_type,
                    "nullable": column.nullable,
                    "description": column.description,
                    "position": column.position,
                    "unique_count": None,
                    "missing_count": None,
                    "statistics": None,
                }
                for column in columns
            ],
        }

    def dataset_versions(self, user: UserRecord, dataset_id: str) -> dict[str, Any]:
        dataset = self._require_dataset(user, dataset_id)
        meta = self.repository.get_metadata(dataset_id)
        return {
            "versions": [
                {
                    "dataset_id": dataset.dataset_id,
                    "version": meta.version_label if meta else "v1",
                    "row_count": dataset.row_count,
                    "column_count": dataset.column_count,
                    "created_at": _iso(dataset.updated_at),
                    "source": "catalog",
                }
            ]
        }

    def update_dataset_metadata(self, *, user: UserRecord, dataset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        dataset = self._require_dataset(user, dataset_id)
        self._require_dataset_editor(user, dataset)
        if payload.get("source_type") and payload["source_type"] not in {"upload", "google_drive", "demo", "api", "import"}:
            raise ValueError("Unsupported source_type.")
        meta = self.repository.upsert_metadata(dataset_id=dataset_id, user_id=user.id, **payload)
        self._audit_dataset_change(user, dataset, "dataset_metadata_updated", {"dataset_id": dataset_id})
        return self.dataset_detail(user, dataset_id)

    def tags(self, user: UserRecord, dataset_id: str) -> dict[str, Any]:
        self._require_dataset(user, dataset_id)
        return {"dataset_id": dataset_id, "tags": self.repository.list_tags([dataset_id]).get(dataset_id, [])}

    def add_tag(self, *, user: UserRecord, dataset_id: str, tag: str) -> dict[str, Any]:
        dataset = self._require_dataset(user, dataset_id)
        self._require_dataset_editor(user, dataset)
        normalized = _normalize_tag(tag)
        workspace_id = self._primary_workspace_for_dataset(user, dataset)
        tags = self.repository.add_tag(dataset_id=dataset_id, tag=normalized, user_id=user.id, workspace_id=workspace_id)
        self._audit_dataset_change(user, dataset, "dataset_tag_added", {"dataset_id": dataset_id, "tag": normalized})
        return {"dataset_id": dataset_id, "tags": tags}

    def remove_tag(self, *, user: UserRecord, dataset_id: str, tag: str) -> dict[str, Any]:
        dataset = self._require_dataset(user, dataset_id)
        self._require_dataset_editor(user, dataset)
        normalized = _normalize_tag(tag)
        self.repository.remove_tag(dataset_id, normalized)
        self._audit_dataset_change(user, dataset, "dataset_tag_removed", {"dataset_id": dataset_id, "tag": normalized})
        return self.tags(user, dataset_id)

    def set_favorite(self, *, user: UserRecord, resource_type: str, resource_id: str, workspace_id: str | None = None) -> None:
        self._require_resource_visible(user, resource_type, resource_id, workspace_id)
        self.repository.set_favorite(user_id=user.id, resource_type=resource_type, resource_id=resource_id, workspace_id=workspace_id)

    def remove_favorite(self, *, user: UserRecord, resource_type: str, resource_id: str) -> None:
        self.repository.remove_favorite(user_id=user.id, resource_type=resource_type, resource_id=resource_id)

    def recent_items(self, user: UserRecord, limit: int = 20) -> list[dict[str, Any]]:
        favorites = self.repository.favorite_ids(user.id)
        results = []
        for row in self.repository.list_recent(user.id, limit):
            try:
                self._require_resource_visible(user, row["resource_type"], row["resource_id"], row.get("workspace_id"))
            except Exception:
                continue
            results.append({
                "id": row["resource_id"],
                "type": row["resource_type"],
                "title": row["title"],
                "description": "Recently used",
                "workspace_id": row.get("workspace_id"),
                "updated_at": row["accessed_at"],
                "score": 0,
                "matched_fields": ["recent"],
                "favorite": (row["resource_type"], row["resource_id"]) in favorites,
                "metadata": {},
            })
        return results

    def record_recent(self, *, user: UserRecord, resource_type: str, resource_id: str, title: str, workspace_id: str | None = None) -> None:
        self._require_resource_visible(user, resource_type, resource_id, workspace_id)
        self.repository.record_recent(user_id=user.id, resource_type=resource_type, resource_id=resource_id, title=title, workspace_id=workspace_id)

    def search_history(self, user: UserRecord, limit: int = 20) -> list[dict[str, Any]]:
        return [
            {"id": row["id"], "query": row["search_query"], "workspace_id": row.get("workspace_id"), "created_at": row["created_at"]}
            for row in self.repository.list_search_history(user.id, limit)
        ]

    def clear_search_history(self, user: UserRecord) -> None:
        self.repository.clear_search_history(user.id)

    def _accessible_datasets(self, user: UserRecord) -> list[DatasetRecord]:
        return DatasetAccessService(self.registry, user, self.workspaces).list_accessible()

    def _require_dataset(self, user: UserRecord, dataset_id: str) -> DatasetRecord:
        try:
            return DatasetAccessService(self.registry, user, self.workspaces).require_dataset(dataset_id)
        except DatasetAccessError as error:
            raise SearchPermissionError("Dataset was not found.") from error

    def _require_dataset_editor(self, user: UserRecord, dataset: DatasetRecord) -> None:
        if dataset.is_builtin:
            raise SearchPermissionError("Built-in datasets cannot be modified.")
        if dataset.user_id == user.id:
            return
        for workspace in self.workspaces.list_workspaces_for_user(user.id):
            shared = self.workspaces.get_shared_dataset(workspace.id, dataset.dataset_id)
            member = self.workspaces.get_member(workspace.id, user.id)
            if shared and member and RolePermissions.can_manage_datasets(member.role):
                return
        raise SearchPermissionError("You do not have permission to edit this dataset metadata.")

    def _require_workspace(self, user: UserRecord, workspace_id: str) -> None:
        if self.workspaces.get_member(workspace_id, user.id) is None and not user.is_admin:
            raise SearchPermissionError("Workspace was not found.")

    def _require_resource_visible(self, user: UserRecord, resource_type: str, resource_id: str, workspace_id: str | None = None) -> None:
        if resource_type == "dataset":
            self._require_dataset(user, resource_id)
        elif resource_type == "workspace":
            self._require_workspace(user, resource_id)
        elif resource_type == "conversation":
            conv = self.chat.get_conversation(resource_id)
            if conv.workspace_id:
                self._require_workspace(user, conv.workspace_id)
            elif conv.user_id != user.id:
                raise SearchPermissionError("Resource was not found.")
        elif workspace_id:
            self._require_workspace(user, workspace_id)
        else:
            raise SearchPermissionError("Resource was not found.")

    def _dataset_and_column_results(self, user: UserRecord, tokens: list[str], filters: SearchFilters) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        datasets = [dataset for dataset in self._accessible_datasets(user) if self._dataset_filter(self._catalog_item(user, dataset, filters), filters)]
        dataset_ids = [dataset.dataset_id for dataset in datasets]
        metadata = self.repository.list_metadata(dataset_ids)
        tags = self.repository.list_tags(dataset_ids)
        favorites = self.repository.favorite_ids(user.id)
        dataset_results = []
        column_results = []
        for dataset in datasets:
            meta = metadata.get(dataset.dataset_id)
            tag_list = tags.get(dataset.dataset_id, [])
            score, matched = _score(tokens, {
                "name": dataset.dataset_name,
                "filename": dataset.original_filename,
                "description": meta.description if meta else "",
                "tags": " ".join(tag_list),
            })
            dataset_results.append(self._search_item(
                id=dataset.dataset_id,
                type="dataset",
                title=dataset.dataset_name,
                description=meta.description if meta else dataset.original_filename,
                updated_at=_iso(dataset.updated_at),
                score=score,
                matched_fields=matched,
                favorite=("dataset", dataset.dataset_id) in favorites,
                metadata={"rows": dataset.row_count, "columns": dataset.column_count, "tags": tag_list, "status": dataset.status},
            ))
            for column in self.registry.get_columns(dataset.dataset_id):
                c_score, c_matched = _score(tokens, {
                    "name": column.column_name,
                    "description": column.description or "",
                    "dataset": dataset.dataset_name,
                })
                column_results.append(self._search_item(
                    id=f"{dataset.dataset_id}:{column.column_name}",
                    type="column",
                    title=column.column_name,
                    description=column.description or f"{dataset.dataset_name} column",
                    dataset_id=dataset.dataset_id,
                    dataset_name=dataset.dataset_name,
                    updated_at=_iso(dataset.updated_at),
                    score=c_score,
                    matched_fields=c_matched,
                    favorite=("dataset", dataset.dataset_id) in favorites,
                    metadata={"data_type": column.data_type, "nullable": column.nullable},
                ))
        return dataset_results, column_results

    def _workspace_results(self, user: UserRecord, tokens: list[str], filters: SearchFilters) -> list[dict[str, Any]]:
        favorites = self.repository.favorite_ids(user.id)
        results = []
        for workspace in self.workspaces.list_workspaces_for_user(user.id):
            if filters.workspace_id and workspace.id != filters.workspace_id:
                continue
            score, matched = _score(tokens, {"name": workspace.name, "description": workspace.description or ""})
            results.append(self._search_item(
                id=workspace.id,
                type="workspace",
                title=workspace.name,
                description=workspace.description,
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                updated_at=_iso(workspace.updated_at),
                score=score,
                matched_fields=matched,
                favorite=("workspace", workspace.id) in favorites,
            ))
        return results

    def _conversation_results(self, user: UserRecord, tokens: list[str], filters: SearchFilters) -> list[dict[str, Any]]:
        favorites = self.repository.favorite_ids(user.id)
        conversations = list(self.chat.list_conversations(user.id, limit=200))
        for workspace in self.workspaces.list_workspaces_for_user(user.id):
            if filters.workspace_id and workspace.id != filters.workspace_id:
                continue
            conversations.extend(self.chat.list_workspace_conversations(workspace.id, limit=200))
        results = []
        for conv in conversations:
            if filters.workspace_id and conv.workspace_id != filters.workspace_id:
                continue
            score, matched = _score(tokens, {"title": conv.title, "dataset": conv.dataset_id or ""})
            results.append(self._search_item(
                id=conv.id,
                type="conversation",
                title=conv.title,
                description="Conversation",
                workspace_id=conv.workspace_id,
                dataset_id=conv.dataset_id,
                updated_at=_iso(conv.updated_at),
                score=score,
                matched_fields=matched,
                favorite=("conversation", conv.id) in favorites,
            ))
        return results

    def _saved_query_results(self, user: UserRecord, tokens: list[str], filters: SearchFilters) -> list[dict[str, Any]]:
        favorites = self.repository.favorite_ids(user.id)
        results = []
        for workspace in self.workspaces.list_workspaces_for_user(user.id):
            if filters.workspace_id and workspace.id != filters.workspace_id:
                continue
            for query in self.automation.list_saved_queries(workspace.id):
                score, matched = _score(tokens, {"title": query["title"], "question": query["question"], "dataset": query["dataset_id"]})
                results.append(self._search_item(
                    id=query["id"],
                    type="saved_query",
                    title=query["title"],
                    description=query["question"],
                    workspace_id=workspace.id,
                    workspace_name=workspace.name,
                    dataset_id=query["dataset_id"],
                    updated_at=query["updated_at"],
                    score=score,
                    matched_fields=matched,
                    favorite=("saved_query", query["id"]) in favorites,
                    metadata={"status": query.get("status")},
                ))
        return results

    def _analytics_result_results(self, user: UserRecord, tokens: list[str], filters: SearchFilters) -> list[dict[str, Any]]:
        favorites = self.repository.favorite_ids(user.id)
        results = []
        for workspace in self.workspaces.list_workspaces_for_user(user.id):
            if filters.workspace_id and workspace.id != filters.workspace_id:
                continue
            for result in self.workspaces.list_analysis_results(workspace.id, limit=200):
                score, matched = _score(tokens, {"question": result.question, "answer": result.answer, "dataset": result.dataset_id})
                results.append(self._search_item(
                    id=result.id,
                    type="analytics_result",
                    title=result.question,
                    description=result.answer[:240],
                    workspace_id=workspace.id,
                    workspace_name=workspace.name,
                    dataset_id=result.dataset_id,
                    updated_at=_iso(result.created_at),
                    score=score,
                    matched_fields=matched,
                    favorite=("analytics_result", result.id) in favorites,
                ))
        return results

    def _catalog_item(self, user: UserRecord, dataset: DatasetRecord, filters: SearchFilters) -> dict[str, Any]:
        metadata = self.repository.get_metadata(dataset.dataset_id)
        tags = self.repository.list_tags([dataset.dataset_id]).get(dataset.dataset_id, [])
        favorites = self.repository.favorite_ids(user.id, "dataset")
        workspace_ids = self._workspace_ids_for_dataset(user, dataset)
        file_format = (metadata.file_format if metadata else None) or _file_extension(dataset.original_filename)
        source_type = metadata.source_type if metadata else ("demo" if dataset.is_builtin else "upload")
        return {
            "dataset_id": dataset.dataset_id,
            "dataset_name": dataset.dataset_name,
            "filename": dataset.original_filename,
            "description": metadata.description if metadata else None,
            "owner_id": dataset.user_id,
            "workspace_ids": workspace_ids,
            "source_type": source_type,
            "file_format": file_format,
            "rows": dataset.row_count,
            "columns": dataset.column_count,
            "quality_score": metadata.quality_score if metadata else None,
            "status": dataset.status,
            "validation_status": dataset.validation_status,
            "version": metadata.version_label if metadata else "v1",
            "tags": tags,
            "favorite": ("dataset", dataset.dataset_id) in favorites,
            "is_builtin": dataset.is_builtin,
            "sharing_status": "shared" if workspace_ids else ("public_demo" if dataset.is_builtin else "private"),
            "created_at": _iso(dataset.created_at),
            "updated_at": _iso(dataset.updated_at),
            "last_analyzed_at": metadata.last_analyzed_at if metadata else None,
        }

    def _dataset_filter(self, item: dict[str, Any], filters: SearchFilters) -> bool:
        if filters.workspace_id and filters.workspace_id not in item.get("workspace_ids", []):
            return False
        if filters.file_type and (item.get("file_format") or "").lower() != filters.file_type.lower().lstrip("."):
            return False
        if filters.status and item.get("status") != filters.status:
            return False
        if filters.source_type and item.get("source_type") != filters.source_type:
            return False
        if filters.tags and not set(filters.tags).issubset(set(item.get("tags", []))):
            return False
        if filters.favorite is not None and bool(item.get("favorite")) != filters.favorite:
            return False
        if filters.shared is not None and (item.get("sharing_status") == "shared") != filters.shared:
            return False
        if filters.min_rows is not None and item.get("rows", 0) < filters.min_rows:
            return False
        if filters.max_rows is not None and item.get("rows", 0) > filters.max_rows:
            return False
        if filters.min_columns is not None and item.get("columns", 0) < filters.min_columns:
            return False
        if filters.max_columns is not None and item.get("columns", 0) > filters.max_columns:
            return False
        quality = item.get("quality_score")
        if filters.min_quality is not None and (quality is None or quality < filters.min_quality):
            return False
        if filters.max_quality is not None and (quality is None or quality > filters.max_quality):
            return False
        return True

    def _workspace_ids_for_dataset(self, user: UserRecord, dataset: DatasetRecord) -> list[str]:
        ids = []
        for workspace in self.workspaces.list_workspaces_for_user(user.id):
            if self.workspaces.get_shared_dataset(workspace.id, dataset.dataset_id):
                ids.append(workspace.id)
        return ids

    def _primary_workspace_for_dataset(self, user: UserRecord, dataset: DatasetRecord) -> str | None:
        ids = self._workspace_ids_for_dataset(user, dataset)
        return ids[0] if ids else None

    def _audit_dataset_change(self, user: UserRecord, dataset: DatasetRecord, event_type: str, metadata: dict[str, Any]) -> None:
        workspace_id = self._primary_workspace_for_dataset(user, dataset)
        if workspace_id:
            self.workspaces.log_activity(workspace_id, user.id, event_type, metadata)

    @staticmethod
    def _search_item(**kwargs: Any) -> dict[str, Any]:
        return {
            "description": None,
            "workspace_id": None,
            "workspace_name": None,
            "dataset_id": None,
            "dataset_name": None,
            "updated_at": None,
            "score": 0,
            "matched_fields": [],
            "favorite": False,
            "metadata": {},
            **kwargs,
        }

    @staticmethod
    def _sort_results(items: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
        if sort == "updated_asc":
            return sorted(items, key=lambda item: item.get("updated_at") or "")
        if sort == "name_asc":
            return sorted(items, key=lambda item: item["title"].lower())
        if sort == "name_desc":
            return sorted(items, key=lambda item: item["title"].lower(), reverse=True)
        return sorted(items, key=lambda item: (item.get("score", 0), item.get("updated_at") or ""), reverse=True)

    @staticmethod
    def _sort_catalog(items: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
        if sort == "created_desc":
            return sorted(items, key=lambda item: item["created_at"], reverse=True)
        if sort == "created_asc":
            return sorted(items, key=lambda item: item["created_at"])
        if sort == "name_asc":
            return sorted(items, key=lambda item: item["dataset_name"].lower())
        if sort == "name_desc":
            return sorted(items, key=lambda item: item["dataset_name"].lower(), reverse=True)
        if sort == "largest":
            return sorted(items, key=lambda item: item["rows"], reverse=True)
        if sort == "smallest":
            return sorted(items, key=lambda item: item["rows"])
        if sort == "quality_desc":
            return sorted(items, key=lambda item: item.get("quality_score") or -1, reverse=True)
        if sort == "quality_asc":
            return sorted(items, key=lambda item: item.get("quality_score") if item.get("quality_score") is not None else 101)
        if sort == "analyzed_desc":
            return sorted(items, key=lambda item: item.get("last_analyzed_at") or "", reverse=True)
        return sorted(items, key=lambda item: item.get("updated_at") or "", reverse=True)


def _tokens(query: str) -> list[str]:
    return [part for part in re.split(r"[^a-z0-9_]+", query.lower().strip()) if part]


def _score(tokens: list[str], fields: dict[str, str | None]) -> tuple[float, list[str]]:
    if not tokens:
        return 0, []
    score = 0.0
    matched: list[str] = []
    weights = {"name": 80, "title": 80, "filename": 45, "tags": 60, "description": 35, "question": 50, "answer": 20, "dataset": 25}
    for field, raw_value in fields.items():
        value = (raw_value or "").lower()
        if not value:
            continue
        all_found = True
        field_score = 0.0
        for token in tokens:
            if value == token:
                field_score += weights.get(field, 20) + 35
            elif value.startswith(token):
                field_score += weights.get(field, 20) + 15
            elif token in value:
                field_score += weights.get(field, 20)
            else:
                all_found = False
        if all_found:
            score += field_score
            matched.append(field)
    return score, matched


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique = []
    for item in items:
        key = (item["type"], item["id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _normalize_tag(tag: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", tag.strip().lower()).strip("-")
    if not normalized:
        raise ValueError("Tag must contain letters or numbers.")
    return normalized[:64]


def _file_extension(filename: str) -> str | None:
    if "." not in filename:
        return None
    return filename.rsplit(".", 1)[-1].lower()


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
