from typing import Any

from analytics.cleaning import copy_for_analysis
from analytics.filters import apply_filters
from analytics.comparisons import comparison_metrics
from analytics.generic_analytics import run_generic_operation
from analytics.grouping import grouped_analytics
from analytics.metrics import basic_metrics
from analytics.placement import placement_metrics

from backend.core.dataset_constants import DEMO_PLACEMENT_DATASET_ID
from backend.repositories.database_repository import DatabaseRepository
from backend.repositories.dataset_registry_repository import DatasetNotFoundError

ALLOWED_PLACEMENT_OPERATIONS = {
    "overall_placement_rate",
    "placement_by_internship",
    "placement_by_cgpa_group",
    "placement_by_project_group",
    "placement_by_communication",
    "average_metrics_by_placement",
}

GENERIC_OPERATIONS = {
    "overview",
    "count",
    "average",
    "minimum",
    "maximum",
    "sum",
    "value_counts",
    "group_average",
    "data_quality_report",
    "impute_missing_values",
    "correlation",
    "trend",
    "median",
    "describe",
    "std",
    "variance",
    "percentile",
    "custom_analytics",
}

GENERAL_OPERATIONS = {"general_answer"}

ALLOWED_OPERATIONS = ALLOWED_PLACEMENT_OPERATIONS | GENERIC_OPERATIONS | GENERAL_OPERATIONS | {"summary", "placement"}


class InvalidAnalyticsOperation(ValueError):
    pass


class AnalyticsService:
    def __init__(self, repository: DatabaseRepository) -> None:
        self.repository = repository

    def _load(self, dataset_id: str):
        try:
            return copy_for_analysis(self.repository.load_dataframe(dataset_id))
        except DatasetNotFoundError as error:
            raise InvalidAnalyticsOperation(str(error)) from error

    def _supports_placement_analytics(self, dataframe) -> bool:
        required = {"Placement", "Internship_Experience", "CGPA", "Projects_Completed", "Communication_Skills"}
        return required.issubset(set(dataframe.columns))

    def _all(self, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> dict[str, Any]:
        dataframe = self._load(dataset_id)
        return {
            "basic": basic_metrics(dataframe),
            "placement": placement_metrics(dataframe),
            "grouped": grouped_analytics(dataframe),
            "comparisons": comparison_metrics(dataframe),
        }

    def summary(self, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> dict[str, Any]:
        dataframe = self._load(dataset_id)
        if self._supports_placement_analytics(dataframe):
            basic = self._all(dataset_id)["basic"]
            return {
                key: basic[key]
                for key in (
                    "total_students",
                    "placed_students",
                    "not_placed_students",
                    "placement_rate",
                    "average_cgpa",
                    "average_iq",
                    "average_projects",
                )
            }
        overview = run_generic_operation(dataframe, "overview")
        return {
            "row_count": overview["row_count"],
            "column_count": overview["column_count"],
            "numeric_columns": overview["numeric_columns"],
            "categorical_columns": overview["categorical_columns"],
            "missing_values": overview["missing_values"],
        }

    def placement(self, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> dict[str, Any]:
        if not self._supports_placement_analytics(self._load(dataset_id)):
            raise InvalidAnalyticsOperation("Placement analytics are unavailable for this dataset.")
        values = self._all(dataset_id)["placement"]
        return {"overall_placement_rate": self._all(dataset_id)["basic"]["placement_rate"], **values}

    def internship(self, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> dict[str, Any]:
        grouped = self.run_operation("placement_by_internship", dataset_id=dataset_id)
        return {"groups": grouped}

    def run_operation(
        self,
        operation: str,
        *,
        dataset_id: str = DEMO_PLACEMENT_DATASET_ID,
        column: str | None = None,
        group_by: str | None = None,
        numeric_param: float | None = None,
        pandas_script: str | None = None,
        filters: list[Any] | None = None,
    ) -> dict[str, Any] | list[Any] | float | int:
        if operation not in ALLOWED_OPERATIONS:
            raise InvalidAnalyticsOperation(f"Unsupported analytics operation: {operation}")
        if operation in GENERAL_OPERATIONS:
            raise InvalidAnalyticsOperation("General questions are answered by the AI layer, not the analytics engine.")
        dataframe = apply_filters(self._load(dataset_id), filters or [])
        if operation in GENERIC_OPERATIONS or operation == "overview":
            return run_generic_operation(
                dataframe,
                operation,
                column,
                group_by,
                numeric_param=numeric_param,
                pandas_script=pandas_script,
            )
        if operation in {"summary", "placement"}:
            return self.summary(dataset_id) if operation == "summary" else self.placement(dataset_id)
        if not self._supports_placement_analytics(dataframe):
            raise InvalidAnalyticsOperation(f"Operation `{operation}` is not supported for this dataset.")
        values = self._all(dataset_id)
        if operation == "overall_placement_rate":
            return values["basic"]["placement_rate"]
        mapping = {
            "placement_by_internship": values["grouped"]["placement_rate_by_internship"],
            "placement_by_cgpa_group": values["grouped"]["placement_rate_by_cgpa_group"],
            "placement_by_project_group": values["grouped"]["placement_rate_by_project_group"],
            "placement_by_communication": values["grouped"]["placement_rate_by_communication"],
            "average_metrics_by_placement": values["placement"],
        }
        return mapping[operation]

    def grouped(self, operation: str, dataset_id: str = DEMO_PLACEMENT_DATASET_ID) -> list[dict[str, Any]]:
        result = self.run_operation(operation, dataset_id=dataset_id)
        if not isinstance(result, list):
            raise InvalidAnalyticsOperation(f"Operation is not grouped: {operation}")
        return result
