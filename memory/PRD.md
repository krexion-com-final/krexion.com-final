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
