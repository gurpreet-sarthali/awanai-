"""Dataset-agnostic analytics helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd


def dataset_overview(dataframe: pd.DataFrame) -> dict[str, Any]:
    numeric_columns = [str(column) for column in dataframe.select_dtypes(include="number").columns]
    categorical_columns = [
        str(column)
        for column in dataframe.columns
        if column not in numeric_columns and dataframe[column].nunique(dropna=True) <= min(50, max(5, len(dataframe) // 10))
    ]
    return {
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "missing_values": {str(column): int(value) for column, value in dataframe.isna().sum().items() if int(value) > 0},
    }


def run_generic_operation(dataframe: pd.DataFrame, operation: str, column: str | None = None, group_by: str | None = None) -> Any:
    if operation == "overview":
        return dataset_overview(dataframe)
    if operation == "count":
        return int(len(dataframe))
    if operation in {"average", "minimum", "maximum", "sum"}:
        if not column or column not in dataframe.columns:
            raise ValueError("A valid numeric column is required for this operation.")
        numeric = pd.to_numeric(dataframe[column], errors="coerce")
        if operation == "average":
            value = numeric.mean(skipna=True)
        elif operation == "minimum":
            value = numeric.min(skipna=True)
        elif operation == "maximum":
            value = numeric.max(skipna=True)
        else:
            value = numeric.sum(skipna=True)
        return None if pd.isna(value) else float(value)
    if operation == "value_counts":
        if not column or column not in dataframe.columns:
            raise ValueError("A valid column is required for value_counts.")
        counts = dataframe[column].value_counts(dropna=False).head(25)
        return [{"group": str(index), "value": int(count)} for index, count in counts.items()]
    if operation == "group_average":
        if not column or not group_by:
            raise ValueError("Both column and group_by are required for group_average.")
        if column not in dataframe.columns or group_by not in dataframe.columns:
            raise ValueError("column and group_by must exist in the dataset.")
        grouped = dataframe.groupby(group_by, dropna=False)[column].mean(numeric_only=True)
        return [{"group": str(index), "value": None if pd.isna(value) else float(value)} for index, value in grouped.items()]
    raise ValueError(f"Unsupported generic operation: {operation}")
