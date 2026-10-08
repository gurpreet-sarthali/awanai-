import pandas as pd

from analytics.metrics import basic_metrics, not_placed_students, placed_students, placement_rate


def sample_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "College_ID": ["A", "B", "C"],
            "IQ": [100, 110, 90],
            "CGPA": [8.0, 7.0, 6.0],
            "Academic_Performance": [8, 6, 4],
            "Communication_Skills": [8, 6, 3],
            "Projects_Completed": [2, 1, 0],
            "Internship_Experience": ["Yes", "No", "No"],
            "Placement": ["Yes", "No", "No"],
        }
    )


def test_core_metrics():
    dataframe = sample_dataframe()
    assert placed_students(dataframe) == 1
    assert not_placed_students(dataframe) == 2
    assert placement_rate(dataframe) == 100 / 3
    assert basic_metrics(dataframe)["average_cgpa"] == 7.0


def test_empty_dataframe_has_safe_zero_rate():
    dataframe = sample_dataframe().iloc[0:0]
    assert placement_rate(dataframe) == 0.0
    assert basic_metrics(dataframe)["total_students"] == 0


def test_no_placed_and_no_non_placed_cases():
    dataframe = sample_dataframe()
    dataframe["Placement"] = "No"
    assert placed_students(dataframe) == 0
    assert placement_rate(dataframe) == 0.0
    dataframe["Placement"] = "Yes"
    assert not_placed_students(dataframe) == 0
    assert placement_rate(dataframe) == 100.0


def test_missing_numeric_values_are_skipped_by_average():
    dataframe = sample_dataframe()
    dataframe.loc[0, "CGPA"] = None
    assert basic_metrics(dataframe)["average_cgpa"] == 6.5