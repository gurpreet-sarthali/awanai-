"""Static numerical distribution charts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .metadata import failure_metadata, output_path, success_metadata
from .validators import validate_chart_data


def generate_histogram(
    dataframe: pd.DataFrame, column: str, *, title: str, output_dir: str | Path,
    bins: int = 10, x_label: str | None = None, filename: str | None = None,
) -> dict[str, Any]:
    validation = validate_chart_data(dataframe, required_columns=[column], numeric_columns=[column])
    if not validation["valid"]:
        return failure_metadata("histogram", validation["errors"], validation["warnings"])
    if bins < 1:
        return failure_metadata("histogram", ["bins must be at least 1."])
    path = output_path(output_dir, filename, "histogram")
    figure, axis = plt.subplots(figsize=(9, 5))
    axis.hist(dataframe[column].dropna().astype(float), bins=bins)
    axis.set_title(title)
    axis.set_xlabel(x_label or column)
    axis.set_ylabel("Frequency")
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return success_metadata(chart_type="histogram", path=path, title=title, row_count=len(dataframe), y_column=column, warnings=validation["warnings"])