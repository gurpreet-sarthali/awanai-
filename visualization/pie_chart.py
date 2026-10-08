"""Static pie chart generation for small meaningful proportions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .metadata import failure_metadata, output_path, success_metadata
from .validators import validate_chart_data


def generate_pie_chart(
    dataframe: pd.DataFrame, label: str, value: str, *, title: str, output_dir: str | Path,
    filename: str | None = None,
) -> dict[str, Any]:
    validation = validate_chart_data(dataframe, required_columns=[label, value], numeric_columns=[value], max_categories=8)
    if not validation["valid"]:
        return failure_metadata("pie", validation["errors"], validation["warnings"])
    values = dataframe[value].astype(float)
    if (values < 0).any() or values.sum() <= 0:
        return failure_metadata("pie", ["Pie values must be non-negative and have a positive total."])
    path = output_path(output_dir, filename, "pie")
    figure, axis = plt.subplots(figsize=(7, 7))
    axis.pie(values, labels=dataframe[label].astype(str), autopct="%1.1f%%", startangle=90)
    axis.set_title(title)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return success_metadata(chart_type="pie", path=path, title=title, row_count=len(dataframe), x_column=label, y_column=value, warnings=validation["warnings"])