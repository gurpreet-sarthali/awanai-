from tests.test_metrics import sample_dataframe

from analytics.grouping import add_cgpa_group, add_project_group, grouped_analytics


def test_cgpa_grouping_boundaries():
    dataframe = sample_dataframe()
    grouped = add_cgpa_group(dataframe)
    assert list(grouped["CGPA_Group"].astype(str)) == ["8 to <9", "7 to <8", "6 to <7"]


def test_project_grouping_boundaries():
    dataframe = sample_dataframe()
    grouped = add_project_group(dataframe)
    assert list(grouped["Project_Group"].astype(str)) == ["1-2", "1-2", "0"]


def test_grouped_placement_rates():
    grouped = grouped_analytics(sample_dataframe())
    rates = {row["group"]: row["value"] for row in grouped["placement_rate_by_internship"]}
    assert rates == {"No": 0.0, "Yes": 100.0}


def test_unexpected_categories_are_reported():
    from analytics.validation import validate_data

    dataframe = sample_dataframe()
    dataframe.loc[0, "Placement"] = "Unknown"
    report = validate_data(dataframe)
    assert report["valid"] is False
    assert report["unexpected_categories"]["Placement"] == ["Unknown"]