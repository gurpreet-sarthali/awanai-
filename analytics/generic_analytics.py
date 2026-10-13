"""Dataset-agnostic analytics helpers."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from analytics.data_quality import profile_and_score_dataset
from analytics.safe_pandas import UnsafeAnalyticsScript, run_pandas_script


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


def data_quality_report(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Full data quality report with missing values, completeness, score etc."""
    report = profile_and_score_dataset(dataframe)
    # Build a simpler summary for the AI explainer
    total_cells = report["total_rows"] * report["total_columns"]
    missing_pct = round((report["total_missing_cells"] / max(1, total_cells)) * 100, 1)
    col_missing = [
        {"column": p["column_name"], "missing": p["null_count"], "pct": p["null_percentage"]}
        for p in report["column_profiles"]
        if p["null_count"] > 0
    ]
    return {
        "quality_score": report["quality_score"],
        "total_rows": report["total_rows"],
        "total_columns": report["total_columns"],
        "total_missing_cells": report["total_missing_cells"],
        "missing_percentage": missing_pct,
        "duplicate_rows": report["duplicate_rows"],
        "columns_with_missing": col_missing,
        "completeness": report["breakdown"]["completeness"],
        "uniqueness": report["breakdown"]["uniqueness"],
        "consistency": report["breakdown"]["consistency"],
        "validity": report["breakdown"]["validity"],
    }


def impute_missing_values(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Report missing values per column and suggest imputation strategy."""
    result = []
    for col in dataframe.columns:
        series = dataframe[col]
        null_count = int(series.isna().sum())
        if null_count == 0:
            continue
        null_pct = round((null_count / len(dataframe)) * 100, 1)
        non_null = series.dropna()
        col_type = str(series.dtype)
        strategy = "N/A"
        fill_value = None
        if col_type.startswith(("int", "float")) or col_type == "number":
            mean_val = round(float(pd.to_numeric(non_null, errors="coerce").mean()), 3)
            median_val = round(float(pd.to_numeric(non_null, errors="coerce").median()), 3)
            strategy = "mean or median imputation"
            fill_value = {"mean": mean_val, "median": median_val}
        elif col_type in ("object", "category", "string"):
            try:
                mode_val = str(non_null.mode().iloc[0]) if not non_null.empty else None
                strategy = "mode imputation"
                fill_value = {"mode": mode_val}
            except Exception:
                strategy = "constant imputation"
                fill_value = {"constant": "Unknown"}
        result.append({
            "column": col,
            "missing_count": null_count,
            "missing_pct": null_pct,
            "recommended_strategy": strategy,
            "suggested_fill": fill_value,
        })
    total_missing = sum(r["missing_count"] for r in result)
    return {
        "total_missing_cells": total_missing,
        "columns_analyzed": len(dataframe.columns),
        "columns_with_missing": len(result),
        "imputation_plan": result,
    }


def correlation_analysis(dataframe: pd.DataFrame, column: str | None = None) -> dict[str, Any]:
    """Compute Pearson correlation matrix or correlations for one column."""
    numeric_df = dataframe.select_dtypes(include="number")
    if numeric_df.shape[1] < 2:
        return {"error": "Need at least 2 numeric columns to compute correlations."}
    corr_matrix = numeric_df.corr(numeric_only=True).round(3)
    if column and column in corr_matrix.columns:
        col_corr = corr_matrix[column].drop(labels=[column]).to_dict()
        top = sorted(col_corr.items(), key=lambda x: abs(x[1]) if x[1] is not None else 0, reverse=True)
        return {
            "target_column": column,
            "correlations": [{"column": k, "correlation": round(v, 3)} for k, v in top if v is not None],
        }
    # Return all pairs flattened
    pairs = []
    cols = list(corr_matrix.columns)
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1 :]:
            val = corr_matrix.loc[c1, c2]
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                pairs.append({"col1": c1, "col2": c2, "correlation": round(float(val), 3)})
    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return {"correlation_pairs": pairs[:20], "numeric_columns": cols}


def trend_analysis(dataframe: pd.DataFrame, column: str | None = None, group_by: str | None = None) -> dict[str, Any]:
    """Calculate trend / distribution of a numeric column over a categorical grouping."""
    if not column or column not in dataframe.columns:
        # Fall back to overview
        return dataset_overview(dataframe)
    numeric = pd.to_numeric(dataframe[column], errors="coerce")
    if group_by and group_by in dataframe.columns:
        grouped = dataframe.groupby(group_by)[column].apply(lambda s: pd.to_numeric(s, errors="coerce").mean())
        return {
            "column": column,
            "group_by": group_by,
            "trend": [{"group": str(k), "mean": round(float(v), 3)} for k, v in grouped.items() if not math.isnan(float(v)) if v is not None],
        }
    # Simple trend: value distribution sorted by index
    return {
        "column": column,
        "min": round(float(numeric.min()), 3),
        "max": round(float(numeric.max()), 3),
        "mean": round(float(numeric.mean()), 3),
        "median": round(float(numeric.median()), 3),
        "std": round(float(numeric.std()), 3),
        "count": int(numeric.count()),
        "missing": int(numeric.isna().sum()),
    }


def run_generic_operation(
    dataframe: pd.DataFrame,
    operation: str,
    column: str | None = None,
    group_by: str | None = None,
    numeric_param: float | None = None,
    pandas_script: str | None = None,
) -> Any:
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
    if operation == "data_quality_report":
        return data_quality_report(dataframe)
    if operation == "impute_missing_values":
        return impute_missing_values(dataframe)
    if operation == "correlation":
        return correlation_analysis(dataframe, column)
    if operation == "trend":
        return trend_analysis(dataframe, column, group_by)
    if operation == "median":
        if not column or column not in dataframe.columns:
            raise ValueError("A valid numeric column is required for median.")
        numeric = pd.to_numeric(dataframe[column], errors="coerce")
        value = numeric.median(skipna=True)
        return None if pd.isna(value) else float(value)
    if operation == "describe":
        try:
            desc = dataframe.describe(include="all").to_dict()
            return {str(col): {str(k): (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in stats.items()} for col, stats in desc.items()}
        except Exception:
            return dataset_overview(dataframe)
    if operation == "std":
        if not column or column not in dataframe.columns:
            raise ValueError("A valid numeric column is required for std.")
        numeric = pd.to_numeric(dataframe[column], errors="coerce")
        value = numeric.std(skipna=True)
        return None if pd.isna(value) else float(value)
    if operation == "variance":
        if not column or column not in dataframe.columns:
            raise ValueError("A valid numeric column is required for variance.")
        numeric = pd.to_numeric(dataframe[column], errors="coerce")
        value = numeric.var(skipna=True)
        return None if pd.isna(value) else float(value)
    if operation == "percentile":
        if not column or column not in dataframe.columns:
            raise ValueError("A valid numeric column is required for percentile.")
        rank = 50.0 if numeric_param is None else float(numeric_param)
        rank = min(100.0, max(0.0, rank))
        numeric = pd.to_numeric(dataframe[column], errors="coerce")
        value = numeric.quantile(rank / 100.0)
        return None if pd.isna(value) else float(value)
    if operation == "custom_analytics":
        if not pandas_script:
            raise ValueError("pandas_script is required for custom_analytics.")
        try:
            return run_pandas_script(dataframe, pandas_script)
        except UnsafeAnalyticsScript as error:
            raise ValueError(str(error)) from error
    raise ValueError(f"Unsupported generic operation: {operation}")
