"""Apply planner filters to a dataframe before analytics."""

from __future__ import annotations

from typing import Any

import pandas as pd


def apply_filters(dataframe: pd.DataFrame, filters: list[Any]) -> pd.DataFrame:
    if not filters:
        return dataframe
    result = dataframe.copy()
    for item in filters:
        field = getattr(item, "field", None) or (item.get("field") if isinstance(item, dict) else None)
        value = getattr(item, "value", None) if not isinstance(item, dict) else item.get("value")
        op = getattr(item, "op", "eq") if not isinstance(item, dict) else item.get("op", "eq")
        if not field or field not in result.columns:
            continue
        series = result[field]
        op = str(op or "eq").lower()
        if op == "eq":
            result = result[series.astype(str).str.strip() == str(value).strip()]
        elif op == "ne":
            result = result[series.astype(str).str.strip() != str(value).strip()]
        elif op == "contains":
            result = result[series.astype(str).str.contains(str(value), case=False, na=False)]
        elif op in {"gt", "gte", "lt", "lte"}:
            numeric = pd.to_numeric(series, errors="coerce")
            try:
                threshold = float(value)
            except (TypeError, ValueError):
                continue
            if op == "gt":
                result = result[numeric > threshold]
            elif op == "gte":
                result = result[numeric >= threshold]
            elif op == "lt":
                result = result[numeric < threshold]
            else:
                result = result[numeric <= threshold]
    return result
