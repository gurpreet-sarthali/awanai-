from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .intent_schema import QueryIntent, QueryPlan
from .query_errors import QueryPlanValidationError
from .schema_context import SchemaContext


@dataclass(frozen=True)
class GeneratedQuery:
    sql: str
    parameters: tuple[Any, ...]
    row_query: bool


def _identifier(column: str) -> str:
    return f"`{column}`"


def generate_sql(plan: QueryPlan, schema: SchemaContext) -> GeneratedQuery:
    from .query_plan import validate_query_plan

    validate_query_plan(plan, schema)
    parameters: list[Any] = []
    row_query = plan.intent in {QueryIntent.SELECT, QueryIntent.FILTER, QueryIntent.DISTINCT}
    if plan.intent == QueryIntent.SELECT or plan.intent == QueryIntent.FILTER:
        selected = ", ".join(_identifier(column) for column in plan.select_columns)
    elif plan.intent == QueryIntent.DISTINCT:
        selected = f"DISTINCT {_identifier(plan.metric_column or plan.group_by or '')}"
    elif plan.intent == QueryIntent.COUNT:
        selected = "COUNT(*) AS `count`"
    elif plan.intent in {QueryIntent.AVERAGE, QueryIntent.MINIMUM, QueryIntent.MAXIMUM, QueryIntent.SUM}:
        function = {QueryIntent.AVERAGE: "AVG", QueryIntent.MINIMUM: "MIN", QueryIntent.MAXIMUM: "MAX", QueryIntent.SUM: "SUM"}[plan.intent]
        metric = f"{function}({_identifier(plan.metric_column or '')}) AS `{plan.intent.value}`"
        selected = f"{_identifier(plan.group_by)}, {metric}" if plan.group_by else metric
    elif plan.intent == QueryIntent.PLACEMENT_RATE:
        selected = "100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS `placement_rate`"
    elif plan.intent in {QueryIntent.GROUP_BY, QueryIntent.COMPARISON}:
        selected = f"{_identifier(plan.group_by or '')}, COUNT(*) AS `count`"
    else:
        raise QueryPlanValidationError(f"Unsupported intent: {plan.intent.value}")

    sql = f"SELECT {selected} FROM `{schema.table}`"
    if plan.intent in {QueryIntent.GROUP_BY, QueryIntent.COMPARISON, QueryIntent.PLACEMENT_RATE} and plan.group_by:
        sql = f"SELECT {selected} FROM `{schema.table}`"
        if plan.intent == QueryIntent.PLACEMENT_RATE:
            sql = f"SELECT {_identifier(plan.group_by)}, 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS `placement_rate` FROM `{schema.table}`"
    if plan.filters:
        clauses: list[str] = []
        for filter_item in plan.filters:
            if filter_item.operator.value == "IN":
                values = filter_item.value if isinstance(filter_item.value, list) else [filter_item.value]
                placeholders = ", ".join("%s" for _ in values)
                clauses.append(f"{_identifier(filter_item.column)} IN ({placeholders})")
                parameters.extend(values)
            else:
                clauses.append(f"{_identifier(filter_item.column)} {filter_item.operator.value} %s")
                parameters.append(filter_item.value)
        sql += " WHERE " + " AND ".join(clauses)
    if plan.intent in {QueryIntent.GROUP_BY, QueryIntent.COMPARISON, QueryIntent.PLACEMENT_RATE} and plan.group_by:
        sql += f" GROUP BY {_identifier(plan.group_by or '')}"
    if plan.intent in {QueryIntent.AVERAGE, QueryIntent.MINIMUM, QueryIntent.MAXIMUM, QueryIntent.SUM} and plan.group_by:
        sql += f" GROUP BY {_identifier(plan.group_by)}"
    if plan.sort:
        sql += f" ORDER BY {_identifier(plan.sort.column)} {'DESC' if plan.sort.descending else 'ASC'}"
    if plan.limit or row_query:
        sql += f" LIMIT {plan.limit or 100}"
    return GeneratedQuery(sql=sql, parameters=tuple(parameters), row_query=row_query)