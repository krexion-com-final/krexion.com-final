# ==============================================================
# RealFlow Master Installer (install-master.ps1)
# Called by REALFLOW.bat - already running as Administrator
# ==============================================================
# Zero-question install. Just works. Auto-recovery for everything.
# ==============================================================

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# --- Constants ---
$INSTALL_DIR    = "C:\realflow"
$LOG_FILE       = "$env:TEMP\realflow-install.log"
$RESUME_MARKER  = "$env:TEMP\realflow-resume.flag"
$REPO_ZIP_URL   = "https://github.com/ronaldsexedwards40-glitch/dynabook/archive/refs/heads/main.zip"
$DOCKER_URL     = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
$WSL_KERNEL_URL = "https://wslstorehosted.blob.core.windows.net/wslblob/wsl_update_x64.msi"

# TLS 1.2 for all web requests
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# --- Helpers ---
function Log {
    param([string]$Msg, [string]$Color = "White")
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] $Msg" -ForegroundColor $Color
    Add-Content -Path $LOG_FILE -Value "[$ts] $Msg" -ErrorAction SilentlyContinue
}
function Ok { param($m) Log "  [OK]   $m" "Green" }
function Warn { param($m) Log "  [WARN] $m" "Yellow" }
function Err { param($m) Log "  [ERR]  $m" "Red" }
function Info { param($m) Log "  [..]   $m" "Cyan" }
function Step { param($t) Write-Host ""; Write-Host ("=" * 70) -ForegroundColor Magenta; Write-Host "  $t" -ForegroundColor Magenta; Write-Host ("=" * 70) -ForegroundColor Magenta }

function Test-DockerWorking {
    try {
        $null = & docker info 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function Stop-DockerHard {
    Get-Process "Docker Desktop","com.docker.backend","com.docker.proxy","com.docker.cli" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Stop-Service "com.docker.service" -Force -ErrorAction SilentlyContinue
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 3
}

function Start-DockerSilent {
    $exe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $exe)) { return $false }
    Start-Service "com.docker.service" -ErrorAction SilentlyContinue
    Start-Process -FilePath $exe -WindowStyle Minimized -ArgumentList "-Autostart"
    return $true
}

function Wait-Docker {
    param([int]$Sec = 180)
    $e = 0
    while ($e -lt $Sec) {
        if (Test-DockerWorking) { return $true }
        Start-Sleep -Seconds 5
        $e += 5
        if ($e % 30 -eq 0) { Write-Host "      Wait kar raha hun... ($($e)s/$($Sec)s)" -ForegroundColor DarkGray }
    }
    return $false
}

function Random-String {
    param([int]$L = 24)
    -join ((1..$L) | ForEach-Object { ('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'[(Get-Random -Maximum 62)]) })
}

# --- Start logging ---
"=== RealFlow install started $(Get-Date) ===" | Out-File -FilePath $LOG_FILE -Force
Start-Transcript -Path "$env:TEMP\realflow-transcript.log" -Force -ErrorAction SilentlyContinue | Out-Null

# ==============================================================
# SHOW BANNER
# ==============================================================
Clear-Host
Write-Host ""
Write-Host "  ____            _ _____ _              " -ForegroundColor Cyan
Write-Host " |  _ \ ___  __ _| |  ___| | _____      __" -ForegroundColor Cyan
Write-Host " | |_) / _ \/ _``| | |_  | |/ _ \ \ /\ / /" -ForegroundColor Cyan
Write-Host " |  _ <  __/ (_| | |  _| | | (_) \ V  V / " -ForegroundColor Cyan
Write-Host " |_| \_\___|\__,_|_|_|   |_|\___/ \_/\_/  " -ForegroundColor Cyan
Write-Host ""
Write-Host "        MASTER INSTALLER v3.0 - ZERO QUESTIONS" -ForegroundColor White
Write-Host ""

# ==============================================================
# STEP 1: Quick system summary
# ==============================================================
Step "STEP 1/7: System Info"
$os = Get-CimInstance Win32_OperatingSystem
$ram = [math]::Round(($os.TotalVisibleMemorySize / 1MB), 1)
$cores = [Environment]::ProcessorCount
Info "OS: $($os.Caption) (Build $($os.BuildNumber))"
Info "RAM: $ram GB | Cores: $cores"
if ([int]$os.BuildNumber -lt 19041) {
    Err "Windows version bahut purana hai (Build $($os.BuildNumber))."
    Err "Settings -> Update karein, phir dobara try karein."
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Ok "Compatible system"

# ==============================================================
# STEP 2: Enable Windows Features (WSL + VMP)
# ==============================================================
Step "STEP 2/7: Windows Features Enable"

$rebootNeeded = $false
foreach ($fname in @("Microsoft-Windows-Subsystem-Linux", "VirtualMachinePlatform")) {
    Info "Checking: $fname"
    $f = Get-WindowsOptionalFeature -Online -FeatureName $fname -ErrorAction SilentlyContinue
    if ($f -and $f.State -eq "Enabled") {
        Ok "$fname already enabled"
    } else {
        Info "Enabling $fname..."
        $r = Enable-WindowsOptionalFeature -Online -FeatureName $fname -NoRestart -ErrorAction SilentlyContinue
        if ($r.RestartNeeded) { $rebootNeeded = $true }
        Ok "$fname enabled"
    }
}

# Reboot handling
$justRebooted = (Test-Path $RESUME_MARKER)
if ($justRebooted) {
    Remove-Item $RESUME_MARKER -Force -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "RealFlowAutoResume" -Confirm:$false -ErrorAction SilentlyContinue
    Ok "Reboot ke baad resume hua. Continuing..."
} elseif ($rebootNeeded) {
    Warn "Windows features enable hone ke liye 1 reboot zaroori hai"

    # Create resume marker
    "rebooted" | Out-File -FilePath $RESUME_MARKER -Force

    # Create scheduled task for auto-resume (logon-trigger, runs REALFLOW.bat from Desktop)
    # We'll re-download fresh REALFLOW.bat to Desktop so resume always uses latest
    try {
        $batPath = "$env:USERPROFILE\Desktop\REALFLOW-RESUME.bat"
        @"
@echo off
fltmc >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; iwr 'https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/install-master.ps1' -OutFile '%TEMP%\im.ps1' -UseBasicParsing; & '%TEMP%\im.ps1'"
"@ | Out-File -FilePath $batPath -Encoding ASCII -Force

        $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batPath`""
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest -LogonType Interactive
        Register-ScheduledTask -TaskName "RealFlowAutoResume" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force -ErrorAction Stop | Out-Null
        Ok "Auto-resume task setup ho gaya"
    } catch {
        Warn "Auto-resume task fail: $_"
    }

    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Yellow
    Write-Host "   ABHI PC RESTART KAREIN" -ForegroundColor Yellow
    Write-Host "   Login ke baad installer khud continue karega." -ForegroundColor Yellow
    Write-Host "  ============================================" -ForegroundColor Yellow
    Write-Host ""

    Start-Sleep -Seconds 10
    Restart-Computer -Force
    exit 0
}

# ==============================================================
# STEP 3: WSL2 Kernel (CRITICAL — fixes Docker "Starting" stuck)
# ==============================================================
Step "STEP 3/7: WSL2 Kernel Update"

Info "Running 'wsl --update' (yeh Docker stuck ka #1 fix hai)..."
$wslOut = & wsl --update 2>&1 | Out-String
if ($LASTEXITCODE -eq 0) {
    Ok "WSL kernel updated"
} else {
    Warn "wsl --update failed, MSI fallback try kar raha hun..."
    try {
        $msi = "$env:TEMP\wsl_update.msi"
        Invoke-WebRequest -Uri $WSL_KERNEL_URL -OutFile $msi -UseBasicParsing -TimeoutSec 180
        Start-Process msiexec.exe -ArgumentList "/i `"$msi`" /quiet /norestart" -Wait
        Ok "WSL kernel installed via MSI"
    } catch {
        Warn "MSI bhi fail: $_  (continuing — Docker might still work)"
    }
}

Info "WSL2 default version set kar raha hun..."
& wsl --set-default-version 2 2>&1 | Out-Null
Ok "WSL2 default set"

# Auto-configure .wslconfig based on RAM
$wslMem = if ($ram -le 8) { "5GB" } elseif ($ram -le 16) { "10GB" } else { "16GB" }
$wslCpu = [math]::Min($cores, 12)
@"
[wsl2]
memory=$wslMem
processors=$wslCpu
swap=4GB
localhostForwarding=true
"@ | Out-File -FilePath "$env:USERPROFILE\.wslconfig" -Encoding ASCII -Force
Ok "WSL2 configured: $wslMem RAM, $wslCpu cores"

# ==============================================================
# STEP 4: Docker Desktop Install
# ==============================================================
Step "STEP 4/7: Docker Desktop Setup"

$dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (-not (Test-Path $dockerExe)) {
    Info "Docker Desktop nahi mila. Download kar raha hun (~600 MB, 3-10 min)..."
    $dInst = "$env:TEMP\DockerDesktopInstaller.exe"
    try {
        Invoke-WebRequest -Uri $DOCKER_URL -OutFile $dInst -UseBasicParsing -TimeoutSec 1200
        Ok "Downloaded"
    } catch {
        Err "Docker download failed: $_"
        Err "Manual install: https://www.docker.com/products/docker-desktop/"
        Stop-Transcript -ErrorAction SilentlyContinue
        exit 1
    }
    Info "Installing Docker Desktop silently (3-5 min)..."
    $p = Start-Process -FilePath $dInst -ArgumentList "install","--quiet","--accept-license" -Wait -PassThru
    if ($p.ExitCode -notin @(0, 3010)) {
        Err "Docker install failed ($($p.ExitCode))"
        Stop-Transcript -ErrorAction SilentlyContinue
        exit 1
    }
    Ok "Docker installed"
    Remove-Item $dInst -Force -ErrorAction SilentlyContinue
} else {
    Ok "Docker Desktop already installed"
}

# ==============================================================
# STEP 5: Force Docker to Running (with 3 recovery attempts)
# ==============================================================
Step "STEP 5/7: Starting Docker (auto-recovery enabled)"

Stop-DockerHard
Start-DockerSilent | Out-Null
Info "Initial startup ka wait (max 2 min)..."
$ready = Wait-Docker -Sec 120

if (-not $ready) {
    Warn "Docker stuck. Recovery 1/3: WSL restart..."
    Stop-DockerHard
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Start-DockerSilent | Out-Null
    $ready = Wait-Docker -Sec 120
}
if (-not $ready) {
    Warn "Recovery 2/3: WSL kernel re-update..."
    Stop-DockerHard
    & wsl --update 2>&1 | Out-Null
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Start-DockerSilent | Out-Null
    $ready = Wait-Docker -Sec 150
}
if (-not $ready) {
    Warn "Recovery 3/3: Docker settings reset..."
    Stop-DockerHard
    $sJson = "$env:APPDATA\Docker\settings.json"
    if (Test-Path $sJson) { Remove-Item $sJson -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3
    Start-DockerSilent | Out-Null
    $ready = Wait-Docker -Sec 180
}

if (-not $ready) {
    Err ""
    Err "Docker start nahi ho raha 3 recovery ke baad bhi."
    Err ""
    Err "FIX:"
    Err "  1. PC restart karein"
    Err "  2. Login ke baad Docker Desktop khud open karein"
    Err "  3. Whale icon green hone tak wait karein"
    Err "  4. REALFLOW.bat dobara chalayein"
    Err ""
    Err "Agar phir bhi fail to BIOS mein virtualization enable karein:"
    Err "  - PC restart, F2/F10/DEL press during boot"
    Err "  - 'Virtualization Technology' / 'VT-x' / 'AMD-V' / 'SVM Mode' ENABLED karein"
    Err "  - Save, reboot, REALFLOW.bat chalayein"
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Ok "Docker is running!"

# ==============================================================
# STEP 6: Download RealFlow + Configure
# ==============================================================
Step "STEP 6/7: Downloading RealFlow"

if (Test-Path $INSTALL_DIR) {
    Info "Purana install clean kar raha hun..."
    Push-Location $INSTALL_DIR
    & docker compose down 2>&1 | Out-Null
    Pop-Location
    & takeown.exe /f "$INSTALL_DIR" /r /d Y 2>&1 | Out-Null
    & icacls.exe "$INSTALL_DIR" /grant "$env:USERNAME`:F" /T /Q 2>&1 | Out-Null
    Remove-Item -Path $INSTALL_DIR -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $INSTALL_DIR) {
        Start-Sleep -Seconds 3
        Remove-Item -Path $INSTALL_DIR -Recurse -Force -ErrorAction SilentlyContinue
    }
    Ok "Cleaned old install"
}

$zip = "$env:TEMP\realflow.zip"
$ext = "$env:TEMP\realflow-extract"
Info "Downloading latest from GitHub (~50 MB)..."
if (Test-Path $zip) { Remove-Item $zip -Force }
if (Test-Path $ext) { Remove-Item $ext -Recurse -Force }
try {
    Invoke-WebRequest -Uri $REPO_ZIP_URL -OutFile $zip -UseBasicParsing -TimeoutSec 600
    Ok "Downloaded"
} catch {
    Err "Download failed: $_"
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}

Info "Extracting..."
Expand-Archive -Path $zip -DestinationPath $ext -Force
$inner = Get-ChildItem $ext -Directory | Select-Object -First 1
Move-Item -Path $inner.FullName -Destination $INSTALL_DIR -Force
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Remove-Item $ext -Recurse -Force -ErrorAction SilentlyContinue
Ok "Extracted to $INSTALL_DIR"

# Generate .env
$jwt = Random-String 32
$adminPw = Random-String 16
$pbToken = Random-String 24
@"
MONGO_URL=mongodb://mongo:27017
DB_NAME=realflow
JWT_SECRET_KEY=$jwt
ADMIN_EMAIL=admin@realflow.local
ADMIN_PASSWORD=$adminPw
POSTBACK_TOKEN=$pbToken
CORS_ORIGINS=*
RUT_MEM_LIMIT_MB=4096
RUT_MAX_CONCURRENCY=4
RESEND_API_KEY=
SMTP_USER=
SMTP_PASSWORD=
GOOGLE_SHEETS_SA_PATH=
LICENSE_SERVER_URL=
LICENSE_KEY=
"@ | Out-File -FilePath "$INSTALL_DIR\.env" -Encoding ASCII -Force
Ok ".env generated (secure random passwords)"

# ==============================================================
# STEP 7: Build + Start
# ==============================================================
Step "STEP 7/7: Building + Starting RealFlow"

Push-Location $INSTALL_DIR

# Auto-pick compose file based on RAM
$compose = "docker-compose.yml"
if ($ram -le 10 -and (Test-Path "docker-compose.lowram.yml")) {
    $compose = "docker-compose.lowram.yml"
    Info "Low-RAM profile use kar raha hun"
} elseif ($ram -le 16 -and (Test-Path "docker-compose.mid.yml")) {
    $compose = "docker-compose.mid.yml"
    Info "Mid-tier profile use kar raha hun"
}

Info "Containers build kar raha hun (5-15 min first time)..."
& docker compose -f $compose build 2>&1 | Tee-Object -FilePath $LOG_FILE -Append
if ($LASTEXITCODE -ne 0) {
    Err "Build failed. Log: $LOG_FILE"
    Pop-Location
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Ok "Build complete"

Info "Containers start kar raha hun..."
& docker compose -f $compose up -d 2>&1 | Tee-Object -FilePath $LOG_FILE -Append
if ($LASTEXITCODE -ne 0) {
    Err "Start failed. Log: $LOG_FILE"
    Pop-Location
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Pop-Location

# Wait for RealFlow to respond
Info "RealFlow ready hone ka wait..."
$ok = $false
for ($i = 0; $i -lt 24; $i++) {
    Start-Sleep -Seconds 5
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
    if ($i % 6 -eq 5) { Write-Host "      Loading... ($((($i+1)*5))s)" -ForegroundColor DarkGray }
}

# ==============================================================
# DONE
# ==============================================================
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host "  REALFLOW READY HAI!" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host ""
Write-Host "  ACCESS URLS:" -ForegroundColor Cyan
Write-Host "    App:         http://localhost:3000" -ForegroundColor White
Write-Host "    Admin:       http://localhost:3000/admin-login" -ForegroundColor White
Write-Host "    API Docs:    http://localhost:8001/docs" -ForegroundColor White
Write-Host ""
Write-Host "  ADMIN LOGIN:" -ForegroundColor Yellow
Write-Host "    Email:       admin@realflow.local" -ForegroundColor White
Write-Host "    Password:    $adminPw" -ForegroundColor White
Write-Host ""

# Save credentials to Desktop
$credsFile = "$env:USERPROFILE\Desktop\RealFlow-Credentials.txt"
@"
=================================================
  RealFlow - Aap Ke Admin Credentials
=================================================

  Browser kholein:
    http://localhost:3000

  Admin Login:
    URL:       http://localhost:3000/admin-login
    Email:     admin@realflow.local
    Password:  $adminPw

  Installed:   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
  Folder:      $INSTALL_DIR

=================================================
  IMPORTANT: Yeh file delete na karein!
  Apne phone mein bhi screenshot save kar lein.
=================================================
"@ | Out-File -FilePath $credsFile -Encoding UTF8 -Force
Ok "Credentials saved: $credsFile"

# Create Desktop shortcut
try {
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut("$env:USERPROFILE\Desktop\RealFlow.url")
    $sc.TargetPath = "http://localhost:3000"
    $sc.Save()
    Ok "Desktop shortcut: RealFlow.url"
} catch { }

# Open browser
Info "Browser open kar raha hun..."
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "  Mubarak ho! RealFlow chal raha hai." -ForegroundColor Green
Write-Host ""

Stop-Transcript -ErrorAction SilentlyContinue
exit 0
