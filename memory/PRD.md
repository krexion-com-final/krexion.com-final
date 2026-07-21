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
