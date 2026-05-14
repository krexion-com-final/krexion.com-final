# RealFlow — Product Requirements Doc

## Original Problem Statement
User cloned the public GitHub repo `ronaldsexedwards40-glitch/dynabook` (RealFlow) into Emergent preview. They want the **entire** codebase running end-to-end so they can deploy it on their own PC. Goal: full A-to-Z working clone with **proper production-ready user + admin guides** for distribution.

User explicit goal: *"user or admin guide kr do proper ab kese kaam kre ga mein user ko install k liye dena chahta hun proper production k liye"* — they want to share the project with customers for self-installation.

## Architecture
- **Backend**: FastAPI (Python 3.11) on `:8001`, supervisor-managed, hot-reload
  - Entry: `/app/backend/server.py` (~13.6k lines, monolithic)
  - Modules: `cpi_module.py`, `real_user_traffic.py`, `license_module.py`, `form_filler.py`, `notifications.py`, `ai_vision.py`, `gsheet_writer.py`, etc.
- **Frontend**: React 18 + CRA + Craco + Tailwind + shadcn-ui on `:3000`
  - Entry: `/app/frontend/src/App.js`
  - Pages: Dashboard, Clicks, ImportTraffic, RUT, ReferrerStats, Settings, AdminDashboard, CPI*, FormFiller, LicenseAdminPage, etc.
- **Database**: MongoDB local (`mongodb://localhost:27017`), DB `realflow`. Per-user databases (`realflow_user_<id>`) for tenant isolation
- **Worker (out-of-scope for cloud)**: `/app/realflow-cpi-worker/` — runs natively on Windows
- **Deployment**: `docker-compose.yml` + `REALFLOW-DEPLOY.ps1` + GUI wizard (`RealFlow-Setup/setup-engine.ps1`)

## Core Modules
1. Real User Traffic (RUT) — anti-detect Chromium farm
2. Form Filler — automated form submission
3. CPI Module — Cost-Per-Install pipeline
4. Click Tracking + Short Links
5. Email Checker / UA Generator / Referrer Stats
6. Admin Dashboard — user/license/feature gating
7. License Module — SaaS billing + manual purchase flow
8. Sub-users — multi-tenant

## What's been done (May 2026)

### Restored from GitHub (latest session)
- Cloned `ronaldsexedwards40-glitch/dynabook` into `/app` (preserved `.git` for push-back to main)
- Wrote `/app/backend/.env`: MONGO_URL, DB_NAME=realflow, JWT_SECRET_KEY, ADMIN_EMAIL=admin@realflow.local, ADMIN_PASSWORD=admin123, RUT_MAX_CONCURRENCY=8 (HIGH-tier), etc.
- Wrote `/app/frontend/.env`: REACT_APP_BACKEND_URL=preview URL
- Installed 226 Python deps via `pip install -r requirements.txt`
- Installed all frontend deps via `yarn install`
- Restarted supervisor (backend + frontend running)
- Verified `/api/diagnostics/health` returns 200 (mongodb=ok, memory=ok, disk=ok)
- Verified `/api/admin/login` with admin@realflow.local/admin123 → JWT issued
- Frontend renders cleanly at preview URL (login page with RealFlow branding)

### Testing
- **Backend: 33/33 pytest cases PASS** (12 new clone smoke + 21 license regression)
- All P0 safety guardrails intact (license bulk-delete, cleanup, auth)
- Zero critical issues; only 3 P3 cosmetic items (hardware-profile field name, `/license/heartbeat` alias, server.py refactor)

### Production guides created (this session)
1. `/app/USER-GUIDE-PRODUCTION.md` — comprehensive end-user install guide (Urdu + English)
   - 3 install methods (GUI wizard / .bat / PowerShell command)
   - First login, mobile access (GO-ONLINE.bat), daily operations
   - 6 common problems + solutions, verification checklist
   - System requirements, updates, uninstall instructions
2. `/app/ADMIN-GUIDE-PRODUCTION.md` — comprehensive admin/business owner guide
   - 3 admin hosting options (local / mobile via tunnel / Render cloud)
   - User management, license management (all 8 endpoints documented)
   - Pricing/trial config, global kill switch, manual purchase flow
   - Bulk cleanup, analytics, backups, env vars, best practices
3. `/app/README.md` — updated repo entry point, points to both guides

## Test Credentials
See `/app/memory/test_credentials.md`:
- Admin: `admin@realflow.local` / `admin123`

## Backlog / Out-of-scope for Emergent preview
- **CPI Worker** runs natively on Windows only (USB ADB / libimobiledevice)
- **Cloudflare Tunnel** (`.bat` scripts) is for user's home PC public exposure
- **Google Sheets live-delete** requires Service Account JSON at `/app/backend/secrets/gsheets-sa.json`
- **Email sending** disabled until user adds `RESEND_API_KEY`

## Prioritized backlog (P3 — non-blocking)
- (P3) `/api/diagnostics/hardware-profile` field naming: expose canonical `tier` alongside `recommended_tier`
- (P3) Alias `POST /api/license/heartbeat` to `/api/license/validate`
- (P3) Split `server.py` (~13.6k lines) into per-domain routers using `license_module.py` pattern

## Next session ideas
- If user adds Resend API key → wire up email notifications
- If user moves to permanent cloud hosting (Render) → update `LICENSE_SERVER_URL` in installer
- Consider hard-blocking heartbeat enforcement (currently observe-only)

## Save to GitHub
User should use the **"Save to GitHub"** button in Emergent chat to commit `/app` state back to `main` branch of `ronaldsexedwards40-glitch/dynabook`. All 3 new production guides will be included.
