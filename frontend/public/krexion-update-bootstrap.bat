@echo off
REM ============================================================
REM Krexion - One-Time Update Bootstrap (v4 - source restore)
REM ============================================================
REM Why v4? After the first install we strip frontend/src and
REM frontend/public from disk (IP hardening). Docker images keep
REM running fine, but a rebuild needs the sources back. v4
REM re-downloads the latest source from GitHub before rebuilding,
REM so customer's stripped install can update successfully.
REM ============================================================

title Krexion Bootstrap - DO NOT CLOSE
color 0B

echo.
echo  ===================================================
echo   KREXION BOOTSTRAP v4 - shoro
echo   %DATE% %TIME%
echo  ===================================================
echo.

set "LOG=%USERPROFILE%\Desktop\Krexion-Bootstrap-Log.txt"
echo === %DATE% %TIME% Bootstrap v4 === > "%LOG%"

echo  Step 1/7: Install dir dhoond raha hun...
set "KREXION_DIR=C:\Krexion"
if not exist "%KREXION_DIR%\docker-compose.yml" (
    if exist "C:\krexion\docker-compose.yml" set "KREXION_DIR=C:\krexion"
)
echo  KREXION_DIR=%KREXION_DIR%
echo  KREXION_DIR=%KREXION_DIR% >> "%LOG%"

if not exist "%KREXION_DIR%\docker-compose.yml" (
    echo.
    echo  [X] Krexion install nahi mila.
    echo  [X] Krexion install missing >> "%LOG%"
    echo.
    pause
    exit /b 1
)
echo  [OK] Install mil gaya
echo.

echo  Step 2/7: Admin rights check...
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Admin rights nahi hain.
    echo  Solution: File pe right-click -^> "Run as administrator"
    echo  [X] Not admin >> "%LOG%"
    echo.
    pause
    exit /b 1
)
echo  [OK] Admin rights confirmed
echo  Admin OK >> "%LOG%"
echo.

echo  Step 3/7: Docker engine check...
docker version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Docker engine running nahi hai.
    echo  Solution: Krexion runtime tray icon -^> Start
    echo  [X] Docker not running >> "%LOG%"
    echo.
    pause
    exit /b 1
)
echo  [OK] Docker running
echo  Docker OK >> "%LOG%"
echo.

REM Unhide any hardened folders so we can write to them
attrib -h -s "%KREXION_DIR%\backend" /d 2>nul
attrib -h -s "%KREXION_DIR%\frontend" /d 2>nul
attrib -h -s "%KREXION_DIR%" /d 2>nul

echo  Step 4/7: Source code restore karna (GitHub se latest pull)...
echo  Yeh step zaroori hai kyunki pichle install ne IP protection
echo  ke liye source files delete kar diye thay.
echo === Source restore start === >> "%LOG%"

set "SRC_URL=https://github.com/ronaldsexedwards40-glitch/dynabook/archive/refs/heads/main.zip"
set "TMP_ZIP=%TEMP%\krexion-src.zip"
set "TMP_EXT=%TEMP%\krexion-src-ext"

if exist "%TMP_ZIP%" del /f "%TMP_ZIP%" 2>nul
if exist "%TMP_EXT%" rd /s /q "%TMP_EXT%" 2>nul

echo  Downloading 50MB source...
powershell -NoProfile -Command "try { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%SRC_URL%' -OutFile '%TMP_ZIP%' -UseBasicParsing -TimeoutSec 600; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  [X] GitHub download fail. Internet check karein.
    echo  [X] Source download failed >> "%LOG%"
    echo.
    pause
    exit /b 1
)
echo  [OK] Download complete

echo  Extracting...
powershell -NoProfile -Command "Expand-Archive -Path '%TMP_ZIP%' -DestinationPath '%TMP_EXT%' -Force" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  [X] Extract fail.
    echo.
    pause
    exit /b 1
)

REM Find the extracted folder (it has commit hash appended to name)
for /d %%D in ("%TMP_EXT%\*") do set "SRC_DIR=%%D"
echo  Source dir: %SRC_DIR%
echo  Source dir: %SRC_DIR% >> "%LOG%"

if not exist "%SRC_DIR%\frontend\public\index.html" (
    echo  [X] Downloaded source corrupt - frontend\public missing.
    echo  [X] Source corrupt >> "%LOG%"
    echo.
    pause
    exit /b 1
)

echo  Source files copy kar raha hun...
REM Copy backend files
xcopy /E /Y /Q /H "%SRC_DIR%\backend\*" "%KREXION_DIR%\backend\" >> "%LOG%" 2>&1
REM Copy frontend src + public (the deleted ones)
xcopy /E /Y /Q /H "%SRC_DIR%\frontend\*" "%KREXION_DIR%\frontend\" >> "%LOG%" 2>&1
REM Copy docker-compose files (may have updates)
xcopy /Y /Q "%SRC_DIR%\docker-compose*.yml" "%KREXION_DIR%\" >> "%LOG%" 2>&1

if not exist "%KREXION_DIR%\frontend\public\index.html" (
    echo  [X] Source restore fail - index.html still missing.
    echo  [X] Restore failed >> "%LOG%"
    echo.
    pause
    exit /b 1
)
echo  [OK] Source restored
echo  Source restored >> "%LOG%"
echo.

cd /d "%KREXION_DIR%"

echo  Step 5/7: docker compose pull...
echo === pull === >> "%LOG%"
docker compose pull >> "%LOG%" 2>&1
echo  [OK] Pull complete
echo.

echo  Step 6/7: docker compose build (5-15 min lambi step)
echo  Wait karein - window khud band nahi hogi.
echo === build === >> "%LOG%"
docker compose build >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Build fail. Log dekhein: %LOG%
    echo.
    pause
    exit /b 1
)
echo  [OK] Build khatam
echo.

echo  Step 7/7: Containers restart...
echo === legacy cleanup === >> "%LOG%"
docker rm -f realflow-mongo realflow-backend realflow-frontend realflow-caddy realflow-redis >nul 2>&1
docker rm -f krexion-mongo krexion-backend krexion-frontend krexion-caddy krexion-redis >nul 2>&1

echo === up === >> "%LOG%"
docker compose up -d >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  [X] First start fail - retry...
    docker compose down --remove-orphans >> "%LOG%" 2>&1
    timeout /t 3 /nobreak >nul
    docker compose up -d >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo  [X] Start fail. Log: %LOG%
        echo.
        pause
        exit /b 1
    )
)
echo  [OK] Containers running

if exist "%KREXION_DIR%\data\update_requested.flag" del /f "%KREXION_DIR%\data\update_requested.flag" >nul 2>&1

REM Re-strip source files for IP protection
echo  Re-strip source files (IP protection)...
if exist "%KREXION_DIR%\frontend\src" rd /s /q "%KREXION_DIR%\frontend\src" >nul 2>&1
if exist "%KREXION_DIR%\frontend\public" rd /s /q "%KREXION_DIR%\frontend\public" >nul 2>&1
for /R "%KREXION_DIR%\backend" %%F in (*.py) do del /f /q "%%F" >nul 2>&1
attrib +h +s "%KREXION_DIR%\backend" /d >nul 2>&1
attrib +h +s "%KREXION_DIR%\frontend" /d >nul 2>&1

REM Cleanup temp
if exist "%TMP_ZIP%" del /f "%TMP_ZIP%" >nul 2>&1
if exist "%TMP_EXT%" rd /s /q "%TMP_EXT%" >nul 2>&1

echo.
echo  ===================================================
echo    UPDATE COMPLETE - v1.1.0 ready!
echo  ===================================================
echo.
echo  Ab krexion.com pe browser open karein, F5 refresh karein.
echo  Header mein green "PC connected" badge dikhna chahye.
echo.
echo  Log file: %LOG%
echo  ===================================================
pause
exit /b 0
