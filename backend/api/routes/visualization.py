from pathlib import Path

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_visualization_service
from backend.exceptions.handlers import AppError
from backend.schemas.visualization import ChartRequest, ChartResponse
from backend.services.visualization_service import VisualizationService

router = APIRouter(prefix="/visualizations", tags=["visualizations"])


@router.post("/generate", response_model=ChartResponse, summary="Generate an approved chart")
def generate(request: ChartRequest, service: VisualizationService = Depends(get_visualization_service)) -> ChartResponse:
    try:
        result = service.generate(
            request.chart_type,
            request.analysis_operation,
            dataset_id=request.dataset_id,
            column=request.column,
            group_by=request.group_by,
        )
    except ValueError as error:
        raise AppError(400, "invalid_visualization_request", str(error)) from error
    except Exception as error:
        raise AppError(503, "visualization_unavailable", "The visualization could not be generated.") from error
    file_name = Path(str(result["file_path"])).name
    metadata = {key: value for key, value in result.items() if key not in {"success", "file_path", "title", "chart_type"}}
    return ChartResponse(status="success", chart_type=str(result["chart_type"]), title=str(result["title"]), file_url=f"/api/v1/visualizations/files/{file_name}", metadata=metadata)