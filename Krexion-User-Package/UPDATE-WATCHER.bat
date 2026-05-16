@echo off
REM ============================================================
REM Krexion - Update Watcher
REM ------------------------------------------------------------
REM Runs every minute via Windows Task Scheduler.
REM Watches for the update flag written by the local backend
REM at /data/update_requested.flag (mounted into the container)
REM and on the host at: %INSTALL_DIR%\data\update_requested.flag
REM
REM When found:
REM   1. docker compose pull
REM   2. docker compose up -d --build
REM   3. delete the flag
REM ============================================================

if "%KREXION_DIR%"=="" set KREXION_DIR=C:\Krexion
cd /d "%KREXION_DIR%" 2>nul || exit /b 0

set FLAG=%KREXION_DIR%\data\update_requested.flag
if not exist "%FLAG%" exit /b 0

echo [%DATE% %TIME%] Krexion update flag detected — starting update >> "%KREXION_DIR%\updater.log"

REM Pull any new images (no-op if customer builds locally)
docker compose pull >> "%KREXION_DIR%\updater.log" 2>&1

REM Rebuild + restart
docker compose up -d --build >> "%KREXION_DIR%\updater.log" 2>&1

if errorlevel 1 (
    echo [%DATE% %TIME%] Update FAILED >> "%KREXION_DIR%\updater.log"
    exit /b 1
)

echo [%DATE% %TIME%] Update applied successfully >> "%KREXION_DIR%\updater.log"

REM Remove flag so we don't loop
del /f "%FLAG%" 2>nul
exit /b 0
