"""Rule-based chart selection for structured analytics descriptions."""

from __future__ import annotations

from typing import Any


def select_chart(analysis: dict[str, Any]) -> dict[str, Any]:
    """Choose a chart without using an LLM."""

    analysis_type = analysis.get("analysis_type")
    group_by = analysis.get("group_by")
    metric = analysis.get("metric", "value")
    title = analysis.get("title") or _title_for(analysis_type, group_by, metric)
    if analysis_type == "time_series":
        chart_type = "line"
    elif analysis_type == "numerical_distribution":
        chart_type = "histogram"
    elif analysis_type == "numerical_relationship":
        chart_type = "scatter"
    elif analysis_type == "distribution_comparison":
        chart_type = "box"
    elif analysis_type == "percentage_distribution" and analysis.get("category_count", 0) <= 8:
        chart_type = "pie"
    elif analysis_type == "grouped_metric":
        chart_type = "bar"
    else:
        return {"valid": False, "errors": [f"No rule for analysis_type: {analysis_type!r}"], "warnings": []}
    specification = {
        "chart_type": chart_type,
        "x": analysis.get("x") or group_by,
        "y": analysis.get("y") or metric,
        "title": title,
        "x_label": analysis.get("x_label") or group_by,
        "y_label": analysis.get("y_label") or metric,
        "data_source": analysis.get("data_source", "structured analytics result"),
    }
    return {"valid": True, "errors": [], "warnings": [], "specification": specification}


def _title_for(analysis_type: str | None, group_by: str | None, metric: str) -> str:
    if analysis_type == "grouped_metric":
        return f"{metric.replace('_', ' ').title()} by {str(group_by).replace('_', ' ').title()}"
    return str(analysis_type or "Analytics").replace("_", " ").title()