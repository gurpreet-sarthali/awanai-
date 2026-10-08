# Phase 8: Natural Language to Safe SQL

## Status

Phase 8 adds provider-independent natural-language-to-SQL infrastructure. Live Gemini execution is intentionally deferred until the final project stage. The current mock provider is explicitly labeled `MOCK / TEST PROVIDER` and supports only predefined benchmark-style questions.

## Architecture

```text
Natural-language question
  -> provider interface
  -> strict QueryPlan
  -> schema/operation/value validation
  -> deterministic parameterized SQL generator
  -> SQLGlot read-only validator
  -> MySQL executor
  -> normalized rows + query metadata
```

The SQL layer does not know whether a future plan came from Gemini, another provider, or the current mock provider.

Query limits are configurable through `MAX_RESULT_ROWS`, `MAX_QUERY_LENGTH`, and `QUERY_TIMEOUT_SECONDS`. The current executor enforces the first two through plan/SQL validation; connector-level timeout enforcement is reserved for a future database infrastructure hardening pass.

## Schema context

`schema_context.py` obtains the live `askmydata.placement` schema through the existing read-only repository. It includes database/table, columns, MySQL types, nullable flags, primary-key flags, and observed categorical values. Identifiers are accepted only when present in this context.

The current verified table columns are `College_ID`, `IQ`, `Prev_Sem_Result`, `CGPA`, `Academic_Performance`, `Internship_Experience`, `Extra_Curricular_Score`, `Communication_Skills`, `Projects_Completed`, and `Placement`.

## Query-plan schema

```json
{
  "intent": "average",
  "metric_column": "CGPA",
  "group_by": null,
  "select_columns": [],
  "filters": [{"column": "Placement", "operator": "=", "value": "Yes"}],
  "sort": null,
  "limit": null
}
```

Pydantic forbids unknown fields. Supported intents are `select_rows`, `count`, `average`, `minimum`, `maximum`, `sum`, `placement_rate`, `group_by`, `filter`, `sort`, `limit`, `distinct`, and `comparison`.

## SQL generation and parameterization

`generate_sql()` is deterministic and accepts only a validated `QueryPlan`. Table and column identifiers are backtick-quoted from the live schema allowlist. User-derived values become MySQL connector `%s` parameters.

Example:

```text
Question: What is the average CGPA of placed students?
Plan: average(CGPA), filter Placement = Yes
SQL: SELECT AVG(`CGPA`) AS `average` FROM `placement` WHERE `Placement` = %s
Parameters: ["Yes"]
```

No raw SQL is accepted from the question or API.

## SQL validation rules

The SQL validator uses SQLGlot plus application checks. It rejects:

- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `CREATE`, `REPLACE`, `GRANT`, `REVOKE`, `CALL`.
- `LOAD DATA`, `INTO OUTFILE`, comments, and multiple statements.
- Unauthorized tables, schemas, columns, and joins.
- Row queries without a safe `LIMIT`.
- Queries exceeding `MAX_QUERY_LENGTH`.

Only `SELECT` and safely parsed `WITH ... SELECT` statements are allowed. The executor also requires a validator result marked `read_only`.

## Query execution and metadata

`execute_query()` closes the cursor and connection, captures execution time, and returns:

```json
{
  "columns": ["average"],
  "rows": [{"average": 8.592483423749247}],
  "row_count": 1,
  "metadata": {
    "sql": "SELECT AVG(`CGPA`) AS `average` FROM `placement` WHERE `Placement` = %s",
    "parameters": ["Yes"],
    "execution_time_ms": 12.4,
    "read_only": true
  }
}
```

Passwords and connection details are never included.

## API endpoints

### `POST /api/v1/nlsql/validate`

Accepts a natural-language question and uses the deterministic mock provider to return the plan, generated SQL, safe parameters, and read-only validation metadata. It does not execute the query.

```json
{"question": "What is the average CGPA of placed students?"}
```

### `POST /api/v1/nlsql/execute`

Accepts only an internal Pydantic `QueryPlan`, then validates, generates, validates again, and executes it. It does not accept a SQL string.

## Mock provider and unsupported questions

The mock provider supports the Phase 8 benchmark vocabulary: placement rates, internship/project/communication groups, averages, minimum/maximum values, counts, placed/non-placed filters, and CGPA-above row selection. It rejects destructive language and unavailable fields such as branch or company with a controlled explanation.

It is not AI and must not be presented as Gemini. Future Gemini integration can implement the same `plan(question) -> QueryPlan` interface without changing SQL execution.

## Benchmark and security tests

The repository includes all 30 existing Phase 2 benchmark questions in `backend/ai/nlsql/benchmark.py`. The test suite exercises the supported mock-provider subset, verifies the complete 30-question inventory, and covers real plan validation, parameterized SQL checks, executor normalization, API validation, unsupported branch/company questions, and malicious inputs including `DROP`, `DELETE`, `UPDATE`, multiple statements, and SQL comments.

Run without `GEMINI_API_KEY`:

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

## Gemini later

Live Gemini execution is intentionally deferred until the final project stage. A future provider may produce a `QueryPlan`, but the backend must continue to validate the plan, generate deterministic SQL, validate read-only safety, and execute approved queries itself.