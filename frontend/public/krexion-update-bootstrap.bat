@echo off
REM ============================================================
REM Krexion - One-Time Update Bootstrap (v3 - flat, no tricks)
REM ============================================================

title Krexion Bootstrap - DO NOT CLOSE
color 0B

echo.
echo  ===================================================
echo   KREXION BOOTSTRAP v3 - shoro
echo   %DATE% %TIME%
echo  ===================================================
echo.

set "LOG=%USERPROFILE%\Desktop\Krexion-Bootstrap-Log.txt"
echo === %DATE% %TIME% === > "%LOG%"

echo  Step 1/6: Install dir dhoond raha hun...
set "KREXION_DIR=C:\Krexion"
if not exist "%KREXION_DIR%\docker-compose.yml" (
    if exist "C:\krexion\docker-compose.yml" set "KREXION_DIR=C:\krexion"
)
echo  KREXION_DIR=%KREXION_DIR%
echo  KREXION_DIR=%KREXION_DIR% >> "%LOG%"

if not exist "%KREXION_DIR%\docker-compose.yml" (
    echo.
    echo  [X] Krexion install nahi mila C:\Krexion ya C:\krexion mein.
    echo  [X] Krexion install missing >> "%LOG%"
    echo.
    echo  Solution: Krexion-User-Package se INSTALL.bat dobara chalayein.
    echo.
    pause
    exit /b 1
)
echo  [OK] Install mil gaya
echo.

echo  Step 2/6: Admin rights check...
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Admin rights nahi hain.
    echo  [X] Not admin >> "%LOG%"
    echo.
    echo  Solution: Yeh file pe right-click -^> "Run as administrator"
    echo.
    pause
    exit /b 1
)
echo  [OK] Admin rights confirmed
echo  Admin OK >> "%LOG%"
echo.

echo  Step 3/6: Docker engine check...
docker version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Docker engine running nahi hai.
    echo  [X] Docker not running >> "%LOG%"
    echo.
    echo  Solution:
    echo    1. System tray mein "Krexion runtime" icon dhoondein
    echo    2. Right-click -^> Start / Resume
    echo    3. 30 sec wait karein
    echo    4. Phir yeh file dobara chalayein
    echo.
    pause
    exit /b 1
)
echo  [OK] Docker running
echo  Docker OK >> "%LOG%"
echo.

cd /d "%KREXION_DIR%"

echo  Step 4/6: docker compose pull...
echo === pull start === >> "%LOG%"
docker compose pull >> "%LOG%" 2>&1
echo  [OK] Pull khatam ^(skipped if no images^)
echo.

echo  Step 5/6: docker compose build ^(5-15 min lambi step^)
echo  Yeh sabse lambi step hai. Wait karein - window khud rahegi.
echo === build start === >> "%LOG%"
docker compose build >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Build fail ho gaya.
    echo.
    echo  Wajah ke liye log file dekhein:
    echo    %LOG%
    echo.
    echo  Yeh log file mujhe attach kar k bhejein.
    echo.
    pause
    exit /b 1
)
echo  [OK] Build khatam
echo.

echo  Step 6/6: Containers restart...
echo === legacy cleanup === >> "%LOG%"
docker rm -f realflow-mongo realflow-backend realflow-frontend realflow-caddy realflow-redis >nul 2>&1
docker rm -f krexion-mongo krexion-backend krexion-frontend krexion-caddy krexion-redis >nul 2>&1

echo === up start === >> "%LOG%"
docker compose up -d >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo  [X] First start fail - cleanup karke retry...
    docker compose down --remove-orphans >> "%LOG%" 2>&1
    timeout /t 3 /nobreak >nul
    docker compose up -d >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo  [X] Start permanently fail - log check karein:
        echo      %LOG%
        echo.
        pause
        exit /b 1
    )
)
echo  [OK] Containers running

REM Clean up legacy flag file
if exist "%KREXION_DIR%\data\update_requested.flag" del /f "%KREXION_DIR%\data\update_requested.flag" >nul 2>&1

echo.
echo  ===================================================
echo    UPDATE COMPLETE - v1.1.0 ready!
echo  ===================================================
echo.
echo  Ab krexion.com pe browser open karein.
echo  F5 refresh karein.
echo.
echo  Header mein green "PC connected" badge dikhna chahye.
echo.
echo  Aage se updates direct krexion.com Update button se honge.
echo.
echo  Log file: %LOG%
echo.
echo  ===================================================
pause
exit /b 0
