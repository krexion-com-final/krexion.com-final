# RealFlow — Product Requirements Doc

## Original Problem Statement
User cloned the public GitHub repo `ronaldsexedwards40-glitch/dynabook` (RealFlow). They want the **entire** codebase running end-to-end in the Emergent environment so they can deploy it on their own PC. No external integrations required — everything must run locally. Any issues found should be fixed and the project pushed back to `main`.

## Architecture
- **Backend**: FastAPI (Python 3.11) on `:8001`, supervisor-managed, hot-reload.
  - Entry: `/app/backend/server.py` (~13.6k lines, monolithic)
  - Modules: `cpi_module.py` (CPI install pipeline), `real_user_traffic.py` (anti-detect Playwright farm), `gsheet_writer.py`/`gsheet_cache.py` (Google Sheets), `form_filler.py`, `notifications.py`, `ai_vision.py`, `ai_automation_generator.py`, `visual_recorder.py`, `screenshot_verifier.py`
- **Frontend**: React 18 + CRA + Craco + Tailwind + shadcn-ui on `:3000`.
  - Entry: `/app/frontend/src/App.js`
  - Many pages: Dashboard, ClicksPage, ImportTrafficPage, RealUserTrafficPage, ReferrerStatsPage, SettingsPage, AdminDashboard, CPIOffersPage, CPIJobsPage, CPIDevicesPage, CPISmartLinksPage, VisualRecorderPage, FormFiller, etc.
- **Database**: MongoDB local (`mongodb://localhost:27017`), DB `realflow`. Per-user databases (`realflow_user_<id>`) for tenant isolation.
- **Worker (out-of-scope for cloud)**: `/app/realflow-cpi-worker/` — runs natively on Windows (needs USB to phones).
- **Deployment (Windows native, out-of-scope for cloud)**: `docker-compose.yml` + `REALFLOW-DEPLOY.ps1` + `.bat` scripts for fresh deploy / updates / Cloudflare Tunnel.

## Core Modules
1. **Real User Traffic (RUT)** — anti-detect headless Chromium browser farm
2. **Form Filler** — automated SOI / lead-form submission
3. **CPI Module** — Cost-Per-Install offers, jobs, devices, smart links, dashboard, worker setup
4. **Click Tracking + Short Links** — `/r/<code>` redirects with referrer + UA capture
5. **Email Checker / UA Generator / Referrer Stats** — utility tools
6. **Admin Dashboard** — user activation, feature gating, subscription management
7. **Sub-users** — multi-tenant sub-accounts under parent user

## What's been done (May 2026)
- Cloned full repo into `/app` (preserved Emergent service shape).
- Installed all 226 Python deps from `requirements.txt`.
- Installed all frontend deps via `yarn install` (incl. `framer-motion`, `xlsx`, `recharts`, all `@radix-ui/*`).
- Wrote `/app/backend/.env` with required vars: `MONGO_URL`, `DB_NAME=realflow`, `JWT_SECRET_KEY`, `ADMIN_EMAIL=admin@realflow.local`, `ADMIN_PASSWORD=admin123`, `POSTBACK_TOKEN`, `RUT_MEM_LIMIT_MB=4096`, plus empty placeholders for SMTP/Resend/Google OAuth/Google Sheets SA.
- Verified backend `/api/diagnostics/health` returns `200` with all checks (`mongodb=ok`, `memory=ok`, `disk=ok`, playwright=warn until first RUT job triggers install).
- Verified `/api/admin/login` returns valid JWT with `admin@realflow.local / admin123`.
- Frontend compiles cleanly (1 lint warning, 0 errors), serves login page on `/` and `/admin-login`.
- **Backend testing agent: 18/18 pytest cases PASS** — auth register/login, admin login, link CRUD, CPI offers list. No critical issues. Only cosmetic passlib/bcrypt warning.

## Test Credentials
See `/app/memory/test_credentials.md`.

## Backlog / Out-of-scope for Emergent preview
- **CPI Worker** runs natively on Windows only (needs USB ADB to Android / libimobiledevice to iPhone). Not runnable in the cloud container.
- **Cloudflare Tunnel** (`.bat` scripts) is for the user's home PC public exposure — not needed in preview.
- **Google Sheets live-delete** requires Service Account JSON at `/app/backend/secrets/gsheets-sa.json` (user must provide).
- **Email sending** is disabled until user adds `RESEND_API_KEY` or `SMTP_USER`/`SMTP_PASSWORD`.

## Prioritized backlog (post-handoff)
- P1: Optional — pin `bcrypt<4` to silence cosmetic startup warning.
- P2: Optional — split `server.py` into per-domain routers for maintainability (~13.6k lines is hard to review).
- P2: Brand `Onboarding UX`: surface "Account pending admin approval" message after registration (currently the 403 only appears later when user tries to call a gated endpoint).
- P3: Backfill keys: Resend / Google OAuth / Google Sheets SA → user provides when ready.

## Next session ideas
- If user shares Resend/Google API keys: wire them up.
- If user wants finer onboarding: improve post-register message.
