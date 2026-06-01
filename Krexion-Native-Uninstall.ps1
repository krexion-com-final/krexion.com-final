# ════════════════════════════════════════════════════════════════════════
# Krexion — Native Uninstaller
# ════════════════════════════════════════════════════════════════════════
# Cleanly removes everything installed by Krexion-Native-Install.ps1.
# Run as administrator.
# ════════════════════════════════════════════════════════════════════════

[CmdletBinding()]
param(
    [string]$InstallDir = "C:\Program Files\Krexion",
    [string]$DataDir    = "$env:ProgramData\Krexion",
    [switch]$KeepData
)

$ErrorActionPreference = "Continue"

function Write-Ok($m)   { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Write-Warn($m) { Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Write-Info($m) { Write-Host "  [..]   $m" -ForegroundColor Gray }

# Admin check
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pp = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Run as administrator." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  KREXION UNINSTALLER" -ForegroundColor Magenta
Write-Host ""

$nssm = "$InstallDir\bin\nssm.exe"
if (Test-Path $nssm) {
    foreach ($svc in @("KrexionBackend", "KrexionDatabase")) {
        Write-Info "Stopping + removing service: $svc"
        & $nssm stop $svc 2>&1 | Out-Null
        Start-Sleep -Seconds 2
        & $nssm remove $svc confirm 2>&1 | Out-Null
        Write-Ok "Service $svc removed"
    }
} else {
    # Fallback to sc.exe if NSSM is gone
    foreach ($svc in @("KrexionBackend", "KrexionDatabase")) {
        sc.exe stop $svc 2>&1 | Out-Null
        Start-Sleep -Seconds 2
        sc.exe delete $svc 2>&1 | Out-Null
    }
}

# Kill stray Krexion / mongod processes
Write-Info "Stopping any remaining Krexion / mongod processes..."
Get-Process | Where-Object { $_.Name -match "krexion|mongod" } |
    Stop-Process -Force -ErrorAction SilentlyContinue

# Remove install directory
if (Test-Path $InstallDir) {
    Write-Info "Removing $InstallDir..."
    Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok "Install directory removed"
}

# Remove data directory (unless --KeepData)
if ((Test-Path $DataDir) -and -not $KeepData) {
    Write-Info "Removing $DataDir (license data + DB)..."
    Remove-Item -Path $DataDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok "Data directory removed"
} elseif (Test-Path $DataDir) {
    Write-Warn "Kept $DataDir (per -KeepData flag)"
}

# Remove tray autostart
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" `
                    -Name "Krexion" -ErrorAction SilentlyContinue

# Remove shortcuts
Remove-Item -Path "$env:USERPROFILE\Desktop\Krexion.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Krexion" `
            -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "  Krexion has been removed." -ForegroundColor Green
Write-Host ""
