import logging

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

logger = logging.getLogger(__name__)

from backend.api.dependencies import get_current_user, get_dataset_management_service, get_monitoring_service, get_repository
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.repositories.database_repository import DatabaseRepository
from backend.schemas.datasets import (
    DatasetDeleteResponse,
    DatasetUploadResponse,
    ManagedDatasetDetail,
    ManagedDatasetList,
    ManagedDatasetPreview,
    ManagedDatasetSchema,
    ManagedDatasetSummary,
)
from backend.services.dataset_management_service import DatasetManagementError, DatasetManagementService
from backend.services.monitoring_service import MonitoringService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/upload", response_model=DatasetUploadResponse, summary="Upload and register a CSV dataset")
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_name: str | None = Form(default=None),
    service: DatasetManagementService = Depends(get_dataset_management_service),
    current_user: UserRecord = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> DatasetUploadResponse:
    try:
        content = await file.read()
        result = service.upload_csv(file.filename or "upload.csv", content, dataset_name=dataset_name)
        monitoring_service.track_event(
            current_user.id,
            "dataset_uploaded",
            {"dataset_id": result.get("dataset_id"), "filename": file.filename},
        )
        return DatasetUploadResponse(**result)
    except DatasetManagementError as error:
        monitoring_service.track_event(current_user.id, "dataset_upload_failed", {"filename": file.filename})
        raise AppError(400, "invalid_dataset_upload", str(error)) from error
    except Exception as error:
        logger.error("UPLOAD EXCEPTION OCCURRED: %s", error, exc_info=True)
        monitoring_service.track_event(current_user.id, "dataset_upload_failed", {"filename": file.filename})
        raise AppError(503, "dataset_upload_failed", "The dataset could not be uploaded.") from error


@router.get("", response_model=ManagedDatasetList, summary="List available datasets")
def list_datasets(service: DatasetManagementService = Depends(get_dataset_management_service)) -> ManagedDatasetList:
    try:
        datasets = [ManagedDatasetSummary(**item) for item in service.list_datasets()]
        return ManagedDatasetList(datasets=datasets)
    except Exception as error:
        raise AppError(503, "datasets_unavailable", "Datasets could not be listed.") from error


@router.get("/{dataset_id}", response_model=ManagedDatasetDetail, summary="Get dataset details")
def get_dataset(dataset_id: str, service: DatasetManagementService = Depends(get_dataset_management_service)) -> ManagedDatasetDetail:
    try:
        return ManagedDatasetDetail(**service.get_dataset(dataset_id))
    except DatasetManagementError as error:
        raise AppError(404, "dataset_not_found", str(error)) from error
    except Exception as error:
        raise AppError(503, "dataset_unavailable", "The dataset could not be loaded.") from error


@router.get("/{dataset_id}/schema", response_model=ManagedDatasetSchema, summary="Get dataset schema")
def get_schema(dataset_id: str, service: DatasetManagementService = Depends(get_dataset_management_service)) -> ManagedDatasetSchema:
    try:
        return ManagedDatasetSchema(**service.get_schema(dataset_id))
    except DatasetManagementError as error:
        raise AppError(404, "dataset_not_found", str(error)) from error
    except Exception as error:
        raise AppError(503, "dataset_unavailable", "The dataset schema could not be loaded.") from error


@router.get("/{dataset_id}/preview", response_model=ManagedDatasetPreview, summary="Preview dataset rows")
def preview_dataset(
    dataset_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    service: DatasetManagementService = Depends(get_dataset_management_service),
    repository: DatabaseRepository = Depends(get_repository),
) -> ManagedDatasetPreview:
    try:
        return ManagedDatasetPreview(**service.preview(dataset_id, limit, repository=repository))
    except DatasetManagementError as error:
        raise AppError(404, "dataset_not_found", str(error)) from error
    except Exception as error:
        raise AppError(503, "dataset_unavailable", "The dataset preview could not be loaded.") from error


@router.delete("/{dataset_id}", response_model=DatasetDeleteResponse, summary="Delete an uploaded dataset")
def delete_dataset(
    dataset_id: str,
    service: DatasetManagementService = Depends(get_dataset_management_service),
    current_user: UserRecord = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> DatasetDeleteResponse:
    try:
        res = service.delete_dataset(dataset_id)
        monitoring_service.track_event(current_user.id, "dataset_deleted", {"dataset_id": dataset_id})
        return DatasetDeleteResponse(**res)
    except DatasetManagementError as error:
        raise AppError(400, "dataset_delete_failed", str(error)) from error
    except Exception as error:
        raise AppError(503, "dataset_unavailable", "The dataset could not be deleted.") from error
