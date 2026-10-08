"""Type inference and type casting utilities for tabular datasets."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

BOOLEAN_LIKE = {"true", "false", "yes", "no", "0", "1", "y", "n", "t", "f"}
DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d{4}/\d{2}/\d{2}$"),
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    re.compile(r"^\d{2}-\d{2}-\d{4}$"),
]
DATETIME_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?"),
    re.compile(r"^\d{4}/\d{2}/\d{2}[ T]\d{2}:\d{2}(:\d{2})?"),
]


def infer_column_type(series: pd.Series) -> str:
    """Infer the high-level data type of a Pandas Series."""
    non_null = series.dropna()
    if non_null.empty:
        return "empty"

    # Numeric checks
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        # Check if actually integers stored as floats
        try:
            if (non_null % 1 == 0).all():
                return "integer"
        except Exception:
            pass
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    # Try string-based numeric inference
    as_str = non_null.astype(str).str.strip()
    
    # Check boolean-like
    lowered = as_str.str.lower()
    if set(lowered.unique()).issubset(BOOLEAN_LIKE) and len(lowered.unique()) > 0:
        return "boolean"

    # Try numeric conversion
    numeric = pd.to_numeric(as_str.str.replace(",", "", regex=False), errors="coerce")
    valid_numeric_ratio = numeric.notna().mean()
    if valid_numeric_ratio >= 0.9:
        valid_numeric = numeric.dropna()
        if (valid_numeric % 1 == 0).all():
            return "integer"
        return "float"

    # Try datetime / date matching
    if any(as_str.str.match(p).mean() >= 0.85 for p in DATETIME_PATTERNS):
        return "datetime"
    if any(as_str.str.match(p).mean() >= 0.85 for p in DATE_PATTERNS):
        return "date"

    # Check ID-like vs Categorical vs Text
    unique_count = non_null.nunique()
    total_count = len(non_null)
    
    if unique_count == total_count and total_count >= 5:
        return "id_like"
    
    if unique_count <= min(50, max(5, total_count // 10)):
        return "categorical"

    return "string"


def cast_column_type(series: pd.Series, target_type: str) -> pd.Series:
    """Safely cast a Series to target_type without silent corruption."""
    norm_type = target_type.lower().strip()
    
    if norm_type in ("integer", "int"):
        numeric = pd.to_numeric(series.astype(str).str.strip().str.replace(",", "", regex=False), errors="coerce")
        # Use pandas nullable integer type Int64
        return numeric.round().astype("Int64")

    if norm_type in ("float", "double", "numeric", "number"):
        return pd.to_numeric(series.astype(str).str.strip().str.replace(",", "", regex=False), errors="coerce")

    if norm_type in ("boolean", "bool"):
        mapping = {
            "true": True, "1": True, "yes": True, "y": True, "t": True,
            "false": False, "0": False, "no": False, "n": False, "f": False,
        }
        as_lower = series.astype(str).str.strip().str.lower()
        return as_lower.map(mapping).astype("boolean")

    if norm_type in ("date", "datetime"):
        parsed = pd.to_datetime(series, errors="coerce")
        if norm_type == "date":
            return parsed.dt.date
        return parsed

    if norm_type in ("categorical", "category"):
        return series.astype("category")

    if norm_type in ("string", "text", "str"):
        return series.astype("string")

    raise ValueError(f"Unsupported target type '{target_type}'. Supported types: integer, float, boolean, date, datetime, categorical, string.")
