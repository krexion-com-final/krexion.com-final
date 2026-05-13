# ═══════════════════════════════════════════════════════════════════════
#   RealFlow Setup Engine — WinForms wizard, no command line in user's face
# ═══════════════════════════════════════════════════════════════════════

#Requires -RunAsAdministrator

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = "Stop"
$ProgressPreference     = "SilentlyContinue"

# ─── Paths ─────────────────────────────────────────────────────────────
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BundleDir   = Join-Path $ScriptDir "bundle"
$InstallPath = "C:\realflow"
$RepoUrl     = "https://github.com/ronaldsexedwards40-glitch/dynabook.git"
$Branch      = "main"
$ResumeFile  = Join-Path $ScriptDir ".resume-stage"
$LogFile     = Join-Path $ScriptDir "setup.log"

New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null
"" | Out-File -FilePath $LogFile -Encoding utf8

# ─── Logging helper ────────────────────────────────────────────────────
function Log {
    param([string]$Message)
    $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    "$stamp  $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# ─── Build the wizard form ─────────────────────────────────────────────
$form               = New-Object System.Windows.Forms.Form
$form.Text          = "RealFlow Setup"
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
$titleLabel.Text    = "RealFlow"
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

# Body — status label
$statusLabel        = New-Object System.Windows.Forms.Label
$statusLabel.Text   = "Ready to install RealFlow on this PC."
$statusLabel.Font   = New-Object System.Drawing.Font("Segoe UI", 11)
$statusLabel.Location  = New-Object System.Drawing.Point(20, 100)
$statusLabel.Size      = New-Object System.Drawing.Size(600, 28)
$statusLabel.ForeColor = [System.Drawing.Color]::White
$form.Controls.Add($statusLabel)

# Detail label
$detailLabel        = New-Object System.Windows.Forms.Label
$detailLabel.Text   = "Click INSTALL to begin. The wizard will:`r`n  - Download and install Docker Desktop (if missing)`r`n  - Install Git (if missing)`r`n  - Download RealFlow code`r`n  - Generate secure passwords`r`n  - Build and start the app`r`n  - Open it in your browser"
$detailLabel.Font   = New-Object System.Drawing.Font("Segoe UI", 9)
$detailLabel.Location  = New-Object System.Drawing.Point(20, 134)
$detailLabel.Size      = New-Object System.Drawing.Size(600, 130)
$detailLabel.ForeColor = [System.Drawing.Color]::FromArgb(190, 200, 220)
$form.Controls.Add($detailLabel)

# Progress bar
$progress           = New-Object System.Windows.Forms.ProgressBar
$progress.Location  = New-Object System.Drawing.Point(20, 270)
$progress.Size      = New-Object System.Drawing.Size(595, 22)
$progress.Style     = "Continuous"
$progress.Minimum   = 0
$progress.Maximum   = 100
$progress.Value     = 0
$form.Controls.Add($progress)

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

# INSTALL button — the only thing the user touches
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

# ─── Helper: update UI from the install loop ───────────────────────────
function Set-UI {
    param(
        [object]$Percent  = $null,
        [string]$Status   = $null,
        [string]$Progress = $null,
        [string]$Log      = $null
    )
    if ($Percent -ne $null)  { $progress.Value = [Math]::Min(100, [Math]::Max(0, [int]$Percent)) }
    if ($Status   -ne $null) { $statusLabel.Text = $Status }
    if ($Progress -ne $null) { $progressText.Text = $Progress }
    if ($Log      -ne $null) {
        $logBox.AppendText("$Log`r`n")
        Log $Log
    }
    [System.Windows.Forms.Application]::DoEvents()
}

# ─── The actual install logic, broken into stages ──────────────────────
function Invoke-Stage1-PrepareTools {
    Set-UI -Percent 5 -Status "Step 1 / 6 — Checking required tools..." -Progress "" -Log "Stage 1: prepare tools"

    # ── Git ──
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Set-UI -Percent 8 -Progress "Installing Git..."
        $gitInstaller = Join-Path $BundleDir "Git-Installer.exe"
        if (-not (Test-Path $gitInstaller) -or (Get-Item $gitInstaller).Length -lt 10MB) {
            Set-UI -Progress "Downloading Git (~50 MB)..." -Log "  Downloading Git for Windows"
            Invoke-WebRequest -UseBasicParsing `
                -Uri "https://github.com/git-for-windows/git/releases/download/v2.46.0.windows.1/Git-2.46.0-64-bit.exe" `
                -OutFile $gitInstaller
        } else {
            Set-UI -Log "  Using cached Git installer"
        }
        Set-UI -Progress "Installing Git (silent)..."
        Start-Process -FilePath $gitInstaller -ArgumentList "/VERYSILENT", "/NORESTART", "/NOCANCEL", "/SP-", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS" -Wait
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    }
    Set-UI -Log "  Git: OK ($((git --version) 2>$null))"

    # ── Docker Desktop ──
    Set-UI -Percent 15 -Progress "Checking Docker Desktop..."
    $dockerInstalled = (Get-Command docker -ErrorAction SilentlyContinue) -ne $null
    if (-not $dockerInstalled) {
        Set-UI -Percent 18 -Progress "Downloading Docker Desktop (~520 MB, slow internet may take 10-20 min)..." -Log "  Docker Desktop missing — downloading"
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

        # Save resume marker — we need a reboot for WSL2 / Hyper-V to come online
        "stage1_done" | Out-File -FilePath $ResumeFile -Encoding ascii
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

        $result = [System.Windows.Forms.MessageBox]::Show(
            "Docker Desktop installed successfully.`r`n`r`nA RESTART is required so Windows can enable WSL2 / Hyper-V.`r`n`r`nClick OK to restart now. After restart, just double-click  Install.bat  again — the wizard will continue automatically.",
            "Restart Required",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        )
        Restart-Computer -Force
        exit
    }
    Set-UI -Log "  Docker: $((docker --version) 2>$null)"

    # ── Make sure Docker daemon is up ──
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
    Set-UI -Percent 30 -Status "Step 2 / 6 — Tuning WSL memory limit..." -Progress "Writing .wslconfig"

    $wslcfg = Join-Path $env:USERPROFILE ".wslconfig"
    $totalRamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 0)

    if ($totalRamGB -le 10) {
        # 8 GB-class laptops: cap WSL at 5 GB
        $cap = "5GB"
    } elseif ($totalRamGB -le 16) {
        $cap = "10GB"
    } else {
        $cap = "16GB"
    }

    @"
[wsl2]
memory=$cap
processors=4
swap=4GB
localhostForwarding=true

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
"@ | Out-File -FilePath $wslcfg -Encoding ascii

    Set-UI -Log "  Wrote $wslcfg (memory=$cap on a ${totalRamGB} GB system)"
    wsl --shutdown 2>$null | Out-Null
    Start-Sleep 3
}

function Invoke-Stage3-FetchCode {
    Set-UI -Percent 40 -Status "Step 3 / 6 — Downloading RealFlow code..." -Progress "git clone $RepoUrl"

    if (Test-Path (Join-Path $InstallPath ".git")) {
        Set-UI -Log "  Existing install found — pulling latest"
        Push-Location $InstallPath
        git fetch origin 2>$null
        git checkout $Branch 2>$null
        git pull --ff-only origin $Branch 2>$null
        Pop-Location
    } else {
        if (Test-Path $InstallPath) {
            Remove-Item -Recurse -Force $InstallPath
        }
        git clone --branch $Branch $RepoUrl $InstallPath 2>&1 | Out-Null
        Set-UI -Log "  Cloned to $InstallPath"
    }
}

function Invoke-Stage4-GenerateEnv {
    Set-UI -Percent 50 -Status "Step 4 / 6 — Generating secure passwords..." -Progress "Writing .env"

    $envFile = Join-Path $InstallPath ".env"
    if (Test-Path $envFile) {
        Set-UI -Log "  .env already exists — keeping existing secrets"
        return
    }

    function Gen { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_}) }
    $jwt   = Gen
    $admin = Gen
    $post  = Gen

    @"
# Generated by RealFlow Setup on $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))
DB_NAME=realflow
JWT_SECRET_KEY=$jwt
ADMIN_EMAIL=admin@realflow.local
ADMIN_PASSWORD=$admin
POSTBACK_TOKEN=$post
APP_URL=http://localhost:3000
PUBLIC_BASE_URL=http://localhost:3000
CORS_ORIGINS=*

# Optional
RESEND_API_KEY=
RESEND_FROM=no-reply@realflow.local
GOOGLE_SHEETS_SA_PATH=
GOOGLE_SHEETS_SA_JSON=
TUNNEL_TOKEN=
"@ | Out-File -FilePath $envFile -Encoding ascii

    Set-UI -Log "  Generated .env with admin password: $admin"
    $script:GeneratedAdminPassword = $admin
}

function Invoke-Stage5-BuildAndStart {
    Set-UI -Percent 60 -Status "Step 5 / 6 — Building Docker images (5-10 min first time)..." -Progress "docker compose build"

    Push-Location $InstallPath

    # Auto-detect low-RAM
    $totalRamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 0)
    $composeArgs = @("-f", "docker-compose.yml")
    if ($totalRamGB -le 10 -and (Test-Path "docker-compose.lowram.yml")) {
        Set-UI -Log "  Low-RAM mode (${totalRamGB} GB) — adding docker-compose.lowram.yml override"
        $composeArgs += @("-f", "docker-compose.lowram.yml")
    }

    Set-UI -Log "  docker compose $($composeArgs -join ' ') build"
    & docker compose @composeArgs build 2>&1 | Tee-Object -FilePath $LogFile -Append | Out-Null

    Set-UI -Percent 80 -Progress "Starting containers..." -Log "  docker compose up -d"
    & docker compose @composeArgs up -d 2>&1 | Tee-Object -FilePath $LogFile -Append | Out-Null

    Pop-Location
}

function Invoke-Stage6-WaitAndOpen {
    Set-UI -Percent 88 -Status "Step 6 / 6 — Waiting for services to start..." -Progress "Health check"

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
    $shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "RealFlow.url"
    "[InternetShortcut]`r`nURL=http://localhost:3000`r`nIconIndex=0" | Out-File -FilePath $shortcut -Encoding ascii
    Set-UI -Log "  Created Desktop shortcut: RealFlow.url"

    Set-UI -Percent 100 -Progress "Install complete!" -Status "✓ Done — RealFlow is running."

    # Read admin password from .env
    $envFile = Join-Path $InstallPath ".env"
    $adminEmail = ((Get-Content $envFile | Where-Object { $_ -match '^ADMIN_EMAIL=' }) -replace '^ADMIN_EMAIL=', '').Trim('"')
    $adminPass  = ((Get-Content $envFile | Where-Object { $_ -match '^ADMIN_PASSWORD=' }) -replace '^ADMIN_PASSWORD=', '').Trim('"')

    # Switch UI to "Done" mode
    $installBtn.Text = "OPEN REALFLOW"
    $installBtn.BackColor = [System.Drawing.Color]::FromArgb(60, 180, 90)
    $cancelBtn.Text = "Finish"

    $titleLabel.Text = "Installation Complete!"
    $subtitleLabel.Text = "Click OPEN REALFLOW to launch your dashboard."
    $detailLabel.Text = "URL:          http://localhost:3000`r`nAdmin login:  http://localhost:3000/admin-login`r`n  Email:      $adminEmail`r`n  Password:   $adminPass`r`n`r`nIMPORTANT: Save the password above — it is also stored in:`r`n   $envFile`r`n`r`nA Desktop shortcut `"RealFlow.url`" has been created."
    $detailLabel.ForeColor = [System.Drawing.Color]::FromArgb(220, 240, 255)

    # Re-wire the button
    $installBtn.Add_Click({
        Start-Process "http://localhost:3000"
    })

    # Clean resume marker
    if (Test-Path $ResumeFile) { Remove-Item -Force $ResumeFile }
}

# ─── Main install flow (called when user clicks INSTALL) ───────────────
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
        Set-UI -Status "✗ Install failed." -Progress "" -Log "ERROR: $err"
        [System.Windows.Forms.MessageBox]::Show(
            "Installation failed:`r`n`r`n$err`r`n`r`nFull log: $LogFile`r`n`r`nMost common fix: open Docker Desktop manually, wait for it to be ready, then re-run this installer.",
            "RealFlow Setup — Error",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        )
        $installBtn.Enabled = $true
        $cancelBtn.Enabled  = $true
    }
}

# ─── If we are resuming after reboot, auto-start the install ──────────
if (Test-Path $ResumeFile) {
    $form.Add_Shown({ Start-Install })
} else {
    $installBtn.Add_Click({ Start-Install })
}

# ─── Show the wizard ──────────────────────────────────────────────────
[void]$form.ShowDialog()
