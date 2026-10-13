# AskMyData — Security Audit

## Hardcoded Credentials
- No secrets (Gemini, Google OAuth) are exposed in the frontend code (`package.json`, `.tsx` files).
- The `backend/.env` file contains sensitive local development credentials. These must not be committed to Git. `git status` reveals no accidentally staged secret files.

## Injection & SQL Safety
- The application employs `sqlglot` to parse and validate Natural-Language-to-SQL logic (`backend/ai/nlsql/sql_validator.py`).
- **Validation Rules**:
  - Rejects `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, and other DDL/DML statements.
  - Forbids multi-statement execution and SQL comments.
  - Ensures the generated SQL references strictly allowed schemas and columns.
  - Requires safe limits for row-returning queries (`LIMIT`).
- This mitigates SQL injection vulnerabilities from arbitrary LLM output.

## Authentication & Authorization
- Endpoints are protected via dependency injection (`get_current_user`).
- Access token validation explicitly ensures that resources are accessed on a per-user and per-dataset basis.
- `DatasetAccessService` explicitly prevents cross-user dataset contamination.

## Additional Vulnerabilities
- File uploads are validated for CSV formats and maximum size bounds (`MAX_UPLOAD_SIZE_MB`), mitigating basic denial of service via large files.
- Rate limiting is integrated for LLM usage to prevent excessive API costs.
- Security headers (HSTS, nosniff, CORS configuration) are established inside `backend/main.py`.

## High Severity Recommendations
- Rotate the default `dev-only-change-me` JWT secret in production immediately.
- Never use the same database user for schema definition and analytics querying; ensure the backend uses read-only MySQL permissions when executing AI-generated queries.
