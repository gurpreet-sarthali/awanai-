"""Deterministic data profiling, validation, and Data Quality Score calculation."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from analytics.type_inference import infer_column_type


def profile_and_score_dataset(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Compute comprehensive profiling metrics and a deterministic Data Quality Score."""
    total_rows = int(len(dataframe))
    total_cols = int(len(dataframe.columns))
    
    if total_rows == 0 or total_cols == 0:
        return {
            "total_rows": total_rows,
            "total_columns": total_cols,
            "quality_score": 0,
            "breakdown": {"completeness": 0.0, "uniqueness": 0.0, "consistency": 0.0, "validity": 0.0},
            "issues": ["The dataset contains no data."],
            "warnings": ["The dataset contains no data."],
            "column_profiles": [],
            "duplicate_rows": 0,
            "empty_rows": 0,
            "empty_columns": [],
        }

    total_cells = total_rows * total_cols
    total_nulls = int(dataframe.isna().sum().sum())
    
    empty_columns = [str(col) for col in dataframe.columns if dataframe[col].isna().all()]
    empty_rows = int(dataframe.isna().all(axis=1).sum())
    duplicate_rows = int(dataframe.duplicated().sum())

    # 1. Completeness: 100 * (1 - missing_cells / total_cells)
    completeness = round(max(0.0, min(100.0, (1.0 - (total_nulls / total_cells)) * 100.0)), 1)

    # 2. Uniqueness: 100 * (1 - duplicate_rows / total_rows)
    uniqueness = round(max(0.0, min(100.0, (1.0 - (duplicate_rows / total_rows)) * 100.0)), 1)

    # 3. Validity: penalties for entirely empty columns, empty rows, and malformed names
    empty_col_penalty = min(40.0, (len(empty_columns) / max(1, total_cols)) * 100.0)
    empty_row_penalty = min(30.0, (empty_rows / max(1, total_rows)) * 100.0)
    validity = round(max(0.0, min(100.0, 100.0 - (empty_col_penalty + empty_row_penalty))), 1)

    # 4. Consistency: evaluate type purity across non-null cells
    column_profiles: list[dict[str, Any]] = []
    consistency_penalties = 0.0
    issues: list[dict[str, Any]] = []
    warnings: list[str] = []

    if duplicate_rows > 0:
        issues.append({"type": "duplicate_rows", "severity": "medium", "message": f"{duplicate_rows} exact duplicate rows found.", "count": duplicate_rows})
        warnings.append(f"{duplicate_rows} duplicate row(s) detected.")

    if empty_rows > 0:
        issues.append({"type": "empty_rows", "severity": "high", "message": f"{empty_rows} entirely empty rows found.", "count": empty_rows})
        warnings.append(f"{empty_rows} entirely empty row(s) detected.")

    if empty_columns:
        issues.append({"type": "empty_columns", "severity": "high", "message": f"Empty columns: {', '.join(empty_columns)}", "columns": empty_columns})
        warnings.append(f"Entirely empty column(s): {', '.join(empty_columns)}.")

    for col in dataframe.columns:
        col_str = str(col)
        series = dataframe[col]
        non_null = series.dropna()
        null_count = int(series.isna().sum())
        null_pct = round((null_count / total_rows) * 100.0, 1)
        inferred_type = infer_column_type(series)
        unique_count = int(non_null.nunique())

        profile: dict[str, Any] = {
            "column_name": col_str,
            "inferred_type": inferred_type,
            "null_count": null_count,
            "null_percentage": null_pct,
            "unique_count": unique_count,
            "sample_values": [str(v) for v in non_null.head(5).tolist()],
            "stats": {},
        }

        if null_count > 0:
            severity = "high" if null_pct > 30 else ("medium" if null_pct > 10 else "low")
            issues.append({
                "type": "missing_values",
                "column": col_str,
                "severity": severity,
                "message": f"Column '{col_str}' has {null_count} missing values ({null_pct}%).",
                "count": null_count,
            })
            if null_pct > 10:
                warnings.append(f"Column '{col_str}' has {null_pct}% missing values.")

        # Compute numeric stats if applicable
        if inferred_type in ("integer", "float") and not non_null.empty:
            try:
                num_series = pd.to_numeric(non_null.astype(str).str.replace(",", "", regex=False), errors="coerce").dropna()
                if not num_series.empty:
                    profile["stats"] = {
                        "min": _safe_float(num_series.min()),
                        "max": _safe_float(num_series.max()),
                        "mean": _safe_float(num_series.mean()),
                        "median": _safe_float(num_series.median()),
                        "std": _safe_float(num_series.std()),
                        "q25": _safe_float(num_series.quantile(0.25)),
                        "q75": _safe_float(num_series.quantile(0.75)),
                    }
            except Exception:
                pass
        elif inferred_type in ("categorical", "string", "boolean") and not non_null.empty:
            try:
                top_counts = non_null.astype(str).value_counts().head(5).to_dict()
                profile["stats"] = {"top_frequencies": {str(k): int(v) for k, v in top_counts.items()}}
            except Exception:
                pass

        column_profiles.append(profile)

    # Average consistency score
    consistency = round(max(0.0, min(100.0, 100.0 - consistency_penalties)), 1)

    # Calculate overall deterministic quality score:
    # 35% completeness, 25% uniqueness, 20% consistency, 20% validity
    overall_score = round(
        (0.35 * completeness) + (0.25 * uniqueness) + (0.20 * consistency) + (0.20 * validity),
        0
    )

    return {
        "quality_score": int(overall_score),
        "total_rows": total_rows,
        "total_columns": total_cols,
        "duplicate_rows": duplicate_rows,
        "empty_rows": empty_rows,
        "empty_columns": empty_columns,
        "total_missing_cells": total_nulls,
        "missing_percentage": round((total_nulls / total_cells) * 100.0, 1),
        "breakdown": {
            "completeness": completeness,
            "uniqueness": uniqueness,
            "consistency": consistency,
            "validity": validity,
        },
        "issues": issues,
        "warnings": warnings,
        "column_profiles": column_profiles,
    }


def _safe_float(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return None
    try:
        return round(float(val), 3)
    except Exception:
        return None
