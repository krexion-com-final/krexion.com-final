# Krexion — PRD / Work Log

## Original problem statement
User: dennisedmaartins9-sudo
Repo: https://github.com/dennisedmaartins9-sudo/krexion.com.git
Workflow: load repo → user fixes/features → "Save to Github" → VPS auto-deploys
CRITICAL: Nothing breaks, nothing deleted.

## Test credentials
- Admin: admin@krexion.local / admin123
- User: test@krexion.local / test1234 (pending; admin approves)

## Iteration history
1. Visual Recorder — Edit Step (pencil + Edit modal + humanize opt-out)
2. Smart Selector Suggester + Manual Add Step (CSS + XPath)
3. Selector Preview on Hover (blue pulse overlay, right-docked modal)
4. Selector Aliases — self-healing replay (MongoDB persistent memory per user+domain)
5. Bug fix: "Execution context destroyed" during evaluate + Smart Error→Fix Suggester

## Iteration #6 — 2026-01-26 — Post-Finalize Live Visual Test + JSON Editor

### Feature A: Live Visual Test (Step-by-Step) — on Recording Complete page
"Recording Complete!" screen ke top par naya blue button. Click karne par:
1. Frontend POSTs `/visual-recorder/start` with saved URL/proxy/UA/headers/sample_row
2. Polls `/state` until session ready (60 × 500ms = 30s budget)
3. POSTs `/visual-recorder/{sid}/import-steps` with the finalized JSON
4. Transitions UI back to `setupStage = "recording"` so the live screenshot panel + steps panel are visible
5. User can immediately click **"Run Live Test from Start"** — full automation replays end-to-end with screenshots updating live
6. If any step fails, the **Smart Fix Suggester** panel (from iteration #5) shows cause + one-click fix action
7. User can edit any step (pencil), use Find Similar, view alias panel, then re-Finalize

### Feature B: Inline JSON Editor — on Recording Complete page
"Preview JSON" header ab "Edit JSON" pencil button include karta hai. Click karne par:
- `<pre>` becomes a full-height resizable `<textarea>` with monospace + amber border
- "Save JSON Changes" validates:
  - Must be valid JSON
  - Must be an array
  - Not empty
  - Each item must be object with `action: string`
- On error: red inline error message with specific reason
- On success: replaces `finalBundle.automation_json` (used by Copy / Download / Save / Visual Replay)
- "Cancel" reverts without applying

### Backend
- `import_steps(sess, steps)` in visual_recorder.py — bulk replace steps with light validation
- `update_session_data(sess, sample_row?, headers?)` — sync inputs from the imported bundle
- New endpoint: `POST /api/visual-recorder/{session_id}/import-steps` body `{steps, sample_row?, headers?}`

### Verification ✅
- Backend restart clean
- Frontend webpack compiled (1 pre-existing warning)
- ESLint passed
- `import-steps` endpoint returns 404 on invalid session (auth working)
- Git diff: 3 files, +294 / -10 (additive)

### Safety
- Existing Finalize → save / copy / download flow unchanged
- Live Visual Test creates a FRESH session (doesn't mutate the saved bundle until re-finalize)
- JSON editor is opt-in via button — default view shows colorized read-only preview
- Validation prevents broken JSON from corrupting replay
- 582 original files preserved

## Cumulative files
- `backend/visual_recorder.py` — Edit, Manual Add, import_steps, update_session_data, Suggester, bbox, update_step_with_alias
- `backend/server.py` — 9+ endpoints, selector_aliases binding, import-steps
- `backend/real_user_traffic.py` — extra_alts on smart helpers, user_id threading, evaluate nav-fix
- `backend/selector_aliases.py` — self-healing memory store
- `frontend/src/pages/VisualRecorderPage.js` — ALL UI (Edit modal, Find similar, Hover preview, Manual Add, Aliases panel, Smart Fix suggester, Live Visual Test on finalize, JSON inline editor)

## Backlog
- P2: Step-level "Replay from here" (pick up replay mid-flow after fix)
- P2: JSON editor with live syntax-highlighted edit (CodeMirror) instead of plain textarea
- P3: Community alias DB (shared selector drift knowledge base)
