"""Non-destructive helpers for preparing values used by analytics."""

from __future__ import annotations

import pandas as pd


def copy_for_analysis(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return a copy and normalize only status text whitespace for comparisons."""

    result = dataframe.copy()
    for column in ("Internship_Experience", "Placement"):
        if column in result:
            result[column] = result[column].astype("string").str.strip()
    return result