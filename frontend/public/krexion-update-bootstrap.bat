@echo off
REM ============================================================
REM Krexion - One-Time Update Bootstrap (v2 - bulletproof)
REM ------------------------------------------------------------
REM Yeh script DIRECTLY rebuild karta hai - flag file pe depend
REM nahi karta. Plus saari output Desktop pe log file mein
REM jaati hai, taa k agar script crash ho to wajah pata chal jaye.
REM ============================================================

REM Force the window to stay open NO MATTER WHAT happens below.
REM This prevents the "popup khulte hi band" problem completely.
cmd /k call "%~f0" :run
exit /b 0

:run
echo.
echo  ===================================================
echo   Krexion - One-Time Update Bootstrap v2
echo  ===================================================
echo.

REM Log everything to Desktop so customer can attach it on failure
set LOG=%USERPROFILE%\Desktop\Krexion-Bootstrap-Log.txt
echo === Krexion Bootstrap started at %DATE% %TIME% === > "%LOG%"
echo USERPROFILE=%USERPROFILE% >> "%LOG%"

REM Find Krexion install dir (case-insensitive on Windows)
set "KREXION_DIR=C:\Krexion"
if not exist "%KREXION_DIR%\docker-compose.yml" (
    if exist "C:\krexion\docker-compose.yml" set "KREXION_DIR=C:\krexion"
)
echo KREXION_DIR=%KREXION_DIR% >> "%LOG%"
echo  Install dir: %KREXION_DIR%
echo.

if not exist "%KREXION_DIR%\docker-compose.yml" (
    echo  [X] Krexion install nahi mila ^(C:\Krexion ya C:\krexion mein^).
    echo  [X] Krexion install missing >> "%LOG%"
    echo.
    echo  Solution: Krexion-User-Package se INSTALL.bat dobara chalayein.
    goto end
)

REM Verify admin rights
net session >nul 2>&1
if errorlevel 1 (
    echo  [X] Yeh window admin rights se nahi chal rahi.
    echo  [X] Not admin >> "%LOG%"
    echo.
    echo  Solution: File pe right-click karein, "Run as administrator"
    echo            select karein, phir dobara try karein.
    goto end
)
echo  [OK] Admin rights confirmed
echo  Admin OK >> "%LOG%"

REM Verify docker is reachable
docker version >nul 2>&1
if errorlevel 1 (
    echo  [X] Docker engine running nahi hai.
    echo  [X] Docker not running >> "%LOG%"
    echo.
    echo  Solution:
    echo    1. System tray mein "Krexion runtime" icon look karein
    echo    2. Right-click - Start / Resume
    echo    3. 30 sec wait karein
    echo    4. Phir yeh file dobara chalayein.
    goto end
)
echo  [OK] Docker running
echo  Docker OK >> "%LOG%"

cd /d "%KREXION_DIR%"
if errorlevel 1 (
    echo  [X] Cannot cd to %KREXION_DIR%
    echo  [X] cd failed >> "%LOG%"
    goto end
)

echo.
echo  ===================================================
echo   Krexion update shoro kar raha hun ^(5-15 min^)...
echo  ===================================================
echo.
echo  Pyaarse wait karein - yeh window khud band nahi hogi.
echo  Aap dosri kaam karein, yeh background mein chalti rahegi.
echo.

REM Step 1: Pull any pre-built images (no-op for our build-from-source flow)
echo  [1/3] docker compose pull...
echo === Step 1: docker compose pull === >> "%LOG%"
docker compose pull >> "%LOG%" 2>&1
echo  [OK] Pull complete

REM Step 2: Build (this is the long step - 5-15 min)
echo  [2/3] docker compose build ^(5-15 min - yeh sabse lambi step hai^)...
echo === Step 2: docker compose build === >> "%LOG%"
docker compose build >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  [X] Build failed - log file Desktop pe dekhein:
    echo      %LOG%
    echo  [X] Build failed >> "%LOG%"
    goto end
)
echo  [OK] Build complete

REM Step 3: Restart containers (legacy cleanup first to avoid name conflicts)
echo  [3/3] docker compose up -d ^(containers restart^)...
echo === Step 3: legacy cleanup + up === >> "%LOG%"
docker rm -f realflow-mongo realflow-backend realflow-frontend realflow-caddy realflow-redis 2>nul
docker rm -f krexion-mongo krexion-backend krexion-frontend krexion-caddy krexion-redis 2>nul
docker compose up -d >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  [X] Start failed - retrying after cleanup...
    docker compose down --remove-orphans >> "%LOG%" 2>&1
    timeout /t 3 /nobreak >nul
    docker compose up -d >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo  [X] Start failed permanently - check log:
        echo      %LOG%
        goto end
    )
)
echo  [OK] Containers running

REM Clean up the legacy update flag (so we don't loop on next watcher run)
if exist "%KREXION_DIR%\data\update_requested.flag" del /f "%KREXION_DIR%\data\update_requested.flag" 2>nul

echo.
echo  ===================================================
echo    UPDATE COMPLETE - Krexion v1.1.0 ready hai!
echo  ===================================================
echo.
echo  Ab krexion.com pe browser open karein, F5 refresh karein.
echo  Header mein green "PC connected" badge dikhna chahye.
echo.
echo  Aage se updates direct krexion.com Update button se honge.
echo  Yeh bootstrap file phir kabhi nahi chahye.
echo.
echo  Log file: %LOG%
echo.

:end
echo.
echo  ===================================================
echo  Window khuli rahegi - press kuch ka close karein.
echo  ===================================================
pause
exit /b 0
