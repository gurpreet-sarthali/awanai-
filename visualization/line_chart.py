"""Static line chart generation for ordered or time-series data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .metadata import failure_metadata, output_path, success_metadata
from .validators import validate_chart_data


def generate_line_chart(
    dataframe: pd.DataFrame, x: str, y: str, *, title: str, output_dir: str | Path,
    x_label: str | None = None, y_label: str | None = None, filename: str | None = None,
) -> dict[str, Any]:
    validation = validate_chart_data(dataframe, required_columns=[x, y], numeric_columns=[y])
    if not validation["valid"]:
        return failure_metadata("line", validation["errors"], validation["warnings"])
    path = output_path(output_dir, filename, "line")
    figure, axis = plt.subplots(figsize=(9, 5))
    axis.plot(dataframe[x].astype(str), dataframe[y].astype(float), marker="o")
    axis.set_title(title)
    axis.set_xlabel(x_label or x)
    axis.set_ylabel(y_label or y)
    axis.grid(alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return success_metadata(chart_type="line", path=path, title=title, row_count=len(dataframe), x_column=x, y_column=y, warnings=validation["warnings"])