@echo off
REM ============================================================
REM  RealFlow ULTIMATE INSTALLER - Single File, Auto-Recovery
REM  Bagair kisi issue ke install karne ke liye
REM ============================================================
REM  User ko bas double-click karna hai. Bas.
REM  - Auto-elevates to Admin
REM  - WSL2 auto-installs + updates
REM  - Docker Desktop auto-installs + auto-recovers if stuck
REM  - RealFlow downloads + starts automatically
REM  - Browser auto-opens
REM ============================================================

REM Self-elevate to Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  ============================================================
    echo   Administrator privileges required
    echo   Please click YES on the UAC popup
    echo  ============================================================
    echo.
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM Set window title and color
title RealFlow Ultimate Installer
color 0B

REM Create install log
set "LOGFILE=%TEMP%\realflow-ultimate-install.log"
echo [%date% %time%] Installer started > "%LOGFILE%"

REM Run the PowerShell installer with execution policy bypass
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0RealFlow-ULTIMATE-INSTALL.ps1"

set "EXITCODE=%errorlevel%"

if %EXITCODE% neq 0 (
    echo.
    echo  ============================================================
    echo   INSTALLER FAILED - Exit code: %EXITCODE%
    echo  ============================================================
    echo.
    echo  Full log: %LOGFILE%
    echo  Detailed log: %TEMP%\realflow-install.log
    echo.
    echo  Please share these log files for support.
    echo.
    pause
    exit /b %EXITCODE%
)

echo.
echo  ============================================================
echo   INSTALLATION COMPLETE!
echo  ============================================================
echo.
pause
exit /b 0
