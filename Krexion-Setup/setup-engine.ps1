# =======================================================================
#   Krexion Setup Engine -- WinForms wizard, no command line in user's face
# =======================================================================

# Bootstrap log so even the earliest crash is captured to disk
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BootLog   = Join-Path $ScriptDir "setup.log"
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]  Wizard starting (PS $($PSVersionTable.PSVersion))" |
    Out-File -FilePath $BootLog -Encoding utf8

try {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
    Add-Type -AssemblyName System.Drawing       -ErrorAction Stop
} catch {
    $msg = "FATAL: Could not load Windows Forms / Drawing assemblies.`r`n$($_.Exception.Message)"
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]  $msg" | Out-File -FilePath $BootLog -Append -Encoding utf8
    Write-Host ""
    Write-Host $msg -ForegroundColor Red
    Write-Host ""
    Write-Host "This usually means .NET Desktop Runtime is missing. Install" -ForegroundColor Yellow
    Write-Host "it from https://dotnet.microsoft.com/download and try again." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press ENTER to exit"
    exit 1
}

$ErrorActionPreference = "Stop"
$ProgressPreference     = "SilentlyContinue"

# --- Paths -------------------------------------------------------------
$BundleDir   = Join-Path $ScriptDir "bundle"
$InstallPath = "C:\krexion"
$RepoUrl     = "https://github.com/ronaldsexedwards40-glitch/dynabook.git"
$Branch      = "main"
$ResumeFile  = Join-Path $ScriptDir ".resume-stage"
$LogFile     = Join-Path $ScriptDir "setup.log"
$LicenseFile = Join-Path $ScriptDir ".license"

# License-server URL -- installer phones home here to validate keys.
# DEFAULT: empty (license check disabled, free trial auto-granted). Change
# this to your own license server URL after you deploy it on Render/DO/etc.
# Example: $LicenseServer = "https://api.krexion.com"
$LicenseServer = ""

New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null
"" | Out-File -FilePath $LogFile -Encoding utf8

# --- Logging helper ----------------------------------------------------
function Log {
    param([string]$Message)
    $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    "$stamp  $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# --- Build the wizard form ---------------------------------------------
$form               = New-Object System.Windows.Forms.Form
$form.Text          = "Krexion Setup"
$form.Size          = New-Object System.Drawing.Size(640, 470)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox   = $false
$form.BackColor     = [System.Drawing.Color]::FromArgb(20, 24, 31)
$form.ForeColor     = [System.Drawing.Color]::White
$form.Font          = New-Object System.Drawing.Font("Segoe UI", 9)

# Header banner
$header             = New-Object System.Windows.Forms.Panel
$header.Size        = New-Object System.Drawing.Size(640, 80)
$header.Location    = New-Object System.Drawing.Point(0, 0)
$header.BackColor   = [System.Drawing.Color]::FromArgb(40, 60, 120)
$form.Controls.Add($header)

$titleLabel         = New-Object System.Windows.Forms.Label
$titleLabel.Text    = "Krexion"
$titleLabel.Font    = New-Object System.Drawing.Font("Segoe UI Semibold", 22, [System.Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = [System.Drawing.Color]::White
$titleLabel.Location  = New-Object System.Drawing.Point(20, 12)
$titleLabel.Size      = New-Object System.Drawing.Size(400, 36)
$titleLabel.BackColor = [System.Drawing.Color]::Transparent
$header.Controls.Add($titleLabel)

$subtitleLabel      = New-Object System.Windows.Forms.Label
$subtitleLabel.Text = "Self-hosted Traffic + Conversion Platform"
$subtitleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$subtitleLabel.ForeColor = [System.Drawing.Color]::FromArgb(200, 220, 255)
$subtitleLabel.Location  = New-Object System.Drawing.Point(22, 48)
$subtitleLabel.Size      = New-Object System.Drawing.Size(400, 22)
$subtitleLabel.BackColor = [System.Drawing.Color]::Transparent
$header.Controls.Add($subtitleLabel)

# Body -- status label
$statusLabel        = New-Object System.Windows.Forms.Label
$statusLabel.Text   = "Ready to install Krexion on this PC."
$statusLabel.Font   = New-Object System.Drawing.Font("Segoe UI", 11)
$statusLabel.Location  = New-Object System.Drawing.Point(20, 100)
$statusLabel.Size      = New-Object System.Drawing.Size(600, 28)
$statusLabel.ForeColor = [System.Drawing.Color]::White
$form.Controls.Add($statusLabel)

# Detail label
$detailLabel        = New-Object System.Windows.Forms.Label
$detailLabel.Text   = "Click INSTALL to begin. The wizard will:`r`n  - Download and install Docker Desktop (if missing)`r`n  - Install Git (if missing)`r`n  - Download Krexion code`r`n  - Generate secure passwords`r`n  - Build and start the app`r`n  - Open it in your browser"
$detailLabel.Font   = New-Object System.Drawing.Font("Segoe UI", 9)
$detailLabel.Location  = New-Object System.Drawing.Point(20, 134)
$detailLabel.Size      = New-Object System.Drawing.Size(600, 130)
$detailLabel.ForeColor = [System.Drawing.Color]::FromArgb(190, 200, 220)
$form.Controls.Add($detailLabel)

# Progress bar
$progressBar           = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location  = New-Object System.Drawing.Point(20, 270)
$progressBar.Size      = New-Object System.Drawing.Size(595, 22)
$progressBar.Style     = "Continuous"
$progressBar.Minimum   = 0
$progressBar.Maximum   = 100
$progressBar.Value     = 0
$form.Controls.Add($progressBar)

# Progress text
$progressText       = New-Object System.Windows.Forms.Label
$progressText.Text  = ""
$progressText.Font  = New-Object System.Drawing.Font("Consolas", 9)
$progressText.Location  = New-Object System.Drawing.Point(20, 296)
$progressText.Size      = New-Object System.Drawing.Size(595, 22)
$progressText.ForeColor = [System.Drawing.Color]::FromArgb(150, 200, 255)
$form.Controls.Add($progressText)

# Log box
$logBox             = New-Object System.Windows.Forms.TextBox
$logBox.Multiline   = $true
$logBox.ReadOnly    = $true
$logBox.ScrollBars  = "Vertical"
$logBox.Location    = New-Object System.Drawing.Point(20, 326)
$logBox.Size        = New-Object System.Drawing.Size(595, 60)
$logBox.BackColor   = [System.Drawing.Color]::FromArgb(12, 16, 22)
$logBox.ForeColor   = [System.Drawing.Color]::FromArgb(160, 180, 200)
$logBox.Font        = New-Object System.Drawing.Font("Consolas", 8)
$form.Controls.Add($logBox)

# INSTALL button -- the only thing the user touches
$installBtn         = New-Object System.Windows.Forms.Button
$installBtn.Text    = "INSTALL"
$installBtn.Font    = New-Object System.Drawing.Font("Segoe UI Semibold", 11, [System.Drawing.FontStyle]::Bold)
$installBtn.Location  = New-Object System.Drawing.Point(440, 395)
$installBtn.Size      = New-Object System.Drawing.Size(175, 36)
$installBtn.BackColor = [System.Drawing.Color]::FromArgb(70, 130, 220)
$installBtn.ForeColor = [System.Drawing.Color]::White
$installBtn.FlatStyle = "Flat"
$installBtn.FlatAppearance.BorderSize = 0
$form.Controls.Add($installBtn)

$cancelBtn          = New-Object System.Windows.Forms.Button
$cancelBtn.Text     = "Cancel"
$cancelBtn.Font     = New-Object System.Drawing.Font("Segoe UI", 10)
$cancelBtn.Location   = New-Object System.Drawing.Point(20, 395)
$cancelBtn.Size       = New-Object System.Drawing.Size(100, 36)
$cancelBtn.BackColor  = [System.Drawing.Color]::FromArgb(50, 55, 65)
$cancelBtn.ForeColor  = [System.Drawing.Color]::White
$cancelBtn.FlatStyle  = "Flat"
$cancelBtn.FlatAppearance.BorderSize = 0
$form.Controls.Add($cancelBtn)

$cancelBtn.Add_Click({ $form.Close() })

# --- Helper: update UI from the install loop ---------------------------
function Set-UI {
    param(
        [object]$Percent  = $null,
        [string]$Status   = $null,
        [string]$Progress = $null,
        [string]$Log      = $null
    )
    if ($Percent -ne $null)  { $progressBar.Value = [Math]::Min(100, [Math]::Max(0, [int]$Percent)) }
    if ($Status   -ne $null) { $statusLabel.Text = $Status }
    if ($Progress -ne $null) { $progressText.Text = $Progress }
    if ($Log      -ne $null) {
        $logBox.AppendText("$Log`r`n")
        Log $Log
    }
    [System.Windows.Forms.Application]::DoEvents()
}

# --- The actual install logic, broken into stages ----------------------
function Invoke-Stage1-PrepareTools {
    Set-UI -Percent 5 -Status "Step 1 / 6 -- Checking required tools..." -Progress "" -Log "Stage 1: prepare tools"

    # -- Git is OPTIONAL --
    # Stage 3 uses ZIP download from GitHub (no git needed). Git is only
    # installed opportunistically so future updates can use 'git pull'.
    # If Git install fails for any reason, we continue (ZIP fallback works).
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Set-UI -Percent 8 -Progress "Installing Git (optional)..."
        try {
            $gitInstaller = Join-Path $BundleDir "Git-Installer.exe"
            if (-not (Test-Path $gitInstaller) -or (Get-Item $gitInstaller).Length -lt 10MB) {
                Set-UI -Progress "Downloading Git (~50 MB)..." -Log "  Downloading Git for Windows"
                Invoke-WebRequest -UseBasicParsing `
                    -Uri "https://github.com/git-for-windows/git/releases/download/v2.46.0.windows.1/Git-2.46.0-64-bit.exe" `
                    -OutFile $gitInstaller -TimeoutSec 600
            } else {
                Set-UI -Log "  Using cached Git installer"
            }
            Set-UI -Progress "Installing Git (silent)..."
            Start-Process -FilePath $gitInstaller -ArgumentList "/VERYSILENT", "/NORESTART", "/NOCANCEL", "/SP-", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS" -Wait
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        } catch {
            Set-UI -Log "  Git install skipped: $($_.Exception.Message) (continuing -- ZIP download will be used)"
        }
    }
    $gitVer = (& git --version 2>$null)
    if ($gitVer) { Set-UI -Log "  Git: OK ($gitVer)" } else { Set-UI -Log "  Git: not installed (OK -- ZIP download will be used)" }

    # -- Docker Desktop --
    Set-UI -Percent 15 -Progress "Checking Docker Desktop..."
    $dockerInstalled = (Get-Command docker -ErrorAction SilentlyContinue) -ne $null
    if (-not $dockerInstalled) {
        Set-UI -Percent 18 -Progress "Downloading Docker Desktop (~520 MB, slow internet may take 10-20 min)..." -Log "  Docker Desktop missing -- downloading"
        $dockerInstaller = Join-Path $BundleDir "DockerDesktopInstaller.exe"
        if (-not (Test-Path $dockerInstaller) -or (Get-Item $dockerInstaller).Length -lt 200MB) {
            Invoke-WebRequest -UseBasicParsing `
                -Uri "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" `
                -OutFile $dockerInstaller
        } else {
            Set-UI -Log "  Using cached Docker installer"
        }
        Set-UI -Percent 35 -Progress "Installing Docker Desktop (this takes 3-5 min)..." -Log "  Running Docker installer (silent)"
        Start-Process -FilePath $dockerInstaller -ArgumentList "install", "--quiet", "--accept-license" -Wait

        # Save resume marker -- we need a reboot for WSL2 / Hyper-V to come online
        "stage1_done" | Out-File -FilePath $ResumeFile -Encoding ascii
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

        $result = [System.Windows.Forms.MessageBox]::Show(
            "Docker Desktop installed successfully.`r`n`r`nA RESTART is required so Windows can enable WSL2 / Hyper-V.`r`n`r`nClick OK to restart now. After restart, just double-click  Install.bat  again -- the wizard will continue automatically.",
            "Restart Required",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        )
        Restart-Computer -Force
        exit
    }
    Set-UI -Log "  Docker: $((docker --version) 2>$null)"

    # -- Make sure Docker daemon is up --
    Set-UI -Percent 22 -Progress "Waiting for Docker engine..."
    $dockerOk = $false
    for ($i = 0; $i -lt 90; $i++) {
        try { docker info 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break } } catch {}
        Start-Sleep 2
        if ($i % 5 -eq 0) { Set-UI -Progress "Waiting for Docker engine (~$($i*2)s)..." }
    }
    if (-not $dockerOk) {
        # Try to launch Docker Desktop ourselves
        $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        if (Test-Path $dockerExe) {
            Set-UI -Log "  Starting Docker Desktop..."
            Start-Process -FilePath $dockerExe
            for ($i = 0; $i -lt 60; $i++) {
                try { docker info 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { $dockerOk = $true; break } } catch {}
                Start-Sleep 2
            }
        }
    }
    if (-not $dockerOk) {
        throw "Docker engine did not start. Open Docker Desktop from the Start menu, wait until the whale icon stops animating, then re-run this installer."
    }
    Set-UI -Log "  Docker engine: running"
}

function Invoke-Stage2-WSLConfig {
    Set-UI -Percent 28 -Status "Step 2 / 6 -- Updating WSL kernel (if needed)..." -Progress "wsl --update"

    # Run wsl --update -- THE most common reason Docker Desktop refuses
    # to start on fresh Windows 10/11 PCs is "WSL is too old". We do
    # this BEFORE writing .wslconfig and BEFORE relying on Docker engine.
    try {
        Set-UI -Log "  Running: wsl --update (downloads new kernel from Microsoft)"
        $wslOut = & wsl.exe --update 2>&1 | Out-String
        $last = ($wslOut.Trim() -split "`r?`n")[-1]
        Set-UI -Log "  WSL update: $last"
    } catch {
        Set-UI -Log "  WSL update skipped: $($_.Exception.Message)"
    }

    try {
        & wsl.exe --set-default-version 2 2>&1 | Out-Null
        Set-UI -Log "  WSL default version set to 2"
    } catch {}

    Set-UI -Percent 30 -Status "Step 2 / 6 -- Tuning WSL for your hardware..." -Progress "Detecting profile"

    # ----- Load shared profile picker -----
    $detect = Join-Path $InstallPath "scripts\detect-hardware.ps1"
    if (Test-Path $detect) {
        . $detect
    } else {
        # Fallback inline picker if scripts/ folder missing
        function Get-KrexionProfile {
            $r = [int][math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 0)
            $c = (Get-CimInstance Win32_Processor | Measure-Object NumberOfLogicalProcessors -Sum).Sum
            if (-not $c) { $c = [Environment]::ProcessorCount }
            $ceil = [Math]::Max(1, $c * 2)
            if     ($r -le 6)  { @{Tier="MICRO";WSLMemory="4GB"; WSLProcessors=[Math]::Min($c,4); RutConcurrency=[Math]::Min(1, $ceil);  TotalRamGB=$r; CpuCores=$c; ComposeOverride="docker-compose.micro.yml"} }
            elseif ($r -le 10) { @{Tier="LOW";  WSLMemory="5GB"; WSLProcessors=[Math]::Min($c,4); RutConcurrency=[Math]::Min(2, $ceil);  TotalRamGB=$r; CpuCores=$c; ComposeOverride="docker-compose.lowram.yml"} }
            elseif ($r -le 16) { @{Tier="MID";  WSLMemory="10GB";WSLProcessors=[Math]::Min($c,8); RutConcurrency=[Math]::Min(4, $ceil);  TotalRamGB=$r; CpuCores=$c; ComposeOverride="docker-compose.mid.yml"} }
            elseif ($r -le 32) { @{Tier="HIGH"; WSLMemory="20GB";WSLProcessors=[Math]::Min($c,10);RutConcurrency=[Math]::Min(8, $ceil);  TotalRamGB=$r; CpuCores=$c; ComposeOverride="docker-compose.high.yml"} }
            else               { @{Tier="BEAST";WSLMemory="32GB";WSLProcessors=[Math]::Min($c,12);RutConcurrency=[Math]::Min(16,$ceil);  TotalRamGB=$r; CpuCores=$c; ComposeOverride="docker-compose.beast.yml"} }
        }
    }

    $rfProfile = Get-KrexionProfile
    $script:RFProfile = $rfProfile

    Set-UI -Log "  Detected: $($rfProfile.TotalRamGB) GB RAM, $($rfProfile.CpuCores) CPU cores -> Tier $($rfProfile.Tier)"
    Set-UI -Log "  -> RUT concurrency = $($rfProfile.RutConcurrency), WSL memory = $($rfProfile.WSLMemory)"

    $wslcfg = Join-Path $env:USERPROFILE ".wslconfig"
    $totalRamGB = $rfProfile.TotalRamGB
    $cap        = $rfProfile.WSLMemory
    $procs      = $rfProfile.WSLProcessors

    @"
[wsl2]
memory=$cap
processors=$procs
swap=4GB
localhostForwarding=true

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
"@ | Out-File -FilePath $wslcfg -Encoding ascii

    Set-UI -Log "  Wrote $wslcfg (memory=$cap, processors=$procs on a $totalRamGB GB / $($rfProfile.CpuCores)-core system, tier=$($rfProfile.Tier))"
    & wsl.exe --shutdown 2>$null | Out-Null
    Start-Sleep 3

    # Docker Desktop may have shown "WSL too old". Restart it so it picks
    # up the freshly updated WSL kernel.
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    try {
        Get-Process "Docker Desktop" -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
        Get-Process "com.docker.backend" -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
        Set-UI -Log "  Stopped Docker Desktop (will relaunch with new WSL)"
        Start-Sleep 2
        if (Test-Path $dockerExe) {
            Start-Process -FilePath $dockerExe
            Set-UI -Log "  Re-started Docker Desktop, waiting for engine..."
            for ($i = 0; $i -lt 90; $i++) {
                try { docker info 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { break } } catch {}
                Start-Sleep 2
                if ($i % 5 -eq 0) { Set-UI -Progress "Waiting for Docker engine after WSL update ($($i*2)s)..." }
            }
            Set-UI -Log "  Docker engine ready after WSL update"
        }
    } catch {
        Set-UI -Log "  Docker restart skipped: $($_.Exception.Message)"
    }
}

function Invoke-Stage3-FetchCode {
    # ============================================================
    # Bulletproof source fetch: ZIP download from GitHub (no git
    # dependency, no PATH issues, no clone-into-non-empty-folder).
    # ============================================================
    Set-UI -Percent 35 -Status "Step 3 / 6 -- Checking internet..." -Progress "ping github.com"

    # 1. Network pre-check
    try {
        $null = Invoke-WebRequest -Uri "https://github.com" -UseBasicParsing -TimeoutSec 12 -ErrorAction Stop
        Set-UI -Log "  Network OK -- GitHub reachable"
    } catch {
        throw "Cannot reach GitHub.`r`n`r`nCheck your internet connection.`r`nIf on office WiFi try mobile hotspot or VPN.`r`n`r`nDetail: $($_.Exception.Message)"
    }

    Set-UI -Percent 40 -Status "Step 3 / 6 -- Cleaning up any old install..." -Progress "Remove old C:\krexion"

    # 2. ROBUST cleanup of any prior install (handles locked files, partial installs)
    if (Test-Path $InstallPath) {
        # First, stop any docker containers using this path so files unlock
        if (Test-Path (Join-Path $InstallPath "docker-compose.yml")) {
            try {
                Push-Location $InstallPath
                & docker compose down 2>&1 | Out-Null
                Pop-Location
            } catch {}
        }
        # Take ownership + grant full perms (admin already running)
        try {
            & takeown.exe /F $InstallPath /R /D Y 2>&1 | Out-Null
            & icacls.exe $InstallPath /grant "Administrators:F" /T /C /Q 2>&1 | Out-Null
        } catch {}
        # Try delete twice (some processes release locks slowly)
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $InstallPath
        if (Test-Path $InstallPath) {
            Start-Sleep -Seconds 3
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $InstallPath
        }
        if (Test-Path $InstallPath) {
            throw "Could not delete $InstallPath.`r`n`r`nFIX:`r`n  1. Close VS Code, file explorer, and any program with files open in C:\krexion`r`n  2. Open Task Manager -- end any 'docker' or 'node' processes`r`n  3. Restart your PC`r`n  4. Run this installer again"
        }
        Set-UI -Log "  Old install cleaned up successfully"
    }

    Set-UI -Percent 45 -Status "Step 3 / 6 -- Downloading Krexion from GitHub..." -Progress "Downloading ZIP (~5 MB)"

    # 3. Download ZIP (no git needed)
    $zipUrl     = $RepoUrl -replace "\.git$","" -replace "https://github.com","https://github.com"
    $zipUrl     = "$zipUrl/archive/refs/heads/$Branch.zip"
    $tempZip    = Join-Path $env:TEMP "krexion-source.zip"
    $tempExtract = Join-Path $env:TEMP "krexion-extract"

    if (Test-Path $tempZip)     { Remove-Item -Force $tempZip }
    if (Test-Path $tempExtract) { Remove-Item -Recurse -Force $tempExtract }

    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip -UseBasicParsing -TimeoutSec 600
        $sizeMB = [math]::Round((Get-Item $tempZip).Length / 1MB, 1)
        Set-UI -Log "  Downloaded $sizeMB MB from $zipUrl"
    } catch {
        throw "Could not download from GitHub.`r`n`r`nURL: $zipUrl`r`nDetail: $($_.Exception.Message)`r`n`r`nFIX:`r`n  1. Check your internet`r`n  2. Manually open the URL in a browser to test`r`n  3. If your ISP blocks GitHub, use a VPN or mobile hotspot`r`n  4. Re-run this installer"
    }

    Set-UI -Percent 47 -Status "Step 3 / 6 -- Extracting source code..." -Progress "Unzipping"

    # 4. Extract
    try {
        Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force
    } catch {
        throw "Could not extract the downloaded ZIP.`r`n`r`nFIX:`r`n  - Make sure you have at least 1 GB free disk space`r`n  - Run installer as Administrator (right-click -> Run as administrator)"
    }

    # 5. Move extracted folder to C:\krexion
    $extractedFolder = Get-ChildItem -Path $tempExtract -Directory | Select-Object -First 1
    if (-not $extractedFolder) {
        throw "ZIP extracted but no source folder found. Try re-running installer."
    }
    Move-Item -Path $extractedFolder.FullName -Destination $InstallPath -Force
    Remove-Item -Recurse -Force $tempZip, $tempExtract -ErrorAction SilentlyContinue

    Set-UI -Log "  Source code extracted to $InstallPath"
}

function Invoke-Stage4-GenerateEnv {
    Set-UI -Percent 50 -Status "Step 4 / 6 -- Generating secure passwords..." -Progress "Writing .env"

    $envFile = Join-Path $InstallPath ".env"
    if (Test-Path $envFile) {
        Set-UI -Log "  .env already exists -- keeping existing secrets"
        return
    }

    function Gen { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_}) }
    $jwt   = Gen
    $admin = Gen
    $post  = Gen

    @"
# Generated by Krexion Setup on $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))
DB_NAME=krexion
JWT_SECRET_KEY=$jwt
ADMIN_EMAIL=admin@krexion.local
ADMIN_PASSWORD=$admin
POSTBACK_TOKEN=$post
APP_URL=http://localhost:3000
PUBLIC_BASE_URL=http://localhost:3000
CORS_ORIGINS=*

# License (set by installer)
LICENSE_KEY=$(if (Test-Path $LicenseFile) { (Get-Content $LicenseFile -Raw).Trim() } else { '' })
LICENSE_SERVER_URL=$LicenseServer

# Optional
RESEND_API_KEY=
RESEND_FROM=no-reply@krexion.local
GOOGLE_SHEETS_SA_PATH=
GOOGLE_SHEETS_SA_JSON=
TUNNEL_TOKEN=
"@ | Out-File -FilePath $envFile -Encoding ascii

    Set-UI -Log "  Generated .env with admin password: $admin"
    $script:GeneratedAdminPassword = $admin
}

function Invoke-Stage5-BuildAndStart {
    Set-UI -Percent 60 -Status "Step 5 / 6 -- Building Docker images (5-10 min first time)..." -Progress "docker compose build"

    Push-Location $InstallPath

    # ----- Pick the correct docker-compose override based on detected tier -----
    $composeArgs = @("-f", "docker-compose.yml")
    if ($script:RFProfile -and $script:RFProfile.ComposeOverride) {
        $override = $script:RFProfile.ComposeOverride
        if (Test-Path $override) {
            Set-UI -Log "  Tier $($script:RFProfile.Tier): using $override"
            Set-UI -Log "  Tuning: RUT concurrency=$($script:RFProfile.RutConcurrency), $($script:RFProfile.TotalRamGB) GB RAM / $($script:RFProfile.CpuCores) cores"
            $composeArgs += @("-f", $override)
        } else {
            Set-UI -Log "  Tier override $override not found - running with base profile (will use 8 GB defaults)"
        }
    } else {
        # Last-resort fallback (should never trigger because Stage 2 always sets RFProfile)
        $totalRamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 0)
        if ($totalRamGB -le 10 -and (Test-Path "docker-compose.lowram.yml")) {
            Set-UI -Log "  Fallback low-RAM ($totalRamGB GB) - using docker-compose.lowram.yml"
            $composeArgs += @("-f", "docker-compose.lowram.yml")
        }
    }

    Set-UI -Log "  docker compose $($composeArgs -join ' ') build"
    & docker compose @composeArgs build 2>&1 | Tee-Object -FilePath $LogFile -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        throw "Docker image build failed (exit code $LASTEXITCODE). See full log: $LogFile`r`n`r`nCommon causes:`r`n  - Docker Desktop not fully started (open it, wait 1-2 min)`r`n  - Less than 5 GB free disk space`r`n  - Slow internet caused image download to time out (re-run installer)"
    }

    Set-UI -Percent 80 -Progress "Starting containers..." -Log "  docker compose up -d"
    & docker compose @composeArgs up -d 2>&1 | Tee-Object -FilePath $LogFile -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        throw "Docker containers failed to start (exit code $LASTEXITCODE). See log: $LogFile`r`n`r`nTry: open Command Prompt -> cd C:\krexion -> docker compose up -d -> read the error"
    }

    Pop-Location
}

function Invoke-Stage6-WaitAndOpen {
    Set-UI -Percent 88 -Status "Step 6 / 6 -- Waiting for services to start..." -Progress "Health check"

    # Backend health
    $backendOk = $false
    for ($i = 0; $i -lt 90; $i++) {
        try {
            $r = Invoke-WebRequest "http://localhost:8001/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $backendOk = $true; break }
        } catch {}
        Start-Sleep 2
        if ($i % 5 -eq 0) { Set-UI -Progress "Waiting for backend ($($i*2)s)..." }
    }
    if ($backendOk) { Set-UI -Log "  Backend: UP" } else { Set-UI -Log "  Backend: timeout (check Docker Desktop)" }

    # Frontend
    Set-UI -Percent 95 -Progress "Waiting for frontend..."
    $frontOk = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $r = Invoke-WebRequest "http://localhost:3000" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $frontOk = $true; break }
        } catch {}
        Start-Sleep 2
    }
    if ($frontOk) { Set-UI -Log "  Frontend: UP at http://localhost:3000" } else { Set-UI -Log "  Frontend: timeout" }

    # Desktop shortcut
    $shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Krexion.url"
    "[InternetShortcut]`r`nURL=http://localhost:3000`r`nIconIndex=0" | Out-File -FilePath $shortcut -Encoding ascii
    Set-UI -Log "  Created Desktop shortcut: Krexion.url"

    Set-UI -Percent 100 -Progress "Install complete!" -Status "OK Done -- Krexion is running."

    # Read admin password from .env
    $envFile = Join-Path $InstallPath ".env"
    $adminEmail = ((Get-Content $envFile | Where-Object { $_ -match '^ADMIN_EMAIL=' }) -replace '^ADMIN_EMAIL=', '').Trim('"')
    $adminPass  = ((Get-Content $envFile | Where-Object { $_ -match '^ADMIN_PASSWORD=' }) -replace '^ADMIN_PASSWORD=', '').Trim('"')

    # Switch UI to "Done" mode
    $installBtn.Text = "OPEN KREXION"
    $installBtn.BackColor = [System.Drawing.Color]::FromArgb(60, 180, 90)
    $cancelBtn.Text = "Finish"

    $titleLabel.Text = "Installation Complete!"
    $subtitleLabel.Text = "Click OPEN KREXION to launch your dashboard."
    $detailLabel.Text = "URL:          http://localhost:3000`r`nAdmin login:  http://localhost:3000/admin-login`r`n  Email:      $adminEmail`r`n  Password:   $adminPass`r`n`r`nIMPORTANT: Save the password above -- it is also stored in:`r`n   $envFile`r`n`r`nA Desktop shortcut `"Krexion.url`" has been created."
    $detailLabel.ForeColor = [System.Drawing.Color]::FromArgb(220, 240, 255)

    # Re-wire the button
    $installBtn.Add_Click({
        Start-Process "http://localhost:3000"
    })

    # Clean resume marker
    if (Test-Path $ResumeFile) { Remove-Item -Force $ResumeFile }
}

# --- Main install flow (called when user clicks INSTALL) ---------------
function Start-Install {
    $installBtn.Enabled = $false
    $cancelBtn.Enabled  = $false

    try {
        $resume = ""
        if (Test-Path $ResumeFile) { $resume = (Get-Content $ResumeFile -Raw).Trim() }

        if ($resume -ne "stage1_done") {
            Invoke-Stage1-PrepareTools
        } else {
            Set-UI -Status "Resuming after restart..." -Log "Resume from stage 1"
            # Re-verify docker is up after reboot
            Invoke-Stage1-PrepareTools
        }
        Invoke-Stage2-WSLConfig
        Invoke-Stage3-FetchCode
        Invoke-Stage4-GenerateEnv
        Invoke-Stage5-BuildAndStart
        Invoke-Stage6-WaitAndOpen

        $cancelBtn.Enabled = $true
        $installBtn.Enabled = $true
    }
    catch {
        $err = $_.Exception.Message
        Set-UI -Status "X Install failed." -Progress "" -Log "ERROR: $err"

        # Pick a context-aware fix suggestion based on the error message
        $fix = ""
        if ($err -match "Cannot reach GitHub|unable to access|github.com|getaddrinfo|timed out|TimeoutSec") {
            $fix = "NETWORK ISSUE:`r`n  1. Check WiFi / Ethernet`r`n  2. Open https://github.com in a browser to verify`r`n  3. If your ISP blocks it, try mobile hotspot or VPN`r`n  4. Re-run this installer"
        } elseif ($err -match "Could not delete|access.*denied|in use by another process|Permission denied") {
            $fix = "FILE LOCK ISSUE:`r`n  1. Close VS Code, file explorer, terminals open on C:\krexion`r`n  2. Open Task Manager -- end any 'docker'/'node' processes`r`n  3. Restart your PC`r`n  4. Run this installer AS ADMINISTRATOR (right-click -> Run as administrator)"
        } elseif ($err -match "Docker|docker daemon|docker engine|dockerd|wsl") {
            $fix = "DOCKER ISSUE:`r`n  1. Open Start Menu -> Docker Desktop -> wait for whale icon to stop animating (1-2 min)`r`n  2. If still failing, restart your PC`r`n  3. Make sure Windows 10 (Build 19041+) or Windows 11`r`n  4. Re-run this installer"
        } elseif ($err -match "disk space|out of space|enough space") {
            $fix = "DISK SPACE ISSUE:`r`n  1. Free up at least 10 GB on C: drive`r`n  2. Empty Recycle Bin`r`n  3. Run Disk Cleanup (Win+R -> cleanmgr)`r`n  4. Re-run this installer"
        } else {
            $fix = "GENERIC FIX:`r`n  1. Open the log file: $LogFile`r`n  2. Scroll to the END for the real error`r`n  3. WhatsApp / email the last 30 lines of the log to support`r`n  4. Or just try: restart PC -> open Docker Desktop -> re-run installer"
        }

        [System.Windows.Forms.MessageBox]::Show(
            "Installation failed:`r`n`r`n$err`r`n`r`n--------------------`r`n$fix`r`n--------------------`r`n`r`nFull log: $LogFile",
            "Krexion Setup -- Error",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        )
        $installBtn.Enabled = $true
        $cancelBtn.Enabled  = $true
    }
}

# --- If we are resuming after reboot, auto-start the install ----------
if (Test-Path $ResumeFile) {
    $form.Add_Shown({ Start-Install })
} else {
    $installBtn.Add_Click({
        # Run license activation first; only proceed if it succeeds
        if (Invoke-LicenseActivation) {
            Start-Install
        }
    })
}

# =======================================================================
#   LICENSE ACTIVATION  --  shown as a modal dialog before install starts
# =======================================================================
function Get-MachineId {
    # Stable per-PC fingerprint that survives reboot but not OS reinstall
    try {
        $uuid = (Get-CimInstance Win32_ComputerSystemProduct -ErrorAction Stop).UUID
        if ($uuid -and $uuid -notmatch "^0+$") { return "WIN-$uuid" }
    } catch {}
    try {
        $mac = (Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | Select-Object -First 1).MacAddress
        if ($mac) { return "MAC-" + ($mac -replace "[:\-]", "") }
    } catch {}
    return "GUID-" + ([guid]::NewGuid().ToString("N"))
}

function Invoke-LicensingDisabled {
    # Server returned enabled=false -- proceed without a key, "open install"
    Set-UI -Log "  Licensing disabled on server -- installing without activation"
    "DISABLED" | Out-File -FilePath $LicenseFile -Encoding ascii
    return $true
}

function Show-LicenseDialog {
    param($Config)

    # Build secondary dialog
    $dlg = New-Object System.Windows.Forms.Form
    $dlg.Text = "Krexion -- License Activation"
    $dlg.Size = New-Object System.Drawing.Size(560, 460)
    $dlg.StartPosition = "CenterParent"
    $dlg.FormBorderStyle = "FixedDialog"
    $dlg.MaximizeBox = $false
    $dlg.BackColor = [System.Drawing.Color]::FromArgb(20, 24, 31)
    $dlg.ForeColor = [System.Drawing.Color]::White
    $dlg.Font = New-Object System.Drawing.Font("Segoe UI", 9)

    $hdr = New-Object System.Windows.Forms.Label
    $hdr.Text = "Activate $($Config.product_name)"
    $hdr.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 16, [System.Drawing.FontStyle]::Bold)
    $hdr.Location = New-Object System.Drawing.Point(20, 18)
    $hdr.Size = New-Object System.Drawing.Size(500, 32)
    $dlg.Controls.Add($hdr)

    $sub = New-Object System.Windows.Forms.Label
    $price = "{0:N2}" -f [double]$Config.monthly_price
    $cur = $Config.currency.ToString().ToUpper()
    $trial = [int]$Config.trial_days
    $sub.Text = "$price $cur / month  *  $trial-day free trial  *  1 license = 1 PC  *  Manual purchase via admin"
    $sub.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $sub.ForeColor = [System.Drawing.Color]::FromArgb(180, 200, 230)
    $sub.Location = New-Object System.Drawing.Point(20, 52)
    $sub.Size = New-Object System.Drawing.Size(500, 22)
    $dlg.Controls.Add($sub)

    # Tab: License key
    $gp1 = New-Object System.Windows.Forms.GroupBox
    $gp1.Text = "  I already have a license key  "
    $gp1.Location = New-Object System.Drawing.Point(20, 86)
    $gp1.Size = New-Object System.Drawing.Size(500, 90)
    $gp1.ForeColor = [System.Drawing.Color]::White
    $dlg.Controls.Add($gp1)

    $lblKey = New-Object System.Windows.Forms.Label
    $lblKey.Text = "License key (RFLW-XXXX-XXXX-XXXX-XXXX):"
    $lblKey.Location = New-Object System.Drawing.Point(12, 26)
    $lblKey.Size = New-Object System.Drawing.Size(260, 18)
    $gp1.Controls.Add($lblKey)

    $txtKey = New-Object System.Windows.Forms.TextBox
    $txtKey.Location = New-Object System.Drawing.Point(12, 46)
    $txtKey.Size = New-Object System.Drawing.Size(370, 26)
    $txtKey.Font = New-Object System.Drawing.Font("Consolas", 10)
    $gp1.Controls.Add($txtKey)

    $btnActivate = New-Object System.Windows.Forms.Button
    $btnActivate.Text = "Activate"
    $btnActivate.Location = New-Object System.Drawing.Point(390, 44)
    $btnActivate.Size = New-Object System.Drawing.Size(100, 30)
    $btnActivate.BackColor = [System.Drawing.Color]::FromArgb(70, 130, 220)
    $btnActivate.ForeColor = [System.Drawing.Color]::White
    $btnActivate.FlatStyle = "Flat"
    $btnActivate.FlatAppearance.BorderSize = 0
    $gp1.Controls.Add($btnActivate)

    # Tab: Start trial
    $gp2 = New-Object System.Windows.Forms.GroupBox
    $gp2.Text = "  Start a free trial  "
    $gp2.Location = New-Object System.Drawing.Point(20, 186)
    $gp2.Size = New-Object System.Drawing.Size(500, 90)
    $gp2.ForeColor = [System.Drawing.Color]::White
    $dlg.Controls.Add($gp2)

    if ($trial -le 0) {
        $gp2.Enabled = $false
        $gp2.Text = "  Free trial currently disabled  "
    }

    $lblEmail = New-Object System.Windows.Forms.Label
    $lblEmail.Text = "Your email (where activation receipt is sent):"
    $lblEmail.Location = New-Object System.Drawing.Point(12, 26)
    $lblEmail.Size = New-Object System.Drawing.Size(280, 18)
    $gp2.Controls.Add($lblEmail)

    $txtEmail = New-Object System.Windows.Forms.TextBox
    $txtEmail.Location = New-Object System.Drawing.Point(12, 46)
    $txtEmail.Size = New-Object System.Drawing.Size(370, 26)
    $gp2.Controls.Add($txtEmail)

    $btnTrial = New-Object System.Windows.Forms.Button
    $btnTrial.Text = "Start trial"
    $btnTrial.Location = New-Object System.Drawing.Point(390, 44)
    $btnTrial.Size = New-Object System.Drawing.Size(100, 30)
    $btnTrial.BackColor = [System.Drawing.Color]::FromArgb(60, 180, 90)
    $btnTrial.ForeColor = [System.Drawing.Color]::White
    $btnTrial.FlatStyle = "Flat"
    $btnTrial.FlatAppearance.BorderSize = 0
    $gp2.Controls.Add($btnTrial)

    # Tab: Contact admin to buy (manual / crypto / bank -- no online payment)
    $btnBuy = New-Object System.Windows.Forms.Button
    $contactEmail = if ($Config.admin_contact_email) { $Config.admin_contact_email } else { "admin@krexion.local" }
    $btnBuy.Text = "Contact Admin to Buy a License"
    $btnBuy.Location = New-Object System.Drawing.Point(20, 290)
    $btnBuy.Size = New-Object System.Drawing.Size(500, 36)
    $btnBuy.BackColor = [System.Drawing.Color]::FromArgb(120, 80, 200)
    $btnBuy.ForeColor = [System.Drawing.Color]::White
    $btnBuy.FlatStyle = "Flat"
    $btnBuy.FlatAppearance.BorderSize = 0
    $btnBuy.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 10)
    $dlg.Controls.Add($btnBuy)

    $lblStatus = New-Object System.Windows.Forms.Label
    $lblStatus.Location = New-Object System.Drawing.Point(20, 336)
    $lblStatus.Size = New-Object System.Drawing.Size(500, 40)
    $lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(220, 230, 245)
    $dlg.Controls.Add($lblStatus)

    $btnCancel = New-Object System.Windows.Forms.Button
    $btnCancel.Text = "Cancel"
    $btnCancel.Location = New-Object System.Drawing.Point(20, 386)
    $btnCancel.Size = New-Object System.Drawing.Size(100, 30)
    $btnCancel.BackColor = [System.Drawing.Color]::FromArgb(50, 55, 65)
    $btnCancel.ForeColor = [System.Drawing.Color]::White
    $btnCancel.FlatStyle = "Flat"
    $dlg.Controls.Add($btnCancel)

    $machineId = Get-MachineId
    Log "  Machine ID: $($machineId.Substring(0, [Math]::Min(16, $machineId.Length)))..."

    $script:ActivationKey = $null

    $btnActivate.Add_Click({
        $key = $txtKey.Text.Trim().ToUpper()
        if (-not $key) { $lblStatus.Text = "Please enter a license key."; return }
        $lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(220, 230, 245)
        $lblStatus.Text = "Validating with license server..."
        $btnActivate.Enabled = $false
        try {
            $body = @{ license_key = $key; machine_id = $machineId; machine_label = $env:COMPUTERNAME } | ConvertTo-Json
            $r = Invoke-RestMethod -Uri "$LicenseServer/api/license/activate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 30
            $script:ActivationKey = $key
            $key | Out-File -FilePath $LicenseFile -Encoding ascii
            $lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(80, 220, 130)
            $lblStatus.Text = "Activated! Status: $($r.license.status). Click Cancel to close and the installer will continue."
            $dlg.DialogResult = "OK"
            $dlg.Close()
        } catch {
            $msg = $_.Exception.Message
            try { $msg = ($_.ErrorDetails.Message | ConvertFrom-Json).detail } catch {}
            $lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(240, 110, 110)
            $lblStatus.Text = "Activation failed: $msg"
        }
        $btnActivate.Enabled = $true
    })

    $btnTrial.Add_Click({
        $email = $txtEmail.Text.Trim()
        if ($email -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') { $lblStatus.Text = "Please enter a valid email."; return }
        $btnTrial.Enabled = $false
        $lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(220, 230, 245)
        $lblStatus.Text = "Requesting trial license..."
        try {
            $body = @{ email = $email; machine_id = $machineId } | ConvertTo-Json
            $r = Invoke-RestMethod -Uri "$LicenseServer/api/license/start-trial" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 30
            $key = $r.license_key
            # Auto-bind to this machine
            $body2 = @{ license_key = $key; machine_id = $machineId; machine_label = $env:COMPUTERNAME } | ConvertTo-Json
            Invoke-RestMethod -Uri "$LicenseServer/api/license/activate" -Method Post -Body $body2 -ContentType "application/json" -TimeoutSec 30 | Out-Null
            $script:ActivationKey = $key
            $key | Out-File -FilePath $LicenseFile -Encoding ascii
            $lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(80, 220, 130)
            $lblStatus.Text = "Trial activated! Your key: $key  (saved). Closing..."
            Start-Sleep -Milliseconds 1500
            $dlg.DialogResult = "OK"
            $dlg.Close()
        } catch {
            $msg = $_.Exception.Message
            try { $msg = ($_.ErrorDetails.Message | ConvertFrom-Json).detail } catch {}
            $lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(240, 110, 110)
            $lblStatus.Text = "Trial failed: $msg"
        }
        $btnTrial.Enabled = $true
    })

    $btnBuy.Add_Click({
        # Show a modal with the admin's contact email + instructions, and offer to
        # open the user's default email client with a pre-filled message.
        $msg = if ($Config.admin_contact_message) {
            $Config.admin_contact_message
        } else {
            "Please email the admin to purchase a license. The admin accepts manual payments (crypto / bank transfer / etc.) and will reply with a license key once payment is confirmed."
        }
        $full = "Admin email:  $contactEmail`r`n`r`n$msg`r`n`r`nClick OK to open your email app with a pre-filled message."
        $choice = [System.Windows.Forms.MessageBox]::Show(
            $full,
            "Contact Admin to Buy",
            [System.Windows.Forms.MessageBoxButtons]::OKCancel,
            [System.Windows.Forms.MessageBoxIcon]::Information
        )
        if ($choice -eq [System.Windows.Forms.DialogResult]::OK) {
            $subject = "License Purchase Request - $($Config.product_name)"
            $emailBody = "Hello,`r`n`r`nI would like to purchase a license for $($Config.product_name).`r`n`r`nMy details:`r`n  Name:`r`n  Company (optional):`r`n  Preferred payment method (crypto / bank / etc.):`r`n  PC name: $($env:COMPUTERNAME)`r`n`r`nPlease reply with payment instructions.`r`n`r`nThank you."
            # mailto: URL encoding
            Add-Type -AssemblyName System.Web
            $mailto = "mailto:$contactEmail?subject=" + [System.Web.HttpUtility]::UrlEncode($subject) + "&body=" + [System.Web.HttpUtility]::UrlEncode($emailBody)
            try { Start-Process $mailto } catch {
                [System.Windows.Forms.MessageBox]::Show("Could not open your email app. Please manually email:`r`n`r`n$contactEmail", "Email", "OK", "Information") | Out-Null
            }
            $lblStatus.Text = "Email opened. After admin replies with your key, paste it above and click Activate."
        } else {
            $lblStatus.Text = "Once you receive your license key from the admin, paste it above and click Activate."
        }
    })

    $btnCancel.Add_Click({ $dlg.DialogResult = "Cancel"; $dlg.Close() })

    $result = $dlg.ShowDialog($form)
    return ($script:ActivationKey -ne $null)
}

function Invoke-LicenseActivation {
    # If we have a saved license from previous run AND not disabled, validate
    if ((Test-Path $LicenseFile)) {
        $saved = (Get-Content $LicenseFile -Raw).Trim()
        if ($saved -eq "DISABLED") {
            Set-UI -Status "Licensing disabled -- installing..." -Log "Saved license state: DISABLED"
            return $true
        }
        if ($saved) {
            Set-UI -Status "Re-validating saved license..." -Log "Saved license key found, validating with server"
            try {
                $body = @{ license_key = $saved; machine_id = (Get-MachineId) } | ConvertTo-Json
                $r = Invoke-RestMethod -Uri "$LicenseServer/api/license/validate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 20
                if ($r.ok) {
                    Set-UI -Log "  License valid (status: $($r.status))"
                    return $true
                }
                Set-UI -Log "  Saved license invalid: $($r.reason). Asking for a new one."
            } catch {
                Set-UI -Log "  Could not reach license server -- proceeding offline with cached key"
                return $true
            }
        }
    }

    # Fetch live config from server
    Set-UI -Status "Connecting to license server..." -Log "GET $LicenseServer/api/license/config"

    # If no license server is configured -- skip licensing entirely (auto-activate)
    if ([string]::IsNullOrWhiteSpace($LicenseServer)) {
        Set-UI -Log "  No LICENSE_SERVER_URL configured -- skipping license activation."
        return (Invoke-LicensingDisabled)
    }

    try {
        $cfg = Invoke-RestMethod -Uri "$LicenseServer/api/license/config" -Method Get -TimeoutSec 15
    } catch {
        # License server unreachable -- proceed in offline / free mode
        Set-UI -Log "  License server unreachable ($LicenseServer) -- proceeding without license check."
        return (Invoke-LicensingDisabled)
    }
    if (-not $cfg.enabled) {
        return (Invoke-LicensingDisabled)
    }

    return (Show-LicenseDialog -Config $cfg)
}

# --- Show the wizard --------------------------------------------------
try {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]  Showing wizard form..." |
        Out-File -FilePath $BootLog -Append -Encoding utf8
    [void]$form.ShowDialog()
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]  Wizard closed cleanly." |
        Out-File -FilePath $BootLog -Append -Encoding utf8
} catch {
    $errMsg = "FATAL while showing the wizard:`r`n$($_.Exception.Message)`r`n$($_.ScriptStackTrace)"
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]  $errMsg" |
        Out-File -FilePath $BootLog -Append -Encoding utf8
    Write-Host ""
    Write-Host $errMsg -ForegroundColor Red
    Write-Host ""
    Read-Host "Press ENTER to exit"
    exit 1
}
