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

---

## Update — One-click installer added (May 2026)

New files in repo root for cross-PC deployment:

| File | Purpose |
|------|---------|
| `INSTALL-REALFLOW.bat` | Windows one-click — double-click to install everything (auto-elevates, runs `REALFLOW-DEPLOY.ps1`) |
| `install-realflow.sh` | Linux/macOS one-click — `sudo bash install-realflow.sh` |
| `INSTALL.md` | Top-level deployment guide (Urdu + English) |
| `REALFLOW-DEPLOY.ps1` | Existing PS1 — fixed repo URL to `dynabook`, now prints frontend URL + admin password at end |
| `docker-compose.yml` | Added `frontend` service (nginx + React build) on port `3000:80`. Whole stack is now self-contained in Docker. |

User can now:
1. Download/clone repo on any Windows 10/11 PC → double-click `INSTALL-REALFLOW.bat` → everything installs and starts.
2. On Linux/macOS → `sudo bash install-realflow.sh`.
3. Open `http://localhost:3000` to access the app.
4. Admin login credentials printed by installer + stored in `.env`.

What the installer does:
- Auto-elevates to Admin (Windows) / re-execs with sudo (Linux)
- Installs Docker Desktop / Docker Engine if missing (winget on Win, apt/dnf/yum/pacman on Linux)
- Installs Git if missing
- Clones repo to `C:\realflow` (Win) or `/opt/realflow` (Linux)
- Generates `.env` with strong random `JWT_SECRET_KEY`, `ADMIN_PASSWORD`, `POSTBACK_TOKEN`
- `docker compose build && docker compose up -d`
- Health-checks backend (`/health`) and frontend (`:3000`)
- Prints admin email + password + all useful URLs

---

## Update — 8 GB PC tuning (Dynabook L50-G profile, May 2026)

User confirmed target PC: **Intel i5-10210U / 8 GB RAM / 119 GB SSD / Win 10**.
Priority: **RUT must run smoothly** on this hardware.

New files added:
- `docker-compose.lowram.yml` — override file: Mongo cap 1 GB, Backend 2.5 GB, Frontend 192 MB, RUT_MAX_CONCURRENCY=2, RUT_MEM_LIMIT_MB=2048
- `WSLCONFIG-8GB.bat` — writes `%USERPROFILE%\.wslconfig` with `memory=5GB processors=4 swap=4GB`
- `DYNABOOK-8GB-GUIDE.md` — dedicated Urdu/English guide with optimal RUT settings (concurrency=2, delay=3-5s, headless, no screenshots)

Install-script changes:
- `install-realflow.sh` — auto-detects `<=10 GB` RAM, automatically adds `-f docker-compose.lowram.yml` to all compose commands.
- `REALFLOW-DEPLOY.ps1` — same auto-detection on Windows + auto-creates `.wslconfig` with `memory=5GB` if missing.

Backend code change:
- `real_user_traffic.py` — concurrency hard ceiling now reads `RUT_MAX_CONCURRENCY` env var (default 50). On 8 GB PCs this caps to 2 even if user slider goes higher, preventing OOM.
- `backend/.env` updated locally with same values so Emergent preview reflects the production tune.

Math on the user's 8 GB PC:
- WSL cap 5 GB
- Mongo 1 GB + Backend 2.5 GB + Frontend 0.2 GB + WSL overhead ~0.5 GB = **~4.2 GB** ≪ 5 GB ✓
- Windows itself gets remaining 3 GB ✓
- Result: no swap, no OOM, predictable performance.

Expected RUT throughput on this hardware: **~30 visits per 5 min** with 2 concurrent workers (form-fill visits ~10-15 sec each).

---

## Update — True one-folder GUI installer (May 2026)

User asked for a folder-based installer that works like a normal Windows Setup Wizard — single double-click, GUI window, big "INSTALL" button, no command line in their face.

New artifacts in `RealFlow-Setup/`:

| File | Purpose |
|------|---------|
| `Install.bat` | One-click entry — auto-elevates, hides itself, launches the PS wizard |
| `setup-engine.ps1` | **WinForms GUI wizard** with progress bar + status + log box. Big blue "INSTALL" button (only thing user touches). 6-stage installer with reboot/resume support. |
| `README.txt` | Detailed English instructions |
| `START-HERE.txt` | 5-line ultra-simple instruction |
| `bundle/` | Cache folder. After first install, contains `DockerDesktopInstaller.exe` + `Git-Installer.exe` — copy the whole `RealFlow-Setup/` folder via USB and the next PC installs OFFLINE in 5 min. |
| `bundle/README.txt` | Explains the cache mechanism |
| `EASY-INSTALL.md` (repo root) | Top-level pointer to this folder |

### Wizard flow (6 stages, with auto-reboot/resume):
1. **Prepare tools** — download+silent-install Docker Desktop (if missing, ~520 MB) and Git (~50 MB). Caches both in `bundle/`. If Docker was just installed → write `.resume-stage` marker, prompt reboot, auto-resume after restart.
2. **WSL config** — auto-detect total RAM, write `%USERPROFILE%\.wslconfig` with `memory=5GB` (≤10GB RAM) / `10GB` (≤16) / `16GB` (else).
3. **Fetch code** — `git clone` (or pull) to `C:\realflow\`.
4. **Generate .env** — random 24-char `JWT_SECRET_KEY`, `ADMIN_PASSWORD`, `POSTBACK_TOKEN`.
5. **Build + start** — auto-adds `-f docker-compose.lowram.yml` if RAM ≤ 10 GB. `docker compose build` + `up -d`.
6. **Wait + open** — health-check backend (`/health`) + frontend (`:3000`), create Desktop shortcut `RealFlow.url`, swap UI to green "OPEN REALFLOW" button → launches browser.

Error path: any throw → red error label + MessageBox with full path to `setup.log`, "INSTALL" re-enabled for retry.

UI design: dark navy palette (#14181F bg, #2840A0 header), Segoe UI font, Consolas in log box. Looks like a normal commercial Windows installer, not a script.

Result: user literally only sees:
1. UAC popup → Yes
2. Wizard window
3. Click blue INSTALL
4. Wait → click green OPEN REALFLOW
5. Browser opens
