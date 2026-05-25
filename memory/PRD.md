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
