@echo off
REM ====================================================================
REM  Krexion — One-Click Windows Build
REM  Double-click this file ON YOUR WINDOWS MACHINE to build the
REM  customer-facing Krexion-Setup-X.X.X.exe.
REM
REM  Prerequisites:
REM    - Python 3.11 installed   (https://www.python.org/downloads/)
REM    - Node.js 20+ installed   (https://nodejs.org/)
REM    - Yarn installed          (npm install -g yarn)
REM    - Admin rights (UAC will prompt)
REM
REM  Output:
REM    installer\Output\Krexion-Setup-1.0.0.exe
REM
REM  Upload the .exe to GitHub Releases, then set the asset URL on the
REM  admin panel (Releases page) — customers will then download the
REM  white-label .exe via krexion.com/download.
REM ====================================================================
setlocal
title Krexion Windows Build
color 0B
cls

echo.
echo  ============================================================
echo   KREXION WINDOWS BUILD - One-Click
echo  ============================================================
echo.
echo   This will build the customer-facing Krexion installer.
echo   Expected time: 20-30 minutes (first run includes downloads).
echo.

REM Self-elevate if not running as admin (NSSM service ops need admin)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [..] Requesting administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>&1
    exit /b 0
)

REM Bypass PowerShell execution policy just for this session
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build-Krexion-Windows.ps1" %*
set "EC=%errorlevel%"

echo.
if %EC% equ 0 (
    color 0A
    echo  ============================================================
    echo   BUILD SUCCESSFUL
    echo  ============================================================
    echo.
    echo   Your installer is at:  installer\Output\Krexion-Setup-*.exe
    echo.
    echo   Next steps:
    echo     1. Upload that .exe to GitHub Releases
    echo     2. Copy the asset URL
    echo     3. On krexion.com admin panel, open Releases -^> New
    echo     4. Paste the URL into "Download URL" and Publish
    echo     5. Customers can now download it from /download
    echo.
) else (
    color 0C
    echo  ============================================================
    echo   BUILD FAILED  (exit code %EC%)
    echo  ============================================================
    echo.
    echo   Scroll up to see the error. Most common causes:
    echo     - Python 3.11 not installed or not on PATH
    echo     - Node.js or Yarn missing
    echo     - No internet connection
    echo.
)

echo  Press any key to close this window.
pause >nul
exit /b %EC%
