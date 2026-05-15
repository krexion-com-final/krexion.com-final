# Krexion — One-Click Deploy (Urdu Quick Reference)

## 🚀 Truly One-Click Install / Update

**Bas yeh PowerShell command Administrator mode mein chalayein**:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; iwr -UseBasicParsing https://raw.githubusercontent.com/amna00661226-create/krexion-amna/main/KREXION-DEPLOY.ps1 | iex
```

Yeh script automatic detect karega:

| Aap Ki Situation | Script Kya Karega |
|---|---|
| **Naya PC (kuch installed nahi)** | Docker Desktop install + Git install + clone + .env auto-generate + build + start |
| **Existing PC (purani version chal rahi)** | Mongo backup + git pull + docker compose down + rebuild + restart |

⏱ **Pehli baar**: ~15-20 min (Docker download). **Updates**: 3-5 min.

---

## 📋 Quick Commands (After First Deploy)

Sab `C:\krexion` directory mein hain (default location):

| Kya Karna Hai | Command |
|---|---|
| **Latest update install karein** | `cd C:\krexion && .\KREXION-UPDATE.bat` |
| **Sab kuch stop karein** | `cd C:\krexion && .\KREXION-STOP.bat` |
| **Live logs dekhein** | `cd C:\krexion && .\KREXION-LOGS.bat` |
| **Status check karein** | `cd C:\krexion && docker compose ps` |
| **Re-deploy (force fresh)** | `.\KREXION-DEPLOY.ps1 -Force` |

---

## 🆕 Doosre PC Pe Same Setup

Bilkul same one-liner chalayein. Naye PC pe:
1. Docker Desktop install hoga automatic
2. Repo clone hoga `C:\krexion` me
3. .env auto-generate hoga unique random secrets ke saath
4. Service start ho jayegi

**Important**: Doosre PC pe Cloudflare Tunnel chahiye to:
- Cloudflare dashboard → Zero Trust → Tunnels → naya tunnel → token copy
- `C:\krexion\.env` me `TUNNEL_TOKEN=<paste>`
- `.\KREXION-UPDATE.bat`

---

## 🔑 First Login

Pehli baar deploy ke baad PowerShell window me yeh credentials dikhenge:
```
Admin Email    : admin@krexion.local
Admin Password : <random-16-char-password>
```

**Yeh save kar lein!** Lost ho jaye to `C:\krexion\.env` file me `ADMIN_PASSWORD=` line mein bhi hai.

Login karein: `https://krexion.com/admin-login`

---

## 🎯 Custom Install Path

Default `C:\krexion` ke alawa kahin install karna ho:

```powershell
.\KREXION-DEPLOY.ps1 -InstallPath "D:\my-krexion"
```

---

## 🐛 Common Issues

### "Docker Desktop not running"
- Start menu → Docker Desktop → click karein
- Whale icon system tray me settle hone tak wait karein
- Re-run script

### "git pull failed: local changes"
- Aap ne kahin manually edit kiya hai
- Force clean: `git stash push -u -m "manual" && .\KREXION-UPDATE.bat`

### "Port 8001 already in use"
- Purani service abhi bhi chal rahi
- `docker compose down --remove-orphans` chalayein, phir update

### "Cloudflare Tunnel container restarting"
- `TUNNEL_TOKEN` invalid ya expired
- Cloudflare dashboard se naya token banayein, .env update, restart

### "I want to start completely fresh"
- ⚠️ Sab data lost ho jayega
- `cd C:\krexion && docker compose down -v && cd .. && rmdir /s /q krexion`
- Phir bootstrap one-liner

---

## 📦 Sab Files (Aap Ke C:\krexion Pe)

```
C:\krexion\
├── KREXION-DEPLOY.ps1        ← One-click install/upgrade master
├── KREXION-UPDATE.bat        ← Quick git pull + rebuild
├── KREXION-STOP.bat          ← Stop all services
├── KREXION-LOGS.bat          ← Live backend logs
├── docker-compose.yml         ← Service definitions
├── .env                        ← Your secrets (auto-generated, gitignored)
├── .env.example                ← Template
├── backend/                    ← FastAPI source
├── frontend/                   ← React source (deployed on Vercel separately)
├── krexion-cpi-worker/        ← CPI worker (runs natively on Windows)
├── deployment/cpi/             ← CPI worker setup scripts
├── memory/                     ← PRD, test_credentials
├── CPI-SETUP-URDU.md           ← CPI setup guide
├── CPI-FAQ-URDU.md             ← CPI troubleshooting
├── DEPLOY-README-URDU.md       ← This file
└── backups/                    ← Auto-created Mongo backups before each upgrade
```

---

## 💾 Backups

`KREXION-DEPLOY.ps1` upgrade mode me **automatic Mongo backup** leta hai:
- Location: `C:\krexion\backups\<timestamp>\mongo.archive`
- Restore: `docker compose exec -T mongo mongorestore --archive < backups\<timestamp>\mongo.archive`

Manual backup (anytime):
```powershell
$ts = Get-Date -Format yyyyMMdd-HHmmss
docker compose exec -T mongo mongodump --archive | Out-File "backups\manual-$ts\mongo.archive" -Encoding byte
```

---

## 🌍 New Features Add Hone Pe

Future me jab bhi mein naya feature add karoon (or aap khud GitHub me push karein):
1. Browser me krexion.com open
2. PowerShell open
3. **`cd C:\krexion && .\KREXION-UPDATE.bat`** ← Bas yeh ek command
4. 3-5 min wait
5. Naya feature live!

**Same command, every time. No re-learning. No new steps.** ✨
