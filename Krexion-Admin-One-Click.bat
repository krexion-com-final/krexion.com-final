@echo off
REM =====================================================================
REM  KREXION - ADMIN ONE-CLICK BUILDER  (v5 - goto-based, no :main wrapper)
REM =====================================================================
REM  Window HAMESHA khuli rahegi - har step ke baad pause ya error ke
REM  baad guaranteed pause. v5 mein call :main pattern hata diya kyunki
REM  cmd.exe ke yarn.cmd shim ke saath label table corrupt ho jata tha.
REM =====================================================================

setlocal EnableDelayedExpansion

set "BUILD_DIR=C:\Krexion-Build"
set "REPO_URL=https://github.com/dennisedmaartins9-sudo/krexion.com.git"
set "LOG=%USERPROFILE%\Desktop\Krexion-Admin-Build-Log.txt"
set "TRACE=%USERPROFILE%\Desktop\Krexion-Trace.txt"
set "INNO_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"

echo Krexion v5 trace started: %DATE% %TIME% > "%TRACE%" 2>nul
echo Krexion v5 build started: %DATE% %TIME% > "%LOG%" 2>nul

cls
echo.
echo  =====================================================
echo   KREXION - ADMIN ONE-CLICK BUILDER  v5
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

echo [trace] User pressed key >> "%TRACE%"

REM =====================================================================
REM  STEP 0: Admin check
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
    set "FINAL_EC=2"
    echo [trace] FAILED: not admin >> "%TRACE%"
    goto :END_PAUSE
)
echo   [OK] Running as Administrator
echo [trace] Step 0 done >> "%TRACE%"

REM =====================================================================
REM  STEP 1: Chocolatey
REM =====================================================================
echo.
echo  [STEP 1/7] Chocolatey package manager check...
where choco >nul 2>&1
if errorlevel 1 (
    echo   [..] Chocolatey install ho raha hai - 1 minute wait...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; iex ((New-Object Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))" 1>>"%LOG%" 2>&1
)
set "PATH=%ALLUSERSPROFILE%\chocolatey\bin;%PATH%"
where choco >nul 2>&1
if errorlevel 1 (
    echo   [ERR] Chocolatey install fail.
    set "FINAL_EC=3"
    echo [trace] FAILED: choco >> "%TRACE%"
    goto :END_PAUSE
)
echo   [OK] Chocolatey ready
echo [trace] Step 1 done >> "%TRACE%"

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
    echo   [ERR] Git PATH mein nahi mila.
    set "FINAL_EC=5"
    echo [trace] FAILED: git >> "%TRACE%"
    goto :END_PAUSE
)
echo   [OK] Git ready
echo [trace] Step 2 done >> "%TRACE%"

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
    echo   [ERR] Python PATH mein nahi mila.
    set "FINAL_EC=6"
    echo [trace] FAILED: python >> "%TRACE%"
    goto :END_PAUSE
)
echo   [OK] Python ready
python --version
echo [trace] Step 3 done >> "%TRACE%"

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
    echo   [ERR] Node.js PATH mein nahi mila.
    set "FINAL_EC=7"
    echo [trace] FAILED: node >> "%TRACE%"
    goto :END_PAUSE
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
    set "FINAL_EC=8"
    echo [trace] FAILED: yarn >> "%TRACE%"
    goto :END_PAUSE
)
echo   [OK] Yarn ready
REM Skip yarn --version output - causes label-table corruption with cmd.exe
echo [trace] Step 4 done >> "%TRACE%"

REM =====================================================================
REM  STEP 5: Inno Setup
REM =====================================================================
echo.
echo  [STEP 5/7] Inno Setup install check...
if not exist "!INNO_EXE!" (
    echo   [..] Inno Setup install ho raha hai - 1 min...
    choco install innosetup -y --no-progress 1>>"%LOG%" 2>&1
)
if not exist "!INNO_EXE!" (
    echo   [ERR] Inno Setup install fail.
    set "FINAL_EC=9"
    echo [trace] FAILED: inno >> "%TRACE%"
    goto :END_PAUSE
)
set "PATH=%ProgramFiles(x86)%\Inno Setup 6;%PATH%"
echo   [OK] Inno Setup ready
echo [trace] Step 5 done >> "%TRACE%"

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
        set "FINAL_EC=10"
        echo [trace] FAILED: clone >> "%TRACE%"
        goto :END_PAUSE
    )
) else (
    echo   [..] Repo update ho raha hai...
    pushd "%BUILD_DIR%"
    git pull 1>>"%LOG%" 2>&1
    popd
)
echo   [OK] Source code ready at %BUILD_DIR%
echo [trace] Step 6 done >> "%TRACE%"

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

REM Pre-flight: confirm Build-Krexion-Windows.ps1 exists in the repo
if not exist "%BUILD_DIR%\Build-Krexion-Windows.ps1" (
    echo   [ERR] Build-Krexion-Windows.ps1 file %BUILD_DIR% mein nahi mili!
    echo         Repo clone incomplete ho gaya. C:\Krexion-Build ko delete
    echo         karke phir se script run karein.
    set "FINAL_EC=11"
    echo [trace] FAILED: Build script missing >> "%TRACE%"
    goto :END_PAUSE
)
if not exist "%BUILD_DIR%\build\build-backend.py" (
    echo   [ERR] build\build-backend.py file nahi mili!
    echo         C:\Krexion-Build ko delete karke phir se script run karein.
    set "FINAL_EC=12"
    echo [trace] FAILED: build-backend.py missing >> "%TRACE%"
    goto :END_PAUSE
)

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
echo   PowerShell build script chal raha hai. Sab output yahan
echo   aur log file dono mein dikhega:
echo.

REM Direct invocation - NO try/catch wrapper. Any PowerShell error message
REM goes straight to screen + log so user sees actual cause of failure.
REM Exit code propagates via $LASTEXITCODE automatically.
powershell -NoProfile -ExecutionPolicy Bypass -File ".\Build-Krexion-Windows.ps1" -Version "%VER%" 2>&1
set "BUILD_EC=!errorlevel!"

popd

if !BUILD_EC! neq 0 (
    echo.
    echo  =====================================================
    echo   BUILD FAILED  (exit code: !BUILD_EC!)
    echo  =====================================================
    echo.
    echo   Upar screen pe jo error dikha hai woh actual cause hai.
    echo   Scroll up karke uske paas ki red lines dekhein.
    echo.
    echo   Full log:  %LOG%
    echo.
    set "FINAL_EC=!BUILD_EC!"
    echo [trace] FAILED: build, EC=!BUILD_EC! >> "%TRACE%"
    goto :END_PAUSE
)

echo [trace] Step 7 done - BUILD COMPLETE v%VER% >> "%TRACE%"

cls
echo.
echo  =====================================================
echo            BUILD SUCCESSFUL!  v%VER%
echo  =====================================================
echo.
echo   Aap ki Krexion installer file:
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

start "" explorer.exe "%BUILD_DIR%\installer\Output"

set "FINAL_EC=0"

:END_PAUSE
echo.
echo  =====================================================
echo   SCRIPT FINISHED  (exit code: %FINAL_EC%)
echo  =====================================================
echo.
echo   Yeh window khuli rahegi. Koi key dabayein band karne ke liye.
pause
exit /b %FINAL_EC%
