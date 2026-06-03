# Krexion Desktop Dashboard (`/desktop`)

This folder is the customer-facing **PyWebView + pystray** dashboard that
ships inside the native Windows installer. It is the **only GUI** the
user sees on their PC — krexion.com is the main cloud UI, and this
window is a lightweight companion that:

- Stays open until the customer explicitly Quits from the tray menu
  (closing the window minimises to tray — never silently dies)
- Shows live status of the local Krexion services (Backend + Database)
- Displays CPU / RAM / heavy-job throughput in real time
- Reports the PC's adaptive **capacity tier** (low / medium / high /
  extreme) and the max concurrent heavy jobs the runtime will allow
- Surfaces auto-update banners as soon as the admin publishes a new
  release on krexion.com — one-click silent install

## File map

```
desktop/
├── __init__.py
├── krexion_dashboard.py      # PyWebView window + pystray tray icon entry
├── updater.py                 # Self-update orchestrator (download + run)
├── system_info.py             # PC specs detection (psutil + installer JSON)
├── krexion_tray_launcher.bat  # .bat shim installed to {app}\krexion-tray.bat
└── static/
    ├── index.html             # Dashboard markup
    ├── style.css              # Dark theme styling
    └── dashboard.js           # Local + cloud polling loops
```

## How it's bundled

The GitHub Actions workflow (`.github/workflows/build-windows-release.yml`)
runs `build/build-backend.py`, which:

1. Downloads Python 3.11.9 embeddable Windows distribution
2. Installs `pywebview`, `pystray`, `Pillow`, `psutil`, `requests`
3. Copies this `desktop/` folder verbatim into
   `build/dist/krexion-backend.dist/app/desktop/`
4. Renames `python.exe` → `krexion-core.exe`, `pythonw.exe` →
   `krexion-coreapp.exe`, deletes the originals so Task Manager never
   shows third-party branding
5. Uses `verpatch.exe` to rewrite the renamed binaries' PE Version Info
   (FileDescription / CompanyName / ProductName) so customers see the
   Krexion brand even in process details views

The Inno Setup installer (`installer/krexion-setup.iss`) then:

1. Lays the bundle out under `C:\Program Files\Krexion\bin\`
2. Drops `desktop/krexion_tray_launcher.bat` at `{app}\krexion-tray.bat`
3. Registers the launcher in `HKCU\...\Run` (autostart on login)
4. Pops the Inno final-page "Launch Krexion now" checkbox which fires
   the .bat → `krexion-coreapp.exe -m desktop.krexion_dashboard`

## Endpoints the dashboard talks to

| Method | URL | Why |
| --- | --- | --- |
| `GET` | `http://127.0.0.1:8001/api/desktop/stats` | Live CPU/RAM/jobs payload (polled every 2 s) |
| `GET` | `https://krexion.com/api/system/public-latest` | Auto-update banner (polled every 15 min) |
| `POST` | `http://127.0.0.1:8001/api/desktop/run-update` | Customer clicks Update Now |

## Adaptive capacity tiers

Detection runs **twice**: once in the installer's `[Code]` section (so
the customer sees their tier immediately, even before the backend
starts) and once at runtime via psutil:

| Tier | Condition | Max concurrent heavy jobs |
| ---: | --- | ---: |
| `low` | <= 4 GB RAM **or** <= 2 cores | 1 |
| `medium` | <= 8 GB RAM **or** <= 4 cores | 2 |
| `high` | <= 16 GB RAM **or** <= 8 cores | 4 |
| `extreme` | 16+ GB RAM **and** 8+ cores | 8 |

Installer-detected values are written to
`%PROGRAMDATA%\Krexion\system-specs.json` and read by the backend on
startup to size the heavy-job semaphore. This means a customer with 4
cores / 8 GB RAM will **never** be asked to run 8 heavy jobs at once —
their PC stays responsive, and the VPS never sees the load either.
