from typing import Any, Literal

from pydantic import Field

from .common import APIModel

AIChartType = Literal["bar", "line", "pie", "histogram", "scatter", "box"]
AIIntent = Literal["lookup", "comparison", "distribution", "relationship", "unsupported"]


class AnalyticsFilter(APIModel):
    field: str
    value: str


class AnalyticsPlan(APIModel):
    intent: AIIntent
    operation: str
    filters: list[AnalyticsFilter] = Field(default_factory=list)
    chart_type: AIChartType | None = None
    needs_chart: bool = False
from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID


class AIQuestionRequest(APIModel):
    question: str
    dataset_id: str = DEMO_PLACEMENT_DATASET_ID


class AIPlanResponse(APIModel):
    question: str
    plan: AnalyticsPlan


class AIAnalysisResponse(APIModel):
    question: str
    answer: str
    metrics: Any
    chart: dict[str, Any] | None = None
    insights: list[str]
    recommendations: list[str]
    warnings: list[str]
    analysis: dict[str, Any]


class ExplanationPayload(APIModel):
    answer: str
    insights: list[str]
    recommendations: list[str]
    warnings: list[str]