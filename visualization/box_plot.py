"""Static distribution comparison charts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .metadata import failure_metadata, output_path, success_metadata
from .validators import validate_chart_data


def generate_box_plot(
    dataframe: pd.DataFrame, value: str, *, title: str, output_dir: str | Path,
    group_by: str | None = None, x_label: str | None = None, y_label: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    required = [value] + ([group_by] if group_by else [])
    validation = validate_chart_data(dataframe, required_columns=required, numeric_columns=[value])
    if not validation["valid"]:
        return failure_metadata("box", validation["errors"], validation["warnings"])
    path = output_path(output_dir, filename, "box")
    figure, axis = plt.subplots(figsize=(8, 5))
    if group_by:
        groups = [group[value].dropna().astype(float).tolist() for _, group in dataframe.groupby(group_by, dropna=False)]
        labels = [str(group) for group in dataframe[group_by].dropna().unique()]
        axis.boxplot(groups, tick_labels=labels)
        axis.set_xlabel(x_label or group_by)
    else:
        axis.boxplot(dataframe[value].dropna().astype(float))
    axis.set_title(title)
    axis.set_ylabel(y_label or value)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return success_metadata(chart_type="box", path=path, title=title, row_count=len(dataframe), x_column=group_by, y_column=value, warnings=validation["warnings"])