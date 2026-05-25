# Krexion.com — Project Memory

## Original Problem Statement
User collaborated on repo `https://github.com/dennisedmaartins9-sudo/krexion.com.git` (public, main branch).
Goal: Verify that all heavy features are configured to run on the customer's PC (not VPS) to prevent VPS overload, and fix any bugs or conflicts that leak heavy work onto the cloud edge.

Constraint: Nothing existing should break. Changes are pushed via "Save to GitHub" to main branch by the user; auto-deploys to VPS. Customer-side updates flow via admin Releases page.

## Architecture
- Backend: FastAPI (Python, `backend/server.py` 15.7k+ lines) + 25+ modules (CPI, AdsPower, Crypto Payments, Releases, Sync, Bridge, Form Filler, AI Vision, Email Service, License, etc.)
- Frontend: React + craco (`frontend/`) — 43 pages
- Database: MongoDB
- Deployment modes:
  - `KREXION_MODE=cloud` → public krexion.com VPS (edge: auth, links, licensing, admin, dashboard)
  - `KREXION_MODE=local` → customer desktop install (heavy features execute here)
  - `STRICT_CLOUD_HEAVY_BLOCK=true` (default, 2026-05) → cloud refuses heavy work, forces customer to use desktop app

## Work Done (2026-05-25 — Iteration 1: Heavy-Feature Audit)
Audited all heavy endpoints in `backend/server.py`. Found 9 endpoints already guarded with `Depends(require_local_mode)` + `/proxies/bulk-test` with smart bridge fallback.

### Bugs Found & Fixed (all backend-only, server.py)
1. **B1** — Startup auto-installed Playwright Chromium (~150MB) even on cloud edge → wrapped in `if not (IS_CLOUD and STRICT_CLOUD_HEAVY_BLOCK)`. (Lines ~15397-15418)
2. **B2** — Startup orphan-job reaper auto-resumed queued/running RUT jobs by spawning Playwright on the VPS → now skips auto-resume on cloud-strict mode, leaves jobs `queued` with a prep_step message so the customer's desktop bridge worker picks them up. (Lines ~15490-15527)
3. **B3** — `POST /api/real-user-traffic/jobs/{job_id}/retry` missing guard → added `_cloud_gate: bool = Depends(require_local_mode)`.
4. **B4** — `POST /api/real-user-traffic/engine-prewarm` missing guard → added same guard.
5. **B5** — `POST /api/clicks/generate-traffic` missing guard (inconsistent with sibling `/clicks/import-ips`, `/clicks/import-bulk` which were guarded) → added same guard.

Diff: +63 / -5 lines in `backend/server.py` only. No other files touched.

### Verification
- Backend restart: clean, no syntax errors, all modules loaded.
- Public site (`https://krexion-preview-2.preview.emergentagent.com/`): loads correctly post-fix.
- Preview runs in `KREXION_MODE=local` so behavior is unchanged on preview (only cloud VPS sees new behavior).
- Guarded endpoint count: 6 → 9.
- Backward compatible: admin can still flip `STRICT_CLOUD_HEAVY_BLOCK=false` to fall back to legacy cloud-execution.

## Next Action Items
- User to "Save to GitHub" → auto-deploys to VPS. On krexion.com VPS, new safer behavior takes effect immediately:
  - VPS boot no longer downloads Chromium.
  - VPS restart no longer spawns Playwright BG tasks for orphan RUT jobs — they wait for the customer's desktop app.
  - Retry / prewarm / generate-traffic endpoints from cloud UI return 503 with the existing "open desktop app" message.
- No customer-side release update needed (server-only change).

## Backlog / Future
- (Optional, P2) Audit `visual-recorder/{session_id}/*` continuation endpoints — currently rely on `/start` being gated; if a session somehow exists on cloud, click/type/navigate would run Playwright.
- (Optional, P2) Move the same gate to `/api/diagnostics/repair` for the Chromium-install action so admin's "Auto Repair" doesn't reinstall it on cloud edge.
