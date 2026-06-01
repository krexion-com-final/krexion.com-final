@echo off
REM ════════════════════════════════════════════════════════════════════════
REM  KREXION — ADMIN ONE-CLICK BUILDER
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
REM ════════════════════════════════════════════════════════════════════════

setlocal EnableDelayedExpansion
title Krexion Admin One-Click Builder
mode con: cols=110 lines=45
color 0B
cls

set "BUILD_DIR=C:\Krexion-Build"
set "REPO_URL=https://github.com/dennisedmaartins9-sudo/krexion.com.git"
set "LOG=%USERPROFILE%\Desktop\Krexion-Admin-Build-Log.txt"

echo. > "%LOG%" 2>nul
echo Krexion Admin Builder — started: %DATE% %TIME% >> "%LOG%"

echo.
echo  ============================================================
echo   KREXION - ADMIN ONE-CLICK BUILDER
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

REM Now we're admin
echo  [OK] Running as Administrator
echo.

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
        pause
        exit /b 1
    )
    REM Refresh PATH so choco is available in this session
    call refreshenv >nul 2>&1
    set "PATH=%ALLUSERSPROFILE%\chocolatey\bin;%PATH%"
)
echo   [OK] Chocolatey ready
echo.

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 2: Install Git
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 2/7] Git install check...
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo   [..] Git install ho raha hai...
    choco install git -y --no-progress 1>>"%LOG%" 2>&1
    set "PATH=%PROGRAMFILES%\Git\cmd;%PATH%"
)
echo   [OK] Git ready
echo.

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 3: Install Python 3.11
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 3/7] Python 3.11 install check...
python --version 2>nul | findstr /C:"Python 3.11" >nul
if %errorlevel% neq 0 (
    echo   [..] Python 3.11 install ho raha hai - 2-3 min wait...
    choco install python311 -y --no-progress 1>>"%LOG%" 2>&1
    REM Add to PATH manually for this session
    set "PATH=%PROGRAMFILES%\Python311;%PROGRAMFILES%\Python311\Scripts;%PATH%"
)
echo   [OK] Python ready
echo.

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 4: Install Node.js + Yarn
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 4/7] Node.js install check...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [..] Node.js 20 LTS install ho raha hai - 2 min wait...
    choco install nodejs-lts -y --no-progress 1>>"%LOG%" 2>&1
    set "PATH=%PROGRAMFILES%\nodejs;%APPDATA%\npm;%PATH%"
)
echo   [OK] Node.js ready

echo  [..] Yarn install check...
where yarn >nul 2>&1
if %errorlevel% neq 0 (
    echo   [..] Yarn install ho raha hai...
    call npm install -g yarn 1>>"%LOG%" 2>&1
)
echo   [OK] Yarn ready
echo.

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 5: Install Inno Setup
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 5/7] Inno Setup install check...
if not exist "%PROGRAMFILES(X86)%\Inno Setup 6\ISCC.exe" (
    echo   [..] Inno Setup install ho raha hai - 1 min...
    choco install innosetup -y --no-progress 1>>"%LOG%" 2>&1
)
echo   [OK] Inno Setup ready
echo.

REM Refresh environment one final time so PowerShell sees everything
call refreshenv >nul 2>&1
set "PATH=%PROGRAMFILES%\Python311;%PROGRAMFILES%\Python311\Scripts;%PROGRAMFILES%\nodejs;%APPDATA%\npm;%PROGRAMFILES%\Git\cmd;%PATH%"

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
        echo   [ERR] Repo clone fail. Internet check karein. Log: %LOG%
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
echo.

REM ════════════════════════════════════════════════════════════════════════
REM  STEP 7: Run the build pipeline
REM ════════════════════════════════════════════════════════════════════════
echo  [STEP 7/7] Krexion .exe build - YEH STEP 20-30 MIN LEGA
echo            Chai/coffee piyen, sab automatic hai.
echo.

pushd "%BUILD_DIR%"

REM Compute version: increment patch from VERSION file or use 1.0.0
set "VER=1.0.0"
if exist "backend\VERSION" (
    set /p VER=<backend\VERSION
)

REM Bump patch automatically — replace last digit
for /f "tokens=1-3 delims=." %%a in ("%VER%") do (
    set /a "PATCH=%%c+1"
    set "VER=%%a.%%b.!PATCH!"
)
echo   Building version: %VER%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "Build-Krexion-Windows.ps1" -Version "%VER%" 1>>"%LOG%" 2>&1
set "BUILD_EC=!errorlevel!"

if !BUILD_EC! neq 0 (
    popd
    color 0C
    echo.
    echo  ============================================================
    echo   BUILD FAILED (exit code: !BUILD_EC!)
    echo  ============================================================
    echo.
    echo   Log file:  %LOG%
    echo   Log ko Desktop se attach kar ke support@krexion.com pe bhejein
    echo.
    pause
    exit /b !BUILD_EC!
)
popd

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

REM Open the output folder so the user can drag the .exe directly
start "" explorer.exe "%BUILD_DIR%\installer\Output"

echo.
echo  Yeh window khuli rahegi. Koi key dabayein band karne ke liye.
pause
exit /b 0
