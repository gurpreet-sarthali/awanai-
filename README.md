# AI-Powered Data Analytics Platform

## Current phase

**Phase 1 - Dataset Understanding and Cleaning**

This phase prepares the data foundation for the future analytics platform. The first dataset will be a Kaggle College Placement CSV. The raw file is inspected and copied into a conservative cleaned version without changing the original data.

## Project goal

The eventual system will let users select a dataset, ask questions in natural language, turn those questions into validated analytics plans, query data, calculate results with Python/Pandas/NumPy, generate visualizations, and explain the actual results with an LLM. Authentication, Gemini integration, database storage, and the application UI belong to later phases.

## Phase 1 files

- `data/raw/` - place the original Kaggle CSV here.
- `data/processed/` - generated cleaned datasets go here.
- `data/sample/` - optional small, non-sensitive sample datasets.
- `scripts/inspect_dataset.py` - prints a dataset profile.
- `scripts/clean_dataset.py` - creates a cleaned copy and reports every decision.
- `docs/data_dictionary.md` - template for documenting confirmed column meanings.

## Setup

Use Python 3.11 or newer, then install the Phase 1 dependencies:

```text
python -m pip install -r requirements.txt
```

## Add the dataset

Place the Kaggle CSV at `data/raw/placement.csv`. The CSV is not included in this workspace yet, so do not run the commands below until the file has been added.

## Inspect the dataset

```text
python scripts/inspect_dataset.py data/raw/placement.csv
```

The inspection prints row and column counts, names, types, sample rows, missing values, duplicates, categorical value counts, numerical statistics, and possible ID, boolean-like, and date-like columns.

## Clean the dataset

```text
python scripts/clean_dataset.py data/raw/placement.csv
```

The cleaned file is written to `data/processed/placement_cleaned.csv`. Exact duplicate rows are removed, column names are standardized to snake_case, and surrounding whitespace in string values is trimmed. Missing values and suspicious numeric-looking values are reported but not filled, dropped, or converted automatically because their meaning needs confirmation.

An alternate output path can be supplied when needed:

```text
python scripts/clean_dataset.py data/raw/placement.csv --output data/processed/another_name.csv
```

## Expected output

Inspection produces a readable terminal profile. Cleaning reports rows before and after cleaning, duplicates removed, trimmed values, missing values remaining, suspicious numeric values, and the output path. The raw CSV remains unchanged.

## Future architecture constraint

Later phases must keep the execution boundary explicit: a future LLM may produce a structured analytics plan, but validated backend code will execute the plan. The LLM must not directly execute arbitrary Python or SQL.

## Phase 5 FastAPI backend

The FastAPI orchestration layer is documented in `docs/api.md`. Configure the variables in `.env.example`, then start it with:

```text
.venv\Scripts\uvicorn.exe backend.main:app --reload
```

The API exposes versioned health, dataset, analytics, and visualization endpoints under `/api/v1/`. It does not implement authentication or AI integration yet.

## Phase 7 Gemini integration

Phase 7 adds server-side Gemini planning and result explanation. Copy `.env.example` to `.env`, set `GEMINI_API_KEY`, and keep the key server-side. The React Ask page calls `POST /api/v1/ai/analyze`; FastAPI validates Gemini's plan, executes only approved Phase 3/4 operations, and returns grounded results. No arbitrary SQL or Python is accepted.

```text
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

See `docs/gemini_integration.md` for the architecture, allowlists, rate limits, testing, and limitations.

## Phase 8 safe natural-language SQL

Phase 8 adds a provider-independent, deterministic query-plan and safe SQL pipeline. It uses a clearly labeled mock/test provider because live Gemini execution is intentionally deferred. The endpoints are `/api/v1/nlsql/validate` and `/api/v1/nlsql/execute`; arbitrary SQL, Python, and destructive database statements are rejected. See `docs/natural_language_sql.md`.

## Phase 9 user CSV datasets

Phase 9 makes AskMyData dataset-agnostic. Users upload CSV files, the backend validates and imports them into isolated MySQL tables, and every analytics, chart, and NL-to-SQL request is scoped by `dataset_id`.

Supported upload type: `.csv`

Configurable limits (see `.env.example`):

- `MAX_UPLOAD_SIZE_MB`
- `MAX_CSV_ROWS`
- `MAX_CSV_COLUMNS`
- `DATASET_PREVIEW_LIMIT`

Dataset APIs:

- `POST /api/v1/datasets/upload`
- `GET /api/v1/datasets`
- `GET /api/v1/datasets/{dataset_id}`
- `GET /api/v1/datasets/{dataset_id}/schema`
- `GET /api/v1/datasets/{dataset_id}/preview`
- `DELETE /api/v1/datasets/{dataset_id}`

The built-in demo dataset remains available as `demo-placement` (`Demo Placement Dataset`). The React `/dataset` page supports upload, schema, preview, and delete. The sidebar dataset selector sends `dataset_id` with analytics and Ask-your-data requests. Live Gemini is not required for Phase 9; the Ask page uses the mock NL-to-SQL provider.

See `docs/dataset_management.md` for lifecycle, isolation, storage, and limitations.

## Phase 22 — Developer API, API Keys, Webhooks & External Integrations

Phase 22 makes AskMyData a fully-featured API platform.

### API Key management

Workspace administrators can create, rotate, and revoke API keys from the **Developer** page (`/developer`):

```
POST  /api/v1/developer/api-keys           Create a new API key (shown once)
GET   /api/v1/developer/api-keys           List workspace API keys
POST  /api/v1/developer/api-keys/{id}/revoke   Immediately revoke a key
POST  /api/v1/developer/api-keys/{id}/rotate   Issue replacement key (with optional grace period)
GET   /api/v1/developer/usage              View API usage summary
```

**Key format:** `ask_live_<32-char-secure-random>` in production, `ask_test_<...>` in development.

Raw keys are **never stored**. Only the SHA-256 hash is persisted.

### Authentication

```
Authorization: Bearer ask_live_<key>
```

API keys are accepted only via the `Authorization` header — not URL query parameters.

### Scopes

Keys are granted least-privilege scopes:

| Scope | Permission |
|---|---|
| `datasets:read` | List/view dataset metadata |
| `datasets:write` | Upload and manage datasets |
| `analytics:read` | View saved results |
| `analytics:run` | Execute structured analytics |
| `analytics:question` | Ask natural-language questions |
| `reports:read` | View reports |
| `workspace:read` | View workspace info |
| `webhooks:read/write` | Manage webhooks |

### Public API endpoints

```
GET  /api/v1/public/datasets                List accessible datasets
GET  /api/v1/public/datasets/{id}           Get dataset metadata
GET  /api/v1/public/workspace               Get workspace info
POST /api/v1/public/analytics/query         Run structured analytics
POST /api/v1/public/analytics/question      Ask a natural-language question
```

Every response includes `X-Request-ID` and `X-RateLimit-*` headers.

### Rate limiting

Rate limits are enforced per workspace and per API key per hour, based on subscription plan (Free: 100/hr, Pro: 1000/hr, Team: 5000/hr, Enterprise: 10000/hr). HTTP 429 is returned with `X-RateLimit-Remaining: 0` when exceeded.

### Webhooks

```
GET    /api/v1/developer/webhooks                        List webhooks
POST   /api/v1/developer/webhooks                        Create webhook
PATCH  /api/v1/developer/webhooks/{id}                   Update webhook
DELETE /api/v1/developer/webhooks/{id}                   Delete webhook
POST   /api/v1/developer/webhooks/{id}/rotate-secret     Rotate signing secret
POST   /api/v1/developer/webhooks/{id}/test              Send test event
GET    /api/v1/developer/webhooks/{id}/deliveries         Delivery history
```

Webhook deliveries are signed with `HMAC-SHA256` via the `X-AskMyData-Signature` header. Webhook URLs are validated against SSRF — private IPs, localhost, and cloud metadata endpoints are blocked. Delivery is retried up to 3 times with exponential backoff.

### Required environment variable

```bash
# Generate once and keep secret:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Then set in .env:
WEBHOOK_ENCRYPTION_KEY=<output>
```

### Developer dashboard

Navigate to `/developer` in the UI for:

- API key management (create, copy, rotate, revoke)
- Webhook management (create, test, delivery history)
- API usage statistics
- Inline documentation and code examples

See `docs/developer_api.md` for the complete API reference.