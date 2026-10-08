from typing import Any

from pydantic import Field

from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID
from .common import APIModel


class AnalyticsRequest(APIModel):
    operation: str
    dataset_id: str = Field(default=DEMO_PLACEMENT_DATASET_ID)
    column: str | None = None
    group_by: str | None = None


class AnalyticsResponse(APIModel):
    operation: str
    dataset_id: str = DEMO_PLACEMENT_DATASET_ID
    result: dict[str, Any] | list[Any] | float | int