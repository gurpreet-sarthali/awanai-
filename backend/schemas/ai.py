from typing import Any, Literal

from pydantic import Field

from .common import APIModel

AIChartType = Literal["bar", "line", "pie", "histogram", "scatter", "box"]
AIIntent = Literal["lookup", "comparison", "distribution", "relationship", "unsupported"]


FilterOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains"]
AnswerMode = Literal["dataset", "general"]


class AnalyticsFilter(APIModel):
    field: str
    value: str
    op: FilterOp = "eq"


class AnalyticsPlan(APIModel):
    intent: AIIntent
    operation: str
    answer_mode: AnswerMode = "dataset"
    column: str | None = None
    group_by: str | None = None
    numeric_param: float | None = None
    filters: list[AnalyticsFilter] = Field(default_factory=list)
    chart_type: AIChartType | None = None
    needs_chart: bool = False
    pandas_script: str | None = None


class AnalystCodePlan(APIModel):
    intent: Literal["custom_code", "data_quality", "impute_missing", "unsupported"]
    code: str | None = None
    needs_chart: bool = False
    chart_type: AIChartType | None = None
    chart_x: str | None = None
    chart_y: str | None = None
    chart_title: str | None = None
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