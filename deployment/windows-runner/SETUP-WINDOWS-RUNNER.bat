@echo off
setlocal
:: ============================================================================
::  Krexion Windows Runner -- One-Click Setup Launcher
:: ============================================================================
::  Ye .bat file aap ki Windows PC pe self-hosted GitHub Actions runner
::  install karega taake har deploy par Windows + Electron builds free me
::  automatically ban jayen (GitHub minutes consume nahi honge).
::
::  Steps:
::    1. Right-click ye file -> "Run as administrator"
::    2. Prompt me apna GitHub PAT paste karo (jo pehle diya tha)
::    3. Wait ~5-10 min while it installs Python, Node, Yarn, Inno Setup, etc.
::    4. Ho gaya. Ab har `backend/VERSION` bump par ye PC build karegi.
:: ============================================================================

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Ye script Administrator ke tor par run karo.
    echo         Right-click -^> Run as administrator
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo   KREXION WINDOWS RUNNER SETUP
echo ================================================================================
echo.
echo   Ye script aap ki PC pe permanent GitHub Actions runner install karega.
echo   Time required: ~5-10 min (first time). Aap ka internet chahiye.
echo.
echo   Aap ka GitHub Personal Access Token (PAT) chahiye jis me `repo` +
echo   `workflow` scope ho.
echo.

set /p PAT="Apna GitHub PAT paste karo (ghp_xxxxx...): "
if "%PAT%"=="" (
    echo.
    echo [ERROR] PAT khali hai. Cancel.
    pause
    exit /b 1
)

echo.
echo Starting setup...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SETUP-WINDOWS-RUNNER.ps1" -GithubPAT "%PAT%"
set rc=%errorlevel%

echo.
if %rc% equ 0 (
    echo ================================================================================
    echo   SUCCESS! Runner online hai.
    echo   Verify: https://github.com/krexion-com-final/krexion.com-final/settings/actions/runners
    echo ================================================================================
) else (
    echo ================================================================================
    echo   SETUP FAILED. Upar wale errors dekho aur `WINDOWS-RUNNER-GUIDE.md` refer karo.
    echo ================================================================================
)
echo.
pause
exit /b %rc%
