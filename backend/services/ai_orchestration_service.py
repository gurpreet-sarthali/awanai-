"""Question-to-plan-to-explanation orchestration for Phase 7."""

from __future__ import annotations

from typing import Any

from analytics.validation import validate_data
from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID
from backend.repositories.database_repository import DatabaseRepository
from backend.schemas.ai import AIAnalysisResponse, AIPlanResponse

from .analytics_service import AnalyticsService
from .gemini_service import GeminiService, schema_context_from_dataframe
from .rate_limiter import AIRateLimiter
from .dataset_access_service import DatasetAccessService
from .visualization_service import VisualizationService


class AIOrchestrationService:
    def __init__(
        self,
        repository: DatabaseRepository,
        analytics_service: AnalyticsService,
        visualization_service: VisualizationService,
        gemini_service: GeminiService,
        rate_limiter: AIRateLimiter,
        dataset_access: DatasetAccessService | None = None,
    ) -> None:
        self.repository = repository
        self.analytics_service = analytics_service
        self.visualization_service = visualization_service
        self.gemini_service = gemini_service
        self.rate_limiter = rate_limiter
        self.dataset_access = dataset_access

    def _ensure_dataset(self, dataset_id: str) -> None:
        if self.dataset_access is not None:
            self.dataset_access.can_use_for_analytics(dataset_id)

    def plan(self, question: str, dataset_id: str = DEMO_PLACEMENT_DATASET_ID, user_id: str | None = None) -> AIPlanResponse:
        self._ensure_dataset(dataset_id)
        dataframe = self.repository.load_dataframe(dataset_id)
        self.rate_limiter.check(user_id=user_id)
        plan = self.gemini_service.plan(question, schema_context_from_dataframe(dataframe))
        return AIPlanResponse(question=question, plan=plan)

    def analyze(self, question: str, dataset_id: str = DEMO_PLACEMENT_DATASET_ID, user_id: str | None = None) -> AIAnalysisResponse:
        self._ensure_dataset(dataset_id)
        dataframe = self.repository.load_dataframe(dataset_id)
        validation = validate_data(dataframe) if dataset_id == DEMO_PLACEMENT_DATASET_ID else {"warnings": []}
        schema_context = schema_context_from_dataframe(dataframe)
        self.rate_limiter.check(user_id=user_id)
        plan = self.gemini_service.plan(question, schema_context)
        actual_result = self.analytics_service.run_operation(plan.operation, dataset_id=dataset_id)
        warnings = list(validation["warnings"])
        warnings.append("This analysis shows observed association and does not establish causation.")

        chart: dict[str, Any] | None = None
        if plan.needs_chart:
            if not plan.chart_type:
                raise ValueError("Gemini requested a chart without selecting a chart type.")
            chart = self.visualization_service.generate(plan.chart_type, plan.operation, dataset_id=dataset_id)

        self.rate_limiter.check(user_id=user_id)
        explanation = self.gemini_service.explain(question, plan.operation, actual_result, warnings)
        merged_warnings = list(dict.fromkeys([*warnings, *explanation.warnings]))
        return AIAnalysisResponse(
            question=question,
            answer=explanation.answer,
            metrics=actual_result,
            chart=chart,
            insights=explanation.insights,
            recommendations=explanation.recommendations,
            warnings=merged_warnings,
            analysis={
                "operation": plan.operation,
                "filters": [filter_item.model_dump() for filter_item in plan.filters],
                "chart_type": plan.chart_type,
                "needs_chart": plan.needs_chart,
            },
        )