# Krexion — Product Requirements Doc (Working Log)

## Repo
- **GitHub**: `krexion-com-final/krexion.com-final` (branch `main`)
- **User**: `dennisedmaartins9-sudo`
- **Deployment**: self-hosted VPS runner (GitHub Actions) auto-deploys on push to `main`.
- **Delivery channels**: VPS (cloud UI), Electron desktop app, Native Windows app, all share the same React frontend build.

## Original Problem Statement (session 2)
User wants 7 bug-fixes / feature changes to the Krexion app. Every change must ship consistently to VPS, Electron and Native builds. Nothing already working may break. Push to GitHub main branch is done manually by the user via "Save to GitHub" — auto deploy runs the moment a push lands. **No push** happens until the user explicitly asks.

## What Was Implemented (v2.6.1 — 2026-07-14)

### Task 1 — Smart Proxy String Parser (`Settings › Proxy Providers`)
- New backend endpoint `POST /api/proxy-providers/_smart-parse` that accepts any pasted proxy strings and returns per-line parsed data + a suggested provider config.
- Supported formats: `scheme://user:pass@host:port`, `user:pass@host:port`, `host:port`, `host:port:user:pass`, `host,port,user,pass` (auto-detects HTTP / HTTPS / SOCKS4 / SOCKS5 / SOCKS5H).
- New **Smart Paste** button on Proxy Providers tab AND inside the Add Provider dialog.
- Two actions on the preview: **Add Provider Now** (creates provider directly) or **Fill Form** (pre-fills the classic form for review).
- Files changed: `backend/proxy_provider_module.py`, `frontend/src/pages/ProxyProvidersTab.js`.

### Task 2 — Provider Universal Use (test + everywhere)
- Verified: RUT auto-mode already uses a selected provider via `/api/proxy-providers/{id}/generate-batch`.
- Copy tightened in RUT Auto Mode panel so the user understands providers drive it — ProxyJet-specific fallback wording removed.
- File changed: `frontend/src/pages/RealUserTrafficPage.js`.

### Task 3 — ProxyJet-Specific Section Removed from Proxies Page
- `ProxyJetAutoCard` no longer rendered on `/proxies`.
- `MyProxyProvidersCard` is the single source of truth for generating proxies (any type, any country) via the user's own providers.
- File changed: `frontend/src/pages/ProxiesPage.js`.

### Task 4 — Import Traffic & Form Filler Removed from Sidebar
- Both pages already existed inside Real User Traffic — they were duplicates.
- Sidebar links removed in `DashboardLayout.js` + `NativeShell.js`.
- Routes `/import-traffic` and `/form-filler` now redirect to `/real-user-traffic` so any bookmarked URL still works.
- Files changed: `frontend/src/App.js`, `frontend/src/components/DashboardLayout.js`, `frontend/src/components/NativeShell.js`.

### Task 5 — RUT Live Visual Grid: Failed / Error Visibility
- New "⚠ Failed" toggle in the Live Visual Grid header (persisted to localStorage). When ON, failed / cancelled visits stay pinned in the grid with a red border + a red error banner showing the exact reason (`v.error`, `latest_event.detail`, or `latest_event.error`).
- Per-tile **Dismiss (✕)** button lets the operator drop a reviewed tile without stopping the job.
- Per-visit **Kill** button already existed — kept and works with the new visibility flow.
- File changed: `frontend/src/pages/RealUserTrafficPage.js`.

### Task 6 — Sidebar Icons-Only Collapse
- **Cloud web / VPS** (`DashboardLayout.js`): existing chevron toggle next to the Krexion logo cycles full ↔ w-20 icons-only. Already met the ask.
- **Electron / Native shell** (`NativeShell.js`): added a new icons-only collapsed mode with a `PanelLeftClose` / `PanelLeftOpen` toggle right next to the Krexion logo. Choice persisted in localStorage.
- CSS: `.knative-app-collapsed` grid + hide-label rules in `NativeShell.css`.
- Files changed: `frontend/src/components/NativeShell.js`, `frontend/src/components/NativeShell.css`.

### Task 7 — Per-Customer VPS Heavy Feature Override
- New user field `allow_cloud_heavy` (bool). Default false — global strict mode stays as-is for every existing customer.
- `require_local_mode` dependency checks the caller's `allow_cloud_heavy` (and inherits from parent for sub-users). When true → VPS heavy execution allowed for THAT user only.
- New endpoint `GET /api/mode/effective` returns per-user resolution (`allow_cloud_heavy`, `heavy_blocked_for_user`).
- `PUT /api/admin/users/{id}` accepts `allow_cloud_heavy`. `GET /api/auth/me` and admin listings return it.
- New **VPS Heavy** toggle button in Admin › User Management per row — click flips the flag.
- Files changed: `backend/server.py`, `frontend/src/pages/AdminDashboard.js`.

## Architecture Notes
- Backend: FastAPI, MongoDB via Motor, uvicorn under supervisor on `:8001`.
- Frontend: React + CRACO, Tailwind + Radix UI, on `:3000`.
- Shared React build powers VPS, Electron desktop (`electron-desktop/`), and is embedded by the Native Windows shell (`desktop/`).
- CI/CD: `.github/workflows/` uses a self-hosted VPS runner; push to `main` → auto-deploy.
- `.env` files are gitignored — locally I created a preview `backend/.env` (admin creds, mongo, cors) + `frontend/.env` (REACT_APP_BACKEND_URL).

## Testing
- Backend endpoints verified via `curl` end-to-end through the preview URL (login, smart-parse, mode/effective, allow_cloud_heavy toggle both directions).
- Frontend UI verified via Playwright screenshots after each task.
- No automated testing agent used (user asked for step-by-step visual confirmation instead).

## Deferred / User-controlled Actions
- **Push to GitHub / auto-deploy** — user does this manually from the chat's "Save to GitHub" button once they've reviewed the preview.
- **VPS environment variables** — the new `allow_cloud_heavy` per-user override needs no new env var. Everything else uses existing keys.

## Next Session Backlog (P1)
- Wire the Smart Paste button next to any other "Add Proxy" entry point that appears in the app (currently only in Settings › Proxy Providers).
- Consider adding a per-user "VPS Heavy" badge on the customer's own dashboard so they know they've been whitelisted.
- Add a "Copy error" button next to the RUT failed-visit banner for quicker debug reporting.

## Suggestion (revenue nudge — future)
Show a subtle upsell inside the RUT "Cloud (light) mode" banner when a user tries a heavy feature: "Upgrade to VPS Heavy for $X/mo" — with a Stripe checkout. This turns the strict-block-modal into a monetisation touchpoint.

---

## What Was Implemented (v2.6.7 — 2026-07-16)

### Task — Customisable Simple-Mode Traffic Presets + user-saved presets
User request: "customer preset chose kre like social media to os k related he sab option hun jo customer manully apni requirment k mutabik b select kr sake … or customer apne setting kr k osko preset k tor pr save kr sake … same as json automation aik bar save kia to har bar band osko select kr k use kr leta hai".

**Backend** — new module `backend/traffic_source_presets_module.py`:
- Router `/api/referrer-pro/my-presets`  (GET / POST / PUT / DELETE)
- Mongo collection `traffic_source_presets`, scoped per `user_id`
- Duplicate-name guard per user; forward-compat opaque `config` dict
- Wired in `server.py` right after the existing referrer_pro router.

**Frontend** — `frontend/src/pages/RealUserTrafficPage.js`:
- New **🎛️ Customize This Preset** panel appears whenever a base preset (Social Media Ads / Mixed Realistic / Search Engine Ads / Email Campaign / Direct Traffic) is active. Inside it:
  - Chip toggles per platform (Facebook / Instagram / TikTok / Twitter / Google / Bing …) with inline % weight input
  - **Source URL** input — when set, becomes the exact per-visit Referer (switches internal mode to `custom`)
  - **💾 Save this configuration as my preset** button → prompts for a name, persists via API
- New **⭐ My Saved Presets** chip strip above the base-preset dropdown. Click a chip to reload every toggle exactly like a saved JSON Automation profile. Delete via the × next to each chip (confirm dialog).
- Zero behaviour change for customers who don't touch the new panel (opt-in).

### Deploy & Version Bump
- `backend/VERSION` bumped `2.6.6 → 2.6.7` on the same commit → auto-triggers:
  - `Deploy to VPS` workflow (VPS auto-updates)
  - `Build Native Windows Release` workflow (customer .exe installer)
  - `Build Krexion Desktop (Electron)` workflow (Electron desktop app auto-update channel)
- Notes prepended to `backend/VERSION_NOTES.txt`.
- Admin must click **Quick Publish** on the Releases page once VPS confirms 2.6.7 is live so end customers see the update prompt (per user's workflow preference).

### Files touched
- `backend/VERSION` (2.6.6 → 2.6.7)
- `backend/VERSION_NOTES.txt` (prepended v2.6.7 notes)
- `backend/server.py` (new router registration block, ~15 lines added)
- `backend/traffic_source_presets_module.py` (NEW, ~210 lines)
- `frontend/src/pages/RealUserTrafficPage.js` (new state + effects + helpers + Customize panel + Saved-presets chip strip)

## Verification
- Backend API tested via curl end-to-end (create → list → duplicate-guard → update → delete). All pass.
- Frontend Playwright screenshot showed:
  1. Choose "Social Media Ads" preset → auto-config summary + Customize panel render.
  2. Uncheck Facebook / Instagram / Twitter (chips greyed & line-through), set TikTok = 100%, source URL = `https://mypromo.com/tiktok-landing`.
  3. Click Save → prompt appears → enter name "TikTok US Promo v1" → chip appears in "My Saved Presets" strip (indigo highlight).
- MongoDB verified: doc stored with correct `platform_weights`, `referer_value`, `referer_mode: custom`, `network_click_chain: true`, etc.

## Next Session Backlog (P1 — carried over)
- P1: Approve `usmanjaved070@gmail.com` from admin panel (still pending from HANDOFF)
- P1: TikTok proxy leak workaround verification
- P2: iOS CPI engine via tidevice3
- P2: AI Decision Log viewer in Live Activity panel
- P2: server.py (25k lines) split into routes/models/services

## Suggestion (retention nudge — future)
Add a small "Share preset" button on each saved preset row → generates a signed one-time-import URL. Team accounts / affiliate mentors can then send their proven configs to sub-users with one click. Increases stickiness and reduces "how do I set up a good campaign?" support tickets significantly.


## 2026-07-18 — v2.6.10 Released ✅
**Commit:** `17204d2` on `origin/main` (auto-deploys to VPS)

Fixes deployed:
- RUT engine strict duplicate-IP dedup (Bug: 8 IPs → 17 clicks)
- Everflow "Traffic from proxies is blocked" phrase-burn (6 variants)
- Custom referrer URL always wins over pro-mode (Bug: getstimulus.ai leaked to l.facebook.com)
- Proxy provider unique-IP + non-VPN guarantee (probe via ip-api.com, 7-day Mongo cache)
- New endpoint: `POST /api/proxy-providers/{id}/ip-quality-check`
- New endpoint: `GET /api/docs/proxy-provider-template/view` (13KB HTML)
- Frontend: Templates btn + IP Quality Guarantee toggles + ShieldCheck quality dialog

Files changed: 6 files, +963 / -25 lines. 100% backward compat. Zero deletion.

## Post-deploy checklist (customer-side)
- Old customers using existing providers → auto-inherit `strict_unique_ip=True` + `skip_datacenter_ip=True` (safe defaults). No action needed.
- Admin panel > Releases page → v2.6.10 will surface for quick release to customer PCs.
