@echo off
REM ======================================================================
REM   KREXION CPI - PROXY BRIDGE DIAGNOSTIC & AUTO-FIX
REM   Tests every layer step-by-step. No worker restart needed for tests.
REM ======================================================================

if "%~1"=="_NESTED_" goto MAIN
set "LOG=%~dp0proxy-bridge-test.log"
echo Diagnostic log: %LOG% > "%LOG%"
"%~f0" _NESTED_ 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOG%' -Append"
pause
exit /b

:MAIN
setlocal EnableDelayedExpansion
title Krexion CPI - Proxy Bridge Diagnostic
color 0E
cls

set "ROOT=C:\Krexion\krexion-cpi-worker"
set "VENV=%ROOT%\venv-cpi-worker\Scripts\python.exe"

echo.
echo  ============================================================
echo    PROXY BRIDGE COMPREHENSIVE DIAGNOSTIC
echo  ============================================================
echo.

REM [1/8] Check files exist
echo [1/8] Code files check
if not exist "%ROOT%\krexion_cpi_worker\proxy_bridge.py" (
    echo        [FAIL] proxy_bridge.py NOT FOUND. Patch nahi laga.
    echo        Fix: Save to GitHub, fresh download, re-extract project.
    pause & exit /b 1
)
echo        [OK] proxy_bridge.py mojood
findstr /C:"get_bridge" "%ROOT%\krexion_cpi_worker\android_engine.py" >nul
if errorlevel 1 (
    echo        [FAIL] android_engine.py mein bridge integration nahi
    echo        Fix: Pichle PowerShell patch script ko phir chalao.
    pause & exit /b 1
)
echo        [OK] android_engine.py patched
echo.

REM [2/8] Find PC LAN IP
echo [2/8] PC LAN IP detection
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.PrefixOrigin -eq 'Dhcp' -or $_.PrefixOrigin -eq 'Manual' } ^| Where-Object { $_.IPAddress -notlike '169.*' -and $_.IPAddress -notlike '127.*' } ^| Select-Object -First 1).IPAddress"') do set "PC_IP=%%i"
echo        PC LAN IP: %PC_IP%
echo.

REM [3/8] Test upstream proxy directly
echo [3/8] Direct upstream proxy test (UK)
"%VENV%" -c "import asyncio,httpx; \
async def t(): \
 async with httpx.AsyncClient(proxy='http://260202i9bQO-resi-UK-ip-534707743:eeTlJJ6Ot7gzPYG@eu.proxy-jet.io:1010', timeout=20, verify=False) as c: \
  r=await c.get('https://api.ipify.org?format=json'); print(f'        IP: {r.text}'); \
asyncio.run(t())" 2>&1
echo.

REM [4/8] Start bridge in background and test
echo [4/8] Starting bridge ^& testing local connectivity
start /B "" "%VENV%" -c "import asyncio; \
import sys; sys.path.insert(0,r'%ROOT%'); \
from krexion_cpi_worker.proxy_bridge import ProxyBridge; \
async def main(): \
 b=ProxyBridge(8788); await b.start(); \
 b.set_upstream('260202i9bQO-resi-UK-ip-534707743:eeTlJJ6Ot7gzPYG@eu.proxy-jet.io:1010'); \
 print(f'        Bridge ready on 0.0.0.0:8788, LAN IP {b.lan_ip}'); \
 await asyncio.sleep(60); \
asyncio.run(main())" >nul 2>&1

timeout /t 3 /nobreak >nul

echo        Testing 127.0.0.1:8788 (local loopback)
"%VENV%" -c "import httpx; r=httpx.get('https://api.ipify.org?format=json',proxy='http://127.0.0.1:8788',timeout=20,verify=False); print(f'        Bridge IP: {r.text}')" 2>&1
echo.

REM [5/8] Open firewall port
echo [5/8] Windows Firewall port 8788
powershell -NoProfile -Command "Get-NetFirewallRule -DisplayName 'Krexion CPI Proxy Bridge' -ErrorAction SilentlyContinue | Remove-NetFirewallRule" 2>nul
powershell -NoProfile -Command "New-NetFirewallRule -DisplayName 'Krexion CPI Proxy Bridge' -Direction Inbound -LocalPort 8788 -Protocol TCP -Action Allow -Profile Any" >nul 2>&1
echo        [OK] Firewall rule recreated
echo.

REM [6/8] Test from "phone" perspective using PC LAN IP
echo [6/8] LAN IP test (simulates phone connecting from WiFi)
"%VENV%" -c "import httpx; r=httpx.get('https://api.ipify.org?format=json',proxy='http://%PC_IP%:8788',timeout=20,verify=False); print(f'        IP via LAN bridge: {r.text}')" 2>&1
echo.

REM [7/8] Phone connectivity test
echo [7/8] Phone connectivity test (USB)
where adb >nul 2>&1
if errorlevel 1 (
    echo        [SKIP] adb not on PATH
) else (
    echo        Listing devices:
    adb devices -l
    echo.
    echo        Phone se PC bridge tak ping test:
    adb shell ping -c 2 %PC_IP% 2>&1 | findstr /C:"bytes from" /C:"100% packet loss"
    echo.
    echo        Phone WiFi info:
    adb shell ip route 2>&1 | findstr "wlan"
    echo.
    echo        Phone se bridge tak HTTP test:
    adb shell "echo -e 'GET https://api.ipify.org HTTP/1.1\r\nHost: api.ipify.org\r\n\r\n' | nc -w 5 %PC_IP% 8788" 2>&1
)
echo.

REM Kill any running bridge testers
taskkill /F /IM python.exe /FI "WINDOWTITLE eq " >nul 2>&1

REM [8/8] Summary
echo  ============================================================
echo    DIAGNOSTIC COMPLETE
echo  ============================================================
echo.
echo    KEY OUTPUTS TO VERIFY (above):
echo      [3/8] Direct upstream IP   = some UK IP (proves upstream works)
echo      [4/8] Bridge local IP      = SAME UK IP (proves bridge works)
echo      [6/8] LAN bridge IP        = SAME UK IP (proves LAN reachable)
echo      [7/8] Phone ping           = "bytes from %PC_IP%" (proves WiFi)
echo.
echo    AGAR Step 6 fail kare:
echo      - Phone aur PC SAME WiFi par hai? (mobile data nahi)
echo      - Antivirus block kar raha port 8788?
echo      - Router mein "client isolation" off hai?
echo.
echo    AGAR Step 7 ping fail kare:
echo      - Phone WiFi kholo: Settings -^> WiFi -^> apna router select
echo      - Mobile data DISABLE karo (sirf WiFi)
echo      - Router admin mein dekho phone IP same subnet mein
echo.
echo    Log saved: %LOG%
echo.
endlocal
