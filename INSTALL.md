# Krexion — One-Click Deploy (Any Computer)

> **Goal**: Aap kisi b PC pe sirf aik file double-click karein aur poora Krexion stack
> (FastAPI backend + MongoDB + React frontend) automatically install + start ho jaye.

---

## 🪟 Windows 10 / 11

### Method 1 — One-click (recommended)

1. Is repo ko `Save to GitHub` ke baad apne PC pe download karein (ZIP ya `git clone`).
2. Folder ke andar **`INSTALL-KREXION.bat`** ko **double-click** karein.
3. Bas. Script automatically:
   - Administrator privileges maangega (UAC popup → Yes)
   - Docker Desktop install karega (agar nahi hai)
   - Git install karega (agar nahi hai)
   - Repo ko `C:\krexion` pe clone karega
   - `.env` mein strong random passwords generate karega
   - Backend + MongoDB + Frontend containers build + start karega
   - Aapko admin password screen pe dikhayega

### Method 2 — Direct from internet (no download needed)

PowerShell ko **As Administrator** open karein aur:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
iwr -UseBasicParsing https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/KREXION-DEPLOY.ps1 | iex
```

### After install — open browser

| What | URL |
|------|-----|
| **Frontend (main UI)** | `http://localhost:3000` |
| **Admin login** | `http://localhost:3000/admin-login` |
| **Backend API docs** | `http://localhost:8001/docs` |
| **Health check** | `http://localhost:8001/api/diagnostics/health` |

Admin credentials:
- **Email**: `admin@krexion.local`
- **Password**: (printed by installer + saved in `C:\krexion\.env` as `ADMIN_PASSWORD`)

### Daily Windows commands (run from `C:\krexion`)

| File | What it does |
|------|--------------|
| `LOCAL-START.bat`     | Start the stack |
| `LOCAL-STOP.bat`      | Stop the stack |
| `LOCAL-UPDATE.bat`    | Pull latest code + rebuild |
| `KREXION-LOGS.bat`   | Live tail logs |
| `KREXION-DOCTOR.bat` | Diagnose issues |
| `INSTALL-KREXION.bat`| Run again for in-place upgrade |

---

## 🐧 Linux / 🍎 macOS

### Method 1 — From cloned repo

```bash
git clone https://github.com/ronaldsexedwards40-glitch/dynabook.git
cd dynabook
sudo bash install-krexion.sh
```

### Method 2 — Direct from internet

```bash
curl -fsSL https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/install-krexion.sh | sudo bash
```

(macOS users: install Docker Desktop manually first from <https://www.docker.com/products/docker-desktop>, then run the script without `sudo`.)

Script ye sab kar deta hai:
1. Docker + docker-compose-plugin install (`apt`/`dnf`/`yum`/`pacman` auto-detect)
2. Git install (agar missing ho)
3. Repo clone to `/opt/krexion` (ya current dir agar already cloned ho)
4. `.env` generate with strong random secrets (saves admin password)
5. `docker compose build && docker compose up -d`
6. Health-check loop until backend ready
7. Final screen pe sari URLs + admin password print

### Daily Linux/macOS commands

```bash
cd /opt/krexion                       # ya jis dir mein cloned hai

docker compose ps                       # status
docker compose logs -f                  # live logs
docker compose restart                  # restart everything
docker compose down                     # stop everything
docker compose up -d --build            # rebuild + start (after code update)
```

---

## 🧱 Architecture (jo install hota hai)

```
┌─────────────────────────────────────────────────────────────┐
│  YOUR PC                                                    │
│                                                             │
│   ┌──────────────┐    ┌───────────────┐   ┌─────────────┐   │
│   │  krexion-   │    │  krexion-    │   │  krexion-  │   │
│   │  frontend    │───▶│  backend      │──▶│  mongo      │   │
│   │  (nginx +    │    │  (FastAPI +   │   │  (MongoDB 7)│   │
│   │   React)     │    │   Playwright) │   │             │   │
│   │  port 3000   │    │  internal     │   │  internal   │   │
│   └──────┬───────┘    └───────────────┘   └─────────────┘   │
│          │                                                  │
│          │ public on http://localhost:3000                  │
│          ▼                                                  │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
       Aap (browser)
```

- **Frontend** (nginx + React build) — port **3000** → public face. Proxies `/api/*` to backend.
- **Backend** (FastAPI + Playwright) — internal, no public port. Reachable from frontend container only.
- **MongoDB 7** — internal, data persisted in `mongo-data` Docker volume. WiredTiger cache hard-capped at 2.5 GB.
- **CPI Worker** — installs natively on Windows (not in Docker) because it needs USB access to Android / iPhone for installs.

---

## 🔐 Important env vars (`.env`)

Generated automatically — change only if you know what you're doing.

| Key | What it does |
|-----|--------------|
| `JWT_SECRET_KEY` | Signs all auth tokens. **Rotate = log everyone out**. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | The single admin account (no DB row needed) |
| `POSTBACK_TOKEN` | Secret token for affiliate postback URLs |
| `DB_NAME` | MongoDB database name (default `krexion`) |
| `CORS_ORIGINS` | `*` for local; lock down to your domain in production |
| `TUNNEL_TOKEN` | (optional) Cloudflare Tunnel token → makes your PC reachable publicly. Empty = local-only. |
| `RESEND_API_KEY` | (optional) Transactional email |
| `GOOGLE_SHEETS_SA_*` | (optional) Live Google Sheets row-delete |

---

## 🆘 Troubleshooting

- **"Docker is installed but not running"** → Open Docker Desktop, wait for whale icon to stabilize, re-run installer.
- **Port 3000 / 8001 already in use** → Stop the conflicting service or change the port in `docker-compose.yml`.
- **Frontend loads but API calls fail** → Check `docker compose logs backend` for errors.
- **Forgot admin password** → Run `ADMIN-CREDENTIALS-MANAGER.bat` (Windows) or `grep ADMIN_PASSWORD .env` (Linux/Mac).
- **Detailed Urdu guide** → see `DEPLOY-README-URDU.md`.

---

## 🚮 Uninstall / Clean reset

```bash
cd <install-dir>
docker compose down -v        # WARNING: -v wipes mongo data + uploads
```
