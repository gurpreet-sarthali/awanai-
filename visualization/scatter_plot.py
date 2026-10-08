"""Static numerical relationship charts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .metadata import failure_metadata, output_path, success_metadata
from .validators import validate_chart_data


def generate_scatter_plot(
    dataframe: pd.DataFrame, x: str, y: str, *, title: str, output_dir: str | Path,
    group_by: str | None = None, x_label: str | None = None, y_label: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    required = [x, y] + ([group_by] if group_by else [])
    validation = validate_chart_data(dataframe, required_columns=required, numeric_columns=[x, y])
    if not validation["valid"]:
        return failure_metadata("scatter", validation["errors"], validation["warnings"])
    path = output_path(output_dir, filename, "scatter")
    figure, axis = plt.subplots(figsize=(9, 5))
    if group_by:
        for group, subset in dataframe.groupby(group_by, dropna=False):
            axis.scatter(subset[x], subset[y], label=str(group), alpha=0.55)
        axis.legend(title=group_by)
    else:
        axis.scatter(dataframe[x], dataframe[y], alpha=0.55)
    axis.set_title(title)
    axis.set_xlabel(x_label or x)
    axis.set_ylabel(y_label or y)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return success_metadata(chart_type="scatter", path=path, title=title, row_count=len(dataframe), x_column=x, y_column=y, warnings=validation["warnings"])