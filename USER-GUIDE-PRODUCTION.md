# RealFlow — Production Installation Guide for Users

> Yeh guide aap (end-user) ke liye hai. Apne PC pe RealFlow install karne ke liye sirf
> yeh 5 minute padhein. Koi technical knowledge ki zaroorat nahi.

[English version below — اردو ‎version پہلے]

---

## 🌟 RealFlow Kya Hai?

RealFlow aik **all-in-one self-hosted traffic + conversion automation platform** hai:
- 🌐 **Real User Traffic (RUT)** — anti-detect Chromium browser farm
- 📝 **Form Filler** — automated lead/SOI form submission
- 📲 **CPI Module** — Cost-Per-Install pipeline for Android + iPhone
- 🔗 **Click Tracking + Smart Short Links**
- 📧 **Email Checker / UA Generator / Referrer Stats**
- 👥 **Multi-tenant Sub-users**

Aap kahin se bhi mobile/laptop se access kar sakte ho (One-Click GO-ONLINE feature).

---

# 🟢 Aap Ke Liye 3 Asaan Tareeqe (Easy / Easier / Easiest)

## ✨ Tareeqa 1 — One-Click GUI Wizard (Recommended for non-tech users)

> Sab se asaan tareeqa. Sirf double-click karein aur GUI wizard sab kuch kar dega.

### Steps:

1. **Repo download karein** (yeh link kholein):
   ```
   https://github.com/ronaldsexedwards40-glitch/dynabook
   ```
   Top right pe green **"Code"** button click karein → **"Download ZIP"**

2. ZIP ko extract karein (kisi bhi folder mein, e.g. Desktop pe)

3. Folder ke andar `RealFlow-Setup` folder open karein

4. **`Install.bat`** ko **double-click** karein

5. UAC popup aaye to **"Yes"** click karein

6. GUI wizard khulega — aik bara nila **"INSTALL"** button hoga → click karein

7. Wizard 6 stages mein automatically:
   - Docker Desktop install karega (agar nahi hai)
   - Git install karega (agar nahi hai)
   - WSL2 setup karega (auto-tuned for your RAM)
   - Code download karega (`C:\realflow`)
   - Random strong passwords generate karega
   - Docker containers build + start karega

8. 15-30 minute baad green **"OPEN REALFLOW"** button aaye ga → click → browser khul jaye ga

9. ✅ **Done!** RealFlow `http://localhost:3000` pe chal raha hai

### 💡 Tip: Hardware Auto-Tuning
Wizard automatically aap ke PC ka RAM/CPU detect karta hai aur **5 tiers** mein se best chunta hai:
| Tier | RAM | RUT Workers |
|------|-----|-------------|
| MICRO | ≤6 GB | 1 |
| LOW | 7-10 GB | 2 |
| MID | 11-16 GB | 4 |
| HIGH | 17-32 GB | 8 |
| BEAST | >32 GB | 16 |

---

## 🚀 Tareeqa 2 — One-Click Batch File (Recommended for slightly tech users)

> Bilkul same kaam, lekin GUI ki bajaye console window se. Slightly faster.

### Steps:

1. Repo download karein (same as above)
2. Folder ke andar **`RealFlow-EASY-INSTALL.bat`** ko **double-click** karein
3. UAC → Yes → wait 15-30 minute → done
4. Browser automatically khul jaye ga `http://localhost:3000` pe

---

## 💻 Tareeqa 3 — Direct PowerShell Command (For tech users)

> Sab se fast. Sirf 1 command. Nothing to download manually.

### Steps:

1. **PowerShell** kholein **As Administrator** (right-click → "Run as administrator")

2. Yeh command paste karein aur Enter:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   iwr -useb https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/REALFLOW-DEPLOY.ps1 | iex
   ```

3. Script automatically sab install karega (Docker, Git, code, containers)

4. End mein admin password screen pe dikhega — **save karein!**

5. Browser kholein: `http://localhost:3000/admin-login`

---

# 🔐 First Login

Install ke baad:

| Field | Value |
|-------|-------|
| **URL** | `http://localhost:3000/admin-login` |
| **Email** | `admin@realflow.local` |
| **Password** | Installer ne console pe print kiya tha (random) — `C:\realflow\.env` mein bhi save hai (`ADMIN_PASSWORD=` line) |

⚠️ **Password kahin save zaroor kar lein!** First login ke baad change karne ke liye Settings → Profile.

---

# 📱 Mobile Se Access (GO-ONLINE Feature)

PC ghar pe hai aur aap bahar? **GO-ONLINE.bat** se duniya bhar se access kar sakte ho!

### Steps:

1. PC pe `C:\realflow\GO-ONLINE.bat` ko **double-click** karein

2. Script automatically Cloudflare tunnel banaye gi (free, no signup)

3. Aik beautiful page khulegi jis pe:
   - 🌐 Public URL (e.g. `https://abc-xyz-123.trycloudflare.com`)
   - 📱 QR code (mobile se scan karein)
   - 📋 Copy URL button
   - 💬 WhatsApp share button

4. Mobile se QR scan karein ya URL kholein → app khul jaye gi

5. **Console window band na karein!** Window band karne se tunnel band ho jaye ga

### ⚠️ Note:
- Quick Tunnel free hai lekin URL har baar change hota hai
- Permanent URL chahiye to **Cloudflare Named Tunnel** setup karein (advanced)
- Ya **Render.com** pe deploy karein (`render.yaml` already provided) — 15 min setup, $0-7/month

---

# 🛠️ Daily Operations (After install)

PC pe `C:\realflow\` folder ke andar yeh files double-click karein:

| File | Kya karta hai |
|------|---------------|
| `LOCAL-START.bat` | RealFlow start karta hai |
| `LOCAL-STOP.bat` | RealFlow stop karta hai |
| `LOCAL-UPDATE.bat` | Latest code download + rebuild |
| `REALFLOW-LOGS.bat` | Live logs dekhne ke liye |
| `REALFLOW-DOCTOR.bat` | Issues diagnose karne ke liye |
| `GO-ONLINE.bat` | Public URL banane ke liye |
| `ADMIN-GO-ONLINE.bat` | Admin panel ke liye separate URL (admin only) |

---

# ❓ Common Problems & Solutions

### ❌ Problem 1: "Docker Desktop not running"
**Solution**: Start menu → "Docker Desktop" run karein → wait until whale icon green ho → phir installer re-run karein

### ❌ Problem 2: "Port 3000 already in use"
**Solution**: Doosri kisi app ne 3000 use kiya hai
```powershell
# Check kaun use kar raha hai:
netstat -ano | findstr :3000
# Phir process kill karein
taskkill /PID <PID> /F
```

### ❌ Problem 3: "Installation fails with git clone error"
**Solution**: Use **`QUICK-FIX-INSTALL.bat`** instead — it uses ZIP download, no git needed

### ❌ Problem 4: Forgot admin password
**Solution**:
```powershell
# Windows PowerShell:
Get-Content C:\realflow\.env | Select-String "ADMIN_PASSWORD"
# Ya:
notepad C:\realflow\.env
# (ADMIN_PASSWORD line dekhein)
```

### ❌ Problem 5: 8 GB RAM PC pe slow chal raha hai
**Solution**: Already auto-tuned for low RAM. Manual retune:
- Double-click `RealFlow-RETUNE.bat`
- Ya `DYNABOOK-8GB-GUIDE.md` padhein

### ❌ Problem 6: License key expired/revoked
**Solution**: Admin ko contact karein — manual purchase flow:
1. Setup wizard → "Contact Admin to Buy a License"
2. Email send hogi automatically
3. Admin nayi key send karega
4. Setup → "I have a license key" → paste → Activate

---

# 🎯 First-Time Usage Tips

Login ke baad aap dekhenge:

### 🏠 Dashboard
Overall stats, recent activity, system health

### 🌐 Real User Traffic (RUT)
1. **New Job** click karein
2. Target URL daalein
3. Concurrency 1-8 (auto-tuned)
4. Visit count
5. Headless mode on
6. **Start** click karein

### 📝 Form Filler
1. Form URL daalein
2. Field mapping configure karein
3. CSV/Excel upload (data)
4. Concurrency set karein
5. Submit

### 📲 CPI Module
1. **Offers** tab — naya offer create karein
2. **Devices** tab — Android (USB) ya iPhone connect karein
3. **Jobs** tab — kitne installs chahiye
4. **Smart Links** — affiliate URLs banaye

### 🔗 Click Tracking
1. **Links** → "New Short Link"
2. Original URL paste karein
3. Custom code (optional)
4. Aapko `https://yoursite/r/<code>` URL milegi
5. Clicks track honge with referrer + UA

---

# 🆘 Support / Help

| Resource | Link |
|----------|------|
| 📖 Full User Guide | `REALFLOW-USER-GUIDE.md` (in repo) |
| 📖 CPI Setup Guide (Urdu) | `CPI-SETUP-URDU.md` |
| 📖 8 GB PC Guide | `DYNABOOK-8GB-GUIDE.md` |
| 📖 Performance Profiles | `PERFORMANCE-PROFILES.md` |
| 📖 Deployment Guide (Urdu) | `DEPLOY-README-URDU.md` |
| 🆘 GitHub Issues | https://github.com/ronaldsexedwards40-glitch/dynabook/issues |

---

# ✅ Verification Checklist

Install karne ke baad yeh check karein:

- [ ] `http://localhost:3000` browser mein khulta hai
- [ ] Login page dikhta hai (RealFlow logo + EST 2025 badge)
- [ ] Admin login (admin@realflow.local + password from .env) successful
- [ ] Dashboard load hota hai (no errors)
- [ ] `docker compose ps` se 3 containers RUNNING (frontend, backend, mongo)
- [ ] Health check: `http://localhost:8001/api/diagnostics/health` → `200 OK`

Agar yeh sab tick hain → **🎉 Aap ready hain!**

---

# 🚮 Uninstall / Clean Reset

⚠️ **WARNING: Yeh sara data delete kar dega!**

```powershell
cd C:\realflow
docker compose down -v
cd C:\
Remove-Item -Recurse -Force C:\realflow
```

Ya complete fresh restart ke liye:
```powershell
cd C:\realflow
docker compose down -v
.\REALFLOW-EASY-INSTALL.bat
```

---

# 📊 System Requirements

| Component | Minimum | Recommended | Optimal |
|-----------|---------|-------------|---------|
| OS | Windows 10 (1909+) | Windows 11 | Windows 11 + WSL2 |
| RAM | 4 GB | 8 GB | 16+ GB |
| Storage | 20 GB free | 50 GB free | 100 GB SSD |
| CPU | Dual-core | Quad-core | 6+ cores |
| Internet | 5 Mbps | 25 Mbps | 100 Mbps |

**Linux/macOS**: Docker + 4 GB RAM minimum. Native containers, no WSL needed.

---

# 🔄 Updates

Future mein code update karne ke liye:

```powershell
# Windows:
cd C:\realflow
.\REALFLOW-UPDATE.bat

# Linux/macOS:
cd /opt/realflow
git pull
docker compose up -d --build
```

Update preserve karta hai:
- ✅ MongoDB data (volumes)
- ✅ Aap ki `.env` file (credentials)
- ✅ Uploaded resources

---

**Made with ❤️ for self-hosted traffic automation**

🐛 Bug found? → GitHub Issues
💡 Feature request? → GitHub Discussions
📧 Admin contact? → Setup wizard mein "Contact Admin" button
