# Krexion Desktop — Parallel Electron Build (100% Local PC App)

> **Roman Urdu summary**
> Yeh `electron-desktop/` folder bilkul **alag, parallel** build hai — maujooda
> Inno-Setup wala installer (`installer/krexion-setup.iss`, `BUILD-KREXION.bat`,
> `Build-Krexion-Windows.ps1`) bilkul **untouched** hai. Customer ke PC pe
> Database (MongoDB), Backend (FastAPI) aur Frontend (React) — sab ek hi
> Electron app ke andar local chalte hain, jaise AdsPower. Admin panel cloud
> pe alag chalta rahega.

---

## What this produces

```
dist/Krexion-Desktop-Setup-<version>.exe
```

A single Windows `.exe` (NSIS) that installs **Krexion Desktop** as a
standalone native app. When the customer launches it:

1. A bundled portable **MongoDB** starts on `127.0.0.1:27117` with its data
   in `%APPDATA%\Krexion-Desktop\db\`.
2. The bundled **FastAPI backend** (embedded Python 3.11) starts on
   `127.0.0.1:8088` with `MONGO_URL=mongodb://127.0.0.1:27117` and
   `KREXION_MODE=local`.
3. The packaged **React frontend** (built with `REACT_APP_BACKEND_URL=
   http://127.0.0.1:8088`) loads inside the Electron BrowserWindow.
4. Heavy workload data **never leaves the PC**. Only license / release
   checks hit `krexion.com` (handled by the existing `license_module` /
   `releases_module` already in the backend).

A tray icon lets the customer reopen the dashboard or open log folders.

---

## Layout

```
electron-desktop/
├── package.json                # Electron app metadata + build scripts
├── electron-builder.yml        # Packaging config (NSIS, x64, asar)
├── src/
│   ├── main.js                 # Electron main: spawns mongo + backend, loads UI
│   ├── preload.js              # Minimal contextBridge surface
│   └── splash.html             # Boot splash
├── scripts/
│   └── prepare-resources.js    # Downloads Python embed + Mongo, builds frontend
├── build/
│   ├── installer.nsh           # NSIS firewall rule hook
│   └── icon.ico                # Created at build time from installer/krexion.ico
└── resources/krexion/          # POPULATED AT BUILD TIME — git-ignored
    ├── python/                 # Embedded Python 3.11 + requirements installed
    ├── mongodb/                # Portable MongoDB 7.0.x
    ├── backend/                # Copy of /app/backend (no .env, no caches)
    ├── frontend/               # Production React build with PUBLIC_URL=.
    └── icon.ico
```

`resources/krexion/`, `dist/`, `node_modules/`, `.cache/` are git-ignored.
Nothing committed to the repo is large.

---

## Build locally (Windows)

Prereqs (one-time): **Node.js 20+**, **Python 3.11**, **Yarn**, and an
internet connection (Mongo / Python embed downloads ~250 MB the first run,
cached afterwards in `.cache/`).

```cmd
cd electron-desktop
yarn install
yarn build:win
```

Output:

```
electron-desktop\dist\Krexion-Desktop-Setup-2.1.8.exe
```

---

## Build via GitHub Actions

Workflow: `.github/workflows/build-electron-desktop.yml`

- Trigger manually from the **Actions** tab → **Build Krexion Desktop
  (Electron)** → *Run workflow*.
- Optional input: `release_tag` (e.g. `desktop-v2.1.8`). If provided, the
  built `.exe` is attached to a new GitHub Release with that tag, leaving
  the existing `Krexion-Setup-X.X.X.exe` releases untouched.
- Runs on `windows-latest`. ~15-20 min cold, ~6-8 min warm.

---

## Coexistence guarantees

| Layer                              | Touched by this PR? |
|------------------------------------|---------------------|
| `installer/krexion-setup.iss`      | ❌ no               |
| `Build-Krexion-Windows.ps1`        | ❌ no               |
| `BUILD-KREXION.bat`                | ❌ no               |
| `.github/workflows/build-windows-release.yml` | ❌ no   |
| `backend/`, `frontend/` source code | ❌ no              |
| Cloud deployment / `render.yaml`   | ❌ no               |
| New folder `electron-desktop/`     | ✅ added            |
| New workflow `build-electron-desktop.yml` | ✅ added     |

Both installers (`Krexion-Setup-X.X.X.exe` from Inno Setup **and**
`Krexion-Desktop-Setup-X.X.X.exe` from this Electron build) can ship to
customers in parallel.

---

## Why a separate folder and artifact?

1. **No merge conflicts** — every byte added by this work is inside
   `electron-desktop/` or in a brand-new workflow file.
2. **No accidental release overlap** — the artifact name is
   `Krexion-Desktop-Setup-*.exe`, not `Krexion-Setup-*.exe`.
3. **No backend changes** — the backend already supports
   `MONGO_URL=mongodb://127.0.0.1` (the Inno installer uses the same
   pattern), so no Python code needs to change.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `prepare-resources` fails downloading MongoDB | Re-run; downloads are cached in `electron-desktop\.cache\`. |
| `yarn build` for frontend errors out about `REACT_APP_BACKEND_URL` | The script already sets it. Confirm Node 20+ and Yarn are on PATH. |
| Installed app shows blank window | Open `%APPDATA%\Krexion Desktop\logs\backend.log` and `mongo.log`. |
| Port 27117 / 8088 in use | Close the conflicting process or change `MONGO_PORT` / `BACKEND_PORT` in `src/main.js`. |
