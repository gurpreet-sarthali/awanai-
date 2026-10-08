from pydantic import Field

from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID
from .common import APIModel


class ChartRequest(APIModel):
    chart_type: str
    analysis_operation: str
    dataset_id: str = Field(default=DEMO_PLACEMENT_DATASET_ID)
    column: str | None = None
    group_by: str | None = None


class ChartResponse(APIModel):
    status: str
    chart_type: str
    title: str
    file_url: str
    metadata: dict[str, object]