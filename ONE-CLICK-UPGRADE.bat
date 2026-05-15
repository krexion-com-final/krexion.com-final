@echo off
setlocal EnableDelayedExpansion
title Krexion - One Click Upgrade
color 0A

REM ====================================================================
REM   Krexion ONE-CLICK UPGRADE
REM   ─────────────────────────
REM   Double-click karo. Bas. Wait and see.
REM
REM   Ye script kya karega:
REM     1. Docker containers band karega
REM     2. .env aur mongo-data ka backup banayega
REM     3. Naya code purane folder par copy karega (data safe)
REM     4. Containers rebuild karke start karega
REM     5. Status dikhayega
REM ====================================================================

REM ───── PATHS (aap ke system ke according hardcoded) ─────
set "OLD_PATH=F:\online\real flow\real flow amna\krexion-amna-main\krexion-amna-main"
set "NEW_PATH=F:\online\real flow\lenovo real flow\lenovo-krexion-main\lenovo-krexion-main"
set "BACKUP_ROOT=F:\online\real flow\krexion-backups"

cls
echo.
echo  ============================================================
echo    Krexion - ONE CLICK UPGRADE
echo  ============================================================
echo.
echo    Old install : %OLD_PATH%
echo    New code    : %NEW_PATH%
echo    Backup to   : %BACKUP_ROOT%
echo.
echo    Bas wait karo - 3 to 5 minutes lagein ge.
echo  ============================================================
echo.
timeout /t 3 /nobreak >nul

REM ───── [0/6] Verify paths exist ─────
echo [0/6] Paths verify kar raha hun...
if not exist "%OLD_PATH%\docker-compose.yml" (
    echo.
    echo  [ERROR] Old install path par docker-compose.yml nahi mila!
    echo          Path: %OLD_PATH%
    echo.
    pause
    exit /b 1
)
if not exist "%NEW_PATH%\docker-compose.yml" (
    echo.
    echo  [ERROR] New code path par docker-compose.yml nahi mila!
    echo          Path: %NEW_PATH%
    echo          Kya aap ne file extract ki hai?
    echo.
    pause
    exit /b 1
)
echo        OK - Dono paths sahi hain.
echo.

REM ───── [1/6] Docker check ─────
echo [1/6] Docker Desktop check kar raha hun...
docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Docker Desktop chalu nahi hai!
    echo          Start menu se Docker Desktop kholein, phir ye script dobara chalayein.
    echo.
    pause
    exit /b 1
)
echo        OK - Docker chal raha hai.
echo.

REM ───── [2/6] Stop old containers ─────
echo [2/6] Purane containers band kar raha hun...
pushd "%OLD_PATH%"
docker compose down --remove-orphans
popd
echo        OK - Containers band ho gaye.
echo.

REM ───── [3/6] Safety backup ─────
echo [3/6] Backup bana raha hun (.env + mongo-data)...
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "TS=%dt:~0,8%-%dt:~8,6%"
set "BACKUP_DIR=%BACKUP_ROOT%\backup-%TS%"

if not exist "%BACKUP_ROOT%" mkdir "%BACKUP_ROOT%"
mkdir "%BACKUP_DIR%"

REM Backup all .env files (recursive)
pushd "%OLD_PATH%"
for /r %%F in (.env) do (
    if exist "%%F" (
        set "REL=%%F"
        set "REL=!REL:%OLD_PATH%\=!"
        set "DEST=%BACKUP_DIR%\!REL!"
        for %%D in ("!DEST!") do if not exist "%%~dpD" mkdir "%%~dpD" >nul 2>&1
        copy /Y "%%F" "!DEST!" >nul
        echo        Backed up: !REL!
    )
)
popd

REM Backup mongo-data (if exists)
if exist "%OLD_PATH%\mongo-data" (
    echo        mongo-data copy ho raha hai... (ye thori der le sakta hai)
    robocopy "%OLD_PATH%\mongo-data" "%BACKUP_DIR%\mongo-data" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP >nul
    echo        OK - mongo-data backed up.
) else (
    echo        Note: mongo-data folder nahi mila (pehli baar deploy ho raha?).
)
echo        OK - Backup ready: %BACKUP_DIR%
echo.

REM ───── [4/6] Robocopy new code over old ─────
echo [4/6] Naya code copy kar raha hun (.env + mongo-data SAFE rahein ge)...
echo.
robocopy "%NEW_PATH%" "%OLD_PATH%" /MIR /R:2 /W:2 /MT:8 ^
    /XD "mongo-data" "node_modules" ".git" "__pycache__" "venv" ".venv" "build" "dist" "logs" ".pytest_cache" ".idea" ".vscode" ^
    /XF ".env" "*.local.env" ^
    /NFL /NDL /NJH /NJS /NC /NS /NP

REM Robocopy ke exit codes 0-7 success, 8+ error
if %ERRORLEVEL% GEQ 8 (
    echo.
    echo  [ERROR] Robocopy fail ho gaya. Exit code: %ERRORLEVEL%
    echo          Backup safe hai: %BACKUP_DIR%
    echo.
    pause
    exit /b 1
)
echo        OK - Naya code apply ho gaya.
echo.

REM ───── [5/6] Rebuild and start ─────
echo [5/6] Containers rebuild kar raha hun (3-5 minute lagein ge)...
echo.
pushd "%OLD_PATH%"
docker compose build
if errorlevel 1 (
    echo.
    echo  [ERROR] Docker build fail. Logs ke liye:
    echo          cd "%OLD_PATH%" ^&^& docker compose logs
    echo.
    popd
    pause
    exit /b 1
)

echo.
echo        Services start ho rahi hain...

REM Detect if TUNNEL_TOKEN is set in .env
findstr /R "^TUNNEL_TOKEN=." .env >nul 2>&1
if errorlevel 1 (
    docker compose up -d
) else (
    docker compose --profile tunnel up -d
)
popd
echo        OK - Services chal pari hain.
echo.

REM ───── [6/6] Status ─────
echo [6/6] Final status:
echo.
pushd "%OLD_PATH%"
docker compose ps
popd
echo.

REM ───── Done ─────
echo  ============================================================
echo    UPGRADE COMPLETE!
echo  ============================================================
echo.
echo    Backup location: %BACKUP_DIR%
echo.
echo    Ab kya karein:
echo      1. Apna Krexion URL browser mein kholein
echo      2. Login karein (admin@krexion.local / admin123)
echo      3. Sidebar mein "CPI Module" dropdown dikhega
echo      4. Phir CPI Worker setup karein (Android phone connect karne ke liye)
echo.
echo    Logs check karne ke liye: KREXION-LOGS.bat
echo    Containers band karne ke liye: KREXION-STOP.bat
echo.
echo  ============================================================
echo.
pause
endlocal
