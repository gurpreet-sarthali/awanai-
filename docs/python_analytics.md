# Python/Pandas Analytics Engine

## Purpose

Phase 3 provides a reusable Python analytics engine for the verified AskMyData placement dataset. It loads data from MySQL, validates it without silently changing rows, calculates Pandas/NumPy-compatible metrics, and returns JSON-safe structured results for a future analytics-plan layer.

No frontend, AI integration, chart library, authentication, API, or deployment code is included.

## Verified data source

- Database: `askmydata`
- Table: `placement`
- Rows loaded: 10,000
- Columns: `College_ID`, `IQ`, `Prev_Sem_Result`, `CGPA`, `Academic_Performance`, `Internship_Experience`, `Extra_Curricular_Score`, `Communication_Skills`, `Projects_Completed`, `Placement`
- Live NULL count: 0 across the verified table.
- `College_ID` has duplicate values and is not treated as a unique key.

The CGPA range is 4.54-10.46 and the project range is 0-5. Therefore the engine uses the documented groups `Below 6`, `6 to <7`, `7 to <8`, `8 to <9`, `9+`, and project groups `0`, `1-2`, `3-4`, `5+`.

## Structure

- `analytics/database.py` - environment-based connection configuration and connection handling.
- `analytics/loader.py` - loads the verified table into a Pandas DataFrame and closes connections.
- `analytics/cleaning.py` - creates an analysis copy and trims status text only; it does not alter the source database.
- `analytics/validation.py` - reports missing values, duplicate IDs, invalid numeric ranges, and unexpected statuses.
- `analytics/metrics.py` - basic counts, rates, and numeric statistics.
- `analytics/placement.py` - placement and internship comparisons.
- `analytics/grouping.py` - group assignment and grouped placement rates/averages.
- `analytics/comparisons.py` - observational differences and highest-rate groups.
- `analytics/structured.py` - machine-readable scalar and grouped result shapes.
- `scripts/run_analytics.py` - live summary runner.
- `scripts/compare_sql_pandas.py` - live SQL/Pandas comparison runner.

## Database connection

Set these environment variables in the terminal before running the live scripts. Values are never hardcoded in the project:

```powershell
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "root"
$env:MYSQL_PASSWORD = "<your-password>"
$env:MYSQL_DATABASE = "askmydata"
```

The connector raises a clear configuration error for missing variables and a connection error for database failures. Connections are closed after loading or querying.

## Loading and validation

`load_placement_data()` selects the verified columns, preserves SQL NULLs as Pandas missing values, reports shape through `dataframe_shape()`, and does not clean data implicitly. `validate_data()` returns a dictionary containing `valid`, row and column counts, missing-value counts, duplicate-ID count, invalid numeric counts, unexpected categories, and warnings.

Validation checks include non-negative projects, positive IQ and CGPA, expected `Yes`/`No` statuses, and missing values. These checks report findings; they do not drop or impute records.

## Metrics and structured output

The engine implements the Phase 2 metrics with Pandas calculations: counts, placement rate, internship rates, averages, minimums, maximums, grouped rates, placed-versus-not-placed averages, observed differences, and highest observed groups.

Scalar output follows this shape:

```json
{"metric": "placement_rate", "value": 16.59, "unit": "percent"}
```

Grouped output follows this shape:

```json
{"metric": "placement_rate", "group_by": "Internship_Experience", "results": [{"group": "Yes", "value": 16.32}]}
```

The command runner saves a complete machine-readable result at `analytics/results/placement_analytics.json` after a successful live run.

## SQL versus Pandas validation

Run `scripts/compare_sql_pandas.py` after setting the environment variables. It calculates the same totals, counts, rates, average CGPA, CGPA groups, and project groups independently through SQL and Pandas, then prints `PASS` only when the values match within `1e-4`. The tolerance accounts for MySQL's rounded DECIMAL percentage output.

## Commands

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the analytics summary:

```powershell
python scripts/run_analytics.py
```

Compare SQL and Pandas:

```powershell
python scripts/compare_sql_pandas.py
```

Run unit tests:

```powershell
python -m pytest tests -q
```

## Limitations

- Validation rules are dataset checks, not causal or predictive claims.
- Duplicate `College_ID` values are reported and not removed.
- No chart generation is included in Phase 3.
- SQL/Pandas comparison currently covers key scalar metrics; grouped results are separately tested and generated.
- The engine assumes the verified table and columns from the current database inspection.