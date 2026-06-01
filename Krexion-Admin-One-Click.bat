@echo off
REM =====================================================================
REM  KREXION - ADMIN ONE-CLICK BUILDER  (v4 - guaranteed pause-on-exit)
REM =====================================================================
REM  Yeh script aap ki Windows VPS pe Krexion installer .exe banayega.
REM  Window HAMESHA khuli rahegi - chahe success ho ya error.
REM =====================================================================

REM --- Outer wrapper: call :main, then ALWAYS pause before exit ---
call :main %*
set "FINAL_EC=%errorlevel%"
echo.
echo  =====================================================
echo   SCRIPT FINISHED  (exit code: %FINAL_EC%)
echo  =====================================================
echo.
echo   Yeh window khuli rahegi. Koi key dabayein band karne ke liye.
pause
exit /b %FINAL_EC%


REM =====================================================================
REM  :main - actual logic
REM =====================================================================
:main
setlocal EnableDelayedExpansion

set "BUILD_DIR=C:\Krexion-Build"
set "REPO_URL=https://github.com/dennisedmaartins9-sudo/krexion.com.git"
set "LOG=%USERPROFILE%\Desktop\Krexion-Admin-Build-Log.txt"
set "TRACE=%USERPROFILE%\Desktop\Krexion-Trace.txt"

REM Wipe both log files at start
echo Krexion v4 trace started: %DATE% %TIME% > "%TRACE%" 2>nul
echo Krexion v4 build started: %DATE% %TIME% > "%LOG%" 2>nul

cls
echo.
echo  =====================================================
echo   KREXION - ADMIN ONE-CLICK BUILDER  v4
echo  =====================================================
echo.
echo   Build folder: %BUILD_DIR%
echo   Build log:    %LOG%
echo   Trace log:    %TRACE%
echo.
echo  =====================================================
echo   Press any key to start (or close window to cancel)
echo  =====================================================
pause >nul

echo [trace] User pressed key, starting checks >> "%TRACE%"

REM =====================================================================
REM  STEP 0: Admin check (NO self-elevation - we tell user how to fix)
REM =====================================================================
echo.
echo  [STEP 0/7] Admin rights check...
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [ERR] Yeh script ko ADMIN rights chahiye.
    echo.
    echo   Solution:
    echo     1. Yeh .bat file pe RIGHT-CLICK karein
    echo     2. "Run as administrator" select karein
    echo     3. UAC popup pe "Yes" click karein
    echo.
    echo [trace] FAILED: not admin >> "%TRACE%"
    exit /b 2
)
echo   [OK] Running as Administrator
echo [trace] Step 0 done - admin OK >> "%TRACE%"

REM =====================================================================
REM  STEP 1: Chocolatey
REM =====================================================================
echo.
echo  [STEP 1/7] Chocolatey package manager check...
where choco >nul 2>&1
if errorlevel 1 (
    echo   [..] Chocolatey install ho raha hai - 1 minute wait...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; iex ((New-Object Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))" 1>>"%LOG%" 2>&1
    if errorlevel 1 (
        echo.
        echo   [ERR] Chocolatey install fail ho gaya.
        echo         Log file Desktop pe hai: %LOG%
        echo [trace] FAILED: Chocolatey install >> "%TRACE%"
        exit /b 3
    )
)
set "PATH=%ALLUSERSPROFILE%\chocolatey\bin;%PATH%"
where choco >nul 2>&1
if errorlevel 1 (
    echo   [ERR] Chocolatey install ke baad bhi PATH mein nahi mila.
    echo [trace] FAILED: choco not in PATH after install >> "%TRACE%"
    exit /b 4
)
echo   [OK] Chocolatey ready
echo [trace] Step 1 done - choco OK >> "%TRACE%"

REM =====================================================================
REM  STEP 2: Git
REM =====================================================================
echo.
echo  [STEP 2/7] Git install check...
where git >nul 2>&1
if errorlevel 1 (
    echo   [..] Git install ho raha hai...
    choco install git -y --no-progress 1>>"%LOG%" 2>&1
)
set "PATH=%PROGRAMFILES%\Git\cmd;%PROGRAMFILES%\Git\bin;%PATH%"
where git >nul 2>&1
if errorlevel 1 (
    echo   [ERR] Git install ke baad bhi PATH mein nahi mila.
    echo [trace] FAILED: git not in PATH >> "%TRACE%"
    exit /b 5
)
echo   [OK] Git ready
echo [trace] Step 2 done - git OK >> "%TRACE%"

REM =====================================================================
REM  STEP 3: Python 3.11
REM =====================================================================
echo.
echo  [STEP 3/7] Python 3.11 install check...
where python >nul 2>&1
if errorlevel 1 (
    echo   [..] Python 3.11 install ho raha hai - 2-3 min wait...
    choco install python311 -y --no-progress 1>>"%LOG%" 2>&1
)
set "PATH=C:\Python311;C:\Python311\Scripts;%PROGRAMFILES%\Python311;%PROGRAMFILES%\Python311\Scripts;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
where python >nul 2>&1
if errorlevel 1 (
    echo   [ERR] Python install ke baad bhi PATH mein nahi mila.
    echo         Check karein: C:\Python311\python.exe ya C:\Program Files\Python311\python.exe
    echo [trace] FAILED: python not in PATH >> "%TRACE%"
    exit /b 6
)
echo   [OK] Python ready
python --version
echo [trace] Step 3 done - python OK >> "%TRACE%"

REM =====================================================================
REM  STEP 4: Node.js + Yarn
REM =====================================================================
echo.
echo  [STEP 4/7] Node.js install check...
where node >nul 2>&1
if errorlevel 1 (
    echo   [..] Node.js 20 LTS install ho raha hai - 2 min wait...
    choco install nodejs-lts -y --no-progress 1>>"%LOG%" 2>&1
)
set "PATH=%PROGRAMFILES%\nodejs;%APPDATA%\npm;%PATH%"
where node >nul 2>&1
if errorlevel 1 (
    echo   [ERR] Node.js install ke baad bhi PATH mein nahi mila.
    echo [trace] FAILED: node not in PATH >> "%TRACE%"
    exit /b 7
)
echo   [OK] Node.js ready
node --version

where yarn >nul 2>&1
if errorlevel 1 (
    echo   [..] Yarn install ho raha hai...
    call npm install -g yarn 1>>"%LOG%" 2>&1
)
where yarn >nul 2>&1
if errorlevel 1 (
    echo   [ERR] Yarn install fail.
    echo [trace] FAILED: yarn not in PATH >> "%TRACE%"
    exit /b 8
)
echo   [OK] Yarn ready
yarn --version
echo [trace] Step 4 done - node+yarn OK >> "%TRACE%"

REM =====================================================================
REM  STEP 5: Inno Setup
REM =====================================================================
echo.
echo  [STEP 5/7] Inno Setup install check...
if not exist "%PROGRAMFILES(X86)%\Inno Setup 6\ISCC.exe" (
    echo   [..] Inno Setup install ho raha hai - 1 min...
    choco install innosetup -y --no-progress 1>>"%LOG%" 2>&1
)
if not exist "%PROGRAMFILES(X86)%\Inno Setup 6\ISCC.exe" (
    echo   [ERR] Inno Setup install fail.
    echo [trace] FAILED: ISCC.exe missing >> "%TRACE%"
    exit /b 9
)
set "PATH=%PROGRAMFILES(X86)%\Inno Setup 6;%PATH%"
echo   [OK] Inno Setup ready
echo [trace] Step 5 done - inno OK >> "%TRACE%"

REM =====================================================================
REM  STEP 6: Clone or update Krexion repo
REM =====================================================================
echo.
echo  [STEP 6/7] Krexion source code (clone/update)...
if not exist "%BUILD_DIR%\.git" (
    echo   [..] Repo clone ho raha hai - 30 sec...
    if exist "%BUILD_DIR%" rmdir /S /Q "%BUILD_DIR%" 2>nul
    git clone %REPO_URL% "%BUILD_DIR%" 1>>"%LOG%" 2>&1
    if errorlevel 1 (
        echo   [ERR] Repo clone fail. Internet check karein.
        echo [trace] FAILED: git clone >> "%TRACE%"
        exit /b 10
    )
) else (
    echo   [..] Repo update ho raha hai...
    pushd "%BUILD_DIR%"
    git pull 1>>"%LOG%" 2>&1
    popd
)
echo   [OK] Source code ready at %BUILD_DIR%
echo [trace] Step 6 done - repo OK >> "%TRACE%"

REM =====================================================================
REM  STEP 7: Run build pipeline
REM =====================================================================
echo.
echo  [STEP 7/7] Krexion .exe build - YEH STEP 20-30 MIN LEGA
echo            Chai/coffee piyen, sab automatic hai.
echo.

echo === Final tool check === >> "%LOG%"
where python >> "%LOG%" 2>&1
where node >> "%LOG%" 2>&1
where yarn >> "%LOG%" 2>&1
where git >> "%LOG%" 2>&1

pushd "%BUILD_DIR%"

set "VER=1.0.0"
if exist "backend\VERSION" (
    set /p VER=<backend\VERSION
)
for /f "tokens=1-3 delims=." %%a in ("%VER%") do (
    set /a "PATCH=%%c+1"
    set "VER=%%a.%%b.!PATCH!"
)
echo   Building version: %VER%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "& { try { & '.\Build-Krexion-Windows.ps1' -Version '%VER%' *>&1 | Tee-Object -FilePath '%LOG%' -Append; exit $LASTEXITCODE } catch { Write-Host ('FATAL: ' + $_.Exception.Message); exit 99 } }"
set "BUILD_EC=!errorlevel!"

popd

if !BUILD_EC! neq 0 (
    echo.
    echo  =====================================================
    echo   BUILD FAILED  (exit code: !BUILD_EC!)
    echo  =====================================================
    echo.
    echo   Last 50 lines from log:
    echo  =====================================================
    powershell -NoProfile -Command "Get-Content -Path '%LOG%' -Tail 50 -ErrorAction SilentlyContinue"
    echo  =====================================================
    echo   Full log file:  %LOG%
    echo [trace] FAILED: build step 7, EC=!BUILD_EC! >> "%TRACE%"
    exit /b !BUILD_EC!
)

echo [trace] Step 7 done - BUILD COMPLETE v%VER% >> "%TRACE%"

cls
echo.
echo  =====================================================
echo            BUILD SUCCESSFUL!  v%VER%
echo  =====================================================
echo.
echo   Aap ki Krexion installer file ban gayi hai:
echo.
echo     %BUILD_DIR%\installer\Output\Krexion-Setup-%VER%.exe
echo.
echo  =====================================================
echo   NEXT STEPS:
echo  =====================================================
echo.
echo   A) Upload .exe to GitHub Releases:
echo      https://github.com/dennisedmaartins9-sudo/krexion.com/releases/new
echo      - Tag: v%VER%
echo      - Drag-drop the .exe
echo      - Click Publish release
echo      - Right-click .exe - Copy link address
echo.
echo   B) Paste URL in admin panel:
echo      https://krexion.com/admin-login
echo      - Releases page - New release
echo      - Windows installer URL = pasted link
echo      - Click Publish
echo.
echo   C) Customers download from:
echo      https://krexion.com/download
echo.
echo  =====================================================
echo.

start "" explorer.exe "%BUILD_DIR%\installer\Output"

exit /b 0
