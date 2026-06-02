@echo off
REM ====================================================================
REM   Krexion DOCTOR — Full Stack Health Check + Auto-Fix
REM   Drop anywhere. Right-click - Run as Administrator.
REM ====================================================================

if "%~1"=="_NESTED_" goto MAIN
set "LOG=%~dp0doctor.log"
echo Logs: %LOG% > "%LOG%"
"%~f0" _NESTED_ 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOG%' -Append"
echo.
echo  Saved log: %LOG%
pause
exit /b

:MAIN
setlocal EnableDelayedExpansion
title Krexion - DOCTOR (Health Check + Auto-Fix)
color 0E
cls

echo.
echo  ============================================================
echo    Krexion - DOCTOR
echo  ============================================================
echo.

REM ───── 1. Docker daemon ─────
echo [1] Docker Desktop running?
docker info >nul 2>&1
if errorlevel 1 (
    echo     FAIL - Docker chalu nahi. Start Docker Desktop and retry.
    pause & exit /b 1
)
echo     OK
echo.

REM ───── 2. Krexion containers ─────
echo [2] Krexion containers status:
docker ps -a --filter "name=krexion-" --format "    {{.Names}}: {{.Status}}"
echo.

REM Check each expected container
set "MONGO_OK=0"
set "BACKEND_OK=0"
for /f "delims=" %%c in ('docker ps --format "{{.Names}}" 2^>nul') do (
    if "%%c"=="krexion-mongo" set "MONGO_OK=1"
    if "%%c"=="krexion-backend" set "BACKEND_OK=1"
)

if "!MONGO_OK!"=="0" echo     [MISSING] krexion-mongo not running
if "!BACKEND_OK!"=="0" echo     [MISSING] krexion-backend not running
if "!MONGO_OK!"=="1" if "!BACKEND_OK!"=="1" echo     OK - Both running
echo.

REM ───── 3. Find project working dir ─────
echo [3] Project working dir (where compose was started from):
set "WORKDIR="
for /f "delims=" %%p in ('docker inspect krexion-backend --format "{{ index .Config.Labels \"com.docker.compose.project.working_dir\" }}" 2^>nul') do (
    set "WORKDIR=%%p"
)
if defined WORKDIR (
    echo     OK - !WORKDIR!
) else (
    echo     UNKNOWN - container ne label nahi diya
)
echo.

REM ───── 4. Show .env file location + admin values ─────
echo [4] .env file admin values:
if defined WORKDIR (
    if exist "!WORKDIR!\.env" (
        echo     File: !WORKDIR!\.env
        for /f "usebackq tokens=1,* delims==" %%a in ("!WORKDIR!\.env") do (
            if /I "%%a"=="ADMIN_EMAIL"     echo     ADMIN_EMAIL=%%b
            if /I "%%a"=="ADMIN_PASSWORD"  echo     ADMIN_PASSWORD=%%b
            if /I "%%a"=="JWT_SECRET_KEY" (
                set "JWT=%%b"
                if "!JWT!"=="" (
                    echo     JWT_SECRET_KEY=^(EMPTY - PROBLEM!^)
                ) else (
                    echo     JWT_SECRET_KEY=^(set, length OK^)
                )
            )
        )
    ) else (
        echo     [MISSING] .env file nahi hai
    )
) else (
    echo     SKIP - workdir unknown
)
echo.

REM ───── 5. Show ACTUAL env loaded INSIDE container ─────
echo [5] Backend container ke ANDAR loaded env:
if "!BACKEND_OK!"=="1" (
    for /f "delims=" %%e in ('docker exec krexion-backend env 2^>nul ^| findstr /B /C:"ADMIN_EMAIL=" /C:"ADMIN_PASSWORD=" /C:"JWT_SECRET_KEY="') do (
        REM Mask JWT_SECRET_KEY value but show others
        set "LINE=%%e"
        echo !LINE! | findstr /B /C:"JWT_SECRET_KEY=" >nul && (
            echo     JWT_SECRET_KEY=^(loaded^)
        ) || (
            echo     !LINE!
        )
    )
) else (
    echo     SKIP - backend not running
)
echo.

REM ───── 6. Backend health endpoint ─────
echo [6] Backend /health endpoint:
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health' -TimeoutSec 5; Write-Host '    OK -' (ConvertTo-Json $r -Compress) -ForegroundColor Green } catch { Write-Host \"    FAIL - $($_.Exception.Message)\" -ForegroundColor Red }"
echo.

REM ───── 7. MongoDB ping ─────
echo [7] MongoDB ping:
if "!MONGO_OK!"=="1" (
    docker exec krexion-mongo mongosh --quiet --eval "db.runCommand({ping:1}).ok" 2>nul
) else (
    echo     SKIP - mongo not running
)
echo.

REM ───── 8. Test admin login with current .env values ─────
echo [8] Admin login test (using values from container env):
set "TEST_EMAIL="
set "TEST_PASS="
if "!BACKEND_OK!"=="1" (
    for /f "tokens=1,* delims==" %%a in ('docker exec krexion-backend env 2^>nul ^| findstr /B /C:"ADMIN_EMAIL="') do set "TEST_EMAIL=%%b"
    for /f "tokens=1,* delims==" %%a in ('docker exec krexion-backend env 2^>nul ^| findstr /B /C:"ADMIN_PASSWORD="') do set "TEST_PASS=%%b"

    echo     Testing: !TEST_EMAIL! / !TEST_PASS!
    powershell -NoProfile -Command "try { $body = @{email='!TEST_EMAIL!';password='!TEST_PASS!'} ^| ConvertTo-Json; $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/admin/login' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 10; if ($r.access_token) { Write-Host '    PASS - Login working with these credentials!' -ForegroundColor Green } else { Write-Host '    FAIL - no token' -ForegroundColor Red } } catch { Write-Host \"    FAIL - $($_.Exception.Message)\" -ForegroundColor Red }"
) else (
    echo     SKIP - backend not running
)
echo.

REM ───── 9. Cloudflare Tunnel ─────
echo [9] Cloudflare Tunnel status:
docker ps --filter "name=krexion-cloudflared" --format "    {{.Names}}: {{.Status}}" 2>nul
docker ps --filter "name=krexion-cloudflared" --format "{{.Names}}" 2>nul | findstr "krexion-cloudflared" >nul
if errorlevel 1 echo     [OFF] Tunnel not running ^(local-only mode^)
echo.

REM ───── 10. Recent backend errors ─────
echo [10] Recent backend errors (last 20 lines):
echo     ────────────────────────────────────────
docker compose -f "!WORKDIR!\docker-compose.yml" logs --tail=20 backend 2>nul | findstr /I "error fail exception traceback warning" 2>nul
if errorlevel 1 echo     OK - no recent errors found
echo     ────────────────────────────────────────
echo.

REM ════════════════════════════════════════════════════════════
REM   AUTO-FIX MENU
REM ════════════════════════════════════════════════════════════
echo  ============================================================
echo    AUTO-FIX OPTIONS
echo  ============================================================
echo.
echo    [1] Reset admin to admin@krexion.local / admin123
echo        ^(.env update + force restart backend^)
echo    [2] Set CUSTOM admin email + password
echo    [3] Force restart backend (load latest .env)
echo    [4] Show full backend logs (last 100 lines)
echo    [5] Exit (no changes)
echo.
set "OPT="
set /p "OPT=    Choose option: "

if "!OPT!"=="1" goto RESET_DEFAULT
if "!OPT!"=="2" goto RESET_CUSTOM
if "!OPT!"=="3" goto RESTART_ONLY
if "!OPT!"=="4" goto SHOW_LOGS
goto END

REM ════════════════════════════════════════════════════════════
:RESET_DEFAULT
set "NEW_EMAIL=admin@krexion.local"
set "NEW_PASS=admin123"
goto APPLY_RESET

:RESET_CUSTOM
set "NEW_EMAIL="
set /p "NEW_EMAIL=    Naya Admin Email: "
if "!NEW_EMAIL!"=="" set "NEW_EMAIL=admin@krexion.local"
set "NEW_PASS="
set /p "NEW_PASS=    Naya password (visible typing): "
if "!NEW_PASS!"=="" set "NEW_PASS=admin123"
goto APPLY_RESET

:APPLY_RESET
if not defined WORKDIR (
    echo     [ERROR] Workdir unknown - .env update nahi ho sakta.
    goto END
)

set "ENV_FILE=!WORKDIR!\.env"
echo.
echo    Updating !ENV_FILE!
echo    New: !NEW_EMAIL! / !NEW_PASS!

REM Backup
copy /Y "!ENV_FILE!" "!ENV_FILE!.bak" >nul 2>&1

REM Use PowerShell to surgically update .env
powershell -NoProfile -Command ^
    "$f='!ENV_FILE!';" ^
    "$lines = if (Test-Path $f) { Get-Content $f } else { @() };" ^
    "$out = @(); $hE=$false; $hP=$false; $hJ=$false;" ^
    "foreach($l in $lines) {" ^
        "if ($l -match '^\s*ADMIN_EMAIL\s*=') { $out += 'ADMIN_EMAIL=!NEW_EMAIL!'; $hE=$true }" ^
        "elseif ($l -match '^\s*ADMIN_PASSWORD\s*=') { $out += 'ADMIN_PASSWORD=!NEW_PASS!'; $hP=$true }" ^
        "elseif ($l -match '^\s*JWT_SECRET_KEY\s*=(.*)$') {" ^
            "$v=$matches[1].Trim();" ^
            "if ([string]::IsNullOrWhiteSpace($v)) { $r = -join ((1..48)|%%{[char[]](48..57+65..90+97..122)|Get-Random}); $out += \"JWT_SECRET_KEY=$r\" } else { $out += $l };" ^
            "$hJ=$true" ^
        "}" ^
        "else { $out += $l }" ^
    "};" ^
    "if (-not $hE) { $out += 'ADMIN_EMAIL=!NEW_EMAIL!' };" ^
    "if (-not $hP) { $out += 'ADMIN_PASSWORD=!NEW_PASS!' };" ^
    "if (-not $hJ) { $r = -join ((1..48)|%%{[char[]](48..57+65..90+97..122)|Get-Random}); $out += \"JWT_SECRET_KEY=$r\" };" ^
    "Set-Content -Path $f -Value $out -Encoding ASCII"

echo    .env updated.
echo.

REM Force restart with new env
echo    Backend restart kar raha hun...
pushd "!WORKDIR!"
docker compose up -d --force-recreate --no-deps backend
popd
echo    Wait 15 sec for backend...
timeout /t 15 /nobreak >nul

echo.
echo    Login test:
powershell -NoProfile -Command "try { $body = @{email='!NEW_EMAIL!';password='!NEW_PASS!'} ^| ConvertTo-Json; $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/admin/login' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 15; if ($r.access_token) { Write-Host '    SUCCESS - LOGIN WORKING!' -ForegroundColor Green } else { Write-Host '    FAIL' -ForegroundColor Red } } catch { Write-Host \"    FAIL - $($_.Exception.Message)\" -ForegroundColor Red }"
echo.
echo    Use these credentials in browser:
echo       Email   : !NEW_EMAIL!
echo       Password: !NEW_PASS!
goto END

REM ════════════════════════════════════════════════════════════
:RESTART_ONLY
if not defined WORKDIR (
    echo    [ERROR] Workdir unknown.
    goto END
)
echo    Restarting backend from !WORKDIR!...
pushd "!WORKDIR!"
docker compose up -d --force-recreate --no-deps backend
popd
echo    Wait 15 sec...
timeout /t 15 /nobreak >nul
echo    Done.
goto END

REM ════════════════════════════════════════════════════════════
:SHOW_LOGS
if defined WORKDIR (
    pushd "!WORKDIR!"
    docker compose logs --tail=100 backend
    popd
) else (
    docker logs --tail=100 krexion-backend 2>nul
)
goto END

:END
echo.
echo  ============================================================
echo    Doctor done. Log: !LOG!
echo  ============================================================
echo.
endlocal
exit /b 0
