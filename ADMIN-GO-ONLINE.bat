@echo off
REM +================================================================+
REM |   Krexion ADMIN GO-ONLINE                                      |
REM |                                                                  |
REM |   FOR THE OWNER/ADMIN ONLY -- not for customers.                |
REM |                                                                  |
REM |   What this does:                                                |
REM |   - Creates a public HTTPS URL for YOUR admin server             |
REM |   - URL goes straight to /admin-login                            |
REM |   - Manage licenses, customers, pricing -- all from mobile       |
REM |   - Customers are NOT affected when this is off                  |
REM |                                                                  |
REM |   Difference vs customer GO-ONLINE.bat:                          |
REM |   - This shows YOUR admin credentials in the popup               |
REM |   - URL bookmarks /admin-login directly (one less click)         |
REM |   - Different look so you don't confuse them                     |
REM +================================================================+

setlocal EnableDelayedExpansion
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ADMIN-GO-ONLINE.ps1"

if %errorLevel% neq 0 (
    echo.
    echo  Something went wrong. Press any key to close.
    pause >nul
)

endlocal
