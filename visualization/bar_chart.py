"""Static bar chart generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .metadata import failure_metadata, output_path, success_metadata
from .validators import validate_chart_data


def generate_bar_chart(
    dataframe: pd.DataFrame, x: str, y: str, *, title: str, output_dir: str | Path,
    x_label: str | None = None, y_label: str | None = None, filename: str | None = None,
    orientation: str = "vertical", value_labels: bool = True,
) -> dict[str, Any]:
    validation = validate_chart_data(dataframe, required_columns=[x, y], numeric_columns=[y])
    if not validation["valid"]:
        return failure_metadata("bar", validation["errors"], validation["warnings"])
    if orientation not in {"vertical", "horizontal"}:
        return failure_metadata("bar", ["Orientation must be 'vertical' or 'horizontal'."])
    path = output_path(output_dir, filename, "bar")
    figure, axis = plt.subplots(figsize=(9, 5))
    labels = dataframe[x].astype(str).tolist()
    values = dataframe[y].astype(float).tolist()
    positions = range(len(labels))
    bars = axis.barh(list(positions), values) if orientation == "horizontal" else axis.bar(labels, values)
    if orientation == "horizontal":
        axis.set_yticks(list(positions), labels)
    if value_labels:
        for bar, value in zip(bars, values):
            if orientation == "horizontal":
                axis.text(value, bar.get_y() + bar.get_height() / 2, f"{value:.2f}", va="center")
            else:
                axis.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}", ha="center", va="bottom")
    axis.set_title(title)
    axis.set_xlabel(x_label or x)
    axis.set_ylabel(y_label or y)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return success_metadata(chart_type="bar", path=path, title=title, row_count=len(dataframe), x_column=x, y_column=y, warnings=validation["warnings"])