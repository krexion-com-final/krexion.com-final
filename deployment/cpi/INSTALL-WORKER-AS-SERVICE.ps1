# Install RealFlow CPI Worker as Windows Service (auto-start on boot) - ASCII safe

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$ROOT        = (Resolve-Path "$PSScriptRoot\..\..").Path
$WORKER      = Join-Path $ROOT "realflow-cpi-worker"
$VENV_PYTHON = Join-Path $WORKER "venv-cpi-worker\Scripts\python.exe"
$WORKER_PY   = Join-Path $WORKER "worker.py"
$CONFIG_YAML = Join-Path $WORKER "config.yaml"
$SERVICE     = "RealFlowCPIWorker"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "[ERROR] venv not found. Run CPI-ONE-CLICK.bat from project root first." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
if (-not (Test-Path $CONFIG_YAML)) {
    Write-Host "[ERROR] config.yaml missing. Run CPI-ONE-CLICK.bat first." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "Installing NSSM..." -ForegroundColor Cyan
    choco install -y nssm | Out-Null
}

sc.exe stop $SERVICE 2>$null | Out-Null
sc.exe delete $SERVICE 2>$null | Out-Null

Write-Host "Installing $SERVICE service..." -ForegroundColor Cyan
nssm install $SERVICE $VENV_PYTHON $WORKER_PY "--config" $CONFIG_YAML
nssm set $SERVICE AppDirectory $WORKER
nssm set $SERVICE Start SERVICE_AUTO_START
nssm set $SERVICE AppStdout "$WORKER\worker.out.log"
nssm set $SERVICE AppStderr "$WORKER\worker.err.log"
nssm set $SERVICE AppRotateFiles 1
nssm set $SERVICE AppRotateBytes 5242880
nssm set $SERVICE Description "RealFlow CPI Install Worker"

nssm start $SERVICE
Start-Sleep -Seconds 2
Write-Host ""
Write-Host "Status:" -ForegroundColor Cyan
nssm status $SERVICE

Write-Host ""
Write-Host "Logs:" -ForegroundColor Cyan
Write-Host "  stdout: $WORKER\worker.out.log"
Write-Host "  stderr: $WORKER\worker.err.log"
Write-Host ""
Write-Host "Manage: nssm start/stop/restart/remove $SERVICE" -ForegroundColor Yellow
Read-Host "Press Enter to close"
