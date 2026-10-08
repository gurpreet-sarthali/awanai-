from datetime import UTC, datetime

import pytest

from backend.repositories.dataset_registry_repository import DatasetNotFoundError, DatasetRecord
from backend.services.dataset_access_service import DatasetAccessError, DatasetAccessService
from tests.test_helpers import RegistryStub, make_user


def _owned_dataset(dataset_id: str, user_id: str) -> DatasetRecord:
    now = datetime.now(UTC)
    return DatasetRecord(
        dataset_id=dataset_id,
        user_id=user_id,
        dataset_name="Sales",
        original_filename="sales.csv",
        internal_table_name="ds_abc123456789",
        storage_reference="ref",
        row_count=10,
        column_count=5,
        status="READY",
        is_builtin=False,
        validation_status="valid",
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def test_user_sees_only_own_datasets_plus_demo():
    registry = RegistryStub()
    user_a = make_user("user-a", "a@example.com")
    user_b = make_user("user-b", "b@example.com")
    registry.datasets["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"] = _owned_dataset("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", user_a.id)
    registry.datasets["bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"] = _owned_dataset("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", user_b.id)

    access_a = DatasetAccessService(registry, user_a)
    access_b = DatasetAccessService(registry, user_b)
    ids_a = {item.dataset_id for item in access_a.list_accessible()}
    ids_b = {item.dataset_id for item in access_b.list_accessible()}
    assert "demo-placement" in ids_a and "demo-placement" in ids_b
    assert "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in ids_a
    assert "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" not in ids_b
    assert "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" in ids_b
    assert "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" not in ids_a


def test_cross_user_dataset_access_returns_not_found():
    registry = RegistryStub()
    owner = make_user("user-a", "a@example.com")
    other = make_user("user-b", "b@example.com")
    dataset_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    registry.datasets[dataset_id] = _owned_dataset(dataset_id, owner.id)
    access = DatasetAccessService(registry, other)
    with pytest.raises(DatasetAccessError):
        access.require_dataset(dataset_id)
    with pytest.raises(DatasetNotFoundError):
        registry.get_dataset_for_user(dataset_id, other.id)
