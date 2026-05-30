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

## Bug Fixes (2026-01-30, third iteration)

### Issue 1 — Admin shows "0 clicks" for users with thousands of clicks ✅
**Root cause**: `GET /api/admin/users/stats/all` counted `db.links`, `db.clicks`, `db.proxies` from the MAIN database. But every user's actual content lives in their own per-tenant DB (`krexion_user_<id>`). The main collections are empty for those names → admin saw 0 everywhere.

**Fix** (`backend/server.py`): Endpoint now uses `get_user_db(user_id)` to count from each user's per-tenant DB. Parallel async counts (link/proxy/sub-user). Legacy fallback to main DB for very old accounts.

**Verified**: Admin endpoint now returns `testuser@test.local: links=1, clicks=1817, proxies=5, sub_users=1` (matches user-side dashboard).

### Issue 2 — DB architecture confirmation ✅ (already correct)
- Each main user has separate DB: `krexion_user_<id>`
- Sub-users share parent's DB via `get_db_for_user()`
- IP from main user's click → sub-user's click from same IP → correctly flagged as duplicate (shared DB)

### Issue 3 — CRITICAL: Cross-tenant duplicate IP pollution ✅
**Root cause**: User said the "Offer-side duplicate" message was actually OUR panel's check. Investigation found:
- `get_all_click_ips_from_entire_database()` was scanning EVERY `krexion_user_*` DB and merging IPs
- `is_ip_duplicate_in_any_database()` (link redirect + proxy test) was looking up the IP in EVERY tenant's DB
- So User A's RUT job got "duplicate IP" flags for IPs that only User B had ever clicked from — cross-tenant pollution
- The link-redirect endpoint at `/r/{short_code}` had the same bug — clicks were rejected as duplicate because some unrelated user had ever clicked from the same IP

**Fix** (`backend/server.py`):
- Added `user_id` parameter to `get_all_click_ips_from_entire_database()` → scoped scan to that user's per-tenant DB only
- Added `owner_user_id` parameter to `is_ip_duplicate_in_any_database()` → scoped duplicate check to the link OWNER's tenant only
- Cache keyed by user_id (was global before)
- `rut_burnt_ips` filtered by `user_ids` array (only this user's burns)
- Link redirect (`/r/{short_code}`) no longer scans every tenant's DB — only the link owner's DB + legacy fallback scoped by owner's link_ids
- Updated 4 callers: RUT prep, proxy upload, proxy refresh, link redirect

**Verified** (unit-tested):
- User A clicks from IP 1.1.1.1 → only User A's dup set contains 1.1.1.1
- User B's dup set does NOT contain 1.1.1.1 (isolated tenant)
- `is_ip_duplicate_in_any_database(1.1.1.1, B_db, owner_user_id=B)` → False
- `is_ip_duplicate_in_any_database(1.1.1.1, A_db, owner_user_id=A)` → True

### Issue 4 — Sub-user "all features" option ✅
**Before**: Sub-user had only 5 permissions (view_clicks, view_links, view_proxies, view_conversions, import_data). Main user couldn't delegate features like Real User Traffic, Form Filler, Profile Builder, etc.

**Fix**:
- Backend: Added `SUB_USER_PERMISSION_MAP` covering all 14 features + helper `_build_sub_user_features(perms, parent_features)` that computes effective features capped by parent ownership
- Used the helper in 3 places (auth flow, login, sub-user JWT login endpoint)
- Sub-user can NEVER have more than parent (cap enforced backend-side)
- `max_sub_users` always forced to 0 (sub-users can't create sub-users)
- Frontend: Sub-user create/edit modal shows all 14 permission toggles + "Grant all" / "Revoke all" quick buttons. Toggles for features the parent doesn't own are visually disabled with helpful tooltip.

**Verified**: Sub-user granted all 14 perms → all features True. Granted 2 perms → only those 2 True. Parent revokes real_user_traffic → sub-user real_user_traffic flips to False even if still in sub-user's permissions doc (cap working).

## Files Modified (third iteration)
1. `backend/server.py` — duplicate-IP scoping (per-user), sub-user features helper + 3 call sites, admin stats per-tenant fix
2. `frontend/src/pages/SettingsPage.js` — all 14 permission toggles + Grant-all/Revoke-all buttons + smart badges

No deletions in either file. Only additive/refactoring.
