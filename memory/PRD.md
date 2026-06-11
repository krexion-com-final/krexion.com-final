# Krexion.com — Agent Working Memory (PRD)

## Original Problem Statement
User ne `https://github.com/dennisedmaartins9-sudo/krexion.com.git` repo share kiya hai (PAT diya hai). User collaborator hai aur main branch par directly changes save karna chahta hai. Repo VPS par auto-deploy hai (git push -> auto deploy). Customer updates admin panel ke "Release" page par push hote hain.

Critical requirements (user):
- Koi cheez break ya delete nahi honi chahye.
- Main branch par direct save karega, conflict bilkul nahi ana chahye.
- Preview pe sab test ho sake — login chahye.
- Native app, electron app, cloud VPS, customers — sab jagah consistency maintain ho.

## Architecture
- Backend: FastAPI (Python 3.11) — `/app/backend/server.py` + modules. Port 8001. Routes under `/api/`.
- Frontend: React 18 (CRA + craco) — `/app/frontend/`. Port 3000. Uses `REACT_APP_BACKEND_URL`.
- Database: MongoDB 7 (local in preview, container in prod). DB name: `krexion`.
- Auxiliary: Playwright (RUT browser farm), CPI worker (native Windows), Cloudflare tunnel, Electron desktop, etc.
- Deploy targets: Render.com (render.yaml), Docker Compose (multi-tier), Windows native installer, Electron desktop.

## Environment Setup (Preview — Emergent container)
- `/app/backend/.env` created with required vars (gitignored).
- `/app/frontend/.env` created with REACT_APP_BACKEND_URL (gitignored).
- All backend Python deps installed in /root/.venv.
- Frontend yarn install completed (947 packages).
- Supervisor: backend, frontend, mongodb — all RUNNING.

## Git Setup
- Remote origin: PAT-authenticated for `dennisedmaartins9-sudo/krexion.com`.
- Branch: main (in-sync with origin/main).
- User: emergent-agent-e1 <github@emergent.sh>.
- Working tree clean.
- Push workflow: User uses Emergent "Save to Github" feature → commits to main → VPS auto-deploys.

## Implemented (2026-06-11)
1. Cloned upstream repo into /app preserving original .git.
2. Installed all backend & frontend dependencies for Emergent preview.
3. Created `.env` files (gitignored) for preview-only credentials.
4. `/api/diagnostics/health` returns 200 ok (Mongo connected).
5. `/api/admin/login` returns valid JWT with admin credentials.
6. Frontend renders Krexion landing page on preview URL.
7. `git fetch` + `ls-remote` work via PAT — no conflicts, ready for clean main pushes.

## Pending / Awaiting User Input
- **Specific bug fixes / changes list** — user said: "ap repo complete check kr lo phr main changes bta deta hun".

## Notes for future iterations
- ANY change must respect all deploy surfaces: cloud VPS, Windows native installer (.bat/.ps1), Electron desktop, customer admin panel Release page, Render.com.
- NEVER delete files. Use targeted `search_replace` edits.
- After change → preview test → user pushes via Save to Github → VPS auto-deploys.
- Repo has 80+ installer scripts — touch only if directly relevant.
