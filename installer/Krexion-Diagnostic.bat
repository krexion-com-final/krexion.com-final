@echo off
REM Krexion Self-Diagnostic Tool v1.0.8 (ASCII + CRLF safe)
REM Double-click to run. Output saved to Desktop\krexion-diagnostic.txt

setlocal EnableDelayedExpansion

set "OUT=%USERPROFILE%\Desktop\krexion-diagnostic.txt"
set "KREXION=C:\Program Files\Krexion"

echo Krexion Self-Diagnostic Tool
echo ============================
echo Please wait, this takes about 30 seconds...
echo Output will be saved to: %OUT%
echo.

REM First, ensure we can create the output file
echo Krexion Diagnostic Report > "%OUT%" 2>nul
if not exist "%OUT%" (
    echo ERROR: Cannot write to Desktop. Check permissions.
    pause
    exit /b 1
)

echo Generated: %DATE% %TIME% >> "%OUT%"
echo Computer: %COMPUTERNAME% >> "%OUT%"
echo User: %USERNAME% >> "%OUT%"
echo ============================================================ >> "%OUT%"
echo. >> "%OUT%"

echo [1/11] Windows version
echo --- 1. Windows version --- >> "%OUT%"
ver >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo [2/11] Install folder
echo --- 2. Krexion install folder --- >> "%OUT%"
if exist "%KREXION%" (
    echo Install dir: %KREXION% >> "%OUT%"
    echo. >> "%OUT%"
    echo TOP-LEVEL files: >> "%OUT%"
    dir /B "%KREXION%" >> "%OUT%" 2>&1
    echo. >> "%OUT%"
    echo bin contents: >> "%OUT%"
    dir /B "%KREXION%\bin" >> "%OUT%" 2>&1
    echo. >> "%OUT%"
    echo bin\app\desktop contents: >> "%OUT%"
    if exist "%KREXION%\bin\app\desktop" (
        dir /B "%KREXION%\bin\app\desktop" >> "%OUT%" 2>&1
    ) else (
        echo   MISSING - bin\app\desktop folder not found >> "%OUT%"
    )
    echo. >> "%OUT%"
    echo database\bin contents: >> "%OUT%"
    if exist "%KREXION%\database\bin" (
        dir /B "%KREXION%\database\bin\*.exe" >> "%OUT%" 2>&1
    ) else (
        echo   MISSING - database\bin folder not found >> "%OUT%"
    )
) else (
    echo MISSING! %KREXION% does not exist >> "%OUT%"
)
echo. >> "%OUT%"

echo [3/11] Data and config
echo --- 3. Krexion data and config --- >> "%OUT%"
echo data\db: >> "%OUT%"
if exist "%KREXION%\data\db" (
    dir /B "%KREXION%\data\db" >> "%OUT%" 2>&1
) else (
    echo   MISSING - data\db folder not found >> "%OUT%"
)
echo. >> "%OUT%"
echo C:\ProgramData\Krexion: >> "%OUT%"
if exist "C:\ProgramData\Krexion" (
    dir /B "C:\ProgramData\Krexion" >> "%OUT%" 2>&1
) else (
    echo   MISSING - C:\ProgramData\Krexion not found >> "%OUT%"
)
echo. >> "%OUT%"
echo system-specs.json: >> "%OUT%"
if exist "C:\ProgramData\Krexion\system-specs.json" (
    type "C:\ProgramData\Krexion\system-specs.json" >> "%OUT%" 2>&1
) else (
    echo   MISSING - PowerShell detection did not write file >> "%OUT%"
)
echo. >> "%OUT%"

echo [4/11] Services
echo --- 4. Service status --- >> "%OUT%"
echo KrexionBackend: >> "%OUT%"
sc query KrexionBackend >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo KrexionDatabase: >> "%OUT%"
sc query KrexionDatabase >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo NSSM dump for KrexionDatabase: >> "%OUT%"
if exist "%KREXION%\bin\krexion-service.exe" (
    "%KREXION%\bin\krexion-service.exe" dump KrexionDatabase >> "%OUT%" 2>&1
) else (
    echo   krexion-service.exe missing! >> "%OUT%"
)
echo. >> "%OUT%"

echo [5/11] Log files
echo --- 5. Log files --- >> "%OUT%"
echo logs folder: >> "%OUT%"
if exist "%KREXION%\logs" (
    dir /B "%KREXION%\logs" >> "%OUT%" 2>&1
) else (
    echo   MISSING >> "%OUT%"
)
echo. >> "%OUT%"
echo mongod.stderr.log last 40 lines: >> "%OUT%"
if exist "%KREXION%\logs\mongod.stderr.log" (
    powershell -NoProfile -Command "Get-Content '%KREXION%\logs\mongod.stderr.log' -Tail 40" >> "%OUT%" 2>&1
) else (
    echo   No mongod.stderr.log found >> "%OUT%"
)
echo. >> "%OUT%"
echo mongod.stdout.log last 20 lines: >> "%OUT%"
if exist "%KREXION%\logs\mongod.stdout.log" (
    powershell -NoProfile -Command "Get-Content '%KREXION%\logs\mongod.stdout.log' -Tail 20" >> "%OUT%" 2>&1
) else (
    echo   No mongod.stdout.log found >> "%OUT%"
)
echo. >> "%OUT%"
echo backend.stderr.log last 30 lines: >> "%OUT%"
if exist "%KREXION%\logs\backend.stderr.log" (
    powershell -NoProfile -Command "Get-Content '%KREXION%\logs\backend.stderr.log' -Tail 30" >> "%OUT%" 2>&1
) else (
    echo   No backend.stderr.log found >> "%OUT%"
)
echo. >> "%OUT%"

echo [6/11] VC++ runtime
echo --- 6. Visual C++ Redistributable --- >> "%OUT%"
echo vcruntime140.dll: >> "%OUT%"
if exist "%SystemRoot%\System32\vcruntime140.dll" (
    echo   FOUND >> "%OUT%"
) else (
    echo   MISSING >> "%OUT%"
)
echo vcruntime140_1.dll required by MongoDB: >> "%OUT%"
if exist "%SystemRoot%\System32\vcruntime140_1.dll" (
    echo   FOUND >> "%OUT%"
) else (
    echo   MISSING - this is likely why mongod is crashing >> "%OUT%"
)
echo. >> "%OUT%"

echo [7/11] mongod direct test
echo --- 7. mongod direct invocation --- >> "%OUT%"
if exist "%KREXION%\database\bin\mongod.exe" (
    echo Running mongod --version: >> "%OUT%"
    "%KREXION%\database\bin\mongod.exe" --version >> "%OUT%" 2>&1
    echo Exit code: !errorlevel! >> "%OUT%"
) else (
    echo mongod.exe MISSING >> "%OUT%"
)
echo. >> "%OUT%"

echo [8/11] Dashboard launcher test
echo --- 8. Dashboard launch test --- >> "%OUT%"
echo krexion-coreapp.exe GUI interpreter: >> "%OUT%"
if exist "%KREXION%\bin\krexion-coreapp.exe" (
    echo   FOUND >> "%OUT%"
) else (
    echo   MISSING - this is why dashboard does not open >> "%OUT%"
)
echo krexion-core.exe console interpreter: >> "%OUT%"
if exist "%KREXION%\bin\krexion-core.exe" (
    echo   FOUND >> "%OUT%"
) else (
    echo   MISSING >> "%OUT%"
)
echo. >> "%OUT%"
echo Trying dashboard module import: >> "%OUT%"
if exist "%KREXION%\bin\krexion-core.exe" (
    if exist "%KREXION%\bin\app\desktop\krexion_dashboard.py" (
        pushd "%KREXION%\bin\app"
        "%KREXION%\bin\krexion-core.exe" -c "import desktop.krexion_dashboard; print('IMPORT OK')" >> "%OUT%" 2>&1
        echo Exit code: !errorlevel! >> "%OUT%"
        popd
    ) else (
        echo desktop\krexion_dashboard.py MISSING in bin\app >> "%OUT%"
    )
)
echo. >> "%OUT%"

echo [9/11] Tray launcher .bat
echo --- 9. Tray launcher --- >> "%OUT%"
if exist "%KREXION%\krexion-tray.bat" (
    echo krexion-tray.bat FOUND. Content: >> "%OUT%"
    type "%KREXION%\krexion-tray.bat" >> "%OUT%" 2>&1
) else (
    echo MISSING! krexion-tray.bat not at install root >> "%OUT%"
)
echo. >> "%OUT%"

echo [10/11] Autostart registry
echo --- 10. Autostart registry key --- >> "%OUT%"
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v Krexion >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo [11/11] Backend health
echo --- 11. Backend health --- >> "%OUT%"
echo http://127.0.0.1:8001/api/system/version: >> "%OUT%"
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8001/api/system/version' -UseBasicParsing -TimeoutSec 5).Content } catch { 'ERROR: ' + $_.Exception.Message }" >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo http://127.0.0.1:8001/api/desktop/stats: >> "%OUT%"
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8001/api/desktop/stats' -UseBasicParsing -TimeoutSec 5).Content } catch { 'ERROR: ' + $_.Exception.Message }" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo ============================================================ >> "%OUT%"
echo END OF DIAGNOSTIC >> "%OUT%"
echo ============================================================ >> "%OUT%"

echo.
echo ============================================================
echo Diagnostic complete!
echo.
echo File saved to: %OUT%
echo.
echo Next steps:
echo  1. Open the file krexion-diagnostic.txt from your Desktop
echo  2. Select all (Ctrl+A) and copy (Ctrl+C)
echo  3. Paste it in the Emergent chat
echo  OR
echo     just attach the file to the chat directly.
echo ============================================================
echo.
pause
endlocal
