"""Validation shared by all chart generators."""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd

SUPPORTED_CHART_TYPES = {"bar", "line", "pie", "histogram", "scatter", "box"}


def validate_chart_data(
    dataframe: pd.DataFrame,
    *,
    required_columns: Iterable[str],
    numeric_columns: Iterable[str] = (),
    max_categories: int | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if dataframe is None or not isinstance(dataframe, pd.DataFrame):
        return {"valid": False, "errors": ["Data must be a Pandas DataFrame."], "warnings": []}
    if dataframe.empty:
        errors.append("DataFrame is empty.")
    missing = [column for column in required_columns if column not in dataframe.columns]
    if missing:
        errors.append(f"Missing required column(s): {', '.join(missing)}")
    for column in numeric_columns:
        if column in dataframe and not pd.api.types.is_numeric_dtype(dataframe[column]):
            errors.append(f"Column '{column}' must be numeric.")
    if max_categories is not None and len(dataframe.iloc[:, 0].dropna().unique()) > max_categories:
        errors.append(f"Too many categories for this chart: maximum is {max_categories}.")
    if len(dataframe) > 100_000:
        warnings.append("Large dataset may produce a slow or dense chart.")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def validate_chart_spec(spec: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    chart_type = spec.get("chart_type") if isinstance(spec, dict) else None
    if chart_type not in SUPPORTED_CHART_TYPES:
        errors.append(f"Unsupported chart type: {chart_type!r}.")
    if not isinstance(spec, dict) or not spec.get("title"):
        errors.append("Chart specification requires a title.")
    if chart_type in {"bar", "line", "scatter", "box"} and not spec.get("x"):
        errors.append(f"{chart_type} chart specification requires an x field.")
    if chart_type in {"bar", "line", "scatter", "box", "histogram"} and not spec.get("y"):
        errors.append(f"{chart_type} chart specification requires a y field.")
    return {"valid": not errors, "errors": errors, "warnings": []}