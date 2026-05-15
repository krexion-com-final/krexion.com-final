@echo off
setlocal EnableDelayedExpansion
title Krexion - Admin Credentials Manager
color 0B

REM ====================================================================
REM   Krexion ADMIN CREDENTIALS MANAGER (v2 - smart folder detection)
REM   Auto-detects the folder where krexion-backend container was created.
REM ====================================================================

cls
echo.
echo  ============================================================
echo    Krexion - ADMIN CREDENTIALS MANAGER
echo  ============================================================
echo.

REM ───── Smart project root detection ─────
REM Priority 1: Find folder where running krexion-backend container was started from
REM Priority 2: Hardcoded OLD install path
REM Priority 3: Script's own directory
set "ROOT="
set "DETECTED_FROM=none"

REM Try to detect from existing container
for /f "usebackq delims=" %%p in (`docker inspect krexion-backend --format "{{ index .Config.Labels \"com.docker.compose.project.working_dir\" }}" 2^>nul`) do (
    set "ROOT=%%p"
    set "DETECTED_FROM=running container"
)

REM If not found, try OLD hardcoded path
if "%ROOT%"=="" (
    if exist "F:\online\real flow\real flow amna\krexion-amna-main\krexion-amna-main\docker-compose.yml" (
        set "ROOT=F:\online\real flow\real flow amna\krexion-amna-main\krexion-amna-main"
        set "DETECTED_FROM=hardcoded OLD path"
    )
)

REM Fallback: script's own directory
if "%ROOT%"=="" (
    if exist "%~dp0docker-compose.yml" (
        set "ROOT=%~dp0"
        set "DETECTED_FROM=script directory"
    )
)

REM Trim trailing slash
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if "%ROOT:~-1%"=="/" set "ROOT=%ROOT:~0,-1%"

if "%ROOT%"=="" (
    echo  [ERROR] Project root nahi mila. Manually .env edit karein:
    echo            F:\online\real flow\real flow amna\krexion-amna-main\krexion-amna-main\.env
    pause & exit /b 1
)

echo    Project root: %ROOT%
echo    Detected via: %DETECTED_FROM%
echo.

REM Warning if script is in different folder than detected root
if /I not "%~dp0"=="%ROOT%\" (
    echo    [INFO] Script kahin aur se chala hai, lekin actual running install
    echo           hai: %ROOT%
    echo           Iska matlab safe hai - main correct .env ko hi update karunga.
    echo.
)

if not exist "%ROOT%\docker-compose.yml" (
    echo  [ERROR] docker-compose.yml nahi mila is path par.
    pause & exit /b 1
)

set "ENV_FILE=%ROOT%\.env"
if not exist "%ENV_FILE%" (
    type nul > "%ENV_FILE%"
)

REM ───── Read current credentials ─────
set "CURRENT_EMAIL="
set "CURRENT_PASS="

for /f "usebackq tokens=1,* delims==" %%a in ("%ENV_FILE%") do (
    if /I "%%a"=="ADMIN_EMAIL"    set "CURRENT_EMAIL=%%b"
    if /I "%%a"=="ADMIN_PASSWORD" set "CURRENT_PASS=%%b"
)

if "%CURRENT_EMAIL%"=="" set "CURRENT_EMAIL=(not set)"
if "%CURRENT_PASS%"==""  set "CURRENT_PASS=(not set / empty)"

echo  ============================================================
echo    CURRENT ADMIN CREDENTIALS (from %ROOT%\.env)
echo  ============================================================
echo.
echo    Email    : %CURRENT_EMAIL%
echo    Password : %CURRENT_PASS%
echo.
echo  ============================================================
echo.

:ASK
echo    Kya karna hai?
echo.
echo      [1] Same rakhna hai - main inhi se login kar lunga (exit)
echo      [2] Change karna hai - naya email/password set karunga
echo      [3] Sirf password reset to "admin123" (default)
echo.
set "CHOICE="
set /p "CHOICE=   Apna option choose karein (1/2/3): "

if "%CHOICE%"=="1" goto KEEP
if "%CHOICE%"=="2" goto CHANGE
if "%CHOICE%"=="3" goto QUICKRESET
echo    Galat input. 1, 2 ya 3 likhain.
goto ASK

:KEEP
echo.
echo    No changes made.
echo    Aap inhi credentials se login karein:
echo      Email    : %CURRENT_EMAIL%
echo      Password : %CURRENT_PASS%
echo.
pause & exit /b 0

:CHANGE
echo.
echo  ============================================================
echo    NAYI CREDENTIALS DALEIN
echo  ============================================================
echo.

:ASK_EMAIL
set "NEW_EMAIL="
set /p "NEW_EMAIL=   Naya Admin Email (e.g. admin@krexion.local): "
if "%NEW_EMAIL%"=="" (
    echo    Email khali nahi ho sakta. Dobara likhain.
    goto ASK_EMAIL
)

echo.
echo    Naya password type karein (typing dikhe gi nahi - security):
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$p = Read-Host -AsSecureString; $b = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($p); [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($b)"`) do set "NEW_PASS=%%p"

if "%NEW_PASS%"=="" (
    echo    Password khali nahi ho sakta.
    goto CHANGE
)

echo    Password confirm karein (dobara likhain):
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$p = Read-Host -AsSecureString; $b = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($p); [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($b)"`) do set "CONFIRM_PASS=%%p"

if not "%NEW_PASS%"=="%CONFIRM_PASS%" (
    echo.
    echo    [ERROR] Dono passwords match nahi kar rahe! Dobara try.
    goto CHANGE
)

echo.
echo    New Email    : %NEW_EMAIL%
echo    New Password : (hidden - %NEW_PASS:~0,1%***)
set "OK="
set /p "OK=   Confirm karna hai? (y/n): "
if /I not "%OK%"=="y" (
    echo    Cancelled.
    pause & exit /b 0
)
goto APPLY

:QUICKRESET
set "NEW_EMAIL=admin@krexion.local"
set "NEW_PASS=admin123"
echo.
echo    Quick reset:
echo      Email    : %NEW_EMAIL%
echo      Password : %NEW_PASS%

:APPLY
echo.
echo  ============================================================
echo    APPLYING CHANGES
echo  ============================================================
echo.

REM ── Backup ──
echo [1/5] .env backup banaya ja raha hai...
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"`) do set "TS=%%a"
if "!TS!"=="" set "TS=backup"
copy /Y "%ENV_FILE%" "%ENV_FILE%.bak-!TS!" >nul
echo        OK
echo.

REM ── Update .env (and ensure required vars are set) ──
echo [2/5] .env update kar raha hun (admin + safe defaults)...
powershell -NoProfile -Command ^
    "$f='%ENV_FILE%';" ^
    "$email='%NEW_EMAIL%';" ^
    "$pass='%NEW_PASS%';" ^
    "$lines = if (Test-Path $f) { Get-Content $f } else { @() };" ^
    "$out = @();" ^
    "$has = @{};" ^
    "foreach($l in $lines) {" ^
        "if ($l -match '^\s*ADMIN_EMAIL\s*=')        { $out += \"ADMIN_EMAIL=$email\"; $has['email']=$true }" ^
        "elseif ($l -match '^\s*ADMIN_PASSWORD\s*=') { $out += \"ADMIN_PASSWORD=$pass\";  $has['pass']=$true }" ^
        "elseif ($l -match '^\s*JWT_SECRET_KEY\s*=(.*)$') {" ^
            "$v = $matches[1].Trim();" ^
            "if ([string]::IsNullOrWhiteSpace($v)) {" ^
                "$rand = -join ((1..48) | %% { [char[]](48..57+65..90+97..122) | Get-Random });" ^
                "$out += \"JWT_SECRET_KEY=$rand\"" ^
            "} else { $out += $l };" ^
            "$has['jwt']=$true" ^
        "}" ^
        "elseif ($l -match '^\s*POSTBACK_TOKEN\s*=(.*)$') {" ^
            "$v = $matches[1].Trim();" ^
            "if ([string]::IsNullOrWhiteSpace($v)) {" ^
                "$rand = -join ((1..32) | %% { [char[]](48..57+97..122) | Get-Random });" ^
                "$out += \"POSTBACK_TOKEN=$rand\"" ^
            "} else { $out += $l };" ^
            "$has['post']=$true" ^
        "}" ^
        "else { $out += $l }" ^
    "};" ^
    "if (-not $has['email']) { $out += \"ADMIN_EMAIL=$email\" };" ^
    "if (-not $has['pass'])  { $out += \"ADMIN_PASSWORD=$pass\" };" ^
    "if (-not $has['jwt'])   { $rand = -join ((1..48) | %% { [char[]](48..57+65..90+97..122) | Get-Random }); $out += \"JWT_SECRET_KEY=$rand\" };" ^
    "if (-not $has['post'])  { $rand = -join ((1..32) | %% { [char[]](48..57+97..122) | Get-Random }); $out += \"POSTBACK_TOKEN=$rand\" };" ^
    "Set-Content -Path $f -Value $out -Encoding ASCII"

if errorlevel 1 (
    echo  [ERROR] .env update fail.
    pause & exit /b 1
)
echo        OK - admin credentials + JWT_SECRET_KEY + POSTBACK_TOKEN ready
echo.

REM ── Docker check ──
docker info >nul 2>&1
if errorlevel 1 (
    echo  [WARN] Docker chalu nahi hai - .env update ho gaya, lekin restart skip.
    echo         Docker chala kar manually:
    echo            cd "%ROOT%"
    echo            docker compose up -d --force-recreate --no-deps backend
    pause & exit /b 0
)

REM ── Stop conflicting backend container if exists ──
echo [3/5] Existing backend container check...
for /f "usebackq delims=" %%c in (`docker ps -a --filter "name=^krexion-backend$" --format "{{.Names}}" 2^>nul`) do (
    echo        Found: %%c - removing to avoid name conflict...
    docker rm -f krexion-backend >nul 2>&1
)
echo        OK
echo.

REM ── Recreate from CORRECT folder ──
echo [4/5] Backend container start kar raha hun (from %ROOT%)...
pushd "%ROOT%"
docker compose up -d --no-deps backend
if errorlevel 1 (
    echo  [ERROR] Backend start fail. Logs:
    docker compose logs --tail=30 backend
    popd & pause & exit /b 1
)
popd
echo        OK
echo.

REM ── Verify ──
echo [5/5] Login test (15 sec wait)...
timeout /t 15 /nobreak >nul

powershell -NoProfile -Command ^
    "try {" ^
        "$body = @{ email='%NEW_EMAIL%'; password='%NEW_PASS%' } | ConvertTo-Json;" ^
        "$r = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/admin/login' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 10;" ^
        "if ($r.access_token) { Write-Host '       OK - Login WORKING!' -ForegroundColor Green }" ^
        "else { Write-Host '       FAIL - No token returned' -ForegroundColor Red }" ^
    "} catch {" ^
        "Write-Host \"       FAIL: $($_.Exception.Message)\" -ForegroundColor Red;" ^
        "Write-Host '       Check: docker compose logs --tail=50 backend' -ForegroundColor Yellow" ^
    "}"
echo.

echo  ============================================================
echo    DONE!
echo  ============================================================
echo.
echo    Admin Email   : %NEW_EMAIL%
echo    Admin Password: %NEW_PASS%
echo.
echo    Browser mein Krexion URL kholein - Admin Login - login karein.
echo    Backup: %ENV_FILE%.bak-!TS!
echo.
echo  ============================================================
echo.
pause
endlocal
