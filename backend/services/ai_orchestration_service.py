"""Question-to-plan-to-explanation orchestration."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

# Operations that work directly on the dataframe without placement constraints
_DATA_OPS = {
    "data_quality_report",
    "impute_missing_values",
    "correlation",
    "trend",
    "overview",
    "count",
    "average",
    "minimum",
    "maximum",
    "sum",
    "value_counts",
    "group_average",
    "median",
    "describe",
    "summary",
}


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

        # Rate limit check before AI call
        self.rate_limiter.check(user_id=user_id)
        plan = self.gemini_service.plan(question, schema_context)

        if plan.answer_mode == "general" or plan.operation == "general_answer":
            self.rate_limiter.check(user_id=user_id)
            explanation = self.gemini_service.general_answer(question)
            return AIAnalysisResponse(
                question=question,
                answer=explanation.answer,
                metrics={"mode": "general_answer"},
                chart=None,
                insights=explanation.insights,
                recommendations=explanation.recommendations,
                warnings=explanation.warnings,
                analysis={
                    "operation": "general_answer",
                    "answer_mode": "general",
                    "filters": [],
                    "chart_type": None,
                    "needs_chart": False,
                },
            )

        column = getattr(plan, "column", None)
        group_by = getattr(plan, "group_by", None)
        numeric_param = getattr(plan, "numeric_param", None)
        pandas_script = getattr(plan, "pandas_script", None)
        if not column and plan.filters:
            column = plan.filters[0].field

        # Execute the analytics operation
        actual_result = self.analytics_service.run_operation(
            plan.operation,
            dataset_id=dataset_id,
            column=column,
            group_by=group_by,
            numeric_param=numeric_param,
            pandas_script=pandas_script,
            filters=plan.filters,
        )

        warnings = list(validation.get("warnings", []))
        if plan.operation != "custom_analytics":
            warnings.append("This analysis shows observed association and does not establish causation.")

        # Generate chart only when requested AND operation supports it
        chart: dict[str, Any] | None = None
        chart_supported_ops = {
            "average", "minimum", "maximum", "sum", "value_counts",
            "group_average", "trend", "correlation", "custom_analytics",
            "overall_placement_rate", "placement_by_internship",
            "placement_by_cgpa_group", "placement_by_project_group",
            "placement_by_communication", "average_metrics_by_placement",
        }
        if plan.needs_chart and plan.operation in chart_supported_ops:
            if not plan.chart_type:
                warnings.append("No chart type was specified; skipping chart generation.")
            else:
                try:
                    chart = self.visualization_service.generate(
                        plan.chart_type,
                        plan.operation,
                        dataset_id=dataset_id,
                        column=column,
                        group_by=group_by,
                    )
                except Exception as chart_err:
                    logger.warning("chart_generation_failed op=%s err=%s", plan.operation, chart_err)
                    warnings.append(f"Chart could not be generated: {chart_err}")

        # Rate limit check before second AI call
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