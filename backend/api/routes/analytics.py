from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_analytics_service
from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID
from backend.exceptions.handlers import AppError
from backend.schemas.analytics import AnalyticsRequest, AnalyticsResponse
from backend.services.analytics_service import AnalyticsService, InvalidAnalyticsOperation

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _run(
    service: AnalyticsService,
    operation: str,
    *,
    dataset_id: str = DEMO_PLACEMENT_DATASET_ID,
    column: str | None = None,
    group_by: str | None = None,
) -> AnalyticsResponse:
    try:
        result = service.run_operation(operation, dataset_id=dataset_id, column=column, group_by=group_by)
        return AnalyticsResponse(operation=operation, dataset_id=dataset_id, result=result)
    except InvalidAnalyticsOperation as error:
        raise AppError(400, "invalid_operation", str(error)) from error
    except Exception as error:
        raise AppError(503, "analytics_unavailable", "Analytics could not be calculated.") from error


@router.get("/summary", response_model=AnalyticsResponse, summary="Get core analytics summary")
def summary(
    dataset_id: str = Query(default=DEMO_PLACEMENT_DATASET_ID),
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsResponse:
    try:
        return AnalyticsResponse(operation="summary", dataset_id=dataset_id, result=service.summary(dataset_id))
    except Exception as error:
        raise AppError(503, "analytics_unavailable", "Analytics could not be calculated.") from error


@router.get("/placement", response_model=AnalyticsResponse, summary="Get placement analytics")
def placement(
    dataset_id: str = Query(default=DEMO_PLACEMENT_DATASET_ID),
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsResponse:
    try:
        return AnalyticsResponse(operation="placement", dataset_id=dataset_id, result=service.placement(dataset_id))
    except Exception as error:
        raise AppError(503, "analytics_unavailable", "Analytics could not be calculated.") from error


@router.get("/internship", response_model=AnalyticsResponse, summary="Get internship analytics")
def internship(
    dataset_id: str = Query(default=DEMO_PLACEMENT_DATASET_ID),
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsResponse:
    try:
        return AnalyticsResponse(operation="placement_by_internship", dataset_id=dataset_id, result=service.internship(dataset_id))
    except Exception as error:
        raise AppError(503, "analytics_unavailable", "Analytics could not be calculated.") from error


@router.get("/cgpa", response_model=AnalyticsResponse, summary="Get CGPA-group analytics")
def cgpa(dataset_id: str = Query(default=DEMO_PLACEMENT_DATASET_ID), service: AnalyticsService = Depends(get_analytics_service)) -> AnalyticsResponse:
    return _run(service, "placement_by_cgpa_group", dataset_id=dataset_id)


@router.get("/projects", response_model=AnalyticsResponse, summary="Get project-group analytics")
def projects(dataset_id: str = Query(default=DEMO_PLACEMENT_DATASET_ID), service: AnalyticsService = Depends(get_analytics_service)) -> AnalyticsResponse:
    return _run(service, "placement_by_project_group", dataset_id=dataset_id)


@router.get("/communication", response_model=AnalyticsResponse, summary="Get communication-score analytics")
def communication(dataset_id: str = Query(default=DEMO_PLACEMENT_DATASET_ID), service: AnalyticsService = Depends(get_analytics_service)) -> AnalyticsResponse:
    return _run(service, "placement_by_communication", dataset_id=dataset_id)


@router.post("/run", response_model=AnalyticsResponse, summary="Run an approved analytics operation")
def run(request: AnalyticsRequest, service: AnalyticsService = Depends(get_analytics_service)) -> AnalyticsResponse:
    return _run(service, request.operation, dataset_id=request.dataset_id, column=request.column, group_by=request.group_by)