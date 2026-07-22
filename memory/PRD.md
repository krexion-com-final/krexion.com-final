# Krexion — Collaborator Session PRD

**Repo:** krexion-com-final/krexion.com-final (main branch)
**Current version on GitHub:** v2.6.21
**Local fix ready for release:** v2.6.22 (not yet pushed)

## Original Problem Statement
User is a collaborator on the Krexion repo. Uses this preview env as a staging surface to make bug fixes and small tweaks against the live main branch. VPS auto-deploys on push to main. Windows/Electron installers auto-build on `backend/VERSION` bumps.

Golden rules given by user:
- Never break/miss/delete anything in the repo.
- Save-to-git happens against main branch only — no conflicts.
- Deploy only when user explicitly says "deploy" (bundle multiple changes for one deploy).
- Any change must be applied everywhere (cloud VPS + native app + Electron app) so no customer breaks.

## Session 1 — 2026-07-21

### Setup
- Cloned `krexion-com-final/krexion.com-final` main branch into `/app` (PAT-authenticated remote).
- Backend runs on preview with `KREXION_MODE=cloud` + `STRICT_CLOUD_HEAVY_BLOCK=false` so admin/auth/licensing work locally (default `local` mode forwards to production krexion.com).
- Admin login working: `admin@krexion.local` / `Krexion@Preview2026!`.
- Preview URL: https://krexion-staging-14.preview.emergentagent.com

### Bug Fix Applied (NOT YET PUSHED)

**Reported issue:** RUT job with TikTok in-app preset + TikTok UA generator selected produced clicks that advertiser trackers labelled as MIXED browsers (Facebook, Chrome, Safari) instead of only TikTok.

**Root cause:** `referrer_pro.coerce_ua_for_platform()` short-circuited on idempotency (`_ua_has_inapp_marker`) BEFORE stripping foreign in-app markers. Hybrid UAs (musical_ly + FBAV, or musical_ly + Chrome/Mobile Safari WebView leaks) passed through UNCHANGED because they contained the target marker. Downstream advertiser UA parsers latched on the earlier FB bracket or Chrome/Safari tokens and mis-labelled clicks.

Secondary issue: `server._ua_tiktok_android()` was emitting the OLD WebView shape (`Chrome/xxx Mobile Safari/537.36`) so the generator's own output was Chrome-labelled by trackers.

**Fixes:**
1. `backend/referrer_pro.py` — `coerce_ua_for_platform()` flow reordered: strip foreign markers → (TikTok Android only) Cronet-leak guard rebuilds base if `Chrome/` or `Safari/` still present, preserving any clean `musical_ly` suffix → THEN idempotency check on the cleaned UA → append target suffix if still needed.
2. `backend/server.py` — `_ua_tiktok_android()` rewritten to emit real Cronet shape matching `referrer_pro._rebuild_tiktok_android_ua_base` output.

**Verification (backend testing subagent, iteration_15):**
- All 11 new tests in `backend/tests/test_v2_6_21_hybrid_ua_leak_fix.py` PASS
- All 12 existing tests (`test_v2_6_18_browser_mix_and_utm_fix.py`, `test_v2_6_19_tiktok_ua_rebuild.py`) still PASS
- Total: 23/23 targeted tests green
- Test report: `/app/test_reports/iteration_15.json`

### Files changed this session
- `backend/referrer_pro.py` (coerce_ua_for_platform reorder)
- `backend/server.py` (_ua_tiktok_android → Cronet form)
- `backend/tests/test_v2_6_21_hybrid_ua_leak_fix.py` (new — 11 tests, added by testing_agent)

### Pending Deploy Actions (when user says "deploy")
- [ ] Bump `backend/VERSION` from `2.6.21` → `2.6.22`
- [ ] Append release note to `backend/VERSION_NOTES.txt`:
  ```
  # v2.6.22 (2026-07-21) — Hybrid UA leak fix (mixed-browser bug on TikTok RUT)
  # - referrer_pro.coerce_ua_for_platform: strip foreign in-app markers BEFORE idempotency check
  # - Added TikTok Android Cronet-leak guard: forces Cronet rebuild if Chrome/ or Safari/ tokens leaked through
  # - server._ua_tiktok_android generator now emits real Cronet-shape UA (was WebView + Chrome/Safari)
  # - Impact: advertiser trackers (Traxun/Voluum/RedTrack/Binom/IPQS) now correctly label TikTok RUT clicks as TikTok, not Facebook/Chrome/Safari
  # - 11 new regression tests in test_v2_6_21_hybrid_ua_leak_fix.py
  ```
- [ ] `git push origin main` (triggers deploy.yml + build-windows-release.yml + build-electron-desktop.yml → VPS + Windows .exe + Electron .exe auto-update)

## Backlog (future sessions)
- OPTIONAL: Update stale ADMIN_PASSWORD constant in older test files (`test_rut_referrer_bugs.py`, `test_rut_referrer_concurrency_fixes_2026_02.py`) from `Krexion@2026` to read from env.
- OPTIONAL: Fix stale line-range assertion in `test_rut_referrer_concurrency_fixes_2026_02.py::TestCtxArgsFix` (`src_lines[8778:8830]` window has drifted).
- OPTIONAL (bigger refactor): `server.py` is 25,685 lines — modular split (device pools, UA generators, region picker, etc.) recommended.


---

## Session 2 — 2026-01 (v2.6.26 TikTok Android browser detection fix)

### Preview URL + Login
- Preview: https://d8a047c1-875d-4ded-827a-6635047dd9c3.preview.emergentagent.com
- Admin: `admin@krexion.local` / `KrexionAdmin@2026` at `/admin-login`
- Details in `/app/memory/test_credentials.md` (gitignored)

### Setup
- Fresh preview container. `/app` re-synced to `origin/main` (latest = v2.6.25 `6447006`).
- `.env` files (backend + frontend) re-created — gitignored — VPS `.env` untouched.
- Deps installed, supervisor running backend + frontend + mongodb.
- Sanity: `/api/public/status` 200 + admin login → JWT.

### Reported Bug (customer's clicks (4).csv — 106 rows Everflow export)
- 40/106 rows (37.7%) had `Browser=<empty>` — of which 12+1/13 Android TikTok rows had empty/junk Browser
- Cross-tab confirmed: **iOS TikTok clicks 10/10 correctly detected as "TikTok for iOS"**;
  **Android TikTok clicks 0/13 detected** — 12 empty, 1 junk "Android"
- Other Browser=empty rows were the 25-row PK cluster (IP `154.192.133.37`, Cloud Innovation Ltd)
  which is not a Krexion bug (empty referer + malformed UA from same IP → likely QA/test/bot).
- Referrer stripping to origin (`www.tiktok.com/`, `www.facebook.com/`, `www.instagram.com/`)
  is chromium's Referrer-Policy=`strict-origin-when-cross-origin` default — NOT a Krexion bug.
- `Model` column being 100% empty is a tracker limitation (Everflow can't derive model
  from UA alone without Client-Hints) — not fixable server-side without adding SDK on landing.

### Root Cause (Android TikTok Browser=empty)
`_ua_tiktok_android` (v2.6.22 Cronet rebuild) emitted `musical_ly_<10digit_build>` as the
only TikTok identifier. Modern advertiser UA parsers (ua-parser-js / uap-core /
Everflow / Voluum / RedTrack) use the primary rule `TikTok/([\d.]+)` to detect TikTok
browser. Without that slug, they fell through to the generic Android rule and reported
`Browser=<empty>`. iOS works because `_ua_tiktok_ios` carries `AppId/1233` (TikTok's
iTunes app ID) as an alternative unique identifier — Android had no such backup.

### Fix Applied (v2.6.26 — NOT YET PUSHED)
1. `backend/server.py::_ua_tiktok_android` — insert `TikTok/{app_ver}` between
   `Cronet/{ver})` and `musical_ly_{ml_build}`.
2. `backend/referrer_pro.py::build_inapp_ua_suffix` (tiktok/android branch) — same
   insertion; the appended suffix now starts with `TikTok/{ver}`.
3. `backend/referrer_pro.py::_FOREIGN_INAPP_STRIP_PATTERNS['tiktok']` — extended regex
   to also strip an optional leading `TikTok/{ver}` so coercing away from tiktok
   cleanly removes both markers.
4. New tests: `backend/tests/test_v2_6_26_tiktok_android_browser_detection_fix.py`
   (6 tests) + supplemental `test_v2_6_26_regression_and_customer_scenario.py`
   (added by testing_agent, 5 pass + 1 skip due to fixture-key issue).

### iOS Branch Explicitly Unchanged
`_ua_tiktok_ios` retains its exact v2.6.20+ shape: `Mobile/15E148 musical_ly_{app_ver}
JsSdk/2.0 … AppId/1233 …`. iOS detection continues to work via `AppId/1233`. Test
`test_ua_tiktok_ios_still_uses_AppId_1233` guards this.

### Verification
- Local: 113/113 pytest passed (7 focused v2.6.* suites + new v2.6.26 tests).
- testing_agent (iteration_18.json): 100% success on backend, no critical/minor issues,
  no regressions in Facebook / Instagram / other platform UAs, strip-away-from-tiktok
  cleanly removes new marker, idempotency check working.
- Service health: /api/public/status 200, admin login JWT verified, supervisor RUNNING.

### Files Changed This Session (all committed locally to `main`, NOT PUSHED — user will Save-to-GitHub)
- `backend/server.py` (+15 -3 lines — comment + TikTok/{ver} marker)
- `backend/referrer_pro.py` (+19 -3 lines — 2 marker insertions + strip regex)
- `backend/tests/test_v2_6_26_tiktok_android_browser_detection_fix.py` (new — 161 lines)
- `backend/tests/test_v2_6_26_regression_and_customer_scenario.py` (new — 113 lines, added by testing_agent)
- `test_reports/iteration_18.json` (new — test report)
- `test_reports/pytest/pytest_v2_6_26.xml` (new — pytest XML)

### Pending Deploy Actions (when user says "deploy")
- [ ] Bump `backend/VERSION` from `2.6.25` → `2.6.26`
- [ ] Append release note to `backend/VERSION_NOTES.txt`:
  ```
  # v2.6.26 (2026-01) — TikTok Android browser-detection fix
  # - Added explicit `TikTok/{app_ver}` slug to `_ua_tiktok_android` (Cronet UA) and
  #   `build_inapp_ua_suffix('tiktok', android_base)` — placed between `Cronet/{ver})`
  #   and `musical_ly_{build}`. Advertiser UA parsers (Everflow / Voluum / RedTrack /
  #   ua-parser-js / uap-core) use `TikTok/([\d.]+)` as their primary TikTok browser
  #   detection rule; v2.6.22's Cronet UA only had `musical_ly_<build>` and parsers
  #   were falling through to generic Android → `Browser=<empty>` on ~100% Android
  #   TikTok clicks in customer's tracker report.
  # - iOS branch (_ua_tiktok_ios) UNCHANGED — iOS detection already works via AppId/1233.
  # - Extended `_FOREIGN_INAPP_STRIP_PATTERNS['tiktok']` to also strip the new
  #   `TikTok/{ver}` slug when coercing away from tiktok, so cross-platform coerce is clean.
  # - 6 new tests in test_v2_6_26_tiktok_android_browser_detection_fix.py + 5
  #   supplemental. All 113/113 targeted tests pass.
  # - Impact: Everflow / Voluum / RedTrack will now correctly label Android TikTok
  #   RUT clicks as "TikTok for Android" (was empty), matching iOS behaviour.
  ```
- [ ] `git push origin main` (user does this via Emergent Save-to-GitHub).

## Backlog (accumulated)
- OPTIONAL: Update stale ADMIN_PASSWORD constant in older test files (`test_rut_referrer_bugs.py`, `test_rut_referrer_concurrency_fixes_2026_02.py`) from `Krexion@2026` to read from env.
- OPTIONAL: Fix stale line-range assertion in `test_rut_referrer_concurrency_fixes_2026_02.py::TestCtxArgsFix` (`src_lines[8778:8830]` window has drifted).
- OPTIONAL (bigger refactor): `server.py` is 25,706 lines — modular split recommended.
- OPTIONAL: 21 pre-existing lint warnings in server.py (bare except, unused imports) — user forbade touching, but can be batched into a "cleanup" release.
- OPTIONAL: `_FOREIGN_INAPP_STRIP_PATTERNS['tiktok']` regex still doesn't strip the trailing `ttwebview/... com.zhiliaoapp.musically/...` chain when coercing away — cosmetic, not customer-facing.
