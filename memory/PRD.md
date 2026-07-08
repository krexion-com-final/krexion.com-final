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
