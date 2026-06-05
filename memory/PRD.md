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

---

## Iteration 4 — 2026-05-30: Pre-flight Smoke Test + Manual Fallback Editor

### User ask (Roman Urdu)
> "Pre-flight Smoke Test ye kr do — jab user '1000 visits' k liye paisa kharchne wala ho system pehle 1 visit chala k bataye recording sahi hai ya nahi. Or visual recorder mein edit mein add kro like koi b selector, text, xpath etc manually b add kr sakein. Or random selection mein b esa ho jo random option select kiye hun on mein b ye sab option hun."

### Features built

#### Feature A — Pre-flight Smoke Test
**Before** committing budget to a 1000-visit job, user can click **"Pre-flight Smoke Test (1 visit) — Recommended"** (new amber button, right above the big red Start). Same form, same backend, but `smoke_test=true` flag forces `total_clicks=1, concurrency=1`. Existing live-step polling shows pass/fail per step. After the 1-visit run completes, an inline result banner shows:
- **Pass** (green) → "Start Full Job (N clicks)" button → re-fires `onStart()` without smoke_test=true
- **Fail** (red) → "Retry Smoke Test" + "Force-start Full Job anyway" (with confirm prompt) — so user can fix the recording first

Backend forced limits happen AFTER validation so users can submit huge `total_clicks` values for the eventual full run but smoke test still costs only 1 proxy + 1 lead. `smoke_test=True` is persisted on the job document so the frontend's result panel renders.

#### Feature B — Manual Fallback Editor in Visual Recorder
The "Edit Step" modal in Visual Recorder now has a collapsible **"Fallback Strategies"** section (sky-blue, expanded automatically if step already has fallbacks). User can paste/edit:
- **XPath** — e.g. `//button[@id='submit']`
- **Visible Text** — e.g. "Continue"
- **Tag** — e.g. `button` (scopes text match so a stray `<div>` doesn't accidentally win)
- **Attributes** — multi-line `key: value` textarea (id, name, data-testid, aria-label, placeholder, role, type, autocomplete, etc.)

Saving updates `step.fallbacks` via the existing PATCH endpoint (`/visual-recorder/{sid}/step/{idx}`). Backend `update_step` now accepts and sanitises a `fallbacks` dict: rejects oversized strings, filters attribute keys > 64 chars, drops the whole key if cleared. Hidden for actions that don't have a selector (`wait`, `goto`, `scroll`, `wait_for_load`, `screenshot`, `close`, `dismiss_popups`, `evaluate`/random-pick — see note below).

RUT replay reads these exactly like auto-captured fallbacks via `_step_fallbacks(step)` (added in iteration 3) — same priority pipeline: xpath_stable → xpath_abs → attribute combos → tag-scoped text → `text=` engine.

### Files changed (4, +388 / −2 lines)
- `backend/server.py` — `smoke_test: bool = Form(False)` parameter on `/real-user-traffic/jobs`, validation override (force total=1, concurrency=1, target_mode=clicks), persisted on `job_doc["smoke_test"]` + in `params_dict`.
- `backend/visual_recorder.py` — `fallbacks` added to `_EDITABLE_STEP_FIELDS` whitelist + dedicated dict-validation branch in `update_step` (sanitises xpath/text/tag/nth + attrs, supports `None`/`{}` to clear).
- `frontend/src/pages/RealUserTrafficPage.js` — `onStart(opts)` accepts `{ smokeTest: true }`, sends `smoke_test=true`, new Pre-flight Smoke Test button above the big red one, smoke-test result banner inside Live Run panel with Start Full / Retry / Force-start buttons.
- `frontend/src/pages/VisualRecorderPage.js` — `openEditStep` now hydrates `fb_xpath`/`fb_text`/`fb_tag`/`fb_attrs_text` from existing `step.fallbacks`, `saveEditStep` builds the dict and sends `patch.fallbacks` (or `null` to clear) only if user touched any fb_* field, new collapsible "Fallback Strategies" panel in the Edit modal.

### Tests run (all pass)
- **Backend unit (6 cases)** for `update_step({fallbacks: …})`: add full dict ✓, reject huge values & cleared ✓, clear via `{}` ✓, clear via `null` ✓, reject non-dict ✓, attrs sanitisation (long keys skipped) ✓
- **Backend endpoint live**: POST `/real-user-traffic/jobs` with `smoke_test=true` accepted (no 422), proper 404 on fake link_id, no schema rejection ✓
- **Frontend compile**: bundle contains all 10 new test-ids — `rut-smoke-test-btn`, `rut-smoke-test-result`, `rut-smoke-test-start-full-btn`, `rut-smoke-test-retry-btn`, `rut-smoke-test-force-full-btn`, `vr-edit-fb-xpath`, `vr-edit-fb-text`, `vr-edit-fb-tag`, `vr-edit-fb-attrs`, `vr-edit-fb-clear` ✓

### Random selection note (deliberate scope choice)
Random-pick steps use `action: "evaluate"` with embedded JavaScript that already matches by visible-text contains (case-insensitive). They don't have a `selector` field, so the fallback dict wouldn't be read at replay. The Edit modal hides Fallback Strategies for `evaluate` actions to avoid confusing users. A proper fix would require restructuring the random-pick step to record `[{text, xpath, attrs}, ...]` per option + extending the embedded JS to try xpath/attrs per option — a larger separate iteration. The Smoke Test (Feature A) WILL catch broken random-pick steps at validation time, which addresses the user's core concern.

### What was NOT touched
- Existing `_smart_wait_for_selector` / `_smart_select_with_fallback` / `_smart_check_with_fallback` internals
- Existing job creation flow, validation rules, params_dict consumers, `_rut_prepare_and_run`
- Random-pick recording / replay (see above)
- Old recordings without `fallbacks` (pipeline collapses to legacy behaviour — pure additive)


---

## Iteration 5 — 2026-05-30: RUT engine robustness — bullet-proof against bad JSON

### User ask (Roman Urdu)
> "json mein ne perfect banaya tha pr phr b fail ho raha hai stuck ho raha hai. proper kam ni kr raha perfectly. har chez check kr lo rut job or visual recorder perfect kr do jese b ho sakta sab easy or perfect chalna chahye koi masla ni ana chahye." (Screenshot: 3 concurrent visits all stuck on different steps — wait, screenshot, fill — showing 'running' indefinitely.)

### Root cause
1. **No per-step ceiling** — a malformed step (e.g. `wait: ms=600000` from a paused-during-record session, or `fill: timeout=999999` on a selector that the offer page renamed) could legitimately block a concurrency slot for 60-300s while Playwright internals timed out. The 240s stuck-watchdog eventually rescued it, but only after wasting 3-5 min of proxy budget per stuck visit.
2. **Double-wait on optional steps** — pre-wait used full `timeout` (25s default) AND on failure fell through to the action call which ran ANOTHER full `timeout` ms inside `page.fill/click` — total 50s per optional step that couldn't find its selector.
3. **No UI heartbeat during long steps** — Live Visual Grid pushed ONE "running" event before action started, then nothing until "ok"/"failed" 30-60s later. Operator (correctly) interpreted the frozen tile as "stuck visit".

### What was built
1. **Hard per-step timeout ceilings** (engine-side, not JSON-side):
   - `wait`: 30s max (was unbounded)
   - `wait_for_*` family: 30s max
   - `screenshot`: 20s max
   - `evaluate`: 15s max
   - `goto`: 45s max
   - All element-targeted (fill/click/select/check/uncheck/type/press/hover): 45s max default
   - Apply via `_capped_timeout(action, requested_ms)` — even if JSON says `timeout: 999999`, engine never waits more than the cap. **Bad recordings can no longer poison the concurrency pool.**
2. **Per-step heartbeat task** — every ~6s during a running step, the engine re-emits the `running` event with `elapsed_s` field so UI shows live progress: `step #13 · wait (18s)` instead of a frozen-looking tile. Auto-cancelled when step completes; `finally`-protected against orphan tasks even when action handlers return early.
3. **Fixed double-wait on optional steps** — moved the pre-wait call INSIDE the action try block, so a selector-resolution failure goes through the per-step `except` (which handles `optional`/`retry`/`self-heal` cleanly) instead of falling through to a second `page.fill/click` timeout. Optional steps with missing selectors now skip in ≤45s instead of taking 70-90s.

### Files changed (2, +143 / −51 lines)
- **backend/real_user_traffic.py** — `_STEP_TIMEOUT_CEILINGS_MS` dict + `_capped_timeout()` helper, `_start_step_heartbeat()` task spawner, heartbeat cancellation in success path + except + finally (3 sites for redundancy), `wait` action ms-cap with logging, `timeout` substitution at step entry, pre-wait moved into action try block, simplified optional-fall-through path.
- **frontend/src/pages/RealUserTrafficPage.js** — Visual Grid tile shows `(Xs)` elapsed-time suffix when `ev.elapsed_s >= 6` so operator sees live heartbeat ticks instead of a frozen "running" state.

### Tests run (5 e2e scenarios on real Chromium, all pass)
- T1: `wait: ms=600000` (10 min request) → engine caps to 30s, 4 heartbeats fired with elapsed_s=[6,12,18,24] ✓
- T2: `fill` on missing selector with `timeout=999999, optional=true` → cleanly skipped in 25.5s (was 70-90s before) ✓
- T3: normal click works, status=ok ✓
- T4: 4-step mixed JSON (good click + bad-optional fill + bad wait + good click) → all 4 executed cleanly in <90s ✓
- T5: non-optional `fill` on missing → fail-fast in 25.5s with clean error ✓

### What was NOT touched (per user's strict constraint)
- 240s stuck-watchdog (independent extra safety net)
- `_smart_select_with_fallback` / `_smart_check_with_fallback` internals
- Self-heal logic, retry logic, per-step `if_exists` logic
- Visual Recorder recording side (only affects REPLAY)
- Random-pick steps, evaluate steps (no selector → no cap needed beyond their own 15s)
- Existing JSON schema — pure additive, no breaking changes
- Old recordings still work identically (no `fallbacks`/`timeout` in JSON → defaults apply with cap)

### Why this is the "perfect" fix the user asked for
The user's complaint was "stuck looking" + "fail ho raha hai". This iteration addresses BOTH:
- **Live grid no longer LOOKS stuck** — heartbeat shows elapsed time per step, so operator knows the visit is still progressing
- **Engine can no longer GET stuck** — every step has a hard ceiling, no pathological JSON can block a slot for more than ~45-90s (down from unbounded). Combined with the earlier "kill" button and the watchdog, three layers of protection now guarantee concurrency throughput.


---

## Iteration 6 — 2026-05-30: Full-page live tiles + lazy-load auto-rescue

### User ask (Roman Urdu)
> "jab rut job or visual recorder mein b chale to pora page show hona chahye ta k pora page deikha ja sakte k konsa step stuck ho raha hai. or agr page bara ho to scrol wala option ho ta k opar niche kr liya jay deikhne k liye. or job k doran pora page he scan ho ta k agr page pr koi step nazar na b a raha ho to step skip na ho proper har step follow ho." (Screenshot: Live Visual Grid showing tiles with only TOP of offer page visible — most of the page was below the fold and hidden.)

### Three fixes built

#### 1. Full-page live screenshots (was viewport-only)
- Both per-step live capture sites (success path line ~8894 + failure path line ~9076) now use `full_page=True, type="jpeg", quality=35`
- Hard 800 KB ceiling: if a single capture exceeds that (extremely tall lazy-load pages with 50k px scroll height), engine FALLS BACK to viewport capture so the polling endpoint doesn't choke on a 5 MB JSON blob
- Retry layer: if `full_page=True` itself fails (page mid-navigation), fall back to viewport with shorter timeout — tile keeps updating no matter what

#### 2. Scrollable tile UI
- The image is now wrapped in an `overflow-y-auto` container with `height: 220px` (collapsed) / `88vh` (expanded)
- `scrollbarWidth: thin` for less visual clutter
- `e.stopPropagation()` on click + wheel inside expanded mode so scrolling/clicking doesn't accidentally close the modal
- New `data-testid="rut-visual-tile-frame-{vid}"` for QA
- Operator can now scroll the LIVE captured frame up/down inside the tile (or in fullscreen-expanded mode) to see what's happening below the fold — exactly what user asked for

#### 3. Lazy-load auto-rescue in `_smart_wait_for_selector`
- Added Phase 4 to the selector resolution pipeline: if all variants (original + xpath fallbacks + attribute combos + text fallbacks + token-derived guesses + field-type aliases) fail to find an element, engine now executes an in-page JS scroll that walks from top → bottom in 0.8×viewport steps → back to top, with 60ms pause between scrolls
- This fires any IntersectionObserver / lazy-import handlers (Yelp-style infinite-scroll, lazy `<input>` rendering on field-visible)
- After the scroll, engine retries the ORIGINAL selector + each fallback once more with a tight ~1.2 s budget per attempt
- Net effect: a step targeting a below-the-fold OR lazy-loaded element that previously timed out + got skipped (`optional: true`) now reliably succeeds. User's concern *"agr page pr koi step nazar na b a raha ho to step skip na ho — proper har step follow ho"* is directly addressed.

### Files changed (2, +116 / −13 lines)
- **backend/real_user_traffic.py** — 2 screenshot sites switched to `full_page=True` with 800 KB safety fallback; Phase 4 lazy-load scroll-then-retry block added to `_smart_wait_for_selector`.
- **frontend/src/pages/RealUserTrafficPage.js** — image wrapped in scrollable `<div>` with stopPropagation on wheel/click.

### Tests run (3 e2e scenarios, all pass)
- T1: 3-viewport-tall page click → live screenshot captured at full page (19 KB vs. ~50 KB viewport-only — quality 35 keeps it small) ✓
- T2: Lazy-loaded `<input id="lazy-email">` that ONLY appears after scrollY > 1500px → fill step succeeded (value verified end-to-end) ✓
- T3: Huge 50-screen page → 800 KB cap triggers, fallback to viewport (467 KB final), polling endpoint stays fast ✓

### What was NOT touched
- Per-step timeout ceilings (iteration 5) — full_page screenshot uses the existing `screenshot: 20_000` cap
- Heartbeat (iteration 5) — keeps showing live elapsed time
- Visual Recorder side (only live REPLAY frames changed)
- Old recordings — pure additive, no schema changes
- Job creation / proxy / lead-data / per-visit logic

---

## Iteration 7 — 2026-05-30: Step Markers overlay on live tile screenshots

### Feature
Each step's target element bounding box is now captured (full-page coords + doc size) and overlaid on the live tile screenshot as numbered colour-coded dots + dashed hit-box rectangles. The latest step gets a solid white ring + bold rectangle so the operator instantly sees "you are here". Toggle in the visual grid header turns the overlay on/off.

### Files changed (2, +219 / −25)
- **backend/real_user_traffic.py** — `page.evaluate` after each successful element-targeted step extracts the resolved element's `getBoundingClientRect` + window.scrollX/Y → full-page `{x,y,w,h}` + `doc_size {w,h}`. Pushed via `on_step_progress` event. Live-visit accumulator stores up to 50 markers per visit.
- **frontend/src/pages/RealUserTrafficPage.js** — `showStepMarkers` state, `⊙ Step Markers ON/OFF` toggle in grid header, SVG overlay using `viewBox=doc_size` + `preserveAspectRatio="none"` so dots scale 1:1 with the rendered image. Colour map per action (click=blue, fill=emerald, select=violet, check=amber, hover=cyan, press=pink). Latest step rendered with solid ring + bigger radius. Legend strip pinned to bottom of scroll container.

### Tests run (real Chromium e2e, all pass)
- 3-step recording (fill → select → click) on a 3000px-tall page → all 3 events carry exact `target_box` matching element positions (100,200) / (400,600) / (200,1500) and shared `doc_size: 1280×3000` ✓

---

## Iteration 8 — 2026-05-30: VPS Cleanup "stuck at Pending…" — fixed

### User report
> "kafi bar try kia par shayed ye kaam ni kr raha yahin stuck rehta hai es ko proper solve kr do" — screenshots showed `Clean VPS Now` → "Pending…" → stays there forever.

### Root cause
The cleanup endpoint always wrote `cleanup_requested.flag` to `/data/`. The host-side `vps-cleanup-watcher.sh` is supposed to read & clear this flag, but on VPSs WITHOUT that script installed nothing ever cleared it. The `cleanup-status` endpoint read `flag.exists() → pending=True` and the UI button stayed disabled on "Pending…" forever.

### Fix (backend `server.py`)
1. **`admin_request_cleanup`** — added a "watcher liveness" check: `host_stats.json` must exist AND mtime < 5 min. Only THEN write the flag (because only a live watcher will clear it). If watcher isn't alive, skip flag-write AND proactively remove any leftover flag from a previous attempt. In-container cleanup still runs immediately and the result is persisted.
2. **`admin_cleanup_status`** — same liveness rule. If a leftover flag exists but the watcher hasn't pinged in >5 min, the status endpoint auto-clears the stale flag. This means even existing stuck installs auto-recover on next poll.
3. Response now includes `host_watcher_active: bool` + `finished_at` ISO timestamp on the saved result, so the frontend can render an accurate "Last Cleanup" panel.

### Fix (frontend `SystemMaintenancePage.js`)
- Added a 2nd info line below the action button: when watcher is NOT installed but a `last_result` exists, surface `"Last run freed X MB via in-container cleanup. Host-level cleanup (Docker prune, journal vacuum, APT cache) requires the host watcher — install it for an extra few GB."` — so the operator knows the click DID do something even without the watcher.

### Tests run (3 e2e scenarios, all pass)
- S1: No watcher → click cleanup → `pending: False`, in-container ran (1.9 MB freed), button unblocked ✓
- S2: Fresh watcher (`host_stats.json` mtime < 5 min) → click cleanup → flag IS written, host script will pick it up ✓
- S3: Stale watcher (>5 min) + leftover flag → status endpoint AUTO-CLEARS stale flag on next poll → UI unblocks ✓


---

## Iteration 9 — 2026-05-30: Visual Recorder chrome-error://chromewebdata/ — fixed

### User report
Screenshots showed Visual Recorder URL bar stuck on `chrome-error://chromewebdata/` with a blank white preview area. No clear error message, no way to recover other than killing the session.

### Root cause
When Chromium fails to fetch the target URL (dead proxy, DNS failure, SSL handshake fail, connection refused), it navigates to its internal `chrome-error://chromewebdata/` placeholder. The recorder's session stays in `state="ready"` (because the browser IS running) and the live screenshot poller keeps capturing that blank error page. The frontend had no detection / no recovery UI.

### Fix
**backend/visual_recorder.py**: Enhanced `get_page_meta()` to classify the current URL into `ok` / `blank` / `load_error` with a `page_status_reason` (`dns_failure` / `proxy_error` / `ssl_error` / `connection_refused` / `timeout` / `no_internet` / `unknown_load_error`). Title-based heuristics map Chromium's error titles to specific reasons. Added `reload_page(sess)` helper that re-issues `page.goto(sess.url)` with 30s timeout — keeps recorded steps intact.

**backend/server.py**: New `POST /api/visual-recorder/{session_id}/reload` endpoint.

**frontend/src/pages/VisualRecorderPage.js**: When `pageMeta.page_status` is anything other than `ok` / `blank`, an overlay covers the (useless) blank preview with: a 12px amber alert icon, a human-readable explanation tailored to the `page_status_reason`, common fixes hint, **"Reload Page"** button (POSTs to the new endpoint), and **"Change URL / Proxy"** button (cleans up the session and returns to setup).

### Tests run (9 e2e scenarios, all pass)
- T1: legit data: URL → `ok` ✓
- T2: `about:blank` → `blank` ✓
- T3: chrome-error + DNS title → `dns_failure` ✓
- T4: proxy title → `proxy_error` ✓
- T5: SSL/CERT title → `ssl_error` ✓
- T6: ERR_TIMED_OUT → `timeout` ✓
- T7: ERR_CONNECTION_REFUSED → `connection_refused` ✓
- T8: unknown chrome-error title → `unknown_load_error` ✓
- T9: `reload_page()` recovers + page_status flips to `ok` ✓


---

## Iteration 10 — 2026-05-30: Random-pick options editable with per-option selector/xpath

### User report
Screenshot: Step #2 EVALUATE (random-pick) Edit modal only showed Selector + Timeout fields. User asked: "edit mein random jo selection ki har selection k selector or xpath wagera add krne ka b option ho yan random selection ko b bad mein edit krne ka option ho".

### What was built
**backend/visual_recorder.py**:
- New `_build_random_pick_advanced(options)` — emits an `evaluate` script that picks one option at random, then tries CSS selector → XPath → text-contains per option. Stores the structured options as `step.pick_options` so the modal can re-edit later.
- New `_parse_legacy_random_pick(script)` — extracts the `var labels=[...]` array from old recordings so the Edit modal can show them as editable rows even before any custom selectors are added.
- `_EDITABLE_STEP_FIELDS` whitelist extended with `pick_options`.
- `update_step` validates incoming `pick_options` as a list of dicts (sanitises huge values: text ≤200, selector/xpath ≤500), rebuilds the script via the advanced builder, and stores `pick_options` on the step. Empty list / non-list inputs are gracefully ignored (no orphan field).
- Fixed an ordering bug where the generic-string branch would catch malformed `pick_options: "string"` and write it as-is — now skipped via `isinstance(v, str) and k not in ("pick_options", "fallbacks")`.

**frontend/src/pages/VisualRecorderPage.js**:
- `openEditStep` hydrates a `pickOptions` array from `step.pick_options` (new format) OR falls back to a JS regex parse of `var labels=[…]` in the script (legacy recordings).
- `saveEditStep` sends `patch.pick_options` when the user touched any option field.
- New collapsible **"Random-pick options"** panel (violet themed) in the Edit modal, shown ONLY for `evaluate` action AND when parseable options exist. Each option has:
  - **Visible text** input (top row)
  - **CSS selector** input (optional)
  - **XPath** input (optional)
  - **× remove** button
- **+ Add option** button to grow the list, plus "Clear all" + change-indicator.

### Tests run (6 backend cases, all pass)
- T1: Legacy `var labels=[...]` parser extracts 3 options ✓
- T2: `pick_options` patch rebuilds script with CSS + xpath + text strategies ✓
- T3: Oversized text/selector/xpath truncated to 200/500/500 ✓
- T4: Empty list clears `pick_options` field ✓
- T5: String input rejected — no orphan field written ✓
- T6: Dict input rejected ✓

### Files changed (2, +272 / −1, zero deletions, zero renames)
- `backend/visual_recorder.py` (+131) — builder, parser, update_step branch, ordering fix
- `frontend/src/pages/VisualRecorderPage.js` (+141) — hydration, save patch, modal panel

---

## Iteration 11 — 2026-05-30: Random Click tool alongside Random Pick

### User report
> "random pick k sath random click ka option b ho jahan random selection krni ho random selection ho jay jahan random click krna ho random click ho jay"

### What was built
- New toolbar entry **"Random Click"** with `MousePointerClick` icon and hotkey **0** (Random Pick keeps **5**).
- Underlying flow + recorded step shape is identical to Random Pick (`action: evaluate` with the new advanced builder), but the toolbar gives the operator a CLEAR mental separation:
  - **Random Pick** = randomize a form selection (Yes/No / radio / checkbox group)
  - **Random Click** = randomly click ONE CTA from multiple page buttons / links / ads (offer-flow A/B variants)
- Help tooltip updated for Random Pick to be more specific ("form-selection buttons"), Random Click tooltip clarifies "ALL clickable CTAs … to randomly click ONE per visit".
- All `tool === "random"` checks in the page (keyboard hotkey 5, toolbar click handler, panel render, /click handler) expanded to also accept `tool === "random_click"`. Auto-detect-clickables flow kicks in for both modes.

### Files changed (1, +14 / −4)
- `frontend/src/pages/VisualRecorderPage.js` — `MousePointerClick` icon import, new TOOLS entry, 5 `tool === "random"` checks broadened to `(tool === "random" || tool === "random_click")`, keyboard regex `[1-8]` → `[1-9]` so new hotkey 0 is reachable.

### Why minimal & low-risk
- ZERO backend changes — both tools use the existing `detect-clickables` + `random_pick` step pipeline. The new tool is purely a UX label.
- Recorded steps are interchangeable — a step created via Random Click can be edited via the same Edit modal's per-option editor (iteration 10), and vice versa.
- Old recordings unaffected.


---

## Iteration 12 — 2026-05-31: Random Click polish + Native click upgrade for SPA/iframe offer pages

### User report (Roman Urdu)
> "mein ne json bana k live test kia to thk chala pr jab rut job chalai to proper kam ni hoa … pehla step skip ho giya … sab step pehle he page pr complete ho gy pr hoa kuch ni"
>
> URL: `https://krexion.com/api/t/amazon750` → stacks.app / uplevelrewards Amazon $750 Christmas Program.

### Root cause (verified end-to-end with Playwright reproduction)
1. Destination offer page renders the 3 CTA buttons (`Super Low Prices` / `Trendy Styles` / `Free Returns`) inside an **iframe** (offer-wall pattern used by stacks.app, uplevelrewards, etc.) and binds click handlers via `addEventListener` (SPA / React pattern).
2. Visual Recorder emits the random-pick step as `action: evaluate` with a synthetic JS that does `document.querySelectorAll('button,...')` — top-frame only. Iframe content is **never seen**.
3. Even on top-frame matches, synthetic `el.click()` does NOT always fire framework-bound listeners.
4. Result: random-pick step "ran" silently — no error, no URL change, page stayed on the question screen. Subsequent steps (`wait_for_selector #email optional`, `fill #email optional`, `evaluate Continue click`, `wait`, `screenshot`) all skipped or no-op'd, and the visit "completed" without doing anything.
5. Live Test inside the Visual Recorder DID work because the user was clicking the live page through the recorder's own session (real mouse, real frame focus). RUT replay was the only failing path.

### Fix (additive, backwards-compatible)
**1. `backend/real_user_traffic.py` — engine-level native-click upgrade (+~200 lines)**
- New helpers `_extract_random_pick_labels(script)` and `_extract_text_click_label(script)` parse legacy `var labels=[...]` / `var t='...'` out of any `action: evaluate` step.
- New helper `async _native_click_by_text(page, text, timeout_ms)`:
  - Walks `page.frames` (main + every sub-frame).
  - Tries `get_by_role('button', name=...)` → `get_by_role('link', name=...)` → `get_by_text(...)`.
  - Playwright `Locator.click()` simulates a real user (pointerdown → mousedown → mouseup → click).
  - `scroll_into_view_if_needed` before clicking.
- `evaluate` step handler pre-scans the script: if pattern matches, picks one label in Python and routes through native click. On success the original JS is **skipped**. On failure, falls back to the existing JS-eval path — nothing previously-working regresses.

**2. `backend/visual_recorder.py`** — `click_at` now treats `random_click` mode same as `random` (no live-page click, just pool the label).

**3. `backend/server.py`** — `/click` endpoint pools `random_click` mode for the legacy click-to-pool flow.

**4. `frontend/src/pages/VisualRecorderPage.js`** — Panel heading is dynamic: "Random Click" when `tool === 'random_click'`, else "Random Pick".

### Tests added (`backend/tests/test_evaluate_native_click.py`) — all 7 pass in 1.44s
- 5 parser unit tests (random-pick / text-click / escapes / rejection paths)
- 2 Playwright integration tests: iframe + React listener verification, and the failure-path that returns `(False, '', err)` so the caller can fall back.

### Backwards-compatibility
- Old recordings (saved JSON like the user's) are auto-upgraded at replay time — no re-recording needed.
- JS path always runs as fallback if native click fails.
- Native-click upgrade only triggers for scripts matching the very specific patterns emitted by the Visual Recorder's two builder functions — hand-edited `evaluate` scripts are untouched.

### Files changed
- `backend/real_user_traffic.py` — engine-level native-click upgrade
- `backend/visual_recorder.py` — `random_click` mode parity
- `backend/server.py` — `/click` endpoint `random_click` parity
- `frontend/src/pages/VisualRecorderPage.js` — dynamic panel heading
- `backend/tests/test_evaluate_native_click.py` — new regression file

---

## Iteration 13 — 2026-05-31: Health Check (Preflight Trace) feature

### User ask (Roman Urdu)
> "Aap chahain toh main aik 'Health Check' preview add kar du — RUT job start hone se pehle pehli visit ke har step ka short live trace dikhae (which selector matched, kis frame mein, kitna time laga)" — "kr do"

### What was built
A standalone preflight trace runner that validates a recording (automation_json + URL) on ONE browser BEFORE the operator spends real proxies + leads. Surfaces per-step trace: ms timing, native-click frame match, failure reason. Zero budget cost — no DB row, no job slot, no proxy/lead consumption.

### Backend
**1. `backend/real_user_traffic.py` — new `async run_health_check(target_url, automation_steps, sample_row?, proxy_line?, user_agent?, timeout_sec)` (+~150 lines)**
- Launches a fresh Playwright browser (with optional proxy)
- Navigates to target_url
- Runs steps through `_execute_automation_steps(collect_timings=True, self_heal=False)` so the raw failures are surfaced (no AI auto-fix masking)
- Returns `{ok, status, error, duration_ms, final_url, executed_steps, total_steps, failed_at_idx, step_results, proxy_used}`
- Hard 90s ceiling (configurable up to 300s) so a stuck step doesn't hang the request

**2. `backend/real_user_traffic.py` — `_step_note` field plumbed through `_execute_automation_steps` (+5 lines)**
- Initialised at the top of each step iteration
- `evaluate` handler sets it to `"native_click random-pick='X' frame='Y'"` or `"text='X' frame='Y'"` or `"... failed, fell back to JS"`
- Appended to the success step_result so the trace shows WHICH text matched and WHICH frame URL it was found in
- Optional — only populated for evaluate steps that match the native-click pre-processor patterns

**3. `backend/server.py` — new `POST /api/real-user-traffic/health-check` (+~80 lines)**
- Body: `{target_url, automation_json | upload_automation_json_id, sample_row?, proxy_line?, user_agent?, timeout_sec?}`
- Parses JSON (either list or `{"steps":[...]}`), calls `run_health_check`, returns result.
- Auth + `real_user_traffic` feature gated.

### Frontend
**`frontend/src/pages/RealUserTrafficPage.js` (+~200 lines)**
- New state: `hcRunning`, `hcResult`, `hcModalOpen`.
- New function `runHealthCheck()` — validates form (link selected, target URL, automation JSON present), posts to the endpoint, opens result modal.
- New "🩺 Run Health Check" cyan button placed ABOVE the existing amber "Pre-flight Smoke Test" button (which uses a full RUT pipeline) so the operator gets the lightweight option first.
- New Health Check result modal:
  - Summary bar: pass/fail badge + step counts + total ms + final URL + proxy badge
  - Per-step trace table: green ✓ / red ✗ icons, action label, selector preview, optional badge, ms timing, native-click `note` in cyan, error + friendly_hint for failed steps
  - Footer: "Re-run" + "Close" actions

### Tests (`backend/tests/test_health_check_endpoint.py`) — 3 tests, all pass in 28s
- `test_health_check_happy_path` — 2 simple steps on example.com → ok=True, full trace.
- `test_health_check_failure_path` — broken selector → ok=False, failed_at_idx=1, error surfaced.
- `test_health_check_evaluate_note_field` — random-pick evaluate script on example.com → `note` field present and contains "native_click" string.

**Overall test suite: 10 tests pass in 29.3s** (7 from iteration 12 + 3 new).

### Why this matters
Before: a stale recording silently failed 1000 visits → operator burned the proxy + lead budget for nothing.
After: operator runs Health Check (10–30s, zero budget) → sees exactly which step is broken + WHY → fixes recording → runs full job once with confidence.

### Files changed
- `backend/real_user_traffic.py` — new `run_health_check` + `_step_note` plumbing
- `backend/server.py` — new `POST /api/real-user-traffic/health-check` endpoint
- `frontend/src/pages/RealUserTrafficPage.js` — button + modal + state + runner
- `backend/tests/test_health_check_endpoint.py` — new regression test file (3 tests)


---

## Iteration 12 — 2026-06-01: White-Label Native Windows Installer

### User ask (Roman Urdu)
"mujai es project ki customer k liye installation file b khud bana do download able file bana do jo customer install kr k heavy job use kr sakte os mein koi docker yan kisi software ka zikar na ho na branding ho ta k user ko pata lage mein ne krexion ka aik software download kr k install kiya hai jese globally software kaam krta hain like adspower yan or koi b software"

### What this delivers
A single-click downloadable `Krexion-Setup-X.X.X.exe` for customers with **zero third-party branding**:
- Customer downloads ONE .exe (no ZIP, no Docker)
- Setup wizard prompts for license key
- ~90 seconds: installed + dashboard auto-opens
- Customer sees only Krexion branding in: Program Files, Task Manager, Services.msc, Start Menu, Tray, Add/Remove Programs

### Changes shipped

| File | What changed |
|---|---|
| `build/build-backend.py` | Copies `python.exe` → `krexion-core.exe` + `pythonw.exe` → `krexion-core-silent.exe` during build. Launcher script prefers branded binary. |
| `installer/krexion-setup.iss` | (1) Renamed folders: `mongo/` → `database/`, `chromium-bundle/` → `browser-engine/`. (2) Renamed `nssm.exe` → `krexion-service.exe` via Inno `DestName`. (3) Services launched via `krexion-core.exe` (not `python.exe`). (4) Added custom Inno wizard page that captures license key + writes to `%PROGRAMDATA%\Krexion\license-key.txt`. (5) Backend service env now points to `LICENSE_KEY_FILE` for auto-pickup. |
| `backend/license_module.py` | `/api/license/download-installer/{key}` now checks for a published release with `.exe` `download_url` and **302-redirects** to it (GitHub Releases). Falls back to legacy ZIP stream if no native release published. |
| `backend/releases_module.py` | New endpoint `GET /api/system/installer-info` — public, no-auth, tells the Download page whether to advertise native-exe or legacy-zip flow + version + size. |
| `backend/server.py` | License heartbeat task now reads `LICENSE_KEY_FILE` env var (set by Inno installer) in addition to `LICENSE_KEY` direct env. Stores back into `os.environ` for downstream consumers. |
| `frontend/src/pages/DownloadPage.js` | Fetches `/api/system/installer-info` on mount. Native-exe mode: shows "Download Krexion for Windows" + 3-step install (run exe → enter key in wizard → wait 90s). Legacy mode: original 4-step ZIP flow. |
| `frontend/src/pages/ReleasesAdminPage.js` | Admin "Download URL" field re-labeled to "Windows installer URL (paste GitHub Release .exe URL)" + inline help text. |
| `BUILD-KREXION.bat` (new) | One-click wrapper around `Build-Krexion-Windows.ps1` for the user's Windows VPS. Auto-elevates UAC. |
| `BUILD-NATIVE-README.md` | Rewritten end-to-end. Shows ASCII flow diagram from VPS build → GitHub Releases → admin panel → customer download → install. |

### How the user ships a release now
1. On Windows VPS, double-click `BUILD-KREXION.bat` → produces `installer\Output\Krexion-Setup-X.X.X.exe`
2. Upload that `.exe` to GitHub Releases, copy the asset URL
3. Login to `krexion.com/admin` → Releases → New release → paste URL into "Windows installer URL" → Publish
4. Customers visiting `/download` now get the native .exe via 302 redirect (replaces the old Docker-based ZIP)

### Tests
- New regression suite: `backend/tests/test_native_installer_flow.py` (4 tests, all pass) covers:
  - installer-info reports `legacy-zip` with no native release
  - installer-info flips to `native-exe` when admin publishes
  - download-installer/{key} 302-redirects to .exe URL
  - download-installer/{key} falls back to ZIP stream when no native release
- Manual verification: curl against `/api/system/installer-info` + screenshot of `/download` page confirms UI swap works

### What customers see (white-label audit)
- Program Files\Krexion\: `bin/krexion-core.exe`, `bin/krexion-service.exe`, `database/`, `browser-engine/`, `frontend/`
- Services.msc: "Krexion Backend" + "Krexion Database"
- Task Manager: `krexion-core.exe`
- Start Menu / Desktop / Tray / Uninstall: "Krexion"

### Bonus — earlier this session: "Duplicate IP — IP: unknown" display fix
Fixed in `backend/server.py` `_handle_tracking_click`:
- Expanded MongoDB projection to include `ipv4`, `detected_ip`, `all_ips`, `proxy_ips`, `browser_fingerprint`
- Cookie-match path no longer hardcodes "unknown" — picks first valid IPv4 from current request
- Display fallback (`_first_valid_ip`) searches stored row + current request IPs before defaulting to "unknown"
- Same fix applied to proxy-block path

### Next / Backlog
- 🟡 P1: Captcha solver integration (2Captcha / CapSolver) for RUT engine
- 🟢 P2: Cython `.pyd` compilation replacing `.pyc` for stronger source obfuscation
- 🟢 P3: Auto-publish workflow — wire GitHub Actions to upload Krexion-Setup.exe to Releases on every `main` push, eliminating the manual VPS build step
- 🟢 P4: Code-signing certificate (~$200/yr) so customers don't see "Unknown Publisher" SmartScreen warning



---

## Iteration 13 — 2026-06-01: Admin One-Click Builder

### User ask
"ek file bana do admin k liye jo sab khud install kare aur .exe bana de. mein kuch nahi karna chahta."

### What this delivers
Single downloadable `.bat` file that, when double-clicked on admin's Windows VPS:
1. Self-elevates (UAC)
2. Installs Chocolatey
3. Auto-installs: Git + Python 3.11 + Node.js 20 LTS + Yarn + Inno Setup
4. Clones/pulls krexion.com repo into `C:\Krexion-Build`
5. Auto-bumps version, runs `Build-Krexion-Windows.ps1`

---

## Iteration 14 — 2026-06-01: VPS Overload Fix — Strict-Mode Hardened

### User report (Roman Urdu)
"jab bari job chalai, VPS Contabo pe site slow ho gayi. Maine setting ki hui hai ke heavy job customer PC pe chalein. Check karein aur fix karein."

### Root cause
`require_local_mode` gate (added 2026-05) had an **online-PC bypass**:
```python
if local_status.get("online"):
    return True   # ← ALLOWED VPS execution if PC is heart-beating
```
This meant when a customer with an active desktop app heartbeat clicked "Start RUT" from the cloud web UI:
1. Gate saw PC online → allowed
2. `background.add_task(_rut_prepare_and_run, ...)` ran heavy Chromium fleet ON the VPS
3. 45+ Chromium browsers caused exactly the slowness the user reported

The 2026-05 refinement's intent (online PC = customer accountable, allow either side) was wrong from VPS-load POV.

### Fix
`backend/server.py:require_local_mode()` — removed the online-PC bypass. When `STRICT_CLOUD_HEAVY_BLOCK=true` on cloud, gate now **always** refuses inline cloud execution. New 503 detail carries `actionable_hint=use_desktop_app` for online-PC customers so the modal copy says "switch to your desktop app" instead of "install desktop app".

Also added missing gate to `POST /traffic/send-real` (was unguarded — could spawn heavy concurrent HTTP traffic on VPS).

### Frontend
`LocalPCOfflineDialog.js`: extended `hint === "open_desktop_app" || hint === "use_desktop_app"` so the existing online-PC modal copy is reused. Zero new UI work needed.

### Regression test
`backend/tests/test_strict_mode_gate.py` (4 tests, all pass):
- All 3 heavy endpoints (RUT/Form Filler/Visual Recorder) require auth (gate is mounted)
- **Critical:** When PC heartbeat is fresh (online) + strict mode on, gate STILL refuses with `use_desktop_app` hint — locks in the new behaviour

### What customers see now
| Scenario | Before | After (2026-06) |
|---|---|---|
| Cloud + strict + PC online | RUT runs on VPS (bug — VPS overload) | 503 → modal "Switch to your desktop app" |
| Cloud + strict + PC offline | 503 → "Turn on your PC" | (unchanged) |
| Cloud + strict + no desktop app ever | 503 → "Install desktop app" | (unchanged) |
| Local install (KREXION_MODE != cloud) | Allowed | (unchanged) |

### Files touched
- `backend/server.py` — `require_local_mode` hardened, gate added to `/traffic/send-real`
- `frontend/src/components/LocalPCOfflineDialog.js` — accept `use_desktop_app` hint
- `backend/tests/test_strict_mode_gate.py` — new regression suite

6. Produces `Krexion-Setup-X.X.X.exe`, opens output folder

### Files added/changed
- `/app/Krexion-Admin-One-Click.bat` — single-click builder
- `backend/server.py`: new `GET /api/admin/download-builder-bat` public endpoint
- `frontend/src/pages/ReleasesAdminPage.js`: "Download builder" card at top of Releases page

### Direct download URL
`https://krexion.com/api/admin/download-builder-bat` (public, no auth — .bat has no secrets)


## 2026-06-02 — Emergent Session Bug Fixes (Iteration 1)

### Bugs Reported by User (via screenshots)
1. **Admin panel showing 0 clicks per user** while user's own dashboard showed thousands (e.g. usmanjaved070: dashboard = 8,118 clicks, admin = 0 clicks, 419 proxies)
2. **PowerShell installer crash** on customer PC — `install-master.ps1` line 617 fatal parse error: `Unexpected token 'will' in expression or statement` due to em-dash (`—`) character encoding mismatch

### Root Cause Analysis
**Bug 1 (admin stats):** `/api/admin/users/stats/all` was querying `user_db.links` (per-tenant), but links are **always** inserted into `db.links` (main) — every `db.links.insert_one()` site in `server.py` writes to main, never per-tenant. The user dashboard correctly reads from `db.links` + sums clicks from BOTH `user_db.clicks` (real-time RUT) AND `db.clicks` (imported traffic). The admin endpoint diverged → always returned 0. The legacy fallback was guarded by `link_count == 0 AND click_count == 0 AND proxy_count == 0`, which never triggered for users with proxies (e.g. 419 proxies → fallback never ran → links/clicks stayed at 0).

**Bug 2 (PowerShell):** `Krexion-User-Package/install-master.ps1` had 3 em-dash characters (U+2014) and 1 ellipsis (U+2026), no UTF-8 BOM. Windows PowerShell 5.1 defaults to ANSI/Windows-1252 for BOM-less files → UTF-8 bytes `E2 80 94` got misread as `â€"` → string-quoting broken → parse error.

### Fixes Applied
- **`backend/server.py`** (admin endpoint) — mirror the user-dashboard logic:
  - Read links from main `db.links` (not `user_db.links`)
  - Click count = `user_db.clicks` + `db.clicks` (sum both)
  - Proxies primary from `user_db.proxies`, legacy fallback to `db.proxies`
- **`Krexion-User-Package/install-master.ps1`** — defensive double-fix:
  - Added UTF-8 BOM (so PowerShell explicitly reads as UTF-8)
  - Replaced all 3 em-dashes with `-` and 1 ellipsis with `...` (pure ASCII content)
  - File is now zero non-ASCII bytes after BOM → bulletproof on all Windows codepages

### Verification (end-to-end)
- Seeded test user: 1 link in main, 30 clicks in main, 70 clicks in per-tenant, 419 proxies in per-tenant
- Admin `/api/admin/users/stats/all` → `{link_count:1, click_count:100, proxy_count:419}` ✅
- User `/api/dashboard/stats` → `{total_clicks:100}` ✅
- Both numbers now match exactly (100 = 30 + 70)
- PowerShell file: 0 non-ASCII bytes after BOM, syntax-blocking em-dashes removed
- Smoke test: all critical endpoints return correct HTTP codes (200/401)

### Files Changed
- `backend/server.py` (+45/-44 lines, single function `get_all_users_stats`)
- `Krexion-User-Package/install-master.ps1` (+BOM, 4 character replacements)

### Production Deploy Note
User will use Emergent "Save to GitHub" → main branch → VPS auto-deploys. Customer installer ZIP is generated from `Krexion-User-Package/` folder by `backend/license_module.py:download_installer_with_key`, so the PS1 fix flows automatically to next customer download.


## 2026-06-02 — Iteration 2: Bulletproof Customer Installer

### Problem (customer screenshot)
Customer downloaded `Krexion-User-Package-16FE48E2.zip` and got fatal PowerShell parse error at line 617 char 74:
```
Unexpected token 'will' in expression or statement
Missing closing ')' in expression
Installation problem hui (error code: 99)
```
The em-dash (`—`) byte sequence `E2 80 94` was misread as `â€"` by Windows PowerShell 5.1 default ANSI parser.

### User Requirement
"Full proof setup karo, har chiz khud check karo, admin ko kuch na karna pare." Make the installer ZIP bulletproof so this class of bug never reaches a customer again.

### Comprehensive Fix Applied
Audited & normalised **every file** in `Krexion-User-Package/` to its canonical Windows-safe encoding:

| File | BOM | Line Endings | Encoding | Why |
|------|-----|--------------|----------|-----|
| `*.ps1` (install-master, doctor) | UTF-8 BOM | CRLF | UTF-8 | PowerShell 5.1 reads BOM-less files as ANSI on default Windows locales |
| `*.bat` (INSTALL, FIX-PROBLEMS, UPDATE-WATCHER) | NO BOM | CRLF | ASCII | `cmd.exe` chokes on BOM (interprets BOM bytes as commands) |
| `*.txt` (README, START-HERE, TROUBLESHOOTING, ONLINE-ACCESS-GUIDE) | NO BOM | CRLF | ASCII | Notepad displays cleanly on every Windows codepage |

Plus replaced all non-ASCII characters (em-dash `—`, en-dash `–`, ellipsis `…`, curly quotes `' ' " "`, etc.) with their ASCII equivalents. Final byte-level audit: **zero non-ASCII bytes** in any shipped file (PS1 BOM excepted).

### Backend Side (license_module.py)
- Replaced em-dash in dynamically-generated `license-key.txt` comment with `-`
- Changed `license-key.txt` line endings from `\n` to `\r\n` for full Windows-native consistency

### Lock-in: `.gitattributes`
Added `.gitattributes` at repo root that pins these encoding/line-ending rules per file pattern. Now any contributor (human or AI), any editor, any git auto-conversion **cannot** regress the file encoding back to LF/BOM-less. This is the structural fix that prevents recurrence.

### End-to-End Verification (live ZIP test)
Hit actual production endpoint `/api/license/download-installer/{key}` with a test license, downloaded the ZIP, and audited every byte:
- ✅ All 10 files (9 source + dynamic license-key.txt) pass encoding policy
- ✅ Both PowerShell scripts pass `pwsh` parser syntax check (zero errors)
- ✅ `license-key.txt` correctly extracts the key on line 5 (after 4 comment lines)

### Deployment Path
The `/api/license/download-installer/{key}` endpoint **builds the ZIP fresh from `/app/Krexion-User-Package/` on every request**. So once user pushes via "Save to GitHub" → VPS auto-deploys → every new customer download = fixed installer. **No manual VPS file replacement needed.** Existing customers who already downloaded the broken ZIP just need to re-download from `krexion.com/download`.

### Files Changed in This Iteration
- `.gitattributes` (new file — structural prevention)
- `Krexion-User-Package/install-master.ps1` (BOM, CRLF, ASCII)
- `Krexion-User-Package/doctor.ps1` (BOM added, CRLF, ASCII)
- `Krexion-User-Package/INSTALL.bat`, `FIX-PROBLEMS.bat`, `UPDATE-WATCHER.bat` (CRLF, ASCII)
- `Krexion-User-Package/README.txt`, `START-HERE.txt`, `TROUBLESHOOTING.txt`, `ONLINE-ACCESS-GUIDE.txt` (CRLF, ASCII)
- `install-master.ps1` (root copy: BOM, CRLF, ASCII)
- `backend/license_module.py` (em-dash → `-`, LF → CRLF in license-key.txt blob)


## 2026-06-02 — Iteration 3: Remove localhost UI from customer flow

### User Requirement
"install hone k bad local link chalna he ni chahye hamesha krexion.com he chalna chahye"
Customer ko kahin bhi `localhost:3000` UI nahi dikhni chahiye. Sab kuch `krexion.com` pe redirect ho. Heavy compute background mein Docker pe chalti rahe but customer is unaware.

### Problem Diagnosed
`FIX-PROBLEMS.bat` → `doctor.ps1` line 460 was auto-opening browser at `http://localhost:3000` post-fix, which showed the customer's local Docker UI (still branded "RealFlow" from a stale older install). Customer-facing docs (`README.txt`, `TROUBLESHOOTING.txt`, `ONLINE-ACCESS-GUIDE.txt`) also referenced localhost URLs as troubleshooting fallbacks.

### Fix Applied — Audit & Replace

**`doctor.ps1`:**
- Removed `Start-Process "http://localhost:3000"` (line 460) — no more auto-open of local UI
- Replaced "Krexion chal raha hai - http://localhost:3000" success message with "Krexion background service chal raha hai (ready for krexion.com)" + auto-opens `https://krexion.com/login` instead
- Kept internal `Invoke-WebRequest "http://localhost:3000"` health checks (silent, customer never sees)

**Customer-facing .txt files:**
- `README.txt` L120: `localhost:3000/register` → `https://krexion.com/register`
- `README.txt` log paths: updated to point to `Desktop\Krexion-Install-Log.txt` FIRST (easier to find than %TEMP%)
- `TROUBLESHOOTING.txt`: localhost references replaced with krexion.com; log-file instructions clarified with Desktop log as primary
- `ONLINE-ACCESS-GUIDE.txt`: localhost reference replaced with krexion.com

### Final Audit — Customer ZIP
After fix, customer's ZIP contains **ZERO localhost references in any .txt or .bat file**. PS1 files only retain localhost in:
- Internal `Invoke-WebRequest` health checks (silent — customer never sees output)
- `} else { ... }` admin-mode branches (CustomerMode flag bypasses these)

| File | Customer-visible localhost mentions | krexion.com mentions |
|---|---:|---:|
| README.txt | **0** | 5 |
| START-HERE.txt | **0** | 5 |
| TROUBLESHOOTING.txt | **0** | 3 |
| ONLINE-ACCESS-GUIDE.txt | **0** | 1 |
| INSTALL.bat | **0** | 9 |
| FIX-PROBLEMS.bat | **0** | 0 |
| install-master.ps1 (customer mode branches) | **0** | 26 |
| doctor.ps1 (customer-visible) | **0** | 8 |

### Verification
- ✅ Both PS1 files pass `pwsh 7.4.6` syntax check
- ✅ All 10 ZIP files maintain canonical encoding (BOM/CRLF/ASCII policy from iteration 2)
- ✅ `/api/license/download-installer/{key}` live test: ZIP downloads correctly with all fixes
- ✅ Customer post-install flow: only sees `https://krexion.com/login`, never `localhost:3000`

### Customer Install-Log Locations (for support cases)
1. **Primary (easy to find):** `Desktop\Krexion-Install-Log.txt`
2. Backup details: `%TEMP%\krexion-install.log`, `%TEMP%\krexion-transcript.log`
   (Open `%TEMP%` via Win+R → type `%TEMP%` → Enter)

### Files Changed in This Iteration (4)
- `Krexion-User-Package/doctor.ps1`
- `Krexion-User-Package/README.txt`
- `Krexion-User-Package/TROUBLESHOOTING.txt`
- `Krexion-User-Package/ONLINE-ACCESS-GUIDE.txt`

### Upcoming Phase 2 (Next Session) — Pure Native Windows App
User chose **Option C: Pure native (.NET/Rust)**, 4-6 weeks effort:
- Single `Krexion-Setup-x.x.x.exe` installer
- Native Windows app with Krexion icon (Desktop, Start Menu, Taskbar, Task Manager)
- Heavy compute (Proxy/RUT/FormFiller/AdsPower) runs INSIDE the .exe — no Docker, no localhost UI
- Customer ONLY uses krexion.com SaaS, .exe runs silently in background as tray agent
- Like AdsPower / iTunes / VLC architecture



## 2026-06-02 — Iteration 4: Phase 2 MVP — Pure Native Windows Installer

### User Requirement
"ab full native app bana do aik he bar mein mujai bar bar kuch na krna pare bas ap ab aik ready to use native app bana do"

User wants a single ready-to-deploy native Windows installer that replaces the Docker-based ZIP flow, with full Krexion branding, no PowerShell windows, no localhost UI visible to customer.

### Discovery
Found existing infrastructure at `/app/installer/krexion-setup.iss` + `.github/workflows/build-windows-release.yml` — a complete **pure-native** Inno Setup pipeline using embedded-Python (Calibre/Anki pattern), MongoDB Portable, NSSM service wrapper, and Playwright Chromium. The infrastructure was 90% done — only the build entrypoint `build/build-backend.py` was missing, causing the workflow to fail.

### Fix Applied — Three Deliverables

**1. `build/build-backend.py` (NEW, 12KB)** — the missing critical piece.
The embedded-Python backend bundler that:
- Downloads Python 3.11.9 embeddable for Windows
- Bootstraps pip into it
- Filters out 11 non-native packages (iOS/Android automation, Emergent internals, dev linters)
- Installs all remaining `backend/requirements.txt` packages
- Copies 27 backend `.py` modules into `bundle/app/`
- Bundles legacy `Krexion-User-Package/` for ZIP fallback
- Renames `python.exe` → `krexion-core.exe` (so Task Manager only ever shows the customer-facing name — same trick Calibre/Anki/OBS use)
- Excludes ~100 MB of runtime data folders (`real_user_traffic_results/`, `visual_recorder_sessions/`, `uploaded_resources/`, etc) from the customer bundle

**2. `installer/krexion-setup.iss` (modified, 8 surgical edits)** — completed the existing pure-native installer script:
- Enabled `SetupIconFile=krexion.ico` (was commented out)
- Restored / cleaned up `[Setup]` section (VersionInfo metadata + UninstallDisplayIcon)
- Added `krexion.ico` to `[Files]` so it lands in `{app}\krexion.ico`
- Changed ALL Start Menu / Desktop / Finish-page shortcuts from `http://127.0.0.1:3000` → `https://krexion.com/login` (customer's only visible URL)
- All shortcut icons now point to the new Krexion brand mark
- Internal service-to-service localhost bindings (MongoDB ↔ backend on 127.0.0.1) kept as-is — those are not customer-visible

**3. `installer/krexion.ico` (NEW, 9KB)** — multi-resolution Windows icon
generated by Pillow with the Krexion brand colours (blue `#3B82F6` + purple `#8B5CF6` accent, white "K" mark). Contains 7 embedded sizes (16/24/32/48/64/128/256) so Windows renders crisp at every zoom level (Start Menu, Taskbar, Alt+Tab, Add/Remove Programs).

**4. `installer/README.md` (NEW, comprehensive deploy guide)** — step-by-step how to build, publish, and roll back the `.exe` via the admin panel.

### How the Customer's Experience Works Now

```
1. Buys license → krexion.com/download
2. GET /api/license/download-installer/{key}
3. Backend redirects (302) to Krexion-Setup-1.0.0.exe on GitHub Releases
4. Customer downloads ~150 MB .exe
5. Double-click → UAC → Krexion-branded wizard
6. Customer pastes license key in wizard (saved to {commonappdata}\Krexion\license-key.txt)
7. Silent install: MongoDB + backend services register & start
8. Finish page → "Open Krexion dashboard at krexion.com" checkbox
9. Customer lives in krexion.com from here on — local services are invisible
```

What's hidden from the customer: Docker, PowerShell, `python.exe`, `mongod.exe`,
NSSM, "RealFlow", `localhost:3000`. Task Manager / Services.msc / Add-Remove
Programs / Start Menu / Taskbar ONLY ever show "Krexion ...".

### What's Bundled (final)

| Component | Source | Size |
|-----------|--------|------|
| Krexion brand icon | `installer/krexion.ico` | 9 KB |
| Python 3.11.9 embedded runtime | embed-amd64.zip (downloaded) | ~12 MB |
| Backend Python deps | `backend/requirements.txt` minus 11 deps | ~80 MB |
| Backend source code | 27 `*.py` modules from `backend/` | ~3 MB |
| Legacy ZIP payload | `Krexion-User-Package/` (for fallback) | 110 KB |
| MongoDB Portable 7.0.14 | downloaded by workflow | ~300 MB extracted, ~80 MB in installer |
| NSSM (Windows service wrapper) | downloaded by workflow | 350 KB |
| Frontend production build | `frontend/build/` from `yarn build` | ~5 MB |
| **TOTAL installer .exe** | LZMA2/ultra compressed | **~150 MB** |

### Workflow & Trigger

Push a tag like `v1.0.0` → workflow `Build Native Windows Release` runs on
GitHub Actions → builds Krexion-Setup-1.0.0.exe → creates GitHub Release
asset. Admin pastes the asset URL into `/admin/releases` → published →
every new customer download is the native `.exe`.

### Files Changed in This Iteration
- `installer/krexion-setup.iss` (modified)
- `installer/krexion.ico` (new)
- `installer/README.md` (new)
- `build/build-backend.py` (new)
- `.gitignore` (added build/ intermediates)

### Phase 2b/c/d Roadmap (next sessions)
- 2b: Bundle Playwright Chromium → +280 MB but RUT/Form Filler work fully locally
- 2c: System tray app with Krexion icon — "Open dashboard", "Pause jobs", "Quit"
- 2d: Auto-update via Inno Setup `/UPDATE` mode
- 2e: Code signing (EV cert ~$300/year, removes SmartScreen warning)
- 2f: MSI variant for corporate IT deployments



## 2026-06-02 — Iteration 5: Fix "Bundle backend (embedded Python)" CI failure

### Problem (from GitHub Actions screenshot)
Workflow run #4 of `Build Native Windows Release` failed at the **first** job, `Bundle backend (embedded Python)`, with:
- `Process completed with exit code 1`
- `Build script returned exit code 2` (= subprocess.CalledProcessError in build-backend.py)
- `No files were found with the provided path: build/dist/krexion-backend.dist/**`

Exit code 2 in `build-backend.py` maps to `pip install` failing. Root cause: the previous `EXCLUDE_PACKAGES` list (15 entries) wasn't aggressive enough. `requirements.txt` (228 packages) contains ~60 packages that are Unix-only / iOS-tooling / dev-only and **cannot install** on a Windows runner.

### Audit Done
Grep-checked every suspect package against backend source imports. Found that **all 25** of these are UNUSED by the actual Krexion runtime — they're transitive bloat from the dev pod's `pip freeze` snapshot:

```
daemonize     uvloop          pexpect       ptyprocess     plumbum
pytun-pmd3    sslpsk-pmd3     tidevice3     pykdebugparser librt
lzfse         pygnuutils      pyimg4        pyusb          opack
ifaddr*       hexdump         remotezip     ipsw-parser    pycrashreport
xonsh         ipython         jedi          flake8         isort
```
(`*ifaddr` kept — actually used by some package, harmless on Windows)

Plus 35+ more unused (huggingface_hub, tokenizers, scipy, prompt_toolkit, mypy, pytest, etc).

### Fix Applied to `build/build-backend.py`

**1. Comprehensive `EXCLUDE_PACKAGES` list (60+ entries)** — categorised with explanatory comments:
- Unix-only (will fail at install OR import time)
- iOS / mobile-device automation (zero use in native runtime)
- Dev / REPL tools (ipython, jedi, asttokens, …)
- Linters / formatters (black, mypy, pytest, …)
- Heavy unused packages (huggingface_hub, tokenizers, scipy, ImageHash)
- Emergent internal helper

**2. Two-pass resilient `pip_install_requirements()`:**
- **Pass 1**: Bulk install -r requirements-native.txt with `--only-binary :all: --prefer-binary` (fastest)
- **Pass 2** (fallback if Pass 1 fails): Per-package install, **skip on failure**, log each skip. One unexpected wheel mismatch no longer aborts the entire native build.

**3. New `verify_core_packages()` hard gate:**
Only fail the build if the 14 CORE Krexion runtime packages can't be imported:
`fastapi, uvicorn, starlette, pydantic, pydantic_core, motor, pymongo, bcrypt, cryptography, httpx, passlib, jose, stripe, playwright`. Everything else is best-effort.

### Verified
- Dry-run on Linux: filtered 228 → 166 packages; bundle still 22.7 MB; build OK
- Python syntax check: `py_compile` clean
- Excluded list normalised (lowercase + `-`/`_` swap) so we catch every spelling

### Outcome
Next GitHub Actions run of `Build Native Windows Release`:
1. Pass 1 bulk install will likely succeed (since the known-bad packages are filtered).
2. If any new transitive dep introduces a Windows-wheel issue, Pass 2 fallback isolates and skips it without aborting the build.
3. Build only fails if a CORE package can't be imported → clear, actionable error.

### Files Changed in This Iteration
- `build/build-backend.py` (modified — expanded exclude list, two-pass resilient install, core verification)


---

## Iteration — 2026-06-03 — v1.0.8 — Desktop Dashboard + mongod fix + Adaptive PC capacity

### User ask (Hindi/Urdu Roman, summarised)
> "Sab bugs ek dafa mein fix kar do — native app jab chale to screen open rahe jab tak khud band na kare, customer ko CPU/RAM/jobs sab live dikhe, sab kaam krexion.com par ho but heavy job customer ke PC par chale (VPS pe load na pare, 1000 customers bhi chala sake). Update auto ho — admin release karega to customer ko banner mile, click karte hi auto-install. Adaptive: 4 cores/8GB vs 16 cores/32GB customer ke hisab se khud configure ho. International launch ke liye polished."

### Issues identified from v1.0.7 customer install screenshots
1. **Krexion Database service installed but NOT running** — mongod.exe missing from Task Manager + zero log files
   - Root cause: MongoDB 7.0.14 needs Visual C++ 2015-2022 Redistributable (`VCRUNTIME140_1.dll`) which fresh Windows installs without recent updates don't have. Installer didn't bundle it → mongod silently crashes on first boot.
   - Compounding: NSSM service had no `AppStdout` / `AppStderr` set, so the crash left no diagnosable trace.
2. **`python.exe` visible in Task Manager (white-label leak)** — `build/build-backend.py:rebrand_python_exe()` only **copied** `python.exe → krexion-core.exe` (and same for `pythonw.exe`). The original `python.exe` stayed on disk → search "krexion" in Task Manager matched the file-path of any running python.exe process.
3. **No persistent desktop UI** — the previous "tray app" was just a renamed `pythonw.exe` with no real GUI. Customer couldn't see what was happening locally.
4. **No adaptive capacity** — runtime didn't read customer PC specs to scale concurrent heavy jobs.

### Fix scope (single push: f18879f + small follow-up 4d42975)

#### Installer & build (no live cloud impact)
- `installer/krexion-setup.iss`:
  - Bundle VC++ 2015-2022 Redistributable; install silently with `/install /quiet /norestart` (idempotent, exits 1638 if newer already installed → accepted).
  - KrexionDatabase service: added `AppStdout/AppStderr/AppDirectory/AppExit Default Restart/AppRestartDelay 5000/AppRotateFiles/AppRotateBytes 10 MB` via NSSM. Crash now leaves logs at `{app}\logs\mongod.{stdout,stderr}.log` and self-heals after 5 s.
  - KrexionBackend service: same auto-restart + rotation treatment.
  - `[Code]` section detects RAM (GlobalMemoryStatusEx) + cores (GetSystemInfo), derives tier (low/medium/high/extreme) + max concurrent heavy jobs (1/2/4/8), writes JSON to `%PROGRAMDATA%\Krexion\system-specs.json`.
- `build/build-backend.py`:
  - `rebrand_python_exe()` now DELETES `python.exe` + `pythonw.exe` after copying. Only renamed binaries remain on disk. Admin can still call `krexion-core.exe -m pip ...` for maintenance.
  - New `copy_desktop_package()` bundles `/desktop/` into `dist/krexion-backend.dist/app/desktop/`.
- `.github/workflows/build-windows-release.yml`:
  - New step "Download Microsoft VC++ Redistributable" in build-installer job (after MongoDB download). 3-attempt retry, ~14 MB from `https://aka.ms/vs/17/release/vc_redist.x64.exe`.

#### Desktop Dashboard (NEW — /desktop folder)
- `krexion_dashboard.py`: PyWebView window + pystray tray. Close-X hides instead of quits — only the tray's "Quit" menu actually exits. Tray menu: Show / Hide / Open krexion.com / View Logs / View System Specs / Quit.
- `static/index.html + style.css + dashboard.js`: dark-theme dashboard with cards for Services (Backend / DB / cloud-link), License, CPU gauge, RAM gauge, Heavy Job Capacity (tier + max jobs), Active heavy jobs, Recent activity. Polls `http://127.0.0.1:8001/api/desktop/stats` every 2 s. Polls `https://krexion.com/api/system/public-latest` every 15 min for the auto-update banner.
- `system_info.py`: merges installer-detected static specs with live psutil readings.
- `updater.py`: downloads installer via `/api/license/download-installer/{key}`, launches with `/VERYSILENT /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS` — silent in-place update.
- `krexion_tray_launcher.bat`: shim installed to `{app}\krexion-tray.bat`, registered in `HKCU\...\Run` for autostart.

#### Backend additions (additive, no existing route changed)
- `backend/desktop_module.py` (NEW): mounts 3 endpoints — `GET /api/desktop/stats`, `GET /api/desktop/specs`, `POST /api/desktop/run-update`.
- `backend/server.py`: +15 lines mounting the new router beside existing releases_module mount. **Zero existing endpoints touched.**
- `backend/requirements.txt`: +2 lines — `pywebview==5.4`, `pystray==0.19.5`.

### Adaptive tiers (matches installer + dashboard + backend)
| Tier | Trigger | Max concurrent heavy jobs |
| ---: | --- | ---: |
| `low` | <= 4 GB RAM **or** <= 2 cores | 1 |
| `medium` | <= 8 GB RAM **or** <= 4 cores | 2 |
| `high` | <= 16 GB RAM **or** <= 8 cores | 4 |
| `extreme` | 16+ GB RAM **and** 8+ cores | 8 |

### Tests run (all pass)
- Backend boots cleanly on Linux container with new module ✅
- `/api/desktop/stats` returns full live snapshot ✅ (verified on 31 GB / 8 cores dev container → tier=high, max=4)
- `/api/desktop/specs` returns specs (200 on local with desktop pkg + 200 fallback on cloud edge) ✅
- `/api/desktop/run-update` rejects on cloud (KREXION_MODE=cloud → 400) ✅
- Existing routes (`/api/system/version`, `/api/system/public-latest`, `/api/system/installer-info`) unchanged + 200 ✅
- Dashboard HTML renders in browser with no JS errors, all polling working ✅
- `ruff` lint passes on all new modules ✅
- VPS auto-deploy succeeded (commit `f18879f` + follow-up `4d42975`) ✅
- All endpoints on `https://krexion.com` return 200 ✅

### Customer-PC impact (when they install v1.0.8)
- `VCRUNTIME140_1.dll` auto-installed → mongod runs ✅
- Krexion Database service starts + auto-restarts on crash ✅
- Task Manager shows only `krexion-core.exe` / `krexion-coreapp.exe` / `krexion-service.exe` (no `python.exe`) ✅
- Dashboard window opens at install end + on every login ✅
- Adaptive tier configured to their actual hardware ✅
- "Update Now" banner appears when admin publishes new release on krexion.com ✅

### Build artifact path for customer
Admin needs to manually trigger **Actions → Build Native Windows Release → Run workflow → enter version `v1.0.8`** → ~12 minute build → new `Krexion-Setup-v1.0.8.exe` attached to GitHub Release → admin publishes via Releases admin page → customers get auto-update banner.

### Future / Backlog (not in this push)
- `verpatch.exe` PE Version Info rewrite for renamed binaries (so even Process Properties → Details panel shows Krexion brand instead of "Python")
- EV code signing certificate (~$300/yr DigiCert) to remove Windows SmartScreen "Unknown Publisher" warning — biggest international-launch trust win
- Sentry / Rollbar crash reporting wired into the desktop dashboard for visibility into customer-side errors
- Cloud → desktop **auto-push** heavy jobs (currently customer must open desktop app and submit there; with auto-push, krexion.com "Start Recording" would dispatch to the connected PC transparently)
- Multi-language i18n in the cloud frontend (Spanish / Arabic / Hindi) for international expansion
- Anonymous opt-out telemetry for product analytics
- Backup-channel for desktop updates (stable / beta) so power users can opt in early

### Files Changed in This Iteration
- `installer/krexion-setup.iss` (modified — +160 lines incl. VC++ + service hardening + system-specs [Code])
- `build/build-backend.py` (modified — +55 lines incl. delete-original rename + desktop bundle copier)
- `.github/workflows/build-windows-release.yml` (modified — +28 lines for VC++ download step)
- `backend/server.py` (modified — +15 lines mounting desktop_router)
- `backend/requirements.txt` (modified — +2 lines: pywebview, pystray)
- `backend/desktop_module.py` (new — 281 lines, 3 routes + helpers)
- `desktop/__init__.py` (new — package marker)
- `desktop/krexion_dashboard.py` (new — 191 lines, PyWebView + pystray)
- `desktop/updater.py` (new — 131 lines, silent installer launcher)
- `desktop/system_info.py` (new — 121 lines, psutil + installer JSON merger)
- `desktop/krexion_tray_launcher.bat` (new — 44 lines, autostart shim)
- `desktop/static/index.html` (new — 152 lines, dashboard markup)
- `desktop/static/style.css` (new — 259 lines, dark-theme styling)
- `desktop/static/dashboard.js` (new — 195 lines, local + cloud polling)
- `desktop/README.md` (new — 81 lines, architecture doc)


---

## Iteration v1.0.10 — 2026-06-03: Native install dashboard + heavy-feature fixes

### User-reported symptoms (after v1.0.4 install on a fresh Windows PC)
1. **`krexion.com` opens after install but the local Krexion dashboard window does NOT** — customer expected the v1.0.8 PyWebView dashboard (per saved screenshot showing "Krexion — Local PC Dashboard" with CPU/RAM gauges + tier badge).
2. **No tray icon** — pystray icon never appears in the Windows notification area.
3. **Heavy features don't run** — RUT / conversion / click jobs submitted from krexion.com don't execute on the local PC; backend log shows Playwright chromium missing.

### Root causes
1. **`krexion_tray_launcher.bat` used `start /B "%PY%" ... >> logfile 2>&1`** — the `>>` redirection only captured `start`'s own output, NOT the launched `krexion-coreapp.exe` process (start detaches stdio handles). Since `krexion-coreapp.exe` is pythonw.exe (no console), ANY PyWebView/pystray/WebView2 init failure went to NUL → customer sees nothing, no crash log, no clue.
2. **PyWebView 5.x EdgeChromium backend requires Microsoft WebView2 Runtime.** Win11 ships it; clean Win10 LTSC / older 1809-1909 builds / N-editions don't. Without WebView2 → `webview.start()` raises silently → dashboard window never appears.
3. **GitHub Actions workflow had no Playwright Chromium bundling step.** The installer's Inno Setup source line `..\build\chromium-bundle\*` is marked `skipifsourcedoesntexist`, so when the folder doesn't exist the install silently skips it. Backend's `PLAYWRIGHT_BROWSERS_PATH` env var was being set to a missing folder → heavy jobs fail at `chromium.launch()` with "Executable doesn't exist".

### Fixes (4 files, +180 / -45 lines, zero existing behaviour removed)

#### 1. `desktop/krexion_dashboard.py` (rewritten — +200 lines, kept all original logic)
- **File logger initialised at the TOP of the module** (before any heavy imports). Lands at `{InstallDir}\logs\dashboard.log`. Even a top-level ImportError now leaves a paper trail.
- **`sys.excepthook` installed** to capture every uncaught exception with full traceback.
- **`_launch_pywebview_window()`** now returns False (not raise) when WebView2 fails to init.
- **`_launch_tkinter_fallback()`** — brand-new compatibility window using Tkinter (ships with embeddable CPython, zero extra deps). Shows Krexion brand + live backend status (polled every 2 s via `urllib.request`) + clear "Install WebView2 from go.microsoft.com/fwlink/p/?LinkId=2124703" hint + buttons to open krexion.com / logs folder. Customer ALWAYS sees a Krexion window after install — never a silent miss.
- **Tray icon fallback now uses solid-teal 16x16 image** instead of 1x1 transparent pixel (which Windows refused to render → invisible icon bug).

#### 2. `desktop/krexion_tray_launcher.bat` (rewritten — clean v1.0.10)
- Removed `start /B "%PY%" ... >> logfile 2>&1` (broken redirection).
- Now uses `start "" "%PY%" -m desktop.krexion_dashboard` — spawns the GUI interpreter detached, relies on Python's file logger inside the module for diagnostics.
- Exports `KREXION_LOG_DIR` env var so the Python logger always knows where to write (regardless of working-dir detection).
- Logs interpreter path + cwd + diagnostic context to `dashboard.log` BEFORE launching the Python process, so even if Python itself fails to start we see the .bat's last words.

#### 3. `installer/krexion-setup.iss` (additive — +20 lines)
- **New `[Files]` line**: bundles `MicrosoftEdgeWebview2Setup.exe` (Microsoft's official ~1.6 MB Evergreen bootstrapper) into `{tmp}`.
- **New `[Run]` line**: invokes `MicrosoftEdgeWebview2Setup.exe /silent /install` between the VC++ Redistributable step and the license-key persistence step. Idempotent — Microsoft's installer exits 0 instantly if WebView2 is already present.
- Both lines use `skipifdoesntexist` so a local build without the bootstrapper still produces a working installer.
- **Zero existing lines deleted or modified.**

#### 4. `.github/workflows/build-windows-release.yml` (additive — +60 lines)
- **New step: "Download Microsoft Edge WebView2 Runtime bootstrapper"** — pulls from `go.microsoft.com/fwlink/p/?LinkId=2124703` with 3-attempt retry, lands at `build/webview2/MicrosoftEdgeWebview2Setup.exe`.
- **New step: "Bundle Playwright Chromium"** — invokes `python -m playwright install chromium chromium-headless-shell` with `PLAYWRIGHT_BROWSERS_PATH=build/chromium-bundle`. Ships both the full Chromium (for visual recording / debugging) and the smaller chromium-headless-shell (used by the production RUT runner) so customers get heavy features working immediately, with no first-run download stall (also fixes corporate-proxy installs).

#### 5. `backend/VERSION` + `desktop/__init__.py` — bumped to `1.0.10`

### Tests run
- `ruff check desktop/krexion_dashboard.py` → all checks passed.
- `python -m ast.parse` syntax check on rewritten dashboard.py → OK.
- Verified `pywebview`, `pystray`, `pillow`, `psutil` already present in `backend/requirements.txt` → `build-backend.py`'s bulk-install path will pick them up.
- Verified the Inno Setup `[Files]` and `[Run]` additions use `skipifdoesntexist` so partial builds (e.g. a local dev who didn't run the workflow) still produce a working installer.

### What was NOT touched (per user's strict "kuch bhi kharab na ho" constraint)
- `backend/server.py` — zero changes
- `backend/desktop_module.py` — zero changes (endpoints still `/api/desktop/stats`, `/api/desktop/run-update`, `/api/desktop/specs`)
- `desktop/static/index.html`, `style.css`, `dashboard.js` — zero changes
- `desktop/updater.py`, `desktop/system_info.py` — zero changes
- All existing installer `[Setup]`, `[Tasks]`, `[Files]`, `[Dirs]`, `[Icons]`, `[Registry]`, `[UninstallRun]`, `[UninstallDelete]`, `[Code]` sections — preserved verbatim
- All other workflow steps (build-backend, build-frontend, MongoDB Portable, NSSM, Inno Setup install, compile, upload) — preserved verbatim
- Database schema, MongoDB collections, user data — untouched
- Frontend (cloud krexion.com) — untouched

### How customer experience changes after re-release as v1.0.10
1. Install runs as before (no change in wizard).
2. NEW: silent WebView2 install during prerequisites step (~2-20 s on Win10 without it, instant on Win11).
3. Backend + Database services register and start (same as before).
4. Final wizard page → "Launch Krexion now" checkbox → **dashboard window appears with brand + live stats** (instead of empty browser tab).
5. Tray icon appears in notification area; closing X minimises to tray (per design).
6. Heavy jobs submitted from krexion.com → actually run on the customer's PC (Chromium bundled).
7. If WebView2 still fails to init (unusual, e.g. corporate policy block), the Tkinter compatibility window appears with a clear "Install WebView2" button — customer is NEVER left wondering whether the install worked.

### Push status (ready for "Save to GitHub" → main)
Files changed (8):
- `backend/VERSION`
- `desktop/__init__.py`
- `desktop/krexion_dashboard.py`
- `desktop/krexion_tray_launcher.bat`
- `installer/krexion-setup.iss`
- `.github/workflows/build-windows-release.yml`
- `memory/PRD.md` (this entry)
- `frontend/.env` — left out of push by `.gitignore` (already gitignored, no change risk)

Working tree clean apart from these 8 files, no merge conflicts possible.

### Build & release flow for admin
After "Save to GitHub" lands on `main`:
1. Go to GitHub → Actions → "Build Native Windows Release" → Run workflow → enter tag `v1.0.10` → run.
2. ~12-18 minute build (Chromium download adds ~3-5 min). Produces `Krexion-Setup-v1.0.10.exe`.
3. Workflow auto-attaches the .exe to a new GitHub Release named `v1.0.10`.
4. Admin publishes via krexion.com → Releases admin page → customers get auto-update banner via the existing desktop updater path.

### Correction note (added same session)
First push went out as v1.0.5 because the local repo's `backend/VERSION`
file still read `1.0.4` and that's what we bumped from. The customer
pointed out that **v1.0.9 was already published** on GitHub Releases
on 2026-06-03. We cancelled the v1.0.5 workflow run, bumped both
`backend/VERSION` → `1.0.10` and `desktop/__init__.py.__version__` →
`1.0.10` to slot in cleanly after v1.0.9, and re-pushed + re-triggered
the build with tag `v1.0.10`. No code changes — only the version
strings and PRD wording were updated. The fix set described in this
section is identical to what landed in commit a72b41e plus the
version bump.

### Build chase log (same session) - finally green on build #23
- **#20** v1.0.5 - cancelled (wrong tag - v1.0.5 was already published).
- **#21** v1.0.10 - failed at "Bundle Playwright Chromium" step. PowerShell parser
  error on em-dash inside a Write-Warning string literal (U+2014 mangled to
  multi-byte by Windows-1252 codepage assumption inside the YAML heredoc).
  Fix: replaced all em-dashes / arrows / box-drawing characters in workflow
  YAML with ASCII equivalents (commit 86fe267).
- **#22** v1.0.10 - cancelled at minute 35 during "Compile installer". Inno
  Setup's lzma2/ultra solid compression of the new ~250 MB Chromium bundle
  needed ~14 min of silent ISCC.exe progress, blowing past the 30-min
  build-installer job timeout. Fix: raised timeout-minutes 30 -> 75 (commit
  d7486e7). No compression / output changes.
- **#23** v1.0.10 - SUCCESS. Total wall-clock ~50 min. Installer artifact
  `Krexion-Setup-v1.0.10.exe` (570.5 MB) published to GitHub Releases at
  https://github.com/dennisedmaartins9-sudo/krexion.com/releases/tag/v1.0.10



---

## v1.0.18 — Heavy job E2E (multipart bridge replay) — 2026-02

### Symptom seen by user on v1.0.17
- Heartbeat: green ✅, dashboard online in cloud
- `GET /api/sync/jobs/pull` → 200 OK every 5 s ✅
- But `[bridge] pulled N job(s)` NEVER logged → jobs NEVER reached the
  desktop bridge worker. Heavy job clicks on krexion.com vanished
  silently (or returned generic 503 / 422).

### Root cause (two stacked bugs)
1. `require_local_mode` in `backend/server.py` captured the heavy-
   endpoint body via `await request.json()`. That returns `{}` for
   ANY `multipart/form-data` POST. So the bridge payload had an
   empty `body` for RUT / Form Filler / Visual Recorder (all
   multipart). The desktop bridge worker then replayed `json={}`
   against its local backend, which immediately 422'd because
   those endpoints declare `Form(...)` fields.
2. The user's `Authorization: Bearer <jwt>` header was NOT forwarded
   on bridge replay. The desktop backend's `get_current_user`
   dependency would 401 even for pure-JSON heavy endpoints, because
   sync_client only sets `X-Krexion-License`.

### Fix
- `backend/server.py::require_local_mode`
  - `await request.body()` → raw bytes, b64-encoded into payload as
    `raw_body_b64` along with original `content_type` and
    `authorization` headers.
  - JSON parse still attempted when `application/json`, otherwise
    `body` stays empty (multipart replays use raw bytes).
  - `wait_for_result` timeout raised 10 s → 25 s.
  - Verbose `[bridge] auto-route ...` INFO log.
- `backend/sync_client.py::_execute_job_locally`
  - Decodes `raw_body_b64`; when content-type is multipart /
    urlencoded, replays via `httpx.AsyncClient.request(content=raw_bytes)`
    so FastAPI sees the exact original payload.
  - Forwards `Authorization` header to local backend.
  - Verbose `[bridge] replay ...` / `[bridge] replay → HTTP X` logs.
- `backend/bridge_module.py`
  - INFO logs on `enqueue`, inline `done/pending` exit, worker
    `claimed` jobs, and `worker_post_result`.
- `backend/VERSION` → 1.0.18; sync_client UA + version strings bumped.

### Push
- Commit `e4b5d7f` pushed to origin/main.
- GitHub Actions will:
  - Auto-deploy cloud (deploy.yml) → 2-3 min
  - Build Windows installer `Krexion-Setup-v1.0.18.exe` (build-windows-release.yml) → ~50 min
- Customer must reinstall v1.0.18 to receive the multipart replay fix
  (pure-JSON heavy endpoints, e.g. `proxies/bulk-test`, work
  immediately because the cloud-side raw-body fix routes through).

### Backlog / not addressed yet
- v1.0.18 still relies on the customer's local Playwright bundle
  being healthy. If a fresh installer somehow ships a broken
  `chrome-win/`, RUT will fail with browser-launch error — a
  separate self-heal that re-downloads chromium on demand would
  guard against that. Out-of-scope for this iteration.


---

## v1.0.19 / v1.0.20 — Stateful Bridge + Installer UX — 2026-02

### v1.0.19 fixes
1. **Legacy PowerShell `KrexionBridge` race condition** — old paired
   PCs had a Scheduled Task that polled `/api/sync/jobs/pull` every
   5 s with NO feature filter. It atomically claimed heavy jobs
   like `visual-recorder/start` and failed them with "feature not
   supported by the PowerShell bridge worker."
   Fix:
   - `bridge_module.enqueue_bridge_job` now pre-marks any
     non-adspower/* job with `excluded_workers=['powershell']`.
   - `/api/sync/jobs/pull` accepts `worker_type` param; legacy PS
     pulls default to `powershell` and get filtered out.
   - Failed PS jobs auto-requeue (max 3x) so the Python worker
     picks them up next cycle.
   - `sync_client.start_if_local()` `schtasks /Delete` the legacy
     KrexionBridge + KrexionHeartbeat tasks on startup
     (idempotent).

### v1.0.20 fixes
2. **RUT toast "undefined visit(s) queued"** — `require_local_mode`
   used `HTTPException(status=200, detail=body)` which made FastAPI
   wrap the body under `{detail: ...}`, so frontend's `data.total`
   / `data.job_id` were undefined. Replaced with a custom
   `_BridgeDone` exception + handler that returns the body verbatim
   as top-level JSON.
3. **Visual Recorder stuck on "Spinning up Chromium directly..."** —
   Only `/start` was bridged. Subsequent stateful calls
   (`/screenshot`, `/state`, `/click`, `/scroll`, etc) hit the
   cloud which has no session → silent 404 → spinner forever.
   Fix: new `@app.middleware('http')` `_vr_bridge_middleware` that
   transparently bridges every `/api/visual-recorder/*` request to
   the user's online desktop. Handles:
   - JWT from `Authorization: Bearer` header OR `?t=` query param
     (screenshot uses `?t=` so `<img src>` works without fetch).
   - Raw body + content-type forwarding (multipart, JSON, urlencoded).
   - Binary response support — sync_client base64-encodes non-JSON
     responses (e.g. `image/jpeg` screenshots) under
     `__binary_b64__` and the middleware re-decodes them, returning
     the original media type to the browser.
4. **VPS disk full → deploy timeouts** — VPS hit 100% disk with
   709 MB free. `docker builder prune -af` was unbounded and timed
   out at 30 min. Fix: timeboxed cleanup steps (60 s container/image
   prune, 5 min builder prune), nuclear fallback if `<3 GB` free,
   hard fail with `::error::` if still `<2 GB`.
5. **UX: Replaced PowerShell "Pair my PC" flow with installer CTA**
   - `LocalPCStatusBadge` now leads with a "Download Krexion-Setup.exe"
     button pointing to GitHub Releases.
   - License key still prominently displayed for paste into
     installer on first launch.
   - Legacy PowerShell snippet kept under collapsible
     "Advanced: PowerShell-only setup" with a warning that it only
     supports adspower/*.
   - This removes the future possibility of customers re-introducing
     the v1.0.19 race condition.

### Files changed
- `backend/server.py` — `_BridgeDone` exception + handler,
  `_vr_bridge_middleware`, raw-body + Authorization forwarding in
  `require_local_mode`, PowerShell template adds
  `feature_prefix=adspower/`.
- `backend/bridge_module.py` — `worker_type` filter,
  `excluded_workers` pre-mark, auto-requeue on PS feature-not-
  supported, verbose INFO logs.
- `backend/sync_client.py` — multipart+auth replay, base64 binary
  response support, `worker_type=python` on pull, startup cleanup
  of legacy KrexionBridge / KrexionHeartbeat scheduled tasks.
- `backend/VERSION` → `1.0.20`.
- `.github/workflows/deploy.yml` — aggressive timeboxed cleanup,
  nuclear fallback, fail-fast if disk still full.
- `.github/workflows/build-windows-release.yml` — auto-trigger on
  `backend/VERSION` change; tag derived from VERSION file.
- `frontend/src/components/LocalPCStatusBadge.js` — Download-first
  CTA, legacy PowerShell snippet collapsed under `<details>`.
- `frontend/src/pages/AdsPowerPage.js` — toast text updated.

### Released
- `Krexion-Setup-v1.0.18.exe` → cosmetic (multipart bridge)
- `Krexion-Setup-v1.0.19.exe` → kills race condition, adds
  KrexionBridge cleanup
- `Krexion-Setup-v1.0.20.exe` → full Visual Recorder bridging
  (binary response support) + UI changes

### What's verified
- ✅ Cloud deploy SUCCESS (commit `a247667`).
- ✅ `https://krexion.com/health` returns `{status:ok, mongo:true}`.
- ✅ All three Windows .exe installers published in
  https://github.com/dennisedmaartins9-sudo/krexion.com/releases
- 🟡 E2E heavy job test on customer's Windows VM pending.


---

## Iteration 21 — 2026-06-05: RUT bridging E2E — final completion (v2.1.7 + v2.1.8)

### User ask (Roman Urdu)
> "ab complete fix kr do login mein ne diya hai or proxy jet b fix kr k
> doabara test kr lena ab mujai proper working chahye ... ab koi masla
> ni ana chahye or rut job proper chalna chahye"

### Symptom chain that surfaced one-by-one
1. **Cloud edge 422 "Field required (body.link_id)"** —  already
   fixed in previous iteration (v2.1.6) via `request.form()` cache
   inside `require_local_mode`. Confirmed gone.
2. **Desktop returned 404 "Link not found"** — root cause: link was
   created on krexion.com UI so it landed in the cloud Mongo only;
   `sync_client` never pulls links cloud → desktop, so the desktop's
   local `db.links.find_one({id, user_id})` had nothing.
3. **Desktop returned 400 "ProxyJet Auto Mode … credentials not
   configured"** — same root cause: ProxyJet creds saved on
   krexion.com sit in the cloud's `proxyjet_credentials` only; the
   desktop's local DB had none.
4. **Cloud GET /api/real-user-traffic/jobs/{id} returned 404** —
   the bridged job was created on the desktop DB only; the cloud's
   `real_user_traffic_jobs` doesn't know about it, so polling for
   live progress, screenshots, stop button, etc. all 404'd.

### Fixes (cloud-only — NO desktop / installer rebuild)
- **v2.1.7 (a)** `backend/server.py` `require_local_mode`:
  before enqueueing the main heavy bridge job, if the body carries
  a `link_id`, fetch the link from the cloud DB and enqueue a tiny
  `POST /api/sync/links` bridge job first. The desktop's existing
  `sync_module._upsert_link` (already bundled in v2.1.4) writes it
  to the local DB with the same `id`/`short_code`/`user_id`.
- **v2.1.7 (b)** Same idea for ProxyJet creds: when the body has
  `use_proxyjet_auto=true`, fetch from `proxyjet_credentials` and
  pre-enqueue a `POST /api/proxyjet/credentials` bridge job. The
  bridge worker mints a local JWT so the local `get_current_user`
  dep succeeds.
- **v2.1.8** Extend `_vr_bridge_middleware` to also bridge every
  `GET/POST /api/real-user-traffic/jobs/*` (excluding the POST
  /jobs path which already bridges via `require_local_mode`). Now
  the cloud UI's polls for job detail, live-log, live-visits,
  diagnostics, screenshots, and stop reach the desktop.

Both pre-sync jobs are best-effort — failures log + continue so
the main job still runs and surfaces a clear error if anything
else is wrong.

### Files changed
- `backend/server.py` (+183 / -16, three commits)

### Verified end-to-end (under aadspower301@gmail.com)
- `POST /api/real-user-traffic/jobs` (cloud) → `200` + `job_id` ✅
- Bridge job ledger shows the auto-injected sequence:
  `sync/links → 200`, `proxyjet/credentials → 200`,
  `real-user-traffic/jobs → 200` ✅
- `GET /api/real-user-traffic/jobs/{id}` (cloud) → `200` with
  desktop's live job state ✅
- Job ran on desktop with ProxyJet US exit IP, visited
  `https://www.booking.com/`, returned **status=completed
  succeeded=1 failed=0** ✅
- live_steps include `geo/ok: Exit 100.1.222.78 · United States,
  Freehold`, `browser/ok: Page loaded (HTTP 202)`,
  `done/ok: Visit complete` ✅

### What was NOT touched
- Desktop bundle, `backend/VERSION`, installer (v2.1.4 stays in
  field — pre-sync uses endpoints that already exist in v2.1.4)
- No GitHub-Actions Windows-build trigger
- No frontend changes

### Commits
- `b8fe2dc` v2.1.7 (a) link pre-sync
- `56b7481` v2.1.7 (b) ProxyJet creds pre-sync
- `460399e` v2.1.8 bridge RUT GET endpoints

### Open / backlog
- ROW-FIRST ProxyJet mode without form-fill data still fails with
  "data file required" — pre-existing user-config requirement, not
  a bug. User workflow already uses form-fill + data file.
- `proxyjet_legacy_pregen=true` form param is read inside
  `_rut_prepare_and_run` but not declared in the `/jobs` POST
  signature, so it can't be enabled from the API today. Low
  priority (the real fix is on-demand fetcher which is the
  default).


---

## Iteration 22 — 2026-06-05: 'Resync to PC' button + v2.1.8 Windows build

### User ask (Roman Urdu)
> "kr do or ab new version sab changing k sath complet build kr do
> ta k ab koi issue na ay"

### What shipped
1. **Backend** — `POST /api/bridge/resync-to-desktop`
   (`backend/server.py`). Bulk-pushes the caller's links +
   ProxyJet credentials into the desktop's local Mongo using the
   same `wait_for_result` bridge replay as the v2.1.7 auto
   pre-sync. Returns per-record status + an `errors[]` array so
   the UI can show partial results. Refuses with a friendly
   message when the PC is offline.
2. **Frontend** — `LocalPCStatusBadge.js`. New sky-coloured
   "Resync to PC" pill button next to the green "PC connected"
   badge. Toast loader → success / partial / error. Disabled
   while a sync is in flight.
3. **VERSION bump** `2.1.4 → 2.1.8` to trigger
   `build-windows-release.yml` (auto-builds & publishes a fresh
   `Krexion-Setup-v2.1.8.exe` carrying every cumulative
   sync_client / bridge / heartbeat fix from this work block).

### Why
The auto pre-sync (v2.1.7) handles the common path — RUT /
Form-Filler bridges carry a `link_id`, so the cloud injects a
`sync/links` job ahead of them.  The manual button covers:
- Fresh installs that heartbeat AFTER the user populated
  krexion.com.
- Reconnects after long offline periods.
- Edge cases where a bridged POST has no `link_id` in the body.

### Verified
- Cloud deploy `2567f3b` → success.
- `POST /api/bridge/resync-to-desktop` reachable; offline-PC
  branch returns the proper guardrail JSON
  (`online:false, message:"Your PC is offline..."`).
- Online-PC branch shares the exact `_enq()` codepath as the
  auto pre-sync that was end-to-end verified in iteration 21
  (booking.com visit completed via ProxyJet US exit IP).
- Windows installer build `in_progress` on Actions for
  `2567f3b`.

### Files changed
- `backend/server.py`  +154
- `frontend/src/components/LocalPCStatusBadge.js`  +63 / -19
- `backend/VERSION`  2.1.4 → 2.1.8

### Commit
- `2567f3b` feat: v2.1.8 — 'Resync to PC' button + full v2.1.8
  desktop build.
