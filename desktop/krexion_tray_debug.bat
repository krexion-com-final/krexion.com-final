@echo off
REM ────────────────────────────────────────────────────────────────
REM Krexion Dashboard - DIAGNOSTIC (visible console) launcher
REM ────────────────────────────────────────────────────────────────
REM Twin of krexion-tray.bat that intentionally KEEPS this console
REM window open AND uses the console-mode interpreter (krexion-core.exe
REM == python.exe) so every byte of stdout/stderr from the Python side
REM is shown to the customer in real time. Use this when the silent
REM normal launcher seems to do nothing - the visible output will
REM immediately surface ImportError / WebView2 missing / pythonnet
REM unavailable / pystray crash, etc.
REM
REM Customer-side trigger:
REM   Start Menu -> Krexion -> "Krexion Diagnostic"
REM OR double-click this file directly from
REM   C:\Program Files\Krexion\krexion-tray-debug.bat
REM ────────────────────────────────────────────────────────────────

title Krexion Dashboard - Diagnostic Mode

setlocal

set "KREXION_HOME=%~dp0"
set "KREXION_BIN=%KREXION_HOME%bin"
set "KREXION_LOGS=%KREXION_HOME%logs"
set "KREXION_LOG_DIR=%KREXION_LOGS%"

if not exist "%KREXION_LOGS%" mkdir "%KREXION_LOGS%" 2>nul

echo.
echo ============================================================
echo   KREXION DASHBOARD - DIAGNOSTIC MODE
echo ============================================================
echo.
echo This window stays open so you can see every error message
echo from Python / pywebview / pystray / WebView2.
echo.
echo If everything works the dashboard window will appear in
echo a few seconds. Close THIS window (not the dashboard one)
echo to free up resources after the dashboard is up.
echo.
echo ------------------------------------------------------------
echo Install dir : %KREXION_HOME%
echo Bin dir     : %KREXION_BIN%
echo Logs dir    : %KREXION_LOGS%
echo ------------------------------------------------------------
echo.

REM Console-mode interpreter so output prints to THIS window.
REM (krexion-coreapp.exe is pythonw.exe - no console - useless here.)
set "PY=%KREXION_BIN%\krexion-core.exe"
if not exist "%PY%" (
  echo ERROR: krexion-core.exe not found at %PY%
  echo The install may be corrupted. Re-run the installer.
  echo.
  pause
  exit /b 1
)
echo Interpreter : %PY%

if not exist "%KREXION_BIN%\app\desktop\krexion_dashboard.py" (
  echo ERROR: desktop\krexion_dashboard.py not found at:
  echo        %KREXION_BIN%\app\desktop\krexion_dashboard.py
  echo The install is missing the dashboard module. Re-install.
  echo.
  pause
  exit /b 1
)
echo Module      : %KREXION_BIN%\app\desktop\krexion_dashboard.py
echo.

cd /d "%KREXION_BIN%\app"

REM Quick diagnostic: which packages can Python actually import?
echo Running import diagnostic...
echo ------------------------------------------------------------
"%PY%" -c "import sys; print('Python', sys.version)"
"%PY%" -c "import sys; print('sys.path:'); [print(' ', p) for p in sys.path]"
echo.
"%PY%" -c "import pywebview; print('pywebview OK,', pywebview.__version__)" 2>&1
"%PY%" -c "import pystray; print('pystray OK')" 2>&1
"%PY%" -c "import PIL; print('PIL OK,', PIL.__version__)" 2>&1
"%PY%" -c "import psutil; print('psutil OK,', psutil.__version__)" 2>&1
"%PY%" -c "import clr; print('pythonnet/clr OK')" 2>&1
echo ------------------------------------------------------------
echo.
echo Launching dashboard with full stderr capture...
echo (close this window after the dashboard window opens)
echo.

REM Run synchronously so customer sees every byte of output.
"%PY%" -m desktop.krexion_dashboard

echo.
echo ------------------------------------------------------------
echo Dashboard process exited with code %ERRORLEVEL%
echo Check the log file for details:
echo   %KREXION_LOGS%\dashboard.log
echo.
echo Press any key to close this window...
pause >nul
endlocal
