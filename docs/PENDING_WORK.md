# Pending and Paused Work

This document tracks all currently pending, incomplete, or partially implemented tasks across the AskMyData project. 
**DO NOT** automatically resume these tasks without explicit instruction.

---

## Phase 21 — Automated Analytics, Scheduled Reports & Smart Data Monitoring

**Status:** 
PAUSED

**Completed:**
- Initial analytics automation structure
- Database schema persistence (saved queries, schedules, runs, snapshots, alerts, worker locks)
- Allowlisted deterministic analytics configuration
- Daily, weekly, monthly timezone-aware scheduling logic
- Separate worker entry point (`automation_worker.py`)
- APIs for automations, runs, snapshots, and alerts
- `AutomationsPage` UI stub and Admin dashboard metrics

**Partially Implemented:**
- Worker supervision logic
- Recurrence configuration in UI vs API limits
- Snapshot comparisons
- Gemini optional text generation on reports

**Pending:**
- Scheduler execution loop and robust worker deployment
- SMTP/email delivery for digests and alerts
- Notifications delivery retry mechanism
- Google Drive file-version change events & auto-reimport
- Advanced PDF/Excel/HTML report generation
- Full production-scale soak testing
- Rich UI for saved-query filters, chart config, and workspace recipient configuration

**Files/Components Already Changed:**
- `backend/repositories/automation_repository.py`
- `backend/services/automation_service.py`
- `backend/services/automation_worker.py`
- `backend/schemas/automation.py`
- `backend/api/routes/automations.py`
- `frontend/src/services/automationApi.ts`
- `frontend/src/components/AdminDashboard.tsx`
- `docs/automations.md`
- `docs/phase21_status.md`

**Known Issues:**
- Cloud email, Drive events, and production worker behavior are not verified.
- The background worker needs to be supervised externally and is not natively running in the main FastAPI loop.

**Dependencies:**
- Requires email provider credentials for notification delivery.
- Requires robust external scheduler infrastructure.

**Resume Later From:**
- Start with `tests/test_phase21_automations.py`, then review `AutomationService.process_pending_runs()` and `AutomationRepository.claim_run()`. 
- Finish deferred integrations only after explicitly requested and once providers/credentials are obtained.

---

## Phase 22 — Deployment

**Status:**
PENDING - NOT STARTED

**Completed:**
- Cloud architecture docs (`docs/cloud_deployment.md`)
- Local `docker-compose` environment structure

**Pending:**
- CI/CD pipelines
- Infrastructure as Code (Terraform/CloudFormation)
- Production secrets management
- Staging/Production environment configuration
- Autoscaling configurations

**Files/Components Already Changed:**
- `docs/cloud_deployment.md`
- `.env.example`

**Known Issues:**
- Deployment scripts do not yet support the background worker separated in Phase 21.

**Dependencies:**
- AWS/GCP infrastructure provisioned.

**Resume Later From:**
- Review `docs/cloud_deployment.md` and implement the CI/CD pipeline and cloud manifest files.
