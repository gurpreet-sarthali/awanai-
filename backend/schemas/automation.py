from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .common import APIModel


class SavedAnalyticsQueryCreate(APIModel):
    workspace_id: str = Field(min_length=1, max_length=64)
    dataset_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1, max_length=1000)
    config: dict[str, Any]


class AutomationCreate(APIModel):
    workspace_id: str = Field(min_length=1, max_length=64)
    saved_query_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    frequency: Literal["daily", "weekly", "monthly"]
    run_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(min_length=1, max_length=64)
    weekday: int = Field(default=0, ge=0, le=6)
    day_of_month: int = Field(default=1, ge=1, le=31)
    ai_summary: bool = False


class AutomationUpdate(APIModel):
    workspace_id: str = Field(min_length=1, max_length=64)
    active: bool | None = None
    saved_query_id: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    frequency: Literal["daily", "weekly", "monthly"] | None = None
    run_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    weekday: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    ai_summary: bool | None = None


class ActiveUpdate(APIModel):
    active: bool


class AlertCreate(APIModel):
    workspace_id: str = Field(min_length=1, max_length=64)
    dataset_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    alert_type: Literal["threshold", "anomaly"] = "threshold"
    metric: str = Field(min_length=1, max_length=128)
    operator: Literal[">", "<", ">=", "<=", "=", "!=", "percentage_change", "percentage_point_change"]
    threshold: float
    cooldown_seconds: int = Field(default=3600, ge=0, le=604800)