#Requires -RunAsAdministrator
<#
================================================================================
  Krexion Runner -- Service Install (Post-Config Fix)
================================================================================
  Ye script tab use karo jab aap ne SETUP-WINDOWS-RUNNER.bat chalaya tha aur
  runner register to ho gaya (C:\krexion-runner\ mein config.cmd successfully
  chali) LEKIN Windows Service install fail ho gayi (svc.cmd not recognized).

  Ye script sirf service install karega using NSSM -- baaki kuch nahi chhoona.

  Usage (PowerShell as Administrator):
    .\INSTALL-RUNNER-SERVICE.ps1
    .\INSTALL-RUNNER-SERVICE.ps1 -RunnerDir "C:\krexion-runner" -RunnerName "krexion-windows"
================================================================================
#>

[CmdletBinding()]
param(
    [string]$RunnerDir  = "C:\krexion-runner",
    [string]$RunnerName = "krexion-windows"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step { param($msg) Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }

Write-Step "Sanity checks"
if (-not (Test-Path $RunnerDir)) { throw "Runner dir not found: $RunnerDir" }
$runCmd = Join-Path $RunnerDir "run.cmd"
if (-not (Test-Path $runCmd)) { throw "run.cmd missing in $RunnerDir -- runner not extracted properly" }
if (-not (Test-Path (Join-Path $RunnerDir ".runner"))) {
    throw "$RunnerDir\.runner missing -- runner is not registered with GitHub yet. Run SETUP-WINDOWS-RUNNER.bat first."
}
Write-Ok "Runner dir + registration confirmed"

Write-Step "Ensuring NSSM is installed"
$nssmCmd = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssmCmd) {
    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
        throw "Chocolatey not installed -- run SETUP-WINDOWS-RUNNER.bat first to install base toolchain"
    }
    Write-Host "  Installing NSSM via Chocolatey..."
    choco install nssm -y --no-progress --limit-output 2>&1 | Select-Object -Last 3
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $nssmCmd = Get-Command nssm -ErrorAction SilentlyContinue
    if (-not $nssmCmd) { throw "NSSM install failed" }
}
Write-Ok "NSSM ready at $($nssmCmd.Source)"

$svcName = "actions.runner.$RunnerName"

Write-Step "Cleaning any existing service"
$existing = Get-Service -Name $svcName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Stopping + removing existing '$svcName'..."
    Stop-Service $svcName -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    & nssm remove $svcName confirm 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    Write-Ok "Old service removed"
} else {
    Write-Ok "No existing service (clean install)"
}

$diagDir = Join-Path $RunnerDir "_diag"
if (-not (Test-Path $diagDir)) { New-Item -ItemType Directory -Path $diagDir -Force | Out-Null }

Write-Step "Installing service '$svcName'"
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

# CRITICAL: PATH must prefer Git Bash over WSL so 'shell: bash' works
$gitBash1 = "C:\Program Files\Git\bin"
$gitBash2 = "C:\Program Files\Git\usr\bin"
& nssm set $svcName AppEnvironmentExtra "PATH=$gitBash1;$gitBash2;%PATH%" | Out-Null
Write-Ok "Service configured (with Git Bash PATH priority)"

Write-Step "Starting service"
& nssm start $svcName 2>&1 | Out-Null
Start-Sleep -Seconds 4

$svcStatus = Get-Service -Name $svcName -ErrorAction SilentlyContinue
if ($svcStatus -and $svcStatus.Status -eq "Running") {
    Write-Ok "Service '$svcName' is RUNNING"
} elseif ($svcStatus) {
    Write-Warn "Service installed but status is '$($svcStatus.Status)'"
    Write-Host "  Try: nssm start $svcName"
    Write-Host "  Logs: $diagDir\service-stdout.log + service-stderr.log"
} else {
    throw "Service was not created"
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "  RUNNER SERVICE READY" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Service name : $svcName"
Write-Host "  Runner dir   : $RunnerDir"
Write-Host "  Logs         : $diagDir\service-stdout.log"
Write-Host ""
Write-Host "  Verify at    : https://github.com/krexion-com-final/krexion.com-final/settings/actions/runners"
Write-Host "                 (krexion-windows should show as 'Idle' green dot)"
Write-Host ""
Write-Host "  Restart      : Restart-Service $svcName"
Write-Host "  Stop         : Stop-Service    $svcName"
Write-Host "  Status       : Get-Service     $svcName"
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
