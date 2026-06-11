# Krexion — Product Requirements & Build Log

## Architecture
- **Cloud (VPS)**: FastAPI + React + MongoDB. Auto-deploys on every push.
- **Native Windows installer**: Inno-Setup ~571 MB. Triggers on backend/VERSION.
- **Electron Desktop**: Same backend on 127.0.0.1:8088 with KREXION_MODE=native.
  Auto-updates via electron-updater. Triggers on backend/VERSION.

## Iteration 1 — v2.1.38 (cross-platform browser-profile + in-app updater)
**Root cause:** commit 638d253 added browser-profile launch but didn't bump
VERSION, so Electron + Native builds never ran. Customers stuck on 2.1.37.
**Fix (commit 949f1c6):** VERSION bump + cloud-proxy for banners/version
endpoints + UpdateBanner in NativeShell + IPC bridge in Electron.

## Iteration 2 — v2.1.39 (hotfix: Electron startup crash)
**Bug:** v2.1.38 Electron crashed at startup with "ipcMain is not defined"
because the require('electron') destructure on line 21 of main.js never
included ipcMain (the search_replace silently dropped — only the IPC
handlers landed).
**Fix (commit bbadaae):** add ipcMain to the destructure.

## Iteration 3 — v2.1.40 (Browser Profiles visible + actually launches)
**Bugs:**
- Browser Profiles sidebar item was missing from NativeShell.js (Electron
  uses NativeShell, not DashboardLayout). User saw the cloud feature but
  no menu entry inside the desktop app.
- Even if the user navigated manually to /browser-profiles, the launch
  flow failed at runtime because the Electron installer shipped the
  Playwright Python package but never downloaded the Chromium binary.
  `prepare-resources.js` had `playwright` in the verify list but never
  ran `playwright install chromium`. Backend logged
  `Playwright chromium-headless-shell rev XXX missing` and every heavy
  feature (Browser Profile / RUT / Visual Recorder / automation) was
  silently broken.
**Fix (commit ceeef39):**
- `frontend/src/components/NativeShell.js`: import Globe lucide icon and
  add Browser Profiles to the Traffic Engine group (next to Real-User
  Traffic and Visual Recorder, matching DashboardLayout 1:1).
- `electron-desktop/scripts/prepare-resources.js`: new `prepareChromium()`
  invokes the embedded Python's `playwright install chromium
  chromium-headless-shell` and bundles them under
  `resources/krexion/chromium/`. Same approach as the Inno-Setup workflow.
- `electron-desktop/src/main.js` startBackend env: set
  `PLAYWRIGHT_BROWSERS_PATH` to `<resourcesRoot>/chromium` so the backend
  finds the bundled browser offline without falling back to
  `%USERPROFILE%\AppData\Local\ms-playwright` (empty on fresh install).
- `backend/VERSION` 2.1.39 → 2.1.40 to re-arm both build workflows.

**Outcome:** Installer size grew from 414 MB → 581 MB (Chromium adds
~167 MB). All 3 workflows green. desktop-v2.1.40 + v2.1.40 published.
- Cloud: `current=2.1.40` (https://krexion.com/api/system/public-latest).
- desktop-v2.1.40 latest.yml pushed to krexion.com/downloads/desktop/.
- Existing 2.1.39 Electron customers will be auto-upgraded on next launch
  via electron-updater.

## Released versions
- v2.1.40 (Native), desktop-v2.1.40 — current. Browser Profile works end
  to end on all 3 surfaces.
- v2.1.39 (Native), desktop-v2.1.39 — Browser Profile menu missing on
  desktop; launch would have failed even if reached.
- v2.1.38 desktop — withdrawn (Electron startup crash).

## Backlog
- Cache the chromium-bundle in `electron-desktop/.cache/chromium/` and
  restore it via actions/cache to shave 5–10 min off each build.
- Expand workflow `paths:` to include `backend/**.py`,
  `electron-desktop/**`, and `frontend/src/components/NativeShell.js`
  so a forgotten VERSION bump can't strand desktop customers again.
- Add a pre-release smoke job that spawns the packaged Electron app with
  `--no-sandbox` for 5 s and checks the backend health endpoint, so a
  startup-crash regression never reaches `main` again.

## Test credentials
See `/app/memory/test_credentials.md`.
