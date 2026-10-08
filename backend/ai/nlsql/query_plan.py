from __future__ import annotations

from .intent_schema import QueryPlan
from .query_errors import QueryPlanValidationError
from .schema_context import SchemaContext


def validate_query_plan(plan: QueryPlan, schema: SchemaContext) -> QueryPlan:
    allowed = schema.column_names
    referenced = list(plan.select_columns) + [plan.metric_column, plan.group_by]
    referenced.extend(filter_item.column for filter_item in plan.filters)
    if plan.sort:
        referenced.append(plan.sort.column)
    unknown = sorted({str(column) for column in referenced if column and column not in allowed})
    if unknown:
        raise QueryPlanValidationError(f"Unknown column(s): {', '.join(unknown)}")
    if plan.intent in {plan.intent.AVERAGE, plan.intent.MINIMUM, plan.intent.MAXIMUM, plan.intent.SUM} and not plan.metric_column:
        raise QueryPlanValidationError("This metric operation requires metric_column")
    if plan.intent in {plan.intent.GROUP_BY, plan.intent.COMPARISON} and not plan.group_by:
        raise QueryPlanValidationError("This operation requires group_by")
    if plan.intent == plan.intent.SELECT and not plan.select_columns:
        raise QueryPlanValidationError("select_rows requires select_columns")
    for filter_item in plan.filters:
        if filter_item.column in schema.categorical_values and filter_item.operator.value == "=":
            if str(filter_item.value) not in schema.categorical_values[filter_item.column]:
                raise QueryPlanValidationError(f"Invalid value for {filter_item.column}: {filter_item.value}")
    return plan