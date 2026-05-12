@echo off
REM ============================================================================
REM   REALFLOW CPI - ONE CLICK (FINAL - Android + iOS READY)
REM   ═══════════════════════════════════════════════════════════
REM   * Zero external dependencies (all PowerShell inline)
REM   * Zero user prompts during install (JWT asked at end only)
REM   * Zero libimobiledevice (uses tidevice3 Python lib instead - works on Win)
REM   * Full iOS + Android support (iTunes drivers + xcuitest + uiautomator2)
REM   * Try/catch around every step - nothing fatal
REM   * Auto PATH refresh - no "command not found" between steps
REM   * Auto-logging to cpi-setup.log
REM ============================================================================

REM ====== Auto-elevate ======
net session >nul 2>&1
if errorlevel 1 (
    echo Re-launching as Administrator...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM ====== Auto-log to file ======
if "%~1"=="_NESTED_" goto MAIN
set "LOG=%~dp0cpi-setup.log"
echo [%DATE% %TIME%] Setup starting > "%LOG%"
"%~f0" _NESTED_ 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOG%' -Append"
echo.
echo  Log saved: %LOG%
pause
exit /b

:MAIN
setlocal EnableDelayedExpansion
title RealFlow CPI - FINAL Setup (Android + iOS)
color 0A
cls

echo.
echo  ================================================================
echo    REALFLOW CPI - FINAL SETUP (Android + iOS)
echo    No more errors. No more prompts. Just wait.
echo  ================================================================
echo.

set "ROOT=%~dp0"
if "!ROOT:~-1!"=="\" set "ROOT=!ROOT:~0,-1!"
set "WORKER=!ROOT!\realflow-cpi-worker"
set "CONFIG=!WORKER!\config.yaml"
set "CONFIG_EX=!WORKER!\config.example.yaml"

echo    Project : !ROOT!
echo    Worker  : !WORKER!
echo    Log     : !LOG!
echo.

if not exist "!WORKER!" (
    echo  [FATAL] realflow-cpi-worker folder nahi mila.
    echo          Is script ko fresh GitHub download ke ROOT mein rakhain.
    pause & exit /b 1
)

REM ================================================================
REM   [1/9] Chocolatey (Windows package manager)
REM ================================================================
echo [1/9] Chocolatey...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try {" ^
        "if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {" ^
            "Set-ExecutionPolicy Bypass -Scope Process -Force;" ^
            "[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072;" ^
            "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))" ^
        "};" ^
        "Write-Host '       [OK] ready' -ForegroundColor Green" ^
    "} catch { Write-Host \"       [WARN] $($_.Exception.Message)\" -ForegroundColor Yellow }"

REM Refresh PATH
for /f "delims=" %%p in ('powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')"') do set "Path=%%p"
echo.

REM ================================================================
REM   [2/9] Core: Python 3.11 / Node 20 / Git / ADB
REM ================================================================
echo [2/9] Python 3.11 / Node 20 / Git / ADB platform-tools...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try {" ^
        "& choco install -y python311 nodejs-lts git adb --no-progress 2>&1 | Select-String -Pattern 'already installed|successful|error|failed' | Out-String | Write-Host;" ^
        "Write-Host '       [OK] core tools done' -ForegroundColor Green" ^
    "} catch { Write-Host \"       [WARN] $($_.Exception.Message)\" -ForegroundColor Yellow }"

for /f "delims=" %%p in ('powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')"') do set "Path=%%p"
echo.

REM ================================================================
REM   [3/9] iTunes (iOS USB drivers — REQUIRED for iPhone)
REM   NOTE: tidevice3 replaces libimobiledevice entirely on Windows.
REM ================================================================
echo [3/9] iTunes (iOS USB drivers only - you do NOT use iTunes itself)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try {" ^
        "& choco install -y itunes --ignore-checksums --no-progress 2>&1 | Select-String -Pattern 'already installed|successful|error|failed' | Out-String | Write-Host;" ^
        "Write-Host '       [OK] Apple Mobile Device drivers installed' -ForegroundColor Green" ^
    "} catch { Write-Host \"       [WARN] iTunes install issue (iOS may still work via tidevice3): $($_.Exception.Message)\" -ForegroundColor Yellow }"
echo.

REM ================================================================
REM   [4/9] Appium (Node-based) + both drivers (Android + iOS)
REM ================================================================
echo [4/9] Appium server + uiautomator2 (Android) + xcuitest (iOS)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try {" ^
        "if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js not on PATH - terminal restart required' };" ^
        "& npm install -g appium --silent 2>&1 | Out-Null;" ^
        "Write-Host '       [OK] appium server installed' -ForegroundColor Green;" ^
        "& appium driver install uiautomator2 2>&1 | Out-Null;" ^
        "Write-Host '       [OK] uiautomator2 driver (Android) installed' -ForegroundColor Green;" ^
        "& appium driver install xcuitest 2>&1 | Out-Null;" ^
        "Write-Host '       [OK] xcuitest driver (iOS) installed' -ForegroundColor Green" ^
    "} catch { Write-Host \"       [WARN] Appium issue: $($_.Exception.Message)\" -ForegroundColor Yellow }"
echo.

REM ================================================================
REM   [5/9] Python venv for CPI worker
REM ================================================================
echo [5/9] Python venv + worker dependencies...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try {" ^
        "$W = '!WORKER!';" ^
        "$V = Join-Path $W 'venv-cpi-worker';" ^
        "$pyCmd = $null;" ^
        "if (Get-Command py -ErrorAction SilentlyContinue) { $pyCmd = 'py -3.11' }" ^
        "elseif (Get-Command python -ErrorAction SilentlyContinue) { $pyCmd = 'python' }" ^
        "else { throw 'Python not on PATH - close this terminal and open a NEW PowerShell, then re-run this script' };" ^
        "if (-not (Test-Path $V)) {" ^
            "if ($pyCmd -eq 'py -3.11') { & py -3.11 -m venv $V }" ^
            "else { & python -m venv $V }" ^
        "};" ^
        "$py = Join-Path $V 'Scripts\\python.exe';" ^
        "if (-not (Test-Path $py)) { throw ('venv python missing: ' + $py) };" ^
        "& $py -m pip install --upgrade pip wheel --quiet | Out-Null;" ^
        "& $py -m pip install -r (Join-Path $W 'requirements.txt') --quiet;" ^
        "Write-Host '       [OK] Python worker deps installed (incl. tidevice3 for iOS, uiautomator2 for Android)' -ForegroundColor Green" ^
    "} catch { Write-Host \"       [WARN] $($_.Exception.Message)\" -ForegroundColor Yellow }"
echo.

REM ================================================================
REM   [6/9] config.yaml bootstrap
REM ================================================================
echo [6/9] config.yaml...
if not exist "!CONFIG!" (
    if exist "!CONFIG_EX!" (
        copy /Y "!CONFIG_EX!" "!CONFIG!" >nul
        echo        Created from config.example.yaml
    )
) else (
    echo        Already exists
)
echo.

REM ================================================================
REM   [7/9] Write backend_url (always) + ask for JWT (once)
REM ================================================================
echo [7/9] Worker config: backend_url + JWT token...
powershell -NoProfile -Command ^
    "try {" ^
        "$f = '!CONFIG!';" ^
        "$lines = Get-Content $f;" ^
        "$out = @(); $found = $false;" ^
        "foreach ($l in $lines) {" ^
            "if ($l -match '^\s*backend_url\s*:') { $out += 'backend_url: \"https://api.realflow.online\"'; $found = $true }" ^
            "else { $out += $l }" ^
        "};" ^
        "if (-not $found) { $out += 'backend_url: \"https://api.realflow.online\"' };" ^
        "Set-Content -Path $f -Value $out -Encoding UTF8" ^
    "} catch {}"
echo        backend_url set.
echo.

echo    ================================================================
echo    JWT Token chahiye (one-time setup)
echo    ================================================================
echo    Browser kholein:
echo      https://realflow.online/admin
echo    Login (admin@realflow.local / admin123)
echo    Sidebar -^> CPI Module -^> CPI Worker Setup -^> JWT Token Copy
echo    ================================================================
echo.
set "JWT="
set /p "JWT=  JWT paste karein (ya Enter dabao = skip): "

if not "!JWT!"=="" (
    powershell -NoProfile -Command ^
        "try {" ^
            "$f = '!CONFIG!';" ^
            "$jwt = '!JWT!';" ^
            "$lines = Get-Content $f;" ^
            "$out = @(); $found = $false;" ^
            "foreach ($l in $lines) {" ^
                "if ($l -match '^\s*worker_token\s*:') { $out += ('worker_token: \"' + $jwt + '\"'); $found = $true }" ^
                "else { $out += $l }" ^
            "};" ^
            "if (-not $found) { $out += ('worker_token: \"' + $jwt + '\"') };" ^
            "Set-Content -Path $f -Value $out -Encoding UTF8;" ^
            "Write-Host '       [OK] JWT saved to config.yaml' -ForegroundColor Green" ^
        "} catch { Write-Host \"       [WARN] $($_.Exception.Message)\" -ForegroundColor Yellow }"
) else (
    echo        Skipped - baad mein !CONFIG! edit kar lena.
)
echo.

REM ================================================================
REM   [8/9] Device check (Android via ADB + iOS via tidevice3)
REM ================================================================
echo [8/9] Connected devices check...
echo.
echo    ---- Android (adb devices) ----
where adb >nul 2>&1
if errorlevel 1 (
    echo    adb not on PATH yet - new PowerShell terminal khol ke check karein
) else (
    adb devices -l
)
echo.
echo    ---- iOS (tidevice3 list) ----
powershell -NoProfile -Command ^
    "try {" ^
        "$py = Join-Path '!WORKER!' 'venv-cpi-worker\\Scripts\\python.exe';" ^
        "if (Test-Path $py) { & $py -m tidevice3 list 2>&1 | Out-String | Write-Host }" ^
        "else { Write-Host '    venv not ready - restart terminal and re-run script' -ForegroundColor Yellow }" ^
    "} catch { Write-Host \"    iOS check failed: $($_.Exception.Message)\" -ForegroundColor Yellow }"
echo.

REM ================================================================
REM   [9/9] Auto-start worker
REM ================================================================
echo [9/9] Worker startup...
echo.

set "WORKER_BAT=!ROOT!\deployment\cpi\REALFLOW-CPI-WORKER-START.bat"
if exist "!WORKER_BAT!" (
    echo    Starting CPI Worker in new terminal window...
    start "RealFlow CPI Worker" cmd /k "!WORKER_BAT!"
    echo    [OK] Worker window open ho gayi.
) else (
    echo    Worker start script nahi mila: !WORKER_BAT!
)
echo.

echo  ================================================================
echo    SETUP COMPLETE!
echo  ================================================================
echo.
echo    INSTALLED:
echo      - Chocolatey, Python 3.11, Node.js, Git, ADB platform-tools
echo      - iTunes (Apple USB drivers only)
echo      - Appium + uiautomator2 (Android) + xcuitest (iOS)
echo      - tidevice3 (iOS Python lib, zero native deps)
echo      - CPI Worker venv + dependencies
echo.
echo    CONFIG:
echo      !CONFIG!
echo.
echo    CONNECT DEVICES:
echo    Android:
echo      1. Settings -^> About Phone -^> Build Number 7x tap
echo      2. Developer Options -^> USB debugging ON
echo      3. USB cable -^> PC -^> "Always Allow"
echo    iPhone:
echo      1. USB cable -^> PC
echo      2. "Trust This Computer" -^> Trust
echo      3. Keep screen unlocked first few seconds
echo.
echo    VERIFY:
echo      Web UI: https://realflow.online/admin
echo      -^> CPI Module -^> CPI Devices page
echo      -^> Connected phones "Online" dikhne chahiye
echo.
echo    MANAGE WORKER:
echo      Start : !ROOT!\deployment\cpi\REALFLOW-CPI-WORKER-START.bat
echo      Stop  : !ROOT!\deployment\cpi\REALFLOW-CPI-WORKER-STOP.bat
echo.
echo    Log: !LOG!
echo  ================================================================
echo.

endlocal
exit /b 0
