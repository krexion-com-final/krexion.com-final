#Requires -RunAsAdministrator
<#
================================================================================
  Krexion Windows Self-Hosted Runner -- One-Click Setup
================================================================================
  Aapki apni Windows PC pe permanent GitHub Actions runner install karta hai.
  Iske baad har `backend/VERSION` bump par aap ki PC automatically:
    - Krexion-Setup-<ver>.exe   (Native Inno-Setup installer)
    - Krexion-Desktop-Setup-<ver>.exe   (Electron auto-update installer)
  build karke GitHub Release + krexion.com CDN par publish kar deti hai.
  ZERO GitHub Actions Windows minutes consume hote hain.

  Usage (PowerShell as Administrator):
    .\SETUP-WINDOWS-RUNNER.ps1 -GithubPAT "ghp_xxxxx"

  Ya (agar aap ke paas sirf registration token hai):
    .\SETUP-WINDOWS-RUNNER.ps1 -RegistrationToken "AAAAAA..."

  Optional switches:
    -RunnerDir  "C:\krexion-runner"       (default install location)
    -RunnerName "krexion-windows"         (default runner name)
    -SkipTools                            (skip Python/Node/Yarn/Inno/7z install)
    -Uninstall                            (remove runner + service cleanly)

  Repo: krexion-com-final/krexion.com-final
================================================================================
#>

[CmdletBinding()]
param(
    [string]$GithubPAT = "",
    [string]$RegistrationToken = "",
    [string]$RunnerDir = "C:\krexion-runner",
    [string]$RunnerName = "krexion-windows",
    [switch]$SkipTools,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$repo = "krexion-com-final/krexion.com-final"
$labels = "self-hosted,windows,krexion-windows,X64"

function Write-Step { param($msg) Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "  [ERR] $msg" -ForegroundColor Red }

# --------------------------------------------------------------------
# UNINSTALL PATH
# --------------------------------------------------------------------
if ($Uninstall) {
    Write-Step "Uninstall requested"
    if (Test-Path "$RunnerDir\svc.sh") {
        Push-Location $RunnerDir
        try {
            Write-Host "  Stopping runner service..."
            .\svc.sh stop 2>&1 | Out-Null
            .\svc.sh uninstall 2>&1 | Out-Null
        } catch { Write-Warn "svc.sh not fully clean, continuing" }
        Pop-Location
    }
    # Try config.cmd remove if credentials still exist
    if (Test-Path "$RunnerDir\config.cmd") {
        $tokenForRemove = $RegistrationToken
        if (-not $tokenForRemove -and $GithubPAT) {
            try {
                $resp = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/actions/runners/remove-token" `
                    -Method Post -Headers @{ Authorization = "token $GithubPAT"; "User-Agent" = "krexion-runner-setup" }
                $tokenForRemove = $resp.token
            } catch { Write-Warn "Could not fetch remove-token: $($_.Exception.Message)" }
        }
        if ($tokenForRemove) {
            Push-Location $RunnerDir
            try { & .\config.cmd remove --token $tokenForRemove 2>&1 | Out-Null } catch { }
            Pop-Location
        }
    }
    # Stop + delete Windows service directly (fallback)
    Get-Service -Name "actions.runner.*" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  Stopping service: $($_.Name)"
        Stop-Service $_.Name -Force -ErrorAction SilentlyContinue
        sc.exe delete $_.Name | Out-Null
    }
    if (Test-Path $RunnerDir) {
        Write-Host "  Removing $RunnerDir ..."
        Remove-Item -Recurse -Force $RunnerDir -ErrorAction SilentlyContinue
    }
    Write-Ok "Runner removed cleanly."
    exit 0
}

# --------------------------------------------------------------------
# 0. Sanity checks
# --------------------------------------------------------------------
Write-Step "Environment checks"
$osVer = [System.Environment]::OSVersion.Version
Write-Ok "Windows $($osVer.Major).$($osVer.Minor) build $($osVer.Build)"
if ($osVer.Major -lt 10) { throw "Windows 10 or 11 required." }

if (-not $GithubPAT -and -not $RegistrationToken) {
    Write-Err "Either -GithubPAT or -RegistrationToken required."
    Write-Host ""
    Write-Host "Get a PAT: https://github.com/settings/tokens/new"
    Write-Host "  Required scopes: repo, workflow"
    Write-Host ""
    Write-Host "Or get a registration token manually from:"
    Write-Host "  https://github.com/$repo/settings/actions/runners/new"
    exit 1
}

# --------------------------------------------------------------------
# 1. Install required build tools (Chocolatey + Python + Node + Yarn + Inno + 7z)
# --------------------------------------------------------------------
if (-not $SkipTools) {
    Write-Step "Installing build toolchain (Chocolatey, Python 3.11, Node 20, Yarn, Inno Setup, 7-Zip, Git)"

    # Chocolatey
    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Host "  Installing Chocolatey..."
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        # Refresh PATH so choco is visible in current session
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }
    Write-Ok "Chocolatey ready"

    $tools = @(
        @{ name = "python311"; cmd = "python"; args = "--version" },
        @{ name = "nodejs-lts";  cmd = "node";   args = "--version" },
        @{ name = "yarn";        cmd = "yarn";   args = "--version" },
        @{ name = "innosetup";   cmd = $null;    args = $null },
        @{ name = "7zip";        cmd = "7z";     args = $null },
        @{ name = "git";         cmd = "git";    args = "--version" },
        @{ name = "nssm";        cmd = "nssm";   args = $null },
        @{ name = "pwsh";        cmd = "pwsh";   args = "--version" }
    )
    foreach ($t in $tools) {
        Write-Host "  Installing $($t.name)..."
        choco install $t.name -y --no-progress --limit-output 2>&1 | Where-Object { $_ -notmatch "^$" } | Select-Object -Last 3
    }
    # Refresh PATH again after installs
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Ok "Build toolchain installed"
} else {
    Write-Warn "Skipping tool installation (-SkipTools)"
}

# --------------------------------------------------------------------
# 2. Get registration token if only PAT was provided
# --------------------------------------------------------------------
if (-not $RegistrationToken) {
    Write-Step "Fetching one-shot runner registration token via PAT"
    try {
        $resp = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/actions/runners/registration-token" `
            -Method Post -Headers @{ Authorization = "token $GithubPAT"; "User-Agent" = "krexion-runner-setup"; Accept = "application/vnd.github+json" }
        $RegistrationToken = $resp.token
        Write-Ok "Registration token obtained (expires $($resp.expires_at))"
    } catch {
        Write-Err "Failed to fetch registration token: $($_.Exception.Message)"
        Write-Host "  Check: PAT valid? Has 'repo' + 'workflow' scope? Repo access granted?"
        exit 1
    }
}

# --------------------------------------------------------------------
# 3. Download + extract GitHub Actions runner
# --------------------------------------------------------------------
Write-Step "Downloading GitHub Actions runner (latest)"
$latest = Invoke-RestMethod "https://api.github.com/repos/actions/runner/releases/latest" `
    -Headers @{ "User-Agent" = "krexion-runner-setup" }
$asset = $latest.assets | Where-Object { $_.name -match "actions-runner-win-x64-.*\.zip$" } | Select-Object -First 1
if (-not $asset) { throw "Could not find win-x64 runner asset in latest release" }
$runnerZip = Join-Path $env:TEMP $asset.name
Write-Host "  Version : $($latest.tag_name)"
Write-Host "  Asset   : $($asset.name) ($([math]::Round($asset.size/1MB,1)) MB)"
Write-Host "  Target  : $RunnerDir"

if (Test-Path $RunnerDir) {
    # Stop existing service if reinstalling
    Get-Service -Name "actions.runner.*" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  Stopping existing service: $($_.Name)"
        Stop-Service $_.Name -Force -ErrorAction SilentlyContinue
        sc.exe delete $_.Name | Out-Null
    }
    Write-Host "  Cleaning existing $RunnerDir ..."
    Remove-Item -Recurse -Force $RunnerDir -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $RunnerDir -Force | Out-Null

Write-Host "  Downloading..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $runnerZip -UseBasicParsing
Write-Host "  Extracting..."
Expand-Archive -Path $runnerZip -DestinationPath $RunnerDir -Force
Remove-Item $runnerZip -Force
Write-Ok "Runner binaries extracted"

# --------------------------------------------------------------------
# 4. Configure runner (unattended, replace if same name exists)
# --------------------------------------------------------------------
Write-Step "Registering runner with GitHub"
Push-Location $RunnerDir
try {
    $configArgs = @(
        "--url", "https://github.com/$repo",
        "--token", $RegistrationToken,
        "--name", $RunnerName,
        "--labels", $labels,
        "--work", "_work",
        "--unattended",
        "--replace"
    )
    & .\config.cmd @configArgs
    if ($LASTEXITCODE -ne 0) { throw "config.cmd returned exit code $LASTEXITCODE" }
    Write-Ok "Runner registered as '$RunnerName' with labels [$labels]"
} finally {
    Pop-Location
}

# --------------------------------------------------------------------
# 5. Install as Windows Service (auto-start on boot) -- via NSSM
# --------------------------------------------------------------------
# Modern actions-runner (v2.315+) removed svc.cmd on Windows. Cleanest
# cross-version fix: use NSSM (Non-Sucking Service Manager) to wrap
# run.cmd as a proper Windows service (auto-restart, log rotation,
# correct working directory). NSSM installs via choco in ~10 sec.
# --------------------------------------------------------------------
Write-Step "Installing runner as Windows Service (via NSSM)"

# CRITICAL: Set machine-wide PowerShell execution policy to RemoteSigned.
# The runner service runs under LocalSystem where the default policy is
# Restricted -- this blocks EVERY action that ships a .ps1 script
# (actions/setup-python@v5's setup.ps1, actions/setup-node@v4, etc.)
# with "cannot be loaded because running scripts is disabled".
# RemoteSigned is the recommended standard for build machines: local
# scripts run freely, downloaded scripts need a signature.
try {
    Set-ExecutionPolicy -Scope LocalMachine -ExecutionPolicy RemoteSigned -Force -ErrorAction Stop
    Write-Ok "LocalMachine PowerShell execution policy set to RemoteSigned"
} catch {
    Write-Warn "Could not set execution policy: $($_.Exception.Message) -- may need manual: Set-ExecutionPolicy -Scope LocalMachine RemoteSigned -Force"
}

$nssmCmd = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssmCmd) {
    Write-Host "  Installing NSSM via Chocolatey..."
    choco install nssm -y --no-progress --limit-output 2>&1 | Select-Object -Last 3
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $nssmCmd = Get-Command nssm -ErrorAction SilentlyContinue
    if (-not $nssmCmd) { throw "NSSM install failed -- cannot proceed" }
}
Write-Ok "NSSM ready at $($nssmCmd.Source)"

$svcName = "actions.runner.$RunnerName"
$runCmd = Join-Path $RunnerDir "run.cmd"
if (-not (Test-Path $runCmd)) { throw "run.cmd missing in $RunnerDir" }

$existing = Get-Service -Name $svcName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Removing existing service '$svcName'..."
    Stop-Service $svcName -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    & nssm remove $svcName confirm 2>&1 | Out-Null
    Start-Sleep -Seconds 2
}

$diagDir = Join-Path $RunnerDir "_diag"
if (-not (Test-Path $diagDir)) { New-Item -ItemType Directory -Path $diagDir -Force | Out-Null }

Write-Host "  Installing service '$svcName' wrapping run.cmd..."
& nssm install $svcName $runCmd
if ($LASTEXITCODE -ne 0) { throw "nssm install returned $LASTEXITCODE" }

& nssm set $svcName AppDirectory $RunnerDir                                | Out-Null
& nssm set $svcName Start SERVICE_AUTO_START                               | Out-Null
& nssm set $svcName DisplayName "GitHub Actions Runner ($RunnerName)"      | Out-Null
& nssm set $svcName Description "Krexion self-hosted GitHub Actions runner"| Out-Null
& nssm set $svcName AppStdout (Join-Path $diagDir "service-stdout.log")    | Out-Null
& nssm set $svcName AppStderr (Join-Path $diagDir "service-stderr.log")    | Out-Null
& nssm set $svcName AppRotateFiles 1                                       | Out-Null
& nssm set $svcName AppRotateOnline 1                                      | Out-Null
& nssm set $svcName AppRotateBytes 10485760                                | Out-Null
& nssm set $svcName AppExit Default Restart                                | Out-Null
& nssm set $svcName AppRestartDelay 5000                                   | Out-Null

# CRITICAL: Prepend Git Bash to service PATH so 'shell: bash' in GitHub
# workflows resolves to Git Bash (C:\Program Files\Git\usr\bin\bash.exe)
# and NOT to Windows System32 WSL launcher (which fails with error
# 'Bash/WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED' when the runner service runs
# under LocalSystem/NetworkService account). Without this, EVERY workflow
# step declaring 'shell: bash' fails immediately on step start.
$gitBash1 = "C:\Program Files\Git\bin"
$gitBash2 = "C:\Program Files\Git\usr\bin"
$envPath = "PATH=$gitBash1;$gitBash2;%PATH%"
& nssm set $svcName AppEnvironmentExtra $envPath                           | Out-Null
Write-Ok "Service PATH configured to prefer Git Bash over WSL"

Write-Host "  Starting service..."
& nssm start $svcName 2>&1 | Out-Null
Start-Sleep -Seconds 3

$svcStatus = Get-Service -Name $svcName -ErrorAction SilentlyContinue
if ($svcStatus -and $svcStatus.Status -eq "Running") {
    Write-Ok "Windows service '$svcName' installed and running"
} elseif ($svcStatus) {
    Write-Warn "Service installed but status is '$($svcStatus.Status)' -- check logs at $diagDir"
    Write-Host "  Try: nssm start $svcName"
} else {
    throw "Service '$svcName' not created -- check nssm errors above"
}

# --------------------------------------------------------------------
# 6. Verify runner is online
# --------------------------------------------------------------------
Write-Step "Verifying runner is online with GitHub"
Start-Sleep -Seconds 5
if ($GithubPAT) {
    try {
        $runners = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/actions/runners" `
            -Headers @{ Authorization = "token $GithubPAT"; "User-Agent" = "krexion-runner-setup" }
        $me = $runners.runners | Where-Object { $_.name -eq $RunnerName }
        if ($me) {
            Write-Ok "GitHub sees runner '$($me.name)' status=$($me.status) busy=$($me.busy)"
        } else {
            Write-Warn "Runner not yet visible in API -- may take up to 30s to propagate. Check https://github.com/$repo/settings/actions/runners"
        }
    } catch { Write-Warn "API check failed: $($_.Exception.Message)" }
}

$svc = Get-Service -Name "actions.runner.*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($svc) { Write-Ok "Local service '$($svc.Name)' status=$($svc.Status)" }

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "  KREXION WINDOWS RUNNER READY" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Runner name  : $RunnerName"
Write-Host "  Labels       : $labels"
Write-Host "  Install path : $RunnerDir"
Write-Host "  Repo         : https://github.com/$repo"
Write-Host ""
Write-Host '  Har "backend/VERSION" bump par ye PC automatically build karegi:'
Write-Host "    - Krexion-Setup-<ver>.exe          (native installer)"
Write-Host "    - Krexion-Desktop-Setup-<ver>.exe  (electron installer)"
Write-Host ""
Write-Host "  Verify: https://github.com/$repo/settings/actions/runners"
Write-Host '  Logs  : Check C:\krexion-runner\_diag\Runner_*.log'
Write-Host ""
Write-Host "  Restart : Restart-Service $($svc.Name)"
Write-Host "  Stop    : Stop-Service    $($svc.Name)"
Write-Host "  Remove  : .\SETUP-WINDOWS-RUNNER.ps1 -Uninstall -GithubPAT 'ghp_xxx'"
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
