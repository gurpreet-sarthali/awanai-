"""Basic Pandas/NumPy-compatible placement metrics."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _mean(dataframe: pd.DataFrame, column: str) -> float | None:
    value = dataframe[column].mean(skipna=True)
    return None if pd.isna(value) else float(value)


def _extreme(dataframe: pd.DataFrame, column: str, function: str) -> float | None:
    value = getattr(dataframe[column], function)()
    return None if pd.isna(value) else float(value)


def total_students(dataframe: pd.DataFrame) -> int:
    return int(len(dataframe))


def placed_students(dataframe: pd.DataFrame) -> int:
    return int((dataframe["Placement"] == "Yes").sum())


def not_placed_students(dataframe: pd.DataFrame) -> int:
    return int((dataframe["Placement"] == "No").sum())


def placement_rate(dataframe: pd.DataFrame) -> float:
    denominator = int(dataframe["Placement"].notna().sum())
    return 0.0 if denominator == 0 else placed_students(dataframe) * 100.0 / denominator


def average_cgpa(dataframe: pd.DataFrame) -> float | None:
    return _mean(dataframe, "CGPA")


def minimum_cgpa(dataframe: pd.DataFrame) -> float | None:
    return _extreme(dataframe, "CGPA", "min")


def maximum_cgpa(dataframe: pd.DataFrame) -> float | None:
    return _extreme(dataframe, "CGPA", "max")


def average_iq(dataframe: pd.DataFrame) -> float | None:
    return _mean(dataframe, "IQ")


def minimum_iq(dataframe: pd.DataFrame) -> float | None:
    return _extreme(dataframe, "IQ", "min")


def maximum_iq(dataframe: pd.DataFrame) -> float | None:
    return _extreme(dataframe, "IQ", "max")


def average_projects(dataframe: pd.DataFrame) -> float | None:
    return _mean(dataframe, "Projects_Completed")


def minimum_projects(dataframe: pd.DataFrame) -> float | None:
    return _extreme(dataframe, "Projects_Completed", "min")


def maximum_projects(dataframe: pd.DataFrame) -> float | None:
    return _extreme(dataframe, "Projects_Completed", "max")


def internship_students(dataframe: pd.DataFrame) -> int:
    return int((dataframe["Internship_Experience"] == "Yes").sum())


def non_internship_students(dataframe: pd.DataFrame) -> int:
    return int((dataframe["Internship_Experience"] == "No").sum())


def basic_metrics(dataframe: pd.DataFrame) -> dict[str, Any]:
    return {
        "total_students": total_students(dataframe),
        "placed_students": placed_students(dataframe),
        "not_placed_students": not_placed_students(dataframe),
        "placement_rate": placement_rate(dataframe),
        "internship_students": internship_students(dataframe),
        "non_internship_students": non_internship_students(dataframe),
        "average_cgpa": _mean(dataframe, "CGPA"),
        "minimum_cgpa": _extreme(dataframe, "CGPA", "min"),
        "maximum_cgpa": _extreme(dataframe, "CGPA", "max"),
        "average_iq": _mean(dataframe, "IQ"),
        "minimum_iq": _extreme(dataframe, "IQ", "min"),
        "maximum_iq": _extreme(dataframe, "IQ", "max"),
        "average_projects": _mean(dataframe, "Projects_Completed"),
        "minimum_projects": _extreme(dataframe, "Projects_Completed", "min"),
        "maximum_projects": _extreme(dataframe, "Projects_Completed", "max"),
    }