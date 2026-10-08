"""Create a conservative, documented cleaned copy of a CSV dataset."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean a raw CSV dataset.")
    parser.add_argument("csv_path", type=Path, help="Path to the raw CSV file.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/placement_cleaned.csv"),
        help="Output path (default: data/processed/placement_cleaned.csv).",
    )
    return parser.parse_args()


def to_snake_case(column_name: object) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(column_name).strip())
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    return normalized.strip("_").lower() or "unnamed_column"


def standardize_column_names(columns: list[object]) -> list[str]:
    standardized: list[str] = []
    used: dict[str, int] = {}
    for column in columns:
        base_name = to_snake_case(column)
        occurrence = used.get(base_name, 0)
        used[base_name] = occurrence + 1
        standardized.append(base_name if occurrence == 0 else f"{base_name}_{occurrence + 1}")
    return standardized


def strip_string_values(dataframe: pd.DataFrame) -> int:
    changed_values = 0
    for column in dataframe.select_dtypes(include=["object", "string"]).columns:
        stripped = dataframe[column].map(lambda value: value.strip() if isinstance(value, str) else value)
        changed_values += int((dataframe[column].fillna("") != stripped.fillna("")).sum())
        dataframe[column] = stripped
    return changed_values


def report_invalid_numeric_values(dataframe: pd.DataFrame) -> list[str]:
    findings: list[str] = []
    for column in dataframe.select_dtypes(include=["object", "string"]).columns:
        non_null = dataframe[column].dropna()
        if non_null.empty:
            continue
        converted = pd.to_numeric(non_null, errors="coerce")
        invalid_count = int(converted.isna().sum())
        numeric_count = int(converted.notna().sum())
        if numeric_count > 0 and invalid_count > 0:
            findings.append(f"{column}: {invalid_count} non-numeric value(s) among numeric-looking values")
    return findings


def clean_dataset(csv_path: Path, output_path: Path) -> int:
    if not csv_path.is_file():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        return 1

    try:
        dataframe = pd.read_csv(csv_path)
    except (pd.errors.ParserError, UnicodeDecodeError, OSError, ValueError) as error:
        print(f"Error: could not read CSV '{csv_path}': {error}", file=sys.stderr)
        return 1

    rows_before = len(dataframe)
    dataframe.columns = standardize_column_names(list(dataframe.columns))
    duplicates_removed = int(dataframe.duplicated().sum())
    dataframe = dataframe.drop_duplicates().reset_index(drop=True)
    stripped_values = strip_string_values(dataframe)
    invalid_numeric_values = report_invalid_numeric_values(dataframe)
    missing_counts = dataframe.isna().sum()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False)

    print(f"Rows before cleaning: {rows_before}")
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"String values trimmed: {stripped_values}")
    print("Missing values handled: none removed or imputed; values were preserved for review")
    print(f"Rows after cleaning: {len(dataframe)}")
    print(f"Saved cleaned dataset: {output_path}")
    print("Column names standardized: yes")
    print("Missing values remaining by column:")
    print(missing_counts[missing_counts > 0].to_string() if missing_counts.any() else "None")
    print("Obviously invalid numeric values:")
    print("\n".join(f"- {finding}" for finding in invalid_numeric_values) or "None detected")
    if invalid_numeric_values:
        print("Note: invalid numeric-looking values were reported but not changed to avoid guessing.")
    return 0


if __name__ == "__main__":
    arguments = parse_args()
    raise SystemExit(clean_dataset(arguments.csv_path, arguments.output))