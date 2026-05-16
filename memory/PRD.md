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

### Backlog
- **P1**: Force "change password on first login" for auto-created accounts.
- **P1**: Customer portal `/account` — orders, licenses, sync diagnostics widget, re-download.
- **P2**: Hide heavy menu items in sidebar when cloud mode.
- **P2**: "Resend License Email" admin button + expiry-reminder cron (7d/1d).
- **P3**: Affiliate / Referral system (USDT commissions).
- **P3**: Cloudflare Worker in front of `/r/<short>` (>1M clicks/day scale).
