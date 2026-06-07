# Krexion PRD — Native App + Customer-Side Refactor

## Original Problem Statement (Jan 2026)
User (dennisedmaartins9-sudo) owns `https://github.com/dennisedmaartins9-sudo/krexion.com`. The repo is a large production SaaS:
- Cloud admin & marketing site on krexion.com (VPS auto-deploys on push to `main`)
- Existing Windows native installer (Inno Setup `krexion-setup.iss`, v1.0.22) that ships a self-contained Krexion engine to customer PCs
- GitHub Actions auto-builds `Krexion-Setup-vX.Y.Z.exe` on `backend/VERSION` bump

User wants a NEW AdsPower-style native desktop app shell so customer PCs run everything locally (RUT, MongoDB, Chromium) while the admin stays on krexion.com cloud. Critical constraint: **NOTHING existing may break, be missed, deleted or conflict** during `Save to GitHub` to `main`.

## User Personas
- **Admin (user)** — manages licenses, releases, customer heartbeats from krexion.com/admin
- **Customer (paid license holder)** — installs Krexion-Setup.exe on their Windows PC; runs RUT, Form-Filler, Clicks etc. locally
- **Sub-user** — team member under a customer account; restricted by parent's feature flags

## Core Requirements (Static)
1. New AdsPower-style window shell (title-bar + grouped sidebar + topbar) for **native install only**
2. Cloud DashboardLayout must remain 100% intact for web customers
3. Admin panel (`/admin/*`) must remain 100% intact (never wrapped)
4. **Admin-controlled feature gating** — when admin disables a feature for a customer, that customer cannot use it in UI OR API
5. Engine status (running/offline) **hidden from customer-facing UI**
6. Customer links must be **served from cloud** (krexion.com `/r/{slug}` redirect) so organic traffic survives PC being off — already implemented via `backend/sync_client.py`
7. Single installer bundles Python + MongoDB + Chromium + React build (no manual setup for customer)

## What's Been Implemented

### 2026-01-06 — Iteration 1: NativeShell + Feature-Gating Refactor
**New files:**
- `frontend/src/components/NativeShell.js` — AdsPower-style window UI (title-bar, grouped sidebar, topbar, account card)
- `frontend/src/components/NativeShell.css` — full theme (dark navy + cyan accent, JetBrains Mono for IDs)
- `frontend/src/components/CustomerLayout.js` — switches between DashboardLayout (cloud) and NativeShell (native) based on mode

**Modified files (surgical, minimal):**
- `frontend/src/App.js` — replaced single `<DashboardLayout>` ref with `<CustomerLayout>` for customer PrivateRoute block
- `frontend/src/context/ModeContext.js` — added `isNative` derived flag with 3 activation paths: backend `mode==="native"`, `?ui=native` query, `localStorage.krexion_force_native_ui="1"`
- `backend/server.py` — **CRITICAL BUG FIX** at `check_user_feature()`: previously auto-granted features even when admin set them to False; now respects explicit False denial. Added `check_user_feature` calls to: `/api/conversions`, `/api/form-filler/jobs` (5 endpoints), `/api/emails/check-profile-pics`, `/api/emails/upload-file`, `/api/emails/download-results`, `/api/separate-data/preview-file` (2 endpoints), `/api/user-agents/options`, `/api/user-agents/check`, `/api/user-agents/generate`

### Activation Paths
- **Customer PC (Inno Setup install)** → backend `.env` has `KREXION_MODE=native` → `/api/mode` returns `mode:"native"` → frontend auto-renders NativeShell
- **krexion.com cloud (web customer login)** → `KREXION_MODE=cloud` → frontend renders existing DashboardLayout (untouched)
- **Dev preview / local** → `KREXION_MODE=local` → DashboardLayout renders; `?ui=native` overrides for QA

### Verified (Testing Agent Iteration 12)
- ✅ 28/28 pytest backend feature-gating cases pass
- ✅ Frontend NativeShell renders correctly (all 15 data-testids present)
- ✅ Engine pill removed from customer topbar
- ✅ Admin `/admin` route never wrapped in NativeShell (even with `?ui=native`)
- ✅ Sidebar correctly hides admin-disabled features (Links, CPI section, etc.)
- ✅ Logout reachable via NativeShell user menu
- ✅ All existing customer routes unaffected

## Architecture — Links Run On VPS, Customer PC Runs Engine

```
┌─ Customer's PC ─────────────────┐         ┌─ krexion.com (VPS) ───────┐
│ NativeShell (React)             │ ←──────→│ Cloud edge backend         │
│ ↓                                │ sync   │ • License heartbeat         │
│ Local backend (127.0.0.1:8001)   │ every  │ • Customer status report    │
│ ↓                                │ 30s    │ • /r/{slug} redirect        │
│ MongoDB (127.0.0.1:27017)        │         │ • Click capture             │
│ ↓                                │         │ • Admin panel               │
│ Playwright Chromium (RUT engine) │         └──────────────────────────────┘
│ Customer's own proxies           │
└─────────────────────────────────┘

sync_client.py (already in backend/) handles:
  • PUSH: new local links → cloud (so organic traffic survives PC-off)
  • PULL: cloud-captured clicks → local DB (so customer sees stats)
  • PULL: feature flags / license / sub-users from cloud
```

## What Customer's Single .exe Installer Bundles
Inno Setup `installer/krexion-setup.iss` already packages and the new shell ships inside the same installer:
- Embedded Python 3.11 (renamed to `krexion-core.exe`)
- MongoDB Portable → `C:\Program Files\Krexion\database\`
- Playwright Chromium → `C:\Program Files\Krexion\browser-engine\`
- React frontend build (now containing NativeShell) → `C:\Program Files\Krexion\frontend\`
- NSSM (renamed to `krexion-service.exe`) → registers `KrexionDatabase` + `KrexionBackend` Windows services
- WebView2 runtime auto-installed if missing

## Prioritized Backlog

### P0 (next session)
- **Phase 2:** Wire `desktop/krexion_dashboard.py` PyWebView API to make NativeShell title-bar `min/max/close` buttons functional in production install
- **Phase 3:** Bump `backend/VERSION` from `2.1.8` → `2.2.0` to trigger GitHub Actions auto-build of `Krexion-Setup-v2.2.0.exe`

### P1 (later)
- Add an Admin UI tile under `/admin/users/[id]/features` for one-click feature toggling per customer (currently requires PUT JSON)
- Add per-feature audit log entry so admin can see "Admin enabled `cpi` for user X at 2026-01-06 14:32"
- Add an in-app "License & Features" page for customer to see what they have/don't have (no more guessing why a sidebar item is hidden)

### P2 (nice-to-have)
- Frameless PyWebView window with custom-drawn title-bar drag region (drop OS chrome entirely — AdsPower-style)
- Optional Light theme toggle in NativeShell
- Tray icon "Pause All Jobs" quick action

## Next Action Items
1. User must use **"Save to GitHub"** button in chat input to push the NativeShell + feature-gating commits to `main`. (Main agent does NOT push directly per platform safety rules.)
2. Once pushed, VPS auto-deploys updated code; cloud customers see no change (DashboardLayout intact).
3. To produce a new installer with the NativeShell, user must approve Phase 2 + 3 in a follow-up session.

### 2026-02 — Iteration 2: Parallel Electron Desktop Build (AdsPower-style, additive)
**New folder (zero impact on existing code):**
- `electron-desktop/package.json` — Electron 31 + electron-builder 24 metadata
- `electron-desktop/src/main.js` — spawns local MongoDB (127.0.0.1:27117) + FastAPI backend (127.0.0.1:8088), loads packaged React build inside Electron BrowserWindow, tray icon, single-instance lock
- `electron-desktop/src/preload.js` — minimal contextBridge surface (`window.krexion`)
- `electron-desktop/src/splash.html` — dark splash screen while services boot
- `electron-desktop/scripts/prepare-resources.js` — at build time downloads Python 3.11 embed + MongoDB 7.0.14 portable, installs `backend/requirements.txt`, builds `frontend/` with `REACT_APP_BACKEND_URL=http://127.0.0.1:8088` + `PUBLIC_URL=.`, copies all into `resources/krexion/`
- `electron-desktop/electron-builder.yml` — NSIS x64, output `dist/Krexion-Desktop-Setup-<version>.exe`, `extraResources` maps `resources/krexion/**` → `resources/krexion/**`
- `electron-desktop/build/installer.nsh` — adds Windows Firewall loopback rule for ports 27117/8088 on install, removes on uninstall
- `electron-desktop/.gitignore` — ignores `node_modules/`, `dist/`, `resources/krexion/`, `.cache/`
- `electron-desktop/README.md` — full Roman Urdu + English documentation

**New workflow (parallel pipeline):**
- `.github/workflows/build-electron-desktop.yml` — manual `workflow_dispatch` only, runs on `windows-latest`, optional `release_tag` input to publish a GitHub Release with the `Krexion-Desktop-Setup-*.exe` artifact (different name from existing Inno-Setup `Krexion-Setup-*.exe` → no collision)

**Verification done in pod:**
- `node -c` on all three JS files: syntax clean
- `python3 -c "yaml.safe_load(...)"` on both YAML files: valid
- `npx electron-builder --win --x64 --dir` dry run with stub resources: produced `dist/win-unpacked/Krexion Desktop.exe` + correctly nested `resources/krexion/` — config proven to work end-to-end
- `git status` confirms ONLY two new entries (`electron-desktop/`, `.github/workflows/build-electron-desktop.yml`). Zero existing files modified.

## Files NOT Touched (must remain so unless explicitly requested)
- `installer/krexion-setup.iss`
- `Build-Krexion-Windows.ps1`, `BUILD-KREXION.bat`
- `build/build-backend.py`
- `.github/workflows/build-windows-release.yml`, `deploy.yml`
- `Krexion-User-Package/` (legacy Docker bundle for back-compat)
- `desktop/krexion_dashboard.py`
- `backend/sync_client.py`, `backend/server.py`, all backend modules
- `frontend/` source tree (only consumed read-only by `prepare-resources.js` at CI time)


---

### 2026-02 — v2.1.13: Activate AdsPower-style NativeShell in Electron Desktop

**Problem:** Customer requested an AdsPower-style native desktop UI for the
Electron build. The `NativeShell.js` component (sidebar + topbar + title-bar
chrome) already existed in `frontend/src/components/` but was never reaching
customers because the desktop build was reporting `KREXION_MODE='local'` and
the frontend gates the native shell on `mode === 'native'`. As a result, the
shipped Krexion-Desktop-Setup-2.1.11.exe was still rendering the cloud
`DashboardLayout`.

**Fix (single, minimal, additive — no page logic touched):**
- `electron-desktop/src/main.js`: backend spawn env now sets
  `KREXION_MODE: 'native'` (was `'local'`).
- `electron-desktop/scripts/prepare-resources.js`: bundled fallback `.env`
  mirrors the same value so manual uvicorn launches (KREXION-LOGS.bat, etc.)
  also pick up the native UI.
- `backend/VERSION`: bumped 2.1.12 → 2.1.13.
- `electron-desktop/package.json`: version synced to 2.1.13.

**Why this is safe:**
- `NativeShell.js` is a pure visual wrapper around `{children}` — every
  existing customer page (Links, Clicks, Conversions, Real-User Traffic,
  CPI, Settings, etc.) renders byte-for-byte identical inside the new
  chrome. No form field, button, or feature is removed.
- `CustomerLayout.js` continues to switch between `DashboardLayout` and
  `NativeShell` based on `useMode().isNative`, so the **cloud web app
  (krexion.com) is completely untouched** — it still sees
  `mode === 'cloud'` and renders the existing dashboard.
- Backend treats `'native'` the same as `'local'` everywhere; only
  `IS_CLOUD = KREXION_MODE == 'cloud'` is checked, so all gating logic
  is identical to a `local` install.
- Admin routes (`/admin/*`) are mounted outside `CustomerLayout`, so the
  admin panel is unaffected.

**How to ship:**
1. Push to `main`.
2. Trigger workflow `Build Krexion Desktop (Electron)` on GitHub with
   `release_tag = desktop-v2.1.13`.
3. Existing installs running ≥ v2.1.11 will auto-update via
   `electron-updater` reading `latest.yml` from the new release.

**Verification (in CI / on first install):**
- App launches → splash → main window → AdsPower-style sidebar visible.
- All 26+ existing pages reachable from the new sidebar groups (Main,
  Traffic Engine, Tools, CPI, System).
- Title-bar Min/Max/Close buttons present (frameless behaviour wired in
  NativeShell.js).
- Cloud web app (krexion.com) shows unchanged DashboardLayout.



---

### 2026-02 — v2.1.14: Customer License Dashboard + Anti-detect leak fix

**Two parallel customer-impacting changes shipped together (single commit):**

#### 1. Per-customer License Dashboard
- **Backend (`backend/license_module.py`)**:
  - `GET /api/license/me` (auth: customer JWT) — returns the logged-in
    user's license: status, days_remaining, machine_label, machine_id_short,
    activated_at, last_validated_at, subscription_ends_at. Strips admin-only
    fields (stripe ids, hardening telemetry).
  - `POST /api/license/deactivate-me` — releases the current PC binding so
    the customer can re-activate on another machine WITHOUT contacting
    support. Records a `customer_deactivate` event for audit.
  - `_bind()` extended with `get_current_user` (server.py wires the
    existing customer auth dep). Old `get_current_admin` flow untouched.
- **Frontend (`frontend/src/pages/LicensePage.js`, new — 384 lines)**:
  - Renders status badge, masked license key (Show/Hide + Copy),
    days-remaining card (amber when ≤7, red when 0), plan card with
    "Renew/Upgrade" CTA, bound PC card with "Release this PC" confirm
    dialog. Friendly empty state for accounts without a license yet
    (links to /pricing).
  - Route `/license` added in `App.js`. Sidebar link added in both
    `NativeShell.js` (System group) and `DashboardLayout.js` (cloud).

#### 2. Anti-detect UA leak fix (6 leak points → 0)
- `backend/real_user_traffic.py` and `backend/tls_anti_detect.py` were
  using the literal string `"Mozilla/5.0"` as a UA fallback when no
  per-visit UA was supplied. That string is a CLASSIC bot signature
  (real browsers always send a full UA with platform + WebKit token).
  Cloudflare Bot Management, DataDome, IPQualityScore Deep, Akamai Bot
  Manager and Sift all flag UAs shorter than ~16 chars or missing a
  `(...)` platform block as hard bot signals.
- Replaced all 6 fallbacks with `_realistic_fallback_ua()` /
  `_fallback_ua()`: picks at random from a small pool of current
  Chrome-on-Windows-desktop UAs (the most common residential combo).
- Real per-visit UAs (the COMMON case) are unchanged; this only
  affects pre-browser probes that ran before a device pool was chosen.

**Version:** 2.1.13 → 2.1.14 (backend/VERSION + electron-desktop/package.json).

**Files changed (10):**
- `backend/VERSION`
- `backend/license_module.py` (+150 lines, customer endpoints)
- `backend/real_user_traffic.py` (+40 lines anti-detect helper, 3 fallback fixes)
- `backend/tls_anti_detect.py` (+19 lines anti-detect helper, 3 fallback fixes)
- `backend/server.py` (+6 lines wires get_current_user into license_bind)
- `electron-desktop/package.json` (version sync)
- `frontend/src/App.js` (+2 lines route + import)
- `frontend/src/components/DashboardLayout.js` (+5 lines License nav item)
- `frontend/src/components/NativeShell.js` (+2 lines License nav in System group)
- `frontend/src/pages/LicensePage.js` (NEW, 384 lines)

**Safety / non-regression:**
- All anti-detect changes are FALLBACK paths — they only fire when a
  caller forgot to pass `ua=`. The common code paths (per-visit UA
  from `_IOS_DEVICES` / `_ANDROID_DEVICES` pools) are byte-for-byte
  identical.
- License module additions are purely NEW endpoints. Existing admin
  + installer + activate/validate flows are unchanged.
- Frontend changes are purely additive: one new route, one new page,
  one new sidebar item in each shell. Every existing page/form/field
  is preserved.



---

### 2026-02 — v2.1.15: Cloud-Auth Bridge (architectural shift)

**Problem:** Until v2.1.14 the desktop app ran 100% offline — its embedded
Python backend + embedded MongoDB held auth, users, links, clicks, RUT
jobs, everything. As a result:
- A user who signs up in the desktop app never appears in the
  `krexion.com/admin/dashboard` for approval.
- Centralized admin management is impossible.
- A customer using two PCs sees two independent accounts.

**User's chosen architecture (Hybrid):**
| Cloud (krexion.com VPS)        | Local desktop PC               |
|---------------------------------|--------------------------------|
| Auth / login / register / me   | Clicks data (heavy)           |
| Admin dashboard + approvals    | Conversions                    |
| License management             | RUT jobs / browser automation |
| Links (CRUD + redirect uptime) | User profiles / fingerprints  |
|                                | UA gen, visual recorder, etc. |

VPS only holds links + users + license + admin metadata → minimal load
even with thousands of customers. All heavy work runs on the customer's
own PC.

**Implementation (single-file proxy, frontend untouched):**

1. **`backend/cloud_proxy_module.py` (NEW, ~280 lines)**
   - `CloudProxyMiddleware`: starlette BaseHTTPMiddleware that
     intercepts every request. If the path matches an explicit
     allowlist AND `KREXION_MODE != "cloud"`, forwards to
     `KREXION_CLOUD_URL` via shared `httpx.AsyncClient`.
   - Allowlist (prefix): `/api/auth/`, `/api/admin/`, `/api/license/`,
     `/api/links/`. Allowlist (exact): `/api/links`,
     `/api/customer-signup`. Everything else stays local.
   - Strips hop-by-hop + `content-encoding`/`content-length` headers
     on both directions so the response isn't double-decoded.
   - `verify_cloud_token(authorization_header)`: helper used by
     `get_current_user` to resolve cloud-issued JWTs (different
     SECRET_KEY than local) against `krexion.com/api/auth/me`. 5-min
     cache to avoid hammering cloud.
   - Clear error mapping: cloud unreachable → 502 with
     `{"detail": "Cloud unreachable. Check your internet connection."}`;
     cloud timeout → 504. No infinite buffering.
   - On `KREXION_MODE=cloud` the middleware stays **inert** —
     prevents the cloud from looping into itself.

2. **`backend/server.py`** (+~70 lines)
   - Imports + installs `install_cloud_proxy(app)` right after `IS_CLOUD`
     is computed. Wrapped in try/except so an import failure can't
     bring down the backend.
   - `get_current_user()`: when local `jwt.decode()` fails with
     `JWTError` (the COMMON case on desktop because the JWT was
     signed by cloud's `SECRET_KEY`), falls through to
     `verify_cloud_token()`. On success, mirrors the cloud user into
     local Mongo (`cloud_synced: True`) so other local endpoints
     (clicks, RUT, conversions) keep joining on `user_id` without a
     network round-trip per request.

3. **`electron-desktop/src/main.js`** (+5 lines)
   - Backend spawn env now also sets `KREXION_CLOUD_URL` (override
     via OS env still respected).

4. **`electron-desktop/scripts/prepare-resources.js`** (+1 line)
   - Bundled fallback `.env` mirrors `KREXION_CLOUD_URL=https://krexion.com`
     so manual `uvicorn` launches (KREXION-LOGS.bat) work too.

5. **`backend/VERSION` + `electron-desktop/package.json`** → 2.1.15.

**Smoke tests passed:**
- `ast.parse` clean on server.py + cloud_proxy_module.py + license_module.py.
- Cloud-proxy module imports cleanly with `KREXION_MODE=native`.
- Route-matching matrix verified (17 paths tested, 0 fails):
  cloud-routed paths (auth/admin/license/links) match; local paths
  (clicks/rut/conversions/settings/system) correctly stay local;
  prefix discipline correct (`/api/auth` alone does NOT match —
  only `/api/auth/` prefix does).

**End-to-end flow (what the customer experiences):**
1. Customer opens fresh desktop app → lands on cloud-backed
   login screen (Electron loads localhost frontend, frontend POSTs
   `/api/auth/login` → proxy → `krexion.com/api/auth/login`).
2. Customer registers → cloud Mongo gets the new user → admin sees
   it instantly on `krexion.com/admin/dashboard`.
3. Admin approves the user (status: pending → active) on cloud.
4. Customer logs in → cloud JWT returned → stored in
   `localStorage.token`.
5. Customer creates a link in the desktop UI → POST `/api/links`
   → proxy → cloud → link saved in cloud Mongo (uptime
   guaranteed independent of customer's PC).
6. Customer starts RUT job → POST `/api/rut/start` → stays LOCAL
   → local backend's `get_current_user` falls back to
   `verify_cloud_token` → cloud confirms the user → local mirror
   created → RUT runs on customer's PC consuming customer's CPU.

**Safety:**
- Cloud (`krexion.com`) untouched at runtime — proxy is inert there.
- All paths NOT in the allowlist behave EXACTLY as before
  (RUT, clicks, conversions, settings, every existing form / field
  / button preserved byte-for-byte).
- Auth pass-through preserves every header verbatim.
- The 5-min token cache means cloud receives ~12 verify calls/hour
  per active customer at most.

