@echo off
REM ###################################################################
REM #                                                                 #
REM #         REALFLOW DOCTOR - Self-Healing Tool                     #
REM #                                                                 #
REM #  Agar kahin stuck ho ya kuch kaam na kare to yeh chalayein     #
REM #  Yeh khud sab kuch diagnose aur fix karta hai                  #
REM #                                                                 #
REM ###################################################################

fltmc >nul 2>&1
if %errorLevel% neq 0 (
    echo Administrator rights chahiye. UAC pe YES dabayein.
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>&1
    exit /b 0
)

title RealFlow Doctor - Auto-Fix Tool
mode con: cols=100 lines=40
color 0E
cls

echo.
echo  ###################################################################
echo  #                                                                 #
echo  #         REALFLOW DOCTOR                                         #
echo  #         Auto-Diagnose + Auto-Fix                                #
echo  #                                                                 #
echo  ###################################################################
echo.
echo   Yeh tool aap ki RealFlow ki har problem khud fix karega.
echo.
echo   Time: 5-10 minute
echo.
timeout /t 3 /nobreak >nul

REM Use bundled doctor.ps1 or download from GitHub
set "PS_FILE=%~dp0doctor.ps1"

if not exist "%PS_FILE%" (
    set "PS_FILE=%TEMP%\realflow-doctor.ps1"
    echo  [..] Doctor tool download kar raha hun...
    powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/doctor.ps1' -OutFile '%TEMP%\realflow-doctor.ps1' -UseBasicParsing -TimeoutSec 60 } catch { exit 1 }"

    if not exist "%PS_FILE%" (
        echo.
        echo  Doctor tool download fail hua.
        echo  Solution: Apne admin ko WhatsApp karein.
        pause
        exit /b 1
    )
    echo  [OK] Doctor downloaded
    echo.
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%PS_FILE%"

set "EXITCODE=%errorlevel%"

if "%PS_FILE%"=="%TEMP%\realflow-doctor.ps1" del "%PS_FILE%" >nul 2>&1

echo.
pause
exit /b %EXITCODE%
