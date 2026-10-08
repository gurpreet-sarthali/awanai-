# Dataset management (Phase 9)

AskMyData supports multiple CSV datasets through a server-controlled registry. Clients never send raw MySQL table names.

## Dataset lifecycle

| Status | Meaning |
| --- | --- |
| `UPLOADING` | Reserved for future streaming uploads |
| `VALIDATING` | CSV read and inspection in progress |
| `PROCESSING` | Cleaning and MySQL import in progress |
| `READY` | Dataset may be previewed, analyzed, and queried |
| `FAILED` | Validation or import failed; not queryable |
| `DELETING` | Deletion in progress |
| `DELETED` | Removed from active listings |

Only `READY` datasets are used for analytics, visualization, and NL-to-SQL execution.

## Upload process

1. `POST /api/v1/datasets/upload` accepts a `.csv` file and optional display name.
2. The server validates extension, size (`MAX_UPLOAD_SIZE_MB`), encoding, and shape (`MAX_CSV_ROWS`, `MAX_CSV_COLUMNS`).
3. A UUID `dataset_id` and internal table name `ds_<12 hex chars>` are generated.
4. The original bytes are stored under `data/uploads/<dataset_id>/original.csv` (internal only; not exposed in API responses).
5. The CSV is cleaned, imported into MySQL, and metadata is written to `datasets` / `dataset_columns`.
6. On success the dataset becomes `READY`. On failure it becomes `FAILED`, partial tables/files are cleaned up, and an error is returned.

## CSV validation

Inspection reports duplicate columns, empty columns, empty rows, duplicate rows, missing values, inferred column kinds, and warnings. Upload responses include structured counts and warnings.

## Cleaning

Non-destructive cleaning trims strings, normalizes column names, removes entirely empty rows, removes exact duplicate rows, and standardizes obvious boolean-like values. A cleaning report includes rows before/after, duplicates removed, and normalized column mappings. The original upload file is preserved until deletion.

## Column normalization

Original headers are mapped to SQL-safe snake_case identifiers with collision suffixes (`student_name`, `student_name_2`, …). Both original and normalized names are stored in `dataset_columns`.

## Dataset registry

MySQL tables:

- `datasets` — one row per dataset (`dataset_id`, names, counts, status, internal table reference)
- `dataset_columns` — per-column metadata linked by `dataset_id`

Built-in demo dataset:

- `dataset_id`: `demo-placement`
- display name: `Demo Placement Dataset`
- internal table: `placement`

## MySQL storage

Uploaded datasets use server-generated tables matching `^ds_[a-f0-9]{12}$`. The demo dataset continues to use the existing `placement` table.

## Dataset isolation

Every analytics, visualization, and NL-to-SQL request includes `dataset_id`. The backend resolves:

`dataset_id` → registry row → internal table → schema → operation

Clients cannot choose arbitrary table names.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/datasets/upload` | Upload CSV |
| GET | `/api/v1/datasets` | List datasets |
| GET | `/api/v1/datasets/{dataset_id}` | Dataset detail + validation summary |
| GET | `/api/v1/datasets/{dataset_id}/schema` | Column metadata |
| GET | `/api/v1/datasets/{dataset_id}/preview` | Limited row preview |
| DELETE | `/api/v1/datasets/{dataset_id}` | Delete uploaded dataset |

Legacy single-dataset endpoints under `/api/v1/dataset/*` remain for backward compatibility and default to `demo-placement`.

Integrated endpoints also accept `dataset_id`:

- `/api/v1/analytics/*`
- `/api/v1/visualizations/generate`
- `/api/v1/nlsql/validate`
- `/api/v1/nlsql/execute`
- `/api/v1/ai/*` (optional; live Gemini deferred)

## Analytics integration

Placement-specific operations remain available for the demo dataset when required columns exist. Generic operations (`overview`, `count`, `average`, `value_counts`, …) work for arbitrary uploaded datasets.

## Visualization integration

Charts accept `dataset_id` and reuse analytics results from the selected dataset.

## NL-to-SQL integration

`schema_context(dataset_id)` loads columns and categorical hints only from the selected dataset. The mock provider remains the default execution path; live Gemini is deferred.

## Security

- Strict `dataset_id` validation (UUID or built-in id)
- No client-supplied table names
- CSV-only uploads with size and shape limits
- Internal storage references are not exposed as filesystem paths
- Failed imports trigger table/file cleanup

## Current limitations

- No authentication or per-user ownership yet
- No incremental re-upload or schema evolution
- NL mock provider still understands placement-oriented vocabulary best
- Live Gemini explanation is not required for Phase 9
