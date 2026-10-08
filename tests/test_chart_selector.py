from visualization.chart_selector import select_chart


def test_selector_chooses_expected_chart_types():
    cases = [
        ({"analysis_type": "grouped_metric", "group_by": "Placement", "metric": "average_cgpa"}, "bar"),
        ({"analysis_type": "percentage_distribution", "x": "Placement", "y": "count", "category_count": 2}, "pie"),
        ({"analysis_type": "numerical_distribution", "y": "CGPA"}, "histogram"),
        ({"analysis_type": "numerical_relationship", "x": "CGPA", "y": "IQ"}, "scatter"),
        ({"analysis_type": "distribution_comparison", "x": "Placement", "y": "CGPA"}, "box"),
        ({"analysis_type": "time_series", "x": "month", "y": "value"}, "line"),
    ]
    for analysis, chart_type in cases:
        result = select_chart(analysis)
        assert result["valid"] is True
        assert result["specification"]["chart_type"] == chart_type


def test_selector_rejects_unknown_analysis_type():
    result = select_chart({"analysis_type": "unknown"})
    assert result["valid"] is False


def test_selector_does_not_choose_pie_for_many_categories():
    result = select_chart({"analysis_type": "percentage_distribution", "category_count": 12})
    assert result["valid"] is False