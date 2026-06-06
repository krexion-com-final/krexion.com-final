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
