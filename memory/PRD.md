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

---

## Iteration 3 — 2026-05-30: Robust multi-strategy step matching for Visual Recorder

### User ask (Roman Urdu)
> "visual recorder mein json bnaya pr wo perfect ni chal raha — step match krne k liye mazeed option dal do jese abi siraf selector hai xpath b add ho page content b add ho ye sab option ho agr use krne chahein to kr lien ni to chor dein es se ye ho ga next time koi issue ni ho ga agr selector kisi waja se miss ho jata hai yan rut k doran change hota hai to wo step skip na kre wo xpath se step match kr le or agr xpath b miss hota hai to screen se match kr le"

### What was built
Every recorded **click(form_fill)**, **fill**, **check**, **select**, **dropdown** step now ALSO carries a compact `fallbacks` dict capturing the SAME element by 5 complementary strategies:
- `xpath` — stable xpath anchored on first stable attribute (id / data-testid / name / aria-label / placeholder)
- `xpath_abs` — full root-to-element xpath
- `text` — visible text content (trimmed, ≤80 chars)
- `tag` — element tag (button, input, etc.)
- `attrs` — filtered attribute snapshot (id, name, data-testid, role, type, aria-label, placeholder, etc. — class/style/onclick deliberately excluded)
- `nth` — position among same-tag siblings

At RUT replay, the new `_step_fallbacks(step)` helper expands these into Playwright-compatible selectors prepended to the existing `_alias_alts_for + _field_type_alts_for` chain inside `_smart_wait_for_selector`. New resolution pipeline:
1. **exact selector** recorded (fast path, unchanged)
2. `xpath_stable` → `xpath_abs` (xpath rescues)
3. attribute combos (data-testid, id, name, aria-label, role, etc., tag-scoped & case-insens variants)
4. tag-scoped text match (`button:has-text("Continue")`)
5. Playwright `text=` engine
6. user-aliased selectors (legacy self-healing store)
7. token-derived & field-type fallbacks (legacy)

### Files changed (2, +348 / −33)
1. **backend/visual_recorder.py** — Added module-level `_RICH_ELEMENT_CAPTURE_JS` (in-page JS computing xpath_stable, xpath_abs, attrs, nth_of_type) + `_build_fallbacks()` helper that distils the rich info into a compact dict (~280 bytes per step). Replaced inline JS in `click_at_point` with the new helper. Attached `fallbacks` to recorded click(form_fill), check, dropdown(select via bind_dropdown), and fill(via type_text) steps. Added session-level caches (`_form_fill_fallbacks`, `_pending_dropdown_fallbacks`) so two-stage bindings (click → /type, click → /dropdown-bind) carry the SAME fallbacks across the round-trip.
2. **backend/real_user_traffic.py** — Added `_step_fallbacks(step)` module-level helper that translates the embedded dict into ordered Playwright selector alternatives. Wired into all 3 `_smart_wait_for_selector` call sites in `_execute_automation_steps` (pre-wait for `select/check/uncheck`, pre-wait for `fill/click/type/press/hover`, and the dedicated `wait_for_selector` action).

### Tests run (all pass)
- **Unit (9 cases)**: `_build_fallbacks` with full info / sparse info / None / empty + `_step_fallbacks` for old recordings / empty fallbacks / non-dict step + priority ordering check + quote-escaping in text ✓
- **E2E on real Chromium (5 scenarios)** verified via Playwright headless:
  1. Recorded `#submit-btn` is wrong → rescued via `[data-testid="submit-cta"]` ✓
  2. No attrs captured but xpath was → rescued via `xpath=//button[@data-testid='submit-cta']` ✓
  3. Only text captured → rescued via `button:has-text("Continue Now")` ✓
  4. Old recording (no fallbacks key) → still times out cleanly as before (no regression) ✓
  5. Fill on renamed `#email_address` input → rescued via `[placeholder="Your email"]` ✓

### Backward compatibility
- Old recorded JSONs (no `fallbacks` key) → `_step_fallbacks` returns `[]` → pipeline collapses to legacy `_alias_alts_for + _field_type_alts_for` behaviour. Zero risk to existing customer recordings on the VPS.
- The `fallbacks` dict is opt-in at READ time — engine ignores it gracefully if missing. No version bump needed on the JSON schema.

### Not implemented (deliberately, with reasoning)
- **OCR / image-based "screen match"** — would require shipping a 100MB+ vision model and adding latency per step. Decision: text-based DOM match is FUNCTIONALLY equivalent (same human-visible label) and 1000× faster. If a user later asks for vision-based match specifically, can add tesseract+opencv as a separate iteration.

### What was NOT touched
- `_smart_select_with_fallback` / `_smart_check_with_fallback` internals — they read the already-resolved selector from the pre-wait, so they get the fallback benefit "for free".
- Existing `_alias_alts_for`, `_field_type_alts_for` — fallbacks are PREPENDED, not replacing.
- Visual recorder JSON schema versioning / export format — adding a new optional key.
- Any frontend page — recorder JSON is generated server-side, UI doesn't need changes.
