"""Placement-specific Pandas analytics."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .metrics import placement_rate


def placement_count_by_status(dataframe: pd.DataFrame) -> dict[str, int]:
    return {str(key): int(value) for key, value in dataframe["Placement"].value_counts(dropna=False).items()}


def _rate_for(dataframe: pd.DataFrame, column: str, value: str) -> float:
    return placement_rate(dataframe[dataframe[column] == value])


def placement_metrics(dataframe: pd.DataFrame) -> dict[str, Any]:
    placed = dataframe[dataframe["Placement"] == "Yes"]
    not_placed = dataframe[dataframe["Placement"] == "No"]
    return {
        "placement_count_by_status": placement_count_by_status(dataframe),
        "internship_placement_rate": _rate_for(dataframe, "Internship_Experience", "Yes"),
        "non_internship_placement_rate": _rate_for(dataframe, "Internship_Experience", "No"),
        "average_cgpa_placed": _mean(placed, "CGPA"),
        "average_cgpa_not_placed": _mean(not_placed, "CGPA"),
        "average_iq_placed": _mean(placed, "IQ"),
        "average_iq_not_placed": _mean(not_placed, "IQ"),
        "average_projects_placed": _mean(placed, "Projects_Completed"),
        "average_projects_not_placed": _mean(not_placed, "Projects_Completed"),
        "average_communication_by_placement": _grouped_mean(dataframe, "Communication_Skills"),
        "average_academic_by_placement": _grouped_mean(dataframe, "Academic_Performance"),
    }


def _mean(dataframe: pd.DataFrame, column: str) -> float | None:
    value = dataframe[column].mean()
    return None if pd.isna(value) else float(value)


def _grouped_mean(dataframe: pd.DataFrame, column: str) -> dict[str, float | None]:
    return {str(key): _mean(group, column) for key, group in dataframe.groupby("Placement", dropna=False)}