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
