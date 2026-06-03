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
REM ────────────────────────────────────────────────────────────────

setlocal

REM %~dp0 = directory this .bat lives in (always {InstallDir} since
REM         we ship krexion-tray.bat at the install root).
set "KREXION_HOME=%~dp0"
set "KREXION_BIN=%KREXION_HOME%bin"

REM Prefer the GUI-mode interpreter (no console window). Fall back to
REM the console one if the GUI rename wasn't produced by the build
REM (e.g. nightly with embed-zip layout regressions).
set "PY_GUI=%KREXION_BIN%\krexion-coreapp.exe"
set "PY_CORE=%KREXION_BIN%\krexion-core.exe"

set "PY=%PY_GUI%"
if not exist "%PY%" set "PY=%PY_CORE%"

if not exist "%PY%" (
  REM Last-resort safety net — neither rename present. Don't crash the
  REM customer's auto-start; just open krexion.com so they still see
  REM something happen.
  start "" "https://krexion.com/login"
  exit /b 0
)

REM Use the bundled dashboard package (build-backend.py copies the
REM repo's desktop/ folder into bin\app\desktop\)
cd /d "%KREXION_BIN%\app"
start "" "%PY%" -m desktop.krexion_dashboard

endlocal
exit /b 0
