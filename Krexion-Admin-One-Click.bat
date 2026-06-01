@echo off
REM =====================================================================
REM  KREXION - ADMIN ONE-CLICK BUILDER  (v3 - ASCII-only, max compatible)
REM =====================================================================
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
REM  Phir khud Krexion repo clone karega, build karega, .exe banayega.
REM
REM  Window HAMESHA khuli rahegi - chahe success ho ya error,
REM  aap ko proper message dikhega.
REM =====================================================================

setlocal EnableDelayedExpansion

set "BUILD_DIR=C:\Krexion-Build"
set "REPO_URL=https://github.com/dennisedmaartins9-sudo/krexion.com.git"
set "LOG=%USERPROFILE%\Desktop\Krexion-Admin-Build-Log.txt"

cls
echo.
echo  =====================================================
echo   KREXION - ADMIN ONE-CLICK BUILDER  v3
echo  =====================================================
echo.
echo   Yeh script aap ki VPS pe Krexion installer .exe banayegi.
echo.
echo   Approx time:  30-45 min (pehli baar)
echo                 5-10 min   (next time)
echo.
echo   Build folder: %BUILD_DIR%
echo   Log file:     %LOG%
echo.
echo  =====================================================
echo   Press any key to start (or close window to cancel)
echo  =====================================================
pause >nul

echo Krexion Admin Builder v3 - started: %DATE% %TIME% > "%LOG%" 2>nul

REM =====================================================================
REM  STEP 0: Self-elevate to admin
REM =====================================================================
echo.
echo  [STEP 0/7] Admin rights check...
net session >nul 2>&1
if errorlevel 1 (
    echo   [..] Admin rights chahiye - UAC popup aayega.
    echo        "Yes" click karein.
    timeout /t 2 /nobreak >nul
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)
echo   [OK] Running as Administrator

REM =====================================================================
REM  STEP 1: Install Chocolatey
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
        echo         Log file Desktop pe hai - copy karke share karein.
        echo.
        pause
        exit /b 1
    )
)
set "PATH=%ALLUSERSPROFILE%\chocolatey\bin;%PATH%"
echo   [OK] Chocolatey ready

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
    echo.
    echo   [ERR] Git install ke baad bhi PATH mein nahi mila.
    echo         Manually install karein: https://git-scm.com/download/win
    pause
    exit /b 1
)
echo   [OK] Git ready

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
REM Try both possible install locations
set "PATH=C:\Python311;C:\Python311\Scripts;%PROGRAMFILES%\Python311;%PROGRAMFILES%\Python311\Scripts;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [ERR] Python install ke baad bhi PATH mein nahi mila.
    echo         Manually check karein: C:\Python311\python.exe
    pause
    exit /b 1
)
echo   [OK] Python ready
python --version

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
    echo.
    echo   [ERR] Node.js install ke baad bhi PATH mein nahi mila.
    pause
    exit /b 1
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
    echo.
    echo   [ERR] Yarn install fail.
    pause
    exit /b 1
)
echo   [OK] Yarn ready
yarn --version

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
    echo.
    echo   [ERR] Inno Setup install fail.
    pause
    exit /b 1
)
set "PATH=%PROGRAMFILES(X86)%\Inno Setup 6;%PATH%"
echo   [OK] Inno Setup ready

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
        echo.
        echo   [ERR] Repo clone fail. Internet check karein.
        echo         Log Desktop pe hai - last 20 lines:
        powershell -NoProfile -Command "Get-Content -Path '%LOG%' -Tail 20 -ErrorAction SilentlyContinue"
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

REM =====================================================================
REM  STEP 7: Run build pipeline
REM =====================================================================
echo.
echo  [STEP 7/7] Krexion .exe build - YEH STEP 20-30 MIN LEGA
echo            Chai/coffee piyen, sab automatic hai.
echo.

REM Final env check
echo === Final tool check === >> "%LOG%"
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

REM Run PowerShell build script with output going to log + screen
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
    echo.
    echo   Full log:  %LOG%
    echo.
    echo   Yeh log ka content copy karke main agent ko bhejein.
    echo.
    pause
    exit /b !BUILD_EC!
)

REM =====================================================================
REM  ALL DONE
REM =====================================================================
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
echo   NEXT STEPS (manual - sirf 2 minute):
echo  =====================================================
echo.
echo   STEP A) Upload to GitHub Releases:
echo     1. Browser khol kar jayein:
echo        https://github.com/dennisedmaartins9-sudo/krexion.com/releases/new
echo     2. Tag: v%VER%   Title: Krexion %VER%
echo     3. Attach binaries box mein .exe drag-drop karein
echo     4. Publish release click karein
echo     5. Released .exe pe right-click - Copy link address
echo.
echo   STEP B) Krexion admin panel mein paste:
echo     1. https://krexion.com/admin-login
echo     2. Releases page kholein - New release
echo     3. Version: %VER%
echo     4. Windows installer URL mein woh copied link paste karein
echo     5. Publish release click karein
echo.
echo   STEP C) Customers ko bata dein:
echo     https://krexion.com/download
echo.
echo  =====================================================
echo.
echo   Output folder kholne ja raha hun...
timeout /t 5 /nobreak >nul

start "" explorer.exe "%BUILD_DIR%\installer\Output"

echo.
echo  Yeh window khuli rahegi. Koi key dabayein band karne ke liye.
pause
exit /b 0
