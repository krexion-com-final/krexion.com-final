# Krexion — Product Requirements & Build Log

## Problem Statement (original)
User owns `dennisedmaartins9-sudo/krexion.com` (private collaborator access).
They want me to: (a) explore the repo end-to-end, (b) make bug fixes / feature
changes, (c) push to `main` only when they say so, (d) ensure every push reaches
*all surfaces* — Cloud VPS, Native Windows installer, Electron desktop app —
without anything being lost or broken, (e) provide login for preview testing,
and (f) keep the main branch conflict-free.

## Architecture
- **Cloud (VPS)**: FastAPI backend + React frontend + MongoDB. Auto-deploys on
  every push to `main` (`.github/workflows/deploy.yml`).
- **Native Windows installer**: Inno-Setup bundle (~571 MB) with embedded
  Python, MongoDB Portable, Edge WebView2, Playwright Chromium. Built only
  when `backend/VERSION` changes (`build-windows-release.yml`).
- **Electron Desktop**: `electron-desktop/` runs the same FastAPI backend on
  127.0.0.1:8088 with `KREXION_MODE=native`. Uses `electron-updater` for
  silent in-place upgrades. Built only when `backend/VERSION` changes
  (`build-electron-desktop.yml`).

## Iteration 1 — 2026-06-11 (release v2.1.38)
**Root cause found:** commit `638d253` shipped the new browser-profile launch
implementation but did NOT bump `backend/VERSION`. Consequence: only the cloud
got the code; Native + Electron customers were stuck on v2.1.37 and the
"Launch Browser Profile" feature silently failed on the desktop.

**Changes (one commit, `949f1c6`):**
1. `backend/VERSION` 2.1.37 → 2.1.38 — re-arms the Native + Electron build
   workflows so the browser-profile launcher actually reaches customers.
2. `backend/cloud_proxy_module.py` — forward `/api/banners/active` and
   `/api/system/public-latest` to the cloud. Now admin-published promo
   banners and the "new version available" prompt show up on Electron /
   Native, not just on the cloud web app.
3. `frontend/src/components/NativeShell.js` — render `<UpdateBanner />` next
   to `<BannerBar />` so desktop customers actually see the in-app upgrade
   prompt.
4. `frontend/src/components/UpdateBanner.js` — when running inside Electron
   (`window.krexion.isDesktop`), call `window.krexion.installUpdate()` over
   IPC instead of POSTing `/api/system/install-update` (which is a no-op on
   the desktop).
5. `electron-desktop/src/preload.js` — expose `krexion.installUpdate()` and
   `krexion.checkForUpdates()` via `contextBridge`.
6. `electron-desktop/src/main.js` — register `ipcMain.handle` for both
   channels. The install handler drives `electron-updater`:
   `checkForUpdates` → `downloadUpdate` → `quitAndInstall(false, true)`.
   Result: one-click in-place upgrade — no manual uninstall / reinstall.

**Verification:**
- Deploy to VPS workflow: ✅ success → https://krexion.com on v2.1.38.
- Build Krexion Desktop (Electron) workflow: ✅ success →
  `desktop-v2.1.38` GitHub release published (Krexion-Desktop-Setup-2.1.38.exe,
  414 MB, with latest.yml manifest for auto-updater).
- Build Native Windows Release workflow: ✅ success →
  `v2.1.38` GitHub release published (Krexion-Setup-v2.1.38.exe, 571 MB).
- `https://krexion.com/api/system/public-latest` → `current=2.1.38`.

## Backlog / Future
- (Optional) Expand workflow `paths:` to include `backend/**.py` so a forgotten
  VERSION bump can't strand desktop customers again.
- (Optional) Move the auto-commit metadata in `.emergent/emergent.yml` to
  `.gitignore` if the user doesn't want it churning the repo.

## Test credentials
See `/app/memory/test_credentials.md`.
