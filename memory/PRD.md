# Krexion - Visual Recorder Multi-Session Management

## Problem Statement
User has a public GitHub repo (`krexion.com`) with auto-deploy to VPS. They wanted to:
1. See all currently running Visual Recorder sessions (the "Max 5 concurrent" error was opaque)
2. Stop unwanted sessions to free slots
3. Minimize one session and switch to another (multi-tasking)
4. No breaking changes - additive only - safe to push to main branch

## Architecture
- **Backend**: FastAPI + MongoDB + Playwright (port 8001)
- **Frontend**: React 18 + Tailwind + shadcn-ui (port 3000)
- **Auth**: JWT (regular users + admin)
- **Deploy**: VPS auto-deploy on main branch push

## What's Implemented (2026-01-30)

### Active Sessions Panel
- **Backend** (`backend/visual_recorder.py`):
  - `list_user_sessions(user_id)` → lists all sessions for user with state/url/elapsed/step_count
  - `get_global_session_stats()` → running/max counts
- **API** (`backend/server.py`):
  - `GET /api/visual-recorder/sessions` → returns sessions[], user_session_count, total_running, max_concurrent
- **Frontend** (`frontend/src/pages/VisualRecorderPage.js`):
  - "Active recorder sessions" panel on setup screen
  - X/5 in use counter (red at max)
  - Per-session: hostname, state, elapsed time, step count, Open + Stop buttons
  - 3-second auto-poll
  - Warning banner when at max cap
  - "Minimize" button in recording header (keeps session alive in background)

## Files Modified
1. `backend/visual_recorder.py` (+46 lines, 0 deletions)
2. `backend/server.py` (+23 lines, 0 deletions)
3. `frontend/src/pages/VisualRecorderPage.js` (+189 lines, 0 deletions)
**Total: 258 lines added, 0 deletions, 3 files only**

## Test Credentials (preview only)
- Admin: admin@krexion.local / admin123
- Test user: testuser@test.local / test12345

## Backlog (future)
- Stop-all-my-sessions button (bulk action)
- Per-session "rename" so user can label sessions
- Persistence: rebuild sessions list across pod restarts (currently in-memory)

## Bug Fix (2026-01-30, second iteration)

### ProxyJet Duplicate IP — Cross-job persistence
**Bug**: Every time a RUT job started, `duplicate_ip_set` was rebuilt from `clicks` collection + `rut_burnt_ips`. But ProxyJet exit IPs that were picked for visits which never resulted in a recorded click (e.g. browser launch failed, captcha, or visit aborted) were ONLY tracked in the in-memory set, which died with the job. Next job → same IP could come back from ProxyJet pool → "duplicate IP" issue kept recurring.

**Fix** (`backend/real_user_traffic.py`, +25 lines, 0 deletions):
- When the on-demand ProxyJet retry loop picks a unique exit IP (line ~4063), persist it to `rut_burnt_ips` with `reason="proxyjet_picked"` via the existing `_persist_burnt_ip` helper
- Fire-and-forget (`_spawn_live(...)`) so the request stays fast
- Idempotent upsert (existing rut_burnt_ips schema) — re-picking the same IP just bumps `hit_count`
- Failure-safe: any exception in persistence falls back silently to in-memory set behavior

**Verified**:
- ✓ IP correctly persisted (hit_count = 1)
- ✓ Re-persist same IP increments hit_count to 2 and merges job_ids
- ✓ Next job's blocklist load (`db.rut_burnt_ips.find({},...)`) picks up the persisted IP
- ✓ No regressions (pure additive, only 25 lines added)
