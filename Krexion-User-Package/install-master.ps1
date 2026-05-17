# ==============================================================
# Krexion Master Installer v3.1
# NO here-strings, NO parens-in-strings, Windows-safe encoding
# ==============================================================

param(
    [switch]$CustomerMode  # If true: hide admin info from customer
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# Constants
$INSTALL_DIR    = "C:\krexion"
$LOG_FILE       = "$env:TEMP\krexion-install.log"
$RESUME_MARKER  = "$env:TEMP\krexion-resume.flag"
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
    Start-Process -FilePath $exe -WindowStyle Hidden -ArgumentList "-Autostart"
    return $true
}

function Set-DockerHidden {
    # Configure Docker Desktop to NEVER show its UI / shortcuts / popups
    # so the customer only ever sees the Krexion experience.
    try {
        $settingsDir = "$env:APPDATA\Docker"
        if (-not (Test-Path $settingsDir)) { New-Item -ItemType Directory -Path $settingsDir -Force | Out-Null }
        $settingsPath = "$settingsDir\settings.json"

        # Load existing or start blank
        $settings = @{}
        if (Test-Path $settingsPath) {
            try {
                $existing = Get-Content $settingsPath -Raw | ConvertFrom-Json -ErrorAction SilentlyContinue
                if ($existing) {
                    $existing.PSObject.Properties | ForEach-Object { $settings[$_.Name] = $_.Value }
                }
            } catch { }
        }

        # White-label settings: never show GUI, no tutorial, no telemetry popups
        $settings["autoStart"] = $true
        $settings["openUIOnStartupDisabled"] = $true
        $settings["displayedTutorial"] = $true
        $settings["displayed2WSLTutorialIfApplicable"] = $true
        $settings["displayedWelcomeWhale"] = $true
        $settings["analyticsEnabled"] = $false
        $settings["showAnnouncementNotifications"] = $false
        $settings["showGeneralNotifications"] = $false
        $settings["wslEngineEnabled"] = $true
        $settings["acceptedLicenseAgreement"] = $true

        $settings | ConvertTo-Json -Depth 10 | Set-Content -Path $settingsPath -Encoding UTF8 -Force
    } catch { }

    # Strip out Docker Desktop's user-facing shortcuts (Desktop + Start Menu)
    $shortcuts = @(
        "$env:USERPROFILE\Desktop\Docker Desktop.lnk",
        "$env:PUBLIC\Desktop\Docker Desktop.lnk",
        "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Docker Desktop.lnk",
        "$env:ALLUSERSPROFILE\Microsoft\Windows\Start Menu\Programs\Docker Desktop.lnk"
    )
    foreach ($s in $shortcuts) {
        if (Test-Path $s) { Remove-Item $s -Force -ErrorAction SilentlyContinue }
    }

    # Force Windows to NEVER show the Docker Desktop tray icon. By default
    # Windows shows new app tray icons until the user reorders them. Setting
    # NotifyIconSettings.IsPromoted=0 hides Docker's whale icon completely.
    try {
        $tray = "HKCU:\Control Panel\NotifyIconSettings"
        if (Test-Path $tray) {
            Get-ChildItem $tray -ErrorAction SilentlyContinue | ForEach-Object {
                try {
                    $exe = (Get-ItemProperty -Path $_.PSPath -Name "ExecutablePath" -ErrorAction SilentlyContinue).ExecutablePath
                    if ($exe -and ($exe -match "Docker Desktop\\.*\.exe$" -or $exe -match "com\.docker\.")) {
                        Set-ItemProperty -Path $_.PSPath -Name "IsPromoted" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
                    }
                } catch { }
            }
        }
    } catch { }

    # Also remove Docker Desktop from Windows startup folder so its whale
    # icon doesn't appear after every reboot. The com.docker.service
    # Windows service (which is what we actually need) keeps running
    # regardless and the backend container talks to it directly.
    try {
        $startupShortcut = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Docker Desktop.lnk"
        if (Test-Path $startupShortcut) { Remove-Item $startupShortcut -Force -ErrorAction SilentlyContinue }
    } catch { }

    # Disable Docker Desktop auto-start via the Run registry key so it
    # never opens its tray icon on boot. We start it on-demand when the
    # customer runs Krexion via Start-DockerSilent.
    try {
        $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
        if (Get-ItemProperty -Path $runKey -Name "Docker Desktop" -ErrorAction SilentlyContinue) {
            Remove-ItemProperty -Path $runKey -Name "Docker Desktop" -Force -ErrorAction SilentlyContinue
        }
    } catch { }
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
$startMsg = "=== Krexion install started " + (Get-Date) + " ==="
$startMsg | Out-File -FilePath $LOG_FILE -Force
Start-Transcript -Path "$env:TEMP\krexion-transcript.log" -Force -ErrorAction SilentlyContinue | Out-Null

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
    Unregister-ScheduledTask -TaskName "KrexionAutoResume" -Confirm:$false -ErrorAction SilentlyContinue
    Show-Ok "Reboot ke baad resume hua. Continuing..."
} elseif ($rebootNeeded) {
    Show-Warn "Windows features enable hone ke liye 1 reboot zaroori hai"
    "rebooted" | Out-File -FilePath $RESUME_MARKER -Force

    # Build resume .bat using array (no here-string)
    $batPath = "$env:USERPROFILE\Desktop\KREXION-RESUME.bat"
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
        Register-ScheduledTask -TaskName "KrexionAutoResume" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force -ErrorAction Stop | Out-Null
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
Show-Step "STEP 3/7: System Engine Update"

Show-Info "Engine update - yeh 1-10 min le sakta hai"
Show-Info "Silent download hota hai - heartbeat dikha raha hun ki kaam chal raha hai"
Write-Host ""

# Run wsl --update in background with heartbeat
$wslJob = Start-Job -ScriptBlock {
    $result = & wsl --update 2>&1 | Out-String
    return @{ Exit = $LASTEXITCODE; Out = $result }
}

$wslStartTime = Get-Date
$wslDone = $false
$wslSuccess = $false
$maxWslWait = 600  # 10 min max
$dots = ""

while (-not $wslDone) {
    $elapsed = ((Get-Date) - $wslStartTime).TotalSeconds
    if ($wslJob.State -eq "Completed") {
        $wslDone = $true
        $r = Receive-Job $wslJob
        if ($r.Exit -eq 0) { $wslSuccess = $true }
        Remove-Job $wslJob -Force
        break
    }
    if ($elapsed -gt $maxWslWait) {
        Show-Warn "wsl --update 10 min se zyada le raha hai - cancel kar raha hun"
        Stop-Job $wslJob -ErrorAction SilentlyContinue
        Remove-Job $wslJob -Force -ErrorAction SilentlyContinue
        $wslDone = $true
        break
    }
    Start-Sleep -Seconds 10
    $elapsedInt = [int]$elapsed
    $dots = $dots + "."
    if ($dots.Length -gt 5) { $dots = "." }
    $heartbeat = "  [..]   wsl --update chal raha hai" + $dots + " (" + $elapsedInt + "s elapsed, max 600s)"
    Write-Host $heartbeat -ForegroundColor Cyan
}

if ($wslSuccess) {
    Show-Ok "WSL kernel updated successfully"
} else {
    Show-Warn "wsl --update fail/timeout - MSI fallback try kar raha hun"
    Show-Info "MSI download chal raha hai (50 MB) - 1-3 min lagta hai"
    try {
        $msi = "$env:TEMP\wsl_update.msi"
        if (Test-Path $msi) { Remove-Item $msi -Force -ErrorAction SilentlyContinue }

        # Download with retry (3 attempts)
        $downloaded = $false
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                Show-Info ("MSI download attempt " + $attempt + "/3")
                Invoke-WebRequest -Uri $WSL_KERNEL_URL -OutFile $msi -UseBasicParsing -TimeoutSec 180
                if (Test-Path $msi) {
                    $size = (Get-Item $msi).Length
                    if ($size -gt 1MB) { $downloaded = $true; break }
                }
            } catch {
                Show-Warn ("Attempt " + $attempt + " fail: " + $_.Exception.Message)
                Start-Sleep -Seconds 5
            }
        }

        if ($downloaded) {
            Show-Info "Installing WSL kernel via MSI"
            Start-Process msiexec.exe -ArgumentList "/i `"$msi`" /quiet /norestart" -Wait
            Show-Ok "WSL kernel installed via MSI"
        } else {
            Show-Warn "MSI download fail after 3 attempts - continuing anyway"
            Show-Warn "Krexion engine shayad fir bhi kaam karega - aage check karenge"
        }
    } catch {
        Show-Warn ("MSI install error: " + $_.Exception.Message)
        Show-Warn "Continuing - Krexion engine pe test karenge"
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
Show-Step "STEP 4/7: Krexion Runtime Setup"

$dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (-not (Test-Path $dockerExe)) {
    Show-Info "Krexion runtime install kar raha hun [600MB, 3-10 min]"
    Show-Info "Internet speed pe depend karega - heartbeat dikhata rahunga"
    $dInst = "$env:TEMP\KrexionRuntimeInstaller.exe"
    if (Test-Path $dInst) { Remove-Item $dInst -Force -ErrorAction SilentlyContinue }

    # Download with progress and retry
    $dlSuccess = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Show-Info ("Download attempt " + $attempt + "/3")
            $dlJob = Start-Job -ScriptBlock {
                param($url, $out)
                Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -TimeoutSec 1800
            } -ArgumentList $DOCKER_URL, $dInst

            $dlStart = Get-Date
            $dlDots = ""
            while ($dlJob.State -eq "Running") {
                Start-Sleep -Seconds 15
                $dlElapsed = [int]((Get-Date) - $dlStart).TotalSeconds
                $sizeMb = 0
                if (Test-Path $dInst) { $sizeMb = [math]::Round((Get-Item $dInst).Length / 1MB, 0) }
                $dlDots = $dlDots + "."
                if ($dlDots.Length -gt 5) { $dlDots = "." }
                $msg = "  [..]   Krexion runtime download" + $dlDots + " (" + $dlElapsed + "s, " + $sizeMb + " MB downloaded)"
                Write-Host $msg -ForegroundColor Cyan
                if ($dlElapsed -gt 1800) {
                    Stop-Job $dlJob -ErrorAction SilentlyContinue
                    break
                }
            }
            Remove-Job $dlJob -Force -ErrorAction SilentlyContinue

            if (Test-Path $dInst) {
                $finalSize = (Get-Item $dInst).Length
                if ($finalSize -gt 100MB) {
                    $dlSuccess = $true
                    Show-Ok ("Downloaded - " + [math]::Round($finalSize / 1MB, 0) + " MB")
                    break
                }
            }
        } catch {
            Show-Warn ("Attempt " + $attempt + " fail: " + $_.Exception.Message)
            Start-Sleep -Seconds 10
        }
    }

    if (-not $dlSuccess) {
        Show-Err "Krexion runtime download fail after 3 attempts"
        Show-Err "Internet check karein aur INSTALL.bat dobara chalayein"
        Show-Err "Support: https://krexion.com/support"
        Stop-Transcript -ErrorAction SilentlyContinue
        exit 1
    }

    Show-Info "Installing Krexion runtime silently [3-5 min]"
    Show-Info "Yeh silent install hai - kuch dikhega nahi, please wait"
    $p = Start-Process -FilePath $dInst -ArgumentList "install","--quiet","--accept-license" -Wait -PassThru
    $okCodes = @(0, 3010)
    if ($okCodes -notcontains $p.ExitCode) {
        Show-Err ("Runtime install failed - code " + $p.ExitCode)
        Stop-Transcript -ErrorAction SilentlyContinue
        exit 1
    }
    Show-Ok "Krexion runtime installed"
    Remove-Item $dInst -Force -ErrorAction SilentlyContinue
} else {
    Show-Ok "Krexion runtime already installed"
}

# Apply white-label settings BEFORE first start so the GUI never pops up
Set-DockerHidden
Show-Ok "Runtime configured (background mode)"

# ============================================================
# STEP 5: Force Docker to Running
# ============================================================
Show-Step "STEP 5/7: Starting Krexion engine [auto-recovery enabled]"

Stop-DockerHard
Set-DockerHidden
Start-DockerSilent | Out-Null
Show-Info "Initial startup ka wait [max 2 min]"
$ready = Wait-Docker -Sec 120

if (-not $ready) {
    Show-Warn "Engine stuck. Recovery 1/3: WSL restart"
    Stop-DockerHard
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Set-DockerHidden
    Start-DockerSilent | Out-Null
    $ready = Wait-Docker -Sec 120
}
if (-not $ready) {
    Show-Warn "Recovery 2/3: kernel re-update"
    Stop-DockerHard
    & wsl --update 2>&1 | Out-Null
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Set-DockerHidden
    Start-DockerSilent | Out-Null
    $ready = Wait-Docker -Sec 150
}
if (-not $ready) {
    Show-Warn "Recovery 3/3: Engine settings reset"
    Stop-DockerHard
    $sJson = "$env:APPDATA\Docker\settings.json"
    if (Test-Path $sJson) { Remove-Item $sJson -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3
    Set-DockerHidden
    Start-DockerSilent | Out-Null
    $ready = Wait-Docker -Sec 180
}

if (-not $ready) {
    Show-Err "Krexion engine start nahi ho raha 3 recovery ke baad bhi."
    Show-Err ""
    Show-Err "FIX:"
    Show-Err "  1. PC restart karein"
    Show-Err "  2. KREXION.bat dobara chalayein"
    Show-Err ""
    Show-Err "Agar phir bhi fail to BIOS mein virtualization enable karein."
    Show-Err "Support: https://krexion.com/support"
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Show-Ok "Krexion engine is running!"

# ============================================================
# STEP 6: Download Krexion
# ============================================================
Show-Step "STEP 6/7: Downloading Krexion"

if (Test-Path $INSTALL_DIR) {
    Show-Info "Purana install clean kar raha hun"
    Push-Location $INSTALL_DIR
    & docker compose down --remove-orphans --volumes 2>&1 | Out-Null
    Pop-Location
    & takeown.exe /f $INSTALL_DIR /r /d Y 2>&1 | Out-Null
    & icacls.exe $INSTALL_DIR /grant ($env:USERNAME + ":F") /T /Q 2>&1 | Out-Null
    Remove-Item -Path $INSTALL_DIR -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $INSTALL_DIR) {
        Start-Sleep -Seconds 3
        Remove-Item -Path $INSTALL_DIR -Recurse -Force -ErrorAction SilentlyContinue
    }
    Show-Ok "Cleaned old install folder"
}

# ───────────────────────────────────────────────────────────────────
# Force-remove ANY legacy container/network/project from previous
# installs (e.g. older "realflow-mongo" still running from a v2 build).
# Without this, the next "docker compose up -d" hits a name conflict
# and the install dies at Step 7 — exactly what customer logs showed.
# ───────────────────────────────────────────────────────────────────
Show-Info "Legacy containers cleanup (agar pehle ka koi install tha)"
foreach ($proj in @("realflow", "krexion", "krexion-user-package")) {
    & docker compose -p $proj down --remove-orphans --volumes 2>&1 | Out-Null
}
$legacyContainers = @(
    "realflow-mongo", "realflow-backend", "realflow-frontend", "realflow-caddy", "realflow-redis", "realflow-worker",
    "krexion-mongo", "krexion-backend", "krexion-frontend", "krexion-caddy", "krexion-redis", "krexion-worker"
)
foreach ($n in $legacyContainers) {
    & docker rm -f $n 2>&1 | Out-Null
}
# Drop any orphan networks the previous project may have left behind
foreach ($net in @("realflow-net", "krexion-net", "realflow_realflow-net", "krexion_krexion-net")) {
    & docker network rm $net 2>&1 | Out-Null
}
Show-Ok "Legacy cleanup done"

$zip = "$env:TEMP\krexion.zip"
$ext = "$env:TEMP\krexion-extract"
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
    "DB_NAME=krexion",
    ("JWT_SECRET_KEY=" + $jwt),
    "ADMIN_EMAIL=admin@krexion.local",
    ("ADMIN_PASSWORD=" + $adminPw),
    ("POSTBACK_TOKEN=" + $pbToken),
    "CORS_ORIGINS=*",
    "RUT_MEM_LIMIT_MB=4096",
    "RUT_MAX_CONCURRENCY=4",
    "RESEND_API_KEY=",
    "SMTP_USER=",
    "SMTP_PASSWORD=",
    "GOOGLE_SHEETS_SA_PATH=",
    "LICENSE_SERVER_URL=https://krexion.com",
    "LICENSE_KEY=",
    "KREXION_MODE=local",
    "KREXION_CLOUD_URL=https://krexion.com",
    ("IS_CUSTOMER_INSTALL=" + $CustomerMode.ToString().ToLower())
)
$envLines | Set-Content -Path $envPath -Encoding ASCII -Force
Show-Ok ".env generated [secure random passwords]"

# ============================================================
# STEP 7: Build + Start
# ============================================================
Show-Step "STEP 7/7: Building + Starting Krexion"

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

Show-Info "Containers build kar raha hun - YEH 5-15 MIN LE SAKTA HAI"
Show-Info "Background mein chal raha hai - heartbeat dikhata rahunga"

$buildJob = Start-Job -ScriptBlock {
    param($dir, $argz)
    Set-Location $dir
    $output = & docker compose @argz build 2>&1 | Out-String
    return @{ Exit = $LASTEXITCODE; Out = $output }
} -ArgumentList $INSTALL_DIR, $composeArgs

$buildStart = Get-Date
$buildDots = ""
while ($buildJob.State -eq "Running") {
    Start-Sleep -Seconds 20
    $buildElapsed = [int]((Get-Date) - $buildStart).TotalSeconds
    $buildDots = $buildDots + "."
    if ($buildDots.Length -gt 5) { $buildDots = "." }
    $bmsg = "  [..]   Build chal raha hai" + $buildDots + " (" + $buildElapsed + "s elapsed, please wait)"
    Write-Host $bmsg -ForegroundColor Cyan
    if ($buildElapsed -gt 1800) {
        Show-Warn "Build 30 min se zyada le raha hai - kuch issue ho sakta hai"
        break
    }
}

$buildResult = Receive-Job $buildJob
Remove-Job $buildJob -Force -ErrorAction SilentlyContinue
$buildResult.Out | Add-Content -Path $LOG_FILE -ErrorAction SilentlyContinue

if ($buildResult.Exit -ne 0) {
    Show-Err ("Build failed. Log: " + $LOG_FILE)
    Show-Err "Common fixes:"
    Show-Err "  1. PC restart karein"
    Show-Err "  2. Antivirus 10 min disable karein"
    Show-Err "  3. INSTALL.bat dobara chalayein"
    Pop-Location
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Show-Ok "Build complete"

Show-Info "Containers start kar raha hun"
& docker compose @composeArgs up -d 2>&1 | Tee-Object -FilePath $LOG_FILE -Append
$upExit = $LASTEXITCODE
if ($upExit -ne 0) {
    # Most common cause: a stale container with the same name from an
    # older install (e.g. "realflow-mongo") that survived our Step 6
    # cleanup. Force-remove anything that might conflict, then retry.
    Show-Warn "First start fail hua - conflicting containers clean kar ke retry karta hun"
    foreach ($n in $legacyContainers) {
        & docker rm -f $n 2>&1 | Out-Null
    }
    & docker compose @composeArgs down --remove-orphans 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    Show-Info "Retry: containers start kar raha hun"
    & docker compose @composeArgs up -d 2>&1 | Tee-Object -FilePath $LOG_FILE -Append
    $upExit = $LASTEXITCODE
}
if ($upExit -ne 0) {
    Show-Err ("Start failed. Log: " + $LOG_FILE)
    Show-Err "Common fixes:"
    Show-Err "  1. Krexion runtime (Docker Desktop) tray icon ko quit + restart karein"
    Show-Err "  2. PC restart karein"
    Show-Err "  3. INSTALL.bat dobara chalayein"
    Show-Err "Support: support@krexion.com (yeh log file attach karein)"
    Pop-Location
    Stop-Transcript -ErrorAction SilentlyContinue
    exit 1
}
Pop-Location

# ───────────────────────────────────────────────────────────────────
# Source-code hardening (CUSTOMER installs only).
# After the docker image has been successfully built — which already
# compiled all Python to optimised .pyc bytecode inside the image —
# we delete the readable .py/.js source files from the host disk.
# This prevents technical customers from reading our source, modifying
# it, redistributing it, or attempting to crack the licensing logic.
#
# The Docker container keeps running because the image already has
# the compiled bytecode + built frontend bundle baked in. Updates
# work the same way: UPDATE-WATCHER.bat pulls the latest source,
# rebuilds the image, then re-runs this scrub.
# ───────────────────────────────────────────────────────────────────
if ($CustomerMode) {
    Show-Info "Source hardening (encrypting customer files)…"
    try {
        # Strip backend Python source — only requirements.txt + Dockerfile remain
        Get-ChildItem -Path (Join-Path $INSTALL_DIR "backend") -Recurse -File -Include "*.py" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
        # Strip frontend React/JSX source — built bundle is already in the docker image
        $feSrc = Join-Path $INSTALL_DIR "frontend\src"
        if (Test-Path $feSrc) { Remove-Item $feSrc -Recurse -Force -ErrorAction SilentlyContinue }
        $fePub = Join-Path $INSTALL_DIR "frontend\public"
        if (Test-Path $fePub) { Remove-Item $fePub -Recurse -Force -ErrorAction SilentlyContinue }
        # Drop developer/admin docs that aren't needed at runtime
        Get-ChildItem -Path $INSTALL_DIR -File -Include "*.md", "HANDOFF*.md" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
        # Mark the install directory as "system" + "hidden" so casual file
        # explorer browsing doesn't reveal docker-compose internals.
        try {
            attrib +H +S "$INSTALL_DIR\backend" 2>&1 | Out-Null
            attrib +H +S "$INSTALL_DIR\frontend" 2>&1 | Out-Null
        } catch { }
        Show-Ok "Source files hardened — only compiled artefacts on disk"
    } catch {
        Show-Warn "Source hardening partial: $($_.Exception.Message)"
    }
}

# Wait for Krexion
Show-Info "Krexion ready hone ka wait"
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
Write-Host "  KREXION READY HAI!" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host ""

if ($CustomerMode) {
    # Customer mode - DO NOT show admin password
    Write-Host "  YEH STEPS FOLLOW KAREIN:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1. Browser khud khul jayega krexion.com login page pe" -ForegroundColor White
    Write-Host "  2. Welcome email mein jo email + password mile" -ForegroundColor White
    Write-Host "     wahi krexion.com pe daal kar login karein" -ForegroundColor White
    Write-Host "  3. Link create karein — sab links krexion.com/r/xxx pe" -ForegroundColor White
    Write-Host "     hain — 24/7 live, aap ka PC band ho to bhi chalein gay" -ForegroundColor White
    Write-Host ""
    Write-Host "  HEAVY FEATURES (Proxy Check / RUT / Form Filler):" -ForegroundColor Cyan
    Write-Host "    Yeh app aap ke PC mein silently chalega — sab kuch" -ForegroundColor White
    Write-Host "    krexion.com dashboard se control hoga." -ForegroundColor White
    Write-Host ""
    Write-Host "  YOUR LINKS:" -ForegroundColor Cyan
    Write-Host "    Main dashboard:  https://krexion.com/login" -ForegroundColor White
    Write-Host "    Buy License:     https://krexion.com/pricing" -ForegroundColor White
    Write-Host "    Support:         https://krexion.com/support" -ForegroundColor White
    Write-Host ""
} else {
    # Admin mode - show admin credentials
    Write-Host "  ACCESS URLS:" -ForegroundColor Cyan
    Write-Host "    App:         http://localhost:3000" -ForegroundColor White
    Write-Host "    Admin:       http://localhost:3000/admin-login" -ForegroundColor White
    Write-Host "    API Docs:    http://localhost:8001/docs" -ForegroundColor White
    Write-Host ""
    Write-Host "  ADMIN LOGIN:" -ForegroundColor Yellow
    Write-Host "    Email:       admin@krexion.local" -ForegroundColor White
    Write-Host ("    Password:    " + $adminPw) -ForegroundColor White
    Write-Host ""
}

# Save creds based on mode
$credsFile = "$env:USERPROFILE\Desktop\Krexion-Info.txt"
if ($CustomerMode) {
    # Customer credentials file - NO admin info
    $credsLines = @(
        "=================================================",
        "  Krexion - Aap Ka Setup",
        "=================================================",
        "",
        "  Main Dashboard (online — kahin se b login):",
        "    https://krexion.com/login",
        "",
        "  Welcome email mein jo email + password mile,",
        "  wahi krexion.com pe daal kar login karein.",
        "",
        "  Sab links krexion.com/r/xxx pe live rehte hain —",
        "  aap ka PC band ho ya open, links 24/7 chalein gay.",
        "",
        "  HEAVY FEATURES yahan silently background mein chalte hain:",
        "    - Proxy Check (1000+ proxies parallel)",
        "    - Real User Traffic (real Chrome)",
        "    - Form Filler",
        "    - CPI Worker",
        "  Inhe control karne ke liye bhi krexion.com use karein.",
        "",
        "  License khareedein:  https://krexion.com/pricing",
        "  Support:             https://krexion.com/support",
        "",
        ("  Installed:           " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')),
        ("  Folder:              " + $INSTALL_DIR),
        "",
        "=================================================",
        "  ZAROORI: Yeh file delete na karein!",
        "================================================="
    )
} else {
    # Admin credentials file
    $credsLines = @(
        "=================================================",
        "  Krexion - Aap Ke Admin Credentials",
        "=================================================",
        "",
        "  Browser kholein:",
        "    http://localhost:3000",
        "",
        "  Admin Login:",
        "    URL:       http://localhost:3000/admin-login",
        "    Email:     admin@krexion.local",
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
}
$credsLines | Set-Content -Path $credsFile -Encoding UTF8 -Force
Show-Ok ("Info saved: " + $credsFile)

# Desktop shortcut — opens the CLOUD dashboard at krexion.com/login.
# The local install runs silently in the background for heavy features
# (proxy check, RUT, form filler); the customer's daily work happens
# online so it feels like a true SaaS — not a local-only app.
try {
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut("$env:USERPROFILE\Desktop\Krexion.url")
    if ($CustomerMode) {
        $sc.TargetPath = "https://krexion.com/login"
    } else {
        $sc.TargetPath = "http://localhost:3000"
    }
    $sc.Save()
    Show-Ok "Desktop shortcut: Krexion (opens krexion.com)"
} catch { }

# Add Krexion to Windows startup so the cloud login auto-opens on every
# boot — customer experiences pure Krexion SaaS (local install stays
# headless in background for heavy features only).
try {
    $startupDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
    if (-not (Test-Path $startupDir)) { New-Item -ItemType Directory -Path $startupDir -Force | Out-Null }
    $startupLnk = Join-Path $startupDir "Krexion.url"
    $wsh2 = New-Object -ComObject WScript.Shell
    $sc2 = $wsh2.CreateShortcut($startupLnk)
    if ($CustomerMode) {
        $sc2.TargetPath = "https://krexion.com/login"
    } else {
        $sc2.TargetPath = "http://localhost:3000"
    }
    $sc2.Save()
    Show-Ok "Auto-start configured (Krexion opens on Windows login)"
} catch { }

# Re-apply hidden settings + clean up any Docker shortcuts created by the installer
Set-DockerHidden

# Open browser to cloud dashboard at krexion.com (customer's primary UX)
Show-Info "Browser open kar raha hun"
Start-Sleep -Seconds 2
if ($CustomerMode) {
    Start-Process "https://krexion.com/login"
} else {
    Start-Process "http://localhost:3000"
}

# Register Update Watcher scheduled task (runs every 1 minute) so
# "Install update" inside the app can trigger a host-side docker rebuild.
try {
    $watcherBat = Join-Path $INSTALL_DIR "UPDATE-WATCHER.bat"
    if (Test-Path $watcherBat) {
        $taskName = "KrexionUpdateWatcher"
        # Remove any prior version of the task
        schtasks /Delete /TN $taskName /F 2>$null | Out-Null
        # Re-register: run every 1 minute, highest privileges, no user interaction
        $action  = "cmd /c set KREXION_DIR=$INSTALL_DIR && `"$watcherBat`""
        schtasks /Create /TN $taskName /TR $action /SC MINUTE /MO 1 /RL HIGHEST /F | Out-Null
        # Make sure the data folder exists for the flag file
        $dataDir = Join-Path $INSTALL_DIR "data"
        if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir -Force | Out-Null }
        Show-Ok "Auto-update watcher enabled (runs every 1 min)"
    }
} catch {
    Show-Warn "Could not register update watcher task: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "  Mubarak ho! Krexion chal raha hai." -ForegroundColor Green
Write-Host ""

Stop-Transcript -ErrorAction SilentlyContinue
exit 0
