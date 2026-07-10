# Krexion.com — Collaborator Session PRD

## Original problem statement
Collaborator on https://github.com/krexion-com-final/krexion.com-final.
User makes bug-fix / improvement requests. All changes must be preserved
(nothing deleted, nothing broken), pushed to `origin/main`, and auto-
deployed via `.github/workflows/deploy.yml` (self-hosted VPS runner).

## Architecture (as of 2026-07)
- **Backend**: FastAPI (`backend/server.py` + ~40 modules), MongoDB, uvicorn.
- **Frontend**: React 19 + CRACO + Radix UI + Tailwind (`frontend/`).
- **Cloud edge**: krexion.com (VPS) — this is where `KREXION_MODE=cloud`.
- **Customer desktop**: Native (Inno-Setup / PowerShell installer) + Electron
  desktop package + `Krexion-User-Package.zip`. Heavy features (browser
  automation) run on customer PC; VPS only handles links + coordination.
- **Auto-deploy**: push to `main` → `.github/workflows/deploy.yml`
  runs on self-hosted `krexion-vps` runner → rsync → docker rebuild → up.

## Session history

### 2026-07-10 — v2.5.3 fix rotating-gateway proxy exhaustion
* **Files touched**: `backend/proxy_provider_module.py`,
  `backend/server.py`, `backend/cpi_module.py`,
  `backend/browser_profile_module.py`.
* **Commit**: `8b9a66b` on main. Deployed to VPS successfully.
* **Bug**: RUT jobs with `no_repeated_proxy=on` aborted after visit #1
  with "No more proxies available" when using a rotating-gateway
  provider (BestGo / Bright Data / IPRoyal / Oxylabs / Soax / SmartProxy)
  because the resolver returned ONE identical line per fetch.
* **Fix**: New `get_proxy_lines_from_provider(user_id, provider_id, count)`
  bulk resolver + auto session-token rotation (`-session-XXX`,
  `-sessid-XXX`, `-sessionid-XXX`, `-sess-XXX`, `{sid}` placeholder).
  RUT now fetches `total_clicks` lines; CPI fetches `target_count`;
  Browser Profile launch still fetches 1 line but with rotated session
  so relaunches don't reuse the same sticky IP.
* **Backward compat**: 100%. No config schema change, no field rename,
  legacy single-line resolver still exported.

## Deploy rules (locked-in by user)
1. **NEVER** push automatically. Wait for explicit "deploy" / "save to git"
   instruction from user. Batch multiple changes into one deploy.
2. All changes must apply to **cloud VPS + native app + Electron app +
   customer package** so no user is left on a broken version.
3. Preserve `.emergent` folder, git identity `Krexion Collaborator
   <krexion-collaborator@krexion.com>`, `pull.rebase=false`.
4. `.env` files are gitignored — never commit secrets.
5. Never delete/rename/refactor unrelated files.

## Credentials (preview only — see test_credentials.md)
- Admin login used to test on Emergent preview URL — see
  `/app/memory/test_credentials.md`.
