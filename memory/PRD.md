# Krexion — PRD / Work Log

## Original problem statement
User: dennisedmaartins9-sudo
Repo: https://github.com/dennisedmaartins9-sudo/krexion.com.git (public, collaborator access)
Workflow:
1. Load repo into Emergent preview without breaking anything
2. User provides bug fixes / feature requests
3. Save changes to main branch via "Save to Github" feature → VPS auto-deploys
4. CRITICAL: Nothing must break, nothing deleted

## Test credentials (preview)
- Admin: admin@krexion.local / admin123
- Test User: test@krexion.local / test1234 (status=pending → admin approve)

## Iteration #1 — 2026-01-26 — Visual Recorder Edit Step
- `PATCH /api/visual-recorder/{id}/step/{idx}` + `update_step()` + Edit Modal with pencil button
- Per-step `humanize: false` opt-out for fill/type (skip slow human-typing)

## Iteration #2 — 2026-01-26 — Smart Suggester + Manual Add Step
- `GET /api/visual-recorder/{id}/suggest-selectors` — DOM token-match scan, returns ranked candidates
- `POST /api/visual-recorder/{id}/manual-step` — adds any step (CSS or XPath)
- Frontend: "Find similar" button in Edit modal, "+ Add Step" button in steps panel

## Iteration #3 — 2026-01-26 — Selector Preview on Hover
When user hovers a suggestion in the Edit modal's "Find similar" panel, the matching element on the LIVE screenshot is highlighted with a blue pulse ring + solid outline + selector label badge. Makes selecting the right alternative selector trivially obvious.

### Backend
- `selector_bbox()` in visual_recorder.py — uses Playwright `query_selector().bounding_box()`. Works for both CSS and XPath. Returns x/y/width/height in CSS px + viewport size + found flag.
- Endpoint: `GET /api/visual-recorder/{id}/selector-bbox?selector=...`

### Frontend
- New state: `hoverPreview` (bbox + viewport + selector)
- `showSelectorPreview()` / `clearSelectorPreview()` helpers — debounced via `previewFetchRef` so quick hovers across the list don't pile up requests
- Wired to `onMouseEnter/Leave/Focus/Blur` on each suggestion item
- **Edit modal repositioned**: was centered overlay with backdrop blur → now right-side docked panel with light transparent backdrop. Screenshot in the center stays fully visible.
- **Overlay**: two stacked absolute-positioned divs on the screenshot
  1. Outer pulse ring with `animate-ping` (Tailwind) + blue shadow
  2. Solid blue outline (2px) + label badge above showing the selector string
  - Position uses percent-based coords from CSS-px bbox / viewport — stays aligned at any responsive scale

## Safety / What's NOT changed
- All 582 original repo files preserved
- All existing endpoints, modules, components untouched
- Anti-detect human typing intact (only opt-out per-step)
- Step `action` field still read-only

## Files modified (cumulative)
- `backend/visual_recorder.py` — update_step, add_manual_step, suggest_selectors, selector_bbox (+~280 lines)
- `backend/server.py` — 4 new endpoints (PATCH step, POST manual-step, GET suggest-selectors, GET selector-bbox)
- `backend/real_user_traffic.py` — humanize opt-out in 2 fill/type handlers
- `frontend/src/pages/VisualRecorderPage.js` — Edit modal, Suggester panel + hover-preview, Manual Add modal, overlay highlight, helpers (+~700 lines)

## Backlog / Future
- P2: Selector aliases — save a user-edited selector as a permanent alias so future recordings/sessions auto-detect the renamed element
- P2: Multi-element preview — show all matching elements at once when selector matches >1
- P2: Live "what's behind this overlay" — when an element is found but visually hidden, surface that fact in the suggestion list
