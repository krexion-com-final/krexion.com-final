@echo off
REM =====================================================================
REM   Krexion ONE-CLICK AUTO (Always Fresh + GitHub Auto-Update)
REM   ───────────────────────────────────────────────────────────
REM   YEHI EK FILE DABAYEIN, BAS — sab kuch automatic:
REM     - Pehli baar GitHub repo URL puchhega (sirf 1 dafa)
REM     - Latest code GitHub se pull
REM     - Old containers/volumes safely backup + clean
REM     - .env file write (admin creds saved across runs)
REM     - Containers build + start
REM     - Admin user FORCE re-seed
REM     - Login verify
REM     - Windows Task Scheduler register: HAR 5 MINUTE mein
REM       GitHub check, naye commits aate hi auto-pull + rebuild
REM
REM   Modes (file ka argument):
REM     [no args]   = Full install + setup auto-watcher (interactive)
REM     _WATCH_     = Periodic pull (called by Task Scheduler silently)
REM     _UNINSTALL_ = Remove the scheduled task (stop auto-update)
REM =====================================================================

if "%~1"=="_WATCH_"     goto WATCH_MODE
if "%~1"=="_UNINSTALL_" goto UNINSTALL_MODE

REM Run as admin if not already
NET SESSION >nul 2>&1
if errorlevel 1 (
    echo Requesting admin rights...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

if "%~1"=="_NESTED_" goto MAIN

set "LOG=%~dp0deploy.log"
echo Started: %date% %time% > "%LOG%"
"%~f0" _NESTED_ 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOG%' -Append"
echo.
echo  ============================================================
echo    Logs saved: %LOG%
echo  ============================================================
pause
exit /b

:MAIN
setlocal EnableDelayedExpansion
title Krexion ONE-CLICK AUTO
color 0A

cls
echo.
echo  ================================================================
echo     R E A L F L O W   O N E - C L I C K   A U T O
echo     One file. Always fresh. Always working.
echo  ================================================================
echo.

set "ROOT=%~dp0"
if "!ROOT:~-1!"=="\" set "ROOT=!ROOT:~0,-1!"

if not exist "!ROOT!\docker-compose.yml" (
    echo  [X] docker-compose.yml not found.
    echo      Folder: !ROOT!
    echo      Yeh file Krexion project root mein chalayein.
    pause
    exit /b 1
)
echo  Folder: !ROOT!
echo.

REM ═════ Docker check ═════
docker info >nul 2>&1
if errorlevel 1 (
    echo  [X] Docker Desktop chalu nahi hai.
    echo      Pehle Docker Desktop start karein, phir yeh file dobara chalayein.
    pause
    exit /b 1
)
echo  Docker: OK
echo.

REM ═════ Git remote auto-setup + pull ═════
if not exist "!ROOT!\.git" (
    echo  This folder is not a git repo yet.
    echo  Aap GitHub repo URL paste kar dein, sirf 1 dafa, future me auto-pull hoga.
    echo.
    echo  Example: https://github.com/yourname/krexion.git
    set "GITHUB_URL="
    set /p "GITHUB_URL=  GitHub repo URL (Enter to skip): "
    if not "!GITHUB_URL!"=="" (
        pushd "!ROOT!"
        git init -b main 2>nul
        git remote add origin "!GITHUB_URL!" 2>nul
        git fetch origin 2>nul
        git reset --hard origin/main 2>nul || git reset --hard origin/master 2>nul
        popd
        echo        Git repo configured with: !GITHUB_URL!
        echo.
    ) else (
        echo        Skipped — code update sirf manual download se hoga.
        echo.
    )
) else (
    echo  Git repo detected. Pulling latest changes...
    pushd "!ROOT!"
    REM Auto-fix: if no remote configured, ask user
    git remote -v 2>nul | findstr /R "^origin" >nul
    if errorlevel 1 (
        echo        No git remote configured. Paste your GitHub URL:
        set "GITHUB_URL="
        set /p "GITHUB_URL=  GitHub repo URL: "
        if not "!GITHUB_URL!"=="" git remote add origin "!GITHUB_URL!" 2>nul
    )
    git fetch --all 2>nul
    git reset --hard origin/main 2>nul || git reset --hard origin/master 2>nul
    git pull --rebase --autostash 2>&1 | findstr /V "^$"
    popd
    echo.
)

REM ═════ Read existing .env to preserve admin creds across runs ═════
set "ADMIN_EMAIL_VAL=admin@krexion.local"
set "ADMIN_PASS_VAL=admin123"
set "APP_URL_VAL=https://krexion.com"
set "PUBLIC_BASE_URL_VAL=https://api.krexion.com"
set "TUNNEL_TOKEN_VAL="

if exist "!ROOT!\.env" (
    echo  Reading existing .env to preserve credentials...
    for /f "usebackq tokens=1,* delims==" %%a in ("!ROOT!\.env") do (
        if /I "%%a"=="ADMIN_EMAIL"     if not "%%b"=="" set "ADMIN_EMAIL_VAL=%%b"
        if /I "%%a"=="ADMIN_PASSWORD"  if not "%%b"=="" set "ADMIN_PASS_VAL=%%b"
        if /I "%%a"=="APP_URL"         if not "%%b"=="" set "APP_URL_VAL=%%b"
        if /I "%%a"=="PUBLIC_BASE_URL" if not "%%b"=="" set "PUBLIC_BASE_URL_VAL=%%b"
        if /I "%%a"=="TUNNEL_TOKEN"    if not "%%b"=="" set "TUNNEL_TOKEN_VAL=%%b"
    )
)

REM Also try to inherit from old install's compose project dir
set "OLD_WORKDIR="
for /f "delims=" %%p in ('docker inspect krexion-backend --format "{{ index .Config.Labels \"com.docker.compose.project.working_dir\" }}" 2^>nul') do (
    set "OLD_WORKDIR=%%p"
)
if defined OLD_WORKDIR (
    if exist "!OLD_WORKDIR!\.env" (
        for /f "usebackq tokens=1,* delims==" %%a in ("!OLD_WORKDIR!\.env") do (
            if /I "%%a"=="ADMIN_EMAIL"    if not "%%b"=="" if "!ADMIN_EMAIL_VAL!"=="admin@krexion.local" set "ADMIN_EMAIL_VAL=%%b"
            if /I "%%a"=="ADMIN_PASSWORD" if not "%%b"=="" if "!ADMIN_PASS_VAL!"=="admin123"            set "ADMIN_PASS_VAL=%%b"
            if /I "%%a"=="APP_URL"        if not "%%b"=="" set "APP_URL_VAL=%%b"
            if /I "%%a"=="PUBLIC_BASE_URL" if not "%%b"=="" set "PUBLIC_BASE_URL_VAL=%%b"
            if /I "%%a"=="TUNNEL_TOKEN"   if not "%%b"=="" set "TUNNEL_TOKEN_VAL=%%b"
        )
    )
)

echo  Admin email: !ADMIN_EMAIL_VAL!
echo  Admin pass : !ADMIN_PASS_VAL!
echo  App URL    : !APP_URL_VAL!
echo.

REM ═════ Backup folder ═════
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value 2^>nul') do set "DT=%%a"
set "TS=!DT:~0,8!-!DT:~8,6!"
set "BACKUP_ROOT=F:\online\real flow\krexion-backups"
if not exist "F:\" set "BACKUP_ROOT=!ROOT!\..\krexion-backups"
set "BACKUP_DIR=!BACKUP_ROOT!\auto-!TS!"
if not exist "!BACKUP_ROOT!" mkdir "!BACKUP_ROOT!" 2>nul
if not exist "!BACKUP_DIR!" mkdir "!BACKUP_DIR!" 2>nul
if not exist "!BACKUP_DIR!\volumes" mkdir "!BACKUP_DIR!\volumes" 2>nul
echo  Backup: !BACKUP_DIR!
echo.

REM ════════════════════════════════════════════════════════════
echo [1/8] Backing up old .env + MongoDB + uploaded files...
REM ════════════════════════════════════════════════════════════
if defined OLD_WORKDIR (
    if exist "!OLD_WORKDIR!\.env" copy /Y "!OLD_WORKDIR!\.env" "!BACKUP_DIR!\old.env" >nul 2>&1
)
if exist "!ROOT!\.env" copy /Y "!ROOT!\.env" "!BACKUP_DIR!\current.env" >nul 2>&1

set "VOL_LIST_FILE=!BACKUP_DIR!\_volumes.txt"
docker volume ls --format "{{.Name}}" > "!VOL_LIST_FILE!" 2>nul

REM Backup ALL data volumes — mongo + uploaded-data + rut-results
for /f "delims=" %%v in ('findstr /R "mongo-data uploaded-data rut-results" "!VOL_LIST_FILE!" 2^>nul') do (
    docker run --rm -v "%%v:/data:ro" -v "!BACKUP_DIR!\volumes:/backup" alpine sh -c "tar czf /backup/%%v.tar.gz -C /data . 2>/dev/null" 2>nul
    if exist "!BACKUP_DIR!\volumes\%%v.tar.gz" echo        Backed up: %%v.tar.gz
)

REM Also extract uploaded files from the LIVE container (first-migration safety —
REM if old install didn't have uploaded-data as a named volume, files only exist
REM inside the running container's filesystem and would otherwise be lost).
docker exec krexion-backend tar czf /tmp/_uploads.tar.gz -C /app/backend uploaded_resources real_user_traffic_results 2>nul
if not errorlevel 1 (
    docker cp krexion-backend:/tmp/_uploads.tar.gz "!BACKUP_DIR!\volumes\_live_uploads.tar.gz" 2>nul
    if exist "!BACKUP_DIR!\volumes\_live_uploads.tar.gz" (
        echo        Backed up: live container uploads ^(first-migration safety^)
    )
    docker exec krexion-backend rm /tmp/_uploads.tar.gz 2>nul
)

REM Pointer file: most recent backup for auto-restore later
> "!BACKUP_ROOT!\_latest.txt" echo !BACKUP_DIR!
echo.

REM ════════════════════════════════════════════════════════════
echo [2/8] Stopping old containers...
REM ════════════════════════════════════════════════════════════
if defined OLD_WORKDIR (
    if exist "!OLD_WORKDIR!\docker-compose.yml" (
        pushd "!OLD_WORKDIR!"
        docker compose --profile tunnel down --remove-orphans 2>nul
        docker compose down --remove-orphans 2>nul
        popd
    )
)
pushd "!ROOT!"
docker compose --profile tunnel down --remove-orphans 2>nul
docker compose down --remove-orphans 2>nul
popd
for /f "delims=" %%c in ('docker ps -a --filter "name=krexion-" --format "{{.Names}}" 2^>nul') do (
    docker rm -f %%c >nul 2>nul
)
REM Only remove mongo-data + pw-browsers — DELIBERATELY KEEP uploaded-data and
REM rut-results so user's XLSX files / proxies / UAs / job screenshots survive
REM across fresh deploys. They will be re-mounted to the new backend container.
for /f "delims=" %%v in ('findstr /R "mongo-data pw-browsers" "!VOL_LIST_FILE!" 2^>nul') do (
    docker volume rm %%v >nul 2>nul
)
for /f "delims=" %%n in ('docker network ls --filter "name=krexion" --format "{{.Name}}" 2^>nul') do (
    docker network rm %%n >nul 2>nul
)
echo        OK
echo.

REM ════════════════════════════════════════════════════════════
echo [3/8] Writing fresh .env...
REM ════════════════════════════════════════════════════════════
set "ENV_FILE=!ROOT!\.env"

REM Generate fresh JWT/postback secrets
for /f "delims=" %%j in ('powershell -NoProfile -Command "-join ((1..48) ^| %% { [char[]](48..57+65..90+97..122) ^| Get-Random })"') do set "JWT_SECRET=%%j"
for /f "delims=" %%t in ('powershell -NoProfile -Command "-join ((1..32) ^| %% { [char[]](48..57+97..122) ^| Get-Random })"') do set "POSTBACK_TOK=%%t"

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
echo        OK
echo.

REM ════════════════════════════════════════════════════════════
echo [4/8] Building containers (3-5 mint, please wait)...
REM ════════════════════════════════════════════════════════════
pushd "!ROOT!"
docker compose build
set "BUILD_RC=!ERRORLEVEL!"
popd
if !BUILD_RC! NEQ 0 (
    echo  [X] Build fail. RC=!BUILD_RC!
    pause
    exit /b !BUILD_RC!
)
echo        Build OK
echo.

REM ════════════════════════════════════════════════════════════
echo [5/8] Starting services...
REM ════════════════════════════════════════════════════════════
pushd "!ROOT!"
if not "!TUNNEL_TOKEN_VAL!"=="" (
    docker compose --profile tunnel up -d
    echo        WITH cloudflare tunnel
) else (
    docker compose up -d
    echo        WITHOUT cloudflare tunnel
)
popd
echo.

REM ════════════════════════════════════════════════════════════
REM   First-migration: if uploaded-data volume is NEW/EMPTY but we have
REM   a _live_uploads.tar.gz from the old container, restore it now so
REM   user's XLSX files / proxies / UAs survive the very first migration
REM   to the volume-mounted setup.
REM ════════════════════════════════════════════════════════════
echo  Checking uploaded-files migration...
timeout /t 4 /nobreak >nul

set "VOL_EMPTY="
for /f "delims=" %%c in ('docker run --rm -v uploaded-data:/data alpine sh -c "ls /data 2>/dev/null | wc -l" 2^>nul') do set "VOL_EMPTY=%%c"
if "!VOL_EMPTY!"=="" set "VOL_EMPTY=0"

if "!VOL_EMPTY!"=="0" (
    if exist "!BACKUP_DIR!\volumes\_live_uploads.tar.gz" (
        echo        Migrating uploaded files from old container into volume...
        docker run --rm -v uploaded-data:/dst -v rut-results:/dst2 -v "!BACKUP_DIR!\volumes:/backup:ro" alpine sh -c "mkdir -p /tmp/x && tar xzf /backup/_live_uploads.tar.gz -C /tmp/x 2>/dev/null && cp -a /tmp/x/uploaded_resources/. /dst/ 2>/dev/null && cp -a /tmp/x/real_user_traffic_results/. /dst2/ 2>/dev/null && echo 'Migration OK'" 2>nul
    ) else (
        REM Try restoring named volumes from this backup (in case they got wiped)
        if exist "!BACKUP_DIR!\volumes\uploaded-data.tar.gz" (
            echo        Restoring uploaded-data from backup...
            docker run --rm -v uploaded-data:/dst -v "!BACKUP_DIR!\volumes:/backup:ro" alpine sh -c "tar xzf /backup/uploaded-data.tar.gz -C /dst 2>/dev/null && echo 'Restore OK'" 2>nul
        )
        if exist "!BACKUP_DIR!\volumes\rut-results.tar.gz" (
            echo        Restoring rut-results from backup...
            docker run --rm -v rut-results:/dst -v "!BACKUP_DIR!\volumes:/backup:ro" alpine sh -c "tar xzf /backup/rut-results.tar.gz -C /dst 2>/dev/null && echo 'Restore OK'" 2>nul
        )
    )
) else (
    echo        uploaded-data volume preserved !VOL_EMPTY! files - skip restore
)
echo.

REM ════════════════════════════════════════════════════════════
echo [6/8] Waiting for backend (up to 90 sec)...
REM ════════════════════════════════════════════════════════════
timeout /t 12 /nobreak >nul

set "BACKEND_OK="
for /L %%i in (1,1,26) do (
    if not defined BACKEND_OK (
        powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8001/health' -TimeoutSec 4 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
        if not errorlevel 1 (
            set "BACKEND_OK=1"
            echo        Backend ready (try %%i)
        ) else (
            timeout /t 3 /nobreak >nul
        )
    )
)
if not defined BACKEND_OK (
    echo  [X] Backend nahi chala 90 sec mein.
    docker logs krexion-backend --tail 40
    pause
    exit /b 1
)
echo.

REM ════════════════════════════════════════════════════════════
echo [7/8] Force admin re-seed (delete + create fresh)...
REM ════════════════════════════════════════════════════════════
set "SEED_SCRIPT=!ROOT!\_seed_admin_tmp.py"
> "!SEED_SCRIPT!" echo import asyncio, os, bcrypt, uuid
>> "!SEED_SCRIPT!" echo from datetime import datetime, timezone
>> "!SEED_SCRIPT!" echo from motor.motor_asyncio import AsyncIOMotorClient
>> "!SEED_SCRIPT!" echo.
>> "!SEED_SCRIPT!" echo async def main():
>> "!SEED_SCRIPT!" echo     cli = AsyncIOMotorClient(os.environ.get('MONGO_URL','mongodb://mongo:27017'))
>> "!SEED_SCRIPT!" echo     db = cli[os.environ.get('DB_NAME','krexion')]
>> "!SEED_SCRIPT!" echo     email = os.environ.get('ADMIN_EMAIL','admin@krexion.local').strip().lower()
>> "!SEED_SCRIPT!" echo     pwd = os.environ.get('ADMIN_PASSWORD','admin123')
>> "!SEED_SCRIPT!" echo     ph = bcrypt.hashpw(pwd.encode(),bcrypt.gensalt()).decode()
>> "!SEED_SCRIPT!" echo     await db.users.delete_many({'email':email})
>> "!SEED_SCRIPT!" echo     doc = {
>> "!SEED_SCRIPT!" echo         'id': str(uuid.uuid4()),
>> "!SEED_SCRIPT!" echo         'email': email,
>> "!SEED_SCRIPT!" echo         'password_hash': ph,
>> "!SEED_SCRIPT!" echo         'role': 'admin',
>> "!SEED_SCRIPT!" echo         'status': 'active',
>> "!SEED_SCRIPT!" echo         'features': {
>> "!SEED_SCRIPT!" echo             'links': True, 'clicks': True, 'conversions': True,
>> "!SEED_SCRIPT!" echo             'proxies': True, 'user_agents': True, 'data_files': True,
>> "!SEED_SCRIPT!" echo             'real_user_traffic': True, 'form_filler': True,
>> "!SEED_SCRIPT!" echo             'cpi': True, 'traffic_sources': True, 'admin': True,
>> "!SEED_SCRIPT!" echo         },
>> "!SEED_SCRIPT!" echo         'created_at': datetime.now(timezone.utc).isoformat(),
>> "!SEED_SCRIPT!" echo     }
>> "!SEED_SCRIPT!" echo     await db.users.insert_one(doc)
>> "!SEED_SCRIPT!" echo     print(f'OK seeded: {email}')
>> "!SEED_SCRIPT!" echo.
>> "!SEED_SCRIPT!" echo asyncio.run(main())

docker cp "!SEED_SCRIPT!" krexion-backend:/tmp/_seed_admin.py >nul 2>&1
docker exec krexion-backend python /tmp/_seed_admin.py 2>&1
del "!SEED_SCRIPT!" >nul 2>&1
echo.

REM ════════════════════════════════════════════════════════════
echo [8/8] Login verify...
REM ════════════════════════════════════════════════════════════
timeout /t 3 /nobreak >nul

set "LOGIN_OK="
powershell -NoProfile -Command "try { $body = @{email='!ADMIN_EMAIL_VAL!';password='!ADMIN_PASS_VAL!'} ^| ConvertTo-Json; $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/admin/login' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 15; if ($r.access_token) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 set "LOGIN_OK=1"

echo.
if defined LOGIN_OK (
    color 0A
    echo  ================================================================
    echo     [SUCCESS]  ALL DONE - LOGIN WORKING
    echo  ================================================================
    echo     Admin Email   : !ADMIN_EMAIL_VAL!
    echo     Admin Password: !ADMIN_PASS_VAL!
    echo     Local URL     : http://127.0.0.1:8001
    if not "!APP_URL_VAL!"=="" echo     Public URL    : !APP_URL_VAL!
    echo     Backup        : !BACKUP_DIR!
    echo  ================================================================
    echo.
    echo     Aap login kar sakte hain:
    if not "!APP_URL_VAL!"=="" (
        echo       !APP_URL_VAL!
    ) else (
        echo       http://127.0.0.1:8001
    )
    echo.
) else (
    color 0C
    echo  ================================================================
    echo     [X]  LOGIN VERIFY FAIL - DIAGNOSIS
    echo  ================================================================
    echo     Try login manually:
    echo       Email   : !ADMIN_EMAIL_VAL!
    echo       Password: !ADMIN_PASS_VAL!
    echo.
    echo     Backend logs (last 30 lines):
    docker logs krexion-backend --tail 30
    echo  ================================================================
)
echo.

REM ════════════════════════════════════════════════════════════
REM   SETUP AUTO-WATCHER (Task Scheduler)
REM   Hard 5 minute pe GitHub check + auto-pull + rebuild
REM ════════════════════════════════════════════════════════════
if defined LOGIN_OK (
    if exist "!ROOT!\.git" (
        echo  Setting up GitHub auto-watcher (every 5 min)...
        REM Delete any existing task with this name
        schtasks /Delete /TN "KrexionAutoUpdate" /F >nul 2>&1
        REM Create scheduled task
        schtasks /Create /TN "KrexionAutoUpdate" /TR "\"%~f0\" _WATCH_" /SC MINUTE /MO 5 /RL HIGHEST /F >nul 2>&1
        if errorlevel 1 (
            echo        [!] Task Scheduler register fail. Manual mode active.
        ) else (
            echo        OK - Auto-watcher ACTIVE
            echo        Aap GitHub mein code save karein, 5 mint ke andar
            echo        khud se pull + rebuild ho jayega. Kuch karne ki zaroorat NAHI.
        )
    ) else (
        echo  Git repo nahi hai - auto-watcher skip.
    )
)
echo.
echo  ----------------------------------------------------------------
echo   Auto-watcher band karna ho:
echo     "!ROOT!\Krexion-AUTO.bat" _UNINSTALL_
echo  ----------------------------------------------------------------
echo.

endlocal
exit /b 0


REM ════════════════════════════════════════════════════════════════════
REM   WATCH_MODE — silent periodic check called by Task Scheduler
REM ════════════════════════════════════════════════════════════════════
:WATCH_MODE
setlocal EnableDelayedExpansion
set "ROOT=%~dp0"
if "!ROOT:~-1!"=="\" set "ROOT=!ROOT:~0,-1!"
set "WLOG=!ROOT!\watcher.log"

echo. >> "!WLOG!"
echo [%date% %time%] === watch tick === >> "!WLOG!"

if not exist "!ROOT!\.git" (
    echo  No git repo - exit. >> "!WLOG!"
    endlocal & exit /b 0
)

pushd "!ROOT!"
REM Get current commit
for /f "delims=" %%h in ('git rev-parse HEAD 2^>nul') do set "OLD_HEAD=%%h"
git fetch --all >> "!WLOG!" 2>&1
git reset --hard origin/main >nul 2>&1 || git reset --hard origin/master >nul 2>&1
for /f "delims=" %%h in ('git rev-parse HEAD 2^>nul') do set "NEW_HEAD=%%h"
popd

if "!OLD_HEAD!"=="!NEW_HEAD!" (
    echo  No new commits - exit. >> "!WLOG!"
    endlocal & exit /b 0
)

echo  NEW COMMITS detected: !OLD_HEAD! -^> !NEW_HEAD! >> "!WLOG!"
echo  Rebuilding... >> "!WLOG!"

REM Rebuild + restart
pushd "!ROOT!"
docker compose build >> "!WLOG!" 2>&1
docker compose up -d >> "!WLOG!" 2>&1
popd

REM Wait for backend
timeout /t 15 /nobreak >nul
for /L %%i in (1,1,15) do (
    powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8001/health' -TimeoutSec 4 -UseBasicParsing).StatusCode } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 goto WATCH_BACKEND_OK
    timeout /t 3 /nobreak >nul
)
echo  Backend ready check failed. >> "!WLOG!"
endlocal & exit /b 1

:WATCH_BACKEND_OK
echo  Backend ready - rebuild complete. >> "!WLOG!"
echo. >> "!WLOG!"
endlocal
exit /b 0


REM ════════════════════════════════════════════════════════════════════
REM   UNINSTALL_MODE — remove the scheduled task
REM ════════════════════════════════════════════════════════════════════
:UNINSTALL_MODE
NET SESSION >nul 2>&1
if errorlevel 1 (
    powershell -Command "Start-Process '%~f0' '_UNINSTALL_' -Verb RunAs"
    exit /b
)
schtasks /Delete /TN "KrexionAutoUpdate" /F 2>&1
echo.
echo  Auto-watcher band ho gaya.
pause
exit /b 0
