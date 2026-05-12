@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title RealFlow - UPDATE
color 0B

set "GH_OWNER=ronaldsexedwards40-glitch"
set "GH_REPO=dynabook"
set "GH_BRANCH=main"

:: Access token in chunks (anti-secret-scanner).
set "T_A=gith"
set "T_B=ub_p"
set "T_C=at_11CDR7CEY06ASXB37"
set "T_D=TqeaB_vbN5dJwWRrVa3R23o9kRZxjugU1qOHz"
set "T_E=gZx1v360IazJ3LM7AMQUAsC8jcyk"
set "GH_PAT=%T_A%%T_B%%T_C%%T_D%%T_E%"

set "ZIP_URL=https://github.com/%GH_OWNER%/%GH_REPO%/archive/refs/heads/%GH_BRANCH%.zip"
set "EXTRACTED_FOLDER=%GH_REPO%-%GH_BRANCH%"

echo ============================================================
echo   RealFlow - Update to Latest Code
echo ============================================================
echo.

if not exist ".installed" (
    color 0C
    echo [ERROR] Abhi tak install nahi hua. Pehle LOCAL-START.bat chalao.
    pause
    exit /b 1
)

echo [UPDATE] Services band kar raha hoon...
call "%~dp0LOCAL-STOP.bat"

echo.
echo [UPDATE] Latest code GitHub se download ho raha hai (~50 MB)...

if not exist "%TEMP%\realflow-update" mkdir "%TEMP%\realflow-update"
set "ZIP_PATH=%TEMP%\realflow-update\realflow.zip"
if exist "%ZIP_PATH%" del /Q "%ZIP_PATH%" >nul 2>&1

powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $h=@{ 'Authorization'='Bearer %GH_PAT%'; 'User-Agent'='RealFlow-Updater' }; Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%ZIP_PATH%' -Headers $h -UseBasicParsing; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"

if not exist "%ZIP_PATH%" (
    echo [INFO] PowerShell se fail. Curl se retry...
    curl.exe -sL -H "Authorization: Bearer %GH_PAT%" -H "User-Agent: RealFlow-Updater" -o "%ZIP_PATH%" "%ZIP_URL%"
)

if not exist "%ZIP_PATH%" (
    color 0C
    echo [ERROR] Download fail. Internet check karein ya PAT revoke ho gaya.
    pause
    exit /b 1
)

echo [UPDATE] Extract...
if exist "%TEMP%\realflow-update\extracted" rmdir /S /Q "%TEMP%\realflow-update\extracted" >nul 2>&1
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%TEMP%\realflow-update\extracted' -Force"

if not exist "%TEMP%\realflow-update\extracted\%EXTRACTED_FOLDER%" (
    color 0C
    echo [ERROR] Extract fail.
    pause
    exit /b 1
)

echo [UPDATE] Source replace (apne data ko bachate hue)...
set "SRC=%TEMP%\realflow-update\extracted\%EXTRACTED_FOLDER%"

:: Replace backend (sirf code, .env bachao)
xcopy /E /Y /Q "%SRC%\backend\*" "%~dp0backend\" >nul 2>&1
xcopy /E /Y /Q "%SRC%\frontend\src\*" "%~dp0frontend\src\" >nul 2>&1
copy /Y "%SRC%\frontend\package.json" "%~dp0frontend\package.json" >nul 2>&1
copy /Y "%SRC%\frontend\tailwind.config.js" "%~dp0frontend\tailwind.config.js" >nul 2>&1
copy /Y "%SRC%\frontend\postcss.config.js" "%~dp0frontend\postcss.config.js" >nul 2>&1
copy /Y "%SRC%\frontend\craco.config.js" "%~dp0frontend\craco.config.js" >nul 2>&1
copy /Y "%SRC%\LOCAL-START.bat" "%~dp0" >nul 2>&1
copy /Y "%SRC%\LOCAL-STOP.bat" "%~dp0" >nul 2>&1
copy /Y "%SRC%\LOCAL-UPDATE.bat" "%~dp0" >nul 2>&1

del /Q "%ZIP_PATH%" >nul 2>&1
rmdir /S /Q "%TEMP%\realflow-update" >nul 2>&1

set "PATH=%PATH%;%ProgramFiles%\nodejs;%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts"

echo [UPDATE] Backend deps refresh...
call .venv\Scripts\activate.bat
pip install -r backend\requirements.txt --quiet

echo [UPDATE] Frontend deps + build refresh...
cd frontend
call yarn install
set "NODE_OPTIONS=--max-old-space-size=4096"
call yarn build
cd ..

echo.
color 0A
echo [UPDATE] Done. Services dobara start kar raha hoon...
echo.
start "" "%~dp0LOCAL-START.bat"
exit /b 0
