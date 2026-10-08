# SQL Analytics Layer

## Status

This is the SQL analytics foundation for AskMyData. The placement table has now been imported and the core inspection, aggregate, grouped, CASE, CTE, and window-function queries have been executed against the live database.

## Database and table

- Database: `askmydata` (confirmed live on the local MySQL server).
- Tables in `askmydata`: `placement` (confirmed live).
- Table used by the query files: `placement`.
- Expected columns: `College_ID`, `IQ`, `Prev_Sem_Result`, `CGPA`, `Academic_Performance`, `Internship_Experience`, `Extra_Curricular_Score`, `Communication_Skills`, `Projects_Completed`, `Placement`.

The table was created and loaded from `data/raw/placement.csv` using `sql/00_setup_placement_table.sql`. The live schema and values were then verified with `sql/00_database_inspection.sql`.

## Current inspection evidence

The live table contains 10,000 rows and zero NULL values in all ten columns. Live values include `Yes`/`No` for internship and placement, IQ 41-158, previous-semester result 5.00-10.00, CGPA 4.54-10.46, academic performance 1-10, extra-curricular score 0-10, communication skills 1-10, and projects completed 0-5.

The live table has 9,900 duplicate-ID excess records (`COUNT(*) - COUNT(DISTINCT College_ID)`), so `College_ID` must not be treated as a unique student key.

## Representative live results

These aggregate results were executed against `askmydata.placement`:

| Metric | Result |
|---|---:|
| Total students | 10,000 |
| Placed students | 1,659 |
| Not placed students | 8,341 |
| Overall placement rate | 16.59% |
| Internship placement rate | 16.32% |
| No-internship placement rate | 16.77% |
| Internship minus no-internship rate difference | -0.44 percentage points |
| Average CGPA | 7.532379 |
| Average IQ | 99.4718 |
| Average projects | 2.5134 |

Placed versus non-placed averages:

| Placement status | Average CGPA | Average IQ | Average projects | Average communication | Average academic performance |
|---|---:|---:|---:|---:|---:|
| No | 7.32 | 97.55 | 2.35 | 5.14 | 5.57 |
| Yes | 8.59 | 109.12 | 3.35 | 7.66 | 5.45 |

The `8 to <9` CGPA group had the highest observed placement rate at 33.97%. The `7-10` communication group had 31.32%, and the `5+` project group had 23.74%. These are associations in this dataset, not causal conclusions.

## How to validate

1. Import the placement data into `askmydata` using `sql/00_setup_placement_table.sql` if setting up another environment.
2. Connect to MySQL with an account that can read `askmydata`.
3. Run `sql/00_database_inspection.sql`.
4. Confirm the table name, column types, NULL behavior, status values, and numeric ranges.
5. Run each analytics file and save selected outputs under `sql/results/` only after reviewing them for sensitive data.

The inspection file includes database confirmation, table listing, schema inspection, row count, NULL counts, distinct statuses, duplicate ID checks, and numeric ranges.

## Basic analytics

`sql/01_basic_analytics.sql` contains 14 queries for total records, placement counts, internship counts, and minimum, maximum, and average values for CGPA, IQ, and projects completed. These establish the descriptive baseline that future AI-generated SQL can be compared against.

Example:

```sql
SELECT AVG(`CGPA`) AS average_cgpa
FROM `placement`;
```

Expected result type: one row with one numeric metric.

## Placement analytics

`sql/02_aggregate_analytics.sql` contains 12 queries for overall placement rate, internship comparisons, placed versus non-placed averages, and communication/academic comparisons.

Placement rates use conditional aggregation and `NULLIF`:

```sql
SELECT 100.0 * SUM(`Placement` = 'Yes') / NULLIF(COUNT(`Placement`), 0) AS placement_rate_pct
FROM `placement`;
```

Expected result type: a percentage, count, or average. The calculation avoids division by zero and ignores NULL placement values in the denominator where appropriate.

## Grouping analytics

`sql/03_group_by_analytics.sql` contains 10 queries grouped by internship status, placement status, academic performance, communication score, extra-curricular score, project count, and CGPA range.

## CASE WHEN analytics

`sql/04_case_when_analytics.sql` contains six category queries. Categories are based on the observed CSV ranges:

- CGPA: below 6, 6 to less than 7, 7 to less than 8, 8 to less than 9, and 9+.
- Projects: 0, 1-2, 3-4, and 5+.
- Communication: 1-3, 4-6, and 7-10.
- Academic performance: 1-3, 4-6, and 7-10.

These ranges must be reviewed against the live schema before being treated as a stable business definition.

## Comparison analytics

The comparison queries answer association questions such as:

- Whether internship groups have different observed placement rates.
- Which CGPA, project, communication, or academic group has the highest observed rate.
- Whether placed students have different average projects, communication scores, CGPA, or IQ.

They describe differences in this dataset only. They do not claim that internships, projects, or scores cause placement.

## Advanced SQL

`sql/05_advanced_analytics.sql` contains seven meaningful examples using:

- `HAVING` to require usable group sizes.
- CTEs to compare group rates and the overall rate.
- A window `RANK()` to rank CGPA groups.
- Conditional aggregation for side-by-side comparisons.
- NULL-safe denominators.
- Ordering by calculated metrics.
- A data-quality check for unexpected placement values.

The window-function query requires a MySQL version that supports window functions, and the CTE queries require a MySQL version that supports CTEs.

## Benchmark questions

`sql/06_benchmark_questions.sql` contains 30 natural-language questions, each followed by a reference SQL query. The set covers counts, rates, averages, group comparisons, CASE-based ranges, highest-rate groups, association questions, and duplicate-ID checks.

Each benchmark has:

- A user question in a SQL comment.
- A correct reference query.
- An expected scalar or grouped result shape implied by the selected columns.
- Relevant columns in the query.
- A concise purpose through the question wording and aliases.

These references are intended to become regression tests for a future structured analytics-plan system. They do not implement natural-language-to-SQL.

## Query inventory

| File | Query count | Purpose |
|---|---:|---|
| `00_setup_placement_table.sql` | Setup/import script | Create and load the current CSV |
| `00_database_inspection.sql` | 8 logical checks | Verify live database and schema |
| `01_basic_analytics.sql` | 14 | Descriptive metrics |
| `02_aggregate_analytics.sql` | 12 | Placement and average comparisons |
| `03_group_by_analytics.sql` | 10 | Grouped rates and averages |
| `04_case_when_analytics.sql` | 6 | Meaningful category analysis |
| `05_advanced_analytics.sql` | 7 | CTE, HAVING, window, and quality examples |
| `06_benchmark_questions.sql` | 30 | Natural-language benchmark references |

The analytics library contains **79 analytics/reference queries**, excluding the eight logical inspection checks and the setup/import script.

## Assumptions

- `Placement = 'Yes'` means placed and `Placement = 'No'` means not placed; this must be confirmed against the live data.
- `Internship_Experience = 'Yes'` and `Internship_Experience = 'No'` are the expected status values; the inspection query verifies them.
- The table name is `placement`, confirmed after import into `askmydata`.
- Rates are percentages from 0 to 100, not fractions from 0 to 1.
- NULL placement values are excluded from placement-rate denominators.
- `College_ID` is not assumed to be unique because the available CSV contains duplicate values.

## Limitations

- Live MySQL execution has been completed for the core, grouped, CASE, CTE, window-function, and all 30 benchmark queries. The aggregate outputs are saved under `sql/results/`.
- The actual MySQL placement schema was confirmed as `VARCHAR`, `INT`, `DECIMAL`, and `TINYINT` fields with the expected ten columns.
- Observational comparisons do not establish causation.
- Small groups can produce unstable rates; query outputs should include sample counts before interpretation.
- CGPA and score group boundaries are analytical conveniences, not validated domain standards.
- Aggregate-only grouped results were saved under `sql/results/representative_grouped_results.tsv`; no student-level information was saved.

## Future AskMyData use

This layer provides trusted reference queries and expected result shapes for a later analytics-plan validator. A future model may map a user question to a structured plan, but validated application code should select or generate approved SQL and execute it. The model should not directly execute arbitrary SQL or Python.