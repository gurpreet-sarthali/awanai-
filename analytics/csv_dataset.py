"""CSV inspection, validation, and non-destructive cleaning for uploaded datasets."""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from analytics.column_normalization import normalize_column_names

BOOLEAN_LIKE = {"true", "false", "yes", "no", "0", "1", "y", "n"}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")


class CSVValidationError(ValueError):
    pass


def read_csv_bytes(content: bytes, encoding: str = "utf-8") -> pd.DataFrame:
    if not content.strip():
        raise CSVValidationError("The uploaded file is empty.")
    try:
        text = content.decode(encoding)
    except UnicodeDecodeError as error:
        raise CSVValidationError("Could not decode the CSV using UTF-8.") from error
    buffer = io.StringIO(text)
    try:
        dataframe = pd.read_csv(buffer, sep=None, engine="python")
    except Exception as error:
        raise CSVValidationError("The file is not a readable CSV.") from error
    if dataframe.shape[1] == 0:
        raise CSVValidationError("The CSV has no columns.")
    return dataframe


def inspect_csv_dataframe(dataframe: pd.DataFrame) -> dict[str, Any]:
    warnings: list[str] = []
    duplicate_columns = [name for name in dataframe.columns if list(dataframe.columns).count(name) > 1]
    if duplicate_columns:
        warnings.append(f"Duplicate column name(s): {', '.join(sorted(set(map(str, duplicate_columns))))}.")

    empty_columns = [str(column) for column in dataframe.columns if dataframe[column].isna().all()]
    if empty_columns:
        warnings.append(f"Entirely empty column(s): {', '.join(empty_columns)}.")

    empty_rows = int(dataframe.isna().all(axis=1).sum())
    if empty_rows:
        warnings.append(f"{empty_rows} entirely empty row(s) detected.")

    duplicate_rows = int(dataframe.duplicated().sum())
    missing_values = {str(column): int(value) for column, value in dataframe.isna().sum().items() if int(value) > 0}

    column_profiles: list[dict[str, Any]] = []
    for column in dataframe.columns:
        series = dataframe[column]
        non_null = series.dropna()
        profile: dict[str, Any] = {
            "original_name": str(column),
            "inferred_kind": _infer_kind(series),
            "nullable": bool(series.isna().any()),
            "unique_values": int(non_null.nunique()),
        }
        if profile["inferred_kind"] == "id_like" and profile["unique_values"] == len(non_null):
            profile["possible_id"] = True
        column_profiles.append(profile)

    return {
        "rows": int(len(dataframe)),
        "columns": int(len(dataframe.columns)),
        "missing_values": missing_values,
        "duplicate_rows": duplicate_rows,
        "empty_rows": empty_rows,
        "duplicate_columns": sorted(set(map(str, duplicate_columns))),
        "empty_columns": empty_columns,
        "column_profiles": column_profiles,
        "warnings": warnings,
    }


def clean_csv_dataframe(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Non-destructive cleaning: normalize names, trim strings, drop exact duplicate rows."""

    warnings: list[str] = []
    rows_before = int(len(dataframe))
    renamed = normalize_column_names(dataframe.columns)
    cleaned = dataframe.copy()
    cleaned.columns = [normalized for _, normalized in renamed]
    columns_normalized = [{"original": original, "normalized": normalized} for original, normalized in renamed]

    for column in cleaned.select_dtypes(include=["object", "string"]).columns:
        cleaned[column] = cleaned[column].astype("string").str.strip()

    empty_row_mask = cleaned.isna().all(axis=1)
    removed_empty = int(empty_row_mask.sum())
    if removed_empty:
        cleaned = cleaned.loc[~empty_row_mask].copy()
        warnings.append(f"Removed {removed_empty} entirely empty row(s).")

    duplicates_removed = int(cleaned.duplicated().sum())
    if duplicates_removed:
        cleaned = cleaned.drop_duplicates().reset_index(drop=True)
        warnings.append(f"Removed {duplicates_removed} exact duplicate row(s).")

    _standardize_boolean_like(cleaned, warnings)

    report = {
        "rows_before": rows_before,
        "rows_after": int(len(cleaned)),
        "duplicates_removed": duplicates_removed,
        "empty_rows_removed": removed_empty,
        "columns_normalized": columns_normalized,
        "warnings": warnings,
    }
    return cleaned, report


def infer_mysql_type(series: pd.Series) -> str:
    kind = _infer_kind(series)
    if kind == "numeric":
        return "DOUBLE NULL"
    if kind == "boolean_like":
        return "VARCHAR(16) NULL"
    if kind == "date_like":
        return "VARCHAR(32) NULL"
    max_len = int(series.astype("string").str.len().max(skipna=True) or 0)
    if max_len <= 255:
        return "VARCHAR(255) NULL"
    return "TEXT NULL"


def _infer_kind(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    numeric = pd.to_numeric(non_null, errors="coerce")
    if numeric.notna().mean() >= 0.9:
        return "numeric"
    lowered = {str(value).strip().lower() for value in non_null.unique()}
    if lowered and lowered.issubset(BOOLEAN_LIKE):
        return "boolean_like"
    as_string = non_null.astype("string")
    if as_string.str.match(DATE_PATTERN).mean() >= 0.9:
        return "date_like"
    if non_null.nunique() == len(non_null) and len(non_null) >= 3:
        return "id_like"
    if non_null.nunique() <= min(50, max(5, len(non_null) // 10)):
        return "categorical"
    return "text"


def _standardize_boolean_like(dataframe: pd.DataFrame, warnings: list[str]) -> None:
    mapping = {"true": "Yes", "false": "No", "yes": "Yes", "no": "No", "y": "Yes", "n": "No", "1": "Yes", "0": "No"}
    for column in dataframe.columns:
        series = dataframe[column]
        if _infer_kind(series) != "boolean_like":
            continue
        dataframe[column] = series.astype("string").str.strip().str.lower().map(mapping).fillna(series.astype("string").str.strip())
        warnings.append(f"Standardized boolean-like values in `{column}`.")
