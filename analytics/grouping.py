"""Reusable placement grouping functions."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .metrics import placement_rate

CGPA_BINS = [-float("inf"), 6, 7, 8, 9, float("inf")]
CGPA_LABELS = ["Below 6", "6 to <7", "7 to <8", "8 to <9", "9+"]
PROJECT_BINS = [-float("inf"), 0, 2, 4, float("inf")]
PROJECT_LABELS = ["0", "1-2", "3-4", "5+"]


def add_cgpa_group(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    result["CGPA_Group"] = pd.cut(dataframe["CGPA"], bins=CGPA_BINS, labels=CGPA_LABELS, right=False)
    return result


def add_project_group(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    result["Project_Group"] = pd.cut(dataframe["Projects_Completed"], bins=PROJECT_BINS, labels=PROJECT_LABELS, right=True)
    return result


def placement_rate_by(dataframe: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, subset in dataframe.groupby(column, dropna=False, observed=False):
        rows.append({"group": None if pd.isna(group) else str(group), "value": placement_rate(subset), "count": int(len(subset))})
    return rows


def grouped_analytics(dataframe: pd.DataFrame) -> dict[str, Any]:
    cgpa = add_cgpa_group(dataframe)
    projects = add_project_group(dataframe)
    return {
        "placement_rate_by_internship": placement_rate_by(dataframe, "Internship_Experience"),
        "placement_rate_by_projects": placement_rate_by(dataframe, "Projects_Completed"),
        "placement_rate_by_communication": placement_rate_by(dataframe, "Communication_Skills"),
        "placement_rate_by_academic": placement_rate_by(dataframe, "Academic_Performance"),
        "placement_rate_by_cgpa_group": placement_rate_by(cgpa, "CGPA_Group"),
        "placement_rate_by_project_group": placement_rate_by(projects, "Project_Group"),
        "average_cgpa_by_placement": _grouped_average(dataframe, "CGPA"),
        "average_iq_by_placement": _grouped_average(dataframe, "IQ"),
        "average_projects_by_placement": _grouped_average(dataframe, "Projects_Completed"),
        "average_communication_by_placement": _grouped_average(dataframe, "Communication_Skills"),
        "average_academic_by_placement": _grouped_average(dataframe, "Academic_Performance"),
    }


def _grouped_average(dataframe: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    return [{"group": str(group), "value": float(values[column].mean())} for group, values in dataframe.groupby("Placement")]