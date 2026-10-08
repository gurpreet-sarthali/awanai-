from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from .query_errors import SQLValidationError
from .schema_context import SchemaContext

FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|CALL|LOAD\s+DATA|INTO\s+OUTFILE)\b", re.IGNORECASE)
COMMENT = re.compile(r"(--|/\*|\*/|#)")


@dataclass(frozen=True)
class SQLValidationResult:
    sql: str
    read_only: bool
    row_query: bool


def validate_sql(sql: str, schema: SchemaContext, *, row_query: bool = False, max_query_length: int = 10_000, max_result_rows: int = 1_000) -> SQLValidationResult:
    if not sql or len(sql) > max_query_length:
        raise SQLValidationError("SQL is empty or exceeds the configured query length limit")
    if COMMENT.search(sql) or ";" in sql.rstrip().rstrip(";"):
        raise SQLValidationError("Comments and multiple SQL statements are not allowed")
    if FORBIDDEN.search(sql):
        raise SQLValidationError("Only read-only SELECT queries are allowed")
    try:
        # SQLGlot validates syntax; parameter placeholders are replaced only in
        # this parse copy and remain parameterized in the executable SQL.
        parsed = sqlglot.parse(re.sub(r"%s", "NULL", sql), read="mysql")
    except Exception as error:
        raise SQLValidationError("SQL could not be parsed") from error
    if len(parsed) != 1 or not isinstance(parsed[0], (exp.Select, exp.With)):
        raise SQLValidationError("Only SELECT or WITH ... SELECT queries are allowed")
    table_names = {table.name for table in parsed[0].find_all(exp.Table)}
    if table_names != {schema.table}:
        raise SQLValidationError("Query references an unauthorized table")
    identifiers = {identifier.name for identifier in parsed[0].find_all(exp.Column)}
    if not identifiers.issubset(schema.column_names | {"count", "average", "minimum", "maximum", "sum", "placement_rate"}):
        raise SQLValidationError("Query references an unauthorized column")
    if row_query:
        limit = parsed[0].find(exp.Limit)
        if limit is None or int(limit.expression.name) > max_result_rows:
            raise SQLValidationError("Row-returning queries require a safe LIMIT")
    return SQLValidationResult(sql=sql, read_only=True, row_query=row_query)