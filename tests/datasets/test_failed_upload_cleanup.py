from pathlib import Path

import pytest

from backend.services.dataset_management_service import DatasetManagementError, DatasetManagementService
from tests.test_helpers import access_service


from unittest.mock import patch

def test_failed_import_marks_dataset_failed_and_cleans_storage(tmp_path):
    registry = _FakeRegistry()
    importer = _FailingImport()
    service = DatasetManagementService(registry, importer, tmp_path, access_service(registry))
    content = b"date,product,region,sales,profit\n2024-01-01,Widget,North,10,1\n"
    
    with patch("backend.services.google_drive_service.GoogleDriveService") as mock_drive:
        mock_instance = mock_drive.return_value
        mock_instance.upload_csv.return_value = {
            "google_drive_file_id": "fake_file_id",
            "google_drive_folder_id": "fake_folder_id",
            "file_size": len(content)
        }
        
        with pytest.raises(DatasetManagementError):
            service.upload_csv("sample.csv", content)
    record = registry.records["11111111-1111-1111-1111-111111111111"]
    assert record["status"] == "FAILED"
    assert not (tmp_path / "11111111-1111-1111-1111-111111111111").exists()
    assert importer.dropped is True


class _FailingImport:
    dropped = False

    def import_dataframe(self, table_name, dataframe, column_map):
        raise RuntimeError("simulated mysql failure")

    def drop_table_if_exists(self, table_name):
        self.dropped = True


class _FakeRegistry:
    def __init__(self):
        self.records = {}

    def generate_dataset_id(self):
        return "11111111-1111-1111-1111-111111111111"

    def generate_internal_table_name(self, dataset_id: str):
        return "ds_111111111111"

    def create_dataset(self, **kwargs):
        self.records[kwargs["dataset_id"]] = kwargs

    def update_dataset(self, dataset_id, **kwargs):
        self.records[dataset_id].update(kwargs)

    def replace_columns(self, dataset_id, columns):
        self.records[dataset_id]["columns"] = columns
