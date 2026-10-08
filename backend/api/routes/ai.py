import time
from fastapi import APIRouter, Depends

from backend.api.dependencies import get_ai_service, get_current_user, get_monitoring_service
from backend.core.user_model import UserRecord
from backend.exceptions.handlers import AppError
from backend.schemas.ai import AIAnalysisResponse, AIPlanResponse, AIQuestionRequest
from backend.services.ai_orchestration_service import AIOrchestrationService
from backend.services.gemini_service import AIConfigurationError, AIServiceError, UnsupportedQuestionError
from backend.services.monitoring_service import MonitoringService
from backend.services.rate_limiter import AIRateLimitError

router = APIRouter(prefix="/ai", tags=["ai"])


def _error(error: Exception) -> AppError:
    if isinstance(error, AIConfigurationError):
        return AppError(503, "ai_configuration_missing", "AI service is not configured.")
    if isinstance(error, AIRateLimitError):
        return AppError(429, "ai_rate_limit", str(error))
    if isinstance(error, UnsupportedQuestionError):
        return AppError(400, "unsupported_question", str(error))
    if isinstance(error, AIServiceError):
        return AppError(503, "ai_unavailable", str(error))
    return AppError(503, "analysis_unavailable", "The requested analysis could not be completed.")


@router.post("/plan", response_model=AIPlanResponse, summary="Convert a question into an approved analytics plan")
def plan(
    request: AIQuestionRequest,
    service: AIOrchestrationService = Depends(get_ai_service),
    current_user: UserRecord = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> AIPlanResponse:
    t0 = time.perf_counter()
    try:
        res = service.plan(request.question, dataset_id=request.dataset_id)
        duration_ms = (time.perf_counter() - t0) * 1000
        monitoring_service.log_ai_request(
            user_id=current_user.id,
            request_type="intent_generation",
            status="success",
            response_time_ms=duration_ms,
        )
        return res
    except Exception as error:
        duration_ms = (time.perf_counter() - t0) * 1000
        status_str = "invalid_intent" if isinstance(error, UnsupportedQuestionError) else "failed"
        monitoring_service.log_ai_request(
            user_id=current_user.id,
            request_type="intent_generation",
            status=status_str,
            response_time_ms=duration_ms,
            error_message=str(error),
        )
        raise _error(error) from error


@router.post("/analyze", response_model=AIAnalysisResponse, summary="Analyze a question using approved analytics and Gemini explanation")
def analyze(
    request: AIQuestionRequest,
    service: AIOrchestrationService = Depends(get_ai_service),
    current_user: UserRecord = Depends(get_current_user),
    monitoring_service: MonitoringService = Depends(get_monitoring_service),
) -> AIAnalysisResponse:
    t0 = time.perf_counter()
    monitoring_service.track_event(
        current_user.id,
        "analysis_started",
        {"dataset_id": request.dataset_id},
    )
    try:
        response = service.analyze(request.question, dataset_id=request.dataset_id)
        duration_ms = (time.perf_counter() - t0) * 1000

        if response.chart and response.chart.get("file_path"):
            chart = dict(response.chart)
            file_name = str(chart.pop("file_path")).replace("\\", "/").rsplit("/", 1)[-1]
            chart["file_url"] = f"/api/v1/visualizations/files/{file_name}"
            response = response.model_copy(update={"chart": chart})
            monitoring_service.track_event(current_user.id, "chart_generated", {"chart_type": response.chart.get("chart_type")})

        intent_val = getattr(response, "intent", None)
        analysis_type = intent_val.analysis_type if intent_val and hasattr(intent_val, "analysis_type") else (response.analysis.get("operation") if isinstance(response.analysis, dict) else "general")
        monitoring_service.track_event(
            current_user.id,
            "analysis_completed",
            {"dataset_id": request.dataset_id, "analysis_type": analysis_type},
        )
        monitoring_service.log_ai_request(
            user_id=current_user.id,
            request_type="result_explanation",
            status="success",
            response_time_ms=duration_ms,
        )
        return response
    except Exception as error:
        duration_ms = (time.perf_counter() - t0) * 1000
        monitoring_service.track_event(current_user.id, "analysis_failed", {"dataset_id": request.dataset_id})
        monitoring_service.log_ai_request(
            user_id=current_user.id,
            request_type="result_explanation",
            status="failed",
            response_time_ms=duration_ms,
            error_message=str(error),
        )
        raise _error(error) from error