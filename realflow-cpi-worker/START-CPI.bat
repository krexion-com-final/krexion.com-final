@echo off
title RealFlow CPI Worker
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ================================================================
echo    REALFLOW CPI WORKER - ONE CLICK LAUNCHER
echo ================================================================
echo.

REM ==================== STEP 1: Python ====================
echo [1/7] Python check...
where python >nul 2>&1
if errorlevel 1 goto no_python
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo      OK - !PYVER!
goto step2

:no_python
echo.
echo  [X] Python install nahi hai!
echo.
echo  HALL: https://www.python.org/downloads/ se Python 3.10+ install karein.
echo  Installation ke waqt "Add Python to PATH" check karna ZARURI hai.
echo.
pause
exit /b 1

REM ==================== STEP 2: ADB ====================
:step2
echo.
echo [2/7] ADB check...
set "ADB_FOUND=0"
where adb >nul 2>&1
if not errorlevel 1 set "ADB_FOUND=1"
if exist "%~dp0platform-tools\adb.exe" (
    set "PATH=%~dp0platform-tools;!PATH!"
    set "ADB_FOUND=1"
)
if !ADB_FOUND! EQU 1 goto adb_ok

echo      ADB nahi mila - auto-download 50 MB...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile '%~dp0_pt.zip' -UseBasicParsing; Expand-Archive -Path '%~dp0_pt.zip' -DestinationPath '%~dp0' -Force; Remove-Item '%~dp0_pt.zip' -Force; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 goto adb_dl_fail
set "PATH=%~dp0platform-tools;!PATH!"
echo      OK - ADB install ho gaya
goto step3

:adb_dl_fail
echo  [X] Auto-download fail.
echo     Manually download:
echo     https://dl.google.com/android/repository/platform-tools-latest-windows.zip
echo     Extract karke "platform-tools" folder is .bat ke saath rakhein.
pause
exit /b 1

:adb_ok
echo      OK - ADB ready

REM ==================== STEP 3: Python Packages ====================
:step3
echo.
echo [3/7] Python packages check...
if exist "%~dp0.deps_v4_installed" goto deps_ok
echo      Pehli baar setup - 2-3 mint lagengae...
echo      Using --user flag (no admin needed)...
python -m pip install --user --upgrade pip --quiet --disable-pip-version-check 2>nul
python -m pip install --user -r "%~dp0requirements.txt" --disable-pip-version-check
if errorlevel 1 goto deps_retry_no_user
echo done > "%~dp0.deps_v4_installed"
echo      OK - Saare packages install
goto step4

:deps_retry_no_user
echo.
echo      [!] User-install fail - retry without --user flag...
python -m pip install -r "%~dp0requirements.txt" --disable-pip-version-check
if errorlevel 1 goto deps_fail
echo done > "%~dp0.deps_v4_installed"
echo      OK - Saare packages install
goto step4

:deps_fail
echo.
echo  [X] Packages install fail.
echo     Wajah: Python permissions ya internet issue.
echo.
echo     SOLUTION:
echo     1. Right-click START-CPI.bat - "Run as administrator"
echo        (Admin mode mein retry karein)
echo     2. YA manually CMD me:
echo        python -m pip install --user -r requirements.txt
echo.
pause
exit /b 1

:deps_ok
echo      OK - Packages ready

REM ==================== STEP 4: Config ====================
:step4
echo.
echo [4/7] Config check...
if not exist "%~dp0config.yaml" (
    copy "%~dp0config.example.yaml" "%~dp0config.yaml" >nul 2>&1
    echo      Naya config.yaml banaya
    notepad "%~dp0config.yaml"
)

findstr /C:"PASTE_YOUR_REALFLOW_JWT_HERE" "%~dp0config.yaml" >nul 2>&1
if errorlevel 1 goto config_ok
echo.
echo  [X] config.yaml mein TOKEN paste nahi hua hai!
echo.
echo  TOKEN KAHAN SE LE:
echo    1. https://realflow.online par login karein
echo    2. F12 dabayein - DevTools khulega
echo    3. Application tab - Local Storage - https://realflow.online
echo    4. "token" key dhundhein - lambi value copy karein
echo    5. Notepad mein PASTE_YOUR_REALFLOW_JWT_HERE replace karein
echo    6. Ctrl+S Save karein
echo.
notepad "%~dp0config.yaml"
echo.
echo  Save karne ke baad koi key dabao continue ke liye...
pause
findstr /C:"PASTE_YOUR_REALFLOW_JWT_HERE" "%~dp0config.yaml" >nul 2>&1
if not errorlevel 1 goto token_still_missing
goto config_ok

:token_still_missing
echo  [X] Token abhi bhi paste nahi hua. Exit.
pause
exit /b 1

:config_ok
echo      OK - Config valid

REM ==================== STEP 5: Phone ====================
:step5
echo.
echo [5/7] Phone connection check...
adb kill-server >nul 2>&1
timeout /t 2 /nobreak >nul
adb start-server >nul 2>&1
timeout /t 3 /nobreak >nul

set "RETRY=0"

:check_phone
set "DEVICE_OK=0"
set "HAS_OFFLINE=0"
set "HAS_UNAUTH=0"

adb devices > "%TEMP%\rf_adb.txt" 2>&1
for /f "skip=1 tokens=1,2 usebackq" %%a in ("%TEMP%\rf_adb.txt") do (
    if "%%b"=="device" set "DEVICE_OK=1"
    if "%%b"=="offline" set "HAS_OFFLINE=1"
    if "%%b"=="unauthorized" set "HAS_UNAUTH=1"
)

if !DEVICE_OK! EQU 1 goto phone_ready

set /a RETRY+=1
if !RETRY! GTR 30 goto phone_timeout

if !HAS_UNAUTH! EQU 1 goto phone_unauth
if !HAS_OFFLINE! EQU 1 goto phone_offline
goto phone_missing

:phone_unauth
echo.
echo  [!] Phone UNAUTHORIZED!
echo      Phone par "Allow USB debugging?" popup pe
echo      "Always allow from this computer" CHECK karein, OK dabayein.
echo      Phone unlock rakhein. 10 sec wait...
timeout /t 10 /nobreak >nul
goto check_phone

:phone_offline
echo.
echo  [!] Phone OFFLINE - auto fix try !RETRY!...
adb kill-server >nul 2>&1
timeout /t 3 /nobreak >nul
adb start-server >nul 2>&1
timeout /t 5 /nobreak >nul
if !RETRY! GEQ 3 goto phone_offline_manual
goto check_phone

:phone_offline_manual
echo.
echo  PHONE OFFLINE - MANUAL FIX:
echo    1. Settings - Developer Options - Revoke USB debugging authorizations
echo    2. USB Debugging OFF, 5 sec ruko, phir ON
echo    3. USB cable nikalo, dobara lagao
echo    4. Phone unlock rakhein, popup pe Always Allow check karein
echo    5. DATA cable use karein, charging cable nahi
echo.
echo    R = Retry, Q = Quit
choice /C RQ /N /T 30 /D R
if errorlevel 2 exit /b 1
goto check_phone

:phone_missing
echo.
echo  [!] Koi phone connect nahi (try !RETRY! / 30^)
echo      1. USB cable lagao - DATA cable
echo      2. Phone unlock rakhein
echo      3. Settings - Developer Options - USB Debugging ON
echo      4. Notification bar - USB mode - File Transfer select
echo      10 sec wait... R = retry abhi, Q = quit
choice /C RQ /N /T 10 /D R
if errorlevel 2 exit /b 1
goto check_phone

:phone_timeout
echo  [X] 5 mint mein phone connect nahi hua. Exit.
pause
exit /b 1

:phone_ready
echo      OK - Phone connected and authorized:
adb devices | findstr /R "device$"

REM ==================== STEP 6: Doctor ====================
echo.
echo [6/7] Backend health check...
python "%~dp0worker.py" --doctor
if errorlevel 1 (
    echo  [!] Doctor warnings - phir bhi continue
    timeout /t 3 /nobreak >nul
)

REM ==================== STEP 7: Run Worker ====================
echo.
echo ================================================================
echo    WORKER START - SAB READY HAI
echo ================================================================
echo.
echo  AGLA STEP - Web UI mein:
echo    1. https://realflow.online kholein, login karein
echo    2. CPI module - Naya Job banayein:
echo         Offer URL    : aap ka tracker URL
echo         Proxy        : Japan Proxy Jet
echo         User Agent   : Japan Android UA
echo         Target count : 1
echo    3. Start Job dabayein
echo.
echo  Worker terminal mein logs ayenge.
echo  STOP karne ke liye Ctrl+C
echo ================================================================
echo.
python "%~dp0worker.py"

echo.
echo  Worker stop ho gaya.
pause
endlocal
