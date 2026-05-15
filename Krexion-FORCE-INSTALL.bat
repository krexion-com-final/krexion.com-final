@echo off
REM ============================================================
REM  Krexion FORCE INSTALL - Skip virtualization check
REM ============================================================
REM  Yeh tab use karein jab "CPU virtualization disabled" error
REM  aaye lekin aap ko pata hai ki BIOS mein enabled hai.
REM  Windows 11 24H2 mein yeh false-negative common hai.
REM ============================================================

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Administrator privileges required...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title Krexion Force Installer (Skip Virt Check)
color 0E

echo.
echo  ============================================================
echo   FORCE INSTALL MODE - Virtualization check skipped
echo  ============================================================
echo.
echo   Use karein agar:
echo   - "CPU virtualization is DISABLED" error aaye
echo   - Aap ko confirm hai BIOS mein virtualization ENABLED hai
echo   - Windows 11 24H2 ka false-negative issue hai
echo.
echo  ============================================================
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0Krexion-ULTIMATE-INSTALL.ps1" -SkipVirtCheck

set "EXITCODE=%errorlevel%"

if %EXITCODE% neq 0 (
    echo.
    echo  ============================================================
    echo   INSTALL FAILED - Exit code: %EXITCODE%
    echo  ============================================================
    echo.
    pause
    exit /b %EXITCODE%
)

echo.
pause
exit /b 0
