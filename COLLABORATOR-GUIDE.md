# Krexion — Collaborator Guide (Deploy & Build)

**Purpose:** Ye guide kisi bhi collaborator (ya unke Emergent/AI agent) ko complete picture deta hai kaise Krexion ka deploy + build pipeline chalta hai — taake koi bhi kaam kar sake bina kuch tor phor kiye. Follow this **as-is**. Ye battle-tested hai.

**Last updated:** 2026-01-09 (v2.5.0)
**Repo:** `krexion-com-final/krexion.com-final`
**Owner:** `dennisedmaartins9-sudo`

---

## 🎯 TL;DR — 30-Second Version

- **Sab kuch self-hosted hai.** GitHub-hosted paid runners bilkul use nahi hote (0 minutes consumed).
- **Deploy karne ka tareeqa:** VERSION file bump karo → push to main → 3 workflows automatically fire hoti hain (VPS deploy + Native Windows installer + Electron installer).
- **Deployment infrastructure:**
  - `krexion-vps` runner = VPS pe khud (Linux) → handles VPS deploy + frontend build + mirror-to-CDN jobs
  - `krexion-windows` runner = Owner ki Windows PC → handles Native Windows `.exe` + Electron `.exe` compilation
- **Customer-facing URLs (never change):**
  - `https://krexion.com/api/system/version` — backend
  - `https://krexion.com/downloads/windows/Krexion-Setup-latest.exe`
  - `https://krexion.com/downloads/desktop/Krexion-Desktop-Setup-latest.exe`
  - `https://krexion.com/downloads/desktop/latest.yml` — Electron auto-update manifest

---

## 📐 Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│  DEVELOPER (any collaborator)                                        │
│    git commit + git push origin main                                 │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │  GITHUB (repo main branch)     │
              │  Fires 3 workflows in parallel │
              └────────────────────────────────┘
                    │           │              │
    ┌───────────────┘           │              └─────────────────┐
    ▼                           ▼                                ▼
┌───────────────────┐  ┌────────────────────────────┐  ┌────────────────────────┐
│ deploy.yml        │  │ build-windows-release.yml  │  │ build-electron-        │
│ (any main push)   │  │ (on backend/VERSION path)  │  │ desktop.yml            │
└───────────────────┘  └────────────────────────────┘  │ (on backend/VERSION)   │
    │                          │                       └────────────────────────┘
    │                          │                                │
    ▼                          ▼                                ▼
┌─────────────┐        ┌──────────────────┐              ┌──────────────────┐
│ krexion-vps │        │ build-frontend   │              │ build            │
│ runner      │        │ → krexion-vps    │              │ → krexion-windows│
│ (Linux, on  │        └──────────────────┘              └──────────────────┘
│  the VPS)   │                │                                │
└─────────────┘        ┌───────┴────────┐                       ▼
    │                  ▼                ▼               ┌──────────────────┐
    │           ┌────────────┐  ┌────────────────┐      │ mirror-to-vps    │
    │           │ Bundle     │  │ Build          │      │ → krexion-vps    │
    │           │ backend    │  │ Krexion-       │      │ (curl-based)     │
    │           │ (embedded  │  │ Setup.exe      │      └──────────────────┘
    │           │  Python)   │  │ (installer)    │              │
    │           │ →windows   │  │ →windows       │              │
    │           └────────────┘  └────────────────┘              │
    │                  │                │                       │
    │                  ▼                ▼                       ▼
    │           ┌──────────────────────┐          ┌────────────────────────┐
    │           │ mirror-windows-      │          │ /opt/krexion/downloads │
    │           │ to-vps               │          │ /desktop/ on VPS       │
    │           │ → krexion-vps        │          └────────────────────────┘
    │           │ (curl-based)         │                       │
    │           └──────────────────────┘                       │
    │                     │                                    │
    ▼                     ▼                                    ▼
┌────────────────────────────────────────────────────────────────────┐
│  krexion.com Nginx (docker container)                              │
│    /api/*     → backend container                                  │
│    /*         → frontend static (React build)                      │
│    /downloads/windows/*  → serves Krexion-Setup-latest.exe         │
│    /downloads/desktop/*  → serves Krexion-Desktop-Setup-latest.exe │
│                             + latest.yml (Electron auto-update)    │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                       ┌──────────────────────────┐
                       │  CUSTOMERS                │
                       │    New: download from     │
                       │      krexion.com/downloads│
                       │    Existing Electron:     │
                       │      polls latest.yml     │
                       │      → auto-update prompt │
                       └──────────────────────────┘
```

---

## 🚀 How to Deploy (Standard Flow)

### Scenario 1 — Small change (docs, config, minor bug fix, no customer artifact update needed)

```bash
git commit -m "chore: <description>"
git push origin main
```

**What happens:**
- Only `deploy.yml` fires → VPS deploy (~10 min)
- `krexion.com/api/*` and website reflect the change
- Windows + Electron installers are **NOT** rebuilt (backend/VERSION unchanged)
- Customer PCs continue running previous installer version — no auto-update prompt

### Scenario 2 — Customer-facing release (new features, UI change, backend API change, etc.)

```bash
# 1. Bump the version (2.5.0 → 2.5.1, or whatever next)
echo -n "2.5.1" > backend/VERSION

# 2. Add release notes (optional but recommended)
cat >> backend/VERSION_NOTES.txt << 'EOF'


# v2.5.1 (YYYY-MM-DD) — <short summary>
# - Feature X added
# - Bug Y fixed
EOF

# 3. Commit + push
git add backend/VERSION backend/VERSION_NOTES.txt <other changed files>
git commit -m "v2.5.1 -- <description>"
git push origin main
```

**What happens (fully automatic):**
1. `deploy.yml` fires → VPS deploy (~10 min)
2. `build-windows-release.yml` fires → produces `Krexion-Setup-2.5.1.exe` (~30-40 min on Windows PC)
3. `build-electron-desktop.yml` fires → produces `Krexion-Desktop-Setup-2.5.1.exe` (~25-30 min on Windows PC)
4. All 3 mirror to VPS CDN → `krexion.com/downloads/{windows,desktop}/Krexion-*-latest.*` updated
5. Customer Electron apps poll `latest.yml`, see new version, prompt user to auto-update
6. New customers download from krexion.com and get 2.5.1

**Total time from push to full deploy:** ~40-45 minutes.

**Zero manual intervention.** No SSH, no clicks. Just push.

---

## ⚠️ CRITICAL: Two Runners MUST Be Online

For builds to succeed, both runners must show `online` status:

**Check runner status (any collaborator):**
```bash
curl -s -H "Authorization: token <GITHUB_PAT>" \
  "https://api.github.com/repos/krexion-com-final/krexion.com-final/actions/runners" | \
  python3 -m json.tool
```

Or in GitHub UI (owner account):
👉 https://github.com/krexion-com-final/krexion.com-final/settings/actions/runners

You should see:
```
✅ krexion-vps      status=online  os=Linux
✅ krexion-windows  status=online  os=Windows
```

### If krexion-vps is offline
- Ye owner ki VPS pe systemd service hai (`/opt/krexion-runner`)
- Recovery steps: `RUNNER-SETUP.md` (in repo root)
- SSH into VPS → `sudo systemctl restart actions.runner.*`

### If krexion-windows is offline
- Ye owner ki personal Windows PC pe hai
- **Owner ko contact karo** aur bolen:
  1. PC on karein
  2. Sleep mode disable karein (`powercfg -change -standby-timeout-ac 0`)
  3. PowerShell (Admin) me: `Restart-Service actions.runner.krexion-windows`
- Setup guide: `deployment/windows-runner/WINDOWS-RUNNER-GUIDE.md`

### CRITICAL RULE for owner:
**Before pushing a VERSION-bump commit, ensure your Windows PC is ON and Sleep is DISABLED for the duration of the build (~30-45 min).**

---

## 📋 For AI Agent (Emergent E1) — How to Behave

Agar aap ke paas is repo par kaam karne ke liye ek AI agent hai (jaisa main Emergent E1), toh agent ko ye instructions dena:

### Rules for the agent:

1. **NEVER push without user's explicit "deploy" command.** User batching changes ke liye pehle preview par test karta hai.

2. **NEVER modify these files without user confirmation:**
   - `.github/workflows/*.yml` (deploy pipeline)
   - `backend/VERSION` (release trigger)
   - `RUNNER-SETUP.md` (VPS runner docs)
   - `deployment/windows-runner/*` (Windows runner setup)
   - `docker-compose.yml`, `Dockerfile.*` (production infrastructure)

3. **NEVER install packages via `pip install -U` or `yarn upgrade`** on random files — pin to existing lockfile versions.

4. **NEVER re-run/reset git or push force.** Use `git status` + explicit commit + push.

5. **ALWAYS preserve `.env` gitignore.** Preview environment credentials must never leak to git. Check with `git check-ignore backend/.env`.

6. **ALWAYS pull first before push:** `git pull --rebase origin main` to avoid conflicts (VPS runner may push VERSION bump automations).

7. **When user says "deploy":**
   - If changes are docs/config only → just push (VPS deploys, Windows workflows sleep)
   - If changes are customer-facing → bump `backend/VERSION`, add note to `VERSION_NOTES.txt`, commit + push
   - Monitor workflow status via GitHub API
   - Report failures with specific error → offer targeted fix

8. **When something fails:**
   - Fetch specific job logs (`/actions/jobs/{id}/logs`)
   - Check if runner went offline (`/actions/runners`)
   - Ask user to bring runner back online BEFORE retrying
   - Fix workflow file (if root cause is workflow) → push → let user pick new VERSION for retry

---

## 🔧 Known Issues & Their Permanent Fixes (Already Applied)

Ye issues ek dafa aa chuke hain aur workflows me permanently fix ho gaye hain. Naye collaborator ko dubara face nahi karne padenge:

| # | Issue | Root Cause | Fix (already in repo) |
|---|-------|-----------|----------------------|
| 1 | `svc.cmd not recognized` | Modern actions-runner (v2.315+) removed svc.cmd on Windows | Setup script uses NSSM to wrap `run.cmd` as Windows service |
| 2 | `Bash/WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED` | LocalSystem user can't run WSL bash; GitHub Actions `shell: bash` picked WSL over Git Bash | Runner service env prepends `C:\Program Files\Git\bin` to PATH |
| 3 | `setup.ps1 cannot be loaded because running scripts is disabled` | LocalSystem default PowerShell execution policy is Restricted | `Set-ExecutionPolicy -Scope LocalMachine RemoteSigned -Force` on runner PC |
| 4 | `pwsh: command not found` | `nodejs-lts` choco pkg installs Node 24 not PowerShell 7; Electron workflow uses `shell: pwsh` | `choco install pwsh -y` on runner PC (added to setup script tools list) |
| 5 | `ubuntu-latest` job scheduling fails (runner_id=0) | Org's GitHub-hosted Linux minutes quota exhausted | All Linux jobs moved to `krexion-vps` self-hosted runner |
| 6 | `yarn: command not found` on `krexion-vps` | Self-hosted VPS runner doesn't ship yarn like GitHub-hosted does | Workflow enables yarn via `corepack prepare yarn@1.22.22 --activate` (matches lockfile v1) |
| 7 | `gh: command not found` (mirror jobs) | `gh` CLI not installed on VPS runner | Replaced `gh release download` with pure `curl` + `python3` (universally available) |
| 8 | `Artifact storage quota has been hit` | Private repo 500 MB actions-storage quota exhausted | Mirror jobs use GitHub Release download (releases don't count against quota) |
| 9 | `Cache not found` for frontend cross-runner | Cross-runner cross-OS cache sometimes misses even with `enableCrossOsArchive: true` | build-installer job has "Build frontend locally" fallback that runs when cache miss + artifact miss both happen |
| 10 | Local frontend rebuild fails: `engine "node" incompatible` | Windows PC has Node 24 (via choco); frontend needs Node 20 | Installer job includes `actions/setup-node@v4 with node-version: 20` immediately before local rebuild |

**Meaning for you:** If you ever see any of these errors again, they might be:
- (a) A new manifestation of an old issue (check the setup steps still work)
- (b) A regression (someone modified the fix accidentally)
- (c) Truly new issue (add to this table and fix)

---

## 🛠️ First-Time Windows Runner Setup

**Owner is the only one who ever needs to do this** (once, on their Windows PC). But documented here so any successor can replicate.

### Requirements
- Windows 10 (build 1809+) or Windows 11
- 16 GB RAM, 40 GB free disk
- Broadband internet
- Admin access
- GitHub PAT with `repo` + `workflow` scope

### Steps
1. Download `deployment/windows-runner/SETUP-WINDOWS-RUNNER.bat` + `.ps1`
2. Right-click `.bat` → **Run as administrator**
3. Paste PAT when prompted
4. Wait ~10 min (installs choco, python 3.11, node 20, yarn, inno setup, 7-Zip, git, nssm, pwsh + downloads runner)
5. Verify at https://github.com/krexion-com-final/krexion.com-final/settings/actions/runners → `krexion-windows` = Idle

### If setup script has issues
Full troubleshooting guide: `deployment/windows-runner/WINDOWS-RUNNER-GUIDE.md`

Common one-liners (PS as Admin):
```powershell
# Service missing / crashed — install via NSSM manually
choco install nssm -y
nssm install actions.runner.krexion-windows "C:\krexion-runner\run.cmd"
nssm set actions.runner.krexion-windows AppDirectory "C:\krexion-runner"
nssm set actions.runner.krexion-windows AppEnvironmentExtra "PATH=C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;%PATH%"
nssm set actions.runner.krexion-windows Start SERVICE_AUTO_START
nssm start actions.runner.krexion-windows

# Execution policy blocked
Set-ExecutionPolicy -Scope LocalMachine RemoteSigned -Force
Restart-Service actions.runner.krexion-windows

# Sleep prevention (critical for long builds)
powercfg -change -standby-timeout-ac 0
powercfg -change -standby-timeout-dc 0
```

---

## 📊 How to Monitor a Deploy in Progress

### Web UI (easiest)
Any collaborator can view:
👉 https://github.com/krexion-com-final/krexion.com-final/actions

### CLI (any collaborator with PAT)
```bash
# Get latest 5 workflow runs
curl -s -H "Authorization: token <PAT>" \
  "https://api.github.com/repos/krexion-com-final/krexion.com-final/actions/runs?per_page=5&branch=main" | \
  python3 -m json.tool | grep -E '"name"|"status"|"conclusion"|"head_sha"'

# Get job-level details of a specific run
curl -s -H "Authorization: token <PAT>" \
  "https://api.github.com/repos/krexion-com-final/krexion.com-final/actions/runs/<RUN_ID>/jobs" | \
  python3 -m json.tool

# Get logs of a specific job (may need ~5 min after job completes for logs to be available)
curl -sL -H "Authorization: token <PAT>" \
  "https://api.github.com/repos/krexion-com-final/krexion.com-final/actions/jobs/<JOB_ID>/logs" > logs.txt
```

### Live production verification (any user, no auth needed)
```bash
curl https://krexion.com/api/system/version
curl -I https://krexion.com/downloads/windows/Krexion-Setup-latest.exe
curl -I https://krexion.com/downloads/desktop/Krexion-Desktop-Setup-latest.exe
curl https://krexion.com/downloads/desktop/latest.yml
```

---

## 🚨 Common Deploy Failures & Recovery

### Failure Type A: "Runner offline mid-build"
**Symptom:** Workflow was progressing, suddenly `##[error] The self-hosted runner lost communication with the server`. Job marked failed.

**Cause:** Windows PC went to sleep / lost network / service crashed.

**Recovery:**
1. Owner: bring PC back online, run `Restart-Service actions.runner.krexion-windows`
2. Once runner is `online`, either:
   - **Re-trigger via workflow_dispatch:**
     ```bash
     curl -X POST -H "Authorization: token <PAT>" \
       "https://api.github.com/repos/krexion-com-final/krexion.com-final/actions/workflows/build-electron-desktop.yml/dispatches" \
       -d '{"ref":"main"}'
     ```
   - **Or bump VERSION and re-push** (fresh full cycle)

### Failure Type B: Mirror step failed but build succeeded
**Symptom:** The `.exe` was built and published to GitHub Releases, but `krexion.com/downloads/*` still serves old version.

**Cause:** Mirror job network/permissions issue.

**Recovery:**
- Owner (or agent with VPS SSH) can manually pull the release from GitHub and copy to `/opt/krexion/downloads/{windows,desktop}/`
- Or re-trigger the mirror-only via workflow_dispatch (workflows support it)

### Failure Type C: VERSION bumped but website still shows old version
**Symptom:** `/api/system/version` shows the new number, but `Krexion-Setup-latest.exe` filesize/timestamp is old.

**Cause:** Build finished but mirror didn't run OR ran before build completed (race).

**Recovery:** Same as B — manually copy or re-trigger mirror.

---

## 📁 Repository Layout (Key Files Only)

```
/
├── backend/
│   ├── VERSION                    ← Bump this to trigger Windows + Electron builds
│   ├── VERSION_NOTES.txt          ← Human-readable release notes
│   ├── server.py                  ← Main FastAPI backend
│   └── *.py                       ← Feature modules
├── frontend/
│   ├── package.json               ← Node.js dependencies (yarn.lock v1)
│   └── src/                       ← React app
├── electron-desktop/              ← Electron shell (wraps embedded backend + frontend)
├── desktop/                       ← Native Windows Inno-Setup installer files
├── deployment/
│   └── windows-runner/            ← Owner-only: Windows self-hosted runner setup
│       ├── SETUP-WINDOWS-RUNNER.bat   (main entry)
│       ├── SETUP-WINDOWS-RUNNER.ps1
│       ├── INSTALL-RUNNER-SERVICE.ps1 (post-hoc service fix)
│       └── WINDOWS-RUNNER-GUIDE.md
├── .github/workflows/
│   ├── deploy.yml                     ← VPS deploy (fires on any push to main)
│   ├── build-windows-release.yml      ← Native Windows .exe (fires on backend/VERSION change)
│   └── build-electron-desktop.yml     ← Electron .exe (fires on backend/VERSION change)
├── docker-compose.yml             ← VPS orchestration (nginx + backend + frontend + mongo)
├── RUNNER-SETUP.md                ← VPS runner architecture + recovery
└── COLLABORATOR-GUIDE.md          ← THIS FILE
```

---

## 🎓 Golden Rules

For anyone (human or AI) working on this repo:

1. **Never touch production credentials.** All secrets are in `.env` (gitignored) or GitHub Actions secrets.
2. **Never push force.** History matters for rollback.
3. **Never delete `backend/VERSION` or `VERSION_NOTES.txt`.** These drive the entire release chain.
4. **Never disable `enableCrossOsArchive` on cache steps** without reading the local rebuild fallback logic first.
5. **Always test on preview first** (if you have Emergent access) before pushing to main.
6. **Always describe what changed in the commit message** — commit history is our audit log.
7. **If unsure — ask the owner** (`dennisedmaartins9-sudo`) before pushing.

---

## 💬 One-Line Handoff to Another Collaborator

> "The repo has 2 self-hosted GitHub Actions runners: `krexion-vps` (on my VPS) handles Linux jobs, and `krexion-windows` (on my personal PC) handles Windows compilation. To deploy customer-facing changes, bump `backend/VERSION`, commit, push — everything else is automatic (docker rebuild + Native `.exe` + Electron `.exe` + CDN mirror + auto-update manifest). Zero GitHub minutes used. Full details in `COLLABORATOR-GUIDE.md`. If Windows PC is offline, ping me — I need to unlock it for builds."

---

## 📞 Emergency Contacts

- **Repo owner:** `dennisedmaartins9-sudo` (GitHub)
- **Website:** https://krexion.com
- **Runner status:** https://github.com/krexion-com-final/krexion.com-final/settings/actions/runners
- **Live workflows:** https://github.com/krexion-com-final/krexion.com-final/actions
