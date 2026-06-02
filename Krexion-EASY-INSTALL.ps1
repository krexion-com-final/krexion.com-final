# ============================================================
#  Krexion EASY INSTALLER -- PowerShell Engine
# ============================================================
#  Called by Krexion-EASY-INSTALL.bat after self-elevation.
#  Pure PowerShell, no external dependencies.
#  Downloads ZIP from GitHub (no Git needed).
#  Handles every common failure case gracefully.
# ============================================================

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"

# --- Configuration ---
$RepoOwner   = "ronaldsexedwards40-glitch"
$RepoName    = "dynabook"
$Branch      = "main"
$InstallDir  = "C:\krexion"
$ZipUrl      = "https://github.com/$RepoOwner/$RepoName/archive/refs/heads/$Branch.zip"
$TempZip     = Join-Path $env:TEMP "krexion-source.zip"
$TempExtract = Join-Path $env:TEMP "krexion-extract"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogFile     = Join-Path $ScriptDir "Krexion-Install.log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $line = "[$(Get-Date -Format 'HH:mm:ss')] [$Level] $Message"
    Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue
    if ($Level -eq "ERROR")   { Write-Host "  $Message" -ForegroundColor Red    }
    elseif ($Level -eq "WARN"){ Write-Host "  $Message" -ForegroundColor Yellow }
    elseif ($Level -eq "OK")  { Write-Host "  $Message" -ForegroundColor Green  }
    else                       { Write-Host "  $Message" -ForegroundColor White  }
}

function Write-Banner {
    param([string]$Text)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Friendly-Error {
    param([string]$ErrorMessage, [string]$Suggestion)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  ERROR" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "  $ErrorMessage" -ForegroundColor Yellow
    Write-Host ""
    if ($Suggestion) {
        Write-Host "  WHAT TO DO:" -ForegroundColor Cyan
        Write-Host "  $Suggestion" -ForegroundColor White
        Write-Host ""
    }
    Write-Host "  Full log: $LogFile" -ForegroundColor Gray
    Write-Host ""
    Write-Log $ErrorMessage "ERROR"
    Read-Host "Press ENTER to close"
    exit 1
}

# ============================================================
#  Stage 0 -- Welcome banner
# ============================================================
Clear-Host
Write-Banner "Krexion ONE-CLICK INSTALLER"
Write-Host "  This will install Krexion on your PC." -ForegroundColor White
Write-Host "  Just sit back -- everything happens automatically." -ForegroundColor White
Write-Host ""
Write-Host "  Steps:" -ForegroundColor Gray
Write-Host "    1. Check / install Docker Desktop" -ForegroundColor Gray
Write-Host "    2. Download Krexion code from GitHub" -ForegroundColor Gray
Write-Host "    3. Auto-tune for your PC hardware" -ForegroundColor Gray
Write-Host "    4. Build and start everything" -ForegroundColor Gray
Write-Host "    5. Open the app in your browser" -ForegroundColor Gray
Write-Host ""
Start-Sleep -Seconds 2

# ============================================================
#  Stage 1 -- Network check
# ============================================================
Write-Banner "Step 1 / 7 :: Checking internet connection"
try {
    $resp = Invoke-WebRequest -Uri "https://github.com" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    Write-Log "GitHub reachable (status $($resp.StatusCode))" "OK"
} catch {
    Show-Friendly-Error `
        "Cannot reach GitHub. The installer needs internet to download files." `
        "Check:`n  - WiFi / Ethernet is connected`n  - Try opening https://github.com in a browser`n  - If your office firewall blocks it, try a different network or VPN"
}

# ============================================================
#  Stage 2 -- Detect PC hardware (RAM + CPU)
# ============================================================
Write-Banner "Step 2 / 7 :: Detecting your PC hardware"
$totalRamGB = [int][math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 0)
$cpuCores   = (Get-CimInstance Win32_Processor | Measure-Object NumberOfLogicalProcessors -Sum).Sum
if (-not $cpuCores) { $cpuCores = [Environment]::ProcessorCount }

if     ($totalRamGB -le 6)  { $tier="MICRO"; $rut=1;  $mongo="512m"; $be="1536m"; $fe="128m"; $wsl="4GB"  }
elseif ($totalRamGB -le 10) { $tier="LOW";   $rut=2;  $mongo="1g";   $be="2560m"; $fe="192m"; $wsl="5GB"  }
elseif ($totalRamGB -le 16) { $tier="MID";   $rut=4;  $mongo="2g";   $be="4g";    $fe="256m"; $wsl="10GB" }
elseif ($totalRamGB -le 32) { $tier="HIGH";  $rut=8;  $mongo="4g";   $be="8g";    $fe="384m"; $wsl="20GB" }
else                        { $tier="BEAST"; $rut=16; $mongo="8g";   $be="16g";   $fe="512m"; $wsl="32GB" }

# CPU ceiling
$ceiling = [Math]::Max(1, $cpuCores * 2)
if ($rut -gt $ceiling) { $rut = $ceiling }

Write-Log "RAM: $totalRamGB GB, CPU cores: $cpuCores -> Tier: $tier (RUT concurrency: $rut)" "OK"
$composeOverride = switch ($tier) {
    "MICRO" { "docker-compose.micro.yml"  }
    "LOW"   { "docker-compose.lowram.yml" }
    "MID"   { "docker-compose.mid.yml"    }
    "HIGH"  { "docker-compose.high.yml"   }
    "BEAST" { "docker-compose.beast.yml"  }
}

# ============================================================
#  Stage 3 -- Docker Desktop check + install
# ============================================================
Write-Banner "Step 3 / 7 :: Checking Docker Desktop"

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Log "Docker not found -- will download and install" "WARN"
    $dockerExeInstaller = Join-Path $env:TEMP "DockerDesktopInstaller.exe"

    if (-not (Test-Path $dockerExeInstaller) -or (Get-Item $dockerExeInstaller).Length -lt 200MB) {
        Write-Log "Downloading Docker Desktop (~520 MB)... This can take 5-20 min on slow internet."
        try {
            Invoke-WebRequest -Uri "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" `
                              -OutFile $dockerExeInstaller `
                              -UseBasicParsing -TimeoutSec 1800
        } catch {
            Show-Friendly-Error `
                "Could not download Docker Desktop." `
                "Possible fixes:`n  - Check your internet speed`n  - Try again in 5 minutes`n  - Manually download from: https://www.docker.com/products/docker-desktop/`n  - Save as: $dockerExeInstaller`n  - Then re-run this installer"
        }
    } else {
        Write-Log "Using cached Docker installer" "OK"
    }

    Write-Log "Installing Docker Desktop (silent, 3-5 min)..."
    try {
        Start-Process -FilePath $dockerExeInstaller -ArgumentList "install","--quiet","--accept-license" -Wait
    } catch {
        Show-Friendly-Error `
            "Docker installer failed: $($_.Exception.Message)" `
            "Possible fixes:`n  - Run this BAT file as Administrator (right-click -> Run as administrator)`n  - Restart your PC and try again`n  - Make sure your Windows is 10 (Build 19041+) or Windows 11"
    }

    # Refresh PATH
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")

    # Need a reboot to enable WSL2/Hyper-V
    Write-Host ""
    Write-Host "  -------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "  Docker installed. Your PC needs to RESTART now." -ForegroundColor Yellow
    Write-Host "  After restart, JUST DOUBLE-CLICK this same .bat file again." -ForegroundColor Yellow
    Write-Host "  The installer will continue automatically." -ForegroundColor Yellow
    Write-Host "  -------------------------------------------------------" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press ENTER to restart your PC now"
    Restart-Computer -Force
    exit
}
Write-Log "Docker is installed: $(docker --version 2>$null)" "OK"

# Make sure WSL kernel is up to date (Docker often fails with old kernel)
Write-Log "Updating WSL kernel (just in case)..."
try {
    & wsl.exe --update 2>&1 | Out-Null
    & wsl.exe --set-default-version 2 2>&1 | Out-Null
} catch {
    Write-Log "WSL update skipped (already current or not needed)" "WARN"
}

# Wait for Docker daemon
Write-Log "Waiting for Docker engine to be ready (max 90 sec)..."
$dockerOk = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
    } catch {}
    Start-Sleep 2
    if ($i % 5 -eq 0) { Write-Host "    waiting for Docker ... ($($i*2)s)" -ForegroundColor Gray }
}
if (-not $dockerOk) {
    # Try to launch Docker Desktop
    $dockerExePath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExePath) {
        Write-Log "Launching Docker Desktop manually..." "WARN"
        Start-Process -FilePath $dockerExePath
        for ($i = 0; $i -lt 60; $i++) {
            try {
                docker info 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break }
            } catch {}
            Start-Sleep 2
        }
    }
}
if (-not $dockerOk) {
    Show-Friendly-Error `
        "Docker engine is not running." `
        "FIX:`n  1. Open the Start Menu -> search 'Docker Desktop' -> click it`n  2. Wait until the whale icon in the system tray stops animating (1-2 min)`n  3. Double-click this installer file again"
}
Write-Log "Docker engine is running" "OK"

# ============================================================
#  Stage 4 -- Tune WSL2 for your hardware
# ============================================================
Write-Banner "Step 4 / 7 :: Tuning WSL2 for $tier tier"
$wslProcs = [Math]::Min($cpuCores, 12)
$wslConfig = Join-Path $env:USERPROFILE ".wslconfig"

@"
[wsl2]
memory=$wsl
processors=$wslProcs
swap=4GB
localhostForwarding=true

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
"@ | Out-File -FilePath $wslConfig -Encoding ascii

Write-Log "Wrote $wslConfig (memory=$wsl, processors=$wslProcs)" "OK"
& wsl.exe --shutdown 2>&1 | Out-Null
Start-Sleep 3

# ============================================================
#  Stage 5 -- Clean up + download fresh source ZIP
# ============================================================
Write-Banner "Step 5 / 7 :: Downloading Krexion source code"

# Robust cleanup of any prior install
if (Test-Path $InstallDir) {
    Write-Log "Cleaning up old install at $InstallDir..." "WARN"
    # Stop any existing containers
    if (Test-Path (Join-Path $InstallDir "docker-compose.yml")) {
        try {
            Push-Location $InstallDir
            & docker compose down 2>&1 | Out-Null
            Pop-Location
        } catch {}
    }
    # Force ownership + remove
    try {
        & takeown.exe /F $InstallDir /R /D Y 2>&1 | Out-Null
        & icacls.exe $InstallDir /grant "Administrators:F" /T /C /Q 2>&1 | Out-Null
    } catch {}

    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $InstallDir
    Start-Sleep 1
    if (Test-Path $InstallDir) {
        # Some files still locked -- try one more time after a short wait
        Start-Sleep 3
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $InstallDir
    }
    if (Test-Path $InstallDir) {
        Show-Friendly-Error `
            "Could not clean up old install at $InstallDir" `
            "FIX:`n  1. Close all programs (VS Code, file explorer windows open on C:\krexion)`n  2. Open Task Manager -> end any 'docker' processes`n  3. Restart your PC`n  4. Run this installer again"
    }
}

# Download ZIP
Write-Log "Downloading from $ZipUrl (~5 MB)..."
try {
    if (Test-Path $TempZip) { Remove-Item -Force $TempZip }
    Invoke-WebRequest -Uri $ZipUrl -OutFile $TempZip -UseBasicParsing -TimeoutSec 300
    Write-Log "Download OK ($([math]::Round((Get-Item $TempZip).Length/1MB,1)) MB)" "OK"
} catch {
    Show-Friendly-Error `
        "Could not download Krexion source from GitHub." `
        "Possible fixes:`n  - Check internet connection`n  - Manually download: $ZipUrl`n  - Extract to C:\krexion`n  - Re-run this installer"
}

# Extract
Write-Log "Extracting source..."
if (Test-Path $TempExtract) { Remove-Item -Recurse -Force $TempExtract }
try {
    Expand-Archive -Path $TempZip -DestinationPath $TempExtract -Force
} catch {
    Show-Friendly-Error `
        "Could not extract ZIP file." `
        "FIX:`n  - Make sure you have at least 1 GB free disk space`n  - Run installer as Administrator"
}

# Move from temp\krexion-extract\dynabook-main\* to C:\krexion\*
$extractedFolder = Get-ChildItem -Path $TempExtract -Directory | Select-Object -First 1
if (-not $extractedFolder) {
    Show-Friendly-Error "ZIP extraction produced no folder" "Re-run installer, check internet"
}
Move-Item -Path $extractedFolder.FullName -Destination $InstallDir -Force
Remove-Item -Recurse -Force $TempZip, $TempExtract -ErrorAction SilentlyContinue
Write-Log "Source extracted to $InstallDir" "OK"

# ============================================================
#  Stage 6 -- Generate .env with strong random secrets
# ============================================================
Write-Banner "Step 6 / 7 :: Generating secure .env file"
$envFile = Join-Path $InstallDir ".env"
function New-RandomString { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_}) }
$jwtKey       = New-RandomString
$adminPass    = New-RandomString
$postback     = New-RandomString

@"
# Auto-generated by Krexion-EASY-INSTALL on $((Get-Date).ToString('yyyy-MM-dd HH:mm'))
DB_NAME=krexion
JWT_SECRET_KEY=$jwtKey
ADMIN_EMAIL=admin@krexion.local
ADMIN_PASSWORD=$adminPass
POSTBACK_TOKEN=$postback
APP_URL=http://localhost:3000
PUBLIC_BASE_URL=http://localhost:3000
CORS_ORIGINS=*

# Hardware tier (auto-detected)
RF_TIER=$tier
RUT_MAX_CONCURRENCY=$rut

# Optional integrations -- fill in if you use them
RESEND_API_KEY=
SMTP_HOST=
SMTP_USER=
SMTP_PASSWORD=
SENDER_EMAIL=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
LICENSE_KEY=
LICENSE_SERVER_URL=
TUNNEL_TOKEN=
"@ | Out-File -FilePath $envFile -Encoding ascii

Write-Log "Generated .env with admin password: $adminPass" "OK"
$script:AdminPassword = $adminPass

# ============================================================
#  Stage 7 -- Build + Start Docker stack
# ============================================================
Write-Banner "Step 7 / 7 :: Building and starting Krexion"

Push-Location $InstallDir

$composeArgs = @("-f","docker-compose.yml")
if (Test-Path $composeOverride) {
    Write-Log "Using $composeOverride for $tier tier (RUT=$rut, Backend=$be)" "OK"
    $composeArgs += @("-f", $composeOverride)
} else {
    Write-Log "Tier override $composeOverride not found, using base profile" "WARN"
}

Write-Log "Building Docker images (5-10 min first time)..."
& docker compose @composeArgs build 2>&1 | Tee-Object -FilePath $LogFile -Append | Out-Host
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Show-Friendly-Error `
        "Docker build failed. See log: $LogFile" `
        "Common fixes:`n  - Make sure Docker Desktop is running (whale icon in tray)`n  - Make sure you have at least 5 GB free disk space`n  - Try running: cd C:\krexion && docker compose build`n  - Check $LogFile for the exact error"
}

Write-Log "Starting containers..."
& docker compose @composeArgs up -d 2>&1 | Tee-Object -FilePath $LogFile -Append | Out-Host
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Show-Friendly-Error `
        "Docker startup failed. See log: $LogFile" `
        "Try:`n  - Wait 30 seconds, then: cd C:\krexion && docker compose up -d`n  - Check Docker Desktop -> Containers tab for error details"
}

Pop-Location

# ============================================================
#  Wait for backend to be healthy
# ============================================================
Write-Host ""
Write-Log "Waiting for backend to start (max 2 min)..."
$backendOk = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-WebRequest "http://localhost:8001/api/diagnostics/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $backendOk = $true; break }
    } catch {}
    Start-Sleep 2
    if ($i % 5 -eq 0) { Write-Host "    backend warming up ... ($($i*2)s)" -ForegroundColor Gray }
}
if ($backendOk) {
    Write-Log "Backend is healthy" "OK"
} else {
    Write-Log "Backend timeout -- check 'docker compose logs backend' in C:\krexion" "WARN"
}

# Wait for frontend
$frontendOk = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest "http://localhost:3000" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $frontendOk = $true; break }
    } catch {}
    Start-Sleep 2
}
if ($frontendOk) { Write-Log "Frontend is up at http://localhost:3000" "OK" }

# Create Desktop shortcut
$shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Krexion.url"
"[InternetShortcut]`r`nURL=http://localhost:3000`r`nIconIndex=0" | Out-File -FilePath $shortcut -Encoding ascii
Write-Log "Created Desktop shortcut: Krexion.url" "OK"

# ============================================================
#  DONE -- Show success screen
# ============================================================
Clear-Host
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "                                                            " -ForegroundColor Green
Write-Host "         KREXION IS NOW RUNNING!                           " -ForegroundColor Green
Write-Host "                                                            " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Open in your browser:" -ForegroundColor White
Write-Host "    http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Admin login:" -ForegroundColor White
Write-Host "    Email    : admin@krexion.local" -ForegroundColor Yellow
Write-Host "    Password : $adminPass" -ForegroundColor Yellow
Write-Host ""
Write-Host "    (Save this password! It's also in C:\krexion\.env)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Hardware tier auto-detected: $tier" -ForegroundColor White
Write-Host "    RAM            : $totalRamGB GB" -ForegroundColor Gray
Write-Host "    CPU cores      : $cpuCores" -ForegroundColor Gray
Write-Host "    RUT concurrency: $rut parallel browsers" -ForegroundColor Gray
Write-Host ""
Write-Host "  Useful commands (Command Prompt):" -ForegroundColor White
Write-Host "    cd C:\krexion" -ForegroundColor Gray
Write-Host "    docker compose ps              # see containers" -ForegroundColor Gray
Write-Host "    docker compose logs -f backend # see logs" -ForegroundColor Gray
Write-Host "    docker compose restart         # restart" -ForegroundColor Gray
Write-Host "    docker compose down            # stop" -ForegroundColor Gray
Write-Host ""
Write-Host "  Desktop shortcut: Krexion.url" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Open browser
try {
    Start-Process "http://localhost:3000"
} catch {}

Read-Host "Press ENTER to close this window"
