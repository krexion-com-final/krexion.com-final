@echo off
REM ────────────────────────────────────────────────────────────────
REM Krexion Tray / Dashboard Launcher
REM ────────────────────────────────────────────────────────────────
REM Launched by:
REM   * Installer "Launch Krexion now" final-page checkbox
REM   * HKCU\...\Run "Krexion" key (autostart on login, when the
REM     "Start Krexion automatically when Windows starts" task ticked)
REM
REM Boots the PyWebView+pystray dashboard. Uses krexion-coreapp.exe
REM (== renamed pythonw.exe) so the GUI starts without a console window.
REM
REM Writes every launch attempt to {InstallDir}\logs\dashboard.log so
REM that if the window fails to appear we have a paper trail of what
REM went wrong (the previous version detached the process and any
REM crash output vanished into the void).
REM ────────────────────────────────────────────────────────────────

setlocal

set "KREXION_HOME=%~dp0"
set "KREXION_BIN=%KREXION_HOME%bin"
set "LOGFILE=%KREXION_HOME%logs\dashboard.log"

REM Make sure the logs folder exists (the installer creates it, but be
REM defensive in case someone deletes it).
if not exist "%KREXION_HOME%logs" mkdir "%KREXION_HOME%logs" 2>nul

REM Header for this launch attempt
echo. >> "%LOGFILE%"
echo === Krexion Tray launch attempt @ %DATE% %TIME% === >> "%LOGFILE%"

REM Prefer the GUI-mode interpreter (no console window). Fall back to
REM the console one if the GUI rename wasn't produced by the build.
set "PY_GUI=%KREXION_BIN%\krexion-coreapp.exe"
set "PY_CORE=%KREXION_BIN%\krexion-core.exe"

set "PY=%PY_GUI%"
if not exist "%PY%" (
  echo krexion-coreapp.exe missing, falling back to krexion-core.exe >> "%LOGFILE%"
  set "PY=%PY_CORE%"
)

if not exist "%PY%" (
  echo Both renamed interpreters missing - opening krexion.com as fallback >> "%LOGFILE%"
  start "" "https://krexion.com/login"
  exit /b 0
)

echo Using interpreter: %PY% >> "%LOGFILE%"

REM Use the bundled dashboard package (build-backend.py copies the
REM repo's desktop/ folder into bin\app\desktop\)
cd /d "%KREXION_BIN%\app"
if not exist "desktop\krexion_dashboard.py" (
  echo desktop\krexion_dashboard.py missing! >> "%LOGFILE%"
  start "" "https://krexion.com/login"
  exit /b 0
)

REM Launch the dashboard. Output goes to dashboard.log so any PyWebView
REM init / WebView2-missing / pystray init error is captured. We use a
REM console-mode helper if needed for full stderr capture.
echo Launching: %PY% -m desktop.krexion_dashboard >> "%LOGFILE%"
start "Krexion Dashboard" /B "%PY%" -m desktop.krexion_dashboard >> "%LOGFILE%" 2>&1

REM Give the launched process a head start before we exit so its
REM stdout/stderr has a chance to flush to the log file.
ping -n 2 127.0.0.1 > nul 2>&1

echo Launch returned, .bat exiting >> "%LOGFILE%"
endlocal
exit /b 0
