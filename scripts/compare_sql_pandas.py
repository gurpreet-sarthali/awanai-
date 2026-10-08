"""Compare key SQL metrics with independently calculated Pandas metrics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np

from analytics.cleaning import copy_for_analysis
from analytics.database import connect
from analytics.loader import load_placement_data
from analytics.metrics import placement_rate
from analytics.grouping import add_cgpa_group, add_project_group, placement_rate_by


TOLERANCE = 1e-4


def _sql_metrics() -> dict[str, float]:
    connection = connect()
    try:
        queries = {
            "total_students": "SELECT COUNT(*) FROM placement",
            "placed_students": "SELECT SUM(Placement = 'Yes') FROM placement",
            "placement_rate": "SELECT 100.0 * SUM(Placement = 'Yes') / NULLIF(COUNT(Placement), 0) FROM placement",
            "average_cgpa": "SELECT AVG(CGPA) FROM placement",
            "internship_placement_rate": "SELECT 100.0 * SUM(Placement = 'Yes') / NULLIF(COUNT(Placement), 0) FROM placement WHERE Internship_Experience = 'Yes'",
            "non_internship_placement_rate": "SELECT 100.0 * SUM(Placement = 'Yes') / NULLIF(COUNT(Placement), 0) FROM placement WHERE Internship_Experience = 'No'",
        }
        result: dict[str, float] = {}
        cursor = connection.cursor()
        for name, query in queries.items():
            cursor.execute(query)
            value = cursor.fetchone()[0]
            result[name] = float(value)
        cursor.execute("""
            SELECT CASE WHEN CGPA < 6 THEN 'Below 6' WHEN CGPA < 7 THEN '6 to <7'
                WHEN CGPA < 8 THEN '7 to <8' WHEN CGPA < 9 THEN '8 to <9' ELSE '9+' END AS category,
                100.0 * SUM(Placement = 'Yes') / NULLIF(COUNT(Placement), 0)
            FROM placement GROUP BY category ORDER BY MIN(CGPA)
        """)
        result.update({f"cgpa_group:{row[0]}": float(row[1]) for row in cursor.fetchall()})
        cursor.execute("""
            SELECT CASE WHEN Projects_Completed = 0 THEN '0' WHEN Projects_Completed <= 2 THEN '1-2'
                WHEN Projects_Completed <= 4 THEN '3-4' ELSE '5+' END AS category,
                100.0 * SUM(Placement = 'Yes') / NULLIF(COUNT(Placement), 0)
            FROM placement GROUP BY category ORDER BY MIN(Projects_Completed)
        """)
        result.update({f"project_group:{row[0]}": float(row[1]) for row in cursor.fetchall()})
        return result
    finally:
        connection.close()


def _pandas_metrics(dataframe: pd.DataFrame) -> dict[str, float]:
    dataframe = copy_for_analysis(dataframe)
    result = {
        "total_students": float(len(dataframe)),
        "placed_students": float((dataframe["Placement"] == "Yes").sum()),
        "placement_rate": placement_rate(dataframe),
        "average_cgpa": float(dataframe["CGPA"].mean()),
        "internship_placement_rate": placement_rate(dataframe[dataframe["Internship_Experience"] == "Yes"]),
        "non_internship_placement_rate": placement_rate(dataframe[dataframe["Internship_Experience"] == "No"]),
    }
    for row in placement_rate_by(add_cgpa_group(dataframe), "CGPA_Group"):
        result[f"cgpa_group:{row['group']}"] = float(row["value"])
    for row in placement_rate_by(add_project_group(dataframe), "Project_Group"):
        result[f"project_group:{row['group']}"] = float(row["value"])
    return result


def main() -> int:
    try:
        pandas_values = _pandas_metrics(load_placement_data())
        sql_values = _sql_metrics()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Metric\tSQL Result\tPandas Result\tMatch")
    failures = 0
    for metric, sql_value in sql_values.items():
        pandas_value = pandas_values[metric]
        matches = bool(np.isclose(sql_value, pandas_value, atol=TOLERANCE, rtol=0))
        failures += not matches
        print(f"{metric}\t{sql_value:.10f}\t{pandas_value:.10f}\t{'PASS' if matches else 'FAIL'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())