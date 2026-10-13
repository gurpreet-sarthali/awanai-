# AwanAI: Simple Onboarding, Visitor Management & Temporary CSV Architecture

This document describes the onboarding, visitor registration, session management, and temporary CSV storage architecture for **AwanAI** (formerly AskMyData).

---

## 1. Overview & New Onboarding Flow

AwanAI provides frictionless onboarding for students and analysts:
1. **Welcome Screen (`/`)**:
   - Clean, branded interface displaying:
     - Heading: *"Welcome to AwanAI"*
     - Subtitle: *"Your AI-powered data analytics assistant."*
     - Inputs: **Full Name** and **Gmail/Email Address**.
     - Button: **"Get Started →"**
   - **No Google OAuth**, no passwords, no email verification hurdles.
2. **Visitor Registration (`POST /api/v1/visitors/register`)**:
   - The browser sends `{ name, email }` to the FastAPI backend.
   - The backend validates the inputs, enforces rate limiting (10 requests/min per IP), and saves the visitor record to the Supabase `visitors` table using the backend **Service Role Key**.
   - If the visitor previously registered with the same email, their name and `last_seen_at` timestamp are updated without creating duplicates.
   - The backend issues a signed 24-hour temporary session JWT (`is_visitor: True`, `sub: visitor_id`).
3. **Instant Dashboard Access (`/dashboard`)**:
   - The frontend stores the session locally in `localStorage` (`awanai_visitor_session`) and saves the bearer token in `api.ts`.
   - The user is immediately transitioned to the AwanAI dashboard.
   - The visitor's display name and initials are displayed in the user profile navigation section.

---

## 2. Supabase Database Schema & Migration

### Migration File: `sql/08_visitors_table.sql`

To configure your Supabase database, run the following SQL script in your **Supabase Dashboard → SQL Editor**:

```sql
-- Create table for unverified visitor registrations
CREATE TABLE IF NOT EXISTS public.visitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Case-insensitive unique index on email
CREATE UNIQUE INDEX IF NOT EXISTS idx_visitors_email_lower ON public.visitors (LOWER(email));

-- Index for temporal queries and retention auditing
CREATE INDEX IF NOT EXISTS idx_visitors_last_seen_at ON public.visitors (last_seen_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE public.visitors ENABLE ROW LEVEL SECURITY;

-- Security hardening: explicitly revoke direct table access from public / anon
REVOKE ALL ON TABLE public.visitors FROM anon;
REVOKE ALL ON TABLE public.visitors FROM authenticated;

-- Service role retains full access for backend upserts (bypasses RLS)
GRANT ALL ON TABLE public.visitors TO service_role;
```

---

## 3. Security Configuration & Model

### 3.1 Credential Isolation
- **Service-Role Key**: Stored **strictly on the backend** in the environment variable `SUPABASE_SERVICE_ROLE_KEY`. It is **never sent to the frontend**.
- **Frontend Safe**: The frontend only communicates with the backend API endpoint (`/api/v1/visitors/register`) and never receives or stores database secret keys.
- **Row Level Security**: Direct client access to the `visitors` table is disabled via RLS policies and role revocations (`REVOKE ALL FROM anon`).

### 3.2 Limitations of Unverified Name & Email
- **Unverified Identity**: Because this onboarding flow does not send a verification link or require a password, the submitted email is **self-reported** and cannot be treated as cryptographic proof of ownership.
- **Access Boundary**: Visitor sessions cannot access protected administrator areas (`/admin`).
- **Feature Separation**:
  - **Visitor Features**: Upload CSV datasets, analyze datasets, execute SQL/Gemini queries, view charts, and export results.
  - **Authenticated Admin Features**: Admin monitoring dashboard, user management, system audit logs, and privileged webhook configurations (require real password credentials).

---

## 4. Visitor Session Mechanism

- **Client Storage**: The frontend persists the visitor session in `localStorage` (`awanai_visitor_session`), retaining `{ visitorId, name, email, registeredAt }`.
- **JWT Session Token**: The backend issues an access token with claims `{"sub": visitor_id, "is_visitor": true, "name": name, "email": email}`.
- **Persistence Across Refreshes**: When the user reloads the page, `VisitorContext` restores the session and `useAuth` recognizes the active session, keeping the user in the dashboard without redirecting them back to the welcome screen.
- **Logout Flow**: Clicking the logout icon in the sidebar invokes `clearVisitor()` and `clearAccessToken()`, clearing the session and returning to the welcome screen.

---

## 5. Temporary CSV Storage Architecture

### 5.1 Storage Isolation & Security
- **Backend Temporary Storage**: Uploaded datasets are stored in `data/uploads/<visitor_id>/<dataset_id>_<safe_filename>.csv`.
- **Visitor Isolation**: Each visitor is assigned a unique `visitor_id`. Datasets are registered in SQLite/PostgreSQL with `user_id = visitor_id`.
- **Dataset Access Control**: `DatasetAccessService` guarantees that Visitor A cannot view, query, or delete datasets uploaded by Visitor B.
- **Path Traversal Protection**: Filenames are sanitized via `Path(filename).name` and regex sanitization, stripping path separators and parent directory references (`../`).
- **File Validation & Limits**:
  - File extension must be `.csv`.
  - Max upload size: 25 MB (`MAX_UPLOAD_SIZE_MB`).
  - Max CSV dimensions: 200,000 rows, 200 columns.
- **No Supabase Storage for CSV Data**: Uploaded CSV file contents are **never stored in Supabase**. Supabase only holds the visitor registration details (`name`, `email`, timestamps).

### 5.2 Automatic File Cleanup
- `DatasetManagementService.cleanup_temporary_files(max_age_hours=24)` identifies files older than 24 hours in `data/uploads` and deletes them from disk.
- Deleting a dataset via `DELETE /api/v1/datasets/{dataset_id}` automatically unlinks the temporary CSV file from the filesystem and drops the associated internal SQL table.

---

## 6. Required Environment Variables

Add or verify these environment variables in your `.env` file:

```env
# Application Environment
APP_ENV=development
LOG_LEVEL=INFO

# Supabase (Server-side only — holds service-role key for visitor upserts)
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-secret-key

# JWT Token Secret for Visitor & User Sessions
JWT_SECRET_KEY=your-secure-random-secret-key-at-least-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Temporary Dataset Storage Configuration
DATASET_UPLOADS_DIR=data/uploads
MAX_UPLOAD_SIZE_MB=25
MAX_CSV_ROWS=200000
MAX_CSV_COLUMNS=200

# AI Configuration (Gemini)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
```

---

## 7. How to Run the Application

### Backend
```bash
# Activate virtual environment if configured
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 8. Test Execution & Verified Results

| Test Case | Scope | Result | Details |
|:---|:---|:---:|:---|
| `test_visitor_registration_flow` | API | **PASSED** | Registers visitor, returns `visitor_id`, `access_token`, updates returning visitors |
| `test_visitor_validation_errors` | Validation | **PASSED** | Rejects short names (< 2 chars) and invalid email formats |
| `test_visitor_session_token_and_dataset_isolation` | Security & Storage | **PASSED** | Visitor A and Visitor B datasets strictly isolated; unauthorized deletion blocked |
| `npm run build` | Frontend | **PASSED** | TypeScript compilation and Vite production bundle generated cleanly (0 errors) |
