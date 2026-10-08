"""Association-oriented comparison analytics."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .grouping import add_cgpa_group, add_project_group, placement_rate_by
from .metrics import placement_rate


def comparison_metrics(dataframe: pd.DataFrame) -> dict[str, Any]:
    placed = dataframe[dataframe["Placement"] == "Yes"]
    not_placed = dataframe[dataframe["Placement"] == "No"]
    return {
        "observed_internship_rate_difference": placement_rate(dataframe[dataframe["Internship_Experience"] == "Yes"]) - placement_rate(dataframe[dataframe["Internship_Experience"] == "No"]),
        "observed_average_cgpa_difference": _difference(placed, not_placed, "CGPA"),
        "observed_average_iq_difference": _difference(placed, not_placed, "IQ"),
        "observed_average_projects_difference": _difference(placed, not_placed, "Projects_Completed"),
        "observed_average_communication_difference": _difference(placed, not_placed, "Communication_Skills"),
        "highest_cgpa_group": _highest_rate(add_cgpa_group(dataframe), "CGPA_Group"),
        "highest_project_group": _highest_rate(add_project_group(dataframe), "Project_Group"),
    }


def _difference(first: pd.DataFrame, second: pd.DataFrame, column: str) -> float | None:
    if first.empty or second.empty:
        return None
    return float(first[column].mean() - second[column].mean())


def _highest_rate(dataframe: pd.DataFrame, column: str) -> dict[str, Any] | None:
    groups = placement_rate_by(dataframe, column)
    valid = [row for row in groups if row["count"] and row["value"] is not None]
    return max(valid, key=lambda row: row["value"]) if valid else None