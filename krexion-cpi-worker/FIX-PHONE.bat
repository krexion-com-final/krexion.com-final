@echo off
title Krexion - Phone Offline Fix
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ================================================================
echo    PHONE OFFLINE / UNAUTHORIZED FIX TOOL
echo ================================================================
echo.

REM Use bundled ADB if available
if exist "%~dp0platform-tools\adb.exe" set "PATH=%~dp0platform-tools;!PATH!"

where adb >nul 2>&1
if errorlevel 1 goto no_adb

echo Step 1: ADB server reset...
adb kill-server >nul 2>&1
timeout /t 3 /nobreak >nul
adb start-server >nul 2>&1
timeout /t 3 /nobreak >nul
echo OK
echo.

echo Step 2: Connected devices:
adb devices
echo.

echo --------------------------------------------------------------
echo AGAR phone offline ya unauthorized dikha raha hai:
echo --------------------------------------------------------------
echo  1. Phone par Settings - Developer Options kholein
echo  2. "Revoke USB debugging authorizations" dabayein
echo  3. USB Debugging toggle OFF karein, 5 sec ruko, phir ON karein
echo  4. USB cable nikalo, dobara lagao
echo  5. Phone unlock rakhein
echo  6. Popup "Allow USB debugging?" pe Always allow CHECK karein
echo  7. OK dabayein
echo.
echo Bonus tips:
echo  - Sirf DATA cable use karein, charging cable nahi
echo  - USB port change karein, USB 2.0 try karein
echo  - Notification bar - USB mode - File Transfer MTP select karein
echo.
echo Sab steps karne ke baad koi key dabayein retry ke liye...
pause >nul

echo.
echo Step 3: Final check...
adb kill-server >nul 2>&1
timeout /t 2 /nobreak >nul
adb start-server >nul 2>&1
timeout /t 3 /nobreak >nul
adb devices
echo.

adb devices | findstr /R "device$" >nul
if errorlevel 1 goto still_failing
goto success

:still_failing
echo  [X] Phone abhi bhi connect nahi.
echo     Upper steps dobara try karein, ya phone restart karke try karein.
goto end

:success
echo  [OK] Phone CONNECTED hai! Ab START-CPI.bat run kar sakte hain.
goto end

:no_adb
echo  [X] ADB nahi mila. Pehle START-CPI.bat ek dafa chalayein - ADB
echo     auto-download ho jayega, phir is .bat ko use kar sakte hain.
goto end

:end
echo.
pause
endlocal
