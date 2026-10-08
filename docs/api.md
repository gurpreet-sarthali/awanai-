# AskMyData FastAPI Backend

## Purpose

Phase 5 connects the verified MySQL database, Phase 3 analytics engine, and Phase 4 visualization engine through a versioned read-only FastAPI API. It contains no AI, natural-language processing, authentication, user upload, or frontend logic.

## Install

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and set the local database values. `.env` is not committed and real credentials must never be placed in `.env.example`.

```text
APP_ENV=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=<your-password>
MYSQL_DATABASE=askmydata
```

## Start

```powershell
.venv\Scripts\uvicorn.exe backend.main:app --reload
```

Base URL: `http://127.0.0.1:8000`

Interactive docs:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Endpoints

### Health

`GET /api/v1/health`

```json
{"status": "ok", "service": "AskMyData API"}
```

`GET /api/v1/health/database`

```json
{"status": "ok", "database": "reachable"}
```

Database failures return HTTP `503` without credentials or connection details.

### Dataset

- `GET /api/v1/dataset/summary` returns table, row count, column count, missing values, available columns, and validation warnings.
- `GET /api/v1/dataset/schema` returns column names, MySQL data types, nullable flags, and primary-key flags.
- `GET /api/v1/dataset/sample?limit=5` returns at most 20 sample rows. The full dataset is never returned by this endpoint.

### Analytics

- `GET /api/v1/analytics/summary`
- `GET /api/v1/analytics/placement`
- `GET /api/v1/analytics/internship`
- `GET /api/v1/analytics/cgpa`
- `GET /api/v1/analytics/projects`
- `GET /api/v1/analytics/communication`

Generic approved operation:

`POST /api/v1/analytics/run`

```json
{"operation": "placement_by_internship"}
```

Allowed operations are `overall_placement_rate`, `placement_by_internship`, `placement_by_cgpa_group`, `placement_by_project_group`, `placement_by_communication`, and `average_metrics_by_placement`. Arbitrary SQL and Python are not accepted.

### Visualizations

`POST /api/v1/visualizations/generate`

```json
{
  "chart_type": "bar",
  "analysis_operation": "placement_by_internship"
}
```

Allowed chart types are `bar`, `line`, `pie`, `histogram`, `scatter`, and `box`. The request can select only approved analytics operations; it cannot submit columns, Python, SQL, Matplotlib code, or filesystem paths.

Successful response:

```json
{
  "status": "success",
  "chart_type": "bar",
  "title": "Placement Rate by Internship Experience",
  "file_url": "/api/v1/visualizations/files/api_placement_by_internship.bar.png",
  "metadata": {"row_count": 2, "warnings": []}
}
```

Generated files are served only from the controlled `visualization/results/` directory at `/api/v1/visualizations/files/<filename>`.

## Errors

```json
{"error": "invalid_operation", "detail": "Unsupported analytics operation: arbitrary_sql"}
```

- `400`: unsupported approved operation or chart request.
- `422`: malformed request body or query parameters.
- `503`: database, analytics, or visualization service unavailable.
- `500`: unexpected internal error with a generic message.

Passwords, stack traces, absolute filesystem paths, and database connection details are not returned to API clients.

## CORS

`CORS_ORIGINS` accepts a comma-separated list. Local development defaults to `http://localhost:5173`; set it to the actual frontend origin later rather than using unrestricted `*`.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

The API tests use dependency-injected repository/service doubles. The end-to-end smoke check uses the real MySQL database and real Phase 3/4 services.