"""Dataset access checks for authenticated users."""

from __future__ import annotations

from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID
from backend.core.user_model import UserRecord
from backend.repositories.dataset_registry_repository import DatasetNotFoundError, DatasetRecord, DatasetRegistryRepository
from backend.repositories.workspace_repository import WorkspaceRepository


class DatasetAccessError(LookupError):
    pass


class DatasetAccessService:
    def __init__(
        self,
        registry: DatasetRegistryRepository,
        user: UserRecord,
        workspace_repo: WorkspaceRepository | None = None,
    ) -> None:
        self.registry = registry
        self.user = user
        self.workspace_repo = workspace_repo

    def list_accessible(self) -> list[DatasetRecord]:
        own_datasets = self.registry.list_datasets_for_user(self.user.id)
        if not self.workspace_repo:
            return own_datasets

        # Include datasets shared with user's workspaces
        shared_records = []
        try:
            workspaces = self.workspace_repo.list_workspaces_for_user(self.user.id)
            seen_ids = {d.dataset_id for d in own_datasets}
            for ws in workspaces:
                shared = self.workspace_repo.list_shared_datasets(ws.id)
                for item in shared:
                    if item.dataset_id not in seen_ids:
                        try:
                            record = self.registry.get_dataset(item.dataset_id)
                            shared_records.append(record)
                            seen_ids.add(item.dataset_id)
                        except DatasetNotFoundError:
                            pass
        except Exception:
            pass

        return own_datasets + shared_records

    def require_dataset(self, dataset_id: str) -> DatasetRecord:
        try:
            record = self.registry.get_dataset(dataset_id)
        except DatasetNotFoundError as error:
            raise DatasetAccessError(str(error)) from error

        # 1. Check direct ownership or built-in
        if record.is_builtin or record.user_id == self.user.id:
            return record

        # 2. Check workspace sharing
        if self.workspace_repo and self.workspace_repo.is_dataset_shared_with_user_workspace(dataset_id, self.user.id):
            return record

        raise DatasetAccessError(f"Dataset `{dataset_id}` not found or permission denied.")

    def can_use_for_analytics(self, dataset_id: str) -> DatasetRecord:
        record = self.require_dataset(dataset_id)
        if record.status != "READY":
            raise DatasetAccessError(f"Dataset `{dataset_id}` is not ready for analytics.")
        return record
