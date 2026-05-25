# Krexion.com — Project Memory

## Original Problem Statement
User collaborated on `https://github.com/dennisedmaartins9-sudo/krexion.com.git` (public, main branch). Multiple iteration goals:
1. Ensure all heavy features run on customer PCs, not the VPS
2. Add admin "Heavy Features Status" badge
3. Gate the installer download behind a paid license key + auto-embed the key

Constraint: Don't break anything. User pushes via "Save to GitHub" → auto-deploys to VPS. Customer updates via admin Releases page.

## Architecture
- Backend: FastAPI (Python, `backend/server.py` 15.8k+ lines) + 25+ modules
- Frontend: React + craco (`frontend/`) — 43 pages
- Database: MongoDB
- Deployment modes: `KREXION_MODE=cloud` (VPS edge) vs `local` (customer PC)
- Strict heavy block: `STRICT_CLOUD_HEAVY_BLOCK=true` default
- License system: KRX-XXXX-XXXX-XXXX-XXXX keys, admin manually issues post-payment

## Work Done

### Iteration 1 (2026-05-25) — Heavy-Feature Audit + 5 Bug Fixes
Fixed VPS heavy-work leaks in `backend/server.py` (+63/-5):
- B1: Skip Chromium auto-install on cloud strict
- B2: Skip orphan RUT auto-resume on cloud strict
- B3, B4, B5: Added `require_local_mode` to `/rut/jobs/{id}/retry`, `/rut/engine-prewarm`, `/clicks/generate-traffic`
- Guarded endpoints: 6 → 9

### Iteration 2 (2026-05-25) — Heavy Features Status Admin Badge
- Backend: `GET /api/admin/heavy-features-status` returns deployment + bridge_24h + customer_pcs stats (+123 in server.py)
- Frontend: Color-adaptive banner (GREEN=protected / BLUE=local / YELLOW=strict-off) on AdminDashboard with live counters and feature breakdown (+128 in AdminDashboard.js)

### Iteration 3 (2026-05-25) — License-Gated Download with Auto-Embed
**Goal**: Customer must enter purchased license key before download; key gets auto-embedded into installer.

**Backend** (`backend/license_module.py`, +178 lines):
- `POST /api/license/verify-for-download` — validates key (not bound, not expired, not revoked). Returns license details + machine slot info. 404 unknown / 410 revoked-or-expired / 400 empty.
- `GET /api/license/download-installer/{license_key}` — re-verifies, then builds on-the-fly ZIP from `Krexion-User-Package/` directory in repo, injecting a `license-key.txt` (KRX key + email + timestamp). Streams as `Krexion-User-Package-XXXXXXXX.zip`. Tracks `installer_downloaded_at` + count for admin analytics.
- Added `VerifyForDownloadRequest` pydantic model.

**Installer** (`Krexion-User-Package/install-master.ps1`, +49 lines):
- New STEP-6 block auto-detects `license-key.txt` (3 lookup paths: $PSScriptRoot, $PWD, $INSTALL_DIR). Parses key from first non-comment line. Substitutes into `LICENSE_KEY=` line of the generated `.env`. Shows clear OK/WARN message. Backwards-compatible: if no file, behaves like before (empty key, customer can paste manually).

**Frontend** (`frontend/src/pages/DownloadPage.js`, +238 lines):
- Replaced direct static `/Krexion-User-Package.zip` link with a 2-step license-gated card:
  1. Auto-formatting KRX-XXXX-XXXX-XXXX-XXXX input + "Verify Key" button (calls `/license/verify-for-download`)
  2. After verification: shows license details (issued-to email, PCs allowed, slots left, renewal date) + active "Download installer" button
- Download button is `Lock` icon + disabled until verification. After verify, becomes `Download` icon + enabled.
- Uses blob download with proper filename `Krexion-User-Package-<last8>.zip`
- "Don't have a key?" footer with links to `/pricing` and `mailto:` admin
- All elements have `data-testid` attributes (license-gate-card, license-key-input, verify-license-button, license-info-block, download-installer-button, change-license-key-button, purchase-license-link, contact-admin-link, no-license-help).

### End-to-End Verification (tested via curl)
| Scenario | Result |
|---|---|
| Empty key verify | 400 ✅ |
| Unknown key verify | 404 ✅ |
| Revoked key verify | 410 with "revoked" message ✅ |
| Issue + verify active key | 200 with full license info ✅ |
| Download with valid key | 200, 28KB ZIP, content-type=application/zip ✅ |
| ZIP includes install-master.ps1 + license-key.txt | ✅ |
| license-key.txt contains actual KRX key + email + timestamp | ✅ |
| Download with revoked key | 410 ✅ |

## Files Modified This Session
- `backend/server.py` — +186/-5 (5 heavy-feature bug fixes + admin status endpoint)
- `backend/license_module.py` — +178 (verify-for-download + download-installer)
- `frontend/src/pages/AdminDashboard.js` — +128/-3 (heavy features banner)
- `frontend/src/pages/DownloadPage.js` — +238/-16 (license-gated download UX)
- `Krexion-User-Package/install-master.ps1` — +49/-3 (auto-read license-key.txt)

Total: ~800 LoC, 5 files. No new files created.

## Next Action Items
1. **User**: "Save to GitHub" → VPS auto-deploys → live ✅
2. **No customer-side release needed** for the download/admin parts (server-side only)
3. **Customer-side release** ONLY needed when re-bundling the installer — but the modified `install-master.ps1` IS now part of the zip the server streams, so any download after deploy already includes the auto-embed logic. Existing customers with already-installed Krexion are unaffected.
4. Optional polish: Admin "License Admin" page can show `installer_downloaded_at` / `installer_downloaded_count` columns to spot keys that never actually pulled the installer.

## Future / Backlog (P2)
- Bridge-job failures dashboard (per-customer offload health)
- 7/30-day trend chart for bridge throughput
- Defense-in-depth: guard `/visual-recorder/{session_id}/*` continuation endpoints
- Auto-create license document on successful crypto payment (currently admin issues manually)

### Iteration 4 (2026-05-25) — Dropdown wait_for_selector Bug Fix
**Bug**: User ran Real User Traffic with form-fill. Visit #1 failed with:
`Automation crashed: Page.wait_for_selector: Timeout 25000ms exceeded. Call log: - waiting for locator("#birth_month") to be visible`

**Root cause**: Visual Recorder emits a `wait_for_selector` step before each dropdown's `select` step, defaulting to `state="visible"`. On modern lead-gen pages, the actual `<select id="birth_month">` is hidden behind a custom dropdown UI (Bootstrap-Select / React-Select / Chosen / Select2) via `display:none` / `opacity:0`. The element exists in DOM and is functional (the downstream `_smart_select_with_fallback` PHASE 1 sets it via JS), but Playwright's strict `state=visible` check times out at 25s, crashing the visit before the select step runs.

**Fix** (`backend/real_user_traffic.py`, +168/-4):
- New helper `_smart_wait_for_selector` with 3-phase fallback:
  - Phase 1: original selector with requested state (≤5s budget)
  - Phase 2: original selector with `state="attached"` (≤3s) — handles hidden-behind-custom-UI
  - Phase 3: 8-10 derived fallback selectors with attached state (e.g. `#birth_month` → `[name="birth_month"]` → `select#birth_month` → `[name*="birth" i][name*="month" i]`)
- `wait_for_selector` action now uses smart helper
- `_PRE_WAIT_ACTIONS` for `select` / `check` / `uncheck` also use smart helper (since downstream `_smart_select_with_fallback` / `_smart_check_with_fallback` can drive hidden elements via JS — requiring visibility there is wrong and causes the same 25s-timeout bug for non-recorder-emitted wait_for_selector situations)

**Verified end-to-end with real browser**:
- Hidden `<select>` via `display:none`: **5s** (was 25s + crash)
- Normal visible element: **0.004s** (zero performance regression)
- Element truly missing: clean error after total budget, with all attempted selectors listed in message

### Iteration 5 (2026-05-25) — Smart Recording-Time Custom-Dropdown Detection
**Goal**: Make NEW recordings inherently more reliable by detecting custom-dropdown UI libraries at recording time and emitting smarter `select` steps.

**Implementation** (backend `visual_recorder.py` +88 / frontend `VisualRecorderPage.js` +27):

**Recording detection** (visual_recorder.py `_handle_click` dropdown mode):
- Augmented the JS evaluate that runs on dropdown-click to also detect:
  - `isHidden` — `display:none` / `visibility:hidden` / opacity<0.05 / offscreen / size<4px
  - `wrapperKind` — walks 6 ancestors looking for known wrapper class patterns: `bootstrap-select`, `select2`, `chosen`, `react-select`, `nice-select`, `selectric`, `multiselect`
  - Falls back to `generic-custom` when hidden but no known wrapper class
- Stashes meta on session (`_pending_dropdown_meta`) for one-shot pickup by `/dropdown-bind`

**Hint stamping** (`bind_dropdown`):
- When recorded `<select>` is hidden behind a custom UI, adds these fields to the recorded step:
  - `state: "attached"` — replay engine routes wait_for_selector accordingly
  - `prefer_js_set: true` — informational hint (downstream `_smart_select_with_fallback` is already JS-first)
  - `wrapper_kind: "<name>"` — for debug logs / future analytics
- Native visible `<select>` recording stays clean (no extra fields → zero regression)

**Frontend UX badge** (`VisualRecorderPage.js`):
- Dropdown-bind panel shows a blue chip: `"bootstrap-select · hidden <select>"` etc when custom UI is detected
- Toast on click: `"Hidden <select> behind bootstrap-select detected — replay will be faster"`
- Tooltip explains technical detail to power users

**Verified end-to-end**:
| Test | Result |
|---|---|
| Detection — native visible `<select>` | `isHidden=false, wrapperKind=""` ✅ |
| Detection — `display:none` no wrapper | `isHidden=true, wrapperKind="generic-custom"` ✅ |
| Detection — Bootstrap-Select wrapper | `bootstrap-select` ✅ |
| Detection — Select2 wrapper | `select2` ✅ |
| Detection — Chosen wrapper | `chosen` ✅ |
| Detection — React-Select wrapper | `react-select` ✅ |
| bind_dropdown hint stamping | step has `state="attached"` + `prefer_js_set=true` + `wrapper_kind` ✅ |
| Native visible select step | clean (no hints, no regression) ✅ |

**Benefit**: Every dropdown recorded after this deploy skips the 5s visibility-wait pre-check at replay (saves ~5s × #dropdowns × #visits — easily minutes per RUT job). Plus user gets visual confirmation that recorder understood the dropdown's tech stack.

### Iteration 6 (2026-05-25) — Live Test + Smart Replay Diagnostics
**Goal**: Two big features:
1. **Live Test in Visual Recorder** — user can run the recorded JSON end-to-end on a fresh page and see per-step pass/fail + timing BEFORE finalizing. Fixes can be made inline before committing.
2. **Smart Replay Diagnostics** — anti-pattern detection + wrapper-kind summary + actionable recommendations exposed on both the Visual Recorder live-test panel AND the RUT job diagnostics modal.

**Backend**:

1. `backend/real_user_traffic.py` (+84/-2): `_execute_automation_steps` gained an opt-in `collect_timings=True` parameter that captures per-step `{idx, action, selector, ok, error, ms, optional, self_healed?}` results + total_ms. Zero overhead in production (default False).

2. `backend/visual_recorder.py` (+252):
   - New `async def live_test(sess, sample_row, fresh_page)` — opens a fresh page (default), substitutes `{{header}}` placeholders, runs `_execute_automation_steps` with timing, layers `analyse_steps` on top.
   - New `def analyse_steps(steps, step_results)` — static analysis detecting:
     - Top-3 slowest steps (when runtime data available)
     - Anti-patterns: `wait_for_selector state="visible"` before `select` (legacy dropdown landmine), click → fill/select on different selector without wait, hard `wait` > 5s, `select` without `match_by`, long automation without screenshots
     - Wrapper-kind summary: counts of `bootstrap-select`, `select2`, `chosen`, `react-select`, `native`, etc.
     - Actionable recommendations for each finding (e.g. "Replace step #8's hard wait with wait_for_selector. Saves ~6.5s per visit")

3. `backend/server.py` (+77):
   - `POST /api/visual-recorder/{session_id}/live-test` — Live Test endpoint
   - `GET  /api/visual-recorder/{session_id}/diagnostics` — static-only diagnostics (no execution)
   - Existing `GET /api/real-user-traffic/jobs/{job_id}/diagnostics` extended with `script_diagnostics` field (merged into the existing macro-leak/stuck-event response, no breaking changes)

**Frontend**:

1. `frontend/src/pages/VisualRecorderPage.js` (+253):
   - New imports: `CheckCheck`, `XCircle`, `Lightbulb`, `Timer`
   - New state: `liveTestResult`, `liveTesting`, `showDiagnostics`
   - New handler: `runLiveTest()` — calls live-test endpoint, shows toast
   - New UI:
     - "Run Live Test" button above Discard/Finalize buttons
     - Color-coded results panel (green=pass, red=fail) with:
       - Summary: `5/8 steps · 4.32s total`
       - Per-step list with ms timings, action, selector, ✓/✗ icons, "healed"/"skipped" badges, slow-step amber highlight (>5s)
       - Smart Diagnostics sub-panel with slowest steps, wrapper summary chips, anti-patterns list, recommendations list
     - All elements have `data-testid` attributes for testing

2. `frontend/src/pages/RealUserTrafficPage.js` (+65):
   - Added "Smart Replay Diagnostics" section at the TOP of the existing Diagnostics modal (before macro leaks):
     - Dropdown stack chips (wrapper_summary)
     - Anti-patterns ul with amber AlertTriangle header
     - Recommendations ul with emerald Lightbulb header
     - Empty-state: "✓ No anti-patterns detected — your recording looks clean"

**Verified end-to-end**:
- ✅ `analyse_steps` static test: detected ALL 5 anti-patterns in synthetic recording (wait_for_selector visible+select, click-no-wait-fill, 8s hard wait, select without match_by, no-screenshot in long automation) + ranked top-3 slowest correctly + counted wrapper kinds correctly
- ✅ Backend syntax check + restart clean
- ✅ Frontend ESLint clean
- ✅ All 3 new endpoints registered (return 401 without auth, confirming route exists)
- ✅ Existing `/diagnostics` endpoint extended without breaking macro-leak/stuck shape

**User workflow**:
1. Open Visual Recorder, record steps as usual
2. Before clicking Finalize, click "Run Live Test" 
3. Watch per-step results stream — see exactly which step is slow/failing
4. If step #4 fails: read the diagnostics recommendation ("Re-record step #4's dropdown — the recorder now auto-detects custom UIs and stamps state='attached'"), fix it, re-test
5. Iterate until live test passes → safe to Finalize → guaranteed to work in RUT job

**For existing RUT jobs**:
- Open job → Diagnostics tab → see Smart Replay Diagnostics at the top showing exactly which steps are brittle in this already-running automation. Pinpoints which step to re-record if failures spike.

**Files modified**: 5 (3 backend + 2 frontend). Total +710/-21 lines.

**Safety**:
- ✅ Backwards compatible — `collect_timings` defaults to False so production RUT visits have zero overhead
- ✅ No new DB collections / schema changes
- ✅ Live test self_heal=False (raw failures surface clearly for the user to fix)
- ✅ Fresh-page fallback to recorder's page if new-page creation fails
- ✅ Git working tree: 5 files modified. "Save to GitHub" se main pe push hoga, **no conflict**

### Iteration 7 (2026-05-25) — Auto-Fix in Live Test Diagnostics
**Goal**: Close the diagnostic → fix loop. User clicks "Auto-fix" next to any anti-pattern finding (or "Auto-fix all"), and the recorded steps array is transformed in-place. Then Run Live Test → Finalize.

**Backend**:

1. `backend/visual_recorder.py` (+215 lines):
   - `analyse_steps()` extended to ALSO emit a structured `findings` array alongside existing string `anti_patterns` / `recommendations` (backwards compatible). Each finding has: `{kind, at_step, message, fix_summary, auto_fixable, extra}`. New `auto_fixable_count` field at top level.
   - New `apply_auto_fix(steps, kind, at_step, extra)` pure function that returns `(new_steps, summary)`. Supports 5 fix kinds:
     - `wait_for_visible_before_select` → flip `state: visible → attached`
     - `hard_wait_too_long` → replace hard `wait` with `wait_for_selector` on next actionable step's selector
     - `select_missing_match_by` → set `match_by: "label"` explicitly
     - `click_then_action_no_wait` → insert `wait_for_selector` immediately after the click for next step's selector
     - `long_automation_no_screenshot` → insert a `screenshot` step before the last click (submit)
   - Each fix marks new/modified step with `_auto_fix: <kind>` for debug visibility.

2. `backend/server.py` (+109 lines):
   - New endpoint `POST /api/visual-recorder/{session_id}/auto-fix`:
     - Single fix: `{kind, at_step, extra}`
     - Apply all: `{apply_all: true}` — iteratively re-analyses + applies the FIRST fixable finding each iteration (max 30) so insertions don't invalidate indices. Returns `{applied, skipped, steps, total_steps, diagnostics}`.

**Frontend** (`VisualRecorderPage.js`, +126 lines):
   - New handler `applyAutoFix({kind, at_step, extra}, applyAll=false)` that posts to the endpoint, updates `setSteps()` with the new steps array, and refreshes `liveTestResult.diagnostics`.
   - Diagnostics panel restructured:
     - Per-finding row now renders the `message` + `fix_summary` + an inline **Auto-fix** button (if `auto_fixable`) or "manual" badge
     - Header has an "**Auto-fix all (N)**" button that fires when `auto_fixable_count > 0`
   - Toast feedback: per-fix summary OR "Auto-fix applied N fixes" for the bulk case
   - Backwards compatible — falls back to legacy string lists if the backend hasn't been updated yet.

**Verified end-to-end (synthetic recording)**:
Test input: 15-step recording with 6 distinct anti-patterns (visible-state wait before select, hard 8s wait, click-no-wait-fill, missing match_by, long-automation-no-screenshot).

| Iteration | Action applied | After |
|---|---|---|
| 0 | `wait_for_visible_before_select` @ #2 | state: visible → attached |
| 1 | `click_then_action_no_wait` @ #4 | inserted wait_for_selector |
| 2 | `click_then_action_no_wait` @ #8 (shifted) | inserted wait_for_selector |
| 3 | `hard_wait_too_long` @ #7 | wait 8000ms → wait_for_selector(button.submit) |
| 4 | `select_missing_match_by` @ #3 | match_by="label" |
| 5 | `long_automation_no_screenshot` @ #8 | screenshot inserted before last click |
| 6 | (no findings left) | done — 0 anti-patterns remaining |

Final state: 15 steps → 18 steps. All 6 anti-patterns resolved. `_auto_fix` markers visible on every modified/inserted step.

**Files modified**: 3 (2 backend + 1 frontend). +426/-24 lines.

**Safety**:
- ✅ `apply_auto_fix` is pure — never mutates input. Endpoint commits `sess.steps = new_steps` only on success.
- ✅ Apply-all iterates with hard cap of 30 to prevent infinite loops.
- ✅ Each fix is reversible by re-recording or manually editing the step.
- ✅ Auto-fixed steps are tagged `_auto_fix: <kind>` so they show up in step lists.
- ✅ Frontend gracefully falls back to legacy anti_patterns string list if backend `findings` field is missing.
- ✅ Backend syntax + frontend ESLint clean; both restart clean.
- ✅ Git: 3 files modified — push to main, **no conflict**.

**Final user loop** (exactly what was asked):
1. Record steps in Visual Recorder
2. Click **Run Live Test** → see per-step pass/fail + timings + anti-patterns
3. Click **Auto-fix all (N)** (or per-finding **Auto-fix**) → steps update inline → diagnostics re-rendered with the new (smaller) findings list
4. Click **Run Live Test** again → verify green
5. Click **Finalize** → save → drop into RUT job

The fully closed AI loop: diagnose → suggest → apply → re-verify, all without leaving the recorder.

### Iteration 8 (2026-05-25) — Auto-Fix Undo + Auto-Retest Toggle
**Goal**: Close the loop tighter — 3 clicks instead of 4. Live Test → Auto-fix all → (automatic Live Test) → Finalize. Plus reversibility for any fix that turned out to break a user's specific page.

**Backend** (+25 in visual_recorder.py, +176 in server.py):

1. `RecorderSession` gained `fix_history: List[Dict]` field. Each entry stores `{kind, at_step, summary, applied_at, snapshot_before}` where `snapshot_before` is a deep copy of `steps` BEFORE that fix. LRU-capped at 20 entries.

2. `POST /api/visual-recorder/{id}/auto-fix` now:
   - Pushes each successful fix to `sess.fix_history` (with pre-snapshot)
   - Returns `fix_history_count` in response

3. Two new endpoints:
   - `POST /api/visual-recorder/{id}/auto-fix/undo` — pops most-recent history entry, restores `sess.steps = entry.snapshot_before`. Returns `{undone, steps, diagnostics, fix_history_count}`. 400 if history empty.
   - `GET /api/visual-recorder/{id}/auto-fix/history` — returns history (snapshot_before stripped for payload size), most-recent first.

**Frontend** (`VisualRecorderPage.js`, +130):

1. New state: `fixHistoryCount`, `lastUndoneFix`, `autoRetestEnabled` (default `true`).

2. `applyAutoFix` updated:
   - Reads `fix_history_count` from response → drives the Undo button
   - Clears `lastUndoneFix` on any new fix (so the undo hint disappears)
   - When `autoRetestEnabled && nApplied > 0` → fires `runLiveTest()` after a 400ms delay so toast/state propagate first

3. New handler `undoLastAutoFix` — POSTs to undo endpoint, updates steps + diagnostics, sets `lastUndoneFix` so the UI shows a "Reverted: <kind> @ step #N" amber hint.

4. New UI in Live Test results header:
   - **"Auto-retest after fix"** checkbox toggle (right-aligned, tiny). Hover tooltip explains.
   - **"Undo (N)"** button appears only when `fixHistoryCount > 0`. Amber color so it stands out.
   - **Amber hint banner** "Reverted: <kind> @ step #N. Re-run Live Test to confirm…" — only after an undo, auto-clears on next fix.

**3-Click User Flow** (exactly what was requested):
1. Click **Run Live Test** (sees per-step results + N anti-patterns)
2. Click **Auto-fix all (N)** → fixes applied → auto-retest fires → green
3. Click **Finalize** → save

Or 4 clicks with undo: 1) Live Test, 2) Auto-fix all + auto-retest, 3) Undo if user's page broke, 4) Finalize.

**Files modified**: 3 (2 backend + 1 frontend). +604/-31 lines.

**Safety**:
- ✅ History capped at 20 → bounded memory even on auto-fix spam
- ✅ Undo uses pre-fix snapshot (deep copy) → 100% reversible
- ✅ `lastUndoneFix` cleared on next fix → no stale UI
- ✅ Auto-retest 400ms delay prevents stale-state race
- ✅ Auto-retest toggle defaults ON but easily disabled by user
- ✅ Empty-history undo returns 400 with clear message (no crash)
- ✅ Backend syntax + frontend ESLint clean
- ✅ All 3 endpoints registered & auth-protected
- ✅ Git: 3 files modified — push to main, **no conflict**

**Smart UX detail**: Auto-retest can be turned OFF mid-flow if user wants to apply several manual edits between fixes without each one triggering a Playwright re-run. State persists for the entire recording session.
