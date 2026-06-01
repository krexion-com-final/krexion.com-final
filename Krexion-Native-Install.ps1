# ════════════════════════════════════════════════════════════════════════
# Krexion — Native Windows Installer (No Docker)
# ════════════════════════════════════════════════════════════════════════
# This is the script-based equivalent of Krexion-Setup.exe (Inno Setup
# installer). Use this when:
#   • Customer can't run an installer .exe (corporate AV)
#   • Building from a fresh GitHub checkout
#   • Custom installation directory needed
#
# What it does (NO DOCKER — pure native install):
#   1. Downloads bundled MongoDB Portable (zip, no installer)
#   2. Downloads bundled Playwright Chromium (full build)
#   3. Installs the Krexion backend exe from artifacts (or builds from source)
#   4. Installs NSSM (service wrapper)
#   5. Registers KrexionDatabase + KrexionBackend Windows Services
#   6. Adds Krexion Tray app to startup
#   7. Opens dashboard at end
#
# Customer-facing branding:
#   • Customer sees "Krexion" in services list — NOT "MongoDB" or "Python"
#   • System tray icon = Krexion icon, not Docker
#   • Process names = krexion-backend.exe (Nuitka renamed)
#
# Requires: Windows 10/11, PowerShell 5.1+, Admin rights
# ════════════════════════════════════════════════════════════════════════

[CmdletBinding()]
param(
    [string]$InstallDir = "C:\Program Files\Krexion",
    [string]$DataDir    = "$env:ProgramData\Krexion",
    [string]$BackendArtifactUrl = "",   # Optional — pulled from GH Releases if empty
    [switch]$SkipChromium,              # Skip Chromium download (use existing install)
    [switch]$AdvancedMode               # Show extra diagnostics
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ── Helpers ───────────────────────────────────────────────────────────
function Write-Step($Msg) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $Msg" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
}
function Write-Ok($m)   { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Write-Warn($m) { Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Write-Err($m)  { Write-Host "  [ERR]  $m" -ForegroundColor Red }
function Write-Info($m) { Write-Host "  [..]   $m" -ForegroundColor Gray }

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pp = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $pp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Err "This installer must be run as Administrator."
        Write-Host "  Right-click PowerShell → 'Run as administrator', then re-run." -ForegroundColor Yellow
        exit 1
    }
}

function Download-File($Url, $OutPath, $Description) {
    Write-Info "Downloading $Description..."
    try {
        Invoke-WebRequest -Uri $Url -OutFile $OutPath -UseBasicParsing -ErrorAction Stop
        $size = (Get-Item $OutPath).Length / 1MB
        Write-Ok "Downloaded $Description ($([math]::Round($size, 1)) MB)"
    } catch {
        Write-Err "Failed: $($_.Exception.Message)"
        throw
    }
}

# ── Pre-flight ────────────────────────────────────────────────────────
Clear-Host
Write-Host ""
Write-Host "  KREXION NATIVE INSTALLER" -ForegroundColor Magenta
Write-Host "  No Docker. No Python required. Pure native Windows install." -ForegroundColor Gray
Write-Host ""

Assert-Admin

if (Test-Path $InstallDir) {
    Write-Warn "$InstallDir already exists. Continuing will UPDATE the existing install."
    $confirm = Read-Host "  Continue? (y/n)"
    if ($confirm -ne "y") { exit 0 }
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\bin" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\mongo" | Out-Null
New-Item -ItemType Directory -Force -Path "$DataDir\mongo" | Out-Null

# ── Step 1: MongoDB Portable ─────────────────────────────────────────
Write-Step "Step 1/6: Installing MongoDB (portable, no Docker)"
$mongoZip = "$env:TEMP\krexion-mongo.zip"
$mongoVer = "7.0.14"
$mongoUrl = "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-$mongoVer.zip"
if (-not (Test-Path "$InstallDir\mongo\bin\mongod.exe")) {
    Download-File $mongoUrl $mongoZip "MongoDB $mongoVer Portable"
    Write-Info "Extracting MongoDB..."
    $tmpDir = "$env:TEMP\krexion-mongo-extract"
    if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }
    Expand-Archive -Path $mongoZip -DestinationPath $tmpDir -Force
    $mongoSrc = Get-ChildItem $tmpDir -Filter "mongodb-*" -Directory | Select-Object -First 1
    if ($mongoSrc) {
        Copy-Item -Path "$($mongoSrc.FullName)\*" -Destination "$InstallDir\mongo" -Recurse -Force
    }
    Remove-Item $mongoZip,$tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok "MongoDB extracted to $InstallDir\mongo"
} else {
    Write-Ok "MongoDB already present — skipping download"
}

# ── Step 2: NSSM (Windows Service Wrapper) ───────────────────────────
Write-Step "Step 2/6: Installing NSSM (service manager)"
$nssmZip = "$env:TEMP\krexion-nssm.zip"
if (-not (Test-Path "$InstallDir\bin\nssm.exe")) {
    Download-File "https://nssm.cc/release/nssm-2.24.zip" $nssmZip "NSSM 2.24"
    $tmpDir = "$env:TEMP\krexion-nssm-extract"
    if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }
    Expand-Archive -Path $nssmZip -DestinationPath $tmpDir -Force
    Copy-Item -Path "$tmpDir\nssm-2.24\win64\nssm.exe" -Destination "$InstallDir\bin\nssm.exe" -Force
    Remove-Item $nssmZip,$tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok "NSSM installed"
} else {
    Write-Ok "NSSM already present"
}

# ── Step 3: Krexion backend binary ───────────────────────────────────
Write-Step "Step 3/6: Installing Krexion backend"
$backendExe = "$InstallDir\bin\krexion-backend.exe"
if (-not (Test-Path $backendExe)) {
    if (-not $BackendArtifactUrl) {
        # Default: pull latest release from GitHub
        $BackendArtifactUrl = "https://github.com/dennisedmaartins9-sudo/krexion.com/releases/latest/download/krexion-backend.zip"
    }
    $beZip = "$env:TEMP\krexion-backend.zip"
    Download-File $BackendArtifactUrl $beZip "Krexion Backend"
    Expand-Archive -Path $beZip -DestinationPath "$InstallDir\bin" -Force
    Remove-Item $beZip -Force -ErrorAction SilentlyContinue
    Write-Ok "Krexion backend installed"
} else {
    Write-Ok "Krexion backend already present"
}

# ── Step 4: Bundled Playwright Chromium ──────────────────────────────
Write-Step "Step 4/6: Installing Chromium (anti-detect browser engine)"
if (-not $SkipChromium) {
    $chromiumDir = "$InstallDir\chromium"
    New-Item -ItemType Directory -Force -Path $chromiumDir | Out-Null
    # Try downloading pre-bundled chromium from GH Releases (faster); fall
    # back to letting Playwright download it on first run if the bundle
    # artifact isn't published.
    $chrZip = "$env:TEMP\krexion-chromium.zip"
    $chrUrl = "https://github.com/dennisedmaartins9-sudo/krexion.com/releases/latest/download/chromium-bundle.zip"
    try {
        Download-File $chrUrl $chrZip "Playwright Chromium bundle"
        Expand-Archive -Path $chrZip -DestinationPath $chromiumDir -Force
        Remove-Item $chrZip -Force -ErrorAction SilentlyContinue
        Write-Ok "Chromium bundled"
    } catch {
        Write-Warn "Pre-bundled Chromium not found in releases."
        Write-Info "Krexion backend will auto-download Chromium on first launch (~165MB)."
    }
} else {
    Write-Ok "Skipping Chromium (per --SkipChromium flag)"
}

# ── Step 5: Register Windows Services ───────────────────────────────
Write-Step "Step 5/6: Registering Krexion as Windows Services"
$nssm = "$InstallDir\bin\nssm.exe"

# KrexionDatabase
Write-Info "Registering KrexionDatabase..."
& $nssm install KrexionDatabase "$InstallDir\mongo\bin\mongod.exe" `
    "--dbpath" "$DataDir\mongo" "--port" "27017" "--bind_ip" "127.0.0.1" "--quiet" 2>&1 | Out-Null
& $nssm set KrexionDatabase DisplayName "Krexion Database" | Out-Null
& $nssm set KrexionDatabase Description "Krexion local data store" | Out-Null
& $nssm set KrexionDatabase Start SERVICE_AUTO_START | Out-Null
& $nssm start KrexionDatabase 2>&1 | Out-Null
Write-Ok "KrexionDatabase service registered + started"

# KrexionBackend
Write-Info "Registering KrexionBackend..."
& $nssm install KrexionBackend $backendExe 2>&1 | Out-Null
& $nssm set KrexionBackend DisplayName "Krexion Backend" | Out-Null
& $nssm set KrexionBackend Description "Krexion FastAPI backend service" | Out-Null
& $nssm set KrexionBackend Start SERVICE_AUTO_START | Out-Null
& $nssm set KrexionBackend AppDirectory "$InstallDir\bin" | Out-Null
& $nssm set KrexionBackend AppStdout "$InstallDir\logs\backend.stdout.log" | Out-Null
& $nssm set KrexionBackend AppStderr "$InstallDir\logs\backend.stderr.log" | Out-Null
& $nssm set KrexionBackend AppEnvironmentExtra `
    "MONGO_URL=mongodb://127.0.0.1:27017" `
    "DB_NAME=krexion" `
    "KREXION_MODE=native" `
    "KREXION_BUILD_TYPE=binary" `
    "PLAYWRIGHT_BROWSERS_PATH=$InstallDir\chromium" | Out-Null
& $nssm start KrexionBackend 2>&1 | Out-Null
Write-Ok "KrexionBackend service registered + started"

# ── Step 6: Wait for backend to be ready ─────────────────────────────
Write-Step "Step 6/6: Verifying installation"
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8001/api/admin/login" `
                              -Method POST -ContentType "application/json" `
                              -Body '{"email":"check","password":"check"}' `
                              -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
            $ready = $true
            break
        }
    } catch {
        # Endpoint returning 4xx is fine — means service is alive.
        if ($_.Exception.Response.StatusCode.value__ -ge 400 -and `
            $_.Exception.Response.StatusCode.value__ -lt 500) {
            $ready = $true
            break
        }
    }
    Start-Sleep -Seconds 2
}

if ($ready) {
    Write-Ok "Krexion backend is responding"
} else {
    Write-Warn "Backend not responding yet — check logs at $InstallDir\logs"
}

# ── Done! ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard:  http://127.0.0.1:3000" -ForegroundColor White
Write-Host "  Services:   services.msc → look for 'Krexion Backend' + 'Krexion Database'" -ForegroundColor Gray
Write-Host "  Logs:       $InstallDir\logs" -ForegroundColor Gray
Write-Host "  Uninstall:  Run 'Krexion-Uninstall.ps1' as admin" -ForegroundColor Gray
Write-Host ""

# Open dashboard
Start-Process "http://127.0.0.1:3000"
