# Krexion — PRD & Working Log

## Original Problem Statement
User has a GitHub repo `dennisedmaartins9-sudo/krexion.com` (Krexion — traffic tracking + RPA + anti-detect platform). They want to:
1. Add an RPA Studio feature similar to AdsPower RPA (50+ visual nodes, drag-drop editor)
2. Add a Banner / Announcement system for admin to publish offers
3. All work must be safe — no existing functionality breaks

## Architecture Tasks Done
- Cloned repo into `/app` while preserving `.emergent` settings
- Configured `.env` with `KREXION_MODE=cloud` so auth works locally in preview
- Set up GitHub PAT in credential store (token NOT embedded in remote URL)
- Installed `reactflow` for visual flowchart editor

## User Personas
- **Customer**: traffic affiliate / CPI marketer — builds automation workflows visually
- **Admin**: platform operator — publishes promo banners, manages licenses

## Core Requirements (static)
- Build no-code workflow editor (drag-drop nodes, connect, configure, run)
- Support 55+ node types covering all AdsPower RPA categories
- Banner system: admin posts banners, customers see them on dashboard
- Auto-deploy works via Save-to-GitHub feature

## What's Been Implemented (with dates)

### 2026-06-09 — Initial Repo Setup
- Cloned krexion.com main branch into /app
- Configured backend/.env (MONGO_URL, DB_NAME=krexion, KREXION_MODE=cloud, ADMIN credentials)
- Restored frontend/.env with preview URL
- Installed Python deps: fastapi 0.115.6, motor 3.6, playwright 1.49, orjson, psutil, curl_cffi etc
- Installed frontend deps via `yarn install`
- All services running via supervisor

### 2026-06-09 — Banner System (`banner_module.py` + `BannerBar.js` + `AdminBannersPage.js`)
- Admin CRUD: `POST/GET/PATCH/DELETE /api/admin/banners`
- Customer public endpoint: `GET /api/banners/active`
- Schema: message, theme (info/promo/success/warning/danger), cta_label, cta_url, starts_at, ends_at, is_active, priority, dismissible
- Visible filtering by date range + active flag
- Frontend BannerBar polls every 2 mins, supports per-user dismissal (localStorage)
- Admin page at `/admin/banners` with preview + edit + activate/deactivate

### 2026-06-09 — RPA Studio (`rpa_studio_module.py` + `RPAStudioPage.js` + `RPAWorkflowsPage.js` + `RPARunsPage.js`)
**Backend node executor (55 node types, 7 categories):**
- Web (21): goto, new_tab, close_tab, close_other_tabs, switch_tab, refresh, go_back, go_forward, click, **random_click**, **checkbox**, hover, focus, select, **random_select**, fill, scroll, input_file, screenshot, **mark_final**, evaluate
- Keyboard (2): press, key_combo
- Waits (6): wait, wait_for_selector, wait_for_request, wait_for_load, wait_for_text, wait_for_url
- Get Data (8): get_url, get_element, get_cookies, clear_cookies, save_to_txt, save_to_excel, download_file, import_excel
- Data Processing (6): set_var, regex_extract, to_json, extract_field, random_extract, math
- Control Flow (8): if/else, for_loop_times, for_loop_data, while_loop, exit_loop, throw_error, apply_workflow, quit_browser
- Third-Party (4): OpenAI/Claude/Gemini (Emergent LLM Key ready), 2captcha (stub), Google Sheets (stub), HTTP Request

**Variable system:** `{{var_name}}` substitution, dot-path access (`a.b.c`), per-loop scope

**Endpoints:**
- Workflows: CRUD + duplicate + import + export
- Runs: start, list, get, stop, live progress, screenshot
- Node catalog (drives palette UI)
- Templates (marketplace stub)

**Frontend:**
- `/rpa-studio` workflow list with cards, search, duplicate, delete, import JSON
- `/rpa-studio/:id` visual editor using reactflow with:
  - Left palette (categorized + search)
  - Center canvas with drag/connect/minimap/controls
  - Right inspector (param fields based on node type, on_error toggle, settings drawer)
  - Top toolbar: save, run, export, settings
  - Live run panel with screenshot preview + event log
- `/rpa-runs` run history with status badges + step-by-step event detail

**Sidebar:** Added "RPA Studio" menu link with Zap icon.

**Admin Dashboard:** Added "Banners" button.

### 2026-06-09 — Live Recording → RPA Studio Converter (`from-recorder` + `from-upload`)
- New backend endpoints:
  - `POST /api/rpa/workflows/from-recorder` — converts inline steps array (`{steps: [...]}`) to a fresh flowchart workflow with auto-layout
  - `POST /api/rpa/workflows/from-upload/{upload_id}` — converts a saved Visual Recorder upload (Uploaded Things) to a flowchart
- Converter handles 18 Visual Recorder action types → mapped to RPA Studio node types
  (goto, click, fill, type, select, check/uncheck, press, wait, wait_for_*, scroll, evaluate, extract, screenshot, dismiss_popups, close, branch)
- Unknown actions fall through to Execute JS comment nodes to preserve ordering
- Auto-layout: vertical chain (x=240, y+=110), edges connect consecutive nodes
- Frontend `RPAWorkflowsPage.js`: new "Import from Recording" button opens modal listing user's saved recordings
- Modal shows recording name, description, step count, date; one-click converts and navigates to editor

### 2026-06-09 — ResizeObserver Error Suppression
- Added global handlers in `index.js` to suppress the harmless "ResizeObserver loop" warning from react-flow in CRA dev mode
- Production builds are unaffected (this warning never appears in production)

### Deployment Readiness Verified
- VPS deploy via `.github/workflows/deploy.yml` — rsync excludes `.env`, `node_modules`, `__pycache__`, `.git` (matches user's existing pipeline)
- Electron desktop build via `build-electron-desktop.yml` — independent build, bundles backend + frontend, runs on 127.0.0.1:8088 — new `/api/rpa/*` and `/api/banners/*` endpoints will work without changes
- Windows installer build via `build-windows-release.yml` — independent of new modules
- All new files compile cleanly (Python + JS)
- No hardcoded URLs or secrets in new files (only example.com placeholder hint inside param-helper UI)
- Both modules register cleanly in server.py with try/except — won't break startup if anything fails
- `.gitignore` correctly keeps `.env` excluded — VPS has its own env file already deployed
- ✓ Banner created via admin UI, appears on customer dashboard with theme + CTA + dismiss
- ✓ RPA workflow created (`Test WF` with goto + click nodes), saved
- ✓ RPA workflow run successfully: goto → wait → screenshot all completed
- ✓ Live progress polling works, step events stream
- ✓ Backend logs: "Banner module loaded" + "RPA Studio module loaded"

## Files Changed (git status)
- M backend/server.py (added 2 module registration blocks)
- M frontend/package.json (added reactflow)
- M frontend/src/App.js (added 4 routes)
- M frontend/src/components/DashboardLayout.js (added BannerBar + RPA Studio menu)
- M frontend/src/pages/AdminDashboard.js (added Banners button)
- NEW backend/banner_module.py
- NEW backend/rpa_studio_module.py
- NEW frontend/src/components/BannerBar.js
- NEW frontend/src/pages/AdminBannersPage.js
- NEW frontend/src/pages/RPAStudioPage.js
- NEW frontend/src/pages/RPAWorkflowsPage.js
- NEW frontend/src/pages/RPARunsPage.js

## P0/P1/P2 Backlog
**P1 (nice to have, not blocking):**
- Live recording mode for RPA Studio (like Visual Recorder integration — record clicks as nodes)
- Live inspector overlay (hover element → show selector/XPath, click to copy)
- Workflow scheduler (cron-style: one-time / daily / weekly / monthly)
- Templates Marketplace with admin-curated workflows
- Multi-thread runner for local-mode execution
- Step-by-step debugger with breakpoints
- Workflow groups (collapse multiple steps visually)

**P2 (future enhancement):**
- 2Captcha full integration (currently stub)
- Google Sheets read/write full integration (gsheet_writer adapter)
- WebSocket-based live frame streaming (currently polling-based screenshot)
- Sub-workflow node passing (variables in/out)
