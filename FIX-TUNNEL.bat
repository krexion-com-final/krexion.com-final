@echo off
setlocal EnableExtensions EnableDelayedExpansion
title RealFlow - Cloudflare Tunnel Fix
color 0B

REM ════════════════════════════════════════════════════════════
REM  RealFlow Tunnel Fixer
REM  - Cloudflare error 1033 = cloudflared connector down
REM  - Yeh script TUNNEL_TOKEN ko .env mein dalti hai aur
REM    cloudflared container ko start karti hai (data ko bina chhede)
REM ════════════════════════════════════════════════════════════

cd /d "%~dp0"
set "ROOT=%CD%"
echo.
echo  ============================================================
echo   RealFlow Cloudflare Tunnel Fix
echo  ============================================================
echo.
echo   Folder: !ROOT!
echo.

if not exist "!ROOT!\.env" (
    echo  [X] .env file nahi mili. Pehle RealFlow-AUTO.bat chala ke
    echo      app deploy karo, phir yeh script chalao.
    pause
    exit /b 1
)

REM ─── Token input ───
echo  Cloudflare Zero Trust dashboard se TUNNEL_TOKEN paste karo:
echo  ^(https://one.dash.cloudflare.com -^> Networks -^> Tunnels
echo   -^> realflow tunnel -^> Configure -^> token copy^)
echo.
set "NEW_TOKEN="
set /p "NEW_TOKEN=  Paste TUNNEL_TOKEN: "

if "!NEW_TOKEN!"=="" (
    echo  [X] Token blank hai. Exit.
    pause
    exit /b 1
)

REM Token ke aas paas se quotes/spaces hatao
set "NEW_TOKEN=!NEW_TOKEN:"=!"
for /f "tokens=* delims= " %%t in ("!NEW_TOKEN!") do set "NEW_TOKEN=%%t"

echo.
echo  Token length: 
echo|set /p="    "
powershell -NoProfile -Command "Write-Host ('!NEW_TOKEN!').Length" 2>nul
echo.

REM ─── .env update (TUNNEL_TOKEN line replace ya append) ───
echo  [1/4] .env file update kar raha hun...
set "TMPENV=!ROOT!\.env.tmp"
if exist "!TMPENV!" del /F /Q "!TMPENV!" >nul 2>&1

set "FOUND=0"
for /f "usebackq tokens=1,* delims==" %%a in ("!ROOT!\.env") do (
    if /I "%%a"=="TUNNEL_TOKEN" (
        >> "!TMPENV!" echo TUNNEL_TOKEN=!NEW_TOKEN!
        set "FOUND=1"
    ) else (
        if not "%%b"=="" (
            >> "!TMPENV!" echo %%a=%%b
        ) else (
            >> "!TMPENV!" echo %%a=
        )
    )
)
if "!FOUND!"=="0" (
    >> "!TMPENV!" echo TUNNEL_TOKEN=!NEW_TOKEN!
)
move /Y "!TMPENV!" "!ROOT!\.env" >nul
echo        OK
echo.

REM ─── Old cloudflared container hatao (agar ho) ───
echo  [2/4] Purana cloudflared container saaf kar raha hun...
docker rm -f realflow-cloudflared >nul 2>&1
echo        OK
echo.

REM ─── Tunnel ke saath start ───
echo  [3/4] cloudflared start kar raha hun ^(profile=tunnel^)...
docker compose --profile tunnel up -d
if errorlevel 1 (
    echo  [X] Compose up fail. Logs deikho.
    pause
    exit /b 1
)
echo.

REM Thoda wait for connector to register
echo  [4/4] Connector register hone ka wait ^(15 sec^)...
timeout /t 15 /nobreak >nul

echo.
echo  ============================================================
echo   Status check
echo  ============================================================
docker ps --filter "name=realflow-cloudflared" --format "    {{.Names}}: {{.Status}}"
echo.
echo  Cloudflared container logs ^(last 15 lines^):
docker logs --tail 15 realflow-cloudflared 2>&1
echo.

echo  ============================================================
echo   Test
echo  ============================================================
echo.
echo  Public API test...
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'https://api.realflow.online/api/admin/login' -Method POST -Body (@{email='admin@realflow.local';password='admin123'} ^| ConvertTo-Json) -ContentType 'application/json' -TimeoutSec 20; if ($r.access_token) { Write-Host '  PUBLIC LOGIN: PASS  ✓' -ForegroundColor Green } else { Write-Host '  PUBLIC LOGIN: FAIL (no token)' -ForegroundColor Red } } catch { Write-Host ('  PUBLIC LOGIN: FAIL - ' + $_.Exception.Message) -ForegroundColor Red }"

echo.
echo  ============================================================
echo   Done. Ab browser mein https://realflow.online/admin
echo   khol ke admin@realflow.local / admin123 se login karo.
echo  ============================================================
echo.
pause
endlocal
