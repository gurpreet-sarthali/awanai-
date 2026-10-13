# AskMyData — Deployment Checklist

## Pre-deployment Requirements

### Environment Variables
Ensure the following variables are overridden with strong secrets in your production environment:
- [ ] `APP_ENV=production`
- [ ] `JWT_SECRET_KEY` (must be randomly generated, length > 32 chars)
- [ ] `OAUTH_STATE_SECRET` (must be changed from default)
- [ ] `GEMINI_API_KEY`
- [ ] `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- [ ] `MYSQL_PASSWORD`

### Infrastructure
- [ ] MySQL database instance running.
- [ ] Database initialized with proper permissions (Read-only user for analytics query execution).
- [ ] Docker or appropriate hosting environment ready for `docker-compose.yml`.

### Testing and Readiness
- [ ] **Frontend**: Build succeeds (`npm run build`). No TypeScript compilation errors exist.
- [ ] **Backend**: Backend starts cleanly against the production MySQL database.
- [ ] **Tests**: Resolve test teardown hangs related to the `MonitoringService` and `BillingService`. All Critical End-to-End paths pass.

### Security
- [ ] Ensure `docs/` or source code files containing secrets (.env) are excluded from Docker image builds (verified `.dockerignore`).
- [ ] Configure `CORS_ORIGINS` to precisely match the production domain (e.g., `https://askmydata.com`).

**Status**: Currently blocked from immediate production launch due to test execution hangs and failing test suites (Automations, Workspaces, Developer API). These issues must be investigated in the production context or the test context updated to correctly mock dependencies.
