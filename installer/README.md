# Krexion Native Windows Installer — Build & Deploy Guide

This produces **`Krexion-Setup-{version}.exe`** — a single, professionally-branded
Windows installer that replaces the legacy Docker-based ZIP flow with a
**pure native** installation (no Docker, no PowerShell windows, no localhost UI
visible to the customer).

## What the customer experiences

```
1. krexion.com/download  →  downloads  Krexion-Setup-1.0.0.exe   (~150 MB)
2. Double-click  →  UAC prompt  →  Krexion-branded wizard:
       Welcome → License Key (paste KRX-XXXX-...) → Folder → Install → Finish
3. Wizard installs SILENTLY (no console windows):
       - Krexion Database service       (MongoDB Portable, renamed)
       - Krexion Backend service        (Python embedded, renamed krexion-core.exe)
       - Frontend assets                (in case customer ever needs local UI)
       - Start Menu + Desktop shortcuts (open https://krexion.com/login)
4. Finish page → checkbox "Open Krexion dashboard at krexion.com"
5. Add/Remove Programs entry:  "Krexion 1.0.0"   (publisher: Krexion)
```

What the customer **never** sees: Docker, "RealFlow", `localhost:3000`,
PowerShell, `python.exe`, `mongod.exe`, NSSM. Task Manager / Services.msc
only ever show `krexion-core.exe`, `Krexion Backend`, `Krexion Database`.

---

## Architecture (under the hood)

```
   {ProgramFiles}\Krexion\
   ├── krexion.ico                       (brand icon for shortcuts)
   ├── bin\
   │   ├── krexion-core.exe              (Python 3.11 embeddable, renamed)
   │   ├── krexion-service.exe           (NSSM, renamed)
   │   ├── python311.dll                 (CPython runtime)
   │   ├── Lib\site-packages\            (all backend Python deps)
   │   └── app\                          (server.py + all backend modules)
   ├── database\                         (MongoDB Portable, runs on :27017)
   ├── browser-engine\                   (Playwright Chromium — optional)
   ├── frontend\                         (React production build)
   ├── data\db\                          (MongoDB data files)
   └── logs\

   Windows Services (auto-start):
   - KrexionDatabase    →  mongod.exe --port 27017 --bind_ip 127.0.0.1
   - KrexionBackend     →  krexion-core.exe -m uvicorn server:app --port 8001
                            ENV: KREXION_MODE=native, KREXION_BUILD_TYPE=binary
```

---

## How to build

### Trigger the workflow

```bash
# Open: https://github.com/dennisedmaartins9-sudo/krexion.com/actions
#   → "Build Native Windows Release"
#   → "Run workflow" button
#   → release_tag = v1.0.0   (or leave blank for a nightly build)
#   → "Run workflow"
```

The workflow runs three jobs in parallel/sequence:

1. **`build-backend`** *(windows-latest)* — runs `build/build-backend.py`:
   - Downloads Python 3.11.9 embeddable for Windows
   - Bootstraps pip into it
   - Installs ALL `backend/requirements.txt` (minus 11 dev/mobile deps)
   - Copies `backend/*.py` modules into `bundle/app/`
   - Renames `python.exe` → `krexion-core.exe`
   - Produces:  `build/dist/krexion-backend.dist/`  (~180 MB)

2. **`build-frontend`** *(ubuntu-latest)* — `yarn build`:
   - Compiles React frontend with `REACT_APP_BACKEND_URL=http://127.0.0.1:8001`
   - Produces:  `frontend/build/`  (~5 MB)

3. **`build-installer`** *(windows-latest)* — `ISCC.exe`:
   - Downloads MongoDB Portable 7.0.14 (~300 MB extracted)
   - Downloads NSSM (Windows service wrapper)
   - Installs Inno Setup via Chocolatey
   - Compiles `installer/krexion-setup.iss` → `Krexion-Setup-1.0.0.exe`
   - Uploads as a GitHub Actions artifact (and as a Release asset if you used a `release_tag`)

**Build time:** ~12 minutes end-to-end.
**Final size:** ~150 MB after LZMA2/ultra compression.

### Download the built `.exe`

* **Tagged release (recommended):**
  `https://github.com/dennisedmaartins9-sudo/krexion.com/releases/latest`
  → asset → `Krexion-Setup-1.0.0.exe`
* **Nightly / untagged:**
  Actions tab → latest workflow run → Artifacts → `krexion-installer`

---

## How to publish the new `.exe` to your customers

The backend already has the native-installer redirect built-in
(`backend/license_module.py` ~line 514). When a customer hits
`/api/license/download-installer/{key}` and you have a *published*
release whose `download_url` ends in `.exe`, the customer is
**redirected (302)** to that `.exe` and the legacy ZIP path is bypassed.

### Step-by-step

1. **Tag a release**, e.g.:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
   Then run the GitHub Actions workflow with `release_tag=v1.0.0`. Wait ~12 min.

2. **Copy the asset URL** — open the GitHub release, right-click
   `Krexion-Setup-1.0.0.exe` → "Copy link address". URL looks like:
   ```
   https://github.com/dennisedmaartins9-sudo/krexion.com/releases/download/v1.0.0/Krexion-Setup-1.0.0.exe
   ```

3. **Open admin releases** — `https://krexion.com/admin/releases` → click
   **"New release"**:

   | Field | Value |
   |-------|-------|
   | Version | `1.0.0` |
   | Download URL | paste the URL from step 2 |
   | Title | `Krexion 1.0.0 — Native build` |
   | Published | ✅ checked |

   Save.

4. **Verify** — open `https://krexion.com/api/system/installer-info` in a
   browser; it should report `"kind": "native-exe"` with the version.
   Customers hitting `krexion.com/download` from this moment on get the
   `.exe`, not the ZIP.

5. **Roll back at any time** — just **unpublish** the release in the
   admin panel. The license server transparently falls back to the
   legacy ZIP for all customers. Zero data loss.

---

## Local development

If you ever want to dry-run the backend bundler on Linux (just to
validate the layout — Windows binaries won't actually execute):

```bash
cd /app
python3 build/build-backend.py
# Output:  build/dist/krexion-backend.dist/
# Skips pip-install / .exe rename steps on non-Windows hosts.
```

To compile the `.iss` locally (Windows only):

```powershell
choco install innosetup
cd installer
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=1.0.0 krexion-setup.iss
# Output:  installer\Output\Krexion-Setup-1.0.0.exe
```

---

## Phase 2 roadmap (post-MVP)

| Phase | Feature | Effort |
|-------|---------|--------|
| 2a (now) | Native installer, hidden services, krexion.com-only UI | ✅ shipped |
| 2b | Bundle Playwright Chromium (so RUT / Form Filler run locally too) | +1 day; adds ~280 MB to installer |
| 2c | System tray app (`krexion-tray.exe`) with Krexion icon — status, "Open dashboard", "Pause heavy jobs", "Quit" | 3-5 days |
| 2d | Auto-update via Inno Setup `/UPDATE` mode — installer compares its `AppVersion` with the latest published release on krexion.com and self-replaces | 2 days |
| 2e | Code signing with EV cert → no Windows SmartScreen warning on download | 1 day + cert cost (~$300/year) |
| 2f | MSI installer in addition to EXE (for corporate IT deployments via Group Policy) | 2 days |
| 2g | Auto-uninstall the legacy Docker `C:\krexion` folder when the native installer detects it (clean upgrade path for existing customers) | 1 day |

Each phase is **independent and additive** — customers on phase 2a
auto-upgrade when 2b/2c/2d ships, with no manual reinstall needed.
