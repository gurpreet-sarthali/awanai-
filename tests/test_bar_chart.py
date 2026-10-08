import pandas as pd

from visualization.bar_chart import generate_bar_chart
from visualization.pie_chart import generate_pie_chart


def test_bar_chart_writes_metadata_and_file(tmp_path):
    result = generate_bar_chart(pd.DataFrame({"group": ["Yes", "No"], "rate": [16.3, 16.8]}), "group", "rate", title="Rates", output_dir=tmp_path)
    assert result["success"] is True
    assert result["row_count"] == 2
    assert (tmp_path / result["file_path"].split("\\")[-1]).is_file()


def test_bar_chart_reports_missing_column(tmp_path):
    result = generate_bar_chart(pd.DataFrame({"group": ["Yes"]}), "group", "missing", title="Bad", output_dir=tmp_path)
    assert result["success"] is False
    assert result["errors"]


def test_pie_chart_rejects_too_many_categories(tmp_path):
    data = pd.DataFrame({"group": [str(index) for index in range(9)], "count": [1] * 9})
    result = generate_pie_chart(data, "group", "count", title="Too many", output_dir=tmp_path)
    assert result["success"] is False