# Krexion — Product Requirements & Build Log

## Architecture
- **Cloud (VPS)**: FastAPI + React + MongoDB. Auto-deploys on every push.
- **Native Windows installer**: Inno-Setup ~571 MB. Triggers on backend/VERSION.
- **Electron Desktop**: Same backend on 127.0.0.1:8088 with KREXION_MODE=native.
  Auto-updates via electron-updater. Triggers on backend/VERSION.

## Iteration 1 — v2.1.38 (cross-platform browser-profile + in-app updater)
**Root cause:** commit 638d253 added browser-profile launch but didn't bump
VERSION, so Electron + Native builds never ran. Customers stuck on 2.1.37.
**Fix (commit 949f1c6):** VERSION bump + cloud-proxy for banners/version
endpoints + UpdateBanner in NativeShell + IPC bridge in Electron.

## Iteration 2 — v2.1.39 (hotfix: Electron startup crash)
**Bug:** v2.1.38 Electron crashed at startup with "ipcMain is not defined"
because the require('electron') destructure on line 21 of main.js never
included ipcMain (the search_replace silently dropped — only the IPC
handlers landed).
**Fix (commit bbadaae):** add ipcMain to the destructure.

## Iteration 3 — v2.1.40 (Browser Profiles visible + actually launches)
**Bugs:**
- Browser Profiles sidebar item was missing from NativeShell.js (Electron
  uses NativeShell, not DashboardLayout). User saw the cloud feature but
  no menu entry inside the desktop app.
- Even if the user navigated manually to /browser-profiles, the launch
  flow failed at runtime because the Electron installer shipped the
  Playwright Python package but never downloaded the Chromium binary.
  `prepare-resources.js` had `playwright` in the verify list but never
  ran `playwright install chromium`. Backend logged
  `Playwright chromium-headless-shell rev XXX missing` and every heavy
  feature (Browser Profile / RUT / Visual Recorder / automation) was
  silently broken.
**Fix (commit ceeef39):**
- `frontend/src/components/NativeShell.js`: import Globe lucide icon and
  add Browser Profiles to the Traffic Engine group (next to Real-User
  Traffic and Visual Recorder, matching DashboardLayout 1:1).
- `electron-desktop/scripts/prepare-resources.js`: new `prepareChromium()`
  invokes the embedded Python's `playwright install chromium
  chromium-headless-shell` and bundles them under
  `resources/krexion/chromium/`. Same approach as the Inno-Setup workflow.
- `electron-desktop/src/main.js` startBackend env: set
  `PLAYWRIGHT_BROWSERS_PATH` to `<resourcesRoot>/chromium` so the backend
  finds the bundled browser offline without falling back to
  `%USERPROFILE%\AppData\Local\ms-playwright` (empty on fresh install).
- `backend/VERSION` 2.1.39 → 2.1.40 to re-arm both build workflows.

**Outcome:** Installer size grew from 414 MB → 581 MB (Chromium adds
~167 MB). All 3 workflows green. desktop-v2.1.40 + v2.1.40 published.
- Cloud: `current=2.1.40` (https://krexion.com/api/system/public-latest).
- desktop-v2.1.40 latest.yml pushed to krexion.com/downloads/desktop/.
- Existing 2.1.39 Electron customers will be auto-upgraded on next launch
  via electron-updater.

## Iteration 9 — v2.1.47 (iOS in-app UA cleanup — Version/Safari token strip)
**Root cause:** v2.1.46 appended the in-app webview suffix at the END
of the UA but kept the `Version/<X.X>` and `Safari/<X.X.X>` tokens that
modern iOS Safari emits. UA parsers (HasOffers, CAKE, Affise, Voluum,
ua-parser-js, woothee, useragent-npm) scan left-to-right and stop at the
first known browser token they recognise — they hit `Safari/604.1` and
classified the click as **Safari**, ignoring everything after. So the
in-app suffix was technically present in the UA header but invisible to
tracker UIs and many fraud-detection layers.

Real iOS in-app captures (verified against `whatismybrowser` corpus
2026-06 + Apple's Safari 26 release notes) **drop** both tokens:
- `Version/<X.X>` — replaced by the app-specific version block
- `Safari/<X.X.X>` — never present in real in-app UAs
And keep the `Mobile/<build>` token between AppleWebKit and the marker
block.

**Fix:**
- `backend/referrer_pro.py` (coerce_ua_for_platform iOS branch): now
  strips `Version/<X.X>` AND `Safari/<X.X.X>` for ALL in-app platforms
  on iOS — `facebook` / `messenger` (was already there) PLUS `tiktok` /
  `instagram` / `snapchat` / `linkedin` / `twitter`. Ensures
  `Mobile/<build>` token exists (injects `Mobile/15E148` — the frozen
  iOS 26 default — if missing).

**Result:** iOS TikTok UA now reads identically to real captures:
```
Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15
(KHTML, like Gecko) Mobile/15E148 musical_ly_2033070000 JsSdk/1.0
NetType/5G AppName/musical_ly app_version/33.7.0 ByteLocale/en-CA
Region/US BytedanceWebview/d61a8b9
```
Tracker parsers scanning left-to-right now hit `musical_ly` before any
Safari/Version token → click is correctly attributed to the in-app
source AND fraud detectors see the full TikTok signature.

**Apple iOS 26 / Safari 26 context:** Apple shifted to year-aligned
versioning at WWDC 2025 (iOS 18 → iOS 26). Modern iOS Safari emits a
**frozen** `iPhone OS 18_6` in the parenthesised OS slot regardless of
actual iOS version (privacy by design — see Safari 26 release notes).
Device model tokens are also removed. So `Apple Unknown iOS iOS 26.3`
shown on the tracker for a v2.1.47 click is the CORRECT modern
iOS-Safari signature, not a parser failure — Apple deliberately hides
the device.

**Backward-compatibility:** Android branch unchanged. Desktop UAs still
untouched. iOS UAs with existing in-app markers still short-circuit via
the idempotency check.

## Iteration 8 — v2.1.46 (Anti-fraud: UA ↔ Referer consistency coercion)
**Root cause:** When the operator picked a Referer for an in-app platform
(Facebook / TikTok / Instagram / Snapchat / Messenger / LinkedIn / Twitter)
via `platform_pool` or `custom`/`random_list` but the rotating UA list
contained plain Chrome/Safari mobile UAs, the Referer↔UA combination did
NOT match real-world in-app webview signatures. Real mobile FB/TikTok ad
clicks always carry `[FB_IAB/FB4A;FBAV/…]` / `BytedanceWebview` /
`Instagram …` markers in the UA, so plain-Chrome + FB referer was a
fraud-detector hard signal (Anura / IPQS / Forensiq / Singular /
AppsFlyer Protect360 / Adjust / Forter all flag this combination).

**Fix:**
- `backend/referrer_pro.py`: added `build_inapp_ua_suffix(platform, ua)`,
  `coerce_ua_for_platform(ua, platform)`, `_is_mobile_ua`,
  `_ua_has_inapp_marker` + realistic version pools (FBAV, FBBV, FBRV,
  BytedanceWebview hash, IG/TikTok/Snapchat/LinkedIn versions, TikTok
  region+locale). Pure functions, never raise, idempotent, desktop UAs
  untouched.
- `backend/real_user_traffic.py`: new param
  `referer_match_ua_to_platform: bool = True` plumbed into `_referer_cfg`.
  Initial + retry paths in `process_one` worker call
  `coerce_ua_for_platform(ua, platform)` after `_resolve_visit_referer`.
- `backend/server.py`: Form field + persistence + engine call wiring.
  Default `.get(..., True)` so legacy jobs also get the safer default.
- `frontend/src/pages/RealUserTrafficPage.js`: new toggle "🛡️ Match UA
  to Referer" in the Pro-Mode realism panel (default ON).

**Backward-compatibility:** When override is disabled (legacy `auto`
mode), `_resolve_visit_referer` already returns the UA-derived referer
and the UA already carries the matching markers — so coerce is a no-op
via the idempotency check. Existing jobs see zero change.

## Released versions
- v2.1.47 (Native + Desktop) — iOS in-app UA cleanup (this iteration).
- v2.1.46 (Native + Desktop) — UA ↔ Referer consistency coercion.
- v2.1.40 — Browser Profile end-to-end across 3 surfaces.
- v2.1.39 — Browser Profile menu missing on desktop.
- v2.1.38 desktop — withdrawn (Electron startup crash).

## Backlog
- Cache the chromium-bundle in `electron-desktop/.cache/chromium/` and
  restore it via actions/cache to shave 5–10 min off each build.
- Expand workflow `paths:` to include `backend/**.py`,
  `electron-desktop/**`, and `frontend/src/components/NativeShell.js`
  so a forgotten VERSION bump can't strand desktop customers again.
- Add a pre-release smoke job that spawns the packaged Electron app with
  `--no-sandbox` for 5 s and checks the backend health endpoint, so a
  startup-crash regression never reaches `main` again.

## Test credentials
See `/app/memory/test_credentials.md`.
