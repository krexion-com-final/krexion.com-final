@echo off
REM ====================================================================
REM   Krexion FRESH DEPLOY v2 (Bulletproof)
REM   ───────────────────────────────────────
REM   Drop this in NEW download folder. Right-click - Run as Admin.
REM
REM   Saara output deploy.log mein bhi save hota hai.
REM ====================================================================

REM Capture all output to a log file via PowerShell tee-like wrapper
if "%~1"=="_NESTED_" goto MAIN

REM Re-launch self with output captured to log
set "LOG=%~dp0deploy.log"
echo Logs: %LOG% > "%LOG%"
"%~f0" _NESTED_ 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOG%' -Append"
echo.
echo  ============================================================
echo    Logs saved to: %LOG%
echo  ============================================================
pause
exit /b

:MAIN
setlocal EnableDelayedExpansion
title Krexion - FRESH DEPLOY (Bulletproof)
color 0A

cls
echo.
echo  ============================================================
echo    Krexion - FRESH DEPLOY (Bulletproof)
echo  ============================================================
echo.

set "ROOT=%~dp0"
if "!ROOT:~-1!"=="\" set "ROOT=!ROOT:~0,-1!"

if not exist "!ROOT!\docker-compose.yml" (
    echo  [ERROR] docker-compose.yml not found. Run from NEW download folder.
    echo          Path: !ROOT!
    exit /b 1
)
echo    Deploy from: !ROOT!
echo.

REM ───── Docker check ─────
docker info >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Docker Desktop chalu nahi hai. Pehle ise start karein.
    exit /b 1
)
echo    Docker: OK
echo.

REM ───── Confirm ─────
echo  WARNING: ye actions hone wali hain:
echo    1. Saari purani Krexion containers + volumes HATAYI jayein gi
echo    2. SAFETY backup banega: C:\Krexion-Backups\
echo    3. NEW folder se fresh deploy
echo.
set "GO=yes"
set /p "GO=  Continue? (default yes, Enter dabayein ya 'no' likhain): "
if /I "!GO!"=="no" exit /b 0
echo.

REM ───── Backup folder ─────
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "DT=%%a"
set "TS=!DT:~0,8!-!DT:~8,6!"
set "BACKUP_ROOT=C:\Krexion-Backups"
set "BACKUP_DIR=!BACKUP_ROOT!\fresh-deploy-!TS!"
if not exist "!BACKUP_ROOT!" mkdir "!BACKUP_ROOT!"
if not exist "!BACKUP_DIR!" mkdir "!BACKUP_DIR!"
if not exist "!BACKUP_DIR!\volumes" mkdir "!BACKUP_DIR!\volumes"
echo    Backup dir: !BACKUP_DIR!
echo.

REM ════════════════════════════════════════════════════════════
REM   STEP 1: Backup .env from old install
REM ════════════════════════════════════════════════════════════
echo [1/8] Old .env files backup...
set "OLD_WORKDIR="
for /f "delims=" %%p in ('docker inspect krexion-backend --format "{{ index .Config.Labels \"com.docker.compose.project.working_dir\" }}" 2^>nul') do (
    set "OLD_WORKDIR=%%p"
)

if defined OLD_WORKDIR (
    echo        Old install detected: !OLD_WORKDIR!
    if exist "!OLD_WORKDIR!\.env" (
        copy /Y "!OLD_WORKDIR!\.env" "!BACKUP_DIR!\old.env" >nul
        echo        Backed up: !OLD_WORKDIR!\.env
    )
    if exist "!OLD_WORKDIR!\backend\.env" (
        copy /Y "!OLD_WORKDIR!\backend\.env" "!BACKUP_DIR!\old.backend.env" >nul
    )
)

REM Also try the known amna folder
set "AMNA_PATH=C:\Krexion"
if exist "!AMNA_PATH!\.env" (
    if not exist "!BACKUP_DIR!\old.env" (
        copy /Y "!AMNA_PATH!\.env" "!BACKUP_DIR!\old.env" >nul
        echo        Backed up: !AMNA_PATH!\.env
    )
)
echo.

REM ════════════════════════════════════════════════════════════
REM   STEP 2: Backup mongo-data volumes
REM ════════════════════════════════════════════════════════════
echo [2/8] MongoDB volumes backup...
set "VOL_LIST_FILE=!BACKUP_DIR!\_volumes.txt"
docker volume ls --format "{{.Name}}" > "!VOL_LIST_FILE!" 2>nul

set "BACKED_ANY="
for /f "delims=" %%v in ('findstr /R "mongo-data" "!VOL_LIST_FILE!" 2^>nul') do (
    set "VOLNAME=%%v"
    echo        Volume found: !VOLNAME!
    docker run --rm -v "!VOLNAME!:/data:ro" -v "!BACKUP_DIR!\volumes:/backup" alpine sh -c "tar czf /backup/!VOLNAME!.tar.gz -C /data . 2>/dev/null && echo OK"
    if exist "!BACKUP_DIR!\volumes\!VOLNAME!.tar.gz" (
        echo        Backed up: !VOLNAME!.tar.gz
        set "BACKED_ANY=1"
    )
)
if not defined BACKED_ANY (
    echo        Koi mongo-data volume nahi mila ya empty hai.
)
echo.

REM ════════════════════════════════════════════════════════════
REM   STEP 3: Stop old install via its compose
REM ════════════════════════════════════════════════════════════
echo [3/8] Old install ko clean shutdown...
if defined OLD_WORKDIR (
    if exist "!OLD_WORKDIR!\docker-compose.yml" (
        pushd "!OLD_WORKDIR!"
        docker compose --profile tunnel down --remove-orphans 2>nul
        docker compose down --remove-orphans 2>nul
        popd
    )
)
echo        OK
echo.

REM ════════════════════════════════════════════════════════════
REM   STEP 4: Force-clean leftover resources
REM ════════════════════════════════════════════════════════════
echo [4/8] Force-clean containers/volumes/networks...

REM Remove containers matching krexion-*
for /f "delims=" %%c in ('docker ps -a --filter "name=krexion-" --format "{{.Names}}" 2^>nul') do (
    docker rm -f %%c >nul 2>nul
    echo        Removed container: %%c
)

REM Remove volumes containing mongo-data or pw-browsers
for /f "delims=" %%v in ('findstr /R "mongo-data pw-browsers" "!VOL_LIST_FILE!" 2^>nul') do (
    docker volume rm %%v >nul 2>nul
    echo        Removed volume: %%v
)

REM Remove networks matching krexion
for /f "delims=" %%n in ('docker network ls --filter "name=krexion" --format "{{.Name}}" 2^>nul') do (
    docker network rm %%n >nul 2>nul
    echo        Removed network: %%n
)
echo.

REM ════════════════════════════════════════════════════════════
REM   STEP 5: Build .env in NEW folder
REM ════════════════════════════════════════════════════════════
echo [5/8] Naya .env bana raha hun...

set "ENV_FILE=!ROOT!\.env"
set "ADMIN_EMAIL_VAL=admin@krexion.local"
set "ADMIN_PASS_VAL=admin123"
set "APP_URL_VAL=https://krexion.com"
set "PUBLIC_BASE_URL_VAL=https://api.krexion.com"
set "TUNNEL_TOKEN_VAL="

REM Inherit from old .env if exists
if exist "!BACKUP_DIR!\old.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("!BACKUP_DIR!\old.env") do (
        if /I "%%a"=="ADMIN_EMAIL"     if not "%%b"=="" set "ADMIN_EMAIL_VAL=%%b"
        if /I "%%a"=="APP_URL"         if not "%%b"=="" set "APP_URL_VAL=%%b"
        if /I "%%a"=="PUBLIC_BASE_URL" if not "%%b"=="" set "PUBLIC_BASE_URL_VAL=%%b"
        if /I "%%a"=="TUNNEL_TOKEN"    if not "%%b"=="" set "TUNNEL_TOKEN_VAL=%%b"
    )
    echo        Inherited values from old .env
)

REM Generate random secrets
for /f "delims=" %%j in ('powershell -NoProfile -Command "-join ((1..48) ^| %% { [char[]](48..57+65..90+97..122) ^| Get-Random })"') do set "JWT_SECRET=%%j"
for /f "delims=" %%t in ('powershell -NoProfile -Command "-join ((1..32) ^| %% { [char[]](48..57+97..122) ^| Get-Random })"') do set "POSTBACK_TOK=%%t"

REM Write fresh .env (no quotes, no spaces around =)
> "!ENV_FILE!" echo DB_NAME=krexion
>> "!ENV_FILE!" echo JWT_SECRET_KEY=!JWT_SECRET!
>> "!ENV_FILE!" echo ADMIN_EMAIL=!ADMIN_EMAIL_VAL!
>> "!ENV_FILE!" echo ADMIN_PASSWORD=!ADMIN_PASS_VAL!
>> "!ENV_FILE!" echo POSTBACK_TOKEN=!POSTBACK_TOK!
>> "!ENV_FILE!" echo APP_URL=!APP_URL_VAL!
>> "!ENV_FILE!" echo PUBLIC_BASE_URL=!PUBLIC_BASE_URL_VAL!
>> "!ENV_FILE!" echo CORS_ORIGINS=*
>> "!ENV_FILE!" echo RESEND_API_KEY=
>> "!ENV_FILE!" echo RESEND_FROM=no-reply@krexion.com
>> "!ENV_FILE!" echo TUNNEL_TOKEN=!TUNNEL_TOKEN_VAL!

echo        OK - .env written
echo        ADMIN_EMAIL=!ADMIN_EMAIL_VAL!
echo        ADMIN_PASSWORD=!ADMIN_PASS_VAL!
echo.

REM ════════════════════════════════════════════════════════════
REM   STEP 6: Build
REM ════════════════════════════════════════════════════════════
echo [6/8] Containers build (3-5 min)...
pushd "!ROOT!"
docker compose build
set "BUILD_RC=!ERRORLEVEL!"
popd
if !BUILD_RC! NEQ 0 (
    echo  [ERROR] docker compose build fail. RC=!BUILD_RC!
    exit /b !BUILD_RC!
)
echo        Build OK
echo.

REM ════════════════════════════════════════════════════════════
REM   STEP 7: Start
REM ════════════════════════════════════════════════════════════
echo [7/8] Services start...
pushd "!ROOT!"
if not "!TUNNEL_TOKEN_VAL!"=="" (
    echo        Starting WITH cloudflare tunnel profile
    docker compose --profile tunnel up -d
) else (
    echo        Starting WITHOUT tunnel
    docker compose up -d
)
set "UP_RC=!ERRORLEVEL!"
popd
if !UP_RC! NEQ 0 (
    echo  [ERROR] docker compose up fail. RC=!UP_RC!
    exit /b !UP_RC!
)
echo        Start OK
echo.

REM ════════════════════════════════════════════════════════════
REM   STEP 8: Optional restore + verify
REM ════════════════════════════════════════════════════════════
echo [8/8] Verify (15 sec wait for backend)...
timeout /t 15 /nobreak >nul

pushd "!ROOT!"
docker compose ps
popd
echo.

REM Test admin login
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/admin/login' -Method POST -Body (@{email='!ADMIN_EMAIL_VAL!';password='!ADMIN_PASS_VAL!'} ^| ConvertTo-Json) -ContentType 'application/json' -TimeoutSec 15; if ($r.access_token) { Write-Host '   ADMIN LOGIN: WORKING' -ForegroundColor Green } else { Write-Host '   ADMIN LOGIN: FAIL' -ForegroundColor Red } } catch { Write-Host \"   ADMIN LOGIN: $($_.Exception.Message)\" -ForegroundColor Red }"
echo.

echo  ============================================================
echo    DEPLOY COMPLETE!
echo  ============================================================
echo    Admin Email   : !ADMIN_EMAIL_VAL!
echo    Admin Password: !ADMIN_PASS_VAL!
echo    Backup        : !BACKUP_DIR!
echo    Logs          : !ROOT!\deploy.log
echo  ============================================================
echo.

if defined BACKED_ANY (
    echo  Note: Aap ka purana mongo-data backup safe hai:
    echo    !BACKUP_DIR!\volumes\
    echo  Restore karna ho to ye command chalayein:
    for /f "delims=" %%f in ('dir /b "!BACKUP_DIR!\volumes\*.tar.gz" 2^>nul') do (
        echo    docker stop krexion-mongo
        echo    docker run --rm -v krexion-mongo-data:/data -v "!BACKUP_DIR!\volumes:/backup" alpine sh -c "rm -rf /data/* /data/.* 2^>/dev/null; tar xzf /backup/%%f -C /data"
        echo    docker start krexion-mongo
        goto :NORESTORE_DONE
    )
)
:NORESTORE_DONE
echo.

endlocal
exit /b 0
