import pandas as pd
import pytest

from backend.ai.nlsql.intent_schema import FilterOperator, QueryFilter, QueryIntent, QueryPlan
from backend.ai.nlsql.query_plan import validate_query_plan
from backend.ai.nlsql.query_errors import QueryPlanValidationError
from backend.ai.nlsql.schema_context import SchemaContext


def schema():
    return SchemaContext("askmydata", "placement", "demo-placement", ({"name": "CGPA", "data_type": "decimal", "nullable": True, "primary_key": False}, {"name": "Placement", "data_type": "varchar", "nullable": True, "primary_key": False}), {"Placement": ("No", "Yes")})


def test_valid_average_plan():
    plan = QueryPlan(intent=QueryIntent.AVERAGE, metric_column="CGPA", filters=[QueryFilter(column="Placement", operator=FilterOperator.EQUAL, value="Yes")])
    assert validate_query_plan(plan, schema()) == plan


def test_unknown_column_rejected():
    plan = QueryPlan(intent=QueryIntent.AVERAGE, metric_column="Branch")
    with pytest.raises(QueryPlanValidationError):
        validate_query_plan(plan, schema())