# Krexion — PRD / Work Log

## Original problem statement
User: dennisedmaartins9-sudo
Repo: https://github.com/dennisedmaartins9-sudo/krexion.com.git
Workflow: load repo → user fixes/features → "Save to Github" → VPS auto-deploys
CRITICAL: Nothing breaks / deleted. Only updates and improvements — permanently.

## Test credentials (Preview)
- Admin: admin@krexion.local / admin123
- User: test@krexion.local / test1234

## Iteration history
1. Visual Recorder — Edit Step (pencil + Edit modal + humanize opt-out)
2. Smart Selector Suggester + Manual Add Step (CSS + XPath)
3. Selector Preview on Hover (blue pulse overlay)
4. Selector Aliases — self-healing replay (MongoDB per user+domain)
5. Bug fix: evaluate navigation + Smart Error→Fix Suggester
6. Post-Finalize Live Visual Test + JSON Editor
7. Step-Level "Replay from Here"
8. **Visual Recorder + RUT Universal Compatibility — 4 Phases (2026-01-29)** ⭐

## Iteration #8 — 2026-01-29 — Universal Compatibility (4 PHASES)

### Phase 1: Universal Compatibility
- Iframe auto-detection (selector falls back to iframes when missing on main frame)
- Shadow DOM piercing probe (supports `>>` in selectors)
- Auto cookie/GDPR banner dismissal at start of every automation
- Multi-tab/popup follower helper
- Extended bot detection (Cloudflare Turnstile, hCaptcha, DataDome, PerimeterX, Imperva, Akamai BMP, Arkose, GeeTest, reCAPTCHA v2/v3)

### Phase 2: Powerful Step Types
- `wait_for_text` — wait until specific text appears
- `wait_for_url` — wait until URL matches contains/equals/regex
- `extract` — capture text/attribute into a variable (`{{var_name}}`)
- `dismiss_popups` — explicit cookie banner dismissal step
- Per-step `retry: N, retry_delay: ms` — automatic retry on failure
- Per-step `if_exists: true` — skip step if selector not present (random popups)

### Phase 3: UX Improvements
- Step icons + color coding (click=green, fill=sky, select=purple, etc.)
- "Test from here" button on every step (not just failed step)
- Plain-English error messages (Roman-Urdu/English hints) on failures
- Pre-flight lint endpoint + UI panel (catches missing selectors, hard-waits >30s, invalid actions)
- Cookie/Popup/Wait-text/Wait-URL/Extract quick-add buttons in toolbar

### Phase 4: Real User Traffic Enhancements
- Placeholder formatter pipeline: `{{first_name|upper}}`, `{{phone|digits|last:4}}`, `{{email|trim|lower}}`, `{{missing|default:N/A}}`
- Supports formatters: upper, lower, title, trim, digits, alpha, alnum, reverse, first:N, last:N, slice:A:B, default:X
- Auto cookie banner dismissal at start of every visit
- Friendly_hint field surfaced in step failure responses
- 100% backward compatible — all existing recordings/JSONs work unchanged

### Architecture
- New file: `backend/automation_extensions.py` (631 lines) — all helpers in one module, loaded conditionally with try/except so failures don't break the app.
- All modifications to `real_user_traffic.py`, `visual_recorder.py`, `server.py` are ADDITIVE — no functions removed, no logic broken.
- 8 new server.py endpoints added (visual-recorder/{id}/add-wait-text, /add-wait-url, /add-extract, /add-dismiss-popups, /lint, lint-steps, etc.)
- Frontend: 4 new step-builder buttons + lint button + per-step "Test from here" + step icons + friendly hint panel.

### Verification
- Backend boots clean (extensions module loaded successfully)
- All existing endpoints unchanged + 8 new endpoints active
- Lint endpoint tested with valid and invalid steps — friendly Roman-Urdu messages
- Formatter pipeline tested — all 12 formatters working
- Substitution backward-compatible — legacy `{{key}}` works AND `{{random.N}}` works
- Frontend builds successfully (635 KB gzipped)
- ESLint clean / Ruff clean

### Safety Guarantees Met
✅ No existing functions removed
✅ No existing endpoints removed
✅ No existing step types removed
✅ All new step types are OPT-IN (only used when user adds them)
✅ All new fields are OPT-IN (default behavior unchanged when fields not set)
✅ Failures in new helpers are SWALLOWED (degraded gracefully to old behavior)
✅ Existing JSON automations continue to work exactly as before

### Files modified (lines added/removed)
- `backend/real_user_traffic.py`: +263 / -53 (heavily additive)
- `backend/server.py`: +123 / 0
- `backend/visual_recorder.py`: +127 / -7
- `frontend/src/pages/VisualRecorderPage.js`: +234 / -16
- `backend/automation_extensions.py`: +631 (new)
- Total: ~1380 additive lines

## Cumulative files modified
- backend/visual_recorder.py — Edit, Manual Add, import_steps, Suggester, bbox, update_step_with_alias, live_test(start_index), **NEW: lint_session + 4 new step builders**
- backend/server.py — 10+ endpoints, selector_aliases binding, _VRLiveTestReq.start_index, **NEW: 6 new endpoints**
- backend/real_user_traffic.py — extra_alts on smart helpers, user_id threading, evaluate nav-fix, **NEW: 4 new actions, retry, if_exists, iframe fallback, formatters, auto-cookie-dismiss**
- backend/selector_aliases.py — self-healing memory store
- backend/automation_extensions.py — **NEW MODULE: cookie dismiss, bot detect, iframe lookup, shadow probe, extract, wait_for_text/url, formatters, friendly errors, lint, retry, popup follow**
- frontend/src/pages/VisualRecorderPage.js — ALL UI features + **NEW: lint panel, step icons, test-from-here on every step, friendly hint, 4 new step-add buttons**

## Backlog
- P2: Per-step "Replay from here" icon visual treatment (Phase 3 #11 partially done — basic ⏵ button added on every step)
- P2: CodeMirror-based JSON editor (live syntax highlighting + folding)
- P3: Community alias DB
- P3: Step grouping/collapsible sections (Phase 3 #15)
- P3: Live test progress bar (Phase 3 #5)
