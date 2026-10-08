"""Upload, validate, clean, import, and manage user CSV datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from analytics.csv_dataset import CSVValidationError, clean_csv_dataframe, inspect_csv_dataframe, read_csv_bytes
from analytics.loader import PLACEMENT_TABLE, load_placement_data
from analytics.validation import validate_data
from backend.core.config import settings
from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID, is_valid_dataset_id
from backend.repositories.dataset_registry_repository import DatasetNotFoundError, DatasetRegistryRepository
from backend.services.dataset_access_service import DatasetAccessError, DatasetAccessService
from backend.services.dataset_import_service import DatasetImportError, DatasetImportService


class DatasetManagementError(ValueError):
    pass


class DatasetManagementService:
    def __init__(
        self,
        registry: DatasetRegistryRepository,
        import_service: DatasetImportService,
        uploads_root: Path,
        access: DatasetAccessService | None = None,
    ) -> None:
        self.registry = registry
        self.import_service = import_service
        self.uploads_root = uploads_root
        self.access = access
        self.uploads_root.mkdir(parents=True, exist_ok=True)

    def list_datasets(self) -> list[dict[str, Any]]:
        records = self.access.list_accessible() if self.access else self.registry.list_datasets()
        return [self._public_summary(record) for record in records]

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        record = self._require_ready_or_metadata(dataset_id)
        validation = self._validation_summary(dataset_id, record)
        return {
            "dataset_id": record.dataset_id,
            "dataset_name": record.dataset_name,
            "filename": record.original_filename,
            "rows": record.row_count,
            "columns": record.column_count,
            "status": record.status,
            "is_builtin": record.is_builtin,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "validation": validation,
        }

    def get_schema(self, dataset_id: str) -> dict[str, Any]:
        record = self._require_dataset(dataset_id)
        columns = self.registry.get_columns(dataset_id)
        return {
            "dataset_id": record.dataset_id,
            "dataset_name": record.dataset_name,
            "columns": [
                {
                    "column_name": column.column_name,
                    "original_column_name": column.original_column_name,
                    "data_type": column.data_type,
                    "nullable": column.nullable,
                    "description": column.description,
                    "position": column.position,
                }
                for column in columns
            ],
        }

    def preview(self, dataset_id: str, limit: int | None = None, repository: DatabaseRepository | None = None) -> dict[str, Any]:
        record = self._require_ready(dataset_id)
        preview_limit = limit or settings.dataset_preview_limit
        from backend.repositories.database_repository import DatabaseRepository

        repository = repository or DatabaseRepository(self.registry.config, registry=self.registry)
        rows = repository.sample(dataset_id, preview_limit)
        return {
            "dataset_id": record.dataset_id,
            "dataset_name": record.dataset_name,
            "limit": preview_limit,
            "rows": rows,
        }

    def delete_dataset(self, dataset_id: str) -> dict[str, Any]:
        if not is_valid_dataset_id(dataset_id):
            raise DatasetManagementError("Invalid dataset_id.")
            
        record = self._require_dataset(dataset_id)
        
        if self.access:
            deleted = self.registry.delete_dataset_for_user(dataset_id, self.access.user.id)
        else:
            deleted = self.registry.delete_dataset(dataset_id)
            
        if record.storage_reference and not record.is_builtin:
            if self.access and self.access.user.google_access_token:
                from backend.services.google_drive_service import GoogleDriveService, GoogleDriveError
                drive_service = GoogleDriveService(self.access.user.google_access_token)
                try:
                    drive_service.delete_file(record.storage_reference)
                except GoogleDriveError:
                    pass # Ignore if it's already deleted or access denied
                    
        return {"dataset_id": deleted.dataset_id, "status": "DELETED"}

    def upload_csv(self, filename: str, content: bytes, dataset_name: str | None = None) -> dict[str, Any]:
        self._validate_upload(filename, content)
        dataset_id = self.registry.generate_dataset_id()
        internal_table = self.registry.generate_internal_table_name(dataset_id)
        
        # Determine user and upload to Google Drive
        user_id = self.access.user.id if self.access else None
        if not user_id:
            raise DatasetManagementError("Authentication required for Google Drive upload.")
            
        from backend.services.google_drive_service import GoogleDriveService, GoogleDriveError
        access_token = self.access.user.google_access_token
        if not access_token:
            raise DatasetManagementError("Google account linkage is required to upload files.")
            
        drive_service = GoogleDriveService(access_token)
        try:
            drive_info = drive_service.upload_csv(filename, content)
        except GoogleDriveError as e:
            if e.status_code == 401:
                # Need to implement a way to refresh or just prompt user to re-login
                raise DatasetManagementError("Google Drive access token expired. Please log out and log in again with Google.") from e
            raise DatasetManagementError(f"Failed to upload to Google Drive: {e.message}") from e

        display_name = (dataset_name or Path(filename).stem or "Uploaded dataset").strip()[:255]
        self.registry.create_dataset(
            dataset_id=dataset_id,
            user_id=user_id,
            dataset_name=display_name,
            original_filename=Path(filename).name,
            internal_table_name=internal_table,
            storage_reference=drive_info["google_drive_file_id"],
            google_drive_folder_id=drive_info["google_drive_folder_id"],
            file_size=drive_info["file_size"],
            status="VALIDATING",
            validation_status="pending",
        )

        try:
            raw = read_csv_bytes(content)
            self._enforce_shape_limits(raw)
            inspection = inspect_csv_dataframe(raw)
            cleaned, cleaning_report = clean_csv_dataframe(raw)
            if cleaned.empty:
                raise CSVValidationError("The CSV has no usable rows after validation.")

            self.registry.update_dataset(dataset_id, status="PROCESSING")
            column_map = cleaning_report["columns_normalized"]
            column_map_pairs = [(item["original"], item["normalized"]) for item in column_map]
            import_result = self.import_service.import_dataframe(internal_table, cleaned, column_map_pairs)
            self.registry.replace_columns(dataset_id, import_result["columns"])
            self.registry.update_dataset(
                dataset_id,
                status="READY",
                row_count=import_result["row_count"],
                column_count=import_result["column_count"],
                validation_status="valid",
                error_message=None,
            )
            return {
                "dataset_id": dataset_id,
                "filename": Path(filename).name,
                "dataset_name": display_name,
                "rows": import_result["row_count"],
                "columns": import_result["column_count"],
                "missing_values": inspection["missing_values"],
                "duplicate_rows": inspection["duplicate_rows"],
                "cleaning": cleaning_report,
                "warnings": [*inspection["warnings"], *cleaning_report["warnings"]],
                "status": "READY",
            }
        except Exception as error:
            self.import_service.drop_table_if_exists(internal_table)
            message = str(error)
            self.registry.update_dataset(
                dataset_id,
                status="FAILED",
                validation_status="invalid",
                error_message=message[:2000],
            )
            try:
                drive_service.delete_file(drive_info["google_drive_file_id"])
            except Exception:
                pass
            if isinstance(error, (CSVValidationError, DatasetImportError, DatasetManagementError)):
                raise
            raise DatasetManagementError(message) from error

    def _validate_upload(self, filename: str, content: bytes) -> None:
        if not filename.lower().endswith(".csv"):
            raise DatasetManagementError("Only CSV uploads are supported.")
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise DatasetManagementError(f"File exceeds the configured upload limit of {settings.max_upload_size_mb} MB.")
        if not content.strip():
            raise DatasetManagementError("Uploaded file is empty.")

    def _enforce_shape_limits(self, dataframe: Any) -> None:
        if len(dataframe) > settings.max_csv_rows:
            raise DatasetManagementError(f"CSV exceeds the maximum allowed row count of {settings.max_csv_rows}.")
        if len(dataframe.columns) > settings.max_csv_columns:
            raise DatasetManagementError(f"CSV exceeds the maximum allowed column count of {settings.max_csv_columns}.")

    def _require_dataset(self, dataset_id: str):
        if self.access is None:
            return self.registry.get_dataset(dataset_id)
        try:
            return self.access.require_dataset(dataset_id)
        except DatasetAccessError as error:
            raise DatasetManagementError(str(error)) from error

    def _require_ready(self, dataset_id: str):
        if self.access is None:
            record = self.registry.get_dataset(dataset_id)
            if record.status != "READY":
                raise DatasetManagementError(f"Dataset '{dataset_id}' is not ready for analytics (status: {record.status}).")
            return record
        try:
            return self.access.can_use_for_analytics(dataset_id)
        except DatasetAccessError as error:
            raise DatasetManagementError(str(error)) from error

    def _require_ready_or_metadata(self, dataset_id: str):
        return self._require_dataset(dataset_id)

    def _validation_summary(self, dataset_id: str, record: Any) -> dict[str, Any]:
        if record.dataset_id == DEMO_PLACEMENT_DATASET_ID:
            try:
                dataframe = load_placement_data(self.registry.config)
                validation = validate_data(dataframe)
                return {
                    "validation_status": record.validation_status,
                    "missing_values": validation["missing_values"],
                    "warnings": validation["warnings"],
                }
            except Exception:
                return {"validation_status": record.validation_status, "warnings": []}
        return {
            "validation_status": record.validation_status,
            "error_message": record.error_message,
            "warnings": [],
        }

    def _public_summary(self, record: Any) -> dict[str, Any]:
        return {
            "dataset_id": record.dataset_id,
            "dataset_name": record.dataset_name,
            "filename": record.original_filename,
            "original_filename": record.original_filename,
            "row_count": record.row_count,
            "column_count": record.column_count,
            "status": record.status,
            "is_builtin": record.is_builtin,
            "created_at": record.created_at.isoformat(),
        }
