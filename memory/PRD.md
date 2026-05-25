# Krexion.com — Project Memory

## Original Problem Statement
User collaborated on repo `https://github.com/dennisedmaartins9-sudo/krexion.com.git` (public, main branch). Goal: Verify heavy features run on customer's PC, not on VPS. Fix any bugs/conflicts. Then add an admin-dashboard "Heavy Features Status" badge showing VPS protection + bridge offload stats.

Constraint: Don't break anything existing. User pushes via "Save to GitHub" → auto-deploys to VPS. Customer-side updates flow via admin Releases page.

## Architecture
- Backend: FastAPI (Python, `backend/server.py` 15.8k+ lines) + 25+ modules
- Frontend: React + craco (`frontend/`) — 43 pages
- Database: MongoDB
- Deployment modes:
  - `KREXION_MODE=cloud` → public krexion.com VPS edge
  - `KREXION_MODE=local` → customer desktop install (heavy features execute here)
  - `STRICT_CLOUD_HEAVY_BLOCK=true` (default, 2026-05) → cloud refuses heavy work

## Work Done

### Iteration 1 (2026-05-25) — Heavy-Feature Audit + 5 Bug Fixes
Bugs fixed in `backend/server.py` (+63/-5):
1. **B1** Startup auto-installed Playwright Chromium even on cloud edge → wrapped in cloud-strict gate
2. **B2** Startup orphan-job reaper auto-resumed RUT jobs on VPS → now leaves jobs `queued` for customer bridge
3. **B3** `POST /api/real-user-traffic/jobs/{id}/retry` missing guard → added `require_local_mode`
4. **B4** `POST /api/real-user-traffic/engine-prewarm` missing guard → added
5. **B5** `POST /api/clicks/generate-traffic` missing guard → added (consistency with siblings)

Guarded endpoint count: 6 → 9.

### Iteration 2 (2026-05-25) — Admin "Heavy Features Status" Badge
**Backend** (+123 lines in `server.py`): New endpoint `GET /api/admin/heavy-features-status` (admin auth required) returns:
- `deployment`: mode, is_cloud, strict_heavy_block, protected flag, friendly note
- `bridge_24h`: total/done/failed/pending bridge job counts + by_feature breakdown
- `customer_pcs`: online_now (heartbeat fresh), active_24h (any heartbeat 24h)
- `last_bridge_job_at` / `last_bridge_job_feature`

**Frontend** (+128 lines in `AdminDashboard.js`):
- New state `heavyStatus` populated alongside other admin data
- Color-adaptive banner at top of dashboard (above stats grid):
  - GREEN — VPS Protected (cloud + strict mode)
  - BLUE — Local Install
  - YELLOW — Cloud edge with STRICT block disabled (warning)
- Live counters: Routed to PCs (24h), Total Bridge Jobs, PCs Online Now, PCs Active 24h
- Per-feature breakdown chips (top 3) + pending/failed badges
- All elements have `data-testid` for testing

### Verification
- Backend: endpoint tested with curl + admin token → returns correct JSON shape ✅
- Frontend: ESLint clean ✅, webpack compiled with no new errors ✅
- Backend restart: clean, no syntax errors ✅
- Backward compatible: works on local install (BLUE banner) and cloud strict OFF (YELLOW)

## Next Action Items
- User to "Save to GitHub" → VPS auto-deploys → admin dashboard shows live Heavy Features Status badge
- No customer-side release needed (backend + admin UI only)
- On the production VPS (KREXION_MODE=cloud), the banner will display GREEN "VPS Protected" with live offload stats

## Backlog / Future (P2)
- Audit `/visual-recorder/{session_id}/*` continuation endpoints for defense-in-depth
- Gate `/api/diagnostics/repair` Chromium-install step behind same flag
- Add 7-day / 30-day trend chart for bridge job throughput
