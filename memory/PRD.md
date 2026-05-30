# Krexion — Bug-fix iteration log

## Original problem statement
> Repo: https://github.com/dennisedmaartins9-sudo/krexion.com.git (public, user is collaborator)
> User wants to make small bug-fix changes to the existing Krexion app and push them back to `main` via "Save to GitHub". VPS auto-deploys on push. Critical constraints: nothing must be deleted, missed, broken, or conflict on push.

## Architecture (existing)
FastAPI (backend/server.py 17k lines + 23 sub-modules) + React 18 (CRA + Tailwind + shadcn-ui) + MongoDB.

## Bug fixed this session
**"Duplicate IP — IP: unknown" false-positive block during RUT jobs**

### Root cause
1. `get_all_client_ips()` returns literal string `"unknown"` when no IPv4 can be detected (e.g. visitor over IPv6-only / CDN strips IP).
2. Redirect handler `if client_ip and ":" not in client_ip:` admitted `"unknown"` as a valid IP and queried `{"ip_address": "unknown"}` against MongoDB.
3. Click-storage line `primary_ip_for_storage = ipv4 or client_ip` saved `"unknown"` literal as `ip_address` on the click document.
4. → Every subsequent visitor whose IPv4 also failed detection matched the SAME `"unknown"` row and got falsely blocked with the "Duplicate IP" page.
5. Fallback `{"ip_address": "no-ipv4-detected"}` sentinel had the same self-poisoning trap.

### Fix (single file: `backend/server.py`, +61 / -19)
1. Duplicate-check section (~line 12549): added `_is_valid_dup_ipv4()` helper that rejects `unknown / Unknown / no-ipv4-detected / "" / None / IPv6`. All IP additions to `ip_conditions` now guarded by it.
2. Removed self-poisoning sentinel fallback. If no real IPv4 is detected → `ip_conditions` stays empty → duplicate check is skipped → click passes.
3. New `elif not ip_conditions:` branch before the Mongo query (also prevents `{"$or": []}` invalid-query error).
4. Click storage (~line 13205): `primary_ip_for_storage` now stores `None` instead of literal `"unknown"` when no real IPv4 is available. Frontend UX unchanged (`.get("ip_address", "unknown")` still displays "unknown").

### Tests run (all pass)
- IPv6-only request → 302 (was 403) ✅
- Same IPv6-only request twice → 302 + 302 (was 403) ✅
- Pre-existing legacy `"unknown"` click in DB does NOT trigger false block ✅
- **Real duplicate (same IPv4 twice)** still blocked → 403 ✅ (regression safe)
- Different IPv4 → 302 ✅

### What was NOT touched (per user's strict constraint)
- `get_all_client_ips()` function
- IPv6 handling rules elsewhere
- Click document schema / field names
- Existing MongoDB data (legacy `"unknown"` rows stay; harmlessly ignored by new query)
- Frontend code (zero changes)
- Any other file

## Push status
Working tree has exactly 1 modified file: `backend/server.py`. `.env` files are gitignored. Ready for user to click "Save to GitHub" → pushes to `origin/main` without conflict.

## Backlog / next items (none currently open)

---

## Iteration 2 — 2026-05-30: Per-visit manual kill button in Live Visual Grid

### User ask (Roman Urdu)
> "rut job mein agr kisi profile mein koi issue ai to os ko manualy close krne ka option ho ta k mazeed os pr time waste na ho or next profile pr kam ho sake — like aik concurrent pr kaam ni thk hoa koi masla aya to os ko band kr ne ka option ho ta k next pr ja sake"

### What was built
A **"kill" button** on every tile of the Live Visual Grid that lets the user abort ONE stuck/problematic in-flight visit (e.g. "User ineligible" page loop) without stopping the whole job. The concurrency slot frees instantly so the dispatcher spawns the next pending visit into it.

### Files changed (3, +207 / -1 lines)
1. **backend/real_user_traffic.py** — Added per-visit task registry (`_visit_tasks` dict on `RUT_JOBS[job_id]`) plus `cancel_visit(job_id, visit_index)` helper. Hooked the registry into all 3 task-spawn points (conversions dispatcher, legacy fixed-size gather, clicks budget dispatcher) so every visit is trackable.
2. **backend/server.py** — New endpoint `POST /api/real-user-traffic/jobs/{job_id}/visits/{visit_index}/cancel` with proper user-feature & ownership checks. Returns clean 404/400 on edge cases.
3. **frontend/src/pages/RealUserTrafficPage.js** — Added `cancelOneVisit()` handler with optimistic UI flip + toast feedback. Each tile now renders a small red "kill" button (top-right, just below the status badge) ONLY while the visit is in `running` state. Cancelled tiles show a `⊘ cancelled` badge. `data-testid="rut-visual-tile-kill-{vid}"`.

### How it works under the hood
- User clicks "kill" → POST to the new endpoint → `cancel_visit()` calls `asyncio.Task.cancel()` on the registered task → CancelledError propagates through `worker()` / `process_one()` at the next await → Playwright context cleans up via existing `try/finally` & `async with` patterns → `in_flight` set shrinks → dispatcher's spawn loop replenishes the slot with the next visit.
- `live_visits[vid].status` is flipped to `"cancelled"` immediately so the 800ms-poll UI reflects the kill within one frame.
- `push_live_step()` records a `manual_cancel` audit entry in the Live Activity modal.

### Tests run (all pass)
- Module-level `cancel_visit()` end-to-end: task gets cancelled, raises CancelledError, registry cleaned up, live_visits flipped to "cancelled" with stage="manual_cancel" ✓
- Double-cancel returns `already_done` ✓
- Cancel non-existent visit → `visit_not_found_or_already_done` ✓
- Cancel non-existent job → `job_not_found` ✓
- Cancel on stopped/completed job → `job_not_running` ✓
- New endpoint reachable via API, returns proper 404/400 with auth ✓
- Frontend compiles cleanly, kill button test-id present in bundle, login page renders without errors ✓

### What was NOT touched
- `process_one()` / `worker()` internal logic — only the outer wrapper registers tasks
- `cancel_event` / `target_drain_event` (job-wide cancel) — totally untouched, kill button is additive
- Visit/click DB schema
- Any existing endpoint behaviour
- Any other React page or component
