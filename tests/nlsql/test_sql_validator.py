import pytest

from backend.ai.nlsql.query_errors import SQLValidationError
from backend.ai.nlsql.schema_context import SchemaContext
from backend.ai.nlsql.sql_validator import validate_sql


def schema():
    return SchemaContext("askmydata", "placement", "demo-placement", ({"name": "CGPA", "data_type": "decimal", "nullable": True, "primary_key": False},), {})


@pytest.mark.parametrize("sql", ["DROP TABLE placement", "DELETE FROM placement", "UPDATE placement SET CGPA=10", "SELECT * FROM placement; DROP TABLE placement", "SELECT * FROM placement -- bypass"])
def test_malicious_sql_is_rejected(sql):
    with pytest.raises(SQLValidationError):
        validate_sql(sql, schema(), row_query=True)


def test_safe_select_requires_limit_for_rows():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT `CGPA` FROM `placement`", schema(), row_query=True)


def test_safe_aggregate_is_accepted():
    result = validate_sql("SELECT AVG(`CGPA`) AS `average` FROM `placement`", schema())
    assert result.read_only is True