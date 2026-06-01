# Krexion — Native Build & Installer System

> **What this is:** A completely new install path that does NOT use Docker. Customer downloads `Krexion-Setup.exe`, double-clicks, done. No Docker icon. No `.py` source files. No Python installation required.
>
> **The existing Docker-based install path (KREXION.bat, install-master.ps1, docker-compose.yml) is 100% untouched** — legacy customers keep working exactly as before.

---

## What's in this folder

```
build/
├── build-backend.py            # Nuitka build script — compiles backend/ → krexion-backend.exe
├── krexion-tray.py             # System tray app (replaces Docker whale icon)
└── krexion-manifest.json       # Integrity hash manifest (filled by GH Actions)

installer/
└── krexion-setup.iss           # Inno Setup script — builds Krexion-Setup.exe

.github/workflows/
└── build-windows-release.yml   # GitHub Actions: auto-builds Windows .exe on push to main

Krexion-Native-Install.ps1      # Alternative: PowerShell installer (no .exe required)
Krexion-Native-Uninstall.ps1    # Clean uninstaller

backend/
├── anti_crack.py               # NEW: HWID + anti-debug + integrity + time-bomb (Phase D)
└── license_module.py           # UPDATED: heartbeat now records hardening telemetry
```

---

## How the new build pipeline works

```
                      ┌──────────────────────────┐
  You push to main →  │  GitHub Actions runner   │
                      │  (windows-latest, free)  │
                      │                          │
                      │  1. Nuitka compiles      │
                      │     backend/*.py to      │
                      │     krexion-backend.exe  │
                      │                          │
                      │  2. Downloads MongoDB    │
                      │     Portable + Chromium  │
                      │                          │
                      │  3. Inno Setup wraps     │
                      │     everything into      │
                      │     Krexion-Setup.exe    │
                      │                          │
                      │  4. Publishes to GH      │
                      │     Releases             │
                      └────────────┬─────────────┘
                                   │
              Customer downloads   ▼
                      ┌──────────────────────────┐
                      │   Krexion-Setup.exe      │
                      │   (Nothing else needed)  │
                      └────────────┬─────────────┘
                                   │
                  Double-click →   ▼
                      ┌──────────────────────────┐
                      │   C:\Program Files\      │
                      │     Krexion\             │
                      │       bin\               │
                      │         krexion-backend  │
                      │         nssm.exe         │
                      │       mongo\             │
                      │       chromium\          │
                      │       frontend\          │
                      │   Services:              │
                      │     • Krexion Backend    │
                      │     • Krexion Database   │
                      │   Tray:  Krexion icon    │
                      └──────────────────────────┘
```

**Customer never sees:**
- ❌ Docker Desktop
- ❌ Docker whale icon
- ❌ Python source code (`.py` files)
- ❌ MongoDB Compass
- ❌ Any third-party branding

**Customer sees:**
- ✅ Krexion in Start Menu
- ✅ Krexion icon in system tray
- ✅ "Krexion Backend" + "Krexion Database" in Services
- ✅ http://127.0.0.1:3000 dashboard

---

## Anti-crack protection (Phase D — already in code)

| Layer | What it does | File |
|---|---|---|
| **HWID binding** | License key tied to specific PC hardware ID | `backend/anti_crack.py::compute_hwid()` |
| **Anti-debug** | Detects IDA, x64dbg, Ghidra, Wireshark, etc. | `backend/anti_crack.py::detect_debugger()` |
| **Binary integrity** | SHA-256 of compiled `.pyd` files vs trusted manifest | `backend/anti_crack.py::check_self_integrity()` |
| **Heartbeat** | License server gets HWID + debug-tools list every validate | `backend/license_module.py` (extended) |
| **Time-bomb** | If no heartbeat for 7 days → license invalid | `backend/anti_crack.py::check_license_freshness()` |
| **Source obfuscation** | Nuitka compiles `.py → .c → .pyd` (native machine code) | `build/build-backend.py` |

**Cloud preview pod always stays no-op** — `KREXION_MODE=cloud` env var disables enforcement so the Emergent demo is never affected.

---

## Triggering a build

### Automatic (recommended)
Every push to `main` triggers `.github/workflows/build-windows-release.yml`.

### Manual + GitHub Release
1. Go to GitHub → Actions → "Build Native Windows Release"
2. Click "Run workflow"
3. Enter a release tag (e.g. `v1.2.3`)
4. Wait ~30-40 minutes
5. Download `Krexion-Setup-1.2.3.exe` from Releases

### Local build (on a Windows dev machine)
```powershell
# Prerequisites: Python 3.11, Inno Setup 6
python -m pip install -r backend/requirements.txt
python -m pip install nuitka ordered-set zstandard
python -m playwright install chromium --no-shell
python build/build-backend.py
# Then build installer:
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer/krexion-setup.iss /DAppVersion=1.0.0
```

Output: `installer/Output/Krexion-Setup-1.0.0.exe`

---

## What the customer experience looks like

### Install
1. Customer downloads `Krexion-Setup.exe` (~250-300 MB — bundled Chromium + MongoDB)
2. Double-clicks → standard Windows installer wizard appears with **Krexion branding**
3. Clicks "Install"
4. ~60 seconds later: dashboard opens at http://127.0.0.1:3000
5. Customer logs in with license key → starts using

### Daily use
- **Krexion** icon in system tray (right-click → Open / Restart Services / View Logs / Quit)
- **Krexion Backend** + **Krexion Database** services auto-start at every Windows boot
- Customer can stop/start services from Services.msc just like any other Windows software

### Uninstall
- Standard Windows "Add or Remove Programs" → Krexion → Uninstall
- Cleanly removes services, files, registry entries, shortcuts

---

## What still requires manual action from you

| Task | When | Who |
|---|---|---|
| Push `main` branch | Whenever you want a new release | You (via Save to GitHub) |
| Tag a release | When ready for customer rollout | You (Actions → Run workflow + tag) |
| Update license server with new HWID-aware license format | Only for first new install | License module already supports it (backward-compatible) |
| Provide `installer/krexion.ico` | Before first build (custom icon) | You (optional — default purple square works) |

---

## Backward compatibility

- **Old customers (Docker install)**: Zero impact. `docker-compose.yml`, `install-master.ps1`, `KREXION.bat`, all 30+ existing .bat scripts work exactly as before.
- **License server (cloud-hosted on emergent preview)**: Zero impact. `anti_crack.py` runs in no-op mode automatically when `KREXION_MODE=cloud`.
- **Existing license keys**: Keep working. New hardening fields are OPTIONAL in the heartbeat request.

---

## Roadmap (future improvements you can add later)

- Code-signing certificate (~$200/yr) so customers don't see "Unknown Publisher" warning
- Auto-update mechanism (already partly built in `backend/releases_module.py`)
- macOS + Linux installers (currently Windows-only)
- Hardware-bound license enforcement strictness toggle (admin UI checkbox)
