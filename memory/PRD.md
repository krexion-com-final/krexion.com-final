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
- Test User: test@krexion.local / test1234 (status=pending)

## Iteration #1 — 2026-01-26
### Implemented
- **Repo synced into /app** — preserved `.emergent` config, kept user's `.git` (origin → dennisedmaartins9-sudo/krexion.com, branch main)
- **env files configured**: backend/.env (MONGO_URL, DB_NAME=krexion, JWT, APP_URL, admin creds), frontend/.env (REACT_APP_BACKEND_URL, WDS_SOCKET_PORT)
- **All dependencies installed**: pip install -r requirements.txt, yarn install
- **Services running** via supervisor: backend (:8001), frontend (:3000), mongodb

### Feature: Visual Recorder — Edit Step (NEW)
Files touched (ADDITIVE — no existing logic removed):
- `backend/visual_recorder.py` — added `update_step()` + `_EDITABLE_STEP_FIELDS` whitelist
- `backend/server.py` — added `PATCH /api/visual-recorder/{session_id}/step/{index}` endpoint
- `backend/real_user_traffic.py` — added per-step `humanize: false` opt-out in fill/type handlers (BOTH `_execute_automation_steps` AND `_dispatch_single_action`). Defaults to True → no behaviour change for existing recordings.
- `frontend/src/pages/VisualRecorderPage.js` — added Pencil edit button per step, Edit modal with selector / value / timeout / key / ms / state / match_by / humanize / name fields. `action` is read-only.

Fixes the user's reported scenario:
- Live Test FAILED on `#birth_month` (selector not found) → user can now edit selector + bump timeout from the UI instead of deleting + re-recording.
- Slow 18s FILL → explained as intentional human-typing for anti-detect; user can now opt-out per step via the new "Human-like typing" checkbox.

## What's NOT changed (preserved per user's safety requirement)
- All 582 original repo files
- All existing endpoints, modules, components
- Existing fill/type human-typing default behaviour (anti-detect intact)
- Step `action` field is intentionally NOT editable (would break replay)

## Backlog / Future
- P2: Add "Edit step" support for `goto` action (URL change)
- P2: Bulk-edit timeout across multiple steps at once
- P2: "Auto-suggest selector" — when a step fails, query the live page for nearby elements and suggest alternatives in the Edit modal
