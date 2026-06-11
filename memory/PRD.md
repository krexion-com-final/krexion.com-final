# Krexion — Product Requirements & Build Log

## Problem Statement (original)
User owns `dennisedmaartins9-sudo/krexion.com` (private collaborator access).
They want: end-to-end repo exploration, bug fixes, push to `main` only when
explicitly requested, builds reaching ALL surfaces (Cloud VPS, Native Windows,
Electron desktop) with no regressions, login for preview testing, and a
conflict-free main branch.

## Architecture
- **Cloud (VPS)**: FastAPI + React + MongoDB. Auto-deploys on every push.
- **Native Windows installer**: Inno-Setup ~571 MB with embedded Python,
  MongoDB Portable, Edge WebView2, Playwright Chromium. Triggers on
  `backend/VERSION` change only.
- **Electron Desktop**: same backend on 127.0.0.1:8088 with KREXION_MODE=native.
  Auto-updates via electron-updater. Triggers on `backend/VERSION` change only.

## Iteration 1 — release v2.1.38 (2026-06-11)
**Root cause:** commit `638d253` (browser-profile launch implementation) never
bumped `backend/VERSION`, so Electron + Native builds never ran. Customer
desktop apps stuck on v2.1.37 → "Launch Browser Profile" failed silently.

**Changes (commit `949f1c6`):**
- `backend/VERSION` 2.1.37 → 2.1.38 to re-arm Electron + Native builds.
- `backend/cloud_proxy_module.py` — proxy `/api/banners/active` and
  `/api/system/public-latest` to cloud so discount banners and the
  "new version available" prompt show up on Electron + Native too.
- `frontend/src/components/NativeShell.js` — render `<UpdateBanner />` so
  desktop customers see in-app upgrade prompt.
- `frontend/src/components/UpdateBanner.js` — when in Electron, call
  `window.krexion.installUpdate()` IPC instead of the no-op HTTP path.
- `electron-desktop/src/preload.js` — expose `krexion.installUpdate()` +
  `krexion.checkForUpdates()` via contextBridge.
- `electron-desktop/src/main.js` — `ipcMain.handle()` for both channels
  driving electron-updater → quitAndInstall.

**Outcome:** all 3 workflows green. v2.1.38 + desktop-v2.1.38 published.

## Iteration 2 — hotfix v2.1.39 (2026-06-11)
**Regression in 2.1.38:** Electron app crashed at startup with
"ipcMain is not defined". The previous edit added `ipcMain.handle(...)`
calls in `main.js` but the original `require('electron')` destructure on
line 21 was never updated to include `ipcMain` (the first search_replace
silently dropped — only the function body and the boot() call landed).

**Changes (commit `bbadaae`):**
- `electron-desktop/src/main.js` line 21 — added `ipcMain` to the
  destructure: `const { app, ..., net, ipcMain } = require('electron');`.
- `backend/VERSION` 2.1.38 → 2.1.39 to force a new release so existing
  v2.1.38 customers are auto-upgraded by electron-updater on next launch
  (typically within seconds; manually via Help → Check for Updates).

**Outcome:** all 3 workflows green. v2.1.39 + desktop-v2.1.39 published.
- Cloud: `current=2.1.39`.
- `node -c electron-desktop/src/main.js` → syntax OK.
- All `ipcMain` references (lines 21, 618, 642) consistent.

## Released versions on GitHub
- v2.1.39 (Native), desktop-v2.1.39 — current
- v2.1.38 (Native), desktop-v2.1.38 — withdrawn (Electron startup crash)
- v2.1.37 (Native), desktop-v2.1.37 — last good before v2.1.38 series

## Backlog
- Expand workflow `paths:` to include `backend/**.py` and
  `electron-desktop/**` so a forgotten VERSION bump can't strand desktop
  customers again.
- Consider a "What's New" modal on first launch after auto-update so
  customers actually see new features (browser-profile etc.).
- Consider auto-yanking broken GitHub releases (delete `latest.yml`) when
  a regression is detected, so electron-updater stops serving them.

## Test credentials
See `/app/memory/test_credentials.md`.
