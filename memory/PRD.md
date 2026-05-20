# Krexion — PRD / Project Memory

## Source
- **GitHub**: https://github.com/krexion/krexion.com (owner: user)
- Cloned into `/app/` on 2026-05-15. Git remote `origin` configured, branch `main`.

## Stack
- **Backend**: FastAPI 0.115 + Motor + Playwright 1.49 (Python 3.11)
- **Frontend**: React 18 + CRA + Tailwind + shadcn-ui
- **DB**: MongoDB 7

## Default Credentials (dev)
- Admin: `admin@krexion.local` / `admin123` (login at `/admin`)
- Test User: `testuser1@gmail.com` / `Test12345`

---

## Implemented changes (2026-05-15)

### Bug fix #1 — Delete button blocked after bulk test
- **Root cause**: `testAllProxies` was auto-opening the "Bulk Test Results Summary" dialog. The dialog's full-screen backdrop (`fixed inset-0 z-50 bg-black/80`) intercepted pointer events on the proxy table, blocking delete/test buttons.
- **Fix**: Removed auto-open (`setShowBulkTestSummary(true)` commented out). Toast now informs user; summary still computed and stored.
- **Added**: "View Last Summary" outline button (blue) appears in action bar whenever `bulkTestResults` is available and no bulk test is running. User clicks manually to view the summary modal.
- **Verified end-to-end** via playwright: 5 → 4 rows after one delete; no force-click needed; `Dialogs open after bulk test: 0`.

### Backend (`backend/server.py`)
1. **Enriched `DEFAULT_API_SETTINGS`** with per-API:
   - `tier` (`free` / `paid`)
   - `signup_url` (where to get the key)
   - Long `description` ("What it does: ... Free tier: X. Paid: $Y")
2. **Auto-disable cascade** in `PUT /api/admin/api-settings/{key}`:
   - When admin enables a `paid` API that has an API key, all `free` tier APIs are automatically disabled (`auto_disabled_by` field stores which paid API triggered it).
   - Response now returns `all_settings` + `auto_disabled` list.
3. **Live bulk-test progress**:
   - In-memory `_bulk_test_progress` dict keyed by user id.
   - `POST /api/proxies/bulk-test` now updates `parallel_active`, `checked`, `total`, `alive`, `dead`, `duplicate`, `elapsed_seconds` in real time.
   - **NEW**: `GET /api/proxies/test-progress` returns the live snapshot (polled every 500 ms by frontend).

### Frontend Admin (`AdminDashboard.js` API Settings tab)
- Per-API card now shows: FREE/PAID badge, `Get API key ↗` link, expanded description.
- Auto-disabled state surfaced with a clear yellow notice.
- Toggle visual feedback (disabled while paid is active).
- Updated `handleApiSettingChange` to apply server-returned cascade.
- Two new info blocks at bottom:
  - "How VPN Detection Works (Auto-Fallback)" (5-step)
  - "How to add a Paid API (Step by Step)" (6-step guide with provider links).

### Frontend User (`ProxiesPage.js`)
- **Removed**: "Check My IP" button, dialog, related state (`myIpData`, `userRealIps`, `checkingMyIp`, `showMyIpDialog`, `checkMyIp` fn).
- **Removed**: "Your Real IPs" warning + IPv4/IPv6 rows inside bulk-test summary.
- **Added**: `progress` state + 500ms polling effect calling `/api/proxies/test-progress` while `isBulkTesting === true`.
- **Added**: full-width purple-gradient "System Processing" card during bulk test, showing:
  - Animated spinner + percent badge
  - PARALLEL ACTIVE / CHECKED (X/Total) / TIME ELAPSED (s)
  - Bottom strip with live Alive / Dead / Duplicate counters
  - Top gradient progress bar bound to `percent`

---

## Verified
- ✅ Backend health: `{status:ok, mongo_connected:true}`
- ✅ Admin login: token issued
- ✅ Auto-disable cascade: tested with `iphub` paid key → free APIs auto-disabled
- ✅ Progress endpoint: returns idle / running snapshots correctly
- ✅ Bulk test live UI: rendered with 12% / 7 parallel / 1 checked / 0.5s elapsed (screenshot captured)

## Not changed
- All existing batch test logic / parallel concurrency (50–100/batch, asyncio.gather)
- All other endpoints, modules (CPI, RUT, links, clicks, form-filler) untouched
- Original repo structure preserved (415 files match)

## Backlog / Future
- Add custom-API endpoint test before save
- Per-user progress isolation already done; consider per-session-id for multi-tab UX
- Surface auto-disabled state in `/api/admin/api-settings/status` summary card


---

## 2026-05-15 (later) — Public Landing + Crypto Frontend + Resend

### Added
- **Public Landing Page** (`/app/frontend/src/pages/HomePage.js`) — new route at `/` with hero, 6 feature cards, live pricing pulled from `/api/crypto/plans`, FAQ accordion, payment-flow walkthrough, CTA strip. Logged-in users get auto-redirected to `/dashboard`.
- **Resend Email Integration** — `/app/backend/email_service.py` (new) provides `send_welcome_email`, `send_license_email`, `send_rejection_email`. Wired via dispatcher in `server.py` → `crypto_payment_module._send_email`. HTML templates use brand colors (#A78BFA on dark). Non-blocking via `asyncio.to_thread`. Env keys: `RESEND_API_KEY`, `SENDER_EMAIL`, `SUPPORT_EMAIL`.
- **Crypto checkout customer emails** on order create (welcome), approve (license key delivery), reject (with reason).
- **Customer installer (`Krexion-User-Package/INSTALL.bat`, `README.txt`)** — post-install messages updated to direct users to `https://krexion.com/pricing` to purchase a license via USDT-TRC20 (no more "ask admin on WhatsApp").

### Changed
- Routing: `/` is now public HomePage. Dashboard moved to `/dashboard`. Updated `App.js`, `LoginPage.js` (post-login → `/dashboard`), `DashboardLayout.js` (sidebar Dashboard link), and `FeatureRoute` fallbacks.
- `CryptoOrdersPage.js` — testing agent hot-fixed admin token localStorage key mismatch (now reads `adminToken` → `admin_token` → `token` fallback).

### Deployed (Production VPS — krexion.com)
- rsync’d backend (`email_service.py`, `crypto_payment_module.py`, `server.py`) + frontend (`App.js`, `HomePage.js`, `LoginPage.js`, `PricingPage.js`, `CheckoutPage.js`, `OrderStatusPage.js`, `CryptoOrdersPage.js`, `DashboardLayout.js`) + installer files to `/opt/krexion/`.
- Appended `RESEND_API_KEY`/`SENDER_EMAIL`/`SUPPORT_EMAIL` to `/opt/krexion/backend/.env`.
- `docker compose up -d --build backend frontend` — both containers rebuilt and running healthy.
- Verified: `https://krexion.com/api/crypto/plans` returns 4 plans; `https://krexion.com/` renders new HomePage; backend log: `Resend email service enabled`.

### Tested
- Backend: 14/14 pytest pass — `/app/backend/tests/test_iteration7_crypto_payment.py` (plans, orders, TxID, admin approve/reject, license KRX format, dup TxID 409, admin auth gate).
- Email: live Resend send to `us9661626@gmail.com` returned real Resend id (verified inbox). Sandbox restriction: only verified address receives mail — verify a domain at `resend.com/domains` and update `SENDER_EMAIL` to unlock all customers.
- Frontend: HomePage + Pricing + Checkout + OrderStatus + Admin Crypto Orders flows all green.

### Backlog (next)
- **P0**: Verify `krexion.com` (or sub-domain `mail.krexion.com`) on Resend dashboard, then change `SENDER_EMAIL=Krexion <noreply@krexion.com>` so customer emails actually deliver to non-verified addresses. Until then only `us9661626@gmail.com` receives test mail.
- **P1**: Add license-key entry step inside the local register flow on installed customer instances (currently they create an account locally but the license isn't bound to their email yet).
- **P1**: Expose a public `/download` page that serves the latest `Krexion-User-Package.zip`.
- **P2**: Standardize admin-token localStorage key project-wide (one helper `getAdminToken()`).
- **P2**: Add "Resend License Email" button to admin Crypto Orders panel.
- **P2**: License expiry reminder cron (7d / 1d before expires) using `send_email`.
- **P3**: Replace inline FAQ with markdown-driven content; add testimonials section once we have real users.


---

## 2026-05-16 — Selling-Ready (Phase B)

### Added (this session)
- **White-label installer** (`Krexion-User-Package/install-master.ps1`)
  - New `Set-DockerHidden` function — writes Docker Desktop `settings.json` with `openUIOnStartupDisabled=true`, disables tutorial / analytics / notifications, removes Docker Desktop desktop + Start Menu shortcuts.
  - `Start-DockerSilent` now uses `-WindowStyle Hidden`.
  - User-facing strings rebranded: "Docker Desktop" → "Krexion runtime"; "WSL kernel" → "System engine"; failure messages link to `https://krexion.com/support`.
  - Desktop shortcut + auto-open URL changed from `/register` → `/login` (customers use credentials from welcome email).
- **Auto-account creation on crypto approve** (`server.py:_crypto_create_customer_account`) — when admin approves a paid order, if no krexion.com user exists, backend creates one with random 12-char password, status=active, ALL features enabled, generous quotas.
- **License email upgraded** — embeds login credentials (email + password) in a green-bordered block when account is newly created + login link to `https://krexion.com/login`.
- **Public `/download` page** (`frontend/src/pages/DownloadPage.js`) — hero, system req grid, 4-step install guide, SHA-256 integrity hash with copy button, FAQ. Serves `/Krexion-User-Package.zip`.
- **Installer ZIP** packaged at `/app/frontend/public/Krexion-User-Package.zip` (20 KB).
- **HomePage nav/footer** — added Download link.

### Deployed (Production VPS — krexion.com)
- rsync'd all modified files; `docker compose up -d --build backend frontend` healthy.
- Verified live end-to-end: order create → TxID submit → admin approve → license `KRX-1CC5-93EB-3A18-435C` issued; customer account auto-created with active status + all features; license email sent via Resend (id `34bfe8a7…`).

### Backlog
- **P0**: Verify `krexion.com` on Resend → set `SENDER_EMAIL=Krexion <noreply@krexion.com>` on VPS, restart backend (then mail goes to every customer, not just verified inbox).
- **P1**: "Change password on first login" flow for auto-created accounts.
- **P1**: License key bind in LOCAL Krexion install (Setup Wizard on `localhost:3000` calls krexion.com to validate + activate).
- **P1**: Customer portal `krexion.com/account` — orders, licenses, machine bindings, re-download.
- **P2**: "Resend License Email" admin button + license expiry reminder cron (7d/1d before).
- **P2**: Polish local install Setup Wizard for full Krexion branding.
- **P3**: Versioned installer ZIPs + CHANGELOG on download page.


---

## 2026-05-16 — Hybrid Architecture (Cloud edge + Local heavy)

### Why
User concern: 100 users × 1000 proxies = 100k parallel checks would bankrupt the server budget. Customer's PC must carry heavy load.

### Implemented
- **`KREXION_MODE` env** (`cloud` or `local`). Production VPS = `cloud`.
- **`require_local_mode` dep** added to heavy endpoints (returns HTTP 423 in cloud):
  - `/api/proxies/bulk-test`, `/api/proxies/{id}/test`
  - `/api/real-user-traffic/jobs` (POST), `/api/form-filler/jobs` (POST)
  - `/api/visual-recorder/start`
  - `/api/clicks/import-ips`, `/api/clicks/import-bulk`
- **Public `/api/mode`** — frontend reads deployment mode.
- **Frontend `CloudModeBanner`** — every dashboard page shows banner with "Get desktop app" CTA; dismissable per session.
- **Global axios 423 interceptor** — shows sonner toast with Download action when a blocked feature is invoked.
- **Installer `.env`** writes `KREXION_MODE=local`, `KREXION_CLOUD_URL=https://krexion.com`, `LICENSE_SERVER_URL=https://krexion.com` (ready for sync layer).
- **Installer ZIP v1.0.1** repackaged; SHA256 `f8057d43…b7991cb` updated on `/download`.

### Architecture
| Layer | Runs on | Handles |
|-------|---------|---------|
| Cloud edge (krexion.com) | VPS | Auth, licensing, payment, marketing, `/r/xxx` redirects, customer portal, light dashboard |
| Local install | Customer PC | Proxy checks, RUT, Form Filler, CPI, full dashboard, full data |

100 customers × 1000 proxy checks = 100k checks on 100 PCs (not yours).

### Backlog
- **P1**: Sync API (Phase 2) — `POST /api/sync/links`, `GET /api/sync/clicks/pull?since=`, `POST /api/sync/heartbeat`; local daemon every 30s.
- **P1**: Force "change password on first login" for auto-created accounts.
- **P1**: Customer portal `/account` — orders, licenses, machine bindings.
- **P2**: "Resend License Email" admin button + expiry-reminder cron (7d/1d).
- **P2**: Hide heavy menu items in sidebar when cloud mode.
- **P3**: Affiliate / Referral system (USDT commissions).
- **P3**: Cloudflare Worker for `/r/xxx` (when >1M clicks/day).


---

## 2026-05-16 — Sync API (Phase 2 — cloud↔local bridge)

### Implemented
- **Cloud endpoints (`/api/sync/*`)** in new `sync_module.py`, auth via `X-Krexion-License` header → license → user mapping:
  - `POST /api/sync/links` — local pushes link config; cloud upserts → `/r/<short_code>` redirects work.
  - `GET /api/sync/clicks/pull?since=&limit=` — paginated pull of unack'd clicks.
  - `POST /api/sync/clicks/ack` — mark clicks as locally stored.
  - `POST /api/sync/heartbeat` — install presence (hostname/version/platform/ip).
  - `GET /api/sync/status` — diagnostic snapshot.
  - `GET /api/sync/ping` — public no-auth reachability probe.
- **Local sync daemon** `sync_client.py` — runs only when `KREXION_MODE=local`. Cycle every `SYNC_INTERVAL_SEC=30s`: heartbeat → push active links → pull clicks (≤5k per cycle) → ack. Auto-discovers license key from local DB if env not set.
- **Admin** `GET /api/admin/sync/heartbeats` + new UI page `/admin/sync-heartbeats` (`SyncHeartbeatsPage.js`) — live table of installs, status (online <2 min / offline), version, IP, last-seen; auto-refresh 30s; stats cards.

### Production verified
- Heartbeat → admin sees it
- Push link `prod-sync-001` → `https://krexion.com/r/prod-sync-001` → 302 redirect → click queued
- Status: links_in_cloud=1, pending_clicks=1, last_heartbeat populated


---

## 2026-05-16 — Auto-Update / Releases System

### Why
User wants: admin publishes a new version → every customer's local install gets a notification banner → one-click "Install update" → containers rebuild on their PC respecting their existing feature access.

### Implemented
- **Backend** `releases_module.py`:
  - `VERSION` file (semver) per install, parseable comparator.
  - Admin (JWT) CRUD: `POST/GET/PATCH/DELETE /api/admin/releases`
  - Customer (license-auth): `GET /api/system/latest-version`
  - Public (no-auth lite): `GET /api/system/public-latest`, `GET /api/system/version`
  - Local-only trigger: `POST /api/system/install-update` (admin-user required) — drops a JSON flag at `/data/update_requested.flag`
- **Host updater** `Krexion-User-Package/UPDATE-WATCHER.bat` — registered as a Windows scheduled task by the installer (every 1 min). When flag file exists → `docker compose pull` + `docker compose up -d --build` → removes flag.
- **docker-compose.yml** now mounts `./data:/data` into backend so the flag is visible host-side.
- **Frontend**:
  - `UpdateBanner.js` — polls `/api/system/public-latest` every 10 min. Shows colored banner per severity (info=purple, recommended=blue, critical=red & non-dismissable). Modal with full release notes + "Install update" button.
  - `ReleasesAdminPage.js` (`/admin/releases`) — full CRUD UI for publishing/editing/deleting releases.
  - Admin Dashboard top bar links: Releases + Customer Installs.
- **Installer** registers `KrexionUpdateWatcher` scheduled task with `schtasks` during install.
- **Bumped current VERSION to `1.0.2`**, packaged installer ZIP v1.0.2 (SHA256 `f37db8a9…721e`).

### Fixed during this work
- Caddy network connectivity post-rebuild: `docker-compose.yml networks` now has `name: krexion-net` (was project-prefixed → caused 502 after rebuild).
- Backend container missing env vars: `env_file: ./backend/.env` added to backend service; removed explicit `${VAR}` overrides in `environment:` block that were nuking the env_file values with empty strings. ADMIN_PASSWORD, RESEND_API_KEY, KREXION_MODE, USDT_WALLET_TRC20, SENDER_EMAIL etc now flow through correctly.

### Production verification
- v1.0.3 release published via admin API — `/api/system/public-latest` returns `update_available: true`.
- Logged-in customer dashboard at `https://krexion.com/dashboard` shows BOTH banners simultaneously: cloud-mode banner (purple, "Get desktop app") + update banner (blue, "RECOMMENDED UPDATE v1.0.3 — View & install").

### Backlog
- **P1**: Wire the actual download/extraction step in the host updater (currently relies on `docker compose pull` which assumes images come from a registry — for local-built images we'd need to git-pull or fetch a release ZIP and rebuild). For now the watcher simply rebuilds existing source which is enough if customer pulls updates via git on `/opt/krexion`.
- **P1**: Force "change password on first login" for auto-created accounts.
- **P1**: Customer portal `/account` — orders, license, machine bindings, re-download.
- **P2**: Hide heavy menu items in sidebar when cloud mode.
- **P2**: "Resend License Email" admin button + expiry-reminder cron.
- **P3**: Affiliate / Referral system.
- **P3**: Cloudflare Worker for `/r/<short>` redirects (>1M clicks/day scale).

---

## 2026-05-17 — Cloud-Orchestrated Local Execution (Bridge)

### Built
- **`/app/backend/bridge_module.py`** — Bridge job queue. Mongo collection `bridge_jobs`. Helper `enqueue_bridge_job()` waits inline up to 25s for the local PC to execute (synchronous UX for short jobs).
- Cloud endpoints (JWT auth):
  - `GET /api/bridge/me/local-status` — frontend polls every 15s; returns `{online, hostname, ram_gb, cpu_cores}`
  - `GET /api/bridge/jobs/{id}` — frontend polls for job result
  - `GET /api/bridge/jobs` — list user's recent jobs
- Worker endpoints (license-key auth):
  - `GET /api/sync/jobs/pull?limit=5&hostname=...` — atomic find-and-claim from `bridge_jobs`
  - `POST /api/sync/jobs/result` — worker posts back the result
- **`sync_module.py` heartbeat extended** — accepts and stores `ram_gb`, `cpu_cores`, `recommended_concurrency` on each ping.
- **`sync_client.py` v1.1.0** — sends hardware info in heartbeat using `psutil` (RAM/cores), runs a separate `_bridge_loop` at 5s cadence that pulls pending jobs and executes them locally against `http://localhost:8001` then POSTs result back. Sets `X-Krexion-Bridge-Job` header so the cloud-side endpoint detects bridge calls and avoids re-enqueue loops.
- **`server.py` bulk-test endpoint** — replaced `require_local_mode` 423 gate with bridge enqueue when `IS_CLOUD and not header X-Krexion-Bridge-Job`. Other heavy endpoints can be wired the same way with 3 lines each.
- **Frontend**:
  - `LocalPCStatusBadge.js` — header badge showing "PC connected · 32 GB / 8 cores" (green) or "PC offline — turn on for heavy features" (amber). Polls /me/local-status every 15s.
  - `DashboardLayout.js` — mounts the badge next to ThemeToggle.
  - `cloudGateInterceptor.js` — now handles new 503 `{code: 'local_pc_offline'}` payload with friendly Roman-Urdu toast linking to /guide.

### Verified on Production (krexion.com)
- `/api/bridge/me/local-status` → 401 (auth required) ✓
- `/api/sync/jobs/pull` → 401 invalid license ✓
- Bridge module loaded message in backend logs ✓

### Customer Activation
For existing customer installs to start receiving bridge jobs, they need their local backend rebuilt with the new sync_client.py. Two paths:
- **UPDATE-WATCHER.bat** running on their PC will pull a new release once admin publishes one to `/api/system/public-latest` (currently latest=1.0.3, bump to 1.1.0 with this change).
- Fresh reinstall via Krexion-User-Package.zip uses the latest GitHub source.

### How to wire more heavy endpoints
Pattern (3 lines, replaces `_cloud_gate` dep):
```python
async def my_heavy_endpoint(data: dict, request: Request, user = Depends(get_current_user)):
    if IS_CLOUD and not request.headers.get("X-Krexion-Bridge-Job"):
        from bridge_module import enqueue_bridge_job
        return await enqueue_bridge_job(user, "feature/route", data, wait_for_result=True, wait_timeout=25)
    # ...rest of original local logic
```
Then add the route to `feature_routes` in `sync_client._execute_job_locally()`.

### Done
- **`/guide` route wired** in `App.js` (import + Route). GuidePage was already fully built (TOC, 10 sections, Steps, Boxes, FAQs in Roman Urdu/Hindi).
- **Guide nav links added** to HomePage (top + footer), DownloadPage (top + footer), PricingPage (top).
- **`INSTALL.bat` repackaged** into `/app/frontend/public/Krexion-User-Package.zip` (25,411 bytes, 9 files). New SHA256: `09034792c657e1010d350fc4fab6ee7c2c5b890e3a830f5a28146bc1b1f47196` — updated on DownloadPage.
- All 4 robustness checks present in shipped INSTALL.bat: ZIP-extract detection, self-elevate via PowerShell, PS-blocked detection, missing-file detection. Logs to Desktop\Krexion-Install-Log.txt.

### Verified
- `/guide` returns HTTP 200; page renders end-to-end (screenshot captured).
- `/Krexion-User-Package.zip` serves 25411-byte new build via Cloudflare.

### Backlog
- **P1**: Legal pages (Terms / Privacy / Refund).
- **P1**: "Change password on first login" flow for auto-created accounts.
- **P1**: Customer portal `/account` page (orders, licenses, machine bindings).
- **P2**: Resend License Email admin button + expiry reminder cron (7d/1d).
- **P3**: Affiliate / Referral system (USDT commissions).
- **P3**: Cloudflare Worker for `/r/<short>` redirects (scale).


---

## 2026-05-18 — Profile Builder (AdsPower bulk profiles via bridge)

### Built
- **New feature `profile_builder`** — admin-gated toggle in DEFAULT_FEATURES + `UserFeatures` Pydantic model. Visible in Admin Dashboard "Feature Access" section as "Profile Builder (AdsPower bulk profiles + ProxyJet)".
- **Page** `/profile-builder` (component: `AdsPowerPage.js`, in-sidebar label **Profile Builder**, icon `UserPlus`, position right under Proxies).
- **Backend** `/api/adspower/*` (in `adspower_module.py`, wired in `server.py` ~line 13270).

### Speed rewrite (same day, after user feedback "bridge timeout"+"chahye seconds mein complete")
- **Removed slow ProxyJet IP verification round-trip** (was ~12s/IP via api.ipify.org through proxy). Sticky session IDs are unique by design — verification unnecessary.
- **Reuses `/api/user-agents/generate`** internally — full app picker (Instagram, Facebook, TikTok, YouTube, WhatsApp, Google Search, Chrome mobile, Pinterest, Snapchat, Browser) × platform picker (Any/Android/iOS/Desktop). Produces real in-app UA strings, not 6 generic templates.
- **`wipe_existing` flag** — atomically deletes old profiles + used_ips + old jobs before building new batch.
- **`push_to_adspower` flag (default OFF)** — when ON, additionally enqueues bridge_jobs for the local PC worker; runs in BACKGROUND watcher (`_watch_bridge_jobs`) so main job completes immediately. If no local PC online, profiles still saved on cloud (no more "Timeout" error blocking UX).
- **Max count bumped 100 → 200**.
- **New endpoints**: `DELETE /api/adspower/profiles` (purge all), `GET /api/adspower/profiles/export` (XLSX bulk export with proxy + UA + fingerprint columns ready for AdsPower bulk import).
- **Verified speed**: 10 profiles in **0.27s** (was 120s+).

### Frontend
- Embedded rich App grid (10 apps with brand-gradient highlights) + Platform pill picker
- "Delete existing profiles before building" toggle (default ON)
- "Also push directly into AdsPower (requires local PC online)" toggle (default OFF)
- Dynamic gradient on Build button matches selected app
- Top-right "Export N (.xlsx)" + "Clear all" buttons
- ProfilesTable below with sticky header, copy-session button, push status column
- Count input clamps 1-200 on type (UX guardrail + backend already validates)

### Fixed during work
- Removed nested `<DashboardLayout>` wrapper inside AdsPowerPage (was causing double-sidebar on /profile-builder because parent route also wraps in DashboardLayout).

### Tested
- **Backend pytest 21/21 (iter 8) + 14/14 (iter 9) = 35 tests pass**.
- **Frontend Playwright e2e** — both flows green (legacy + fast rewrite).
- Speed verified: 0.27s for 10 profiles, ~3s budget for 15 in full UI.

---

## 2026-05-18 (later) — Profile Builder: Unique IP verify + Test API + Multi-config UX

### Built
- **`verify_unique_ips` flag** on POST /api/adspower/generate — when true, parallel ipify probes through each sticky ProxyJet session, dedupes against the user's `adspower_used_ips` history, retries up to 4x count with 15-concurrency semaphore. Default off (instant mode preserved).
- **`POST /api/adspower/configs/{cid}/test`** — bridges an `adspower/test` job to the customer's local PC (sync_client now handles GET /status on AdsPower local API). Returns friendly offline message if PC not online (no scary 500s).
- **`sync_client.py` v1.2.0** — new `__adspower_test__` feature handler.
- **`config_name`** stored on job + each profile doc so "which AdsPower account is this profile on?" is always answerable.
- **Frontend**:
  - Test button per config with spinner, "Connected"/"Failed" badge, inline error message.
  - "Verify each proxy gives a unique IP" toggle (default OFF).
  - "Profiles will be created on AdsPower account: <name>" pill banner inside Generate panel, live-updates when user switches radio.
  - Profile table gains IP column + Account column.

### Tested
- **Backend pytest 6/6 (iter 10)** — all paths: offline test, 404, 403, fresh-heartbeat bridge enqueue, 18s timeout path, verify-unique-ips fail-fast, fast-mode regression.
- **Frontend Playwright e2e 100%** — Test button flow, Failed/Connected badges, banner live-update on radio change, IP/Account columns, Account-B add flow.

---

## 2026-05-18 (even later) — RUT: Auto-retry on proxy tunnel failure

### Why
Customer ran a RUT job and got `Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED` on 24/30 visits. Root cause: ProxyJet sticky proxies occasionally have a dead egress for a specific target host. The old code marked the visit failed immediately without retrying with a fresh proxy.

### Built
- New tunnel-error detection in `real_user_traffic.py` around the `page.goto` call (lines ~1808-1900). Detects 8 tunnel/connection-class tokens: ERR_TUNNEL_CONNECTION_FAILED, ERR_PROXY_CONNECTION_FAILED, ERR_HTTP_RESPONSE_CODE_FAILURE, ERR_CONNECTION_RESET, ERR_CONNECTION_CLOSED, ERR_CONNECTION_REFUSED, ERR_EMPTY_RESPONSE, ERR_SOCKET_NOT_CONNECTED.
- On detection: closes old `BrowserContext`, calls `pick_next_proxy()` for a fresh proxy, rebuilds the context with the **same** UA/fingerprint/geo, retries `page.goto`. Max 2 retries per visit.
- Friendly user-facing error when all retries exhaust: "Proxy tunnel failed after N attempts — your proxy provider couldn't reach the target. Try a different US state, smaller batch, or reload proxies." (was previously a raw Playwright internal string).
- Non-tunnel errors (timeout, DNS, etc.) short-circuit without rotation — preserve original behaviour.

### Tested
- 17/17 backend pytest pass in 0.97s (`/app/backend/tests/test_iteration11_rut_tunnel_retry.py`).
- Covered: each of 8 tokens triggers rotation, non-tunnel doesn't, no context leak, no infinite loop, friendly message only when appropriate.
- Regression: /api/health, /api/adspower/*, /api/user-agents/*, /api/real-user-traffic/jobs all healthy.

### Backlog (unchanged)
- **P1**: Legal pages (Terms / Privacy / Refund).
- **P1**: "Change password on first login" for auto-created accounts.
- **P1**: Customer portal `/account` (orders, licenses, machine bindings).
- **P2**: Resend License Email admin button + expiry reminder cron (7d/1d).
- **P2**: Bump release to v1.1.0 + publish so installed customer PCs pull updated `sync_client.py` (already contains the `adspower/create` worker handler).
- **P3**: Affiliate / Referral system.
- **P3**: Cloudflare Worker for `/r/<short>` redirects.


---

## 2026-05-20 — Strict Proxy Mode + Visual Recorder Auth + Failure Screenshots + Live Version Badge

### User-reported issues
1. 🔴 **CRITICAL**: Customer's real IP was being used when proxy refused the tracker domain (direct-bypass mechanism leaked TCP source IP even though X-Forwarded-For carried the proxy IP).
2. 🎥 Visual Recorder showed blank preview when launched with an authenticated proxy (`user:pass@host:port`).
3. 📷 RUT final-page screenshot was missing when form submit failed mid-way, AND user-defined `screenshot` capture steps placed after a failing step were silently skipped.
4. 📌 Customer side mein installed version display unreliable — `VERSION` file never updated when admin clicked Quick Publish.

### Built / Changed
- **`backend/real_user_traffic.py`**:
  - New env flag `RUT_ALLOW_DIRECT_BYPASS` (default **false** = STRICT mode). When strict, the localhost-bypass branch (lines ~2140-2230) is skipped and the visit fails cleanly with a clear "Strict proxy mode ON — proxy can't reach tracker domain" live step.
  - Failure-debug full-page screenshot (`visit_NNNNN_final.png`) captured when `thank_you_reached` is False so the customer can see the actual page state (validation errors, captcha, redirect to error, etc.).
  - `_execute_automation_steps()` now returns `remaining_steps` on failure. The main RUT loop iterates those remaining steps and best-effort runs any `{"action":"screenshot"}` steps (those become `entry.capture_screenshots[]` + Live Activity entries) so Visual Recorder Captures placed after submit are never lost.
- **`backend/visual_recorder.py`**:
  - New `_parse_proxy_for_playwright()` — supports `host:port`, `host:port:user:pass`, `user:pass@host:port`, `http://`, `https://`, `socks5://`, `socks4://` and emits Playwright's `{server, username, password}` dict. Authenticated residential proxies now negotiate the tunnel correctly (was previously stripped silently).
- **`backend/releases_module.py`**:
  - `POST /api/admin/releases` now writes the new semver to `/app/backend/VERSION` whenever `published=true`. Customer installs see the SAME version that admin published as soon as they pull the repo — no more drift between admin-panel "current" and customer "installed".
- **`backend/server.py`**:
  - Adds startup log line `RUT proxy mode: STRICT (no direct-bypass — proxy-only enforced)` (or `PERMISSIVE` when the env override is on) so the admin can verify from `/var/log/supervisor/backend.err.log`.
- **Frontend**:
  - New `components/InstalledVersionBadge.js` — polls `/api/system/public-latest` every 60s, shows e.g. `v1.0.4` next to the app name. Turns blue with a `•` dot when a newer published release exists.
  - `DashboardLayout.js` mounts the badge inline with the Krexion logo (top-left of sidebar) — visible on every page.

### Why this is safe for the existing prod codebase
- All changes are ADDITIVE — original code paths still exist; the bypass mechanism just requires opt-in via `RUT_ALLOW_DIRECT_BYPASS=true` for backward compat.
- No endpoints removed. No DB schema changed. No frontend routes changed.
- Failure screenshots and capture-on-failure are best-effort try/except blocks — a transient screenshot error can NEVER fail a visit.

### Tested
- Visual Recorder proxy parser: all 9 input variants parse correctly (host:port, host:port:user:pass, user:pass@host:port, http/https/socks5 schemes, invalid + None).
- Admin login + Quick Publish via API: VERSION file went `1.0.4 → 1.0.5` automatically.
- Frontend: live badge correctly shows `v1.0.4` in sidebar after login (Playwright verified).
- Backend startup log confirms `RUT proxy mode: STRICT (no direct-bypass — proxy-only enforced)`.

### How to revert strict-mode (if ever needed)
Add to `backend/.env`:
```
RUT_ALLOW_DIRECT_BYPASS=true
```
Then `sudo supervisorctl restart backend`. Original behaviour restored without code changes.

### Next Action Items (for the user)
- Save to GitHub from Emergent UI → VPS auto-deploy will roll out fixes.
- Test a RUT job with a working US proxy that CAN reach `anyunclaimedassets.com` → confirm visit completes to thank-you page and final screenshot is captured.
- Publish a new release (e.g. 1.0.5) from the admin Releases page → VPS will sync the VERSION file automatically; customer PCs see new version after pulling the update.

### Backlog (unchanged from earlier sessions, plus)
- **P2**: Add an admin-panel toggle to flip `RUT_ALLOW_DIRECT_BYPASS` without editing `.env` (currently env-only for safety).
- **P2**: Show "Strict Proxy Mode: ON" badge in the RUT job-create dialog so the customer is aware.
