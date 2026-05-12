@echo off
REM ╔══════════════════════════════════════════════════════════════════╗
REM ║                                                                  ║
REM ║         REALFLOW — ONE-CLICK INSTALLER (Windows)                 ║
REM ║                                                                  ║
REM ║  Just double-click this file on a fresh Windows 10/11 PC.        ║
REM ║                                                                  ║
REM ║  It will:                                                        ║
REM ║   1. Auto-elevate to Administrator                               ║
REM ║   2. Install Docker Desktop  (if missing)                        ║
REM ║   3. Install Git             (if missing)                        ║
REM ║   4. Clone the RealFlow repo to C:\realflow                      ║
REM ║   5. Generate strong random secrets                              ║
REM ║   6. Build + start the full stack (FastAPI + MongoDB)            ║
REM ║   7. Print the admin login URL + password                        ║
REM ║                                                                  ║
REM ║  Re-run this same file later to UPGRADE in-place (auto-backup).  ║
REM ║                                                                  ║
REM ╚══════════════════════════════════════════════════════════════════╝

setlocal

REM ─── Auto-elevate to Administrator ────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  RealFlow installer needs Administrator privileges.
    echo  Re-launching as Admin...
    echo.
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title RealFlow One-Click Installer
color 0B

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║       R E A L F L O W   O N E - C L I C K                ║
echo  ║                                                          ║
echo  ║   Self-hosted traffic + conversion + CPI platform        ║
echo  ║                                                          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo  This installer will set up everything on this PC.
echo  Target install folder: C:\realflow
echo.
echo  Press any key to BEGIN, or close this window to cancel.
pause >nul

REM ─── Make sure we can run PowerShell scripts in this session ────
powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force"

REM ─── Decide whether to run the bundled local copy of the deploy ──
REM ─── script (if the user already has the repo next to this .bat) ─
REM ─── OR pull the live one from GitHub.                          ──
if exist "%~dp0REALFLOW-DEPLOY.ps1" (
    echo.
    echo  Found local REALFLOW-DEPLOY.ps1 — running it...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0REALFLOW-DEPLOY.ps1"
) else (
    echo.
    echo  Downloading latest installer from GitHub...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; ^
       iwr -UseBasicParsing https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main/REALFLOW-DEPLOY.ps1 -OutFile $env:TEMP\REALFLOW-DEPLOY.ps1; ^
       & $env:TEMP\REALFLOW-DEPLOY.ps1"
)

set EXITCODE=%ERRORLEVEL%

echo.
echo  ─────────────────────────────────────────────────────────────
if %EXITCODE% equ 0 (
    color 0A
    echo  ✓ RealFlow installation completed successfully.
    echo.
    echo  Open in browser:   http://localhost:8001/docs   (API)
    echo  Frontend:          deploy frontend separately on Vercel
    echo                     OR run yarn start inside C:\realflow\frontend
    echo.
    echo  Admin password was printed above. Save it now.
    echo.
    echo  Daily commands ^(run from C:\realflow^):
    echo      LOCAL-START.bat       — start
    echo      LOCAL-STOP.bat        — stop
    echo      REALFLOW-LOGS.bat     — live logs
    echo      REALFLOW-UPDATE.bat   — pull ^& rebuild
) else (
    color 0C
    echo  ✗ Installation finished with errors ^(exit code %EXITCODE%^).
    echo.
    echo  Common fixes:
    echo   - Make sure Docker Desktop is RUNNING ^(whale icon in tray^)
    echo   - Re-run this file once Docker is up
    echo   - For deeper help, see  DEPLOY-README-URDU.md  in C:\realflow
)
echo  ─────────────────────────────────────────────────────────────
echo.
pause
endlocal
