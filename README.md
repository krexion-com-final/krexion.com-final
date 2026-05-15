# 🚀 Krexion

> **Self-hosted traffic tracking + conversion + CPI automation platform**

Built with FastAPI + React + MongoDB + Playwright. Production-ready, multi-tenant, with license/billing module, anti-detect browser farm, and one-click installer for end users.

---

## ⚡ Quick Start (For End Users)

### 🪟 Windows (One-Click Install)

Download the repo as ZIP from GitHub → extract → double-click **`Krexion-Setup/Install.bat`** → follow GUI wizard.

📖 **Complete user guide**: [USER-GUIDE-PRODUCTION.md](USER-GUIDE-PRODUCTION.md)

### 🐧 Linux / 🍎 macOS

```bash
git clone https://github.com/ronaldsexedwards40-glitch/dynabook.git
cd dynabook
sudo bash install-krexion.sh
```

After install → open `http://localhost:3000` → login with credentials printed by installer.

---

## 🛠️ For Admins (Business Owners)

📖 **Complete admin guide**: [ADMIN-GUIDE-PRODUCTION.md](ADMIN-GUIDE-PRODUCTION.md)

Includes:
- User management & approval flow
- License management (issue, extend, revoke, delete, bulk cleanup)
- Pricing & trial rule configuration
- Global kill switch
- Mobile admin access (`ADMIN-GO-ONLINE.bat`)
- Permanent cloud hosting via Render.com (`render.yaml` provided)
- Database backups & monitoring

---

## 🧱 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CUSTOMER'S PC (after install)                              │
│                                                             │
│   Frontend (React + nginx) ──> Backend (FastAPI) ──> Mongo │
│   port 3000                    internal              internal│
│                                                             │
│   Optional: Cloudflare Tunnel for public access             │
│   Optional: CPI Worker (native Windows, USB to phones)      │
└─────────────────────────────────────────────────────────────┘
```

| Component | Tech | Port |
|-----------|------|------|
| Frontend | React 18 + CRA + Tailwind + shadcn-ui | 3000 |
| Backend | FastAPI + Playwright + Motor | 8001 (internal) |
| Database | MongoDB 7 | 27017 (internal) |
| Worker (optional) | Python native, runs on Windows | N/A |

---

## 📦 Core Modules

| Module | Description |
|--------|-------------|
| 🌐 **Real User Traffic (RUT)** | Anti-detect headless Chromium browser farm |
| 📝 **Form Filler** | Automated SOI / lead-form submission |
| 📲 **CPI Module** | Cost-Per-Install pipeline (Android + iPhone) |
| 🔗 **Click Tracking** | Short links with referrer + UA capture |
| 📧 **Email Checker** | Bulk email validation |
| 🎲 **UA Generator** | User-agent + fingerprint randomization |
| 📊 **Referrer Stats** | Traffic source analytics |
| 👥 **Sub-users** | Multi-tenant accounts under parent user |
| 🎫 **License Module** | SaaS billing, trial, master kill switch |
| 🛠️ **Admin Dashboard** | User approval, feature gating, license management |

---

## 🎯 Performance Auto-Tuning

Installer detects your hardware and configures the entire stack for optimal performance:

| Tier | RAM | RUT Workers | Mongo Cap | Backend Cap |
|------|-----|-------------|-----------|-------------|
| MICRO | ≤ 6 GB | 1 | 512 MB | 1.5 GB |
| LOW | 7-10 GB | 2 | 1 GB | 2.5 GB |
| MID | 11-16 GB | 4 | 2 GB | 4 GB |
| HIGH | 17-32 GB | 8 | 4 GB | 8 GB |
| BEAST | > 32 GB | 16 | 8 GB | 16 GB |

📖 Details: [PERFORMANCE-PROFILES.md](PERFORMANCE-PROFILES.md)

---

## 📚 All Documentation

### 🆘 Quick Help
- **End-user install guide**: [USER-GUIDE-PRODUCTION.md](USER-GUIDE-PRODUCTION.md) ⭐
- **Admin/business owner guide**: [ADMIN-GUIDE-PRODUCTION.md](ADMIN-GUIDE-PRODUCTION.md) ⭐

### 📖 Deep Dives
- **Full feature reference**: [KREXION-USER-GUIDE.md](KREXION-USER-GUIDE.md) (42 KB, all features explained)
- **CPI module setup (Urdu)**: [CPI-SETUP-URDU.md](CPI-SETUP-URDU.md)
- **CPI FAQs (Urdu)**: [CPI-FAQ-URDU.md](CPI-FAQ-URDU.md)
- **Deployment guide (Urdu)**: [DEPLOY-README-URDU.md](DEPLOY-README-URDU.md)
- **Local setup (Urdu)**: [LOCAL-SETUP-URDU.md](LOCAL-SETUP-URDU.md)

### 🪟 Windows-specific
- **8 GB Dynabook guide**: [DYNABOOK-8GB-GUIDE.md](DYNABOOK-8GB-GUIDE.md)
- **Performance profiles**: [PERFORMANCE-PROFILES.md](PERFORMANCE-PROFILES.md)
- **Easy install**: [EASY-INSTALL.md](EASY-INSTALL.md)

### 🌐 Production Hosting
- **Render.com cloud deploy**: [GITHUB-ONLINE-DEPLOY.md](GITHUB-ONLINE-DEPLOY.md)
- **Admin URL setup**: [ADMIN-URL-SETUP.md](ADMIN-URL-SETUP.md)
- **Customer GO-ONLINE**: [GO-ONLINE-CUSTOMER-GUIDE.md](GO-ONLINE-CUSTOMER-GUIDE.md)

### 🆘 Recovery
- **Quick fix installer**: [QUICK-FIX-INSTALL.bat](QUICK-FIX-INSTALL.bat) (single-file emergency installer)
- **Admin guide (Urdu)**: [ADMIN-GUIDE-URDU.md](ADMIN-GUIDE-URDU.md) (kill switch, license management)

---

## 🔐 First Login Credentials

After install, login at `http://localhost:3000/admin-login`:

| Field | Value |
|-------|-------|
| Email | `admin@krexion.local` |
| Password | Printed by installer (also in `.env` as `ADMIN_PASSWORD`) |

⚠️ **CHANGE the default password immediately in production!**

---

## 🚦 Daily Operations

### Windows (run from `C:\krexion`)
```powershell
.\KREXION-LOGS.bat      # Live logs
.\KREXION-UPDATE.bat    # Pull + rebuild + restart
.\KREXION-STOP.bat      # Stop everything
.\GO-ONLINE.bat          # Public URL (customer access)
.\ADMIN-GO-ONLINE.bat    # Admin mobile access (DO NOT SHARE)
```

### Linux / macOS
```bash
docker compose ps                       # Status
docker compose logs -f                  # Live logs
docker compose restart                  # Restart
docker compose up -d --build            # Update
```

---

## ❓ Troubleshooting

1. **Docker not running** → Open Docker Desktop, wait for whale to stabilize
2. **Port 3000 in use** → Stop conflicting service or change port
3. **Forgot admin password** → Check `.env` file `ADMIN_PASSWORD=` line
4. **Install fails with git error** → Use `QUICK-FIX-INSTALL.bat` (ZIP download, no git needed)
5. **Slow on 8 GB PC** → Already auto-tuned, see [DYNABOOK-8GB-GUIDE.md](DYNABOOK-8GB-GUIDE.md)
6. **License key expired** → Contact admin via setup wizard's "Contact Admin" button

📖 **Full troubleshooting**: see Admin Guide and User Guide

---

## 🔗 Repository

**GitHub**: https://github.com/ronaldsexedwards40-glitch/dynabook

**Issues**: https://github.com/ronaldsexedwards40-glitch/dynabook/issues

---

## ✅ Verified Working (May 2026)

- ✅ Backend: 33/33 pytest cases passing (auth, license, admin, links, CPI)
- ✅ Frontend: React app loads cleanly, login page renders
- ✅ MongoDB: All collections accessible, no schema errors
- ✅ Playwright: Auto-installs on first RUT job
- ✅ License module: Manual purchase flow, bulk cleanup, all CRUD working
- ✅ Multi-tier auto-tuning: MICRO/LOW/MID/HIGH/BEAST profiles verified
- ✅ Installer: ZIP-download fallback, robust error handling
- ✅ Mobile access: Both customer (`GO-ONLINE.bat`) and admin (`ADMIN-GO-ONLINE.bat`)

---

**Made with ❤️ for self-hosted traffic automation**

> Built on: FastAPI 0.115 · React 18 · MongoDB 7 · Playwright 1.49 · Tailwind 3 · shadcn-ui · Python 3.11
