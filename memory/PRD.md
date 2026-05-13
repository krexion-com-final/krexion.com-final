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

---

## Update — Paid SaaS / License + Stripe (May 2026)

### New backend module: `/app/backend/license_module.py`
Central licensing + Stripe subscription engine. All endpoints registered on the existing FastAPI app.

**Public endpoints** (no auth — called by installer + locally-running app):
- `GET /api/license/config` — live pricing/trial/rules
- `POST /api/license/start-trial` — `{email, machine_id?}` → license_key
- `POST /api/license/activate` — `{license_key, machine_id, machine_label?}` → binds 1 PC
- `POST /api/license/validate` — `{license_key, machine_id}` → status (heartbeat)
- `POST /api/license/checkout` — `{license_key, origin_url}` → Stripe URL
- `GET /api/license/status/{session_id}` — poll Stripe (with idempotent credit)
- `POST /api/webhook/stripe` — Stripe async confirmation (authoritative credit path)

**Admin endpoints** (existing admin JWT):
- `GET/PUT /api/admin/license/config` — edit pricing/trial/rules/master-switch GLOBALLY
- `GET /api/admin/license/list` — paginated, searchable
- `POST /api/admin/license/revoke/{key}` — blocks customer's PC instantly
- `POST /api/admin/license/extend/{key}?days=` — manual extension
- `POST /api/admin/license/issue?email=&days=` — comp / vendor license
- `GET /api/admin/license/transactions` — Stripe txn log

### MongoDB collections (in `main_db`):
- `license_config` — single doc id="global"
- `licenses` — license_key, email, status, machine_id, stripe_*, expires
- `payment_transactions` — Stripe checkout txn log (playbook §5 mandated)

### Frontend
- New page `/admin/licenses` (LicenseAdminPage.js) with two tabs:
  - **Pricing & Rules** — product name, monthly price, currency, trial days, max PCs, master switch
  - **Customers / Licenses** — searchable table with extend/revoke + manual issue
- Added "Licenses & Pricing" button to AdminDashboard header

### Desktop installer (PowerShell wizard)
`RealFlow-Setup/setup-engine.ps1` now has a **License Activation modal dialog** before the install starts. UI:
- 3 paths: "I have a license key" / "Start free trial" / "Buy license (calls Stripe)"
- On success → writes `.license` file next to installer, INSTALL stage continues
- On reinstall → re-validates saved key against server; if expired/revoked → re-shows the modal
- Machine fingerprint = Win32_ComputerSystemProduct.UUID (stable per PC)
- Activated key written into `C:\realflow\.env` as `LICENSE_KEY=`

### Locally-running app (heartbeat)
`server.py` adds `_license_heartbeat_task()` background task — every 6h POSTs to `LICENSE_SERVER_URL/api/license/validate` with `LICENSE_KEY` + machine_id. Logs status. (No enforcement yet — runs in observe mode; flip to hard-block in a follow-up by checking status before serving requests.)

### Stripe integration
- Uses `emergentintegrations.payments.stripe.checkout.StripeCheckout` per playbook
- API key: `sk_test_emergent` (in pod env)
- `GET /api/license/status` uses direct `stripe` SDK with `api_base` redirected to `https://integrations.emergentagent.com/stripe` (works around Pydantic v2 vs StripeObject.metadata incompatibility found by testing agent)
- Amount always read from BACKEND `license_config.monthly_price` — never from frontend (playbook §1 security)

### Tests
**26/26 pytest cases PASS** (`/app/backend/tests/test_license_module.py`):
- Trial reuse, 1-PC enforcement (409), validate-wrong-machine,
  Stripe checkout + status, all admin CRUD, master switch, auth gates,
  no _id leak.

### Bugs fixed by testing agent during iter 2:
- Timezone-naive datetime comparison (added `_as_aware()` helper)

### Bugs fixed by main agent after iter 2:
- `/api/license/status` 500 — replaced `emergentintegrations.get_checkout_status()` with direct `stripe.checkout.Session.retrieve()` + proxy api_base
- Stripe SDK `Session.get()` not supported → switched to `getattr()`

### Files added/changed:
- `/app/backend/license_module.py` (new, ~470 lines)
- `/app/backend/server.py` (+license wiring, +heartbeat task)
- `/app/backend/.env` (+STRIPE_API_KEY, +LICENSE_SERVER_URL)
- `/app/frontend/src/pages/LicenseAdminPage.js` (new)
- `/app/frontend/src/App.js` (+route /admin/licenses)
- `/app/frontend/src/pages/AdminDashboard.js` (+Licenses button)
- `/app/RealFlow-Setup/setup-engine.ps1` (+activation modal, +machine ID, +heartbeat key into .env)

### Open items / future
- Hard-block locally-running app when license expired (currently observe-only)
- Email notifications via Resend on activation/payment (`_maybe_notify` is a no-op until `send_email` is wired)
- When user moves off Emergent preview to a permanent license server (DigitalOcean / Vercel), update:
  - `LICENSE_SERVER_URL` in installer (setup-engine.ps1 line 22)
  - `LICENSE_SERVER_URL` in customer .env (installer writes this automatically)

---

## Update — Manual purchase flow (Stripe removed) (May 2026)

User requested: no online payment integration. Customers contact admin manually (crypto / bank / etc.) and admin issues license keys via the admin panel.

### Changes:
**Backend (`license_module.py`):**
- Removed `emergentintegrations.stripe.checkout` import — no Stripe SDK calls anywhere
- `POST /api/license/checkout` → returns **410 Gone** with msg "Online payments are disabled."
- `GET /api/license/status/{sid}` → returns **410 Gone**
- `POST /api/webhook/stripe` → no-op (returns 200 with `deprecated: true` so any stale Stripe webhook configs don't retry forever)
- Added two new fields to `license_config`:
  - `admin_contact_email` (default `"admin@realflow.local"`)
  - `admin_contact_message` (default with crypto/bank/etc. prompt)
- `get_config()` now **back-fills** missing keys on existing DB docs — no migration needed
- Public `GET /api/license/config` returns the new fields (so installer can render them)

**Frontend Admin Panel (`LicenseAdminPage.js`):**
- New section **"Manual Purchase — Contact Details"** with two editable fields
- Pricing/trial/master-switch all remain (purely informational for the customer)

**PowerShell installer (`setup-engine.ps1`):**
- "Buy a license" button (was opening Stripe) → renamed **"Contact Admin to Buy a License"**
- On click: shows the admin's email + message from license_config, then opens user's default email client with pre-filled subject "License Purchase Request — RealFlow" and body containing their PC name + form fields
- After admin replies with key → customer pastes in "I have a license key" field → Activate

**Env cleanup:**
- Removed `STRIPE_API_KEY` from `/app/backend/.env` (no longer needed)

### Flow now:
1. Customer runs `Install.bat` → activation dialog opens
2. Three options:
   a. **Start free trial** (7 days default — admin can change)
   b. **I have a license key** → paste key from admin, click Activate
   c. **Contact Admin to Buy** → mailto: opens their email app, pre-filled message
3. Customer pays admin via crypto / bank / cash (off-app)
4. Admin opens `/admin/licenses` page → "Issue manual license" → enter email + days → click Issue → email key to customer
5. Customer pastes key → Activate → app installs

### Files touched:
- `/app/backend/license_module.py` (removed Stripe ~140 lines, added contact fields)
- `/app/backend/.env` (removed STRIPE_API_KEY)
- `/app/frontend/src/pages/LicenseAdminPage.js` (added contact section)
- `/app/RealFlow-Setup/setup-engine.ps1` (Buy button → mailto:)

---

## Bug fix — Installer encoding crash (May 2026)

User reported: customer's Install.bat / Debug.bat crashed with PowerShell parse errors:
- `Unexpected token 'GB' in expression or statement`
- `Set-UI -Log "  Low-RAM mode (${totalRamGB} GB) â€" adding doc...`
- `Missing closing ')' in expression`
- Lines 199, 224, 309, 350, 353, 361 all flagged

### Root cause
The `setup-engine.ps1` file (written by main agent on a Linux container)
contained Unicode characters:
- em dash `—` (U+2014)
- ellipsis `…` (U+2026)
- smart quotes `"` `"` `'` `'`
- box-drawing chars (header decoration)

When the customer's Windows PowerShell reads the file, it falls back to
Windows-1252 / system ANSI codepage (because there is no UTF-8 BOM).
Em dashes get mis-decoded as `â€"` (3 bytes), turning code like:
```
Set-UI -Log "Step 5 / 6 — Building Docker images..."
```
into:
```
Set-UI -Log "Step 5 / 6 â€" Building Docker images..."
```
which the parser then chokes on (treats `â€` as a token, sees the `"`
as string-end, etc.).

### Fix
Python script ran over `RealFlow-Setup/*` and:
1. Replaced **every non-ASCII character** with its ASCII equivalent
   (em dash → `--`, smart quotes → `"` `'`, ellipsis → `...`, box
   drawing → `+` `-` `|`, emoji → empty).
2. Saved `.ps1` and `.txt` files with **UTF-8 BOM**.
3. Saved `.bat` files **without BOM** (cmd.exe reads BOM bytes as
   command name and fails).
4. Normalised all line endings to **CRLF** (Windows native).

Verification:
- `setup-engine.ps1`: 786 lines, 0 non-ASCII bytes, BOM=yes
- `Install.bat` / `Debug.bat`: starts with `@ech` (no BOM)
- Braces/parens/brackets/here-strings all balanced
- Specific previously-failing lines (199, 224, 309, 350, 353, 361) all
  rebuilt with `--` instead of `—`

### Files touched (all in RealFlow-Setup/):
- setup-engine.ps1, Install.bat, Debug.bat, README.txt, START-HERE.txt,
  bundle/README.txt — all sanitized to pure ASCII + correct BOM policy
