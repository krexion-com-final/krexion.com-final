@echo off
setlocal EnableDelayedExpansion
title Krexion - Admin Password Reset
color 0E

REM ====================================================================
REM   Krexion ONE-CLICK ADMIN PASSWORD RESET
REM   ──────────────────────────────────────
REM   Ye script .env file mein ADMIN_PASSWORD ko reset karega aur
REM   backend container ko restart karega taake naya password load ho.
REM
REM   Default reset to: admin123
REM ====================================================================

cls
echo.
echo  ============================================================
echo    Krexion - ADMIN PASSWORD RESET
echo  ============================================================
echo.

REM Auto-detect: agar script kisi Krexion root mein hai, wahin chalega
REM Otherwise hardcoded path use karega
if exist "%~dp0docker-compose.yml" (
    set "ROOT=%~dp0"
) else (
    set "ROOT=C:\Krexion"
)

REM Trailing slash hatao
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo    Project root: %ROOT%
echo.

if not exist "%ROOT%\docker-compose.yml" (
    echo  [ERROR] docker-compose.yml nahi mila is path par:
    echo          %ROOT%
    echo.
    pause
    exit /b 1
)

set "ENV_FILE=%ROOT%\.env"

REM ───── Check Docker ─────
docker info >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Docker Desktop chalu nahi hai!
    echo          Pehle Docker Desktop start karein, phir ye script chalayein.
    echo.
    pause
    exit /b 1
)

REM ───── Backup .env ─────
if exist "%ENV_FILE%" (
    echo [1/4] .env file ka backup bana raha hun...
    for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
    set "TS=!dt:~0,8!-!dt:~8,6!"
    copy /Y "%ENV_FILE%" "%ENV_FILE%.bak-!TS!" >nul
    echo        OK - Backup: .env.bak-!TS!
) else (
    echo [1/4] .env file nahi mili - nayi banayi ja rahi hai...
    type nul > "%ENV_FILE%"
)
echo.

REM ───── Update .env ─────
echo [2/4] ADMIN_PASSWORD reset kar raha hun to: admin123
echo        ADMIN_EMAIL: admin@krexion.local

REM Powershell istemal karo .env ko safely update karne ke liye
powershell -NoProfile -Command ^
    "$f='%ENV_FILE%';" ^
    "$lines = if (Test-Path $f) { Get-Content $f } else { @() };" ^
    "$out = @();" ^
    "$hasEmail=$false; $hasPass=$false;" ^
    "foreach($l in $lines) {" ^
        "if ($l -match '^\s*ADMIN_EMAIL\s*=') { $out += 'ADMIN_EMAIL=admin@krexion.local'; $hasEmail=$true }" ^
        "elseif ($l -match '^\s*ADMIN_PASSWORD\s*=') { $out += 'ADMIN_PASSWORD=admin123'; $hasPass=$true }" ^
        "else { $out += $l }" ^
    "};" ^
    "if (-not $hasEmail) { $out += 'ADMIN_EMAIL=admin@krexion.local' };" ^
    "if (-not $hasPass)  { $out += 'ADMIN_PASSWORD=admin123' };" ^
    "Set-Content -Path $f -Value $out -Encoding ASCII"

if errorlevel 1 (
    echo  [ERROR] .env update fail. Manually edit karein:
    echo          ADMIN_EMAIL=admin@krexion.local
    echo          ADMIN_PASSWORD=admin123
    pause
    exit /b 1
)
echo        OK - .env updated.
echo.

REM ───── Restart backend container ─────
echo [3/4] Backend container restart kar raha hun...
pushd "%ROOT%"

REM Recreate backend so it picks up new env
docker compose up -d --force-recreate --no-deps backend
if errorlevel 1 (
    echo  [ERROR] Backend restart fail.
    popd
    pause
    exit /b 1
)
echo        OK - Backend restarted.
echo.

REM ───── Wait for healthcheck ─────
echo [4/4] Backend ready hone ka wait kar raha hun (30 seconds)...
timeout /t 15 /nobreak >nul

REM Test login
echo        Login test kar raha hun...
curl -s -X POST "http://127.0.0.1:8001/api/admin/login" ^
    -H "Content-Type: application/json" ^
    -d "{\"email\":\"admin@krexion.local\",\"password\":\"admin123\"}" > "%TEMP%\admin_test.json" 2>nul

findstr /C:"access_token" "%TEMP%\admin_test.json" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [WARN] Login test successful nahi - logs check karein:
    echo          docker compose logs --tail=50 backend
    type "%TEMP%\admin_test.json"
    echo.
) else (
    echo        OK - Admin login working!
)
del "%TEMP%\admin_test.json" >nul 2>&1
popd
echo.

REM ───── Done ─────
echo  ============================================================
echo    PASSWORD RESET COMPLETE!
echo  ============================================================
echo.
echo    Admin Email   : admin@krexion.local
echo    Admin Password: admin123
echo.
echo    Ab browser mein:
echo      1. Apna Krexion URL kholein
echo      2. "Admin Login" pe click karein
echo      3. Login karein:
echo            Email   : admin@krexion.local
echo            Password: admin123
echo.
echo    NOTE: Login ke baad password change kar lein (Settings se)
echo          aur naya password .env mein bhi update karein.
echo.
echo  ============================================================
echo.
pause
endlocal
