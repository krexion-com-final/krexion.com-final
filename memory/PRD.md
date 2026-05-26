# Krexion — PRD / Work Log

## Original problem statement
User: dennisedmaartins9-sudo
Repo: https://github.com/dennisedmaartins9-sudo/krexion.com.git (public, collaborator access)
Workflow:
1. Load repo into Emergent preview without breaking anything
2. User provides bug fixes / feature requests
3. Save changes to main branch via "Save to Github" feature → VPS auto-deploys
4. Customer-facing updates show in admin panel's release page
5. CRITICAL: Nothing must break, nothing deleted, no conflict on save-to-github

## Architecture (existing — preserved as-is)
- Backend: FastAPI + MongoDB + Playwright (RUT engine, CPI, License, Crypto, Sync, Bridge, AdsPower, Releases, Visual Recorder)
- Frontend: React 18 + craco + Tailwind + shadcn/ui
- Deploy: VPS via docker-compose / GitHub auto-deploy

## Test credentials (preview)
- Admin: admin@krexion.local / admin123
- Test User: test@krexion.local / test1234 (status=pending → admin se approve karen)

## Iteration #1 — 2026-01-26
### Repo setup
- Synced into /app — preserved `.emergent` config, kept user's `.git` (origin → dennisedmaartins9-sudo/krexion.com, branch main)
- env files configured, deps installed (`pip install`, `yarn install`)
- Services running via supervisor: backend (:8001), frontend (:3000), mongodb

### Feature: Visual Recorder — Edit Step
- Backend: `update_step()` in visual_recorder.py + `PATCH /api/visual-recorder/{id}/step/{idx}` endpoint
- Frontend: Pencil edit button per step + Edit Modal with selector/value/timeout/key/ms/state/match_by/humanize/name fields. `action` is read-only.
- Per-step `humanize: false` opt-out for fill/type (skips slow ~18s human-typing; default true preserves existing anti-detect behavior)

## Iteration #2 — 2026-01-26
### Feature A: Smart Selector Suggester
When a step fails (e.g., `#birth_month` not found), user clicks "🔍 Find similar" in the Edit modal → backend scans live page DOM for elements where id/name/aria-label/placeholder/class contains tokens from the failed selector → returns ranked top-N candidates → one-click apply.

- Backend `suggest_selectors()` in visual_recorder.py — token extraction handles CSS (#id, [name=x]) AND XPath (@id='x') + camelCase + snake_case splits
- Endpoint: `GET /api/visual-recorder/{id}/suggest-selectors?failed=<sel>&limit=10`
- DOM scan via single `page.evaluate()` — scores by id-exact (10) / name-exact (8) / id-contains (5) / aria-or-label (3) / class (1)
- Returns: selector, tag, input_type, id, name, label, placeholder, visible flag, matched_tokens, score
- Frontend: "Find similar" button in Edit modal selector field; suggestions panel with one-click apply; shows matched tokens + label + hidden flag

### Feature B: Manual Add Step (CSS + XPath)
"+ Add Step" button in steps panel → opens creation modal where user picks action type and supplies selector (CSS or XPath), value, timeout, etc. Playwright auto-detects XPath at replay time (selectors starting with `//` or `xpath=`).

- Backend `add_manual_step()` in visual_recorder.py — whitelisted actions: wait_for_selector, click, fill, type, select, press, wait, wait_for_load/navigation/networkidle, hover, check, uncheck, screenshot
- Endpoint: `POST /api/visual-recorder/{id}/manual-step` (body: {step, position?})
- Tagged with `source: "manual"` for UI distinction
- Sensible default timeouts (8000ms element actions, 1000ms wait)
- Frontend: "Add Step" button next to Undo; Manual Step modal with action-aware fields (selector/value/key/timeout/ms/state/match_by/humanize/position)

## What's NOT changed (preserved per user's safety requirement)
- All 582 original repo files preserved
- All existing endpoints, modules, components untouched
- Existing fill/type human-typing default behaviour intact (anti-detect)
- Step `action` field in Edit modal is intentionally NOT editable (would break replay)

## Files modified across both iterations
- `backend/visual_recorder.py` (+240 lines — update_step, add_manual_step, suggest_selectors)
- `backend/server.py` (+40 lines — 3 new endpoints: PATCH step, POST manual-step, GET suggest-selectors)
- `backend/real_user_traffic.py` (humanize opt-out — 2 places)
- `frontend/src/pages/VisualRecorderPage.js` (+552 lines — Edit modal, Suggester UI, Manual Add modal, helpers)

## Backlog / Future
- P2: Suggester preview — hover a suggestion to highlight that element on the live screenshot
- P2: Bulk-edit timeout across multiple steps
- P2: Save user-edited selectors as "Smart Aliases" so future recordings auto-detect them
