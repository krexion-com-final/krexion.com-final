@echo off
REM +==================================================================+
REM |                 Krexion Setup -- DEBUG MODE                       |
REM |                                                                  |
REM |  Runs the wizard with ALL output visible.                        |
REM |  Use this when Install.bat fails silently.                       |
REM |                                                                  |
REM |  The window will STAY OPEN after the wizard exits so you can     |
REM |  read any error messages and copy them.                          |
REM +==================================================================+

setlocal

REM --- Auto-elevate ------------------------------------------------
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Need Administrator. Re-launching with UAC prompt...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title Krexion Setup -- DEBUG MODE
cd /d "%~dp0"
color 0E

echo.
echo  +==========================================================+
echo  |              Krexion Setup -- DEBUG MODE                 |
echo  +==========================================================+
echo.
echo  This window will STAY OPEN. Watch for error messages below.
echo.
echo  --- Environment diagnostics ---
echo  Script folder: %~dp0
echo  User: %USERNAME%  Computer: %COMPUTERNAME%
echo  Windows: %OS%
ver
echo.

echo  PowerShell version:
powershell -NoProfile -Command "$PSVersionTable.PSVersion.ToString()"
echo.

echo  ExecutionPolicy (all scopes):
powershell -NoProfile -Command "Get-ExecutionPolicy -List | Format-Table -AutoSize | Out-String"
echo.

if not exist "%~dp0setup-engine.ps1" (
    color 0C
    echo  X setup-engine.ps1 NOT FOUND in %~dp0
    echo    Make sure you extracted the WHOLE Krexion-Setup folder.
    pause
    exit /b 1
)
echo  OK setup-engine.ps1 found
echo.

echo  --- Parsing setup-engine.ps1 (syntax check) ---
powershell -NoProfile -ExecutionPolicy Bypass -Command "$null = [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw '%~dp0setup-engine.ps1'), [ref]$null); Write-Host '  OK Script parses cleanly'" 2>&1
if errorlevel 1 (
    color 0C
    echo  X Script has syntax errors. See above.
    pause
    exit /b 1
)
echo.

echo  --- Launching wizard (verbose) ---
echo  --------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0setup-engine.ps1"

echo  --------------------------------------------------------------
echo.
echo  Wizard process ended.
echo.
echo  Full log (if any) is here:  %~dp0setup.log
echo.
pause
endlocal
