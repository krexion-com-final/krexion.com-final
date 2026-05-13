@echo off
REM ──────────────────────────────────────────────────────────────────
REM  RealFlow — RE-TUNE for current hardware
REM
REM  Run this BAT file any time after install to:
REM    1. Re-detect your PC's RAM + CPU cores
REM    2. Re-write %USERPROFILE%\.wslconfig with optimal values
REM    3. Re-pick the right docker-compose override
REM    4. Restart the RealFlow stack with the new tuning
REM
REM  Useful when:
REM    - You added more RAM
REM    - You moved RealFlow to a different / faster PC
REM    - RUT is hitting OOM and you want to drop a tier
REM    - You want to push more concurrency on a powerful machine
REM ──────────────────────────────────────────────────────────────────

setlocal
cd /d %~dp0

echo.
echo ============================================================
echo   RealFlow Hardware Re-Tune
echo ============================================================
echo.

REM Self-elevate if not admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  Requesting Administrator rights...
    powershell -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)

REM Step 1 — show detected profile
echo  Step 1 / 4 -- Detecting hardware...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\detect-hardware.ps1"
if errorlevel 1 (
    echo  ERROR: scripts\detect-hardware.ps1 not found or failed.
    pause
    exit /b 1
)

echo.
echo  Step 2 / 4 -- Writing new .wslconfig...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    ". '%~dp0scripts\detect-hardware.ps1'; ^
     $p = Get-RealFlowProfile; ^
     $wslcfg = Join-Path $env:USERPROFILE '.wslconfig'; ^
     @\"`n[wsl2]`nmemory=$($p.WSLMemory)`nprocessors=$($p.WSLProcessors)`nswap=4GB`nlocalhostForwarding=true`n`n[experimental]`nautoMemoryReclaim=gradual`nsparseVhd=true`n\"@ ^
     | Out-File -FilePath $wslcfg -Encoding ascii; ^
     Write-Host \"  Wrote $wslcfg (memory=$($p.WSLMemory), processors=$($p.WSLProcessors))\""

echo.
echo  Step 3 / 4 -- Shutting WSL down so new memory cap takes effect...
wsl --shutdown 2>nul

echo.
echo  Step 4 / 4 -- Restarting RealFlow with the new profile...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    ". '%~dp0scripts\detect-hardware.ps1'; ^
     $p = Get-RealFlowProfile; ^
     Push-Location '%~dp0'; ^
     $args = @('-f','docker-compose.yml'); ^
     if (Test-Path $p.ComposeOverride) { $args += @('-f', $p.ComposeOverride) }; ^
     Write-Host \"  docker compose $($args -join ' ') down\"; ^
     & docker compose @args down; ^
     Write-Host \"  docker compose $($args -join ' ') up -d\"; ^
     & docker compose @args up -d; ^
     Pop-Location"

echo.
echo ============================================================
echo   Re-tune complete.
echo   Open http://localhost:3000 once Docker reports healthy.
echo ============================================================
echo.
pause
endlocal
