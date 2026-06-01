@echo off
REM ════════════════════════════════════════════════════════════════════════
REM  KREXION — ADMIN ONE-CLICK BUILDER  (v2 — fixed PATH discovery)
REM  ════════════════════════════════════════════════════════════════════════
REM  Yeh file aap (admin) double-click karein. Bas.
REM
REM  Yeh khud install karega:
REM    - Chocolatey (package manager)
REM    - Git
REM    - Python 3.11
REM    - Node.js 20 LTS
REM    - Yarn
REM    - Inno Setup 6
REM
REM  Phir khud:
REM    - Krexion repo clone karega C:\Krexion-Build mein
REM    - Frontend + Backend build karega
REM    - Krexion-Setup-X.X.X.exe banayega
REM    - Output folder kholega
REM
REM  Aap ko sirf:
REM    1. UAC popup pe "Yes" click karna hai
REM    2. ~30-45 minute wait karna hai (pehli baar)
REM    3. Output folder se Krexion-Setup-*.exe upload karein:
REM       https://github.com/dennisedmaartins9-sudo/krexion.com/releases
REM    4. Krexion admin panel pe (krexion.com/admin → Releases → New)
REM       us .exe ka URL paste karein + Publish karein
REM
REM  Total time first run:  30-45 min
REM  Total time next runs:  5-10 min (deps already installed)
REM
REM  v2 changes:
REM    - Better PATH discovery (covers C:\Python311 + Program Files)
REM    - Auto-show last 50 lines of log on failure
REM    - "where python/node/yarn/git/iscc" verification before build
REM    - Captures PowerShell stdout+stderr directly into log file
REM    - Auto-installs playwright chromium if missing during build
REM ════════════════════════════════════════════════════════════════════════

setlocal EnableDelayedExpansion
title Krexion Admin One-Click Builder v2
mode con: cols=110 lines=45
color 0B
cls

set "BUILD_DIR=C:\Krexion-Build"
set "REPO_URL=https://github.com/dennisedmaartins9-sudo/krexion.com.git"
set "LOG=%USERPROFILE%\Desktop\Krexion-Admin-Build-Log.txt"

echo Krexion Admin Builder v2 — started: %DATE% %TIME% > "%LOG%" 2>nul

echo.
echo  ============================================================
echo   KREXION - ADMIN ONE-CLICK BUILDER  (v2)
echo  ============================================================
echo.
echo   Yeh file aap ko admin ka .exe installer banake degi.
echo.
echo   Approx time:  30-45 min (pehli baar)
echo                 5-10 min   (next time)
echo.
echo   Build folder: %BUILD_DIR%
echo   Log file:     %LOG%
echo.

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 0: Self-elevate to admin
REM ════════════════════════════════════════════════════════════════════════
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [..] Administrator rights chahiye - UAC popup aayega.
    echo       "Yes" click karein.
    timeout /t 2 /nobreak >nul
    powershell -NoProfile -Command "try { Start-Process -FilePath '%~f0' -Verb RunAs -ErrorAction Stop } catch { exit 1 }"
    if %errorlevel% neq 0 (
        color 0C
        echo.
        echo   UAC popup cancel kiya gaya. Phir se chalayein aur "Yes" click karein.
        pause
        exit /b 1
    )
    exit /b 0
)

echo  [OK] Running as Administrator
echo. >> "%LOG%"

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 1: Install Chocolatey (if not present)
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 1/7] Chocolatey package manager check...
where choco >nul 2>&1
if %errorlevel% neq 0 (
    echo   [..] Chocolatey install ho raha hai - 1 minute wait...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; iex ((New-Object Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))" 1>>"%LOG%" 2>&1
    if !errorlevel! neq 0 (
        color 0C
        echo   [ERR] Chocolatey install fail ho gaya. Log: %LOG%
        call :TAIL_LOG
        pause
        exit /b 1
    )
)
set "PATH=%ALLUSERSPROFILE%\chocolatey\bin;%PATH%"
echo   [OK] Chocolatey ready
echo. >> "%LOG%"

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 2: Install Git
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 2/7] Git install check...
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo   [..] Git install ho raha hai...
    choco install git -y --no-progress 1>>"%LOG%" 2>&1
)
set "PATH=%PROGRAMFILES%\Git\cmd;%PROGRAMFILES%\Git\bin;%PATH%"
echo   [OK] Git ready
echo. >> "%LOG%"

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 3: Install Python 3.11 (Chocolatey installs to C:\Python311 by default)
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 3/7] Python 3.11 install check...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [..] Python 3.11 install ho raha hai - 2-3 min wait...
    choco install python311 -y --no-progress 1>>"%LOG%" 2>&1
)
REM Add BOTH possible install locations (choco default + python.org installer)
set "PATH=C:\Python311;C:\Python311\Scripts;%PROGRAMFILES%\Python311;%PROGRAMFILES%\Python311\Scripts;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
where python >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo   [ERR] Python install ke baad bhi PATH mein nahi mila.
    echo         C:\Python311\ check karein. Manually open karein.
    pause
    exit /b 1
)
echo   [OK] Python ready - 
python --version
echo. >> "%LOG%"

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 4: Install Node.js + Yarn
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 4/7] Node.js install check...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [..] Node.js 20 LTS install ho raha hai - 2 min wait...
    choco install nodejs-lts -y --no-progress 1>>"%LOG%" 2>&1
)
set "PATH=%PROGRAMFILES%\nodejs;%APPDATA%\npm;%PATH%"
where node >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo   [ERR] Node.js install ke baad bhi PATH mein nahi mila.
    pause
    exit /b 1
)
echo   [OK] Node.js ready - 
node --version

echo  [..] Yarn install check...
where yarn >nul 2>&1
if %errorlevel% neq 0 (
    echo   [..] Yarn install ho raha hai...
    call npm install -g yarn 1>>"%LOG%" 2>&1
)
where yarn >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo   [ERR] Yarn install fail. Manually: npm install -g yarn
    pause
    exit /b 1
)
echo   [OK] Yarn ready - 
yarn --version
echo. >> "%LOG%"

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 5: Install Inno Setup
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 5/7] Inno Setup install check...
if not exist "%PROGRAMFILES(X86)%\Inno Setup 6\ISCC.exe" (
    echo   [..] Inno Setup install ho raha hai - 1 min...
    choco install innosetup -y --no-progress 1>>"%LOG%" 2>&1
)
if not exist "%PROGRAMFILES(X86)%\Inno Setup 6\ISCC.exe" (
    color 0C
    echo   [ERR] Inno Setup install fail.
    pause
    exit /b 1
)
set "PATH=%PROGRAMFILES(X86)%\Inno Setup 6;%PATH%"
echo   [OK] Inno Setup ready
echo. >> "%LOG%"

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 6: Clone or update the Krexion repo
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 6/7] Krexion source code (clone/update)...
if not exist "%BUILD_DIR%\.git" (
    echo   [..] Repo clone ho raha hai - 30 sec...
    if exist "%BUILD_DIR%" rmdir /S /Q "%BUILD_DIR%" 2>nul
    git clone %REPO_URL% "%BUILD_DIR%" 1>>"%LOG%" 2>&1
    if !errorlevel! neq 0 (
        color 0C
        echo   [ERR] Repo clone fail. Internet check karein.
        call :TAIL_LOG
        pause
        exit /b 1
    )
) else (
    echo   [..] Repo update ho raha hai...
    pushd "%BUILD_DIR%"
    git pull 1>>"%LOG%" 2>&1
    popd
)
echo   [OK] Source code ready at %BUILD_DIR%
echo. >> "%LOG%"

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 7: Run the build pipeline
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 7/7] Krexion .exe build - YEH STEP 20-30 MIN LEGA
echo            Chai/coffee piyen, sab automatic hai.
echo.
echo  [..] Final environment check (pre-build verification)...
echo. >> "%LOG%"
echo === Final PATH check === >> "%LOG%"
where python >> "%LOG%" 2>&1
where node >> "%LOG%" 2>&1
where yarn >> "%LOG%" 2>&1
where git >> "%LOG%" 2>&1

pushd "%BUILD_DIR%"

REM Compute version: increment patch from VERSION file or use 1.0.0
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

REM Run the PowerShell build script. PATH is inherited via the parent
REM cmd session — so python/node/yarn are already found inside PS.
REM We pipe to Tee-Object so output goes both to screen AND to the log.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "& { try { & '.\Build-Krexion-Windows.ps1' -Version '%VER%' *>&1 | Tee-Object -FilePath '%LOG%' -Append; exit $LASTEXITCODE } catch { Write-Host ('FATAL: ' + $_.Exception.Message); exit 99 } }"
set "BUILD_EC=!errorlevel!"

popd

if !BUILD_EC! neq 0 (
    color 0C
    echo.
    echo  ============================================================
    echo   BUILD FAILED  (exit code: !BUILD_EC!)
    echo  ============================================================
    echo.
    echo   Last 50 lines from log:
    echo  ============================================================
    call :TAIL_LOG
    echo  ============================================================
    echo.
    echo   Full log:  %LOG%
    echo.
    echo   Yeh log ka content copy karke main agent ko bhejein
    echo   takay actual error fix kiya jaa sake.
    echo.
    pause
    exit /b !BUILD_EC!
)

REM ════════════════════════════════════════════════════════════════════════
REM  ALL DONE
REM ════════════════════════════════════════════════════════════════════════
color 0A
cls
echo.
echo  ============================================================
echo            BUILD SUCCESSFUL!  v%VER%
echo  ============================================================
echo.
echo   Aap ki Krexion installer file ban gayi hai:
echo.
echo     %BUILD_DIR%\installer\Output\Krexion-Setup-%VER%.exe
echo.
echo  ============================================================
echo   NEXT STEPS (manual — sirf 2 minute):
echo  ============================================================
echo.
echo   STEP A) Upload to GitHub Releases:
echo     1. Browser khol kar jayein:
echo        https://github.com/dennisedmaartins9-sudo/krexion.com/releases/new
echo     2. Tag: v%VER%   Title: Krexion %VER%
echo     3. "Attach binaries" mein .exe file drag-drop karein
echo     4. "Publish release" click karein
echo     5. Released .exe pe right-click - "Copy link address"
echo.
echo   STEP B) Krexion admin panel mein paste:
echo     1. https://krexion.com/admin-login
echo     2. Releases page kholein - "New release"
echo     3. Version: %VER%
echo     4. "Windows installer URL" mein woh copied link paste karein
echo     5. "Publish release" click karein
echo.
echo   STEP C) Customers ko bata dein:
echo     https://krexion.com/download
echo     (Native .exe automatic 302-redirect karega GitHub se)
echo.
echo  ============================================================
echo.
echo   Output folder kholne ja raha hun...
timeout /t 5 /nobreak >nul

start "" explorer.exe "%BUILD_DIR%\installer\Output"

echo.
echo  Yeh window khuli rahegi. Koi key dabayein band karne ke liye.
pause
exit /b 0


REM ════════════════════════════════════════════════════════════════════════
REM  Helper: Show the last 50 lines of the log to the console.
REM  Pure PowerShell so it works on every Windows version without extra tools.
REM ════════════════════════════════════════════════════════════════════════
:TAIL_LOG
if exist "%LOG%" (
    powershell -NoProfile -Command "Get-Content -Path '%LOG%' -Tail 50 -ErrorAction SilentlyContinue"
)
exit /b 0
