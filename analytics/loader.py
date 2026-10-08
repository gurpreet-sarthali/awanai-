"""Load the verified placement table into Pandas."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .database import DatabaseConfig, connect

PLACEMENT_TABLE = "placement"
EXPECTED_COLUMNS = [
    "College_ID",
    "IQ",
    "Prev_Sem_Result",
    "CGPA",
    "Academic_Performance",
    "Internship_Experience",
    "Extra_Curricular_Score",
    "Communication_Skills",
    "Projects_Completed",
    "Placement",
]


class DataLoadError(RuntimeError):
    """Raised when the placement table cannot be loaded or does not match its contract."""


def load_placement_data(config: DatabaseConfig | None = None) -> pd.DataFrame:
    """Load placement rows without silently cleaning or changing them."""

    query = "SELECT " + ", ".join(f"`{column}`" for column in EXPECTED_COLUMNS) + f" FROM `{PLACEMENT_TABLE}`"
    connection = None
    try:
        connection = connect(config)
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        dataframe = pd.DataFrame(rows, columns=columns)
        cursor.close()
    except Exception as error:
        raise DataLoadError(f"Could not load `{PLACEMENT_TABLE}`: {error}") from error
    finally:
        if connection is not None:
            connection.close()

    missing_columns = [column for column in EXPECTED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise DataLoadError(f"Loaded data is missing expected column(s): {', '.join(missing_columns)}")
    return dataframe.loc[:, EXPECTED_COLUMNS].copy()


def dataframe_shape(dataframe: pd.DataFrame) -> dict[str, int]:
    return {"row_count": int(dataframe.shape[0]), "column_count": int(dataframe.shape[1])}