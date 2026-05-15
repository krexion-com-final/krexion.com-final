# Aap ke Dynabook L50-G ke liye Special Guide (8 GB RAM)

> Aap ne batayi specs: **Intel i5-10210U · 8 GB RAM · 119 GB SSD (56 GB free) · Win 10/11 · Integrated UHD Graphics**
> Aap ko **RUT (Real User Traffic) smoothly** chahye. Ye file batati hai us PC pe **smoothly** kaise chalega.

---

## ✅ Pehle Check Karne wali Cheezein

| # | Cheez | Aap ki PC pe | Status |
|---|-------|--------------|--------|
| 1 | 64-bit Windows 10 (1903+) ya Win 11 | ✓ (image se confirmed) | ✅ |
| 2 | i5-10210U (4C/8T) | ✓ | ✅ |
| 3 | 8 GB RAM | ✓ | ⚠️ Minimum — tuning chahye |
| 4 | SSD with 30 GB+ free | 56 GB free | ✅ |
| 5 | Virtualization in BIOS (Intel VT-x) | Verify karna | ⚠️ Check below |
| 6 | Internet (first-time install) | — | ✅ |

### Virtualization check (1 second)
1. **Task Manager** open karein (Ctrl+Shift+Esc) → **Performance** tab → **CPU**
2. Bottom-right pe **"Virtualization: Enabled"** dikhna chahye.
   - Agar **Disabled** ho to BIOS mein jaake `Intel VT-x` / `Intel Virtualization Technology` ON karein. (Boot karte time F2 ya F12 — Dynabook ke liye usually F2.)

---

## 🚀 Recommended Install Sequence (aap ke 8 GB PC ke liye)

### Step 1 — WSL ko 5 GB pe cap karein (ZAROORI)

8 GB RAM pe agar WSL ko free chhor diya to Docker poori 8 GB kha jayega aur laptop hang ho jayega.

1. Repo download/clone karne ke baad: **`WSLCONFIG-8GB.bat`** ko double-click.
2. Ye `%USERPROFILE%\.wslconfig` file likh deta hai with:
   - `memory=5GB` (WSL ko 5 GB, Windows ko 3 GB)
   - `processors=4` (sare cores use)
   - `swap=4GB` (extra safety)
3. PowerShell mein: `wsl --shutdown`
4. Docker Desktop ko restart karein (tray icon → Quit → re-open).

### Step 2 — Installer chalaein
**`INSTALL-KREXION.bat`** double-click. Script automatically:
- RAM detect kare ga (8 GB) → **Low-RAM profile** auto-enable kare ga
- Mongo cap **1 GB**, Backend cap **2.5 GB**, Frontend **192 MB**
- `RUT_MAX_CONCURRENCY=2` set kar de ga
- Total Docker usage **~3.7 GB << 5 GB WSL** = no swap, no OOM ✅

### Step 3 — Verify (install ke baad)
Browser pe: `http://localhost:3000/admin-login`

Diagnostics check: `http://localhost:8001/api/diagnostics/health`

---

## ⚡ RUT Smoothly Chalane ki Tips (aap ke i5/8GB PC ke liye)

### Optimal RUT Settings

| Setting | Aap ki PC (i5-U / 8GB) | Reason |
|---------|------------------------|--------|
| **Concurrency** | **2** (max 3) | Har Playwright chromium context ~500 MB RAM eat karta hai |
| **Delay between visits** | **3-5 seconds** | CPU thermal throttling avoid karne ke liye |
| **Visits per job** | **20-50** | Per batch — chhote chunks better than 200 in one go |
| **Headless** | **Yes** | UI render = 30% extra CPU waste |
| **Proxies** | Optional | Agar use kar rahe ho, fast residential proxies hi |
| **Screenshots** | **Off** unless debugging | Disk + RAM kha jate hain |

### Frontend pe slider settings (RUT page pe)
1. Job create karte waqt:
   - **Workers (concurrency)**: `2` set karein (slider ko 2 pe rakhein)
   - **Delay**: `3000-5000` ms
2. Pehla job hamesha **10 visits ka test** karein — agar smooth chala to chunk badha lo.

### Agar phir bhi slow ho?
1. Open Docker Desktop → **Containers** tab → check `krexion-backend` memory bar. Agar 90%+ pe red ho to:
   - `RUT_MAX_CONCURRENCY=1` set karein in `.env`
   - `docker compose down && docker compose -f docker-compose.yml -f docker-compose.lowram.yml up -d`
2. Chrome / Edge band karein RUT job ke time (browser memory eat karta hai).
3. Antivirus exclude karein `C:\krexion\` folder ko (Defender real-time scan slow karta hai Docker file I/O).

---

## 📊 Performance Expectations

Aap ki PC pe **realistic numbers**:

| Operation | Speed |
|-----------|-------|
| Simple GET visit (no form) | ~3-5 sec per visit |
| Form-fill visit | ~8-15 sec per visit |
| **2 concurrent workers** = effective | ~30 visits / 5 minutes |
| **100 visits batch** | ~15-20 minutes |
| Boot time (cold start) | ~2 minutes (first time 8-10 min) |

Agar aap ko **>50 visits/minute** chahiye to **16 GB RAM** ka PC use karein ya cloud VPS (DigitalOcean $24/mo droplet) pe deploy karein — same `install-krexion.sh` chalega.

---

## 🛡 Daily Maintenance (har 2-3 din)

```cmd
cd C:\krexion
KREXION-DOCTOR.bat        :: health check
docker system prune -f      :: purane images delete (saves 1-2 GB disk)
```

Mongo data backup (har hafta):
```cmd
docker exec krexion-mongo mongodump --archive=/data/db/backup.archive
```

---

## ❌ Common Mistakes Avoid Karein

1. **RUT pe 5+ concurrency lagana** → RAM full → swap → laptop hang ❌
2. **Background mein Chrome / Edge / Photoshop chalana** → RAM compete kare gi ❌
3. **WSL cap nahi karna** → Docker poori RAM kha jayega ❌
4. **HDD pe install karna (agar laptop pe second drive ho)** → Mongo slow ho jayega. Always **SSD** pe.
5. **Antivirus scan on**, `C:\krexion\` ko exclude na karna → Docker file I/O slow.

---

## 🆘 TL;DR (single-line)

```
WSLCONFIG-8GB.bat → wsl --shutdown → Docker restart → INSTALL-KREXION.bat → http://localhost:3000
RUT concurrency = 2, delay = 3-5 sec. Done.
```

Smooth chale ga, swap nahi karega, OOM nahi hoga. 🚀
