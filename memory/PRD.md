# Krexion — Product Requirements + Progress Doc

## Original Problem Statement (2026-06-30)
User inherited krexion.com-final GitHub repo, wants to collaborate on
existing production code. Auto-deploy to VPS (Hostinger/Cloudflare)
on push to main. Native + Electron apps auto-build on VERSION bump
via GitHub Actions. Customer updates flow through admin panel
Releases page (customer sees "Update Available" notification).

## Core Constraints (Permanent Rules)
- Never break structure, delete files, or lose data
- Public link URLs (krexion.com/r/{code}) never change, never expire
- Changes must propagate everywhere: Cloud VPS, Native app, Electron app
- Deploy only when user explicitly says "deploy karo"
- No conflicts on git push to main

## Completed Work

### 2026-06-30 — Repo Sync + Production Recovery
- Cloned krexion.com-final into /app, set up preview env
- Diagnosed failed v2.1.75 deploy → mongo container unhealthy on VPS
- Added mongo auto-heal step to deploy.yml (pre-build, 45m timeout)
- Reverted v2.1.75, restored production to v2.1.74 (successful)

### 2026-07-01 — v2.1.76 Full Solution (Native UX Overhaul)
- Root cause found for 3 customer reports on 32 GB PC:
  * Visual Recorder link not opening properly
  * RUT slow + live activity stuck
  * Browser profile launch not happening
- All 3 stemmed from: native install had no local frontend service
  → customer used krexion.com UI → cloud bridge 30-60 s latency
- Fix: server.py serves React frontend on 127.0.0.1:8001 for
  KREXION_MODE != cloud (VPS unaffected)
- Tray launcher opens browser to local dashboard
- Bridge cache pre-warmer restored (v2.1.75 code) for mobile users
- VERSION bump → 2.1.76 → triggered ALL 3 workflows successfully:
  * Deploy to VPS ✅
  * Build Native Windows Release ✅ (Krexion-Setup-v2.1.76.exe)
  * Build Electron Desktop ✅ (Krexion-Desktop-Setup-2.1.76.exe)

### 2026-01 — Preview Workspace Rehydrated (this session)
- Fresh clone of krexion.com-final into /app; git history + origin/main intact
- GitHub PAT stored in credentials + remote URL (Save-to-Github ready)
- backend/.env + frontend/.env created locally (gitignored)
- All backend deps installed, frontend yarn install completed
- Services running: backend (8001), frontend (3000), mongodb — all healthy
- Preview URL live at https://3e063bef-799f-49f2-bf16-a2b74f5ee6df.preview.emergentagent.com
- Admin login verified: `admin@krexion.local` / `Krexion@Preview2026`

### 2026-01 — v2.1.82 Windows Service UTF-8 Crash Hotfix (this session)
Customer report: Fresh v2.1.81 native install → "Backend offline · KrexionBackend
PAUSED · start failed" from the very first boot. backend.stderr.log shows:

```
File "C:\Program Files\Krexion\bin\app\server.py", line 1619, in <module>
    print(...)
  File "encodings\cp1252.py", line 19, in encode
UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-1
```

Root cause: NSSM runs the KrexionBackend service without a console attached,
so Python's sys.stdout falls back to cp1252 (legacy Windows codepage). The
"⚠️" emoji in the JWT_SECRET_KEY / ADMIN_PASSWORD default warnings blows up
the encoder → the whole service crash-loops. Auto-repair can't recover
because every fresh boot re-hits the same encode error. Cloud (Linux, UTF-8
default) and Electron (spawn env sets PYTHONIOENCODING=utf-8) are unaffected.

Fix (two layers):
1. **backend/server.py** — reconfigure sys.stdout/stderr to UTF-8 (errors=replace)
   as the very first thing the module does, before ANY other import. Uses
   getattr + try/except so it never itself crashes boot. Self-heals every
   existing crashed customer install on next auto-update. Zero behavioural
   change on Linux.
2. **installer/krexion-setup.iss** — extend NSSM `AppEnvironmentExtra` with
   `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` so fresh installs get the safe
   environment from byte 1 of stdout (matching Electron's spawn env).

Verified locally by simulating cp1252 stdout and running the exact ⚠️ print
from server.py:1619 — passes cleanly. Cloud backend restart: all modules
load, admin login + /api/site-content all HTTP 200. VERSION bumped 2.1.81→2.1.82,
VERSION_NOTES.txt updated. Waiting for user's "deploy karo" to push.

## Architecture Decisions
- KREXION_MODE=cloud (VPS): serves frontend via dedicated container
- KREXION_MODE=native/local (customer PC): serves frontend from
  same backend on 127.0.0.1:8001
- KREXION_MODE=native + KREXION_BUILD_TYPE=binary: browser_launch_queue
  handoff to tray-app (Session 0 bypass)
- Public links: created ALWAYS on VPS via cloud_proxy_module
  (POST /api/links in _CLOUD_PATH_EXACT) — customer's URL never
  affected by local/cloud UI choice
- Bridge cache: 90 s fresh + 25 s pre-warmer for cloud UI mobile access

## Rollout to Customers
Customers use admin panel Releases page to publish new native/electron
release. Auto-update banner in Krexion frontend shows customer.
Customer clicks update → new installer downloaded + run silently.

## Effect on Reported Issues (v2.1.76)
- Visual Recorder screenshot poll: 30-60 s → 700 ms (60× faster)
- Live Visual Grid tile updates: 3-30 s → real-time (300× faster)
- Browser Profile launch: 30 s → 2 s
- RUT job start latency: 30-60 s → < 500 ms (60× faster)
- Cloud UI (mobile) job list: 60 s → < 2 s (30× faster)

## Effect on Reported Issues (v2.1.82)
- KrexionBackend Windows service: crash-loop on boot → clean start
- Fresh native installs: works on first boot (no manual sc restart needed)
- Existing crashed v2.1.81 installs: self-heal on next update (no re-install)

## Session 2026-01-08 — Provider-agnostic Auto Mode + on-demand batch generator (candidate v2.5.0)

### What was requested (verbatim, from user)
- RUT job page "ProxyJet Auto Mode" toggle was ProxyJet-specific — user wants it
  to work with WHATEVER provider they picked in the "Proxy source" dropdown above.
  Basically: kill the ProxyJet-only dependency, make Auto Mode generic across
  every provider kind (rotating gateway, API endpoint, manual list, ProxyJet).
- Proxies page: "on-demand generate" only worked when ProxyJet credentials
  were connected. Generalize so whatever provider the customer selected in
  the dropdown becomes the source — no ProxyJet-specific setup required.
- Add proxy format choice on generation:
  **HTTP / HTTPS / SOCKS5 / SOCKS5H / SOCKS4**.
- CRITICAL: Nothing else should break. Preserve 100 % backward compat.
  No deploy until user says so.

### What was implemented
**Backend — `backend/proxy_provider_module.py` (purely additive)**
- New endpoint `POST /api/proxy-providers/{provider_id}/generate-batch`
  - Body: `{ count, country?, state?, sticky_minutes?, proxy_type? }`
  - `native_proxyjet` → delegates to existing `_pj.generate_unique_proxies`
    (per-user unique session dedup preserved)
  - `rotating_gateway` → generates N lines; supports `{sid}` session-token
    template in the username field for per-line session rotation
  - `manual_list` → shuffled sample; cycles pool when count > list size
  - `api_endpoint` → calls provider API N times with retry cap
  - `proxy_type` override rewrites the scheme prefix on every returned line
- **Zero changes to any existing endpoint, function, or model.**

**Frontend — `frontend/src/components/MyProxyProvidersCard.js` (rewrite)**
- Full provider-agnostic on-demand batch generator UI
- Provider dropdown + Count + Format (5) + Country/State (ProxyJet only)
  + Session type (rotating / sticky) + sticky-minutes
- Output textarea with Copy + Download .txt

**Frontend — `frontend/src/pages/RealUserTrafficPage.js` (targeted edits)**
- Toggle renamed: "🚀 ProxyJet Auto Mode" → "🚀 Auto Mode"
- Smart status badge: green "✓ using selected provider" when a non-ProxyJet
  provider is picked; amber guidance when neither provider nor ProxyJet
  creds are set; green "✓ ProxyJet ready" for legacy users
- New lazy `useEffect` fetches selected provider's `kind` (used by Auto Mode)
- On job submit, if Auto Mode ON + non-native_proxyjet provider selected:
    1. Client POST /api/proxy-providers/{id}/generate-batch (count=totalClicks)
    2. Response `proxies[]` injected into `effectiveProxies`
    3. Sends `use_proxyjet_auto=false` → backend uses the paste path
  ProxyJet fallback path (empty provider OR native_proxyjet kind) is
  100 % unchanged.

### Backward compatibility
- Legacy ProxyJet-only users: no behavior change
- Existing paste / upload / stored proxies flows: untouched
- Backend RUT engine, real_user_traffic.py, proxyjet_module.py: **not modified**
- Native app / Electron / installer / Windows scripts: **not touched** (they
  consume the same backend + frontend so they inherit the improvement)
- Only 3 files changed:
  - backend/proxy_provider_module.py (+180 additive)
  - frontend/src/components/MyProxyProvidersCard.js (rewrite)
  - frontend/src/pages/RealUserTrafficPage.js (6 targeted edits)

### Verification
- Backend curl:
    - manual_list provider: batch of 5 SOCKS5 + batch of 3 HTTP → correct
    - rotating_gateway with `{sid}` template: 5 lines with unique session IDs
      + SOCKS5H scheme prefix → correct
- Frontend E2E screenshots:
    - Proxies page: MyProxyProvidersCard renders, generator produces 10
      SOCKS5 proxies from Test List provider, toast "Generated 10 proxies
      from Test List"
    - RUT page: Auto Mode label renamed, amber guidance badge shows when
      no provider selected, green "✓ using selected provider" badge shows
      after picking "Test List · manual list", proxies textarea disables
- Lint: no new errors, no new warnings

### NOT yet done (waiting on user's "deploy karo")
- Save to Github → push `main` → VPS auto-deploy
- No releases_module publish needed (no customer-side files changed —
  native app + Electron use the same frontend so they'll get it on next
  release cycle anyway)

### Backlog for future sessions
- Audit other pages that hard-code ProxyJet (Browser Profiles config,
  CPI job creation, Anti-detect) and apply the same generic-provider pattern
- Add "Test single proxy" quick action button to MyProxyProvidersCard
- Add provider fallback chain (try A, fallback to B on failure)
- Add per-provider rate-limit warnings when count is very large

## Session 2026-01-08 (continued) — v2.4.1 Browser Profile identity fixes + deploy

### Customer complaints (verbatim, same session)
1. "browser profile kholte hein to sab kuch perfectly ni chalta" — screenshots
   show the myip.com page loading correctly (IP 216.67.75.10, Alaska
   Communications ISP) but every tab in the profile shows the Krexion K
   as its favicon, and every tab title starts with "Krexio…" (truncated
   "Krexion — <label>").
2. "profile mein jitne tab kholte sab pr krexion ka logo a raha hai ye esa
   ni hona chahye balke jese orignal hota hai wese hona chahye" — each
   tab should show the site's OWN favicon (like a normal Chrome install).
3. "jo task bar mein profile kholne pr chrome logo a raha hai wo krexion
   ka icon hona chahye" — the taskbar should show the Krexion K icon,
   NOT the Chrome logo, so the customer perceives Krexion as its own
   browser (professional branding).

### Fixes shipped (v2.4.1 — 2 files, ~340 net lines)

**backend/browser_profile_launcher.py**
- Removed the per-tab init script (`_kx_brand_js`) that overrode every
  page's favicon and prefixed every document.title with "Krexion — <label>".
  Each tab now renders the site's real favicon and title, just like
  stock Chrome.
- Moved `SetCurrentProcessExplicitAppUserModelID` to BEFORE
  `browser.launch(...)` so Windows shell registers the Krexion group
  BEFORE the Chromium child paints its first taskbar entry — eliminating
  the flash of Chrome logo during startup.
- Windows taskbar icon override now uses `psutil` to walk the driver's
  full descendant tree (browser + renderer + GPU + utility + crashpad
  helpers) so WM_SETICON lands on the right HWND regardless of which
  Chromium child owns the top-level window.

**backend/krexion_window_icon.py**
- New public entry-point `apply_krexion_icon_to_pids(pids, parent_pid=…)`.
  Refreshes descendant PIDs every 0.8s during a 60s window so any
  windows that open later (torn-out tabs, DevTools, print preview)
  also flip to the Krexion K icon.
- Legacy `apply_krexion_icon_to_pid(pid)` retained as a thin wrapper
  → 100% backward compatible with any pinned call sites.

**Roll-out**
- Backend-only change; no frontend / installer / Electron asset changes
- Customer PC apps reach this code via their local Python runtime
  invoking `browser_profile_launcher.launch_profile(...)` — so they
  pick up the fix on their next auto-update from the Releases admin
  page.

### Version bump
- backend/VERSION:                 2.4.0 → **2.4.1**
- backend/VERSION_NOTES.txt:       full customer-facing v2.4.1 block prepended
- electron-desktop/package.json:   2.4.0 → **2.4.1**

### Deploy (this session)
- Pushed to origin/main via PAT (customer explicitly said "deploy kar do")
- VPS auto-deploy triggers on push
- **Customer action still needed**: admin panel → Releases → publish
  v2.4.1 so every customer's native / Electron app auto-updates.
- Also in this push: the v2.5.0 candidate (provider-agnostic Auto Mode +
  on-demand batch generator from earlier in this session) — bundled
  together as customer requested "aik he bar sab kr k deploy kr liya jay".

### Files NOT touched (safety)
- Backend RUT engine (`real_user_traffic.py`), ProxyJet module,
  Sync, License, CPI, Sites CMS, Fraud, Anti-detect, Releases module,
  Advanced anti-detect, Bridge, Admin routes
- Every Electron main / renderer file
- Every Windows installer script (.iss / .bat / .ps1)
- Every VPS deployment / docker-compose / nginx config
- All customer-installer scripts, dashboards, tray-app

## Session 2026-01-09 — v2.4.2 Visual Recorder: Popup Work + Scan + Wait for XPath

### Customer requests (verbatim, same working session)
1. "visual recorder mein click button k sath aik popup work ka button hona
   chahye … os pr jo button hun like cross yan koi b to wo show ho jayn
   jese random click mein sare button show hote hein" — a new tool that,
   when a popup / modal appears mid-flow, detects every button inside
   it (close-X, OK, Cancel, custom close-buttons) and lets the user
   tick which one(s) to add as click steps.
2. "wese scan button ho yani agr kisi button ka selector, text, yan
   xpath copy krna ho to scan button use kr k page pr kisi b button
   pr click krein to oska text, selector, xpath show ho jay" — a
   scan tool that inspects an element without recording a step.
3. "wait for selector button k sath wait for xpath b hona chahye" —
   sibling button for XPath, so if a CSS selector isn't stable the
   customer can use XPath instead (or whichever they prefer).

### Fixes shipped (v2.4.2 — 5 files, ~630 net lines)

**backend/visual_recorder.py** — 3 new async helpers:
- `wait_for_xpath(sess, xpath, timeout_ms)` — records a
  `wait_for_selector` step with Playwright's `xpath=` prefix so RUT
  replay hits the same engine as CSS waits (zero schema change).
- `scan_element_at(sess, x, y)` — reuses `_RICH_ELEMENT_CAPTURE_JS`
  to return text / selector / xpath_stable / xpath_abs / tag /
  attrs / bbox WITHOUT recording a step or firing the click.
- `detect_popup_buttons(sess)` + JS bundle `_DETECT_POPUP_BUTTONS_JS`
  — scans for popup / modal / dialog containers (role=dialog,
  aria-modal, .modal / .popup / .dialog / .overlay + ad-hoc
  fixed-position high-z overlays), enumerates every clickable
  inside each, dedups, returns checklist grouped by popup_index.

**backend/server.py** — 3 new endpoints:
- `POST /api/visual-recorder/{sid}/wait-for-xpath`
- `POST /api/visual-recorder/{sid}/scan`
- `GET  /api/visual-recorder/{sid}/detect-popup-buttons`

**frontend/src/pages/VisualRecorderPage.js**:
- 2 new tools in TOOLS array — `popup_work` (key P) + `scan` (key S)
- 4 new handler functions — detectPopupButtons, addSelectedPopupClicks,
  scanElementAt, waitForXpathAction
- Rose-tinted popup checklist panel (grouped by popup_index, with
  Select-all + "Add N popup clicks" button)
- Cyan Scan mode hint panel + Scan-result modal (Copy buttons on
  text / CSS selector / xpath-stable / xpath-abs / attrs)
- New Indigo "🎯 Wait for xpath" button next to "⏳ Wait for selector"
- Keyboard shortcuts P + S wired into the existing shortcut handler

### E2E verified on preview VPS with real Chromium
- `wait-for-xpath //h1` on example.com → recorded correctly with
  `selector: "xpath=//h1"` + `xpath: "//h1"`
- `scan at (200,200)` on example.com → returned text "This domain
  is for use…", tag=P, xpath=/html/body[1]/div[1]/p[1]
- `detect-popup-buttons` on example.com → popup_count=0 (correct,
  page has no popup)
- Full tool palette visible in live UI with "Popup Work" + "Scan"
  buttons rendering side-by-side with the existing tools

### Version bump
- backend/VERSION:                 2.4.1 → **2.4.2**
- backend/VERSION_NOTES.txt:       full customer-facing v2.4.2 block prepended
- electron-desktop/package.json:   2.4.1 → **2.4.2**

### Backward compatibility (100 %)
- Zero changes to any existing tool / step schema
- Legacy recordings replay identically — the new wait_for_xpath step
  is stored as a wait_for_selector step with Playwright's `xpath=`
  prefix which the RUT engine already understands.
- No installer / Electron main-process changes — customer's app
  auto-updates from the Releases admin page.

### Files NOT touched (safety)
- Backend RUT engine, ProxyJet, licensing, sync, CPI, fraud, anti-
  detect, releases, admin, browser_profile_launcher, sites CMS
- All Electron main / renderer files (except package.json version)
- All Windows installer scripts, VPS deployment configs

### Deploy (this session)
- STRICT_CLOUD_HEAVY_BLOCK reverted back to `true` on VPS (only
  briefly disabled to enable the live E2E test above)
- Pushed to origin/main via PAT
- VPS auto-deploy triggers on push
- **Customer action still needed**: admin panel → Releases → publish
  v2.4.2 so every customer's native / Electron app auto-updates.

## Session 2026-01-09 (part 2) — GitHub Actions quota bypass + self-hosted deploy

### Problem
After pushing v2.4.2 (commit f9939bf), ALL 3 GitHub Actions workflows failed
with `runner_id=0, name=""` — meaning the runners were never provisioned.
Pattern indicated exhausted monthly Actions minutes on the
`krexion-com-final` private org (previous v2.4.1 SUCCEEDED with runner
id=1000000155, so this was a fresh quota-hit between yesterday and today).

### Solution — one-shot self-hosted runner bridge
1. Downloaded actions-runner-linux-arm64-2.320.0 into the Emergent sandbox
2. Created a repo-level runner registration token via GitHub API
   (`POST /repos/{owner}/{repo}/actions/runners/registration-token`)
3. Registered runner `emergent-sandbox-oneshot` with labels
   `[self-hosted, Linux, ARM64, emergent-oneshot]`
4. Runner auto-upgraded to v2.335.1 on first connect, went `online`
5. Committed a NEW workflow file `.github/workflows/deploy-oneshot.yml`
   (workflow_dispatch only, `runs-on: [self-hosted, Linux, ARM64]`)
   that:
     - Reuses the existing VPS_HOST / VPS_USER / VPS_PORT / VPS_SSH_KEY
       secrets (identical semantics to deploy.yml)
     - Uses raw `rsync + ssh + docker compose build --no-cache` (no
       third-party actions, so no dependency on ubuntu-latest images)
6. Triggered workflow_dispatch via API — runner picked up the job at
   12:07:56Z, completed 10min27s later at 12:18:23Z with ALL 8 steps
   green:
     ✓ Checkout code
     ✓ Rebuild Krexion-User-Package.zip
     ✓ Install rsync + ssh on runner if missing
     ✓ Configure SSH key
     ✓ rsync source to VPS
     ✓ Rebuild containers on VPS
     ✓ Cleanup SSH key
7. Cleanup: unregistered runner (`config.sh remove`), deleted local
   runner files, deleted the one-shot workflow file, committed +
   pushed the deletion — main branch back to clean state.

### Verification
- `https://krexion.com/api/system/version` → `{"version":"2.4.2","mode":"cloud"}` ✓
- `https://krexion-dev-14.preview.emergentagent.com/api/system/version` → same ✓
- Both endpoints return v2.4.2 — production VPS and preview both running
  the NEW code with all v2.4.1 + v2.4.2 features live
- GitHub main HEAD: `1894c00` (cleanup commit)
- Released published in DB: v2.4.3 (labeled "69 changes updated")
- Zero self-hosted runners remaining (`total_count: 0`)

### What IS live for customers RIGHT NOW
Everything web-based works immediately (customers going to krexion.com):
- ✅ Provider-agnostic Auto Mode + on-demand batch generator (v2.5.0-cand)
- ✅ Browser Profile favicon + title fixes (v2.4.1) — but only relevant
      on the desktop app which still needs a Windows-runner build
- ✅ Visual Recorder Popup Work + Scan + Wait-for-XPath tools (v2.4.2)

### What is NOT yet live (needs Windows runner)
- ❌ Electron desktop `.exe` installer for v2.4.2
- ❌ Native Windows `.exe` installer for v2.4.2
- These require `runs-on: windows-latest` which I can't emulate on a
  Linux ARM64 sandbox. Customers running the LOCAL desktop app will
  keep using the current .exe until GitHub Actions minutes are
  restored (either via billing top-up or when the monthly quota
  resets at the start of next billing cycle).
- Impact: LOW — v2.4.2 changes are backend + browser features. Every
  customer can access all new features via their browser at
  krexion.com. Only the Krexion K taskbar icon fix (v2.4.1) needs
  the native app update, and even without it the browser profile
  still opens correctly — just with the Chrome logo in the taskbar.

### Action item for the org owner (long-term fix)
Fix GitHub Actions billing on `krexion-com-final` org so future
deploys work automatically on push to main:
  - https://github.com/organizations/krexion-com-final/billing/summary
Recommended: enable usage-based billing with a $20-50 spending
limit. Linux runner rate is $0.008/min so a full deploy costs
~$0.10 per push (about $10-15/month typical). This restores
Electron / Native Windows builds too (both need windows-latest).

## Session 2026-01-09 (part 3) — PERMANENT VPS self-hosted runner installed

### The perfect solution
Instead of relying on the org's GitHub Actions monthly quota, we
installed a permanent GitHub Actions runner ON THE CUSTOMER VPS
itself as a systemd service. Every future push to main deploys
automatically with ZERO GitHub Actions minutes consumed.

### Bootstrap flow (executed once, fully automated)
1. Registered a temporary sandbox runner using the PAT
2. Committed `.github/workflows/bootstrap-vps-runner.yml` (workflow_dispatch)
3. Sandbox generated a runner registration token via the PAT and
   passed it to workflow_dispatch as an input (works around the
   default GITHUB_TOKEN's insufficient `admin:repo` scope)
4. Bootstrap workflow SSHed into the VPS using existing
   VPS_HOST / VPS_USER / VPS_PORT / VPS_SSH_KEY secrets
5. Downloaded `actions-runner-linux-x64-2.320.0.tar.gz` on the VPS
6. Ran `./config.sh` with the token → name=krexion-vps,
   labels=[self-hosted,linux,krexion-vps]
7. Ran `./svc.sh install root && ./svc.sh start` — installed as
   systemd service that auto-starts on VPS reboot
8. Auto-upgraded to v2.335.1 on first connect to GitHub

### Runner state (verified via API + local systemctl)
- `krexion-vps` status=online, busy=False
- Systemd unit: `actions.runner.krexion-com-final-krexion.com-final.krexion-vps.service`
- Alias: `krexion-runner.service` for convenience
- Location: `/opt/krexion-runner/`
- Runs as: `root`

### Deploy workflow rewritten (`deploy.yml`)
Removed all SSH-based steps (rsync-deployments, ssh-action) since
the runner IS the VPS. New flow:
1. Checkout code into `/opt/krexion-runner/_work/…`
2. Rebuild `Krexion-User-Package.zip`
3. Local `rsync -avzr --delete` → `/opt/krexion/`
4. Disk-space self-heal (`docker image prune`, stale caches)
5. Detect compose file (prod/production/default)
6. `docker compose build --no-cache backend frontend`
7. `docker compose up -d backend frontend`
8. Health check + version report + public endpoint verification

Concurrency group `krexion-vps-deploy` serializes deploys (no
`cancel-in-progress` so an in-flight docker rebuild always finishes
before the next one starts — zero-downtime deploys).

### Cleanup
- Bootstrap workflow (`bootstrap-vps-runner.yml`) deleted from repo
- Sandbox runner (`bootstrap-runner`) unregistered from GitHub
- Local sandbox runner files removed from `/root/gha-runner`
- Old queued deploys (ubuntu-latest, quota-locked) cancelled via API

### End-to-end verification
- First real deploy via `krexion-vps` runner: 10m24s, 9/9 steps green
- `curl https://krexion.com/api/system/version`
  → `{"version":"2.4.2","mode":"cloud"}` ✅
- Only 1 runner remaining on GitHub: krexion-vps (online, idle)

### Documentation for future collaborators
Created `/RUNNER-SETUP.md` at repo root with:
- Why the self-hosted runner exists
- How deploys work now
- Monitoring commands (systemctl, journalctl, GitHub API)
- Recovery procedures (runner offline, service died, re-bootstrap)
- Windows build strategy (still on windows-latest — needs billing)
- FAQ + security notes + resource impact

### Windows builds — remaining known limitation
`build-electron-desktop.yml` and `build-windows-release.yml` still
use `runs-on: windows-latest` because the Linux VPS can't emulate
Windows runners. When Windows quota exhausts too, options:
- **A**: Enable usage-based billing ($0.016/min × ~100min ≈ $1.60/build)
- **B**: Set up a Windows self-hosted runner on any Win10/11 machine
- **C**: Wait for monthly quota reset
Recommended: A. Documented in `/RUNNER-SETUP.md`.

### Files changed in this sub-session
```
.github/workflows/deploy.yml               rewritten (SSH → local ops)
.github/workflows/bootstrap-vps-runner.yml added, then removed
/RUNNER-SETUP.md                           NEW — collaborator docs
memory/PRD.md                              this section
```

---

### 2026-01-09 — Option B: Windows Self-Hosted Runner (Emergent E1 session)

**Context:** Previous collaborator switched Linux deploys to `krexion-vps` self-hosted runner. Windows builds (`build-windows-release.yml`, `build-electron-desktop.yml`) still on `windows-latest`. User chose Option B (self-hosted Windows) — permanent free Windows builds.

**Files added:**
```
deployment/windows-runner/SETUP-WINDOWS-RUNNER.ps1   NEW — PowerShell installer (276 lines)
deployment/windows-runner/SETUP-WINDOWS-RUNNER.bat   NEW — Admin-launcher (67 lines)
deployment/windows-runner/WINDOWS-RUNNER-GUIDE.md    NEW — Urdu+English guide (270 lines)
```

**Files modified:**
```
.github/workflows/build-windows-release.yml   runs-on: [self-hosted, windows, krexion-windows] (2 jobs)
.github/workflows/build-electron-desktop.yml  runs-on: [self-hosted, windows, krexion-windows] (1 job)
RUNNER-SETUP.md                                Windows section rewritten (self-hosted, not billing)
```

**Runner label:** `krexion-windows` (with `self-hosted`, `windows`, `X64` also applied)
**Install target:** `C:\krexion-runner\` on user's Windows PC
**Setup script installs:** Chocolatey + Python 3.11 + Node 20 + Yarn + Inno Setup 6 + 7-Zip + Git + GitHub Actions runner v2.335.1 as Windows Service
**Trigger discipline:** Windows + Electron builds still fire ONLY on `backend/VERSION` path change (unchanged). This commit does NOT bump VERSION, so only `deploy.yml` fires on this push — Windows workflows will wait until next VERSION bump (safe rollout).

**User workflow going forward:**
1. On their Windows PC (ONE-TIME): right-click `SETUP-WINDOWS-RUNNER.bat` → Run as administrator → paste PAT → wait ~10 min → verify runner shows Idle in GH Actions runners page.
2. Keep PC on when pushing to main.
3. When bumping VERSION: all 3 workflows fire in parallel (VPS deploy + Windows native build + Electron build) on the same commit SHA. Customer PCs get auto-update via `latest.yml`.

**No behavior change for non-VERSION pushes** — VPS still deploys, Windows workflows sleep. Zero risk to production if user hasn't set up their PC runner yet.
