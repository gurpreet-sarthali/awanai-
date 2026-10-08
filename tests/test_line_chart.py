import pandas as pd

from visualization.box_plot import generate_box_plot
from visualization.histogram import generate_histogram
from visualization.line_chart import generate_line_chart
from visualization.scatter_plot import generate_scatter_plot


def test_line_histogram_scatter_and_box_charts(tmp_path):
    data = pd.DataFrame({"period": ["Q1", "Q2", "Q3"], "x": [1.0, 2.0, 3.0], "y": [2.0, 4.0, 3.0], "group": ["A", "B", "A"]})
    results = [
        generate_line_chart(data, "period", "y", title="Line", output_dir=tmp_path),
        generate_histogram(data, "y", title="Histogram", output_dir=tmp_path),
        generate_scatter_plot(data, "x", "y", group_by="group", title="Scatter", output_dir=tmp_path),
        generate_box_plot(data, "y", group_by="group", title="Box", output_dir=tmp_path),
    ]
    assert all(result["success"] for result in results)


def test_empty_data_is_reported(tmp_path):
    result = generate_histogram(pd.DataFrame({"value": []}), "value", title="Empty", output_dir=tmp_path)
    assert result["success"] is False
    assert "empty" in result["errors"][0].lower()