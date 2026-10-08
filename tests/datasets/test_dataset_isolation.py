import pandas as pd
import pytest

from backend.core.dataset_constants import is_valid_dataset_id
from backend.repositories.dataset_registry_repository import DatasetNotFoundError
from backend.services.analytics_service import AnalyticsService, InvalidAnalyticsOperation


class IsolationRepository:
    def __init__(self) -> None:
        self.frames = {
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa": pd.DataFrame({"region": ["North", "South"], "sales": [100.0, 200.0]}),
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb": pd.DataFrame({"region": ["East"], "sales": [999.0]}),
        }

    def resolve_table(self, dataset_id: str):
        frame = self.frames[dataset_id]
        return f"ds_{dataset_id[:12].replace('-', '')}", list(frame.columns)

    def load_dataframe(self, dataset_id: str):
        if not is_valid_dataset_id(dataset_id) or dataset_id not in self.frames:
            raise DatasetNotFoundError(f"Invalid dataset_id: {dataset_id}")
        return self.frames[dataset_id].copy()


def test_same_operation_returns_dataset_specific_results():
    repository = IsolationRepository()
    service = AnalyticsService(repository)
    result_a = service.run_operation("average", dataset_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", column="sales")
    result_b = service.run_operation("average", dataset_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", column="sales")
    assert result_a == 150.0
    assert result_b == 999.0


def test_invalid_dataset_id_rejected():
    repository = IsolationRepository()
    service = AnalyticsService(repository)
    with pytest.raises(InvalidAnalyticsOperation, match="Invalid dataset_id"):
        service.run_operation("count", dataset_id="not-a-valid-id")
