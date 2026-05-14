@echo off
REM ###################################################################
REM #                                                                 #
REM #              REALFLOW - THE ONE FILE INSTALLER                  #
REM #                                                                 #
REM #  Bas yeh file double-click karein. Aur kuch nahi.               #
REM #                                                                 #
REM #  - Self-elevates to Admin automatically                         #
REM #  - Downloads latest installer from GitHub (always fresh)        #
REM #  - Installs/updates WSL2 + Docker + RealFlow                    #
REM #  - Auto-recovers if Docker gets stuck                           #
REM #  - Opens browser when ready                                     #
REM #                                                                 #
REM #  Total time: 20-30 minutes (first time)                         #
REM #                                                                 #
REM ###################################################################

REM ========== STEP 1: Self-elevate to Administrator ==========
fltmc >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  ===================================================
    echo   Administrator rights chahiye. UAC popup pe YES dabayein.
    echo  ===================================================
    echo.
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>&1
    if %errorLevel% neq 0 (
        echo  UAC popup fail hua. Right-click "Run as administrator" karein.
        pause
    )
    exit /b 0
)

REM ========== STEP 2: Setup environment ==========
title RealFlow One-Click Installer
mode con: cols=100 lines=40
color 0B
cls

echo.
echo  ###################################################################
echo  #                                                                 #
echo  #         REALFLOW - ONE-CLICK BULLETPROOF INSTALLER              #
echo  #                                                                 #
echo  #              v3.0 - Always Latest from GitHub                   #
echo  #                                                                 #
echo  ###################################################################
echo.
echo   Yeh installer aap ki taraf se yeh kaam karega:
echo.
echo     [1] WSL2 setup + kernel update
echo     [2] Docker Desktop install
echo     [3] Docker stuck fix (auto-recovery)
echo     [4] RealFlow download (latest from GitHub)
echo     [5] Containers build + start
echo     [6] Browser auto-open
echo.
echo   Total time: ~20-30 minute
echo.
echo  ===================================================
echo   Reboot ki zaroorat ho sakti hai. Installer khud
echo   resume karega reboot ke baad. Sirf wait karein.
echo  ===================================================
echo.
timeout /t 5 /nobreak >nul

REM ========== STEP 3: Check internet ==========
echo  [..] Internet connection check kar raha hun...
ping -n 1 github.com >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  [ERROR] Internet connection nahi hai!
    echo.
    echo  Please WiFi/internet check karein aur dobara try karein.
    echo.
    pause
    exit /b 1
)
echo  [OK] Internet working
echo.

REM ========== STEP 4: Get installer (local first, then GitHub) ==========
set "PS_FILE=%~dp0install-master.ps1"

if exist "%PS_FILE%" (
    echo  [OK] Local install-master.ps1 mila ^(same folder mein^)
    echo.
    goto :RUN_INSTALLER
)

echo  [..] Local file nahi mila. GitHub se latest download kar raha hun...
echo.

set "PS_URL=https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/install-master.ps1"
set "PS_FILE=%TEMP%\realflow-install-master.ps1"

powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%PS_URL%' -OutFile '%PS_FILE%' -UseBasicParsing -TimeoutSec 60 } catch { exit 1 }"

if not exist "%PS_FILE%" (
    echo  [ERROR] Installer download fail ho gaya.
    echo.
    echo  Possible reasons:
    echo    1. GitHub par install-master.ps1 abhi nahi push hua
    echo    2. Internet slow hai
    echo    3. Antivirus block kar raha hai
    echo.
    echo  Solutions:
    echo    1. Aap admin ho? Save to GitHub button click karein
    echo    2. Aap customer ho? Admin se ZIP file maangein
    echo    3. Antivirus 5 min ke liye disable karein, dobara try karein
    echo.
    pause
    exit /b 1
)

echo  [OK] Latest installer downloaded ^(fresh from GitHub^)
echo.

:RUN_INSTALLER

REM ========== STEP 5: Run the installer ==========
echo  ===================================================
echo   Ab installer chal raha hai. Wait karein...
echo  ===================================================
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%PS_FILE%"

set "EXITCODE=%errorlevel%"

REM ========== STEP 6: Cleanup ==========
if "%PS_FILE%"=="%TEMP%\realflow-install-master.ps1" del "%PS_FILE%" >nul 2>&1

if %EXITCODE% neq 0 (
    echo.
    echo  ===================================================
    echo   Installation kuch issue hua ^(exit code: %EXITCODE%^)
    echo  ===================================================
    echo.
    echo   Log files yahan hain:
    echo     %TEMP%\realflow-install.log
    echo     %TEMP%\realflow-transcript.log
    echo.
    echo   Yeh log files admin ko bhejen WhatsApp pe.
    echo.
    pause
    exit /b %EXITCODE%
)

echo.
echo  ###################################################################
echo  #                                                                 #
echo  #              INSTALLATION COMPLETE!                             #
echo  #                                                                 #
echo  #   Browser khud khul jayegi http://localhost:3000 par             #
echo  #                                                                 #
echo  #   Admin credentials:                                            #
echo  #     Desktop pe "RealFlow-Credentials.txt" file mein hai         #
echo  #                                                                 #
echo  ###################################################################
echo.
pause
exit /b 0
