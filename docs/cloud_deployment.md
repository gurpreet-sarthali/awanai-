# AskMyData — Production Cloud Deployment Guide

> **Phase 15 — Cloud Deployment & Production Launch**

This document provides step-by-step instructions for deploying **AskMyData** to cloud hosting providers.

---

## 1. Overview & Architecture

AskMyData consists of two main components:
1. **FastAPI Backend (Python 3.11)** — Handles authentication, dataset importing, SQL execution, Gemini AI query planning, and chart generation.
2. **React + Vite Frontend (TypeScript)** — Modern single-page web app.

External Cloud Services Used:
- **Database**: Managed MySQL 8.0 (Supabase, PlanetScale, AWS RDS, or Render MySQL)
- **Authentication & Drive Storage**: Google OAuth 2.0 & Google Drive API
- **AI Analytics Engine**: Google Gemini API

---

## Option A: Deploy to Render.com (Recommended - Blueprint Deployment)

Render allows single-repo deployment of both Frontend (Static Site) and Backend (Web Service) using our included `render.yaml` manifest.

### Step 1: Push Code to GitHub / GitLab
Ensure your project repository is committed and pushed to GitHub or GitLab.

### Step 2: Create Managed MySQL Database on Render
1. In [Render Dashboard](https://dashboard.render.com/), click **New +** → **PostgreSQL / MySQL**.
2. Name: `askmydata-db`
3. Copy internal/external database credentials: Host, User, Password, Database Name.

### Step 3: Deploy via Blueprint
1. Click **New +** → **Blueprints**.
2. Connect your GitHub/GitLab repository.
3. Render will detect `render.yaml` and configure:
   - **`askmydata-backend`** (Web Service, Python 3.11)
   - **`askmydata-frontend`** (Static Site, Node 18)

### Step 4: Configure Environment Variables in Render Dashboard
For `askmydata-backend`, set:
- `MYSQL_HOST`: Your managed MySQL host
- `MYSQL_USER`: MySQL user
- `MYSQL_PASSWORD`: MySQL password
- `MYSQL_DATABASE`: `askmydata`
- `APP_ENV`: `production`
- `JWT_SECRET_KEY`: Random 64+ char string (`python -c "import secrets; print(secrets.token_hex(32))"`)
- `OAUTH_STATE_SECRET`: Random 64+ char string
- `GEMINI_API_KEY`: Google AI Studio API key
- `GOOGLE_CLIENT_ID`: Google OAuth Client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth Client Secret
- `GOOGLE_REDIRECT_URI`: `https://askmydata.onrender.com/auth/google/callback`
- `MAX_LOGIN_ATTEMPTS`: `5`
- `CORS_ORIGINS`: `https://askmydata.onrender.com`

For `askmydata-frontend`, set:
- `VITE_API_BASE_URL`: `https://askmydata-backend.onrender.com`

---

## Option B: Container Deployment (Docker / AWS ECS / GCP Cloud Run / DigitalOcean)

We provide optimized production Dockerfiles and a `docker-compose.yml`.

### Step 1: Build & Run Locally with Docker Compose
```bash
docker-compose up --build -d
```
Access Frontend at `http://localhost`, Backend at `http://localhost:8000`.

### Step 2: Deploy to GCP Cloud Run or AWS ECS
1. **Backend**:
   ```bash
   docker build -t gcr.io/YOUR_PROJECT_ID/askmydata-backend:latest -f Dockerfile .
   docker push gcr.io/YOUR_PROJECT_ID/askmydata-backend:latest
   ```
   Deploy to Cloud Run / ECS and set environment variables.

2. **Frontend**:
   ```bash
   docker build -t gcr.io/YOUR_PROJECT_ID/askmydata-frontend:latest -f frontend/Dockerfile frontend/
   docker push gcr.io/YOUR_PROJECT_ID/askmydata-frontend:latest
   ```

---

## Option C: Vercel (Frontend) + Render/Railway (Backend)

### Frontend on Vercel:
1. Import repository in [Vercel](https://vercel.com/).
2. Root Directory: `frontend`
3. Build Command: `npm run build`
4. Output Directory: `dist`
5. Environment Variable: `VITE_API_BASE_URL=https://your-backend-domain.com`

---

## 3. Google OAuth 2.0 Production Setup

If Google displays `Error 403: access_denied` and says the app is currently being tested, add the Google account used for sign-in to the OAuth app's test users:

1. Open [Google Auth Platform - Audience](https://console.cloud.google.com/auth/audience) in the same Google Cloud project as the OAuth client.
2. Under **Test users**, choose **Add users**, enter the exact Google account used in the browser, and save.
3. Retry sign-in using that account. This only grants access to the app in testing mode; it does not publish the app.

For public access, publish the app and complete any Google verification required for the requested scopes.

To configure the OAuth client:

1. Open [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials).
2. Edit the **OAuth 2.0 Client ID** used by this backend.
3. Under **Authorized JavaScript origins**, add:
   - `https://your-frontend-domain.com`
4. Under **Authorized redirect URIs**, add:
   - `https://your-frontend-domain.com/auth/google/callback`
5. Verify Google Drive API is **Enabled**.

---

## 4. Post-Deployment Health & Verification Checklist

Once deployed, run these verification steps:

1. **Check Liveness Health Check**:
   ```bash
   curl -i https://your-backend-domain.com/api/v1/health
   # Expected: {"status":"ok","app_env":"production","version":"1.0.0"}
   ```

2. **Check Full System Health Endpoint**:
   ```bash
   curl -i -H "Authorization: Bearer <ADMIN_TOKEN>" https://your-backend-domain.com/api/v1/health/system
   ```

3. **Verify Security Headers**:
   Ensure response headers contain:
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: strict-origin-when-cross-origin`

4. **Verify Google Drive Sync & OAuth**:
   - Log in with Google OAuth in browser.
   - Upload a CSV dataset.
   - Run a natural language query and verify Gemini query execution + chart rendering.
