#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Native PC dashboard ka "RECENT ACTIVITY" panel kabhi bhi koi activity show nahi karta —
  "No recent activity yet." hi aata rehta hai. Bridge_jobs (Visual Recorder, RUT, Form Filler,
  AdsPower, etc.) chal rahe hote hain magar dashboard pe nazar nahi aate.
  Active Heavy Jobs bhi sirf bare "job" rows dikhata hai bina kisi description ke.

backend:
  - task: "Native dashboard /api/desktop/stats — Active + Recent jobs query"
    implemented: true
    working: true
    file: "backend/desktop_module.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: false
        agent: "user"
        comment: "Recent Activity panel always empty even when jobs were running"
      - working: true
        agent: "testing"
        comment: "11/11 unit + 1 integration test PASSED — wrong field-name regression fixed"

  - task: "Browser Profile launch — crash visibility + un-stick from 'launching'"
    implemented: true
    working: true
    file: "backend/browser_profile_launcher.py, backend/browser_profile_module.py, frontend/src/pages/BrowserProfilesPage.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false

  - task: "Dependency auto-detection + pre-launch checks (Chromium/Playwright/ADB)"
    implemented: true
    working: true
    file: "backend/desktop_module.py, backend/browser_profile_launcher.py, desktop/static/{index.html,dashboard.js,style.css}"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: false
        agent: "user"
        comment: |
          "ap check kro kuch b missing ni hona chahye har feature k liye jo b installed
          chahye ho jab jo app install kre user sab kuch automatic install ho kuch b
          miss na ho jis ki waja se koi error ay"
      - working: true
        agent: "main"
        comment: |
          Added comprehensive dependency health system so customers see at a
          glance which features are usable and which are still installing:

          1) `_dependency_health()` in desktop_module.py reports state of:
             - Playwright Python package (importable?)
             - Chromium binary (ready/installing/missing/error — pulled from
               real_user_traffic.get_engine_status which knows EXACT revision
               required by the installed Playwright)
             - ADB (Android Debug Bridge) — needed for CPI Android flow
             Each entry has actionable {status, message, expected_revision}.

          2) `/api/desktop/stats` endpoint now returns `dependencies: {...}`
             so the Native dashboard shows a "Feature Dependencies" card
             with traffic-light status per dep.

          3) `launch_profile_session()` now has a PRE-FLIGHT chromium check
             BEFORE attempting to launch Playwright. If status is:
             - "ready"      → proceed
             - "installing" → notify error: "wait 60s and try again"
             - "missing"    → auto-kick-off install + notify "downloading,
                              retry once banner clears"
             Previously the customer just got a cryptic Playwright crash.

          4) Native dashboard UI (index.html/dashboard.js/style.css) now
             renders a 2-column dependency grid card with green/yellow/red
             dots + actionable messages. Summary chip shows "N/N ready".

          Tests: 25/25 PASS — 8 new tests cover all dependency states
          (ready/installing/missing/error) + graceful failure when the
          engine status helper itself crashes.

agent_communication:
  - agent: "main"
    message: |
      Phase 3 — Comprehensive dependency auto-detection completed.
      Total test count: 25/25 pass (11 desktop-stats + 6 browser-profile + 8 deps).

      Files modified in this round:
        - backend/desktop_module.py            (new _dependency_health helper)
        - backend/browser_profile_launcher.py  (chromium pre-flight check)
        - desktop/static/index.html            (new deps card)
        - desktop/static/dashboard.js          (new renderDeps fn)
        - desktop/static/style.css             (new .dep-item styles)

      Coverage of customer-install dependencies:
        ✅ Chromium binary (Playwright engine — used by RUT, Visual Recorder,
           Browser Profiles, Form Filler)
        ✅ Playwright Python package
        ✅ ADB (Android Platform-Tools — CPI Android flow)
        ✅ MongoDB (already tracked in desktop_stats.database)
        ✅ Cloud heartbeat link (already tracked in desktop_stats.cloud)
        ✅ License (already tracked in desktop_stats.license)

      Behaviour change summary:
        - Before: customer clicks Launch → Playwright crashes with cryptic
          "Executable doesn't exist at /pw-browsers/chromium_..." stack trace
          → profile stuck on "launching" forever (with previous round's fix
          this at least became a visible error, but error text was Playwright
          jargon).
        - After: customer clicks Launch →
            - chromium ready → launches normally
            - chromium installing → friendly "Downloading… wait 60s" toast
            - chromium missing → auto-triggers install + "Downloading…" toast
          AND the dashboard ALWAYS shows the dep grid so customers can SEE
          the state without trying Launch first.

      No regressions on previous fixes — all 25 tests pass.
    status_history:
      - working: false
        agent: "user"
        comment: |
          Browser profile launch karne pe card "launching" status pe hamesha ke liye
          stuck reh jata hai — Chromium open nahi hota. User screenshot showed
          "Launch queued — your Krexion desktop app will open the browser shortly."
          message but the profile status never moves from "launching" → "running"
          or "error".
      - working: "NA"
        agent: "main"
        comment: |
          Root cause: `launch_profile_session()` in browser_profile_launcher.py was
          called as `asyncio.create_task(...)` from BOTH callers (sync_client.py L738,
          browser_profile_module.py L563 local-desktop direct). Any failure BEFORE
          the in-body `on_session_update("running")` call (Playwright import failure,
          Chromium launch crash, OOM, proxy probe explosion, etc.) silently raised
          into the event loop's void — cloud's `_bridge/session-update` was NEVER
          notified — profile DB row stuck at "launching" forever.

          Fix applied:
          1. browser_profile_launcher.py:
             - Split into outer wrapper + `_launch_profile_session_inner`
             - Outer wrapper has try/except + finally that:
                 a) Calls on_session_update({status:"error", error_message: ...})
                    on ANY failure (Playwright import OR inner launch crash)
                 b) Returns a dict instead of letting the exception escape
                    the asyncio task void
                 c) ALWAYS pops _RUNNING_SESSIONS entry (no slot leak)
             - Error-notify callback itself is wrapped so a flaky cloud
               connection during the notify can't re-trigger silent crash.
          2. browser_profile_module.py /_bridge/session-update endpoint:
             - Now accepts + persists `error_message` field
             - Stores as `profile.last_error` and `session.error_message`
             - Clears `last_error` on next successful "running" update
          3. frontend BrowserProfilesPage.js:
             - Added red 'error' status badge variant (was falling through to grey)
             - Surfaces `p.last_error` text below card buttons (italic red)

          Tests (6 new pytest cases, all PASSING):
            - Playwright import failure → cloud notified, card un-sticks ✓
            - Inner launch crash → cloud notified + _RUNNING_SESSIONS cleaned ✓
            - Crash without callback → still cleans up ✓
            - Successful launch → result forwarded unchanged ✓
            - Callback itself crashing → wrapper doesn't propagate ✓
            - Concurrent launches isolate session_ids ✓

agent_communication:
  - agent: "main"
    message: |
      Two bug fixes applied. Ran pytest in /app/krexion_repo/backend:
      - tests/test_desktop_stats_fix.py            → 11/11 PASS
      - tests/test_browser_profile_launch_fix.py   → 6/6 PASS
      Total: 17/17

      Please verify the Browser Profile launch fix by:
      1. Running the new pytest test suite (`tests/test_browser_profile_launch_fix.py`)
         and confirming all 6 tests pass.
      2. Confirming the wrapper structure: `launch_profile_session` now contains
         a top-level try/except that calls a `_notify_error()` helper on ANY
         failure path, and a `finally` that clears `_RUNNING_SESSIONS[session_id]`.
      3. Confirming the `_bridge/session-update` endpoint persists the new
         `error_message` → `last_error` field correctly:
            - status="error" + error_message="x" → profile.last_error = "x"
            - status="running" → profile.last_error = ""  (cleared)
            - status="closed"/"stopped" without error_message → last_error untouched

      Read-only / safety notes:
        - Only 3 files modified across backend + frontend
        - No DB schema changes (last_error is just a new optional string field)
        - No public API contract breakage — error_message is OPTIONAL on the
          session-update body, and old clients (sync_client < v2.1.59) simply
          won't send it (everything continues to work for them).