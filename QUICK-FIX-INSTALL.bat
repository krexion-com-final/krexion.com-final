@echo off
REM ============================================================
REM  Krexion QUICK FIX -- For users who got "Installation failed"
REM
REM  This single .bat file:
REM  1. Cleans up any stuck/partial install at C:\krexion
REM  2. Downloads the LATEST installer from GitHub
REM  3. Runs the new bulletproof installer
REM
REM  Customer ko bhejna ho to sirf yeh 1 file bhejo:
REM    "Double click karo -- sab automatic"
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Self-elevate to Administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)

cls
echo.
echo ============================================================
echo   Krexion QUICK FIX + INSTALL
echo ============================================================
echo.
echo   This will:
echo   1. Clean any partial install at C:\krexion
echo   2. Download the latest installer from GitHub
echo   3. Install Krexion fresh
echo.
echo   Estimated time: 15-30 minutes (depending on internet)
echo.
echo ============================================================
echo.
timeout /t 3 /nobreak >nul

REM Step 1 -- Hard cleanup C:\krexion
echo Step 1/3 -- Cleaning up any partial install...

if exist "C:\krexion" (
    echo   Found old install at C:\krexion, removing...
    REM Try to stop docker compose first
    pushd "C:\krexion" 2>nul
    docker compose down 2>nul
    popd 2>nul

    REM Take ownership + grant full permissions, then remove
    takeown /F "C:\krexion" /R /D Y >nul 2>&1
    icacls "C:\krexion" /grant "Administrators:F" /T /C /Q >nul 2>&1
    rmdir /s /q "C:\krexion" 2>nul

    REM Try once more if files were locked
    if exist "C:\krexion" (
        timeout /t 3 /nobreak >nul
        rmdir /s /q "C:\krexion" 2>nul
    )

    if exist "C:\krexion" (
        echo.
        echo   ERROR: Could not delete C:\krexion
        echo.
        echo   FIX:
        echo     1. Close all File Explorer windows showing C:\krexion
        echo     2. Close VS Code if open
        echo     3. Open Task Manager -- end any 'docker.exe' or 'node.exe' processes
        echo     4. Restart your PC
        echo     5. Run this file again
        echo.
        pause
        exit /b 1
    )
    echo   Old install removed successfully.
) else (
    echo   No old install found, ready for fresh install.
)
echo.

REM Step 2 -- Download latest installer files from GitHub
echo Step 2/3 -- Downloading latest installer...

set "DOWNLOAD_DIR=%TEMP%\krexion-installer"
if exist "%DOWNLOAD_DIR%" rmdir /s /q "%DOWNLOAD_DIR%"
mkdir "%DOWNLOAD_DIR%" 2>nul

set "BASE=https://raw.githubusercontent.com/ronaldsexedwards40-glitch/dynabook/main"

echo   Downloading Krexion-EASY-INSTALL.ps1...
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri '%BASE%/Krexion-EASY-INSTALL.ps1' -OutFile '%DOWNLOAD_DIR%\Krexion-EASY-INSTALL.ps1' -TimeoutSec 60 } catch { Write-Host '  Download failed:' $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo.
    echo   ERROR: Could not download the installer from GitHub.
    echo   - Check internet connection
    echo   - Try a mobile hotspot or VPN
    echo.
    pause
    exit /b 1
)

echo   Downloading Krexion-EASY-INSTALL.bat...
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri '%BASE%/Krexion-EASY-INSTALL.bat' -OutFile '%DOWNLOAD_DIR%\Krexion-EASY-INSTALL.bat' -TimeoutSec 30 } catch { exit 1 }"

echo   Files downloaded successfully.
echo.

REM Step 3 -- Run the installer
echo Step 3/3 -- Starting the installer...
echo.
echo   The installer window will now take over.
echo   Just sit back -- it handles everything.
echo.
timeout /t 2 /nobreak >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%DOWNLOAD_DIR%\Krexion-EASY-INSTALL.ps1"
set "INSTALL_EXIT=%errorlevel%"

echo.
if "%INSTALL_EXIT%" == "0" (
    echo ============================================================
    echo   Krexion installed successfully!
    echo ============================================================
    echo.
    echo   Open: http://localhost:3000
    echo   Admin password is shown in the installer log + C:\krexion\.env
    echo.
) else (
    echo ============================================================
    echo   Installer exited with error code: %INSTALL_EXIT%
    echo ============================================================
    echo   See log files inside the installer's temp folder.
    echo.
)
pause
endlocal
