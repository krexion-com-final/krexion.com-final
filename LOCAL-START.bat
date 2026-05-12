@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title RealFlow - Local Deploy
color 0B

echo ============================================================
echo   RealFlow - Local One-Click Deploy (Windows / No Docker)
echo ============================================================
echo.

:: Disable Microsoft Store python.exe stub for this session
set "PATH=%PATH:C:\Users\%USERNAME%\AppData\Local\Microsoft\WindowsApps=%"

:: ============ Detect first-time setup ============
if exist ".installed" (
    echo [INFO] Already installed. Services start kar raha hoon...
    goto :START_SERVICES
)

:: ============ FIRST-TIME SETUP ============
echo [SETUP] Pehli baar setup chal raha hai - approx 8-12 minute.
echo         (Python + Node + MongoDB + dependencies install hongi)
echo.

:: ---- Check winget ----
where winget >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] winget nahi mila.
    echo         Microsoft Store khol kar "App Installer" install karein.
    pause
    exit /b 1
)

:: ====================================================================
:: STEP 1: Install Python 3.11 (force install via winget, ignore stubs)
:: ====================================================================
echo.
echo [SETUP] [1/5] Python 3.11 install ho raha hai (skip agar exist)...
set "PY_EXE="
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if "!PY_EXE!"=="" if exist "%ProgramFiles%\Python311\python.exe" set "PY_EXE=%ProgramFiles%\Python311\python.exe"
if "!PY_EXE!"=="" if exist "%ProgramFiles(x86)%\Python311\python.exe" set "PY_EXE=%ProgramFiles(x86)%\Python311\python.exe"

if "!PY_EXE!"=="" (
    echo         winget se Python 3.11 install ho raha hai...
    winget install -e --id Python.Python.3.11 --silent --scope user --accept-package-agreements --accept-source-agreements
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
    if "!PY_EXE!"=="" if exist "%ProgramFiles%\Python311\python.exe" set "PY_EXE=%ProgramFiles%\Python311\python.exe"
)

if "!PY_EXE!"=="" (
    color 0C
    echo [ERROR] Python 3.11 install fail ho gaya.
    echo         Manually install karein: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo         [OK] Python at: !PY_EXE!

:: ====================================================================
:: STEP 2: Install Node.js 20 LTS
:: ====================================================================
echo.
echo [SETUP] [2/5] Node.js 20 LTS install ho raha hai...
set "NODE_EXE="
if exist "%ProgramFiles%\nodejs\node.exe" set "NODE_EXE=%ProgramFiles%\nodejs\node.exe"
if "!NODE_EXE!"=="" if exist "%ProgramFiles(x86)%\nodejs\node.exe" set "NODE_EXE=%ProgramFiles(x86)%\nodejs\node.exe"

if "!NODE_EXE!"=="" (
    echo         winget se Node.js install ho raha hai...
    winget install -e --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
    if exist "%ProgramFiles%\nodejs\node.exe" set "NODE_EXE=%ProgramFiles%\nodejs\node.exe"
)

if "!NODE_EXE!"=="" (
    color 0C
    echo [ERROR] Node.js install fail.
    echo         Manually: https://nodejs.org/
    pause
    exit /b 1
)
set "NODE_DIR=%ProgramFiles%\nodejs"
echo         [OK] Node at: !NODE_EXE!

:: ====================================================================
:: STEP 3: Install MongoDB Community 7
:: ====================================================================
echo.
echo [SETUP] [3/5] MongoDB Community 7 install ho raha hai...
sc query MongoDB >nul 2>&1
if errorlevel 1 (
    echo         winget se MongoDB install ho raha hai...
    winget install -e --id MongoDB.Server --silent --accept-package-agreements --accept-source-agreements
    timeout /t 5 /nobreak >nul
)
sc query MongoDB >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] MongoDB service install fail.
    pause
    exit /b 1
)
echo         [OK] MongoDB service installed

:: Refresh PATH
set "PATH=!NODE_DIR!;%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;%ProgramFiles%\MongoDB\Server\7.0\bin;%ProgramFiles%\MongoDB\Server\6.0\bin;%PATH%"

:: ====================================================================
:: STEP 4: Install yarn + serve globally via npm
:: ====================================================================
echo.
echo [SETUP] [4/5] Yarn + serve install...
call "%NODE_DIR%\npm.cmd" install -g yarn serve --silent
if errorlevel 1 (
    color 0E
    echo [WARN] Yarn/serve install mein issue, retrying...
    call "%NODE_DIR%\npm.cmd" install -g yarn serve
)
set "YARN_CMD=%AppData%\npm\yarn.cmd"
set "SERVE_CMD=%AppData%\npm\serve.cmd"
if not exist "!YARN_CMD!" (
    color 0C
    echo [ERROR] Yarn install fail.
    pause
    exit /b 1
)
echo         [OK] Yarn at: !YARN_CMD!

:: ====================================================================
:: STEP 5: Generate .env files + admin password
:: ====================================================================
echo.
echo [SETUP] [5/5] .env files + admin password generate...

set "JWT_SECRET="
for /f "delims=" %%i in ('powershell -NoProfile -Command "-join ((48..57)+(65..90)+(97..122) ^| Get-Random -Count 48 ^| %% {[char]$_})"') do set "JWT_SECRET=%%i"
if "!JWT_SECRET!"=="" set "JWT_SECRET=realflow-%random%%random%%random%-jwt"

set "ADMIN_PASS="
for /f "delims=" %%i in ('powershell -NoProfile -Command "$c='abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'; -join (1..16 ^| %% { $c[(Get-Random -Maximum $c.Length)] })"') do set "ADMIN_PASS=%%i"
if "!ADMIN_PASS!"=="" set "ADMIN_PASS=Admin@%random%%random%"

set "POSTBACK_TOK="
for /f "delims=" %%i in ('powershell -NoProfile -Command "-join ((48..57)+(65..90)+(97..122) ^| Get-Random -Count 24 ^| %% {[char]$_})"') do set "POSTBACK_TOK=%%i"
if "!POSTBACK_TOK!"=="" set "POSTBACK_TOK=pb-%random%%random%"

> backend\.env (
    echo MONGO_URL=mongodb://localhost:27017
    echo DB_NAME=realflow
    echo JWT_SECRET_KEY=!JWT_SECRET!
    echo ADMIN_EMAIL=admin@realflow.local
    echo ADMIN_PASSWORD=!ADMIN_PASS!
    echo POSTBACK_TOKEN=!POSTBACK_TOK!
    echo APP_URL=http://localhost:3000
    echo PUBLIC_BASE_URL=http://localhost:8001
    echo CORS_ORIGINS=*
    echo RESEND_API_KEY=
    echo RESEND_FROM=no-reply@realflow.local
    echo SENDER_EMAIL=onboarding@resend.dev
    echo GOOGLE_CLIENT_ID=
    echo GOOGLE_CLIENT_SECRET=
    echo GOOGLE_REDIRECT_URI=
)

> frontend\.env (
    echo REACT_APP_BACKEND_URL=http://localhost:8001
    echo WDS_SOCKET_PORT=0
    echo ENABLE_HEALTH_CHECK=false
)

> CREDENTIALS.txt (
    echo ============================================================
    echo  RealFlow Admin Credentials - SAFE RAKHEIN
    echo ============================================================
    echo  Frontend:    http://localhost:3000
    echo  Backend:     http://localhost:8001
    echo  Admin URL:   http://localhost:3000/admin
    echo.
    echo  Admin Email:    admin@realflow.local
    echo  Admin Password: !ADMIN_PASS!
    echo ============================================================
)

echo.
echo [SETUP] Admin Password: !ADMIN_PASS!
echo         Saved in CREDENTIALS.txt

:: ====================================================================
:: Python venv + backend deps
:: ====================================================================
echo.
echo [SETUP] Python venv + backend dependencies (5-7 min)...
"!PY_EXE!" -m venv .venv
if errorlevel 1 (
    color 0C
    echo [ERROR] venv banane mein masla.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    color 0C
    echo [ERROR] Python deps install fail.
    pause
    exit /b 1
)

:: ====================================================================
:: Frontend deps + build
:: ====================================================================
echo.
echo [SETUP] Frontend yarn install + production build (3-5 min)...
cd frontend
call "!YARN_CMD!" install
if errorlevel 1 (
    color 0E
    echo [WARN] yarn install issue, retrying with --force...
    call "!YARN_CMD!" install --force
)
set "NODE_OPTIONS=--max-old-space-size=4096"
call "!YARN_CMD!" build
if errorlevel 1 (
    color 0C
    echo [ERROR] Frontend build fail.
    cd ..
    pause
    exit /b 1
)
cd ..

:: Mark installed
> .installed echo done
echo.
color 0A
echo ============================================================
echo   SETUP COMPLETE! Services start ho rahi hain...
echo ============================================================
echo.

:: ============================================================
:: START SERVICES
:: ============================================================
:START_SERVICES
color 0B

:: Refresh PATH + paths
set "PY_EXE=%~dp0.venv\Scripts\python.exe"
set "YARN_CMD=%AppData%\npm\yarn.cmd"
set "SERVE_CMD=%AppData%\npm\serve.cmd"
set "PATH=%ProgramFiles%\nodejs;%AppData%\npm;%ProgramFiles%\MongoDB\Server\7.0\bin;%ProgramFiles%\MongoDB\Server\6.0\bin;%PATH%"

echo [START] MongoDB service check...
net start MongoDB >nul 2>&1
sc query MongoDB | findstr /I "RUNNING" >nul
if errorlevel 1 (
    color 0C
    echo [ERROR] MongoDB service nahi chal rahi.
    echo         services.msc -^> MongoDB -^> Start
    pause
    exit /b 1
)
echo         [OK] MongoDB OK

:: Start backend
echo [START] Backend (FastAPI) launching on http://localhost:8001
start "RealFlow Backend" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && cd backend && python -m uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1"

timeout /t 5 /nobreak >nul

:: Start frontend
echo [START] Frontend launching on http://localhost:3000
start "RealFlow Frontend" cmd /k "cd /d %~dp0\frontend && %AppData%\npm\serve.cmd -s build -l 3000"

timeout /t 3 /nobreak >nul

:: Open browser
start "" http://localhost:3000

color 0A
echo.
echo ============================================================
echo   REALFLOW IS RUNNING
echo ============================================================
echo   Frontend:    http://localhost:3000
echo   Backend API: http://localhost:8001
echo   Admin Panel: http://localhost:3000/admin
echo.
echo   Credentials: CREDENTIALS.txt
echo   Stop:        LOCAL-STOP.bat
echo ============================================================
echo.
echo   Backend + Frontend windows alag se khulay hain.
echo   Yeh window band kar sakte ho.
echo.
pause
exit /b 0
