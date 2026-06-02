@echo off
REM +==================================================================+
REM |   Krexion ONE-CLICK INSTALLER (Easy Edition)                     |
REM |                                                                    |
REM |   What this does:                                                  |
REM |   1. Auto-elevates to Administrator                                |
REM |   2. Checks/Installs Docker Desktop                                |
REM |   3. Downloads Krexion code from GitHub (ZIP - no git needed)     |
REM |   4. Generates secure passwords                                    |
REM |   5. Auto-tunes for your PC's RAM/CPU                              |
REM |   6. Starts everything in Docker                                   |
REM |   7. Opens http://localhost:3000 in your browser                   |
REM |                                                                    |
REM |   Customer just double-clicks this file. Nothing else.             |
REM +==================================================================+

setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM --- Self-elevate to Admin ---
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)

REM --- Set up paths and constants ---
set "REPO_OWNER=ronaldsexedwards40-glitch"
set "REPO_NAME=dynabook"
set "BRANCH=main"
set "INSTALL_DIR=C:\krexion"
set "ZIP_URL=https://github.com/%REPO_OWNER%/%REPO_NAME%/archive/refs/heads/%BRANCH%.zip"
set "TEMP_ZIP=%TEMP%\krexion-source.zip"
set "TEMP_EXTRACT=%TEMP%\krexion-extract"
set "LOG=%~dp0Krexion-Install.log"

REM --- Clear old log ---
echo Krexion Easy Install - %DATE% %TIME% > "%LOG%"

REM --- Run main PowerShell installer ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Krexion-EASY-INSTALL.ps1"

if %errorLevel% neq 0 (
    echo.
    echo ============================================================
    echo   Install hit an error. See full log:
    echo   %LOG%
    echo ============================================================
    pause
    exit /b 1
)

endlocal
