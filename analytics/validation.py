"""Structured validation checks for the placement dataset."""

from __future__ import annotations

from typing import Any

import pandas as pd

EXPECTED_PLACEMENT_VALUES = {"Yes", "No"}
EXPECTED_INTERNSHIP_VALUES = {"Yes", "No"}


def _counts(dataframe: pd.DataFrame) -> dict[str, int]:
    return {str(column): int(value) for column, value in dataframe.isna().sum().items() if value}


def validate_data(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Return validation findings without dropping or imputing any rows."""

    warnings: list[str] = []
    missing_values = _counts(dataframe)
    duplicate_ids = int(dataframe["College_ID"].duplicated().sum()) if "College_ID" in dataframe else 0
    if missing_values:
        warnings.append("Missing values require review before interpretation.")
    if duplicate_ids:
        warnings.append("College_ID contains duplicate values and is not a unique key.")

    numeric_ranges: dict[str, tuple[float, float]] = {
        "Projects_Completed": (0, float("inf")),
        "CGPA": (0, float("inf")),
        "IQ": (0, float("inf")),
    }
    invalid_numeric: dict[str, int] = {}
    for column, (minimum, maximum) in numeric_ranges.items():
        if column not in dataframe:
            continue
        numeric = pd.to_numeric(dataframe[column], errors="coerce")
        invalid = numeric.isna() & dataframe[column].notna()
        invalid |= numeric.lt(minimum) | numeric.gt(maximum)
        count = int(invalid.sum())
        if count:
            invalid_numeric[column] = count
            warnings.append(f"{column} has {count} invalid numeric value(s).")

    unexpected_categories: dict[str, list[str]] = {}
    for column, expected in {
        "Placement": EXPECTED_PLACEMENT_VALUES,
        "Internship_Experience": EXPECTED_INTERNSHIP_VALUES,
    }.items():
        if column in dataframe:
            observed = {str(value).strip() for value in dataframe[column].dropna().unique()}
            unexpected = sorted(observed - expected)
            if unexpected:
                unexpected_categories[column] = unexpected
                warnings.append(f"{column} has unexpected value(s): {', '.join(unexpected)}.")

    return {
        "valid": not warnings,
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "missing_values": missing_values,
        "duplicate_ids": duplicate_ids,
        "invalid_numeric_values": invalid_numeric,
        "unexpected_categories": unexpected_categories,
        "warnings": warnings,
    }