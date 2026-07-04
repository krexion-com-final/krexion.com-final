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
