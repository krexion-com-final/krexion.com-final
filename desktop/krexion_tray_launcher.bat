@echo off
REM ────────────────────────────────────────────────────────────────
REM Krexion Tray / Dashboard Launcher  (v1.0.5+)
REM ────────────────────────────────────────────────────────────────
REM Launched by:
REM   * Installer "Launch Krexion now" final-page checkbox
REM   * HKCU\...\Run "Krexion" key (autostart on login)
REM   * Start Menu shortcut "Krexion Dashboard"
REM
REM Boots the PyWebView+pystray dashboard via krexion-coreapp.exe
REM (== renamed pythonw.exe). The Python module now sets up its own
REM file logger at logs\dashboard.log BEFORE any imports, so even an
REM ImportError leaves a paper trail.
REM
REM v1.0.5 fix: previously used `start "Krexion Dashboard" /B "%PY%" ...
REM `>> logfile 2>&1` — the redirection only captured `start`'s own
REM output, not the launched process (start detaches handles), so any
REM pywebview/WebView2 failure vanished into NUL. We now use the
REM lightweight `cmd /c start /MIN ""` form which spawns the GUI
REM interpreter detached AND relies on Python's file logging for
REM diagnostics. The .bat itself exits in <1 s so it never blocks the
REM installer's final wizard page.
REM ────────────────────────────────────────────────────────────────

setlocal

set "KREXION_HOME=%~dp0"
set "KREXION_BIN=%KREXION_HOME%bin"
set "KREXION_LOGS=%KREXION_HOME%logs"
set "LOGFILE=%KREXION_LOGS%\dashboard.log"

REM Make sure the logs folder exists (installer creates it, but be
REM defensive in case someone deletes it).
if not exist "%KREXION_LOGS%" mkdir "%KREXION_LOGS%" 2>nul

REM Pass the log dir to Python via env so Python's logger lands in
REM the SAME location even if cwd/path detection is fuzzy at runtime.
set "KREXION_LOG_DIR=%KREXION_LOGS%"

REM ── Header for this launch attempt ───────────────────────────────
>> "%LOGFILE%" echo.
>> "%LOGFILE%" echo === krexion-tray.bat launch @ %DATE% %TIME% ===
>> "%LOGFILE%" echo KREXION_HOME = %KREXION_HOME%
>> "%LOGFILE%" echo KREXION_BIN  = %KREXION_BIN%

REM ── Pick interpreter ─────────────────────────────────────────────
REM Prefer the GUI-mode interpreter (no console window). Fall back to
REM the console one if the GUI rename wasn't produced by the build.
set "PY_GUI=%KREXION_BIN%\krexion-coreapp.exe"
set "PY_CORE=%KREXION_BIN%\krexion-core.exe"

set "PY=%PY_GUI%"
if not exist "%PY%" (
  >> "%LOGFILE%" echo krexion-coreapp.exe missing, falling back to krexion-core.exe
  set "PY=%PY_CORE%"
)

if not exist "%PY%" (
  >> "%LOGFILE%" echo Both renamed interpreters missing - opening krexion.com as fallback
  start "" "https://krexion.com/login"
  exit /b 0
)

>> "%LOGFILE%" echo Using interpreter: %PY%

REM Use the bundled dashboard package (build-backend.py copies the
REM repo's desktop/ folder into bin\app\desktop\)
if not exist "%KREXION_BIN%\app\desktop\krexion_dashboard.py" (
  >> "%LOGFILE%" echo desktop\krexion_dashboard.py missing at %KREXION_BIN%\app\desktop\
  >> "%LOGFILE%" echo Opening krexion.com as fallback.
  start "" "https://krexion.com/login"
  exit /b 0
)

REM Switch working directory to bin\app so `import desktop` resolves
REM cleanly (python311._pth puts `app` on sys.path).
cd /d "%KREXION_BIN%\app"

REM ── Launch the dashboard ─────────────────────────────────────────
REM Use krexion-coreapp.exe (GUI, no console). No `start /B` because
REM that breaks output redirection AND blocks the .bat from exiting
REM until the GUI window closes. The Python side has its own file
REM logger so we don't need to capture stdout/stderr from here.
REM
REM `start ""` (empty title) tells cmd.exe to spawn the GUI process
REM detached and return immediately. `/MIN` is intentionally OMITTED
REM so the dashboard appears in the customer's foreground after
REM install (the customer expects a visible window — that's the
REM whole point of fixing the v1.0.4 "krexion.com opens but no
REM local window" bug).
>> "%LOGFILE%" echo Launching: "%PY%" -m desktop.krexion_dashboard
start "" "%PY%" -m desktop.krexion_dashboard

REM Brief pause to let the launched process attach to its own file
REM handles before we exit (otherwise on very fast machines the .bat
REM exiting can race the Python interpreter's logging init).
ping -n 2 127.0.0.1 > nul 2>&1

>> "%LOGFILE%" echo krexion-tray.bat exiting (Python process detached)
endlocal
exit /b 0
