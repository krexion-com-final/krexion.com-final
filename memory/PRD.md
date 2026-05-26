# Krexion — PRD / Work Log

## Original problem statement
User: dennisedmaartins9-sudo
Repo: https://github.com/dennisedmaartins9-sudo/krexion.com.git
Workflow: load repo → user fixes/features → user runs "Save to Github" → VPS auto-deploys

## Test credentials
- Admin: admin@krexion.local / admin123
- User: test@krexion.local / test1234 (pending; admin approves)

## Iteration history
1. Repo sync + Edit Step (PATCH endpoint + pencil button + Edit modal + humanize opt-out)
2. Smart Selector Suggester + Manual Add Step (CSS/XPath)
3. Selector Preview on Hover (blue pulse overlay on screenshot, right-docked modal)
4. Selector Aliases (self-healing replay, MongoDB persistent memory per user+domain)

## Iteration #5 — 2026-01-26 — Bug Fix + Smart Error→Fix Suggester

### Bug Fix: "Execution context was destroyed during evaluate"
Reproduced from user's screenshot: `Step 1 (evaluate) failed: Page.evaluate: Execution context was destroyed, most likely because of a navigation`

**Root cause**: The recorded `evaluate` JS clicks a button (e.g., UNLOCK NOW) which triggers immediate page navigation. Playwright's JS context dies before `evaluate()` resolves → exception. BUT the click actually succeeded — navigation IS what we wanted.

**Fix**: Wrap `await page.evaluate(js)` in try/except. If the error mentions "execution context" / "navigation" OR if `page.url` changed (proof navigation happened), swallow the error and continue. Applied in BOTH places:
- `_execute_automation_steps` (main step loop) — `backend/real_user_traffic.py:7841`
- `_dispatch_single_action` (self-heal recovery path) — same file ~8362

### Feature: Smart Error → Fix Suggester (Live Test panel)
When Live Test fails, the user now sees:
1. **Raw error** (unchanged, in red)
2. **WHY THIS HAPPENED** — plain-language cause (lightbulb icon)
3. **SUGGESTED FIX** — concrete action to take (sparkles icon)
4. **One-click action button** — Edit step, Re-run, Add wait, Discard/restart depending on error type

`getSuggestedFix()` recognises 9 common error patterns:
- Execution context destroyed → "auto-handled; re-run"
- Selector exhausted variants → "Find similar" in Edit modal
- Wait timeout → "increase timeout / change state / find similar"
- Element not visible → "change State to attached"
- Net error / nav timeout → "check URL / proxy"
- Captcha → "switch proxy or UA"
- Target/browser closed → "discard + restart"
- Frame detached → "add a wait step before"
- Fill/type fail → "find similar OR uncheck human typing"

Each suggestion shows a colour-coded action button that opens the right modal pre-filled.

### Run Live Test from Start (clarified UX)
- Button label changed to **"Run Live Test from Start"**
- Sub-caption: "Opens a fresh browser tab and replays your steps from step 0"
- Already passes `fresh_page: true` to the API (no backend change needed)
- Makes it explicit that this is full-flow validation, not partial replay

## Cumulative files
- `backend/visual_recorder.py` — Edit, Manual Add, Suggester, bbox, update_step_with_alias
- `backend/server.py` — 8+ endpoints, selector_aliases binding
- `backend/real_user_traffic.py` — extra_alts on smart helpers, user_id threading, evaluate navigation-fix
- `backend/selector_aliases.py` — self-healing memory store
- `frontend/src/pages/VisualRecorderPage.js` — all UI: Edit, Find similar, Hover preview, Manual Add, Aliases panel, Smart fix suggester

## Safety
All 582 original files preserved. All changes ADDITIVE — defaults preserve old behaviour. Anti-detect intact.

## Backlog
- P2: Auto-run "Find similar" on failure (no manual click needed)
- P2: Step-level "Re-run from here" — pick up replay mid-flow after fix
- P3: Community alias DB (shared knowledge base)
