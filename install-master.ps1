# ==============================================================
# RealFlow Master Installer v3.1
# NO here-strings, NO parens-in-strings, Windows-safe encoding
# ==============================================================

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# Constants
$INSTALL_DIR    = "C:\realflow"
$LOG_FILE       = "$env:TEMP\realflow-install.log"
$RESUME_MARKER  = "$env:TEMP\realflow-resume.flag"
$REPO_ZIP_URL   = "https://github.com/ronaldsexedwards40-glitch/dynabook/archive/refs/heads/main.zip"
$DOCKER_URL     = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
$WSL_KERNEL_URL = "https://wslstorehosted.blob.core.windows.net/wslblob/wsl_update_x64.msi"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Helpers - all use single param to avoid parser issues
function Log-Line {
    param([string]$Msg, [string]$Color = "White")
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[" + $ts + "] " + $Msg
    Write-Host $line -ForegroundColor $Color
    Add-Content -Path $LOG_FILE -Value $line -ErrorAction SilentlyContinue
}
function Show-Ok    { param([string]$m) Log-Line ("  [OK]   " + $m) "Green" }
function Show-Warn  { param([string]$m) Log-Line ("  [WARN] " + $m) "Yellow" }
function Show-Err   { param([string]$m) Log-Line ("  [ERR]  " + $m) "Red" }
function Show-Info  { param([string]$m) Log-Line ("  [..]   " + $m) "Cyan" }
function Show-Step  {
    param([string]$t)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Magenta
    Write-Host ("  " + $t) -ForegroundColor Magenta
    Write-Host ("=" * 70) -ForegroundColor Magenta
}

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
        if (($e % 30) -eq 0) {
            $msg = "      Wait kar raha hun... " + [string]$e + "s/" + [string]$Sec + "s"
            Write-Host $msg -ForegroundColor DarkGray
        }
    }
    return $false
}

function New-RandomString {
    param([int]$L = 24)
    $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    $out = ""
    for ($i = 0; $i -lt $L; $i++) {
        $out = $out + $chars[(Get-Random -Maximum 62)]
    }
    return $out
}

# Start logging
$startMsg = "=== RealFlow install started " + (Get-Date) + " ==="
$startMsg | Out-File -FilePath $LOG_FILE -Force
Start-Transcript -Path "$env:TEMP\realflow-transcript.log" -Force -ErrorAction SilentlyContinue | Out-Null

# Banner
Clear-Host
Write-Host ""
Write-Host "  ===============================================" -ForegroundColor Cyan
Write-Host "  ||                                           ||" -ForegroundColor Cyan
Write-Host "  ||           R E A L F L O W                 ||" -ForegroundColor Cyan
Write-Host "  ||      Master Installer v3.1 Bulletproof    ||" -ForegroundColor Cyan
Write-Host "  ||                                           ||" -ForegroundColor Cyan
Write-Host "  ===============================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# STEP 1: System Info
# ============================================================
Show-Step "STEP 1/7: System Info"
$os = Get-CimInstance Win32_OperatingSystem
$ram = [math]::Round(($os.TotalVisibleMemorySize / 1MB), 1)
$cores = [Environment]::ProcessorCount
Show-Info ("OS: " + $os.Caption + " - Build " + $os.BuildNumber)
Show-Info ("RAM: " + $ram + " GB | Cores: " + $cores)
if ([int]$os.BuildNumber -lt 19041) {
    Show-Err "Windows version bahut purana hai."
    Show-Err "Settings -> Update karein, phir dobara try karein."
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Show-Ok "Compatible system"

# ============================================================
# STEP 2: Windows Features
# ============================================================
Show-Step "STEP 2/7: Windows Features Enable"

$rebootNeeded = $false
$featureList = @("Microsoft-Windows-Subsystem-Linux", "VirtualMachinePlatform")
foreach ($fname in $featureList) {
    Show-Info ("Checking: " + $fname)
    $f = Get-WindowsOptionalFeature -Online -FeatureName $fname -ErrorAction SilentlyContinue
    if ($f -and $f.State -eq "Enabled") {
        Show-Ok ($fname + " already enabled")
    } else {
        Show-Info ("Enabling " + $fname)
        $r = Enable-WindowsOptionalFeature -Online -FeatureName $fname -NoRestart -ErrorAction SilentlyContinue
        if ($r.RestartNeeded) { $rebootNeeded = $true }
        Show-Ok ($fname + " enabled")
    }
}

# Handle reboot
$justRebooted = (Test-Path $RESUME_MARKER)
if ($justRebooted) {
    Remove-Item $RESUME_MARKER -Force -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "RealFlowAutoResume" -Confirm:$false -ErrorAction SilentlyContinue
    Show-Ok "Reboot ke baad resume hua. Continuing..."
} elseif ($rebootNeeded) {
    Show-Warn "Windows features enable hone ke liye 1 reboot zaroori hai"
    "rebooted" | Out-File -FilePath $RESUME_MARKER -Force

    # Build resume .bat using array (no here-string)
    $batPath = "$env:USERPROFILE\Desktop\REALFLOW-RESUME.bat"
    $batLines = @(
        '@echo off',
        'fltmc >nul 2>&1',
        'if %errorLevel% neq 0 (',
        '    powershell -Command "Start-Process -FilePath ''%~f0'' -Verb RunAs"',
        '    exit /b',
        ')',
        'powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; iwr ''https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/install-master.ps1'' -OutFile ''%TEMP%\im.ps1'' -UseBasicParsing; & ''%TEMP%\im.ps1''"'
    )
    $batLines | Set-Content -Path $batPath -Encoding ASCII -Force

    try {
        $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument ("/c `"" + $batPath + "`"")
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        $principal = New-ScheduledTaskPrincipal -UserId ($env:USERDOMAIN + "\" + $env:USERNAME) -RunLevel Highest -LogonType Interactive
        Register-ScheduledTask -TaskName "RealFlowAutoResume" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force -ErrorAction Stop | Out-Null
        Show-Ok "Auto-resume task setup ho gaya"
    } catch {
        Show-Warn ("Auto-resume task fail: " + $_)
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

# ============================================================
# STEP 3: WSL2 Kernel Update
# ============================================================
Show-Step "STEP 3/7: WSL2 Kernel Update"

Show-Info "Running 'wsl --update' [Docker stuck ka #1 fix]"
$null = & wsl --update 2>&1
if ($LASTEXITCODE -eq 0) {
    Show-Ok "WSL kernel updated"
} else {
    Show-Warn "wsl --update failed, MSI fallback try kar raha hun..."
    try {
        $msi = "$env:TEMP\wsl_update.msi"
        Invoke-WebRequest -Uri $WSL_KERNEL_URL -OutFile $msi -UseBasicParsing -TimeoutSec 180
        Start-Process msiexec.exe -ArgumentList "/i `"$msi`" /quiet /norestart" -Wait
        Show-Ok "WSL kernel installed via MSI"
    } catch {
        Show-Warn "MSI fallback fail - continuing anyway"
    }
}

Show-Info "WSL2 default version set kar raha hun"
& wsl --set-default-version 2 2>&1 | Out-Null
Show-Ok "WSL2 default set"

# Auto-configure .wslconfig - using array, no here-string
$wslMem = "10GB"
if ($ram -le 8) { $wslMem = "5GB" }
if ($ram -gt 16) { $wslMem = "16GB" }
$wslCpu = [math]::Min($cores, 12)

$wslconfPath = $env:USERPROFILE + "\.wslconfig"
$wslconfLines = @(
    "[wsl2]",
    ("memory=" + $wslMem),
    ("processors=" + $wslCpu),
    "swap=4GB",
    "localhostForwarding=true"
)
$wslconfLines | Set-Content -Path $wslconfPath -Encoding ASCII -Force
Show-Ok ("WSL2 configured: " + $wslMem + " RAM, " + $wslCpu + " cores")

# ============================================================
# STEP 4: Docker Desktop Install
# ============================================================
Show-Step "STEP 4/7: Docker Desktop Setup"

$dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (-not (Test-Path $dockerExe)) {
    Show-Info "Docker Desktop nahi mila. Download kar raha hun [600MB, 3-10 min]"
    $dInst = "$env:TEMP\DockerDesktopInstaller.exe"
    try {
        Invoke-WebRequest -Uri $DOCKER_URL -OutFile $dInst -UseBasicParsing -TimeoutSec 1200
        Show-Ok "Downloaded"
    } catch {
        Show-Err ("Docker download failed: " + $_)
        Show-Err "Manual install: https://www.docker.com/products/docker-desktop/"
        Stop-Transcript -ErrorAction SilentlyContinue
        exit 1
    }
    Show-Info "Installing Docker Desktop silently [3-5 min]"
    $p = Start-Process -FilePath $dInst -ArgumentList "install","--quiet","--accept-license" -Wait -PassThru
    $okCodes = @(0, 3010)
    if ($okCodes -notcontains $p.ExitCode) {
        Show-Err ("Docker install failed - code " + $p.ExitCode)
        Stop-Transcript -ErrorAction SilentlyContinue
        exit 1
    }
    Show-Ok "Docker installed"
    Remove-Item $dInst -Force -ErrorAction SilentlyContinue
} else {
    Show-Ok "Docker Desktop already installed"
}

# ============================================================
# STEP 5: Force Docker to Running
# ============================================================
Show-Step "STEP 5/7: Starting Docker [auto-recovery enabled]"

Stop-DockerHard
Start-DockerSilent | Out-Null
Show-Info "Initial startup ka wait [max 2 min]"
$ready = Wait-Docker -Sec 120

if (-not $ready) {
    Show-Warn "Docker stuck. Recovery 1/3: WSL restart"
    Stop-DockerHard
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Start-DockerSilent | Out-Null
    $ready = Wait-Docker -Sec 120
}
if (-not $ready) {
    Show-Warn "Recovery 2/3: WSL kernel re-update"
    Stop-DockerHard
    & wsl --update 2>&1 | Out-Null
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Start-DockerSilent | Out-Null
    $ready = Wait-Docker -Sec 150
}
if (-not $ready) {
    Show-Warn "Recovery 3/3: Docker settings reset"
    Stop-DockerHard
    $sJson = "$env:APPDATA\Docker\settings.json"
    if (Test-Path $sJson) { Remove-Item $sJson -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3
    Start-DockerSilent | Out-Null
    $ready = Wait-Docker -Sec 180
}

if (-not $ready) {
    Show-Err "Docker start nahi ho raha 3 recovery ke baad bhi."
    Show-Err ""
    Show-Err "FIX:"
    Show-Err "  1. PC restart karein"
    Show-Err "  2. Login ke baad Docker Desktop khud open karein from Start Menu"
    Show-Err "  3. Whale icon green hone tak wait karein"
    Show-Err "  4. REALFLOW.bat dobara chalayein"
    Show-Err ""
    Show-Err "Agar phir bhi fail to BIOS mein virtualization enable karein."
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Show-Ok "Docker is running!"

# ============================================================
# STEP 6: Download RealFlow
# ============================================================
Show-Step "STEP 6/7: Downloading RealFlow"

if (Test-Path $INSTALL_DIR) {
    Show-Info "Purana install clean kar raha hun"
    Push-Location $INSTALL_DIR
    & docker compose down 2>&1 | Out-Null
    Pop-Location
    & takeown.exe /f $INSTALL_DIR /r /d Y 2>&1 | Out-Null
    & icacls.exe $INSTALL_DIR /grant ($env:USERNAME + ":F") /T /Q 2>&1 | Out-Null
    Remove-Item -Path $INSTALL_DIR -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $INSTALL_DIR) {
        Start-Sleep -Seconds 3
        Remove-Item -Path $INSTALL_DIR -Recurse -Force -ErrorAction SilentlyContinue
    }
    Show-Ok "Cleaned old install"
}

$zip = "$env:TEMP\realflow.zip"
$ext = "$env:TEMP\realflow-extract"
Show-Info "Downloading latest from GitHub [50MB]"
if (Test-Path $zip) { Remove-Item $zip -Force }
if (Test-Path $ext) { Remove-Item $ext -Recurse -Force }
try {
    Invoke-WebRequest -Uri $REPO_ZIP_URL -OutFile $zip -UseBasicParsing -TimeoutSec 600
    Show-Ok "Downloaded"
} catch {
    Show-Err ("Download failed: " + $_)
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}

Show-Info "Extracting..."
Expand-Archive -Path $zip -DestinationPath $ext -Force
$inner = Get-ChildItem $ext -Directory | Select-Object -First 1
Move-Item -Path $inner.FullName -Destination $INSTALL_DIR -Force
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Remove-Item $ext -Recurse -Force -ErrorAction SilentlyContinue
Show-Ok ("Extracted to " + $INSTALL_DIR)

# Generate .env using array - no here-string
$jwt = New-RandomString -L 32
$adminPw = New-RandomString -L 16
$pbToken = New-RandomString -L 24

$envPath = $INSTALL_DIR + "\.env"
$envLines = @(
    "MONGO_URL=mongodb://mongo:27017",
    "DB_NAME=realflow",
    ("JWT_SECRET_KEY=" + $jwt),
    "ADMIN_EMAIL=admin@realflow.local",
    ("ADMIN_PASSWORD=" + $adminPw),
    ("POSTBACK_TOKEN=" + $pbToken),
    "CORS_ORIGINS=*",
    "RUT_MEM_LIMIT_MB=4096",
    "RUT_MAX_CONCURRENCY=4",
    "RESEND_API_KEY=",
    "SMTP_USER=",
    "SMTP_PASSWORD=",
    "GOOGLE_SHEETS_SA_PATH=",
    "LICENSE_SERVER_URL=",
    "LICENSE_KEY="
)
$envLines | Set-Content -Path $envPath -Encoding ASCII -Force
Show-Ok ".env generated [secure random passwords]"

# ============================================================
# STEP 7: Build + Start
# ============================================================
Show-Step "STEP 7/7: Building + Starting RealFlow"

Push-Location $INSTALL_DIR

# Pick compose files (base + optional override for RAM tier)
$composeArgs = @("-f", "docker-compose.yml")
if (($ram -le 10) -and (Test-Path "docker-compose.lowram.yml")) {
    $composeArgs += @("-f", "docker-compose.lowram.yml")
    Show-Info "Low-RAM profile use kar raha hun"
} elseif (($ram -le 16) -and (Test-Path "docker-compose.mid.yml")) {
    $composeArgs += @("-f", "docker-compose.mid.yml")
    Show-Info "Mid-tier profile use kar raha hun"
} elseif (($ram -gt 32) -and (Test-Path "docker-compose.beast.yml")) {
    $composeArgs += @("-f", "docker-compose.beast.yml")
    Show-Info "Beast profile use kar raha hun"
} elseif (($ram -gt 16) -and (Test-Path "docker-compose.high.yml")) {
    $composeArgs += @("-f", "docker-compose.high.yml")
    Show-Info "High-tier profile use kar raha hun"
}

Show-Info "Containers build kar raha hun [5-15 min first time]"
& docker compose @composeArgs build 2>&1 | Tee-Object -FilePath $LOG_FILE -Append
if ($LASTEXITCODE -ne 0) {
    Show-Err ("Build failed. Log: " + $LOG_FILE)
    Pop-Location
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Show-Ok "Build complete"

Show-Info "Containers start kar raha hun"
& docker compose @composeArgs up -d 2>&1 | Tee-Object -FilePath $LOG_FILE -Append
if ($LASTEXITCODE -ne 0) {
    Show-Err ("Start failed. Log: " + $LOG_FILE)
    Pop-Location
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Pop-Location

# Wait for RealFlow
Show-Info "RealFlow ready hone ka wait"
$ok = $false
for ($i = 0; $i -lt 24; $i++) {
    Start-Sleep -Seconds 5
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
    if (($i % 6) -eq 5) {
        $sec = ($i + 1) * 5
        Write-Host ("      Loading... " + $sec + "s") -ForegroundColor DarkGray
    }
}

# DONE
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
Write-Host ("    Password:    " + $adminPw) -ForegroundColor White
Write-Host ""

# Save creds - using array
$credsFile = "$env:USERPROFILE\Desktop\RealFlow-Credentials.txt"
$credsLines = @(
    "=================================================",
    "  RealFlow - Aap Ke Admin Credentials",
    "=================================================",
    "",
    "  Browser kholein:",
    "    http://localhost:3000",
    "",
    "  Admin Login:",
    "    URL:       http://localhost:3000/admin-login",
    "    Email:     admin@realflow.local",
    ("    Password:  " + $adminPw),
    "",
    ("  Installed:   " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')),
    ("  Folder:      " + $INSTALL_DIR),
    "",
    "=================================================",
    "  IMPORTANT: Yeh file delete na karein!",
    "  Apne phone mein bhi screenshot save kar lein.",
    "================================================="
)
$credsLines | Set-Content -Path $credsFile -Encoding UTF8 -Force
Show-Ok ("Credentials saved: " + $credsFile)

# Desktop shortcut
try {
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut("$env:USERPROFILE\Desktop\RealFlow.url")
    $sc.TargetPath = "http://localhost:3000"
    $sc.Save()
    Show-Ok "Desktop shortcut: RealFlow.url"
} catch { }

# Open browser
Show-Info "Browser open kar raha hun"
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "  Mubarak ho! RealFlow chal raha hai." -ForegroundColor Green
Write-Host ""

Stop-Transcript -ErrorAction SilentlyContinue
exit 0
