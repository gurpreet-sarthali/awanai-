from typing import Any

from .common import APIModel
from backend.ai.nlsql.intent_schema import QueryPlan


from pydantic import Field

from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID


class NLQuestionRequest(APIModel):
    question: str
    dataset_id: str = Field(default=DEMO_PLACEMENT_DATASET_ID)


class NLPlanRequest(APIModel):
    plan: QueryPlan
    dataset_id: str = Field(default=DEMO_PLACEMENT_DATASET_ID)


class NLValidateResponse(APIModel):
    question: str | None = None
    plan: QueryPlan
    sql: str
    parameters: list[Any]
    read_only: bool
    row_query: bool


class NLExecuteResponse(APIModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    metadata: dict[str, Any]