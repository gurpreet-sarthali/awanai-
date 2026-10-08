from pathlib import Path
from typing import Any

import pandas as pd

from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID
from visualization.chart_engine import create_chart

from .analytics_service import AnalyticsService

ALLOWED_VISUALIZATION_OPERATIONS = {
    "placement_by_internship",
    "placement_by_cgpa_group",
    "placement_by_project_group",
    "placement_by_communication",
    "average_metrics_by_placement",
    "value_counts",
    "group_average",
}


class VisualizationService:
    def __init__(self, analytics_service: AnalyticsService, output_dir: Path) -> None:
        self.analytics_service = analytics_service
        self.output_dir = output_dir

    def generate(
        self,
        chart_type: str,
        operation: str,
        *,
        dataset_id: str = DEMO_PLACEMENT_DATASET_ID,
        column: str | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        if chart_type not in {"bar", "line", "pie", "histogram", "scatter", "box"}:
            raise ValueError(f"Unsupported chart type: {chart_type}")
        if operation not in ALLOWED_VISUALIZATION_OPERATIONS:
            raise ValueError(f"Unsupported visualization operation: {operation}")
        if operation == "average_metrics_by_placement":
            return self._average_chart(chart_type, dataset_id=dataset_id)
        if operation in {"value_counts", "group_average"}:
            return self._generic_chart(chart_type, operation, dataset_id=dataset_id, column=column, group_by=group_by)
        rows = self.analytics_service.grouped(operation, dataset_id=dataset_id)
        if chart_type not in {"bar", "pie"}:
            raise ValueError(f"Chart type '{chart_type}' is not supported for grouped operation '{operation}'")
        field = {
            "placement_by_internship": ("Internship_Experience", "placement_rate", "Placement Rate by Internship Experience"),
            "placement_by_cgpa_group": ("CGPA_Group", "placement_rate", "Placement Rate by CGPA Group"),
            "placement_by_project_group": ("Project_Group", "placement_rate", "Placement Rate by Project Group"),
            "placement_by_communication": ("Communication_Skills", "placement_rate", "Placement Rate by Communication Skills"),
        }[operation]
        dataframe = pd.DataFrame(rows).rename(columns={"group": field[0], "value": field[1]})
        spec = {
            "chart_type": chart_type,
            "x": field[0],
            "y": field[1],
            "title": field[2],
            "x_label": field[0],
            "y_label": "Placement Rate (%)",
            "filename": f"api_{dataset_id}_{operation}.{chart_type}.png",
        }
        return self._render(dataframe, spec, dataset_id)

    def _average_chart(self, chart_type: str, dataset_id: str) -> dict[str, Any]:
        if chart_type != "bar":
            raise ValueError("average_metrics_by_placement currently supports only bar charts")
        values = self.analytics_service.run_operation("average_metrics_by_placement", dataset_id=dataset_id)
        rows = [{"Placement": row["group"], "average_cgpa": row["value"]} for row in values["average_cgpa_by_placement"]]
        return self._render(
            pd.DataFrame(rows),
            {"chart_type": "bar", "x": "Placement", "y": "average_cgpa", "title": "Average CGPA by Placement", "filename": f"api_{dataset_id}_average_cgpa_by_placement.png"},
            dataset_id,
        )

    def _generic_chart(
        self,
        chart_type: str,
        operation: str,
        *,
        dataset_id: str,
        column: str | None,
        group_by: str | None,
    ) -> dict[str, Any]:
        if chart_type not in {"bar", "pie"}:
            raise ValueError(f"Chart type '{chart_type}' is not supported for `{operation}`.")
        rows = self.analytics_service.run_operation(operation, dataset_id=dataset_id, column=column, group_by=group_by)
        if not isinstance(rows, list):
            raise ValueError(f"Operation `{operation}` did not return grouped data.")
        x_name = group_by or column or "group"
        y_name = "value"
        dataframe = pd.DataFrame(rows).rename(columns={"group": x_name, "value": y_name})
        title = f"{operation.replace('_', ' ').title()} for {dataset_id}"
        return self._render(
            dataframe,
            {
                "chart_type": chart_type,
                "x": x_name,
                "y": y_name,
                "title": title,
                "filename": f"api_{dataset_id}_{operation}.{chart_type}.png",
            },
            dataset_id,
        )

    def _render(self, dataframe: pd.DataFrame, specification: dict[str, Any], dataset_id: str) -> dict[str, Any]:
        result = create_chart(dataframe, specification, self.output_dir)
        if not result.get("success"):
            raise RuntimeError("Visualization generation failed: " + "; ".join(result.get("errors", [])))
        result["data_source"] = dataset_id
        return result
