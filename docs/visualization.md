# Visualization Engine

## Purpose

Phase 4 converts validated structured analytics results into static PNG charts. It is independent of Gemini, FastAPI, React, authentication, and deployment. Chart selection is deterministic and rule-based.

## Structure

- `visualization/chart_engine.py` - validates a chart specification and dispatches it to a renderer.
- `visualization/chart_selector.py` - maps an analysis description to a chart specification without an LLM.
- `visualization/bar_chart.py` - categorical comparisons.
- `visualization/line_chart.py` - ordered or time-series values.
- `visualization/pie_chart.py` - small meaningful proportions.
- `visualization/histogram.py` - numerical distributions.
- `visualization/scatter_plot.py` - numerical relationships with optional categorical grouping.
- `visualization/box_plot.py` - distribution comparisons by category.
- `visualization/validators.py` - input and specification validation.
- `visualization/metadata.py` - unique output paths and metadata results.
- `visualization/results/` - generated PNG files and `chart_manifest.json`.

Matplotlib's non-interactive `Agg` backend is used, so generation works in terminals and CI without a desktop display. Seaborn is not used.

## Phase 3 input

The demo consumes the real Phase 3 file `analytics/results/placement_analytics.json`. Its grouped records have this shape:

```json
{
  "group": "Yes",
  "value": 16.321897073662967,
  "count": 3964
}
```

The runner maps `group` and `value` to the selected specification fields without recalculating analytics. Raw `data/raw/placement.csv` is used only for charts requiring row-level distributions or relationships, such as histograms, scatter plots, and box plots.

## Chart specification

```json
{
  "chart_type": "bar",
  "x": "Internship_Experience",
  "y": "placement_rate",
  "title": "Placement Rate by Internship Experience",
  "x_label": "Internship Experience",
  "y_label": "Placement Rate (%)",
  "data_source": "structured analytics result"
}
```

`create_chart(dataframe, specification, output_dir)` validates required fields, numeric columns, chart type, and data availability before rendering.

## Selection rules

| Analysis type | Chart |
|---|---|
| `grouped_metric` | Bar |
| `percentage_distribution` with at most 8 categories | Pie |
| `numerical_distribution` | Histogram |
| `numerical_relationship` | Scatter |
| `distribution_comparison` | Box |
| `time_series` | Line |

Pie charts are intentionally rejected for more than eight categories. The placement dataset has no time dimension, so its line-chart example uses a clearly labeled synthetic quarterly series only to test the reusable line renderer.

## Metadata and errors

Successful output includes:

```json
{
  "success": true,
  "chart_type": "bar",
  "file_path": "visualization/results/placement_rate_by_internship.png",
  "title": "Placement Rate by Internship Experience",
  "row_count": 2,
  "x_column": "Internship_Experience",
  "y_column": "placement_rate",
  "warnings": []
}
```

Invalid input returns `success: false` with structured `errors` and `warnings`; chart functions do not silently generate misleading output or crash the caller for missing columns, empty data, non-numeric measures, unsupported chart types, invalid pie totals, or excessive pie categories.

Output names are deterministic when supplied. If a file already exists, a short unique suffix is added so earlier charts are not overwritten.

## Demo runner

```powershell
.venv\Scripts\python.exe scripts\run_visualizations.py
```

The runner generates these real-data charts:

- Placement rate by internship status.
- Placement rate by CGPA group.
- Placement rate by project group.
- Average CGPA by placement status.
- Average communication by placement status.
- Placement Yes/No distribution.
- CGPA histogram.
- CGPA versus IQ scatter plot grouped by placement.
- CGPA box plot grouped by placement.
- Synthetic time-series line-chart example.

It prints metadata and writes `visualization/results/chart_manifest.json`.

## Testing

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

Tests cover all six renderers, selection rules, unsupported requests, empty data, missing fields, non-numeric fields, pie-category limits, file creation, and integration with the existing Phase 3 result structure.

## Limitations

- Static PNG output is used; interactive Plotly output is intentionally deferred.
- A chart shows observed values and distributions. It does not establish causation.
- The current placement dataset has no time field, so the line chart is not used for placement analytics.
- Chart selection is rule-based and does not interpret natural language.
- The engine does not execute arbitrary code from chart specifications.

## Future AI integration

Later, an AI layer may propose a structured chart specification. The backend must validate that specification with this engine before rendering. The visualization engine itself remains deterministic and does not call an LLM.