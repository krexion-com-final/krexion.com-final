# Krexion.com — Maintenance & Bugfix Workflow

## Original Problem Statement
User (aadspower301@gmail.com) owns the krexion.com SaaS (FastAPI + React + Mongo).
- VPS auto-deploys from `main` branch (git push triggers deploy).
- Desktop app distributed via admin "Release" panel — customer PCs auto-update.
- Cloud mode: `KREXION_MODE=cloud`, `STRICT_CLOUD_HEAVY_BLOCK=true`
  → all heavy RUT/Form-Filler jobs BRIDGE to the customer's online desktop.
- User wants me to TEST live, find bugs, fix in `/app`, NEVER push or deploy
  until they explicitly say so.

## Architecture (key)
- Cloud edge (krexion.com / VPS): handles auth, link redirects, upload storage,
  bridge router. NO heavy jobs run on cloud (strict block).
- Customer's desktop app: runs the actual RUT engine via Playwright. Polls
  `/api/bridge/next` for queued jobs and replays them against its OWN local
  FastAPI backend (same `server.py`, just a different process / DB).

## Bug Reports Handled

### 2026-06-25 — RUT data-file bridge inlining (BLOCKER)
Symptom: Every RUT job for aadspower301@gmail.com failed with
`"Selected data-file upload not found · DB doc missing (re-upload required)"`
even though the user's saved data file (`test_data_1782397855`, 946 rows)
was visible in the cloud's Uploaded Things page.

Root cause: When the cloud bridges a heavy RUT job to the customer's desktop,
`_inline_upload_refs` resolves UA / proxy / automation_json uploads into the
bridge payload's urlencoded body — but it did NOT inline the `data_file`
upload. The desktop's local Mongo has no copy of the cloud-uploaded data
file, so `_load_upload_data_file` returned None, then the diagnostic flagged
"DB doc missing".

Fix (in `/app/backend/server.py`, NOT yet pushed):
1. `_inline_upload_refs`: read the data-file bytes from cloud disk, base64
   encode them, and append `data_file_b64` + `data_file_b64_name` form fields.
   `upload_data_file_id` is dropped from the bridge payload only when the
   inline succeeds (so failures still surface clean errors).
2. RUT job endpoint signature: accept `data_file_b64` + `data_file_b64_name`
   Form fields. When set, decode back into `file_bytes` so the rest of the
   pipeline (BG task persists to disk + reads rows) works identically to the
   direct-upload path.

### 2026-06-25 — Watchdog default 240→600
Symptom: User reported long survey + deal flows getting killed by the
inactivity watchdog when a legitimate 5-10 min real-user walk needs more
time than the default 240s.

Fix:
- `backend/server.py`: `stuck_watchdog_seconds: float = Form(600.0)` (was 240).
  Also bumped the fallback in `params_dict` + persisted `submit_params` to 600.
- `backend/real_user_traffic.py`: function default + watchdog construction +
  error message all moved 240 → 600.
- UI is unchanged — users can still override per-job (range 30..1800).

## Pending (waiting on user to "git push" main)
- VPS auto-deploys → cloud edge picks up the bridge inlining fix.
- Admin needs to trigger a desktop "Release" so customer desktops update to
  the version that knows how to decode `data_file_b64`.
- Then I can re-run the live RUT job (3 visits, target01, TikTok UA, ProxyJet)
  and verify the 3-deal completion + conversion flow.

## Useful References
- Saved IDs for aadspower301:
  - automation_json `target 750 v10 (E1-fixed)` → `17cc96a1-689c-4c32-ab26-359089faf059`
  - data_file `test_data_1782397855` → `290b5f9a-1b8f-42e8-90b6-abeb863befc5`
  - user_agents `TikTok Mix (Android+iOS) - RUT test` → `2d96a3dd-4427-45b9-9f88-de9c3a0aff1a`
  - link `target01` → `315d9b7f-f33b-4ace-afe8-1ad3971f65ba` (offer → gift-click-flow.lovable.app)
- ProxyJet credentials already configured for user.
