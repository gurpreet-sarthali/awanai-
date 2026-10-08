"""Validated chart dispatcher."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .bar_chart import generate_bar_chart
from .box_plot import generate_box_plot
from .chart_selector import select_chart
from .histogram import generate_histogram
from .line_chart import generate_line_chart
from .pie_chart import generate_pie_chart
from .scatter_plot import generate_scatter_plot
from .validators import validate_chart_spec


def create_chart(dataframe: pd.DataFrame, specification: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    spec_validation = validate_chart_spec(specification)
    if not spec_validation["valid"]:
        return {"success": False, "chart_type": specification.get("chart_type"), "errors": spec_validation["errors"], "warnings": []}
    chart_type = specification["chart_type"]
    common = {"title": specification["title"], "output_dir": output_dir, "filename": specification.get("filename")}
    if chart_type == "bar":
        return generate_bar_chart(dataframe, specification["x"], specification["y"], x_label=specification.get("x_label"), y_label=specification.get("y_label"), orientation=specification.get("orientation", "vertical"), **common)
    if chart_type == "line":
        return generate_line_chart(dataframe, specification["x"], specification["y"], x_label=specification.get("x_label"), y_label=specification.get("y_label"), **common)
    if chart_type == "pie":
        return generate_pie_chart(dataframe, specification["x"], specification["y"], **common)
    if chart_type == "histogram":
        return generate_histogram(dataframe, specification["y"], bins=specification.get("bins", 10), x_label=specification.get("x_label"), **common)
    if chart_type == "scatter":
        return generate_scatter_plot(dataframe, specification["x"], specification["y"], group_by=specification.get("group_by"), x_label=specification.get("x_label"), y_label=specification.get("y_label"), **common)
    return generate_box_plot(dataframe, specification["y"], group_by=specification.get("x"), x_label=specification.get("x_label"), y_label=specification.get("y_label"), **common)