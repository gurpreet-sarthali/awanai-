from tests.test_metrics import sample_dataframe

from analytics.placement import placement_metrics


def test_internship_and_placement_metrics():
    metrics = placement_metrics(sample_dataframe())
    assert metrics["internship_placement_rate"] == 100.0
    assert metrics["non_internship_placement_rate"] == 0.0
    assert metrics["average_cgpa_placed"] == 8.0
    assert metrics["average_cgpa_not_placed"] == 6.5


def test_one_row_dataset():
    metrics = placement_metrics(sample_dataframe().iloc[[0]])
    assert metrics["placement_count_by_status"] == {"Yes": 1}
    assert metrics["average_projects_placed"] == 2.0