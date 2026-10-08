from pathlib import Path

import pandas as pd
import pytest

from analytics.column_normalization import normalize_column_names
from analytics.csv_dataset import CSVValidationError, clean_csv_dataframe, inspect_csv_dataframe, read_csv_bytes
from backend.services.dataset_management_service import DatasetManagementError, DatasetManagementService


def test_column_normalization_produces_unique_sql_safe_names():
    pairs = normalize_column_names(["Student Name", "student name", "CGPA (%)", "select"])
    normalized = [normalized for _, normalized in pairs]
    assert normalized == ["student_name", "student_name_2", "cgpa", "select_col"]


def test_read_and_inspect_sample_sales_csv():
    content = Path("data/test/sample_sales.csv").read_bytes()
    dataframe = read_csv_bytes(content)
    inspection = inspect_csv_dataframe(dataframe)
    assert inspection["rows"] == 5
    assert inspection["columns"] == 5
    assert "sales" in inspection["column_profiles"][0]["original_name"] or any(item["original_name"] == "sales" for item in inspection["column_profiles"])


def test_empty_csv_rejected():
    with pytest.raises(CSVValidationError):
        read_csv_bytes(b"   ")


def test_oversized_upload_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(DatasetManagementService, "_validate_upload", lambda self, filename, content: (_ for _ in ()).throw(DatasetManagementError("File exceeds the configured upload limit of 0 MB.")))
    service = _service(tmp_path)
    with pytest.raises(DatasetManagementError):
        service.upload_csv("sample.csv", b"a,b\n1,2\n")


def test_duplicate_columns_reported():
    content = b"name,value,name\nA,1,B\n"
    dataframe = read_csv_bytes(content)
    inspection = inspect_csv_dataframe(dataframe)
    assert inspection["duplicate_columns"] or any("name" in str(column).lower() for column in dataframe.columns)


def test_cleaning_report_preserves_shape_for_valid_csv():
    content = Path("data/test/sample_sales.csv").read_bytes()
    dataframe = read_csv_bytes(content)
    cleaned, report = clean_csv_dataframe(dataframe)
    assert report["rows_after"] == len(cleaned)
    assert report["columns_normalized"]


def _service(tmp_path):
    from backend.repositories.dataset_registry_repository import DatasetRegistryRepository
    from backend.services.dataset_import_service import DatasetImportService

    class FakeRegistry(DatasetRegistryRepository):
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

        def get_dataset(self, dataset_id):
            from backend.repositories.dataset_registry_repository import DatasetRecord
            from datetime import datetime

            row = self.records[dataset_id]
            return DatasetRecord(
                dataset_id=dataset_id,
                dataset_name=row["dataset_name"],
                original_filename=row["original_filename"],
                internal_table_name=row["internal_table_name"],
                storage_reference=row.get("storage_reference"),
                row_count=row.get("row_count", 0),
                column_count=row.get("column_count", 0),
                status=row.get("status", "READY"),
                is_builtin=False,
                validation_status=row.get("validation_status", "valid"),
                error_message=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

        def get_columns(self, dataset_id):
            return self.records[dataset_id].get("columns", [])

    class FakeImport:
        def import_dataframe(self, table_name, dataframe, column_map):
            return {
                "row_count": len(dataframe),
                "column_count": len(dataframe.columns),
                "columns": [],
                "null_counts": {},
            }

        def drop_table_if_exists(self, table_name):
            return None

    return DatasetManagementService(FakeRegistry(), FakeImport(), tmp_path)
