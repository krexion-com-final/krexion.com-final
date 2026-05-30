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
