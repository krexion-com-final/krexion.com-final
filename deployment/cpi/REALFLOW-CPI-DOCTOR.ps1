# RealFlow CPI Worker - Doctor (ASCII safe - redirect version)

$ROOT     = (Resolve-Path "$PSScriptRoot\..\..").Path
$WORKER   = Join-Path $ROOT "realflow-cpi-worker"
$VENVDIR  = Join-Path $WORKER "venv-cpi-worker"

Write-Host "RealFlow CPI Worker - Doctor" -ForegroundColor Cyan
Write-Host "---------------------------------"
Write-Host ""

function Check {
    param($label, $script)
    Write-Host ("  - " + $label + "...") -NoNewline
    try {
        $result = & $script
        if ($result -or $LASTEXITCODE -eq 0) {
            Write-Host " OK" -ForegroundColor Green
        } else {
            Write-Host " FAIL" -ForegroundColor Red
        }
    } catch {
        Write-Host (" FAIL (" + $_.Exception.Message + ")") -ForegroundColor Red
    }
}

Check "Python 3.11 available"   { (& py -3.11 --version 2>$null) -match "3\.11" }
Check "ADB on PATH"              { (& adb version 2>$null) -match "Android Debug Bridge" }
Check "Node.js available"        { (& node --version 2>$null) }
Check "Appium installed"         { (& appium --version 2>$null) }
Check "venv exists"              { Test-Path "$VENVDIR\Scripts\python.exe" }
Check "config.yaml exists"       { Test-Path "$WORKER\config.yaml" }
Check "tidevice3 in venv"        { & "$VENVDIR\Scripts\python.exe" -c "import tidevice3" 2>$null; $LASTEXITCODE -eq 0 }

Write-Host ""
Write-Host "Android devices (adb):" -ForegroundColor Cyan
if (Get-Command adb -ErrorAction SilentlyContinue) {
    adb devices -l
} else {
    Write-Host "  adb not on PATH - restart terminal"
}

Write-Host ""
Write-Host "iOS devices (tidevice3):" -ForegroundColor Cyan
if (Test-Path "$VENVDIR\Scripts\python.exe") {
    & "$VENVDIR\Scripts\python.exe" -m tidevice3 list 2>$null
} else {
    Write-Host "  venv not ready"
}

Write-Host ""
Write-Host "Done."
