# RealFlow

Self-hosted traffic tracking + conversion + anti-detect automation platform with **CPI Install Module**.

## 🚀 Quick Deploy (One Command)

Open PowerShell **as Administrator** on your Windows 11 home PC and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; iwr -UseBasicParsing https://raw.githubusercontent.com/amna00661226-create/realflow-amna/main/REALFLOW-DEPLOY.ps1 | iex
```

That single command:
- Installs Docker Desktop and Git (if missing)
- Clones the repo to `C:\realflow`
- Generates strong random secrets in `.env`
- Builds and starts the full stack (FastAPI + MongoDB + optional Cloudflare Tunnel)
- Detects existing installs → upgrades in-place with auto Mongo backup

After first install, future updates take 3-5 minutes:

```powershell
cd C:\realflow
.\REALFLOW-UPDATE.bat
```

📖 **Full deploy guide (Urdu)**: [DEPLOY-README-URDU.md](DEPLOY-README-URDU.md)

---

## 🧱 Architecture

| Component | Where it runs |
|---|---|
| **Frontend** (React) | Vercel — auto-deploys from this repo |
| **Backend** (FastAPI) | Home PC Docker `realflow-backend` |
| **Database** (MongoDB) | Home PC Docker `realflow-mongo` |
| **Public exposure** | Cloudflare Tunnel `realflow-cloudflared` (no port forwarding) |
| **CPI Worker** (Python) | Home PC native Windows service — needs USB access to phones |

---

## 📦 Modules

- **Real User Traffic** (RUT) — anti-detect headless Chromium browser farm
- **Form Filler** — automated SOI / lead-form submission
- **Email Checker / UA Generator / Referrer Stats** — utility tools
- **CPI Module** — full Cost-Per-Install pipeline:
  - Offers, Jobs, Devices, Smart Links, Dashboard, Worker Setup
  - Stateless worker daemon polls cloud backend, executes installs on connected Android (adb) and iPhone (libimobiledevice/tidevice) devices
  - Per-install fingerprint randomization, proxy rotation, behavior simulation, INSTALL_REFERRER broadcast
  - 📖 Setup guide (Urdu): [CPI-SETUP-URDU.md](CPI-SETUP-URDU.md)
  - 📖 FAQ (Urdu): [CPI-FAQ-URDU.md](CPI-FAQ-URDU.md)

---

## 🛠 Daily Operations

```powershell
cd C:\realflow

# Status
docker compose ps

# Live logs
.\REALFLOW-LOGS.bat

# Update (pull + rebuild + restart)
.\REALFLOW-UPDATE.bat

# Stop everything
.\REALFLOW-STOP.bat
```

---

## 🔐 First Login

After fresh deploy, the script prints a generated admin password. Save it. Login:

- **Frontend**: https://realflow.online/admin-login
- **Email**: `admin@realflow.local`
- **Password**: (printed by script — also stored in `C:\realflow\.env`)

---

## 🆘 Troubleshooting

See [DEPLOY-README-URDU.md](DEPLOY-README-URDU.md) for common issues, or run:

```powershell
docker compose logs -f
```

For CPI-specific issues see [CPI-FAQ-URDU.md](CPI-FAQ-URDU.md).
