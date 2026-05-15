# 🚀 Krexion — Easiest Install Method

> Aap chahte hain ek hi folder, ek hi button click, sab automatic? Yahi hai.

## Step 1 — Folder open karein

Is repo mein **`Krexion-Setup/`** folder hai. Use folder ko USB ya new PC pe copy karein (ya yahin chalain).

## Step 2 — Double-click karein

`Krexion-Setup/` folder ke andar **`Install.bat`** ko double-click karein.

## Step 3 — UAC popup pe "Yes" karein

(Windows Admin permission maange ga)

## Step 4 — Wizard mein big blue **INSTALL** button pe click karein

Bas. Wizard khud:
- ✅ Docker Desktop install karega (auto-download ~520 MB)
- ✅ Git install karega (auto-download ~50 MB)
- ✅ WSL2 ko 5 GB pe cap karega (8 GB PC ke liye safe)
- ✅ Code download karega
- ✅ Random secure admin password generate karega
- ✅ Docker images build karega
- ✅ Sab containers start karega
- ✅ Desktop pe "Krexion" shortcut banayega
- ✅ Browser mein `http://localhost:3000` open karega

## Step 5 — Wait karein (5-30 minutes first time)

Progress bar dikhega. Reboot ki zaroorat hui to wizard khud reboot karwa de ga aur restart ke baad **auto-resume** kar de ga.

## Step 6 — "OPEN KREXION" button pe click karein

Done! Browser mein Krexion open ho jayega. Admin password wizard screen pe + `C:\krexion\.env` mein saved hai.

---

## 📦 Folder Contents

```
Krexion-Setup/
├── Install.bat         ← YE DOUBLE-CLICK KAREIN
├── setup-engine.ps1    ← Wizard ki actual logic (PowerShell)
├── README.txt          ← Detailed English instructions
├── START-HERE.txt      ← 5-line ultra-quick guide
└── bundle/             ← First install ke baad cached installers
    ├── DockerDesktopInstaller.exe   (auto-downloaded, ~520 MB)
    ├── Git-Installer.exe            (auto-downloaded, ~50 MB)
    └── README.txt
```

---

## 🔄 Dusre PC pe install karna ho?

**First PC pe install karne ke baad**, `Krexion-Setup/` folder ko USB pe copy karein.

`bundle/` folder ke andar Docker + Git installers cached ho gaye hain. Dusre PC pe wizard khud detect karega cached files aur **skip karega downloads** — install sirf **5 minute** mein ho jayega, internet nahi b ho to b chal jayega.

> ⚡ **Pro tip**: Aik USB stick → 10 PCs pe install. Bas folder copy karein aur `Install.bat` double-click.

---

## 🐧 Linux / Mac users

Linux/Mac pe ye GUI wizard nahi chalega. Aap use karein:

```bash
sudo bash install-krexion.sh
```

(Repo ke root mein already maujood hai.)

---

## ❓ Issues?

`Krexion-Setup/setup.log` file mein full log save hota hai — agar fail ho to ye file open karke last error dekhein. 90% issues "Docker not running" hote hain — Docker Desktop manually start karke `Install.bat` dobara click karein.

Full troubleshooting: **`Krexion-Setup/README.txt`**
