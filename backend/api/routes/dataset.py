from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_dataset_service
from backend.exceptions.handlers import AppError
from backend.schemas.dataset import DatasetColumn, DatasetSample, DatasetSchema, DatasetSummary
from backend.services.dataset_service import DatasetService

router = APIRouter(prefix="/dataset", tags=["dataset"])


@router.get("/summary", response_model=DatasetSummary, summary="Get dataset summary")
def summary(service: DatasetService = Depends(get_dataset_service)) -> DatasetSummary:
    try:
        return DatasetSummary(**service.summary())
    except Exception as error:
        raise AppError(503, "dataset_unavailable", "The dataset could not be loaded.") from error


@router.get("/schema", response_model=DatasetSchema, summary="Get dataset schema")
def schema(service: DatasetService = Depends(get_dataset_service)) -> DatasetSchema:
    try:
        return DatasetSchema(**service.schema())
    except Exception as error:
        raise AppError(503, "dataset_unavailable", "The dataset schema could not be loaded.") from error


@router.get("/sample", response_model=DatasetSample, summary="Get a limited dataset sample")
def sample(limit: int = Query(5, ge=1, le=20), service: DatasetService = Depends(get_dataset_service)) -> DatasetSample:
    try:
        return DatasetSample(**service.sample(limit))
    except Exception as error:
        raise AppError(503, "dataset_unavailable", "The dataset sample could not be loaded.") from error