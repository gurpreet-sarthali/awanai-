# Phase 21 Status: Paused

Phase 21 implementation is intentionally paused to prioritize independent project work. Existing code remains in place; do not revert it.

## Completed

- Added persistence for structured saved queries, schedules, runs, snapshots, alerts, alert events, and worker locks.
- Added an allowlisted deterministic analytics configuration; arbitrary SQL/Python is not accepted.
- Added daily, weekly, and monthly timezone-aware scheduling, durable manual runs, exclusive worker claims, stale-run recovery, and bounded retries.
- Reuses existing dataset analytics, registry, workspace roles/sharing, billing usage and entitlements, audit logs, and in-app notifications.
- Rechecks dataset sharing, workspace analyst role, subscription, feature entitlement, and usage at execution time.
- Added numeric/category profiles, row/schema/type/category comparisons, threshold and IQR anomaly alerts, and idempotent in-app notifications.
- Added authenticated CSV report summaries, automation/run/snapshot/alert APIs, an Automations page, and admin run metrics/filters.
- Added a separate worker entry point: `python -m backend.services.automation_worker`.

## Partial

- Schedules execute only while a separately supervised worker is running against the same database as the API.
- The UI exposes common operations and recurrence defaults; the API supports more recurrence parameters than the current UI exposes.
- Snapshot comparisons use the managed analytics table at run time. Google Drive file-version events do not trigger an automatic refresh.
- Run reports contain deterministic results and profiles; optional Gemini text is generated after those results exist.

## Deferred

- SMTP/email delivery, digests, and notification delivery retry (no email provider exists in the project).
- PDF, Excel, and HTML reports; only authenticated run history and CSV summary export are available.
- Google Drive change-event integration and automatic data re-import.
- Rich saved-query filters, sorting, chart configuration, arbitrary custom intervals, full distribution drift tests, and workspace recipient configuration.
- Full production-scale scheduler/worker soak testing and multi-process MySQL verification.

## Known Validation State

- `python -m pytest -q`: 145 passed, 54 warnings. The Phase 21 focused suite is included (9 passed).
- `npm run build`: passed.
- Diagnostics reported no errors in the changed backend and frontend files.
- Cloud email, Drive events, and production worker behavior are not verified in this local environment.

## Files Changed

- `backend/repositories/automation_repository.py`
- `backend/services/automation_service.py`
- `backend/services/automation_worker.py`
- `backend/schemas/automation.py`
- `backend/api/routes/automations.py`
- `backend/api/dependencies.py`
- `backend/main.py`
- `backend/services/billing_service.py`
- `backend/repositories/dataset_registry_repository.py`
- `backend/repositories/user_repository.py`
- `backend/repositories/workspace_repository.py`
- `frontend/src/services/automationApi.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/AdminDashboard.tsx`
- `frontend/src/styles.css`
- `.env.example`
- `docs/automations.md`
- `docs/phase21_status.md`
- `tests/test_phase21_automations.py`

## Resume Here

TODO(PHASE-21): Resume automated analytics scheduler, background jobs, dataset snapshots, alerts, scheduled reports, and monitoring here.

Start with `tests/test_phase21_automations.py`, then review `AutomationService.process_pending_runs()` / `_execute_run()` and `AutomationRepository.claim_run()` / `enqueue_due_automations()`. Finish deferred integrations only after selecting providers and obtaining their credentials/configuration.