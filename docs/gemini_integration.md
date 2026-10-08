# Phase 7 Gemini Integration

## Purpose

Phase 7 connects the React Ask Your Data experience to a server-side Gemini planner and explainer. Gemini proposes a structured intent only; the FastAPI backend validates it and executes existing Phase 3 analytics and Phase 4 visualization services. Gemini never receives credentials and never executes SQL, Python, shell commands, or filesystem operations.

## Setup

Install the official SDK through the project requirements:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure:

```text
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
AI_MAX_REQUESTS_PER_MINUTE=10
AI_MAX_REQUESTS_PER_DAY=100
```

The API key is read only by `backend/services/gemini_service.py`. It is not in the frontend environment, response payloads, logs, or source code. `.env` is ignored by Git.

## Architecture

```text
React question
  -> POST /api/v1/ai/analyze
  -> GeminiService.plan()
  -> Pydantic + semantic allowlist validation
  -> AnalyticsService.run_operation()
  -> VisualizationService.generate() when approved
  -> GeminiService.explain(actual_result)
  -> structured response to React
```

The planner and explainer prompts live in `backend/ai/prompts/`. The Google `google-genai` SDK requests JSON output using a Pydantic response schema. The application still validates operation names, filter fields, chart types, and unsupported intent after parsing.

## Plan schema

```json
{
  "intent": "comparison",
  "operation": "placement_by_internship",
  "filters": [],
  "chart_type": "bar",
  "needs_chart": true
}
```

Supported intents are `lookup`, `comparison`, `distribution`, `relationship`, and `unsupported`. Filters must reference real dataset columns, and current approved operations reject filters because the existing analytics engine does not expose filtered execution yet.

## Approved operations

- `overall_placement_rate`
- `placement_by_internship`
- `placement_by_cgpa_group`
- `placement_by_project_group`
- `placement_by_communication`
- `average_metrics_by_placement`

Only these operations are passed to `AnalyticsService`. No model output is treated as executable code.

## Endpoints

### `POST /api/v1/ai/plan`

Request:

```json
{"question": "What is the placement rate for students with internships?"}
```

Returns the validated question and plan without executing analytics.

### `POST /api/v1/ai/analyze`

Request:

```json
{"question": "What is the placement rate for students with internships?"}
```

The endpoint loads the real dataset schema, asks Gemini for a plan, executes the approved operation against MySQL/Pandas, optionally generates a Phase 4 chart, and asks Gemini to explain only the actual result.

Response shape:

```json
{
  "question": "What is the placement rate for students with internships?",
  "answer": "...",
  "metrics": [{"group": "Yes", "value": 16.321897073662967, "count": 3964}],
  "chart": {"file_url": "/api/v1/visualizations/files/api_placement_by_internship.bar.png"},
  "insights": ["..."],
  "recommendations": ["..."],
  "warnings": ["This analysis shows observed association and does not establish causation."],
  "analysis": {"operation": "placement_by_internship", "filters": [], "chart_type": "bar", "needs_chart": true}
}
```

Absolute filesystem paths are removed before the response reaches clients.

## Unsupported questions and errors

Questions asking for unavailable columns, such as a nonexistent branch field, are rejected with a safe `400` response. Missing API keys return `503 ai_configuration_missing`. Gemini failures return `503 ai_unavailable`; rate limits return `429 ai_rate_limit`. No stack traces, prompts, API keys, or database credentials are returned.

## Rate limiting

`AIRateLimiter` is an in-process development limiter controlled by `AI_MAX_REQUESTS_PER_MINUTE` and `AI_MAX_REQUESTS_PER_DAY`. An analyze request consumes one allowance for planning and one for explanation. This protects low-cost development use but is not a distributed production limiter.

## Grounding and recommendations

Programmatic validation warnings are retained, including duplicate `College_ID` warnings and the causal limitation. Gemini receives actual result payloads and those warnings, and the explainer prompt prohibits invented metrics, sample sizes, causes, or warnings. Recommendations are framed as cautious observations, not guarantees.

## Frontend integration

The React `/ask` page now calls `POST /api/v1/ai/analyze`, shows `Analyzing…`, renders the returned answer, chart, insights, recommendations, warnings, and structured analysis details. No `VITE_GEMINI_API_KEY` exists or should be added.

## Testing

Gemini calls are mocked in the test suite. Coverage includes valid plans, invalid operations, unknown columns, missing keys, orchestration, safe chart URLs, endpoint responses, and the existing Phase 3/4 regression tests:

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

Real Gemini integration is intentionally opt-in and requires `GEMINI_API_KEY`; no key is committed or used by automated tests.

## Limitations

- Natural-language understanding is limited to the approved operation set.
- Filtered analytics are rejected until a later validated filtering phase adds backend support.
- The in-process rate limiter resets when the server restarts and is not suitable for multiple workers.
- Gemini responses remain probabilistic, so semantic validation and actual backend execution are mandatory.