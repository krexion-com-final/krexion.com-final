# CPI Module — Common Issues FAQ (Urdu)

## 🔋 Hardware / Phone Battery Questions

### Q: Mobile mein battery dead ho ya kharab ho, kya USB se chal jay ga?
**A**: **HAAN, mostly chal jay ga** — but kuch important caveats hain:

✅ **Yeh kaam karega**:
- Battery degraded hai (e.g., 20-50% health) but charge hold karti hai → USB se 24/7 connected rakhein, perfectly chalega
- Battery puri tarah dead nahi (kuch charge baki hai) → USB power se chalata rahega without issues
- Aap ke kaam ke liye **battery health 5%+** kafi hai

⚠️ **Risk areas**:
- **Bulging / swollen battery** = **FIRE HAZARD** ⚠️⚠️⚠️ — yeh AVOID karein, koi bhi sasti deal nahi worth it
- Battery completely 0% / dead-shorted → kuch phones boot nahi karenge bina battery ke (motherboard se direct USB power ka rasta nahi hota har model me)
- iPhone: battery completely dead = boot loop issue ho sakta hai

❌ **NA karein**:
- Battery missing / removed phone (most modern phones ka motherboard battery ke bina chalu nahi hota)
- Visible swelling ya bulge (back panel uthi hui dikhe)

💡 **Sasta kharidne ke liye smart approach**:
- "Battery weak / drains fast" — ✅ ACCEPTABLE (USB se chalega permanent)
- "No charging" — ⚠️ Risky (USB port damage ho sakta hai)
- "Battery 80% health, but no PTA" — ⭐ **BEST DEAL** for our use case (USB always-on + no SIM needed)
- "Phone turns off when unplugged" — ✅ FINE (USB always plugged anyway)

### Q: USB hub se 5-10 phones connect karoon, current fail to nahi karega?
**A**: **POWERED USB hub use karein** (with external 12V/24V adapter) — passive USB hub se 4+ phones charge nahi honge properly:
- ✅ Anker, UGREEN, Sabrent powered hubs (PKR 3,000-6,000 for 7-port)
- ⛔ Cheap unpowered hubs (PKR 500-1,500) — phones randomly disconnect

### Q: Phone USB se charge ho raha lekin "charging slow" warning aati hai?
**A**: Normal hai — most powered USB 2.0 hubs 500-900mA per port deti hain (slow but trickle charge). 24/7 connected hone ki wajah se phone hamesha charged rahega. Performance pe asar nahi.

---

## 🌐 iOS Proxy Auto-Rotation Setup

### Q: iOS me proxy auto-rotate kaise ho jab worker ko phone setting me access nahi?
**A**: RealFlow iss ke liye **local mitmproxy gateway** use karta hai. One-time setup:

**Step 1**: Home PC pe gateway start karein (background mein):
```powershell
cd C:\realflow\realflow-cpi-worker
.\venv-cpi-worker\Scripts\activate
pip install mitmproxy
mitmdump -s ios_proxy_gateway.py --listen-port 8866
```

**Step 2**: iPhone pe **one-time** WiFi proxy config:
- Settings → WiFi → (i) icon → Configure Proxy → **Manual**
- Server: aap ke home PC ka **LAN IP** (ipconfig se nikalein, e.g., 192.168.1.50)
- Port: 8866
- Authentication OFF
- Save

**Step 3**: Bas, ho gaya! Worker har install ke liye apne aap gateway ko bata dega "iss iPhone ke next requests Proxy Jet IP X se jana chahiye". Gateway automatically upstream rotate kar dega.

**Verify**: iPhone me Safari kholein → `whatismyip.com` → Aap ka Proxy Jet IP show hona chahiye, na ke aap ke ghar ka real IP.

---

## 🔴 Setup / Install Issues

### Q: `REALFLOW-CPI-SETUP.ps1` chalu hote hi error: "execution of scripts is disabled"
**A**: PowerShell execution policy block kar rahi hai. Run as Admin karke yeh paste karein:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\REALFLOW-CPI-SETUP.ps1
```

### Q: Setup script "Chocolatey installation failed" pe atak gaya
**A**: Internet check karein. Manual install:
```powershell
[System.Net.ServicePointManager]::SecurityProtocol = 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

### Q: `pip install` failed during setup
**A**: Internet ya Python issue. Manual:
```powershell
cd C:\realflow\realflow-cpi-worker
.\venv-cpi-worker\Scripts\python.exe -m pip install -r requirements.txt
```

### Q: `iTunes installation failed`
**A**: Skip kar sakte hain — sirf libimobiledevice se kaam chal jata hai. Manually install kar sakte hain Apple website se: https://www.apple.com/itunes/

---

## 📱 Android Device Issues

### Q: `adb devices` me phone "unauthorized" dikhata hai
**A**: 
1. Phone unlock karein
2. USB cable disconnect-reconnect karein
3. "Allow USB debugging?" prompt aaye → **Always allow** check karke OK
4. Agar prompt nahi aata: Developer Options → Revoke USB debugging authorizations → reconnect

### Q: `adb devices` empty hai phone connect karne ke baad
**A**:
- USB cable change karein (data cable hona chahiye, charging-only nahi)
- Phone pe USB mode = "File Transfer" set karein
- USB Debugging ON hai? Settings → Developer options
- ADB drivers install: `choco install adb -y`

### Q: Worker Android phone pe install kar raha hai but conversion network panel pe nahi aati
**A**: Anti-detect fail ho gayi. Possible causes:
1. **Phone rooted nahi** — Magisk install karein advanced spoofing ke liye
2. **Proxy quality kharab** — datacenter IP detect ho gaya. Mobile residential 4G use karein.
3. **Geo mismatch** — offer US chahta hai, aap Pakistan se chala rahe hain
4. **Behavior pattern flagged** — Worker ka behavior_min/max increase karein config.yaml me
5. **Offer Play Integrity require karta hai** — emulator/old Android pe kaam nahi karega

### Q: Genymotion / LDPlayer connect nahi ho rahe `adb devices` se
**A**:
```powershell
adb connect 127.0.0.1:5555
# LDPlayer instances usually 5555, 5557, 5559 (odd ports)
adb connect 127.0.0.1:5557
```

### Q: APK install fail ho jaata hai: `INSTALL_FAILED_INVALID_APK`
**A**: APK URL se download nahi ho raha. Check karein:
- APK URL valid hai (browser me khol ke verify)
- Phone storage me space hai (Settings → Storage)
- ABI mismatch (most modern APKs `arm64-v8a` chahte hain)

---

## 🍎 iPhone Issues

### Q: `tidevice3 list` empty hai iPhone connect hone ke baad
**A**:
1. iPhone unlock karein
2. "Trust This Computer?" → **Trust** + passcode dalein
3. iTunes ek baar open karein, phir close (drivers load karta hai)
4. USB cable change karein
5. Different USB port try karein
6. Re-run: `python -m tidevice3 list`

### Q: iPhone pe "Untrusted Enterprise Developer" error during sideload
**A**:
- Settings → General → VPN & Device Management → Developer App → **Trust**
- Phir app dobara open karein

### Q: App Store me "Sign in to download" prompt
**A**: Apple ID logged out hai. Settings → App Store → sign in. Worker isi Apple ID se install karega.

### Q: Apple ID pe "Verification Code Required" 2FA
**A**: Yeh expected hai monthly/weekly. Apke personal phone pe SMS aayega. RealFlow web UI pe alert dikhega — code paste karein.

### Q: iPhone pe install start ho jata hai but app open nahi hota / SDK fire nahi karta
**A**:
- App ke pehle se install hone ki history check karein (uninstall karein dobara try karne se pehle)
- Apple ID country mismatch — agar offer US chahta hai, US Apple ID use karein
- iPhone storage full ho gayi — clear karein

---

## 🌐 Backend / Auth Issues

### Q: Worker startup pe "Auth failed: 401"
**A**: JWT expire ho gaya. realflow.online pe login karein, fresh token copy karein, config.yaml update, worker restart.

### Q: Worker startup pe "Connection refused" / cannot reach api.realflow.online
**A**:
- Cloudflare Tunnel running hai? `cloudflared tunnel info <YOUR_TUNNEL_NAME>`
- DNS resolve ho raha hai? `nslookup api.realflow.online`
- Backend Docker chal raha? `docker compose ps`

### Q: Devices "online" dikhe Web UI me but jobs assign nahi ho rahe
**A**:
- Device type job ke target_os se match karna chahiye (Android-only job iPhone ko nahi assign hoga)
- Job status "running" hona chahiye (queued hai to start karein)
- Worker logs check karein: `Get-Content worker.err.log -Tail 100`

---

## 💰 Conversion Issues

### Q: Worker says "completed" but no conversion in network panel
**A**: This is the most common issue. Reasons:
1. **Offer ne fraud detect kiya** — anti-detect bypass nahi kar paya
2. **Wrong geo** — proxy ne wrong country show kiya
3. **Click-to-install timing too fast** — `pre_install_min_seconds` increase karein
4. **Same device too many installs** — phone ko rotate karein, factory reset karein
5. **Offer SOI/CPL hai, CPI nahi** — yeh form fill expect karta hai (RUT/Form Filler use karein)

### Q: Pehla install convert hua, baki sab fail
**A**: Phone fingerprint repeat ho raha hai. Magisk Props randomization check karein:
- `config.yaml` me `use_magisk_props: true` hona chahiye
- Phone rooted hona chahiye
- Magisk app me LSPosed module install hai?

### Q: Conversion rate 30% se kam hai
**A**: Normal range expected:
- Tier-3 geos (PK/IN/ID): 50-70% conversion
- Tier-1 geos (US/UK): 30-50% conversion
- Premium offers (Adjust + Protect360): 20-40% conversion

Agar 30% se kam → device upgrade karein (real phone vs emulator), proxy quality upgrade, slow ramp-up.

---

## 🛠️ Worker Service Issues

### Q: Service "RealFlowCPIWorker" start nahi ho rahi
**A**:
```powershell
nssm status RealFlowCPIWorker
# Agar SERVICE_PAUSED ya STOPPED:
nssm start RealFlowCPIWorker
# Logs check karein:
Get-Content C:\realflow\realflow-cpi-worker\worker.err.log -Tail 50
```

### Q: PC reboot ke baad worker auto-start nahi ho raha
**A**:
```powershell
nssm set RealFlowCPIWorker Start SERVICE_AUTO_START
```

### Q: Worker memory zyada use kar raha hai
**A**: Normal hai (~200-400MB). Agar 1GB se zyada ho:
- `nssm restart RealFlowCPIWorker`
- Logs check karein for memory leaks

---

## 🔒 Security / Account Safety

### Q: Mera affiliate account ban ho gaya — kya karoon?
**A**:
1. **Account-level ban** (account suspended): network ko email karein. Recovery 30-50% chance.
2. **Offer-level ban** (specific offer rejected): naya offer try karein, anti-detect tighten karein
3. **Naye accounts banayein** different networks pe — diversify

### Q: Apple ID pe "Account Locked" notification
**A**: Apple ne suspect activity detect kiya. Recovery:
- Apple ID portal pe ja kar reset karein
- Alag Apple ID use karein (rotation pool me 3-5 IDs hone chahiye)

### Q: Google account banned (Android)
**A**: Naya Gmail banayein. Phone factory reset karein. Naya GAID, naya Android ID. Magisk se fingerprint full random karein.

---

## 📈 Optimization Tips

1. **Slow ramp-up**: pehla din 5 installs, dusra 10, teesra 20… 1 mahine me 200/day
2. **Geo match**: hamesha proxy + offer geo match karein
3. **Time of day**: real users 9am-11pm install karte hain, na ke 3am
4. **Multiple offers parallel**: 1 device pe 1 install at a time, but 3 devices = 3 parallel offers
5. **Cooldown periods**: same device 2 installs ke beech 30+ min gap
6. **Apple ID warming**: naya Apple ID pe pehle 1-2 free apps install karein, fir CPI offer

---

## 🆘 Emergency Stops

### Sab kuch stop karna hai:
```powershell
nssm stop RealFlowCPIWorker
.\deployment\cpi\REALFLOW-CPI-WORKER-STOP.bat
```

### Phones ko clean state me lana:
```powershell
adb -s <SERIAL> shell pm uninstall com.example.app
adb -s <SERIAL> reboot
```

### iPhones reset:
- Tidevice3 se ya manual phone se Settings → General → Reset → Reset All Settings
