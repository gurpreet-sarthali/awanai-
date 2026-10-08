import pandas as pd

from backend.ai.nlsql.schema_context import SchemaContext


def test_schema_description_contains_real_contract():
    context = SchemaContext("askmydata", "placement", "demo-placement", ({"name": "CGPA", "data_type": "decimal", "nullable": True, "primary_key": False},), {"Placement": ("No", "Yes")})
    assert "TABLE: placement" in context.description()
    assert "CGPA" in context.description()