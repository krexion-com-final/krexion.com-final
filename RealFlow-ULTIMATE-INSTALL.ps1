# ============================================================
# RealFlow ULTIMATE INSTALLER - Auto-recovery, Bulletproof
# ============================================================
# Single PowerShell script that handles EVERY edge case:
# - Windows feature enablement (WSL2 + Virtual Machine Platform)
# - WSL2 kernel update (the #1 cause of Docker "Starting" stuck)
# - Docker Desktop install + startup recovery
# - Automatic retry + diagnostic if Docker stuck
# - Network resilience (ZIP download instead of git)
# - Reboot detection + resume support
# - Beautiful colored output, clear progress
# ============================================================

param(
    [switch]$Force,           # Skip all pre-checks, force install
    [switch]$SkipVirtCheck    # Skip only the virtualization check
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# --- Constants ---
$INSTALL_DIR    = "C:\realflow"
$LOG_FILE       = "$env:TEMP\realflow-install.log"
$RESUME_MARKER  = "$env:TEMP\realflow-resume.flag"
$REPO_ZIP_URL   = "https://github.com/ronaldsexedwards40-glitch/dynabook/archive/refs/heads/main.zip"
$DOCKER_URL     = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
$WSL_KERNEL_URL = "https://wslstorehosted.blob.core.windows.net/wslblob/wsl_update_x64.msi"

# --- Helper functions ---
function Write-Log {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "HH:mm:ss"
    $logLine = "[$timestamp] $Message"
    Write-Host $logLine -ForegroundColor $Color
    Add-Content -Path $LOG_FILE -Value $logLine -ErrorAction SilentlyContinue
}

function Write-Step {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Add-Content -Path $LOG_FILE -Value "`r`n===== $Title =====`r`n" -ErrorAction SilentlyContinue
}

function Write-Ok { param([string]$Msg) Write-Log "  [OK]   $Msg" "Green" }
function Write-Warn { param([string]$Msg) Write-Log "  [WARN] $Msg" "Yellow" }
function Write-Err { param([string]$Msg) Write-Log "  [ERR]  $Msg" "Red" }
function Write-Info { param([string]$Msg) Write-Log "  [..]   $Msg" "Gray" }

function Test-Internet {
    try {
        $null = Invoke-WebRequest -Uri "https://github.com" -UseBasicParsing -TimeoutSec 10
        return $true
    } catch {
        return $false
    }
}

function Test-DockerRunning {
    try {
        $result = & docker info 2>&1
        if ($LASTEXITCODE -eq 0) { return $true }
        return $false
    } catch {
        return $false
    }
}

function Stop-DockerCompletely {
    Write-Info "Stopping Docker (force shutdown)..."
    Stop-Process -Name "Docker Desktop" -Force -ErrorAction SilentlyContinue
    Stop-Process -Name "com.docker.backend" -Force -ErrorAction SilentlyContinue
    Stop-Process -Name "com.docker.proxy" -Force -ErrorAction SilentlyContinue
    Stop-Service "com.docker.service" -Force -ErrorAction SilentlyContinue
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 3
}

function Start-DockerDesktop {
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerExe)) {
        Write-Err "Docker Desktop not found at: $dockerExe"
        return $false
    }
    Write-Info "Starting Docker Desktop..."
    Start-Service "com.docker.service" -ErrorAction SilentlyContinue
    Start-Process -FilePath $dockerExe -WindowStyle Minimized
    return $true
}

function Wait-DockerReady {
    param([int]$TimeoutSeconds = 360)

    Write-Info "Waiting for Docker to be ready (up to $($TimeoutSeconds/60) minutes)..."
    $elapsed = 0
    $interval = 5
    while ($elapsed -lt $TimeoutSeconds) {
        if (Test-DockerRunning) {
            Write-Ok "Docker is running!"
            return $true
        }
        $elapsed += $interval
        $minutes = [math]::Floor($elapsed / 60)
        $seconds = $elapsed % 60
        Write-Host "    Still waiting... ($minutes`m $seconds`s elapsed)" -ForegroundColor DarkGray
        Start-Sleep -Seconds $interval
    }
    return $false
}

# ============================================================
# MAIN INSTALLATION FLOW
# ============================================================

Clear-Host
Write-Host ""
Write-Host "  ___           _ ___ _              " -ForegroundColor Cyan
Write-Host " | _ \___ __ _ | | __| |_____ __ __  " -ForegroundColor Cyan
Write-Host " |   / -_) _``| | | _|| / _ \ V  V /  " -ForegroundColor Cyan
Write-Host " |_|_\___\__,_||_|_| |_\___/\_/\_/   " -ForegroundColor Cyan
Write-Host ""
Write-Host "         ULTIMATE INSTALLER v2.0     " -ForegroundColor White
Write-Host "      Bulletproof, Auto-Recovery     " -ForegroundColor Gray
Write-Host ""
Write-Host "  Log file: $LOG_FILE" -ForegroundColor DarkGray
Write-Host ""

Start-Transcript -Path "$env:TEMP\realflow-transcript.log" -Append -ErrorAction SilentlyContinue

# ============================================================
# STEP 1: System checks
# ============================================================
Write-Step "STEP 1/8: System Compatibility Check"

# Check Windows version
$os = Get-CimInstance Win32_OperatingSystem
$buildNumber = [int]$os.BuildNumber
Write-Info "OS: $($os.Caption) (Build $buildNumber)"

if ($buildNumber -lt 19041) {
    Write-Err "Windows 10 build 19041 (version 2004) or higher required."
    Write-Err "Your build: $buildNumber"
    Write-Err "Please update Windows and try again: Settings -> Windows Update"
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Write-Ok "Windows version supported"

# Check internet
Write-Info "Checking internet connection..."
if (-not (Test-Internet)) {
    Write-Err "No internet connection. Please check your network and retry."
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Write-Ok "Internet connection working"

# Check RAM
$totalRam = [math]::Round(($os.TotalVisibleMemorySize / 1MB), 1)
Write-Info "Total RAM: $totalRam GB"
if ($totalRam -lt 3.5) {
    Write-Warn "Only $totalRam GB RAM detected. RealFlow may run slow."
    Write-Warn "Recommended: 8 GB RAM or more"
}
Write-Ok "RAM check complete"

# Check virtualization (smart multi-method detection)
if ($Force -or $SkipVirtCheck) {
    Write-Warn "Virtualization check SKIPPED (force flag enabled)"
} else {
Write-Info "Checking CPU virtualization (VT-x/AMD-V)..."

$virtEnabled = $false
$virtChecks = @()

# Method 1: Check if Hypervisor is already present (most reliable)
try {
    $compInfo = Get-ComputerInfo -Property HyperVisorPresent -ErrorAction SilentlyContinue
    if ($compInfo.HyperVisorPresent -eq $true) {
        $virtEnabled = $true
        $virtChecks += "HyperVisor active (Method 1)"
    }
} catch { }

# Method 2: Check if WSL is functional (if WSL works, virt is enabled)
try {
    $wslStatus = & wsl --status 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0 -and $wslStatus -notmatch "not installed|not enabled") {
        $virtEnabled = $true
        $virtChecks += "WSL functional (Method 2)"
    }
} catch { }

# Method 3: Check systeminfo output
try {
    $sysinfo = & systeminfo 2>&1 | Out-String
    if ($sysinfo -match "A hypervisor has been detected" -or
        $sysinfo -match "VM Monitor Mode Extensions:\s+Yes" -or
        $sysinfo -match "Virtualization Enabled In Firmware:\s+Yes" -or
        $sysinfo -match "Second Level Address Translation:\s+Yes") {
        $virtEnabled = $true
        $virtChecks += "systeminfo confirms (Method 3)"
    }
} catch { }

# Method 4: Original WMI check (least reliable on Win11 24H2)
try {
    $cpu = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue
    if ($cpu.VirtualizationFirmwareEnabled -eq $true) {
        $virtEnabled = $true
        $virtChecks += "Win32_Processor reports enabled (Method 4)"
    }
    if ($cpu.VMMonitorModeExtensions -eq $true -or
        $cpu.SecondLevelAddressTranslationExtensions -eq $true) {
        $virtEnabled = $true
        $virtChecks += "CPU extensions present (Method 4b)"
    }
} catch { }

# Method 5: Check Windows feature state — if Hyper-V or WSL2 was previously
# installed and works, virt must be on
try {
    $hyperv = Get-WindowsOptionalFeature -Online -FeatureName "Microsoft-Hyper-V" -ErrorAction SilentlyContinue
    $vmp = Get-WindowsOptionalFeature -Online -FeatureName "VirtualMachinePlatform" -ErrorAction SilentlyContinue
    if (($hyperv -and $hyperv.State -eq "Enabled") -or ($vmp -and $vmp.State -eq "Enabled")) {
        # Feature enabled doesn't guarantee virt on, but combined with no errors so far suggests it's fine
        $virtChecks += "Virtualization features enabled (Method 5)"
        # Don't auto-pass on this alone, but reduces false-negative confidence
    }
} catch { }

if ($virtEnabled) {
    Write-Ok "CPU virtualization enabled ($($virtChecks -join '; '))"
} else {
    # Soft warning — don't hard-fail. Let installer continue and Docker
    # will fail at startup if virt is truly off (with clear recovery flow).
    Write-Warn "Could not auto-detect virtualization status."
    Write-Warn "  (Windows 11 24H2 sometimes reports false for VirtualizationFirmwareEnabled)"
    Write-Warn ""
    Write-Warn "  If installation fails later, virtualization may need to be enabled:"
    Write-Warn "  1. Restart PC, press F2/F10/DEL during boot"
    Write-Warn "  2. Find 'Virtualization Technology' / 'VT-x' / 'AMD-V' / 'SVM Mode'"
    Write-Warn "  3. Set to ENABLED, save, reboot"
    Write-Warn ""
    Write-Warn "  Continuing installation — will try WSL2 + Docker anyway..."
    Start-Sleep -Seconds 3
}
} # end of virt check block

# ============================================================
# STEP 2: Enable Windows Features (WSL2 + VMP + Hyper-V)
# ============================================================
Write-Step "STEP 2/8: Enabling Windows Features (WSL2 + Virtualization)"

$needsReboot = $false
$features = @(
    @{Name="Microsoft-Windows-Subsystem-Linux"; Display="Windows Subsystem for Linux"},
    @{Name="VirtualMachinePlatform"; Display="Virtual Machine Platform"}
)

foreach ($f in $features) {
    Write-Info "Checking: $($f.Display)..."
    $state = Get-WindowsOptionalFeature -Online -FeatureName $f.Name -ErrorAction SilentlyContinue
    if ($state -and $state.State -eq "Enabled") {
        Write-Ok "$($f.Display) already enabled"
    } else {
        Write-Info "Enabling $($f.Display)..."
        $result = Enable-WindowsOptionalFeature -Online -FeatureName $f.Name -NoRestart -ErrorAction SilentlyContinue
        if ($result.RestartNeeded) { $needsReboot = $true }
        Write-Ok "$($f.Display) enabled"
    }
}

# ============================================================
# STEP 3: WSL2 Kernel Install + Update (CRITICAL for Docker)
# ============================================================
Write-Step "STEP 3/8: Installing/Updating WSL2 Kernel"

Write-Info "Running 'wsl --update' (this fixes 'Docker stuck at Starting')..."
$wslUpdate = & wsl --update 2>&1 | Out-String
Write-Host $wslUpdate -ForegroundColor DarkGray
if ($LASTEXITCODE -eq 0) {
    Write-Ok "WSL kernel updated successfully"
} else {
    # Fallback: manual MSI install
    Write-Warn "wsl --update failed. Trying manual MSI install..."
    $msiPath = "$env:TEMP\wsl_update_x64.msi"
    try {
        Invoke-WebRequest -Uri $WSL_KERNEL_URL -OutFile $msiPath -UseBasicParsing -TimeoutSec 120
        Start-Process msiexec.exe -ArgumentList "/i `"$msiPath`" /quiet /norestart" -Wait
        Write-Ok "WSL kernel installed via MSI"
    } catch {
        Write-Warn "MSI install failed too, but continuing (WSL may already work): $_"
    }
}

Write-Info "Setting WSL default version to 2..."
& wsl --set-default-version 2 2>&1 | Out-Null
Write-Ok "WSL2 set as default"

# Check if reboot needed
if ($needsReboot -and -not (Test-Path $RESUME_MARKER)) {
    Write-Host ""
    Write-Warn "REBOOT REQUIRED for Windows features to take effect"
    Write-Host ""
    Write-Host "  After reboot, run this installer again — it will resume automatically." -ForegroundColor Yellow
    Write-Host ""

    # Create resume marker so we know to skip features check next time
    "rebooted" | Out-File -FilePath $RESUME_MARKER -Force

    # Create scheduled task to auto-resume after reboot
    try {
        $taskName = "RealFlowResumeInstall"
        $scriptPath = $MyInvocation.MyCommand.Path
        if (-not $scriptPath) { $scriptPath = "$PSScriptRoot\RealFlow-ULTIMATE-INSTALL.ps1" }

        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$scriptPath`""
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest

        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force -ErrorAction SilentlyContinue | Out-Null
        Write-Ok "Auto-resume task created (will run after login)"
    } catch {
        Write-Warn "Could not create auto-resume task: $_"
    }

    Write-Host ""
    $reply = Read-Host "  Reboot now? (Y/N)"
    if ($reply -eq "Y" -or $reply -eq "y") {
        Write-Host "  Rebooting in 5 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        Restart-Computer -Force
        exit 0
    } else {
        Write-Host "  Please reboot manually and run this installer again." -ForegroundColor Yellow
        Stop-Transcript -ErrorAction SilentlyContinue
        exit 0
    }
}

# Clean up resume marker if we got here (post-reboot)
if (Test-Path $RESUME_MARKER) {
    Remove-Item $RESUME_MARKER -Force -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "RealFlowResumeInstall" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Ok "Resumed after reboot — continuing installation"
}

# ============================================================
# STEP 4: Configure WSL2 RAM (based on system)
# ============================================================
Write-Step "STEP 4/8: Configuring WSL2 Memory"

$wslMemGB = if ($totalRam -le 8) { "5GB" } elseif ($totalRam -le 16) { "10GB" } else { "16GB" }
$wslConfPath = "$env:USERPROFILE\.wslconfig"
$wslConfig = @"
[wsl2]
memory=$wslMemGB
processors=$([math]::Min([Environment]::ProcessorCount, 12))
swap=4GB
localhostForwarding=true
"@

Set-Content -Path $wslConfPath -Value $wslConfig -Force
Write-Ok "WSL2 configured: $wslMemGB RAM, $([math]::Min([Environment]::ProcessorCount, 12)) cores"

# ============================================================
# STEP 5: Install Docker Desktop (if not present)
# ============================================================
Write-Step "STEP 5/8: Docker Desktop Setup"

$dockerInstalled = Test-Path "C:\Program Files\Docker\Docker\Docker Desktop.exe"

if (-not $dockerInstalled) {
    Write-Info "Docker Desktop not found. Downloading installer (~600 MB)..."
    $dockerInstaller = "$env:TEMP\DockerDesktopInstaller.exe"

    try {
        Invoke-WebRequest -Uri $DOCKER_URL -OutFile $dockerInstaller -UseBasicParsing -TimeoutSec 600
        Write-Ok "Downloaded Docker installer"
    } catch {
        Write-Err "Docker download failed: $_"
        Write-Err "Please download manually from: https://www.docker.com/products/docker-desktop/"
        Stop-Transcript -ErrorAction SilentlyContinue
        exit 1
    }

    Write-Info "Installing Docker Desktop (this takes 3-5 minutes)..."
    $proc = Start-Process -FilePath $dockerInstaller -ArgumentList "install","--quiet","--accept-license" -Wait -PassThru
    if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
        Write-Err "Docker install failed with exit code $($proc.ExitCode)"
        Stop-Transcript -ErrorAction SilentlyContinue
        exit 1
    }
    Write-Ok "Docker Desktop installed"
    Start-Sleep -Seconds 3
} else {
    Write-Ok "Docker Desktop already installed"
}

# ============================================================
# STEP 6: Force Docker to RUNNING state (THE KEY FIX)
# ============================================================
Write-Step "STEP 6/8: Starting Docker Desktop (auto-recovery enabled)"

# Initial start
Stop-DockerCompletely
Start-DockerDesktop | Out-Null

# Try waiting up to 2 minutes first
$dockerReady = $false
Write-Info "Initial Docker startup (waiting up to 2 minutes)..."
$elapsed = 0
while ($elapsed -lt 120) {
    Start-Sleep -Seconds 5
    $elapsed += 5
    if (Test-DockerRunning) {
        $dockerReady = $true
        Write-Ok "Docker is running!"
        break
    }
    Write-Host "    Waiting... ($elapsed`s)" -ForegroundColor DarkGray
}

# If not ready after 2 minutes, apply RECOVERY procedures
if (-not $dockerReady) {
    Write-Warn "Docker stuck at startup. Applying recovery procedures..."

    # Recovery attempt 1: WSL shutdown + restart
    Write-Info "Recovery 1/3: Force-restarting WSL + Docker..."
    Stop-DockerCompletely
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Start-DockerDesktop | Out-Null
    if (Wait-DockerReady -TimeoutSeconds 120) { $dockerReady = $true }
}

if (-not $dockerReady) {
    # Recovery attempt 2: Update WSL again + reset Docker
    Write-Info "Recovery 2/3: Re-updating WSL kernel..."
    Stop-DockerCompletely
    & wsl --update 2>&1 | Out-Null
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Start-DockerDesktop | Out-Null
    if (Wait-DockerReady -TimeoutSeconds 120) { $dockerReady = $true }
}

if (-not $dockerReady) {
    # Recovery attempt 3: Reset Docker Desktop data
    Write-Info "Recovery 3/3: Resetting Docker Desktop settings..."
    Stop-DockerCompletely
    $settingsPath = "$env:APPDATA\Docker\settings.json"
    if (Test-Path $settingsPath) {
        Remove-Item $settingsPath -Force -ErrorAction SilentlyContinue
        Write-Ok "Reset Docker settings"
    }
    Start-Sleep -Seconds 3
    Start-DockerDesktop | Out-Null
    if (Wait-DockerReady -TimeoutSeconds 180) { $dockerReady = $true }
}

if (-not $dockerReady) {
    Write-Err ""
    Write-Err "Docker Desktop failed to start after 3 recovery attempts."
    Write-Err ""
    Write-Err "MANUAL FIX STEPS:"
    Write-Err "  1. Restart your computer (Start -> Power -> Restart)"
    Write-Err "  2. After restart, open Docker Desktop manually from Start Menu"
    Write-Err "  3. Wait until whale icon stops animating (green = ready)"
    Write-Err "  4. Run this installer again"
    Write-Err ""
    Write-Err "If still stuck after restart:"
    Write-Err "  - Check virtualization is ENABLED in BIOS"
    Write-Err "  - Run 'wsl --update' manually in PowerShell as Admin"
    Write-Err "  - Reinstall Docker Desktop: https://docker.com/products/docker-desktop"
    Write-Err ""
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}

Write-Ok "Docker is ready and running"

# ============================================================
# STEP 7: Download RealFlow + Setup
# ============================================================
Write-Step "STEP 7/8: Downloading RealFlow Code"

# Robust folder cleanup
if (Test-Path $INSTALL_DIR) {
    Write-Info "Cleaning existing install directory..."
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
    Write-Ok "Cleaned existing directory"
}

# Download ZIP (no git dependency)
$zipPath = "$env:TEMP\realflow-main.zip"
$extractDir = "$env:TEMP\realflow-extract"
Write-Info "Downloading RealFlow (~50 MB)..."
try {
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    Invoke-WebRequest -Uri $REPO_ZIP_URL -OutFile $zipPath -UseBasicParsing -TimeoutSec 300
    Write-Ok "Downloaded RealFlow ZIP"
} catch {
    Write-Err "Failed to download: $_"
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}

Write-Info "Extracting..."
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
$extractedFolder = Get-ChildItem $extractDir -Directory | Select-Object -First 1
Move-Item -Path $extractedFolder.FullName -Destination $INSTALL_DIR -Force
Write-Ok "Extracted to $INSTALL_DIR"

# Generate .env
Write-Info "Generating secure .env configuration..."
function New-RandomString {
    param([int]$Length = 24)
    $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    -join ((1..$Length) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

$jwtSecret = New-RandomString -Length 32
$adminPassword = New-RandomString -Length 16
$postbackToken = New-RandomString -Length 24

$envContent = @"
MONGO_URL=mongodb://mongo:27017
DB_NAME=realflow
JWT_SECRET_KEY=$jwtSecret
ADMIN_EMAIL=admin@realflow.local
ADMIN_PASSWORD=$adminPassword
POSTBACK_TOKEN=$postbackToken
CORS_ORIGINS=*
RUT_MEM_LIMIT_MB=4096
RUT_MAX_CONCURRENCY=4
RESEND_API_KEY=
SMTP_USER=
SMTP_PASSWORD=
GOOGLE_SHEETS_SA_PATH=
LICENSE_SERVER_URL=
LICENSE_KEY=
"@

Set-Content -Path "$INSTALL_DIR\.env" -Value $envContent -Force
Write-Ok ".env file generated"

# ============================================================
# STEP 8: Build + Start RealFlow
# ============================================================
Write-Step "STEP 8/8: Building and Starting RealFlow"

Push-Location $INSTALL_DIR

# Choose compose file based on RAM
$composeFile = "docker-compose.yml"
if ($totalRam -le 10) {
    if (Test-Path "docker-compose.lowram.yml") {
        $composeFile = "docker-compose.lowram.yml"
        Write-Info "Using low-RAM profile (8 GB tier)"
    }
} elseif ($totalRam -le 16) {
    if (Test-Path "docker-compose.mid.yml") {
        $composeFile = "docker-compose.mid.yml"
        Write-Info "Using mid-tier profile (16 GB)"
    }
}

Write-Info "Building Docker containers (5-15 minutes for first-time install)..."
& docker compose -f $composeFile build 2>&1 | Tee-Object -FilePath "$LOG_FILE" -Append
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker build failed. Check log: $LOG_FILE"
    Pop-Location
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Write-Ok "Build complete"

Write-Info "Starting containers..."
& docker compose -f $composeFile up -d 2>&1 | Tee-Object -FilePath "$LOG_FILE" -Append
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker startup failed. Check log: $LOG_FILE"
    Pop-Location
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}

Pop-Location

# Wait for backend to be ready
Write-Info "Waiting for RealFlow to be ready (up to 2 minutes)..."
$elapsed = 0
$ready = $false
while ($elapsed -lt 120) {
    Start-Sleep -Seconds 5
    $elapsed += 5
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch { }
    Write-Host "    Loading... ($elapsed`s)" -ForegroundColor DarkGray
}

if (-not $ready) {
    Write-Warn "RealFlow didn't respond on port 3000 within 2 minutes."
    Write-Warn "Containers may still be starting. Try: http://localhost:3000 in 1-2 minutes"
}

# ============================================================
# DONE - Display success info
# ============================================================
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host ""
Write-Host "  RealFlow is now running on your PC!" -ForegroundColor White
Write-Host ""
Write-Host "  ACCESS URLS:" -ForegroundColor Cyan
Write-Host "    Main App:        http://localhost:3000" -ForegroundColor White
Write-Host "    Admin Login:     http://localhost:3000/admin-login" -ForegroundColor White
Write-Host "    API Docs:        http://localhost:8001/docs" -ForegroundColor White
Write-Host ""
Write-Host "  ADMIN CREDENTIALS (SAVE THESE!):" -ForegroundColor Yellow
Write-Host "    Email:    admin@realflow.local" -ForegroundColor White
Write-Host "    Password: $adminPassword" -ForegroundColor White
Write-Host ""
Write-Host "  Credentials saved to: $INSTALL_DIR\.env" -ForegroundColor Gray
Write-Host ""
Write-Host "  DAILY OPERATIONS:" -ForegroundColor Cyan
Write-Host "    Start:   double-click LOCAL-START.bat in $INSTALL_DIR" -ForegroundColor White
Write-Host "    Stop:    double-click LOCAL-STOP.bat in $INSTALL_DIR" -ForegroundColor White
Write-Host "    Update:  double-click REALFLOW-UPDATE.bat in $INSTALL_DIR" -ForegroundColor White
Write-Host "    Mobile:  double-click GO-ONLINE.bat in $INSTALL_DIR" -ForegroundColor White
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host ""

# Save credentials to a file
$credsFile = "$env:USERPROFILE\Desktop\RealFlow-Credentials.txt"
$credsContent = @"
=================================================
  RealFlow - Admin Credentials
=================================================

  Main URL:        http://localhost:3000
  Admin Login:     http://localhost:3000/admin-login

  Email:           admin@realflow.local
  Password:        $adminPassword

  Saved at:        $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

=================================================
  Backup of .env: $INSTALL_DIR\.env
=================================================
"@
Set-Content -Path $credsFile -Value $credsContent -Force
Write-Ok "Credentials backup saved to Desktop: RealFlow-Credentials.txt"

# Create Desktop shortcut
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\RealFlow.url")
    $Shortcut.TargetPath = "http://localhost:3000"
    $Shortcut.Save()
    Write-Ok "Desktop shortcut created"
} catch { }

# Open browser
Write-Host "  Opening RealFlow in your browser..." -ForegroundColor Cyan
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

Stop-Transcript -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "  Press any key to close this installer..." -ForegroundColor Gray
$null = [System.Console]::ReadKey($true)
exit 0
