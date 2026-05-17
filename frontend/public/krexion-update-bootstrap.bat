@echo off
REM ============================================================
REM Krexion - One-Time Update Bootstrap
REM ------------------------------------------------------------
REM This is a small bridge tool for customers who installed
REM Krexion BEFORE v1.1.0 (without the cloud-bridge worker).
REM
REM What it does:
REM   1. Writes the local update-flag at C:\Krexion\data
REM   2. The already-running UPDATE-WATCHER.bat (Task Scheduler,
REM      every 1 minute) picks it up and rebuilds containers.
REM
REM You only need to run this ONCE. After Krexion upgrades to
REM v1.1.0 or later, every future update will be one-click from
REM the krexion.com dashboard directly.
REM ============================================================

setlocal

if "%KREXION_DIR%"=="" set KREXION_DIR=C:\Krexion

echo.
echo  ===================================================
echo   Krexion - One-Time Update Bootstrap
echo  ===================================================
echo.
echo  Install dir: %KREXION_DIR%
echo.

if not exist "%KREXION_DIR%" (
    echo  [X] %KREXION_DIR% nahi mila.
    echo      Krexion installed nahi hai is PC pe.
    echo.
    pause
    exit /b 1
)

REM Make sure the data folder exists
if not exist "%KREXION_DIR%\data" (
    mkdir "%KREXION_DIR%\data" 2>nul
)

REM Write the flag file
set FLAG=%KREXION_DIR%\data\update_requested.flag
echo {"requested_at":"%DATE% %TIME%","requested_by":"one-time-bootstrap","via":"bootstrap.bat"} > "%FLAG%"

if not exist "%FLAG%" (
    echo  [X] Flag file create nahi ho saka:
    echo      %FLAG%
    echo.
    echo  Possible cause: PC ko Admin rights chahye.
    echo  Solution: Yeh file right-click "Run as administrator"
    echo  karein.
    echo.
    pause
    exit /b 1
)

echo  [OK] Update flag written:
echo       %FLAG%
echo.
echo  Krexion update next 1 minute mein automatically shoro hoga.
echo  Total time ~5-10 min. Krexion thodi der ke liye band rahe ga.
echo.
echo  Update khatam hone ke baad krexion.com pe wapas jayein -
echo  header mein green "PC connected" badge dikhna chahye.
echo.
echo  Aage se updates direct krexion.com Update button se chalein
echo  ge - yeh file phir kabhi chalane ki zaroorat nahi hogi.
echo.

REM Try to invoke the watcher right away so the customer doesn't have
REM to wait for the next scheduled minute. Falls back silently if the
REM task scheduler refuses.
schtasks /Run /TN "KrexionUpdateWatcher" >nul 2>&1
if errorlevel 1 (
    echo  Note: Auto-run watcher trigger fail - aap ko 1 min wait karna
    echo        padega (Task Scheduler khud chala dega).
) else (
    echo  Update process abhi start ho gaya hai. Wait karein...
)

echo.
echo  ===================================================
pause
endlocal
exit /b 0
