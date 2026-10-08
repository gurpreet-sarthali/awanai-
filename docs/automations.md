# Scheduled Analytics and Monitoring

> TODO(PHASE-21): Phase 21 is paused. See [phase21_status.md](phase21_status.md) before extending the scheduler or adding deferred integrations.

## Architecture

Saved analytics queries persist an allowlisted structured configuration (`operation`, optional `column`, `group_by`, and `limit`). User-provided SQL, Python, shell commands, and executable expressions are rejected. Execution reuses `AnalyticsService`, the existing dataset registry, workspace sharing, and the existing analytics database connection.

`AutomationRepository` stores saved queries, schedules, durable run history, dataset profile snapshots, alert definitions/events, and worker locks. Snapshot rows contain schema hashes and calculated profile summaries, not CSV copies. Numeric profiles include min/max/mean/median/standard deviation and IQR outlier rates; category summaries are capped. Changes compare the latest profile with the prior snapshot.

Schedules support daily, weekly, and monthly local times using IANA timezones. The backend converts due times to UTC and the worker polls the database. Weekly schedules default to Monday and monthly schedules default to day 1 in the UI; API clients may select another weekday or month day.

## Run the worker

The API does not run a scheduler inside web workers. Start one dedicated worker against the same database as the API:

```powershell
python -m backend.services.automation_worker
```

Set `AUTOMATION_POLL_SECONDS` to adjust its poll interval (default 15 seconds). The worker is restartable; jobs and run history are database-backed. Atomic claims prevent two workers from running the same automation concurrently. Jobs use controlled exponential retry and stale `running` jobs are recovered after one hour. Use the same environment/database configuration for web and worker processes. A production deployment should run a supervised worker process and monitor its logs/health separately from the API.

## Permissions and billing

Creating, editing, pausing, resuming, deleting, or manually enqueuing requires the existing workspace analyst capability. Viewing requires workspace membership. The worker reloads the initiating user and checks role, exact workspace dataset sharing, dataset readiness, subscription status, `scheduled_analytics` entitlement, and analytics/report/AI usage limits on every run. A changed permission, inactive subscription, or exhausted limit blocks execution and creates a safe in-app failure notification. Team, Pro, and Enterprise default plans include scheduled analytics; Free does not.

Workspace activity logs record lifecycle events without dataset contents. Run results and snapshots are visible only through the authorized workspace APIs. CSV report downloads are workspace-authorized and neutralize spreadsheet formula prefixes.

## API

- `GET/POST /api/v1/automations/queries`
- `GET/POST /api/v1/automations`
- `GET/PATCH/DELETE /api/v1/automations/{id}`
- `POST /api/v1/automations/{id}/run`
- `GET /api/v1/automations/{id}/runs`
- `GET /api/v1/automations/{id}/runs/{run_id}/report.csv`
- `GET/POST /api/v1/automations/alerts`
- `PATCH/DELETE /api/v1/automations/alerts/{id}`
- `GET /api/v1/datasets/{dataset_id}/snapshots?workspace_id=...`
- `GET /api/v1/automations/admin/overview` (admin only)
- `GET /api/v1/automations/admin/runs` (admin only; workspace, status, time range, and limit filters)

The protected frontend page is `/automations`. Manual runs return a pending run record; the worker performs the analysis. A report includes deterministic metrics, a reusable dataset profile, snapshot comparisons, alert results, and an optional Gemini explanation generated only after the deterministic result exists. Completed runs can be downloaded as CSV summaries.

## Local configuration and limitations

No SMTP/email delivery service or provider is configured in this project, so notifications use the existing in-app notification store. Email digests and delivery retries are not enabled. Reports are available as authenticated JSON run history and CSV summaries; PDF/Excel/HTML export is not added because no existing report/export engine was found. AI summaries are optional and consume the workspace AI allowance.

Snapshots compare the current managed analytics table when a scheduled job runs. They do not watch Google Drive for file-version events; a changed Drive CSV must first pass through the existing import/refresh flow. Distribution summaries are capped to the most frequent 20 categories and are metadata, not a complete statistical-distribution test. The process uses the current plan entitlements; organizations needing custom automation quotas must add those plan fields explicitly.