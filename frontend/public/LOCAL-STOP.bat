@echo off
title Krexion - STOP
color 0E
echo ============================================================
echo   Krexion - Stopping Services
echo ============================================================
echo.

echo [STOP] Backend window band kar raha hoon...
taskkill /FI "WINDOWTITLE eq Krexion Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Administrator: Krexion Backend*" /T /F >nul 2>&1

echo [STOP] Frontend window band kar raha hoon...
taskkill /FI "WINDOWTITLE eq Krexion Frontend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Administrator: Krexion Frontend*" /T /F >nul 2>&1

:: Hard fallback - kill any uvicorn / serve / node processes that match our ports
echo [STOP] Port 8001 / 3000 par koi process ho to band kar raha hoon...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001 " ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 " ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

color 0A
echo.
echo [STOP] Done. Krexion services band ho gayi hain.
echo        (MongoDB service background mein chalti rahe gi - sahi hai)
echo.
pause
