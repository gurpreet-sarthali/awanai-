from datetime import UTC, datetime

from backend.core.user_model import UserRecord
from backend.repositories.dataset_registry_repository import DatasetNotFoundError, DatasetRecord
from backend.services.dataset_access_service import DatasetAccessService


def make_user(user_id: str = "test-user-0000-0000-0000-000000000001", email: str = "tester@example.com") -> UserRecord:
    now = datetime.now(UTC)
    return UserRecord(
        id=user_id,
        email=email,
        name="Test User",
        password_hash="hashed",
        google_id="google-id-123",
        google_access_token="fake-google-token",
        google_refresh_token="fake-google-refresh",
        profile_picture_url=None,
        is_active=True,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )


class RegistryStub:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.datasets: dict[str, DatasetRecord] = {
            "demo-placement": DatasetRecord(
                dataset_id="demo-placement",
                user_id=None,
                dataset_name="Demo Placement Dataset",
                original_filename="placement.csv",
                internal_table_name="placement",
                storage_reference=None,
                row_count=4,
                column_count=10,
                status="READY",
                is_builtin=True,
                validation_status="valid",
                error_message=None,
                created_at=now,
                updated_at=now,
            )
        }

    def list_datasets_for_user(self, user_id: str, include_deleted: bool = False):
        return [record for record in self.datasets.values() if record.is_builtin or record.user_id == user_id]

    def get_dataset(self, dataset_id: str) -> DatasetRecord:
        if dataset_id not in self.datasets:
            raise DatasetNotFoundError(dataset_id)
        return self.datasets[dataset_id]

    def get_dataset_for_user(self, dataset_id: str, user_id: str) -> DatasetRecord:
        record = self.get_dataset(dataset_id)
        if record.is_builtin and record.user_id is None:
            return record
        if record.user_id != user_id:
            raise DatasetNotFoundError(dataset_id)
        return record

    def get_columns(self, dataset_id: str):
        return []

    def delete_dataset_for_user(self, dataset_id: str, user_id: str) -> DatasetRecord:
        record = self.get_dataset_for_user(dataset_id, user_id)
        del self.datasets[dataset_id]
        return record


def access_service(registry: RegistryStub, user: UserRecord | None = None) -> DatasetAccessService:
    return DatasetAccessService(registry, user or make_user())
