@echo off
REM +================================================================+
REM |   Krexion GO ONLINE - One-Click Global Access                 |
REM |                                                                 |
REM |   What this does:                                               |
REM |   - Creates a public HTTPS URL for your Krexion                |
REM |   - Works from your mobile, laptop, anywhere in the world      |
REM |   - URL is shown in a nice window (with QR code to scan)        |
REM |   - Just double-click. Nothing else.                            |
REM |                                                                 |
REM |   No signup. No domain. No Emergent. Pure Cloudflare.           |
REM +================================================================+

setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Run main PowerShell logic
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0GO-ONLINE.ps1"

if %errorLevel% neq 0 (
    echo.
    echo  Something went wrong. Press any key to close.
    pause >nul
)

endlocal
