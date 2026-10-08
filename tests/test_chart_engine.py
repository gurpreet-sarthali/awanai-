import pandas as pd

from visualization.chart_engine import create_chart


def chart_dataframe() -> pd.DataFrame:
    return pd.DataFrame({"category": ["A", "B", "C"], "value": [2.0, 4.0, 3.0], "group": ["X", "Y", "X"]})


def test_engine_dispatches_all_supported_chart_types(tmp_path):
    data = chart_dataframe()
    specifications = [
        {"chart_type": "bar", "x": "category", "y": "value", "title": "Bar"},
        {"chart_type": "line", "x": "category", "y": "value", "title": "Line"},
        {"chart_type": "pie", "x": "category", "y": "value", "title": "Pie"},
        {"chart_type": "histogram", "y": "value", "title": "Histogram"},
        {"chart_type": "scatter", "x": "value", "y": "value", "title": "Scatter"},
        {"chart_type": "box", "x": "group", "y": "value", "title": "Box"},
    ]
    results = [create_chart(data, specification, tmp_path) for specification in specifications]
    assert all(result["success"] for result in results)
    assert all((tmp_path / result["file_path"].split("\\")[-1]).is_file() for result in results)


def test_engine_rejects_unsupported_chart_type(tmp_path):
    result = create_chart(chart_dataframe(), {"chart_type": "radar", "title": "Unsupported"}, tmp_path)
    assert result["success"] is False
    assert "Unsupported chart type" in result["errors"][0]