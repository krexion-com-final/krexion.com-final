@echo off
REM ════════════════════════════════════════════════════════════════════
REM  Krexion Self-Diagnostic Tool — v1.0.8
REM ════════════════════════════════════════════════════════════════════
REM  Double-click karke chalao. Sab info Desktop par
REM  `krexion-diagnostic.txt` mein save ho jayegi.
REM  Phir wahi text file Emergent chat mein bhej do.
REM ════════════════════════════════════════════════════════════════════

setlocal EnableDelayedExpansion

set "OUT=%USERPROFILE%\Desktop\krexion-diagnostic.txt"
set "KREXION=C:\Program Files\Krexion"

echo Krexion Self-Diagnostic — please wait, may take up to 30 seconds...
echo.

> "%OUT%" echo ============================================================
>> "%OUT%" echo  KREXION DIAGNOSTIC REPORT
>> "%OUT%" echo  Generated: %DATE% %TIME%
>> "%OUT%" echo  Computer:  %COMPUTERNAME%   User: %USERNAME%
>> "%OUT%" echo ============================================================
>> "%OUT%" echo.

REM ── 1. Windows version ──────────────────────────────────────────
>> "%OUT%" echo --- [1] Windows version ---
ver >> "%OUT%" 2>&1
>> "%OUT%" echo.

REM ── 2. Install folder contents ─────────────────────────────────
>> "%OUT%" echo --- [2] Krexion install folder ---
if exist "%KREXION%" (
  >> "%OUT%" echo Install dir: %KREXION%
  >> "%OUT%" echo.
  >> "%OUT%" echo TOP-LEVEL files:
  dir /B "%KREXION%" >> "%OUT%" 2>&1
  >> "%OUT%" echo.
  >> "%OUT%" echo bin\ contents (looking for krexion-core.exe + krexion-coreapp.exe):
  dir /B "%KREXION%\bin" 2>nul | findstr /R "exe$ ._pth$" >> "%OUT%"
  >> "%OUT%" echo.
  >> "%OUT%" echo bin\app\desktop\ contents (dashboard files):
  if exist "%KREXION%\bin\app\desktop" (
    dir /B "%KREXION%\bin\app\desktop" >> "%OUT%" 2>&1
  ) else (
    >> "%OUT%" echo   MISSING!  bin\app\desktop folder not found
  )
  >> "%OUT%" echo.
  >> "%OUT%" echo database\bin\ contents (looking for mongod.exe):
  if exist "%KREXION%\database\bin" (
    dir /B "%KREXION%\database\bin\*.exe" >> "%OUT%" 2>&1
  ) else (
    >> "%OUT%" echo   MISSING!  database\bin folder not found
  )
) else (
  >> "%OUT%" echo MISSING! %KREXION% does not exist
)
>> "%OUT%" echo.

REM ── 3. data folder + ProgramData ───────────────────────────────
>> "%OUT%" echo --- [3] Krexion data + config ---
>> "%OUT%" echo data\db (MongoDB data dir):
if exist "%KREXION%\data\db" (
  dir /B "%KREXION%\data\db" 2>nul | findstr /N "^" | findstr "^[1-9]" >> "%OUT%"
  if errorlevel 1 >> "%OUT%" echo   (empty — mongod has not initialised yet)
) else (
  >> "%OUT%" echo   MISSING! data\db folder not found
)
>> "%OUT%" echo.
>> "%OUT%" echo C:\ProgramData\Krexion contents:
if exist "C:\ProgramData\Krexion" (
  dir /B "C:\ProgramData\Krexion" >> "%OUT%" 2>&1
) else (
  >> "%OUT%" echo   MISSING! C:\ProgramData\Krexion folder not found
)
>> "%OUT%" echo.
>> "%OUT%" echo system-specs.json contents:
if exist "C:\ProgramData\Krexion\system-specs.json" (
  type "C:\ProgramData\Krexion\system-specs.json" >> "%OUT%" 2>&1
) else (
  >> "%OUT%" echo   MISSING — installer's PowerShell detection did not run successfully
)
>> "%OUT%" echo.
>> "%OUT%" echo.

REM ── 4. Service status ───────────────────────────────────────────
>> "%OUT%" echo --- [4] Service status ---
>> "%OUT%" echo KrexionBackend:
sc query KrexionBackend >> "%OUT%" 2>&1
>> "%OUT%" echo.
>> "%OUT%" echo KrexionDatabase:
sc query KrexionDatabase >> "%OUT%" 2>&1
>> "%OUT%" echo.
>> "%OUT%" echo NSSM service config for KrexionDatabase:
"%KREXION%\bin\krexion-service.exe" dump KrexionDatabase >> "%OUT%" 2>&1
>> "%OUT%" echo.

REM ── 5. Log files ───────────────────────────────────────────────
>> "%OUT%" echo --- [5] Log files ---
>> "%OUT%" echo Files in %KREXION%\logs:
if exist "%KREXION%\logs" (
  dir /B "%KREXION%\logs" >> "%OUT%" 2>&1
) else (
  >> "%OUT%" echo   MISSING! logs folder not created
)
>> "%OUT%" echo.
>> "%OUT%" echo mongod.stderr.log (last 40 lines):
if exist "%KREXION%\logs\mongod.stderr.log" (
  powershell -NoProfile -Command "Get-Content '%KREXION%\logs\mongod.stderr.log' -Tail 40" >> "%OUT%" 2>&1
) else (
  >> "%OUT%" echo   No mongod.stderr.log found
)
>> "%OUT%" echo.
>> "%OUT%" echo mongod.stdout.log (last 20 lines):
if exist "%KREXION%\logs\mongod.stdout.log" (
  powershell -NoProfile -Command "Get-Content '%KREXION%\logs\mongod.stdout.log' -Tail 20" >> "%OUT%" 2>&1
) else (
  >> "%OUT%" echo   No mongod.stdout.log found
)
>> "%OUT%" echo.
>> "%OUT%" echo backend.stderr.log (last 30 lines):
if exist "%KREXION%\logs\backend.stderr.log" (
  powershell -NoProfile -Command "Get-Content '%KREXION%\logs\backend.stderr.log' -Tail 30" >> "%OUT%" 2>&1
) else (
  >> "%OUT%" echo   No backend.stderr.log found
)
>> "%OUT%" echo.

REM ── 6. VC++ Redistributable check ──────────────────────────────
>> "%OUT%" echo --- [6] Visual C++ Redistributable ---
>> "%OUT%" echo vcruntime140.dll in System32?
if exist "%SystemRoot%\System32\vcruntime140.dll" (
  >> "%OUT%" echo   FOUND
) else (
  >> "%OUT%" echo   MISSING
)
>> "%OUT%" echo vcruntime140_1.dll in System32?
if exist "%SystemRoot%\System32\vcruntime140_1.dll" (
  >> "%OUT%" echo   FOUND (MongoDB needs this)
) else (
  >> "%OUT%" echo   MISSING — this is why mongod fails. VC++ install did not work.
)
>> "%OUT%" echo.

REM ── 7. Mongod manual run test ──────────────────────────────────
>> "%OUT%" echo --- [7] mongod.exe direct invocation test ---
if exist "%KREXION%\database\bin\mongod.exe" (
  >> "%OUT%" echo Running: mongod.exe --version
  "%KREXION%\database\bin\mongod.exe" --version >> "%OUT%" 2>&1
  >> "%OUT%" echo Exit code: !errorlevel!
) else (
  >> "%OUT%" echo mongod.exe MISSING from %KREXION%\database\bin
)
>> "%OUT%" echo.

REM ── 8. Dashboard launcher direct test ──────────────────────────
>> "%OUT%" echo --- [8] Dashboard launch test ---
>> "%OUT%" echo Looking for krexion-coreapp.exe and krexion-core.exe:
if exist "%KREXION%\bin\krexion-coreapp.exe" (
  >> "%OUT%" echo   krexion-coreapp.exe FOUND  (GUI interpreter — used by dashboard)
) else (
  >> "%OUT%" echo   krexion-coreapp.exe MISSING — this is why the dashboard window did not open
)
if exist "%KREXION%\bin\krexion-core.exe" (
  >> "%OUT%" echo   krexion-core.exe FOUND     (console interpreter — used by backend service)
) else (
  >> "%OUT%" echo   krexion-core.exe MISSING
)
>> "%OUT%" echo.
>> "%OUT%" echo Trying to run dashboard module directly (5 sec timeout)...
if exist "%KREXION%\bin\krexion-core.exe" (
  cd /d "%KREXION%\bin\app" 2>nul
  if exist "desktop\krexion_dashboard.py" (
    >> "%OUT%" echo desktop/krexion_dashboard.py exists, attempting import only:
    "%KREXION%\bin\krexion-core.exe" -c "import desktop.krexion_dashboard; print('IMPORT OK')" >> "%OUT%" 2>&1
    >> "%OUT%" echo Exit code: !errorlevel!
  ) else (
    >> "%OUT%" echo desktop/krexion_dashboard.py MISSING in bin\app\
  )
)
>> "%OUT%" echo.

REM ── 9. krexion-tray.bat exists and content ─────────────────────
>> "%OUT%" echo --- [9] Tray launcher .bat ---
if exist "%KREXION%\krexion-tray.bat" (
  >> "%OUT%" echo krexion-tray.bat FOUND. Content:
  type "%KREXION%\krexion-tray.bat" >> "%OUT%" 2>&1
) else (
  >> "%OUT%" echo MISSING! krexion-tray.bat is supposed to be at install root
)
>> "%OUT%" echo.

REM ── 10. HKCU autostart registry key ────────────────────────────
>> "%OUT%" echo --- [10] Autostart registry key ---
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Krexion 2>&1 >> "%OUT%"
>> "%OUT%" echo.

REM ── 11. Backend health curl ────────────────────────────────────
>> "%OUT%" echo --- [11] Backend health ---
>> "%OUT%" echo Hitting http://127.0.0.1:8001/api/system/version :
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8001/api/system/version' -UseBasicParsing -TimeoutSec 5).Content } catch { 'ERROR: ' + $_.Exception.Message }" >> "%OUT%" 2>&1
>> "%OUT%" echo.
>> "%OUT%" echo Hitting http://127.0.0.1:8001/api/desktop/stats :
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8001/api/desktop/stats' -UseBasicParsing -TimeoutSec 5).Content } catch { 'ERROR: ' + $_.Exception.Message }" >> "%OUT%" 2>&1
>> "%OUT%" echo.

>> "%OUT%" echo ============================================================
>> "%OUT%" echo  END OF DIAGNOSTIC — please send this file to the developer.
>> "%OUT%" echo ============================================================

echo.
echo ============================================================
echo   Diagnostic complete!
echo.
echo   File saved to: %OUT%
echo.
echo   Aage:
echo   1. Apne Desktop par "krexion-diagnostic.txt" file dhundo
echo   2. File open karo (Notepad), Ctrl+A, Ctrl+C
echo   3. Emergent chat mein paste karo
echo   ya
echo   1. File ko hi directly chat mein attach kar do
echo ============================================================
echo.
pause
endlocal
