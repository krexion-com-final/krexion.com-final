# Krexion.com — Maintenance & Bugfix Workflow

## Original Problem Statement
User (aadspower301@gmail.com) owns the krexion.com SaaS (FastAPI + React + Mongo).
- VPS auto-deploys from `main` branch (git push triggers deploy).
- Desktop app distributed via admin "Release" panel — customer PCs auto-update.
- Cloud mode: `KREXION_MODE=cloud`, `STRICT_CLOUD_HEAVY_BLOCK=true`
  → all heavy RUT/Form-Filler jobs BRIDGE to the customer's online desktop.

## Bug Reports Handled

### 2026-06-25 → 2026-06-26 — RUT data-file bridge inlining (RESOLVED ✅)
Symptom: Every RUT job for aadspower301 failed with
`"Selected data-file upload not found · DB doc missing (re-upload required)"`
in <15 seconds, before any visit.

Root cause: When the cloud bridges a heavy RUT job to the customer's
desktop, `_inline_upload_refs` inlined UA / proxy / automation_json but
NOT data_file. Desktop's local Mongo had no copy of the cloud-uploaded
data file → BG task failed at prep.

Fix shipped (commit 91e0d22 / v2.1.66, deployed via new org
`krexion-com-final/krexion.com-final`):
1. `_inline_upload_refs` now returns `(kv, file_attachments)` tuple —
   the cloud-side data file bytes are read via `_load_upload_data_file`
   and added to `file_attachments`.
2. The bridge body-capture loop in `require_local_mode` switches the
   replay body encoding to `multipart/form-data` (via
   `urllib3.filepost.encode_multipart_formdata`) whenever
   `file_attachments` is non-empty.
3. Desktop's existing `file: Optional[UploadFile]` Form param picks the
   attachment up natively — NO desktop-side code change required.
4. `upload_data_file_id` is dropped from the bridge payload only on
   successful inlining (failures preserve the id so the existing
   diagnostic still surfaces clean errors).

Stuck_watchdog default also raised 240s → 600s.

Verification: iteration_14 live test on https://krexion.com — same
scenario as iteration_13 — job now transitions to status='running'
and the desktop browser engine actively executes the visit (used to
fail at prep in <15s).

### Deployment story
- Pushed commit `91e0d22` to old repo `dennisedmaartins9-sudo/krexion.com`
- GitHub Actions FREE-TIER MINUTES EXHAUSTED → 5 sequential deploy
  attempts all failed in 2-7 sec without running any step.
- User created new GitHub Organization `krexion-com-final` and
  transferred the repo. Org has its own fresh 2000 min/month quota.
- Re-triggered deploy via `workflow_dispatch` on the new org → SUCCESS
  in ~10 minutes (full Docker rebuild + rsync + container restart).
- Cloud now serving v2.1.66 — confirmed by live test.

## Open Issues (separate from the now-fixed data-file bug)

### 1. UI gap — no "Saved Automation JSON" picker in RUT form
- Backend supports `upload_automation_json_id` param.
- Frontend RUT page only exposes a manual textarea (`🧩 Use Custom
  Automation JSON`).
- User has to paste the JSON each time OR use the API directly.

### 2. Automation JSON template "target 750 v10 (E1-fixed)" step 37 fails
- Reported in live curl-driven smoke run with API-supplied JSON id.
- Error: `❌ REQUIRED step 37 of 118 (evaluate) did not complete —
  visit aborted. Reason: Page.evaluate: TypeError: undefined is not
  iterable (cannot read property Symbol(Symbol.iterator))` on the deal
  page `https://www.displayoptoffers.com/default.aspx`.
- This is a TEMPLATE-side bug — likely the deal-page DOM changed since
  the template was authored.

### 3. RUT burnt-IP blocklist contains many entries from prior tests
- `rut_burnt_ips` collection has 200+ IPs persisted from previous
  failed test runs.
- Causes high "duplicate IP skipped" rate at start of each new job
  until a fresh exit IP is rolled.
- Not a bug — designed-as behavior. Operator can either clear the
  collection or let it self-prune via natural rotation.

## Useful References
- Saved IDs for aadspower301:
  - automation_json `target 750 v10 (E1-fixed)` → `17cc96a1-689c-4c32-ab26-359089faf059`
  - data_file `test_data_1782397855` → `290b5f9a-1b8f-42e8-90b6-abeb863befc5`
  - data_file `pending_aaa_v2` (uploaded 2026-06-25) → `437604b3-b232-4efc-b04c-707b68f9bd91`
  - user_agents `TikTok Mix (Android+iOS) - RUT test` → `2d96a3dd-4427-45b9-9f88-de9c3a0aff1a`
  - link `target01` → `315d9b7f-f33b-4ace-afe8-1ad3971f65ba`
- Repo: `https://github.com/krexion-com-final/krexion.com-final.git`
- ProxyJet credentials already configured for user.

## Test IDs Confirmed on RUT Form (from iteration_14)
- rut-link-select, rut-use-proxyjet-auto, rut-proxyjet-country,
  rut-ua-option-<id>, rut-total-clicks, rut-concurrency,
  rut-stuck-watchdog-seconds, rut-form-fill-toggle, rut-upload-data-id
  (native <select>, use page.select_option), rut-skip-captcha,
  rut-self-heal, rut-follow-redirect, rut-start-btn.
- networkidle wait fails on krexion.com because tawk.to embed
  (CORS-blocked) keeps polling — always use wait_until='domcontentloaded'.
