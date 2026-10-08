"""Machine-readable output helpers for the future analytics-plan layer."""

from __future__ import annotations

from typing import Any


def metric_result(metric: str, value: Any, unit: str | None = None) -> dict[str, Any]:
    result = {"metric": metric, "value": value}
    if unit is not None:
        result["unit"] = unit
    return result


def grouped_result(metric: str, group_by: str, results: list[dict[str, Any]], unit: str | None = None) -> dict[str, Any]:
    result = {"metric": metric, "group_by": group_by, "results": results}
    if unit is not None:
        result["unit"] = unit
    return result