# Krexion Windows Self-Hosted Runner — Setup Guide (Urdu + English)

**Last updated:** 2026-01-09
**Runner label:** `krexion-windows` · `self-hosted` · `windows` · `X64`
**Repo:** `krexion-com-final/krexion.com-final`

---

## Ye kyun chahiye? (Why this exists)

GitHub Actions ka `windows-latest` runner har build par paid Windows minutes consume karta hai (~10x cost vs Linux). Free tier khatam hone par:

- `Krexion-Setup-<ver>.exe` (Native Inno-Setup installer) build nahi hota
- `Krexion-Desktop-Setup-<ver>.exe` (Electron installer) build nahi hota
- Customers ko naya `.exe` nahi milta → auto-update chain break ho jati hai

**Solution:** Aap ki apni Windows PC pe ek permanent runner install karo. Jab bhi aap `main` branch me push karo (aur `backend/VERSION` bump ho), ye PC automatically dono `.exe` build kar ke:

1. GitHub Release bana degi
2. `krexion.com/downloads/windows/` aur `krexion.com/downloads/desktop/` par mirror kar degi (via VPS SCP)
3. Customer PCs ko `latest.yml` update mil jayegi → auto-update prompt

**Cost:** ZERO GitHub minutes. Sirf aap ki PC ki bijli/internet.

---

## Requirements (System)

| Item | Minimum | Recommended |
|------|---------|-------------|
| OS | Windows 10 (build 1809+) ya Windows 11 | Windows 11 |
| RAM | 8 GB | 16 GB |
| Disk free | 20 GB | 40 GB (Chromium bundle + Node cache + MongoDB portable) |
| Network | Broadband, stable outbound HTTPS | Fiber/wired |
| Admin rights | **Required** — script sirf admin ke tor par chalega | — |
| Availability | PC on rahe deploy ke waqt (~30-45 min per build) | Always-on |

**Firewall:** outbound HTTPS to `*.actions.githubusercontent.com`, `api.github.com`, `github.com`, `objects.githubusercontent.com`, `chocolatey.org`, `nodejs.org`, `python.org`, `fastdl.mongodb.org` — normally koi issue nahi hota.

---

## Setup — 3 Easy Steps

### Step 1 — Files download karo apni Windows PC pe

Aap ke GitHub repo se in 2 files ko apni Windows PC par download karo:

```
deployment/windows-runner/SETUP-WINDOWS-RUNNER.bat
deployment/windows-runner/SETUP-WINDOWS-RUNNER.ps1
```

Sab se aasan tareeqa: repo `main` branch se ZIP download karo → extract → `deployment/windows-runner/` folder me jao.

### Step 2 — GitHub PAT tayaar karo

Aap ke paas pehle se hai (`ghp_zYe4...`). Verify kar lo ke iske scopes me `repo` + `workflow` hain:
https://github.com/settings/tokens

Agar naya banana ho: https://github.com/settings/tokens/new
Scopes: `repo`, `workflow` — expiration jitni bhi (recommended: 90 days ya "no expiration").

### Step 3 — Run karo (Administrator ke tor par)

`SETUP-WINDOWS-RUNNER.bat` par right-click → **"Run as administrator"**

Prompt me apna PAT paste karo. Bas.

Script khud kar degi:
1. Chocolatey install
2. Python 3.11, Node 20, Yarn, Inno Setup 6, 7-Zip, Git install
3. GitHub Actions runner (latest, ~150 MB) download
4. Runner ko `C:\krexion-runner\` me extract
5. GitHub par `krexion-windows` naam se register
6. Windows Service ke tor par install (PC reboot par bhi auto-start)
7. Service start + verify

**Time:** ~5-10 minutes (first time, depends on internet).

**Sab kuch ho jane ke baad verify karo:**
https://github.com/krexion-com-final/krexion.com-final/settings/actions/runners

Aap ko `krexion-windows` idle (green) status me dikhna chahiye.

---

## Verify karo ke sab kuch chal raha hai

**GitHub par:**
- Actions → Runners → `krexion-windows` = green dot / Idle

**Aap ki PC par:**
```powershell
Get-Service -Name "actions.runner.*"
# Status  : Running
# Name    : actions.runner.krexion-com-final-krexion.com-final.krexion-windows
```

**Test deploy karo:**
1. Repo me `backend/VERSION` me ek chhota bump karo (e.g. `2.4.2` → `2.4.3`)
2. `git push origin main`
3. Actions tab par 3 workflows trigger honge:
   - **Deploy to VPS** — `krexion-vps` runner par (Linux, VPS pe khud)
   - **Build Native Windows Release** — `krexion-windows` runner par (aap ki PC!)
   - **Build Krexion Desktop (Electron)** — `krexion-windows` runner par
4. ~30-45 min me dono `.exe` GitHub Release aur `krexion.com` par publish

---

## Har deploy par kya hota hai?

Push to `main` (with VERSION bump) →

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub                                                         │
│    └─> deploy.yml       -> krexion-vps    (~10 min)  VPS deploy │
│    └─> build-windows... -> krexion-windows (~25 min) .exe #1    │
│    └─> build-electron.. -> krexion-windows (~30 min) .exe #2    │
└─────────────────────────────────────────────────────────────────┘

Same commit SHA. Same VERSION. Sab teenon parallel chalte hain.
Deploy VPS pe pehle finish ho jata hai; Windows builds thodi der lagti hai.
```

**Miss nahi hoga kuch:**
- VPS pe naya backend + frontend deploy hote hi
- Aap ki PC dono installers same version ke bana deti hai
- Customer PCs ko `latest.yml` mil jati hai → next launch par auto-update prompt

---

## Troubleshooting

### Q1: "Runner offline" GitHub par dikha raha hai

**Reason:** PC off ho gayi, service stop ho gayi, ya internet issue.

**Fix:**
```powershell
Get-Service -Name "actions.runner.*"        # dekho status kya hai
Restart-Service -Name "actions.runner.*"    # restart karo
```

Ya PC ko simply reboot karo — service auto-start ho jayegi.

### Q2: Build fail hua "yarn install" step par

**Reason:** Node/Yarn PATH me nahi mila. Setup script freshly install karti hai, lekin session me PATH refresh nahi ho paya.

**Fix:** PC ko ek baar reboot karo. Uske baad next build clean chalega.

### Q3: "Inno Setup not found" step par

**Reason:** Chocolatey install hua hoga lekin manually verify karo:
```powershell
choco list --local-only | Select-String innosetup
```

Agar missing hai:
```powershell
choco install innosetup -y
```

### Q4: Runner ek bar chala phir stop ho gaya

**Reason:** GitHub-side runner token expire ho gaya OR credentials corrupt.

**Fix:** Runner ko re-register karo:
```powershell
cd C:\krexion-runner
.\SETUP-WINDOWS-RUNNER.ps1 -GithubPAT "ghp_xxxxx" # (same script fresh runner install kar deti hai)
```

### Q5: PC on rakhna zaroori hai?

Sirf jab aap deploy karte ho tab. Aap batch me deploys karo (multiple changes ek push me) taake PC ka uptime kam ho.

**Best practice:** Push karne se pehle PC on kar lo. Push ke ~45 min baad safely sleep/off kar sakte ho (builds complete + uploaded).

### Q6: Runner ko remove karna hai?

```powershell
# Aap ki PC par:
cd path\to\deployment\windows-runner
.\SETUP-WINDOWS-RUNNER.ps1 -Uninstall -GithubPAT "ghp_xxxxx"
```

Ye service stop → runner unregister from GitHub → `C:\krexion-runner\` delete kar deti hai.

---

## Advanced

### Runner ki state monitoring karo

```powershell
# Service status
Get-Service -Name "actions.runner.*"

# Real-time logs (last 100 lines)
Get-Content "C:\krexion-runner\_diag\Runner_*.log" -Tail 100 -Wait
```

### Multiple runners chahiye (parallel builds)?

Ek PC par sirf 1 runner recommended hai (concurrent builds resource hog karte hain). Agar chahiye:

```powershell
.\SETUP-WINDOWS-RUNNER.ps1 -GithubPAT "ghp_xxx" -RunnerName "krexion-windows-2" -RunnerDir "C:\krexion-runner-2"
```

Aur workflows me labels adjust karo agar specific runner target karna ho.

### Manual registration token (agar PAT flow use nahi karna)

1. Jao: https://github.com/krexion-com-final/krexion.com-final/settings/actions/runners/new
2. Windows chuno
3. `--token` value copy karo (60 min me expire hoti hai)
4. Setup script chalao:
   ```powershell
   .\SETUP-WINDOWS-RUNNER.ps1 -RegistrationToken "AAAA..."
   ```

---

## Security notes

- Runner **admin/system privileges** ke sath chalta hai — kyunke build steps ko admin PowerShell access chahiye (Chocolatey installs, service management).
- Sirf aap ke repo (`krexion-com-final/krexion.com-final`) ke main branch pushes trigger karte hain. External PRs (agar public repo hota) sandbox honge — private repo me sirf collaborators push kar sakte hain.
- Runner ki `_work/` dir me har build ka temp code aa jata hai. Automatically cleanup hoti hai between jobs.
- Agar aap ki PC compromise ho jaye, GitHub Actions runner ko turant remove karo:
  - GitHub: https://github.com/krexion-com-final/krexion.com-final/settings/actions/runners → remove
  - Ya API: `curl -X DELETE -H "Authorization: token <PAT>" https://api.github.com/repos/krexion-com-final/krexion.com-final/actions/runners/<runner_id>`

---

## Bonus — Runner ko normally kaam karte waqt PC slow feel ho raha hai?

Idle me runner ~30 MB RAM, ~0% CPU consume karta hai. Sirf build ke waqt CPU spike aata hai. Agar chahiye ke build low priority par chale:

Edit `C:\krexion-runner\.env` (ya banaao agar nahi hai):
```
ACTIONS_RUNNER_HOOK_JOB_STARTED=C:\krexion-runner\low-priority.ps1
```

Aur `low-priority.ps1`:
```powershell
(Get-Process pwsh -EA SilentlyContinue) + (Get-Process powershell -EA SilentlyContinue) |
  ForEach-Object { $_.PriorityClass = "BelowNormal" }
```

---

## Contact / recovery

Agar setup fail ho jaye ya runner permanently break ho:

1. `WINDOWS-RUNNER-GUIDE.md` (ye file) check karo
2. Logs: `C:\krexion-runner\_diag\Runner_*.log`
3. GitHub Issues: https://github.com/krexion-com-final/krexion.com-final/issues
4. Full reset: `-Uninstall` chalao, phir dobara `SETUP-WINDOWS-RUNNER.bat` chalao

---

**TL;DR:**
1. `SETUP-WINDOWS-RUNNER.bat` → Right-click → Run as administrator
2. PAT paste karo
3. Wait ~10 min
4. Ho gaya. Har deploy par Windows + Electron builds free me automatically ban jayenge.
