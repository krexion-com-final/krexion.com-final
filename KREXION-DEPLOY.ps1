# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                  ║
# ║            KREXION — ONE-CLICK DEPLOY / UPGRADE                 ║
# ║                                                                  ║
# ║  • Fresh PC?  → Installs Docker + Git, clones repo, configures,  ║
# ║                  builds, starts. Done.                            ║
# ║  • Existing?  → Backs up Mongo, git pulls, rebuilds, restarts.    ║
# ║                                                                   ║
# ║  Run:                                                             ║
# ║   1) Open PowerShell AS ADMINISTRATOR                             ║
# ║   2)  iwr -UseBasicParsing https://raw.githubusercontent.com/     ║
# ║         ronaldsexedwards40-glitch/dynabook/main/                   ║
# ║         KREXION-DEPLOY.ps1 | iex                                 ║
# ║                                                                   ║
# ║  OR (after first install):                                        ║
# ║   cd C:\krexion                                                  ║
# ║   .\KREXION-DEPLOY.ps1                                           ║
# ║                                                                   ║
# ╚══════════════════════════════════════════════════════════════════╝

#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$InstallPath  = "C:\krexion",
    [string]$RepoUrl      = "https://github.com/ronaldsexedwards40-glitch/dynabook.git",
    [string]$Branch       = "main",
    [switch]$SkipBackup,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference     = "SilentlyContinue"

# ── Pretty output helpers ────────────────────────────────
function H1($t) { Write-Host "`n╔═════════════════════════════════════╗" -ForegroundColor Cyan; Write-Host "║ $t" -ForegroundColor Cyan; Write-Host "╚═════════════════════════════════════╝`n" -ForegroundColor Cyan }
function Step($n,$t) { Write-Host "`n[$n] $t" -ForegroundColor Cyan }
function OK($t)   { Write-Host "    ✓ $t" -ForegroundColor Green }
function Warn($t) { Write-Host "    ! $t" -ForegroundColor Yellow }
function Err($t)  { Write-Host "    ✗ $t" -ForegroundColor Red }

H1 "Krexion Deploy — $((Get-Date).ToString('yyyy-MM-dd HH:mm'))"

$IsExisting = Test-Path (Join-Path $InstallPath "docker-compose.yml")
if ($IsExisting) {
    Write-Host " Mode: UPGRADE existing install at $InstallPath" -ForegroundColor Yellow
} else {
    Write-Host " Mode: FRESH install at $InstallPath" -ForegroundColor Green
}

# ────────────────────────────────────────────────────────
# 1. PREREQS — Docker Desktop + Git
# ────────────────────────────────────────────────────────
Step 1 "Checking prerequisites…"

# Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Warn "Git not found, installing via winget…"
    winget install --id Git.Git --silent --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
OK "Git: $((git --version) -split '\s+' | Select-Object -Last 1)"

# Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Warn "Docker not found, installing Docker Desktop via winget…"
    winget install --id Docker.DockerDesktop --silent --accept-source-agreements --accept-package-agreements
    Write-Host "`n  ⚠ Docker Desktop installed. PLEASE:" -ForegroundColor Yellow
    Write-Host "     1. Start Docker Desktop from Start menu"
    Write-Host "     2. Wait for it to finish initializing (whale icon stops animating)"
    Write-Host "     3. Re-run this script.`n"
    exit 1
}

# Verify Docker is running
try {
    docker info 2>&1 | Out-Null
    OK "Docker: running"
} catch {
    Err "Docker is installed but not running. Start Docker Desktop and re-run this script."
    exit 1
}

# ────────────────────────────────────────────────────────
# 2. CLONE OR PULL
# ────────────────────────────────────────────────────────
if ($IsExisting) {
    Step 2 "Pulling latest code from $Branch…"
    Push-Location $InstallPath
    # Stash any local changes (shouldn't have any, but safety)
    git stash push -u -m "auto-stash by KREXION-DEPLOY $(Get-Date -Format yyyyMMdd-HHmmss)" 2>&1 | Out-Null
    git fetch origin
    git checkout $Branch
    git pull --ff-only origin $Branch
    Pop-Location
    OK "Code updated"
} else {
    Step 2 "Cloning $RepoUrl into $InstallPath…"
    if (Test-Path $InstallPath) {
        if (-not $Force) {
            Err "$InstallPath exists but is not a Krexion install. Use -Force to overwrite."
            exit 1
        }
        Remove-Item -Recurse -Force $InstallPath
    }
    git clone --branch $Branch $RepoUrl $InstallPath
    OK "Clone complete"
}

# ────────────────────────────────────────────────────────
# 3. .env BOOTSTRAP
# ────────────────────────────────────────────────────────
Step 3 "Configuring environment (.env)…"
$envFile     = Join-Path $InstallPath ".env"
$envExample  = Join-Path $InstallPath ".env.example"

if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile

    # Generate strong random secrets
    $jwtSecret    = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object { [char]$_ })
    $postbackTok  = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    $adminPwd     = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 16 | ForEach-Object { [char]$_ })

    $envContent = Get-Content $envFile
    $envContent = $envContent -replace 'JWT_SECRET_KEY=.*', "JWT_SECRET_KEY=$jwtSecret"
    $envContent = $envContent -replace 'POSTBACK_TOKEN=.*', "POSTBACK_TOKEN=$postbackTok"
    $envContent = $envContent -replace 'ADMIN_PASSWORD=.*', "ADMIN_PASSWORD=$adminPwd"
    Set-Content $envFile $envContent

    OK ".env generated with random secrets"
    Write-Host "`n    ┌─ Save these credentials ─────────────────────────────┐"  -ForegroundColor Yellow
    Write-Host "    │ Admin Email    : admin@krexion.local                │"  -ForegroundColor Yellow
    Write-Host "    │ Admin Password : $adminPwd                  │"  -ForegroundColor Yellow
    Write-Host "    └──────────────────────────────────────────────────────┘`n"  -ForegroundColor Yellow
    Write-Host "    Edit $envFile to customize APP_URL, PUBLIC_BASE_URL, RESEND_API_KEY, TUNNEL_TOKEN.`n"
} else {
    OK ".env exists — preserved"
}

# ────────────────────────────────────────────────────────
# 4. BACKUP MONGO (UPGRADE mode only)
# ────────────────────────────────────────────────────────
if ($IsExisting -and (-not $SkipBackup)) {
    Step 4 "Backing up MongoDB…"
    $backupDir = Join-Path $InstallPath "backups\$(Get-Date -Format yyyyMMdd-HHmmss)"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    try {
        docker compose -f (Join-Path $InstallPath "docker-compose.yml") exec -T mongo mongodump --archive | Out-File -FilePath (Join-Path $backupDir "mongo.archive") -Encoding byte
        OK "Backup → $backupDir"
    } catch {
        Warn "Mongo backup skipped (container may not be running): $_"
    }
}

# ────────────────────────────────────────────────────────
# 5. BUILD + START
# ────────────────────────────────────────────────────────
Step 5 "Building Docker images…"
Push-Location $InstallPath
docker compose down --remove-orphans 2>&1 | Out-Null

# ── Detect total system RAM and pick the right profile ──────────────
$totalRamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 0)
Write-Host "    Detected system RAM: $totalRamGB GB"
$composeFiles = @("-f", "docker-compose.yml")
if ($totalRamGB -le 10 -and (Test-Path (Join-Path $InstallPath "docker-compose.lowram.yml"))) {
    Warn "RAM <= 10 GB — enabling LOW-RAM profile (Mongo 1G, Backend 2.5G, RUT max 2 concurrent)."
    $composeFiles += @("-f", "docker-compose.lowram.yml")

    # Also nudge WSL config if it's missing or unset
    $wslcfg = Join-Path $env:USERPROFILE ".wslconfig"
    if (-not (Test-Path $wslcfg) -or -not (Select-String -Path $wslcfg -Pattern "^memory=" -Quiet)) {
        Warn "No WSL memory cap found — writing $wslcfg (memory=5GB) so Docker can't eat all 8 GB."
        @"
[wsl2]
memory=5GB
processors=4
swap=4GB
localhostForwarding=true

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
"@ | Out-File -FilePath $wslcfg -Encoding ascii
        Warn "After this script finishes, run  wsl --shutdown  and then restart Docker Desktop ONCE so the new cap takes effect."
    }
}

docker compose @composeFiles build --pull
OK "Build complete"

Step 6 "Starting services…"
$tunnelToken = (Get-Content $envFile | Where-Object { $_ -match '^TUNNEL_TOKEN=' }) -replace '^TUNNEL_TOKEN=', ''
if ($tunnelToken -and $tunnelToken.Trim() -ne "") {
    Write-Host "    Cloudflare Tunnel token found — starting with tunnel"
    docker compose @composeFiles --profile tunnel up -d
} else {
    Write-Host "    No tunnel token — starting without tunnel (backend on localhost:8001 only)"
    docker compose @composeFiles up -d
}
Pop-Location

# Wait for backend health
Write-Host "    Waiting for backend to become healthy…"
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest "http://localhost:8001/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if ($ok) { OK "Backend is healthy on http://localhost:8001" } else { Warn "Backend not responding on :8001 yet — check `docker compose logs -f backend`" }

# Wait for frontend (nginx) to be reachable
Write-Host "    Waiting for frontend (port 3000)…"
$frontOk = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest "http://localhost:3000" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $frontOk = $true; break }
    } catch { }
}
if ($frontOk) { OK "Frontend is serving on http://localhost:3000" } else { Warn "Frontend not responding on :3000 yet — check `docker compose logs -f frontend`" }

# Read admin credentials from .env for final printout
$adminEmail = ((Get-Content $envFile | Where-Object { $_ -match '^ADMIN_EMAIL=' }) -replace '^ADMIN_EMAIL=', '').Trim('"')
$adminPass  = ((Get-Content $envFile | Where-Object { $_ -match '^ADMIN_PASSWORD=' }) -replace '^ADMIN_PASSWORD=', '').Trim('"')

# ────────────────────────────────────────────────────────
# 7. SUMMARY
# ────────────────────────────────────────────────────────
H1 "DEPLOY COMPLETE"

Write-Host "  Open in browser   : " -NoNewline -ForegroundColor Green
Write-Host "http://localhost:3000" -ForegroundColor Yellow
Write-Host "  Admin login       : http://localhost:3000/admin-login" -ForegroundColor Green
Write-Host "    email           : $adminEmail"
Write-Host "    password        : " -NoNewline
Write-Host "$adminPass" -ForegroundColor Yellow
Write-Host "    (also stored in $envFile as ADMIN_PASSWORD)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Backend API       : http://localhost:8001"
Write-Host "  API docs          : http://localhost:8001/docs"
Write-Host "  Public tunnel     : (Cloudflare Tunnel — only if TUNNEL_TOKEN set in .env)"
Write-Host ""
Write-Host "  Useful commands:" -ForegroundColor Cyan
Write-Host "    cd $InstallPath"
Write-Host "    docker compose ps          # status"
Write-Host "    docker compose logs -f     # live logs"
Write-Host "    .\KREXION-UPDATE.bat      # quick update next time"
Write-Host "    .\KREXION-STOP.bat        # stop everything"
Write-Host ""
Write-Host "  CPI Worker (when phones arrive):" -ForegroundColor Cyan
Write-Host "    .\deployment\cpi\KREXION-CPI-SETUP.ps1"
Write-Host ""

# Mark this PowerShell session as deployed
$global:KREXION_DEPLOYED = $true
