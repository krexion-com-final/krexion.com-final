@echo off
REM ====================================================================
REM   KREXION LOGIN FIX - PERMANENT ONE-CLICK SOLUTION
REM   ─────────────────────────────────────────────────
REM   1. Saari conflicting backend containers hata deta hai
REM   2. Force resets admin credentials to admin@krexion.local / admin123
REM   3. Force-recreates backend with fresh .env
REM   4. Tests login on LOCAL aur PUBLIC URL dono
REM   5. Browser khol deta hai credentials ke saath
REM ====================================================================

if "%~1"=="_NESTED_" goto MAIN
set "LOG=%~dp0login-fix.log"
echo Logs: %LOG% > "%LOG%"
"%~f0" _NESTED_ 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOG%' -Append"
echo.
echo  Saved log: %LOG%
pause
exit /b

:MAIN
setlocal EnableDelayedExpansion
title Krexion LOGIN FIX - Permanent Solution
color 0A
cls

echo.
echo  ============================================================
echo    KREXION LOGIN FIX - Permanent Solution
echo  ============================================================
echo.

REM ───── Docker check ─────
docker info >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Docker Desktop chalu nahi! Start Docker Desktop and retry.
    exit /b 1
)
echo  [1/9] Docker check: OK
echo.

REM ───── Find ALL krexion-backend containers (might be multiple) ─────
echo  [2/9] Saare Krexion backend containers dhoondh raha hun...
set "CONTAINER_COUNT=0"
for /f "delims=" %%c in ('docker ps -a --filter "name=krexion-backend" --format "{{.Names}}" 2^>nul') do (
    set /a CONTAINER_COUNT+=1
    echo        Found: %%c
)

REM ───── Find the project workdir from the running one ─────
set "WORKDIR="
for /f "delims=" %%p in ('docker inspect krexion-backend --format "{{ index .Config.Labels \"com.docker.compose.project.working_dir\" }}" 2^>nul') do (
    set "WORKDIR=%%p"
)

REM Fallback to known paths
if not defined WORKDIR (
    if exist "C:\Krexion\docker-compose.yml" (
        set "WORKDIR=C:\Krexion"
    )
)

if not defined WORKDIR (
    echo  [ERROR] Project folder nahi mila. Manually run from your install folder.
    exit /b 1
)

echo        Project: !WORKDIR!
echo.

REM ───── KILL ALL krexion containers (clean slate) ─────
echo  [3/9] Saari purani Krexion containers hata raha hun...
for /f "delims=" %%c in ('docker ps -a --filter "name=krexion-" --format "{{.Names}}" 2^>nul') do (
    docker rm -f %%c >nul 2>nul
    echo        Removed: %%c
)
echo.

REM ───── Force-write .env with KNOWN GOOD admin creds ─────
echo  [4/9] .env file reset to admin@krexion.local / admin123
set "ENV_FILE=!WORKDIR!\.env"

REM Backup
if exist "!ENV_FILE!" (
    copy /Y "!ENV_FILE!" "!ENV_FILE!.bak" >nul 2>&1
)

REM Read existing values to preserve URLs/tunnel
set "APP_URL_VAL=https://krexion.com"
set "PUBLIC_BASE_URL_VAL=https://api.krexion.com"
set "TUNNEL_TOKEN_VAL="

if exist "!ENV_FILE!" (
    for /f "usebackq tokens=1,* delims==" %%a in ("!ENV_FILE!") do (
        if /I "%%a"=="APP_URL"         if not "%%b"=="" set "APP_URL_VAL=%%b"
        if /I "%%a"=="PUBLIC_BASE_URL" if not "%%b"=="" set "PUBLIC_BASE_URL_VAL=%%b"
        if /I "%%a"=="TUNNEL_TOKEN"    if not "%%b"=="" set "TUNNEL_TOKEN_VAL=%%b"
    )
)

REM Generate fresh secrets
for /f "delims=" %%j in ('powershell -NoProfile -Command "-join ((1..48) ^| %% { [char[]](48..57+65..90+97..122) ^| Get-Random })"') do set "JWT_SECRET=%%j"
for /f "delims=" %%t in ('powershell -NoProfile -Command "-join ((1..32) ^| %% { [char[]](48..57+97..122) ^| Get-Random })"') do set "POSTBACK_TOK=%%t"

> "!ENV_FILE!" echo DB_NAME=krexion
>> "!ENV_FILE!" echo JWT_SECRET_KEY=!JWT_SECRET!
>> "!ENV_FILE!" echo ADMIN_EMAIL=admin@krexion.local
>> "!ENV_FILE!" echo ADMIN_PASSWORD=admin123
>> "!ENV_FILE!" echo POSTBACK_TOKEN=!POSTBACK_TOK!
>> "!ENV_FILE!" echo APP_URL=!APP_URL_VAL!
>> "!ENV_FILE!" echo PUBLIC_BASE_URL=!PUBLIC_BASE_URL_VAL!
>> "!ENV_FILE!" echo CORS_ORIGINS=*
>> "!ENV_FILE!" echo RESEND_API_KEY=
>> "!ENV_FILE!" echo RESEND_FROM=no-reply@krexion.com
>> "!ENV_FILE!" echo TUNNEL_TOKEN=!TUNNEL_TOKEN_VAL!

echo        OK - .env written
echo        APP_URL=!APP_URL_VAL!
echo        TUNNEL_TOKEN=!TUNNEL_TOKEN_VAL:~0,20!...^(masked^)
echo.

REM ───── Recreate everything from scratch ─────
echo  [5/9] Containers fresh start kar raha hun...
pushd "!WORKDIR!"

if not "!TUNNEL_TOKEN_VAL!"=="" (
    echo        Mode: WITH Cloudflare Tunnel
    docker compose --profile tunnel up -d
) else (
    echo        Mode: LOCAL ONLY (no tunnel)
    docker compose up -d
)
set "UP_RC=!ERRORLEVEL!"
popd

if !UP_RC! NEQ 0 (
    echo  [ERROR] docker compose up fail.
    exit /b !UP_RC!
)
echo        OK
echo.

REM ───── Wait for backend health ─────
echo  [6/9] Backend health wait (max 60 sec)...
set /a TRIES=0
:WAIT_HEALTH
set /a TRIES+=1
timeout /t 3 /nobreak >nul
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/health' -TimeoutSec 3; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    if !TRIES! LSS 20 (
        echo        Wait... [!TRIES!/20]
        goto WAIT_HEALTH
    )
    echo        TIMEOUT - backend not healthy after 60 sec
    pushd "!WORKDIR!"
    docker compose logs --tail=30 backend
    popd
    exit /b 1
)
echo        OK - backend healthy
echo.

REM ───── Verify env loaded inside container ─────
echo  [7/9] Container ke andar loaded env verify:
for /f "delims=" %%e in ('docker exec krexion-backend env 2^>nul ^| findstr /B /C:"ADMIN_EMAIL=" /C:"ADMIN_PASSWORD="') do (
    echo        %%e
)
echo.

REM ───── Test LOCAL login ─────
echo  [8/9] LOCAL login test (http://127.0.0.1:8001):
set "LOCAL_OK=0"
powershell -NoProfile -Command "try { $body = @{email='admin@krexion.local';password='admin123'} ^| ConvertTo-Json; $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/admin/login' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 10; if ($r.access_token) { Write-Host '       PASS - Local login working!' -ForegroundColor Green; exit 0 } else { exit 1 } } catch { Write-Host \"       FAIL - $($_.Exception.Message)\" -ForegroundColor Red; exit 1 }"
if not errorlevel 1 set "LOCAL_OK=1"
echo.

REM ───── Test PUBLIC login (via Cloudflare Tunnel) ─────
echo  [9/9] PUBLIC login test (!PUBLIC_BASE_URL_VAL!):
set "PUBLIC_OK=0"
powershell -NoProfile -Command "try { $body = @{email='admin@krexion.local';password='admin123'} ^| ConvertTo-Json; $r = Invoke-RestMethod -Uri '!PUBLIC_BASE_URL_VAL!/api/admin/login' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 15; if ($r.access_token) { Write-Host '       PASS - Public login working!' -ForegroundColor Green; exit 0 } else { exit 1 } } catch { Write-Host \"       FAIL - $($_.Exception.Message)\" -ForegroundColor Red; exit 1 }"
if not errorlevel 1 set "PUBLIC_OK=1"
echo.

REM ════════════════════════════════════════════════════════════
REM   FINAL VERDICT
REM ════════════════════════════════════════════════════════════
echo  ============================================================

if "!LOCAL_OK!"=="1" if "!PUBLIC_OK!"=="1" (
    echo    SUCCESS - LOGIN WORKING EVERYWHERE!
    echo  ============================================================
    echo.
    echo    Browser mein ye credentials use karein:
    echo.
    echo       URL      : !APP_URL_VAL!/admin
    echo       Email    : admin@krexion.local
    echo       Password : admin123
    echo.
    echo  ============================================================
    echo.
    echo    Browser auto-open ho raha hai...
    timeout /t 2 /nobreak >nul
    start "" "!APP_URL_VAL!/admin"
    goto FINISH
)

if "!LOCAL_OK!"=="1" if "!PUBLIC_OK!"=="0" (
    echo    PARTIAL - LOCAL OK, PUBLIC FAIL
    echo  ============================================================
    echo.
    echo    Local backend chal raha hai par Cloudflare Tunnel issue:
    echo      - Tunnel container chal raha hai ya nahi check karein
    echo      - Cloudflare dashboard mein tunnel "Healthy" status check karein
    echo      - Aap ka tunnel kisi PURANE container pe point ho sakta hai
    echo.
    echo    Cloudflare tunnel container status:
    docker ps -a --filter "name=krexion-cloudflared" --format "       {{.Names}}: {{.Status}}"
    echo.
    echo    Browser mein localhost se test karein (Cloudflare bypass):
    echo       URL      : http://localhost:8001/api/admin/login
    echo       Email    : admin@krexion.local
    echo       Password : admin123
    echo.
    echo    Frontend Vercel pe REACT_APP_BACKEND_URL check karein -
    echo    woh !PUBLIC_BASE_URL_VAL! par point honi chahiye.
    goto FINISH
)

REM Both failed
echo    BOTH FAILED - DEEP DEBUG NEEDED
echo  ============================================================
echo.
echo    Backend logs (last 30 lines):
echo    ────────────────────────────
pushd "!WORKDIR!"
docker compose logs --tail=30 backend
popd
echo.

:FINISH
echo.
echo  ============================================================
echo    Log saved: %~dp0login-fix.log
echo  ============================================================
endlocal
exit /b 0
