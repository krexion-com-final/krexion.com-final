@echo off
title Krexion - Diagnostic Test
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ================================================================
echo   DIAGNOSTIC TEST - Yeh window kabhi band nahi hogi
echo ================================================================
echo.
echo  Aap is window mein har step ka result dekh sakte hain.
echo  Agar START-CPI.bat silent close ho rahi hai to yeh chalayein.
echo.
pause

echo.
echo --- TEST 1: Working Directory ---
echo Current folder: %CD%
echo Script path: %~dp0
pause

echo.
echo --- TEST 2: Python ---
where python
python --version
echo Errorlevel: %errorlevel%
pause

echo.
echo --- TEST 3: ADB ---
if exist "%~dp0platform-tools\adb.exe" (
    set "PATH=%~dp0platform-tools;!PATH!"
    echo Bundled ADB found
)
where adb
adb version
echo Errorlevel: %errorlevel%
pause

echo.
echo --- TEST 4: Required Files ---
if exist worker.py (echo worker.py: OK) else (echo worker.py: MISSING)
if exist requirements.txt (echo requirements.txt: OK) else (echo requirements.txt: MISSING)
if exist config.example.yaml (echo config.example.yaml: OK) else (echo config.example.yaml: MISSING)
if exist config.yaml (echo config.yaml: OK) else (echo config.yaml: NOT YET CREATED)
if exist krexion_cpi_worker\worker.py (echo package: probably present)
dir /B *.py *.yaml *.bat *.txt 2>nul
pause

echo.
echo --- TEST 5: ADB devices ---
adb kill-server >nul 2>&1
timeout /t 2 /nobreak >nul
adb start-server >nul 2>&1
timeout /t 2 /nobreak >nul
adb devices
pause

echo.
echo --- TEST 6: Internet (ping google) ---
ping -n 2 8.8.8.8
pause

echo.
echo --- TEST 7: Python packages list ---
python -m pip list 2>&1 | findstr /I "httpx pyyaml appium tenacity"
pause

echo.
echo ================================================================
echo  DIAGNOSTIC COMPLETE
echo  Agar yahan tak pohanche to .bat files theek chal rahi hain.
echo  Ab START-CPI.bat dobara try karein.
echo ================================================================
pause
endlocal
