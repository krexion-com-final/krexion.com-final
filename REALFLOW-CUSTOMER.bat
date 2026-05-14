@echo off
REM ###################################################################
REM #                                                                 #
REM #         REALFLOW CUSTOMER INSTALLER                             #
REM #                                                                 #
REM #  Yeh customer ke liye hai - admin access NAHI deta              #
REM #  Customer khud register karega normal user account              #
REM #                                                                 #
REM ###################################################################

REM Self-elevate
fltmc >nul 2>&1
if %errorLevel% neq 0 (
    echo  Administrator rights chahiye. UAC popup pe YES dabayein.
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>&1
    exit /b 0
)

title RealFlow Customer Installer
mode con: cols=100 lines=40
color 0A
cls

echo.
echo  ###################################################################
echo  #                                                                 #
echo  #         REALFLOW INSTALLER                                      #
echo  #         For Customer / End User                                 #
echo  #                                                                 #
echo  #  20-30 minute mein install ho jayega                            #
echo  #  Phir aap apna account khud register karenge                    #
echo  #                                                                 #
echo  ###################################################################
echo.
timeout /t 3 /nobreak >nul

REM Check internet
echo  [..] Internet connection check
ping -n 1 github.com >nul 2>&1
if %errorLevel% neq 0 (
    echo  [ERROR] Internet nahi hai!
    pause
    exit /b 1
)
echo  [OK] Internet working
echo.

REM Get installer (local first, then GitHub)
set "PS_FILE=%~dp0install-master.ps1"

if exist "%PS_FILE%" (
    echo  [OK] Local installer mila
) else (
    echo  [..] GitHub se installer download
    set "PS_URL=https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/install-master.ps1"
    set "PS_FILE=%TEMP%\realflow-install-master.ps1"
    powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%PS_URL%' -OutFile '%PS_FILE%' -UseBasicParsing -TimeoutSec 60 } catch { exit 1 }"

    if not exist "%PS_FILE%" (
        echo  [ERROR] Download fail.
        pause
        exit /b 1
    )
    echo  [OK] Downloaded
)
echo.

REM Run installer in CUSTOMER mode
echo  ===================================================
echo   Customer install start ho raha hai...
echo  ===================================================
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%PS_FILE%" -CustomerMode

set "EXITCODE=%errorlevel%"

if "%PS_FILE%"=="%TEMP%\realflow-install-master.ps1" del "%PS_FILE%" >nul 2>&1

if %EXITCODE% neq 0 (
    echo.
    echo  Installation issue. Log files:
    echo    %TEMP%\realflow-install.log
    echo    %TEMP%\realflow-transcript.log
    echo.
    echo  Yeh log files admin ko WhatsApp pe bhejen.
    pause
    exit /b %EXITCODE%
)

echo.
pause
exit /b 0
