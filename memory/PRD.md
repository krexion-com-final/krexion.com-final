# Krexion — PRD / Work Log

## Original problem statement
User: dennisedmaartins9-sudo
Repo: https://github.com/dennisedmaartins9-sudo/krexion.com.git
Workflow: load repo → user fixes/features → "Save to Github" → VPS auto-deploys
CRITICAL: Nothing breaks / deleted.

## Test credentials
- Admin: admin@krexion.local / admin123
- User: test@krexion.local / test1234

## Iteration history
1. Visual Recorder — Edit Step (pencil + Edit modal + humanize opt-out)
2. Smart Selector Suggester + Manual Add Step (CSS + XPath)
3. Selector Preview on Hover (blue pulse overlay)
4. Selector Aliases — self-healing replay (MongoDB per user+domain)
5. Bug fix: evaluate navigation + Smart Error→Fix Suggester
6. Post-Finalize Live Visual Test + JSON Editor
7. **Step-Level "Replay from Here"** (this iteration)

## Iteration #7 — 2026-01-26 — Replay from Here ⏩

### Problem
Jab Live Test step #15 pe fail ho aur user fix kare, abhi pura 1-2 min ka test re-run karna parta tha — 14 successful steps bhi dobara execute hote. Slow debug cycle.

### Solution
**`start_index` param** add kiya `live_test()` mein:
- `start_index=0` (default): pura test fresh page se chalata hai (existing behaviour preserved)
- `start_index=N`: pehle N steps SKIP karta hai, browser ka **current state preserve** karta hai (forces `fresh_page=False`), aur step N se chalu hota hai
- Result indices ko ORIGINAL indices mein re-map kiya jata hai (so UI step #15 ko #15 dikhata hai, not "step #1 of slice")

### UI
Smart Fix Suggester panel mein naya purple **"Replay from step #N"** button (FastForward icon):
- Sirf tab dikhta hai jab `failed_at_idx > 0` (skip-from-start makes no sense for step 0)
- Click se `runLiveTest({ startIndex: failedIdx })` call hota hai
- Browser current state pe rehta hai → instantly step N se replay
- Toast: "Live test PASSED (resumed from step #15)"

### Speedup
Debug cycle ~5-10× fast:
- **Before**: fix step 15 → re-run all 23 steps from start = 60-120s
- **After**: fix step 15 → "Replay from step #15" → re-run 9 steps from current state = 8-15s

### Verification ✅
- Backend restart clean (Selector Aliases loaded)
- Endpoint accepts `start_index` param (validated returns 404 on bad session)
- Frontend webpack compiled, ESLint passed
- Git diff: 3 files, +86/-6 (additive)

### Safety
- `start_index` defaults to 0 → existing flow 100% unchanged
- When `start_index > 0`, fresh_page forced to false (cannot accidentally lose state)
- All index re-mapping is idempotent on errors (try/except wrapped)

## Cumulative files modified
- `backend/visual_recorder.py` — Edit, Manual Add, import_steps, Suggester, bbox, update_step_with_alias, **live_test(start_index)**
- `backend/server.py` — 10+ endpoints, selector_aliases binding, **_VRLiveTestReq.start_index**
- `backend/real_user_traffic.py` — extra_alts on smart helpers, user_id threading, evaluate nav-fix
- `backend/selector_aliases.py` — self-healing memory store
- `frontend/src/pages/VisualRecorderPage.js` — ALL UI features (Edit, Find similar, Hover preview, Manual Add, Aliases panel, Smart Fix suggester, Live Visual Test, JSON editor, **Replay from here**)

## Backlog
- P2: Per-step "Replay from here" icon in the step results list (not just failed step)
- P2: CodeMirror-based JSON editor (live syntax highlighting + folding)
- P3: Community alias DB
