from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryIntent(str, Enum):
    SELECT = "select_rows"
    COUNT = "count"
    AVERAGE = "average"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    SUM = "sum"
    PLACEMENT_RATE = "placement_rate"
    GROUP_BY = "group_by"
    FILTER = "filter"
    SORT = "sort"
    LIMIT = "limit"
    DISTINCT = "distinct"
    COMPARISON = "comparison"


class FilterOperator(str, Enum):
    EQUAL = "="
    NOT_EQUAL = "!="
    GREATER = ">"
    GREATER_EQUAL = ">="
    LESS = "<"
    LESS_EQUAL = "<="
    IN = "IN"


class QueryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str
    operator: FilterOperator
    value: Any


class SortSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str
    descending: bool = False


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: QueryIntent
    metric_column: str | None = None
    group_by: str | None = None
    select_columns: list[str] = Field(default_factory=list)
    filters: list[QueryFilter] = Field(default_factory=list)
    sort: SortSpec | None = None
    limit: int | None = Field(default=None, ge=1, le=1000)

    @field_validator("select_columns")
    @classmethod
    def unique_columns(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("select_columns must not contain duplicates")
        return value