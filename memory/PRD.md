# Krexion — PRD / Work Log

## Original problem statement
User: dennisedmaartins9-sudo
Repo: https://github.com/dennisedmaartins9-sudo/krexion.com.git (public, collaborator)
Workflow: load repo → user requests fixes/features → save to GitHub main → VPS auto-deploys
CRITICAL: Nothing must break / delete / conflict.

## Test credentials (preview)
- Admin: admin@krexion.local / admin123
- Test User: test@krexion.local / test1234 (status=pending)

## Iteration #1 — Visual Recorder Edit Step
- `PATCH /api/visual-recorder/{id}/step/{idx}` + pencil button + Edit Modal
- Per-step `humanize: false` opt-out for fill/type

## Iteration #2 — Smart Suggester + Manual Add Step (CSS + XPath)
- `GET /suggest-selectors` — DOM token-match scan
- `POST /manual-step` — adds any step manually
- Frontend buttons + modals

## Iteration #3 — Selector Preview on Hover
- `GET /selector-bbox` returns bounding box
- Edit modal repositioned right-dock (light backdrop) so screenshot stays visible
- Blue pulse overlay + label on hover

## Iteration #4 — Selector Aliases (Self-Healing Replay) ✨ NEW
**The big one.** When user fixes a wrong selector (e.g., `#birth_month` → `#dob_month`),
the mapping is saved PERMANENTLY for (user_id, domain). Future replays auto-recover.

### New module: `backend/selector_aliases.py`
- MongoDB collection `selector_aliases`
- Doc: `{user_id, domain, original, aliases: [str], hit_count, created_at, updated_at, last_used_at, last_alias_used}`
- Functions: `save_alias()`, `get_aliases_for_domain()`, `record_hit()`, `list_all_for_user()`, `delete_alias()`, `extract_domain()`
- Bound to main_db in server.py

### Backend wiring
- `update_step_with_alias()` in visual_recorder.py — async wrapper that auto-saves alias when selector changes
- `_smart_wait_for_selector(extra_alts=...)` — alias selectors inserted AHEAD of token-derived fallbacks
- `_wait_for_actionable_selector(extra_alts=...)` — same retry-with-aliases on actionable wait
- `_execute_automation_steps(user_id=...)` — pre-loads aliases for current page domain; passes to all smart helpers via `_alias_alts_for()`
- Wired into BOTH Live Test (`live_test()` passes `sess.user_id`) AND RUT job replay (passes `link_owner_id`)

### Endpoints (new)
- `GET /api/visual-recorder/aliases` — list user's aliases
- `DELETE /api/visual-recorder/aliases?domain=...&original=...` — revoke a rule

### Frontend
- Toast on successful save: "🧠 Selector alias saved — future runs will auto-heal"
- **"Aliases" button** (Brain icon) in steps-panel header → opens Aliases panel modal
- Aliases modal lists: domain, hit-count badge ("✓ 3 rescues"), original (red) → alias chain (newest=green, older=grey), last-used timestamp, delete button
- Empty state with explanation

### Verification
- Module loads: `Selector Aliases module loaded — self-healing replay enabled` ✓
- End-to-end DB test passed: save/upsert/retrieve/hit-count/list/delete all work ✓
- Endpoints respond correctly under auth ✓
- Frontend webpack compiled, 1 pre-existing warning ✓

## Cumulative files modified
- `backend/visual_recorder.py` — update_step, update_step_with_alias, add_manual_step, suggest_selectors, selector_bbox
- `backend/server.py` — 6 new endpoints + selector_aliases binding
- `backend/real_user_traffic.py` — `extra_alts` param on smart helpers + alias preload + `user_id` threading
- `backend/selector_aliases.py` — NEW module (self-healing memory store)
- `frontend/src/pages/VisualRecorderPage.js` — all UI for Edit, Suggester, Hover Preview, Manual Add, Aliases panel

## Safety
- All 582 original repo files preserved
- All changes ADDITIVE — `extra_alts` param defaults to None, `user_id` to None → zero behaviour change without aliases
- Anti-detect human typing intact

## Backlog
- P2: "Suggest from screenshot" — let user click on the screenshot to pick the correct element when selector breaks
- P2: Auto-suggest aliases on Live Test failure (run suggester automatically when a step fails)
- P3: Share alias rules across users for the same domain (community-curated selector drift database)
