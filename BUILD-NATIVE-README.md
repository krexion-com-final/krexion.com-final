# Krexion — Native White-Label Installer

> **Goal:** Customer downloads ONE `.exe` file from `krexion.com/download`, double-clicks, enters their license key, and Krexion is ready in ~90 seconds. No Docker. No "Python". No third-party folder names. Pure Krexion branding from start to finish — exactly like AdsPower or any other commercial Windows app.

---

## What customers see

| Where | Customer sees |
|---|---|
| Download | `Krexion-Setup-1.1.0.exe` (~300 MB, single file) |
| Setup wizard | "Krexion Setup — Welcome / License / Install / Finish" — Krexion icon, Krexion publisher |
| Program Files | `C:\Program Files\Krexion\bin\krexion-core.exe`, `database\`, `browser-engine\`, `frontend\` |
| Services.msc | **Krexion Backend** + **Krexion Database** (no MongoDB, no Python) |
| Task Manager | `krexion-core.exe` process (no python.exe) |
| Start Menu | "Krexion" |
| Desktop | "Krexion" icon (opens http://127.0.0.1:3000) |
| Tray | Krexion icon |
| Add/Remove Programs | "Krexion" by Krexion |

**Hidden from customer:** MongoDB, Python embeddable runtime, Playwright/Chromium, NSSM, Inno Setup branding.

---

## End-to-end build & release flow

```
                   ┌──────────────────────────────────────────┐
                   │  ON YOUR WINDOWS VPS / DEV PC           │
                   │                                          │
                   │  Double-click  BUILD-KREXION.bat         │
                   │                                          │
                   │  → Downloads Python embeddable           │
                   │  → pip-installs requirements             │
                   │  → Compiles .py → .pyc and deletes .py   │
                   │  → Copies python.exe → krexion-core.exe  │
                   │  → Downloads MongoDB + Chromium + NSSM   │
                   │  → Renames mongo/ → database/            │
                   │            chromium-bundle/ → browser-   │
                   │                              engine/     │
                   │  → Builds React frontend                 │
                   │  → Inno Setup compiles                   │
                   │                                          │
                   │  Output:                                 │
                   │  installer\Output\Krexion-Setup-X.X.X.exe│
                   └────────────────────┬─────────────────────┘
                                        │
                                        │  1. Upload to GitHub Releases
                                        ▼
                   ┌──────────────────────────────────────────┐
                   │  https://github.com/<org>/krexion.com/   │
                   │       releases/download/vX.X.X/          │
                   │       Krexion-Setup-X.X.X.exe            │
                   └────────────────────┬─────────────────────┘
                                        │
                                        │  2. Paste URL into admin panel
                                        ▼
                   ┌──────────────────────────────────────────┐
                   │  krexion.com/admin → Releases → New      │
                   │                                          │
                   │  Version:      1.1.0                     │
                   │  Title:        Krexion 1.1.0             │
                   │  Download URL: https://github.com/...exe │
                   │  Published:    [✓]                       │
                   └────────────────────┬─────────────────────┘
                                        │
                                        │  3. Customer flow
                                        ▼
                   ┌──────────────────────────────────────────┐
                   │  Customer visits krexion.com/download    │
                   │  → Enters KRX-XXXX-XXXX-XXXX-XXXX        │
                   │  → Clicks "Download Krexion for Windows" │
                   │  → Backend 302-redirects to GitHub asset │
                   │  → Customer's browser downloads .exe     │
                   │  → Customer double-clicks .exe           │
                   │  → Inno Setup wizard:                    │
                   │       Welcome → License key → Install    │
                   │  → ~90 sec later: dashboard opens at     │
                   │       http://127.0.0.1:3000              │
                   └──────────────────────────────────────────┘
```

---

## Building the installer (step-by-step)

### On your Windows VPS

1. **Install prerequisites once:**
   - Python 3.11 from python.org (check "Add to PATH")
   - Node.js 20+ from nodejs.org
   - `npm install -g yarn`

2. **Pull the latest code:**
   ```cmd
   cd C:\krexion-repo
   git pull
   ```

3. **Run the one-click builder:**
   - Double-click `BUILD-KREXION.bat` in the repo root
   - Click "Yes" on UAC
   - Wait ~20-30 minutes (first run downloads Python/Mongo/Chromium ~600 MB)

4. **Find your installer:**
   ```
   installer\Output\Krexion-Setup-1.0.0.exe
   ```

### Publishing to customers

1. Upload `Krexion-Setup-X.X.X.exe` to GitHub Releases:
   - Go to https://github.com/<org>/krexion.com/releases
   - "Draft a new release"
   - Tag: `v1.1.0` | Title: `Krexion 1.1.0`
   - Drag the .exe into "Attach binaries"
   - "Publish release"
   - **Copy the asset URL** (right-click the .exe → "Copy link")

2. Wire it to your dashboard:
   - Login to krexion.com/admin
   - **Releases** → "New release"
   - Version: `1.1.0`
   - Download URL: paste the GitHub URL
   - Published: ✅
   - Save

3. Done! Customers visiting `/download` will now get the .exe.

---

## What's white-labeled

| Original | Renamed to | Where customer sees it |
|---|---|---|
| `python.exe` | `krexion-core.exe` | Task Manager, Services.msc |
| `nssm.exe` | `krexion-service.exe` | Inside `bin/` (rarely browsed) |
| `mongo/` folder | `database/` | `C:\Program Files\Krexion\database\` |
| `chromium-bundle/` folder | `browser-engine/` | `C:\Program Files\Krexion\browser-engine\` |
| MongoDB service | "Krexion Database" | Services.msc display name |
| FastAPI/Uvicorn service | "Krexion Backend" | Services.msc display name |

---

## License key flow

The installer wizard asks for the license key **during setup**, so customers don't need to know about `.env` files or copy keys manually after install.

**How it works:**
1. Customer types `KRX-XXXX-XXXX-XXXX-XXXX` into the wizard's "License Activation" page
2. Inno Setup writes it to `%PROGRAMDATA%\Krexion\license-key.txt`
3. The Krexion Backend service starts with `LICENSE_KEY_FILE=%PROGRAMDATA%\Krexion\license-key.txt` set as an environment variable
4. The backend reads the file on startup and validates against the cloud license server

If a customer leaves the field blank, they can still enter the key later from the Krexion dashboard.

---

## Backwards compatibility

- **Old Docker-based customers**: unaffected. The `Krexion-User-Package/` ZIP is still served when no native release is published. They can update to the native installer whenever they uninstall the Docker version.
- **Cloud preview pod (`KREXION_MODE=cloud`)**: never affected by any of this — installer flow is purely customer-facing.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails: "Python not found" | Install Python 3.11 and tick "Add to PATH" |
| Build fails: "yarn not found" | `npm install -g yarn` |
| Inno Setup compile fails | `BUILD-KREXION.bat` auto-installs Inno Setup via Chocolatey; or install manually from https://jrsoftware.org/isinfo.php |
| Customer download shows ZIP instead of EXE | Admin: create a new release with the GitHub `.exe` URL in "Download URL" |
| Customer's `Krexion-Setup.exe` won't open | Verify the GitHub release is **public** (not draft) and the URL ends in `.exe` |
