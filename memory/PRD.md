# Krexion.com — Agent Working Memory (PRD)

## Original Problem Statement
User ne `https://github.com/dennisedmaartins9-sudo/krexion.com.git` repo share kiya hai (PAT diya hai). User collaborator hai aur main branch par directly changes save karna chahta hai. Repo VPS par auto-deploy hai (git push -> auto deploy). Customer updates admin panel ke "Release" page par push hote hain.

Critical requirements (user):
- Koi cheez break ya delete nahi honi chahye.
- Main branch par direct save karega, conflict bilkul nahi ana chahye.
- Preview pe sab test ho sake — login chahye.
- Native app, electron app, cloud VPS, customers — sab jagah consistency maintain ho.
- **DEPLOY MAT KARO** jab tak user explicitly nahi kahe (batch all changes, single deploy)

## Architecture
- Backend: FastAPI (Python 3.11) — `/app/backend/server.py` + 30+ modules. Port 8001.
- Frontend: React 18 (CRA + craco) — `/app/frontend/`. Port 3000.
- Database: MongoDB 7. DB name: `krexion`.
- Deploy targets: Render.com / Docker Compose / Windows native / Electron / VPS.

## Environment Setup (Preview — Emergent container)
- `.env` files for backend & frontend (gitignored, never pushed).
- Backend has EMERGENT_LLM_KEY now for AI keyword generator.
- All Python deps installed (947 frontend packages, full venv).
- Supervisor: backend, frontend, mongodb — RUNNING.
- Preview URL: https://ec2e63a6-1914-4d70-b460-72eb1cc3124f.preview.emergentagent.com

## Git Setup
- Remote origin: PAT-authenticated for `dennisedmaartins9-sudo/krexion.com`.
- Branch: main (in-sync with origin/main).
- Push workflow: User uses Emergent "Save to Github" feature → VPS auto-deploys.
- **DO NOT push automatically** — wait for user command.

## Implemented Iterations

### Iteration 1 (2026-06-11) — Setup
- Cloned upstream repo into /app preserving original .git.
- Installed all backend & frontend dependencies for Emergent preview.
- Created `.env` files (gitignored) for preview-only credentials.
- Verified health endpoints + admin login + frontend landing page.

### Iteration 2 (2026-06-11) — Referrer Pro-Mode + All 12 Enhancements
**NEW FILES (not yet pushed):**
- `/app/backend/referrer_pro.py` — Weighted pool resolver + 12 realism helpers
- `/app/backend/referrer_pro_api.py` — `/api/referrer-pro/*` endpoints
- `/app/backend/.env` — Added EMERGENT_LLM_KEY

**MODIFIED FILES (not yet pushed):**
- `/app/backend/real_user_traffic.py`:
  - `_resolve_visit_referer()` returns 4-tuple (added `pro_extras` dict). Pro-mode delegates to `referrer_pro.resolve_pro_visit`.
  - `run_real_user_traffic_job()` signature extended with 8 new kwargs (all backward-compatible defaults).
  - Context-header injection merges Sec-Fetch-* family from pro extras.
- `/app/backend/server.py`:
  - RUT submit endpoint accepts 8 new form fields.
  - `_rut_prepare_and_run` and `params` dict store all new fields persistently.
  - `app.include_router(_refpro_router)` registers `/api/referrer-pro/*`.
- `/app/frontend/src/pages/RealUserTrafficPage.js`:
  - New `ReferrerProMultiSelect` helper component (chip + sliders + Equal/Clear).
  - New state: refererProMode, refererPlatformWeights (object), refererEmailWeights, social/inapp/strip/network toggles, search engine + keywords, AI keyword generator state.
  - useEffect loads `/api/referrer-pro/defaults` on mount.
  - Pro Mode UI block conditional on `refererProMode=true`:
    - Platform Mix multi-select with % sliders
    - Email Source Mix (when email is in pool)
    - Search Engine Settings (when google/bing/yahoo/ddg/yandex is in pool)
    - AI Keyword Generator (Claude Sonnet 4.6 via Emergent LLM Key)
    - Realism Layers toggles (social wrapper, inapp deep, network click chain)
    - Brand Identifier (when email is in pool)
  - handleSubmit appends all 8 new form fields.

**Features delivered:**
- A) Geo-localized search Referers (50+ countries, google.de/.fr/.co.uk/.com.br/etc.)
- B) Multi-engine search modes (Google/Bing/Yahoo/DDG/Yandex/YouTube/Baidu/Naver)
- C) Social link-wrapper Referers (l.facebook.com / lm.facebook.com / t.co / lnkd.in / l.instagram.com / out.reddit.com / youtube redirect / Pinterest pin URLs)
- D) Mobile in-app browser deep paths (tiktok video, ig post, fb story_fbid, linkedin urn)
- E) Sec-Fetch-* header family auto-sync (Mode/Dest/User/Site)
- F) [Pending — cookie pre-load — needs implementation in run_real_user_traffic_job]
- G) UTM source/medium variation pool (per platform 4-5 realistic spellings)
- H) AI keyword generator via Claude Sonnet 4.6 (Emergent LLM Key)
- I) Time-of-day platform pacing weights (helper exposed, not yet wired into PacingEngine)
- J) fbclid/gclid realistic embedded timestamps (helper exposed)
- K) Search-engine Referer-Policy strip (configurable in UI)
- L) Network click-redirect chain (12 affiliate-network hosts, per-visit random)
- **+ Multi-select chip UI with % sliders** for both platform pool AND email ESP buckets
- **+ Total auto-shows + Equal/Clear quick actions**

**Verified live (preview):**
- /api/referrer-pro/defaults returns 18 platforms + 19 email buckets + 8 search engines + 50 countries
- /api/referrer-pro/generate-keywords with Claude Sonnet 4.6 → 12-15 realistic keywords (branded + commercial + informational mix)
- /api/referrer-pro/test-resolve → 15 sample visits, weights respected, geo-localized URLs, ESP-matching emails, network click chain rotating, UTMs varying per visit
- UI screenshots confirm: Pro Mode toggle, multi-select chips, sliders with % display, total indicator green at 100%, email mix sliders, AI generator, realism toggles, brand field

## Pending / Awaiting User Input
- **User confirmation to deploy** — all changes are local in /app, NOT pushed to GitHub yet.
- User may want additional refinements/UX tweaks before deploy.
- Gap F (cookie pre-load) deferred — needs deeper work into context creation flow.
- Gap I (time-of-day pacing) helper ready but not wired into pacing engine yet.
- Gap J (fbclid/gclid timestamps) helper ready but the tracker URL builder still uses legacy generator — needs separate hook.

## Notes for future iterations
- ANY change must respect all deploy surfaces: cloud VPS, Windows native installer (.bat/.ps1), Electron desktop, customer admin panel Release page, Render.com.
- NEVER delete files. Use targeted `search_replace` edits.
- After change → preview test → **user pushes via Save to Github** → VPS auto-deploys.
- Repo has 80+ installer scripts — touch only if directly relevant.
