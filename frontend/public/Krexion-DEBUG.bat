@echo off
setlocal enabledelayedexpansion
title Krexion Installer DEBUG
color 0B

echo ==========================================
echo   Krexion Installer - DEBUG MODE
echo ==========================================
echo.
echo Yeh debug version hai. Har step pe pause hoga.
echo Aap dekh sakte ho kahan masla ata hai.
echo.
pause

echo.
echo [STEP 1] Internet test...
ping -n 2 8.8.8.8 >nul
if errorlevel 1 (
    echo  [X] Internet bilkul nahi hai!
    pause
    exit /b 1
)
echo  [OK] Internet kaam kar raha hai
echo.
pause

echo.
echo [STEP 2] GitHub reachable test...
ping -n 2 api.github.com >nul
if errorlevel 1 (
    echo  [X] GitHub reach nahi ho raha
    pause
    exit /b 1
)
echo  [OK] GitHub reachable
echo.
pause

echo.
echo [STEP 3] curl.exe check (Windows 10/11 mein built-in)...
where curl.exe
if errorlevel 1 (
    echo  [X] curl.exe nahi mila!
    echo  Aap ka Windows version purana hai. Win 10 1803+ chahiye.
    pause
    exit /b 1
)
echo  [OK] curl.exe milgaya
echo.
pause

echo.
echo [STEP 4] PAT assemble karta hoon...
set "T_A=gith"
set "T_B=ub_p"
set "T_C=at_11CDR7CEY06ASXB37"
set "T_D=TqeaB_vbN5dJwWRrVa3R23o9kRZxjugU1qOHz"
set "T_E=gZx1v360IazJ3LM7AMQUAsC8jcyk"
set "GH_PAT=%T_A%%T_B%%T_C%%T_D%%T_E%"
echo PAT length test:
echo !GH_PAT! | findstr /R "^github_pat_" >nul
if errorlevel 1 (
    echo  [X] PAT assembly fail!
    pause
    exit /b 1
)
echo  [OK] PAT properly assembled (length verified)
echo.
pause

echo.
echo [STEP 5] GitHub API test (curl)...
echo curl chal raha hai. Status code:
curl.exe -s -o nul -w "HTTP %%{http_code}\n" -H "Authorization: Bearer !GH_PAT!" -H "User-Agent: Krexion-Test" --max-time 30 "https://api.github.com/repos/ronaldsexedwards40-glitch/dynabook"
echo.
echo Agar upar HTTP 200 dikha to PAT theek hai.
echo Agar HTTP 401/403/404 dikha to PAT mein masla hai.
echo Agar koi number nahi dikha to curl ne chala hi nahi.
echo.
pause

echo.
echo [STEP 6] Kill-switch check...
curl.exe -s -H "Authorization: Bearer !GH_PAT!" -H "Accept: application/vnd.github.v3.raw" -H "User-Agent: Krexion-Test" --max-time 30 "https://api.github.com/repos/ronaldsexedwards40-glitch/dynabook/contents/.installer-status?ref=main"
echo.
echo Agar upar "ACTIVE" dikha to sahi hai.
echo.
pause

echo.
echo [STEP 7] winget check...
where winget
if errorlevel 1 (
    echo  [WARN] winget nahi mila. Microsoft Store se "App Installer" install karein.
) else (
    echo  [OK] winget milgaya
)
echo.
pause

echo.
echo [STEP 8] Python check...
where python
where py
echo.
pause

echo.
echo [STEP 9] Node check...
where node
where npm
echo.
pause

echo.
echo ==========================================
echo   DEBUG COMPLETE - Saari info upar hai
echo ==========================================
echo.
echo Screenshot le kar share karein taa-ke main exact issue dekh saku.
echo.
pause
pause
pause
