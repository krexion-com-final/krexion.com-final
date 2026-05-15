# Krexion CPI Module — Urdu Setup Guide

> **Yeh guide aap ke home PC pe Krexion CPI Worker setup karne ka step-by-step process hai.**
> Aap ko sirf phones connect karne hain, baki sab automatic.

---

## 📋 Aap Ke Paas Hona Chahiye

### Hardware
- ✅ **Windows 11 home PC** (16GB RAM, always-on, stable internet)
- ✅ **1 Android phone** (Redmi Note 8/9 type, Android 10+, **rooted with Magisk** preferred)
- ✅ **1 iPhone** (iPhone 7/8 64GB, **non-PTA OK**)
- ✅ **USB cables** (Lightning + USB-C)
- ✅ **Powered USB hub** (4-port, agar zyada phones ho)
- ✅ **Proxy Jet account** (mobile residential 4G proxies)

### Software (sab automatic install hoga)
- Python 3.11
- Node.js 20
- Appium + drivers
- ADB platform-tools
- libimobiledevice (Windows port)
- iTunes drivers (for iPhone USB recognition)

### Krexion Account
- ✅ krexion.com pe **active user account** hona chahiye
- ✅ Admin se **CPI feature enabled** karwana hai (Profile → Features → CPI)

---

## 🚀 Setup — One-Click Installation

### Step 1 — Krexion Update Karein
Aap ke home PC pe pehle se `krexion-backend` aur `krexion-mongo` Docker chal rahe hain. Latest CPI module pull karein:

```powershell
cd C:\krexion
.\KREXION-UPDATE.bat
```

Yeh `git pull` + `docker compose build` + restart kar dega.

### Step 2 — CPI Worker Setup Script Run Karein
PowerShell **Administrator mode** me kholein:
- Right-click on PowerShell → "Run as Administrator"

Phir yeh paste karein:
```powershell
cd C:\krexion
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\deployment\cpi\KREXION-CPI-SETUP.ps1
```

Script automatically install karega:
1. Chocolatey (if missing)
2. Python 3.11, Node 20, Git, ADB
3. Apple Mobile Device Support (iTunes drivers)
4. libimobiledevice for iPhone
5. Appium + uiautomator2 + xcuitest drivers
6. Python venv aur worker dependencies
7. config.yaml file

⏱ **Pehli baar 10-15 minutes lagenge** (downloads).

### Step 3 — config.yaml Edit Karein
File location: `C:\krexion\krexion-cpi-worker\config.yaml`

**JWT token paste karna**:
1. krexion.com pe login karein
2. Browser DevTools open karein (F12)
3. Application → Local Storage → `https://krexion.com`
4. `token` ki value copy karein (lambi string hogi `eyJhbGc...` se start)
5. config.yaml me paste karein:
   ```yaml
   api:
     token: "eyJhbGciOiJIUzI1NiIsInR5cCI6Ik..."
   ```

⚠️ **Token sensitive hai** — kisi ke saath share na karein, GitHub commit na karein.

---

## 📱 Phones Connect Karna

### Android Phone (One-Time, ~30 min)

#### 3.1 — Factory Reset
- Phone ko factory reset karein
- Initial setup karein (WiFi, Google account skip if possible)

#### 3.2 — Developer Options + USB Debugging
- Settings → About Phone → **Build Number 7 baar tap karein**
- "You are now a developer" message aayega
- Settings → System → **Developer options** → **USB debugging ON**

#### 3.3 — Bootloader Unlock + Magisk Root (For Anti-Detect)
**Yeh phone-specific hai**. Common phones ke liye:

**Xiaomi/Redmi**:
- Settings → About Phone → Tap MIUI version 7 times → Developer
- Developer Options → **OEM Unlock ON** + **USB Debugging ON**
- [Mi Unlock Tool](https://en.miui.com/unlock/) se bootloader unlock (7-day wait)
- TWRP recovery flash → Magisk install
- Detailed guide: search YouTube for "Redmi Note 8 Magisk install"

**Samsung**:
- Bootloader unlock + Odin → Magisk patched AP file flash
- Detailed: search "Samsung A20 Magisk root"

**Note**: Agar root nahi hua tab bhi worker chalega — but anti-detect kam hoga.

#### 3.4 — Phone PC Se Connect Karein
- USB cable se phone connect karein
- Phone pe "Allow USB debugging?" prompt aaye → **Always allow** check karke OK
- PowerShell me run:
  ```powershell
  adb devices
  ```
  Output me phone serial dikhna chahiye, state = `device` (na ke `unauthorized`)

### iPhone (One-Time, ~20 min)

#### 4.1 — iPhone Initial Setup
- Apple ID se sign-in karein (apna ya naya banayein)
- WiFi connect karein

#### 4.2 — PC Se Trust Karwayein
- USB cable se PC se connect karein
- iPhone pe "Trust This Computer?" prompt → **Trust**
- Phone unlock kar ke passcode dalein

#### 4.3 — Optional: Jailbreak (Better Anti-Detect)
- iPhone 7-8 = palera1n jailbreak supported
- iPhone X+ = much harder, mostly broken
- Without jailbreak bhi worker chalega — sirf basic install hoga
- Detailed jailbreak guide: search "palera1n iPhone 8 Windows jailbreak"

#### 4.4 — WiFi Proxy Configuration (One-Time)
**iOS me proxy adb se nahi laga sakte. Manual karna padega**:
1. Settings → WiFi → (i) icon next to your WiFi
2. Configure Proxy → **Manual**
3. Server: aap ka **Proxy Jet** mobile proxy (host:port)
4. Authentication ON, username/password set karein
5. Save

**Note**: Yeh ek baar set karein. Sare iPhone installs is proxy se honge.

#### 4.5 — Verify
PowerShell me:
```powershell
cd C:\krexion\krexion-cpi-worker
.\venv-cpi-worker\Scripts\python.exe -m tidevice3 list
```
Output me iPhone UDID dikhna chahiye.

---

## ✅ Health Check — Doctor Run Karein

```powershell
cd C:\krexion
.\deployment\cpi\KREXION-CPI-DOCTOR.ps1
```

Sab green ✓ dikhe, koi red ✗ na ho. Devices section me **Android + iPhone dono** dikhne chahiye.

---

## 🚀 Worker Start Karein

### Manual Start (Foreground)
```powershell
cd C:\krexion
.\deployment\cpi\KREXION-CPI-WORKER-START.bat
```
Logs live console pe dikhenge. Ctrl+C se stop.

### Auto-Start on Boot (Recommended)
```powershell
cd C:\krexion
.\deployment\cpi\INSTALL-WORKER-AS-SERVICE.ps1
```
Yeh `KrexionCPIWorker` naam ki Windows service install karega. PC reboot pe automatic chalegi.

Service manage karne ke commands:
```powershell
nssm status KrexionCPIWorker      # Check status
nssm restart KrexionCPIWorker     # Restart
nssm stop KrexionCPIWorker        # Stop
```

Logs:
- `C:\krexion\krexion-cpi-worker\worker.out.log`
- `C:\krexion\krexion-cpi-worker\worker.err.log`

---

## 🌐 Web Se Use Karna (Daily Routine)

### Pehli Baar
1. krexion.com open karein
2. Login karein
3. Sidebar me **CPI Devices** click karein → aap ka Android + iPhone "online" dikhne chahiye 🟢
4. **CPI Offers** me ek offer add karein (jo aap ke network panel se mil raha hai)
5. **CPI Jobs** → New Job:
   - Offer select karein
   - Proxies paste (Proxy Jet se)
   - User Agents paste (CPI Devices auto-detect karta hai but manual bhi paste kar sakte hain)
   - Lead data paste (CSV: email,first,last,phone)
   - Total Installs set karein (e.g., 10)
   - **Start** click karein

### Live Monitoring
- **CPI Jobs** page → progress bar real-time update hoga
- **CPI Job Detail** click karein → har install ka step-by-step log
- **CPI Dashboard** → earnings (estimated), conversions, devices online

### Conversions Verify Karna
- Krexion panel **conversion_likely** mark karega worker ne workflow complete kiya
- Aap apne **CPI network panel** (taptrcks etc.) pe ja kar verify karein
- Network panel pe agar conversion register ho gayi → aap ki kamai pakki ✅
- Network panel pe nahi aayi → offer ne reject kiya (anti-detect issue ya geo issue)

---

## 🔧 Daily Maintenance

### Weekly (5 min)
- Phone reboot karein (memory cleanup)
- worker.err.log check karein for errors
- Earnings reconciliation (Krexion vs network panel)

### Monthly (30 min)
- Magisk modules update (phone se)
- Apple ID rotation check (iOS)
- Worker code update: `cd C:\krexion && git pull && nssm restart KrexionCPIWorker`
- Performance review: kis offer pe success rate kam, kis pe zyada

### As-Needed
- Naya phone add karna: connect via USB → worker auto-detect → web UI me dikhega
- Apple ID 2FA prompt aaye → web UI alert dikhega → SMS code aap ke personal phone pe → web UI me code dalein → workflow continue
- JWT expire ho jaaye → krexion.com pe re-login → naya token copy → config.yaml update → worker restart

---

## ⚠️ Important Reminders

1. **Conversion numbers Krexion pe = ESTIMATED**. Asli payout network panel pe verify karein.
2. **Offer-level bans normal hain** — ek offer ban hua to dusra try karein, account level pe rare ban hota hai.
3. **Slow ramp-up karein** — pehla din 5 installs, fir 10, 20, 50… acha record banayein.
4. **Multiple offers parallel chala sakte hain** — sirf devices share karne ka resource constraint.
5. **Geo match karein** — agar offer US-only hai, Proxy Jet ka US IP use karein, locale settings auto-match karega worker.

---

## 📞 Issues / Help

`CPI-FAQ-URDU.md` padhein common issues ke liye.

Worker logs check karein:
```powershell
Get-Content C:\krexion\krexion-cpi-worker\worker.err.log -Tail 50
```

Sab kuch ho gaya — happy earning! 💰
