from __future__ import annotations

import time
from typing import Any

from backend.repositories.database_repository import DatabaseRepository
from backend.core.config import settings
from analytics.database import connect

from .query_errors import QueryExecutionError
from .sql_generator import GeneratedQuery
from .sql_validator import SQLValidationResult


def execute_query(repository: DatabaseRepository, query: GeneratedQuery, validation: SQLValidationResult) -> dict[str, Any]:
    if not validation.read_only:
        raise QueryExecutionError("Query was not validated as read-only")
    connection = None
    started = time.perf_counter()
    try:
        connection = connect(repository.config)
        timeout_seconds = max(int(settings.query_timeout_seconds), 1)
        set_progress_handler = getattr(connection, "set_progress_handler", None)
        if callable(set_progress_handler):
            deadline = time.monotonic() + timeout_seconds
            set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        else:
            timeout_cursor = connection.cursor()
            timeout_cursor.execute(f"SET SESSION max_execution_time = {timeout_seconds * 1000}")
            timeout_cursor.close()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query.sql, query.parameters)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []
        cursor.close()
        return {"columns": columns, "rows": rows, "row_count": len(rows), "metadata": {"sql": query.sql, "parameters": list(query.parameters), "execution_time_ms": round((time.perf_counter() - started) * 1000, 2), "read_only": True}}
    except Exception as error:
        raise QueryExecutionError("The validated query could not be executed") from error
    finally:
        if connection is not None:
            connection.close()