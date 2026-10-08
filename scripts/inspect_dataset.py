"""Inspect a CSV dataset and print a readable profiling summary."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


BOOLEAN_VALUES = {"true", "false", "yes", "no", "y", "n", "1", "0"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile a CSV dataset.")
    parser.add_argument("csv_path", type=Path, help="Path to the CSV file to inspect.")
    return parser.parse_args()


def print_section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def print_list(label: str, values: Iterable[str]) -> None:
    values = list(values)
    print(f"{label}: {', '.join(values) if values else 'None detected'}")


def detect_id_columns(dataframe: pd.DataFrame) -> list[str]:
    candidates: list[str] = []
    row_count = len(dataframe)
    for column in dataframe.columns:
        name_suggests_id = "id" in column.lower() or column.lower().endswith("code")
        is_unique = row_count > 0 and dataframe[column].nunique(dropna=True) == row_count
        if name_suggests_id or is_unique:
            candidates.append(column)
    return candidates


def detect_boolean_like_columns(dataframe: pd.DataFrame) -> list[str]:
    candidates: list[str] = []
    for column in dataframe.columns:
        non_null = dataframe[column].dropna()
        normalized = {str(value).strip().lower() for value in non_null}
        if normalized and normalized.issubset(BOOLEAN_VALUES):
            candidates.append(column)
    return candidates


def detect_date_like_columns(dataframe: pd.DataFrame) -> list[str]:
    candidates: list[str] = []
    for column in dataframe.select_dtypes(include=["object", "string"]).columns:
        non_null = dataframe[column].dropna()
        if non_null.empty:
            continue
        parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
        if parsed.notna().mean() >= 0.8:
            candidates.append(column)
    return candidates


def print_unique_counts(dataframe: pd.DataFrame, columns: Iterable[str]) -> None:
    for column in columns:
        counts = dataframe[column].value_counts(dropna=False)
        print(f"\n{column} ({len(counts)} unique values):")
        print(counts.to_string())


def inspect_dataset(csv_path: Path) -> int:
    if not csv_path.is_file():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        return 1

    try:
        dataframe = pd.read_csv(csv_path)
    except (pd.errors.ParserError, UnicodeDecodeError, OSError, ValueError) as error:
        print(f"Error: could not read CSV '{csv_path}': {error}", file=sys.stderr)
        return 1

    print_section("DATASET OVERVIEW")
    print(f"File: {csv_path}")
    print(f"Rows: {len(dataframe)}")
    print(f"Columns: {len(dataframe.columns)}")
    print(f"Column names: {', '.join(map(str, dataframe.columns))}")

    print_section("DATA TYPES")
    print(dataframe.dtypes.to_string())

    print_section("FIRST 10 ROWS")
    print(dataframe.head(10).to_string(index=False))

    print_section("LAST 5 ROWS")
    print(dataframe.tail(5).to_string(index=False))

    print_section("MISSING VALUES")
    print(dataframe.isna().sum().to_string())

    print_section("DUPLICATES")
    print(f"Duplicate rows: {dataframe.duplicated().sum()}")

    categorical_columns = list(dataframe.select_dtypes(include=["object", "string", "category"]).columns)
    print_section("CATEGORICAL VALUE COUNTS")
    print_list("Categorical columns", categorical_columns)
    print_unique_counts(dataframe, categorical_columns)

    numerical_columns = list(dataframe.select_dtypes(include="number").columns)
    print_section("NUMERICAL SUMMARY")
    print_list("Numerical columns", numerical_columns)
    if numerical_columns:
        print(dataframe[numerical_columns].describe().to_string())

    print_section("COLUMN CLASSIFICATION")
    print_list("Possible ID columns", detect_id_columns(dataframe))
    print_list("Boolean-like columns", detect_boolean_like_columns(dataframe))
    print_list("Date-like columns", detect_date_like_columns(dataframe))
    print_list("Numerical columns", numerical_columns)
    print_list("Categorical columns", categorical_columns)
    return 0


if __name__ == "__main__":
    raise SystemExit(inspect_dataset(parse_args().csv_path))