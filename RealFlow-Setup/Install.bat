@echo off
REM +==================================================================+
REM |                                                                  |
REM |         R E A L F L O W   --   S E T U P   W I Z A R D            |
REM |                                                                  |
REM |  Just double-click this file.                                    |
REM |                                                                  |
REM |  A wizard window opens with one big "INSTALL" button.            |
REM |  Click it once.  Sit back.  Watch the progress bar.              |
REM |                                                                  |
REM |  No commands. No technical knowledge. No questions.              |
REM |                                                                  |
REM +==================================================================+

setlocal EnableDelayedExpansion

REM --- Auto-elevate to Administrator -----------------------------
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  RealFlow Setup needs Administrator privileges.
    echo  A UAC popup will appear -- please click YES.
    echo.
    timeout /t 2 >nul
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title RealFlow Setup
cd /d "%~dp0"

REM --- Make sure PowerShell + the wizard script are present -------
where powershell >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  ERROR: PowerShell is not available on this PC.
    echo         RealFlow Setup requires Windows 10 or 11.
    echo.
    pause
    exit /b 1
)

if not exist "%~dp0setup-engine.ps1" (
    echo.
    echo  ERROR: setup-engine.ps1 not found in this folder:
    echo         %~dp0
    echo.
    echo  Make sure you extracted the entire RealFlow-Setup folder,
    echo  not just Install.bat by itself.
    echo.
    pause
    exit /b 1
)

REM --- Launch the WinForms wizard ---------------------------------
REM  We DO NOT use -WindowStyle Hidden any more, because if the
REM  wizard script ever fails to load (e.g. missing .NET assembly,
REM  parse error, antivirus block) the user would just see a CMD
REM  window flash and close. Keeping the host PowerShell window
REM  open lets us print a clear error + pause.
echo.
echo  Launching RealFlow Setup wizard...
echo  ^(If a new window does not appear within 5 seconds, see the
echo   error message that prints below.^)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-engine.ps1"

set RC=%ERRORLEVEL%

if %RC% neq 0 (
    echo.
    echo  ----------------------------------------------------------
    echo   The wizard ended with exit code %RC%.
    echo.
    echo   Full log saved to:  %~dp0setup.log
    echo.
    echo   Most common causes:
    echo     - Antivirus blocked the script. Try disabling
    echo       real-time protection for the RealFlow-Setup folder.
    echo     - PowerShell ExecutionPolicy is locked by Group Policy.
    echo       Run Debug.bat from this same folder for details.
    echo     - .NET Desktop / Windows Forms missing. Install
    echo       "Windows Desktop Runtime" from microsoft.com.
    echo  ----------------------------------------------------------
    echo.
    pause
)

endlocal
