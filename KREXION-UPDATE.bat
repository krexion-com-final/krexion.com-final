@echo off
REM ════════════════════════════════════════════════════════════════════
REM   Krexion — Quick Update
REM   ─────────────────────
REM   Pulls latest code from GitHub, rebuilds, restarts. ~3-5 min.
REM   Use this for ongoing feature updates after the first deploy.
REM ════════════════════════════════════════════════════════════════════

setlocal
pushd "%~dp0"

echo.
echo ╔════════════════════════════════════════╗
echo ║   Krexion — Quick Update              ║
echo ╚════════════════════════════════════════╝
echo.

REM Verify Docker is up
docker info > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running. Start it from the Start menu and retry.
    pause
    exit /b 1
)

echo [1/4] Pulling latest code...
git fetch origin
git pull --ff-only
if errorlevel 1 (
    echo [WARN] git pull failed - you may have local changes. Stash them with:
    echo        git stash push -u -m "manual-stash"
    pause
    exit /b 1
)

echo.
echo [2/4] Stopping old containers...
docker compose down --remove-orphans

echo.
echo [2.5/4] Ensuring Google Sheets SA JSON is in place...
if not exist "backend\secrets" mkdir "backend\secrets"
if exist "backend\secrets\gsheets-sa.json" (
    echo        SA JSON present.
) else (
    echo        SA JSON missing — downloading from artifact URL...
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://customer-assets.emergentagent.com/job_fluid-dynamics-12/artifacts/kt820qb4_gsheets-sa.json' -OutFile 'backend\secrets\gsheets-sa.json' -UseBasicParsing -TimeoutSec 30 } catch { Write-Host '[WARN] SA download failed:' $_.Exception.Message ; exit 0 }"
    if exist "backend\secrets\gsheets-sa.json" (echo        SA JSON downloaded.) else (echo [WARN] SA JSON missing - live gsheet delete will be disabled.)
)

echo.
echo [3/4] Building new images...
docker compose build

echo.
echo [4/4] Starting services...

REM Detect if TUNNEL_TOKEN is set in .env
findstr /R "^TUNNEL_TOKEN=." .env > nul 2>&1
if errorlevel 1 (
    echo        TUNNEL_TOKEN not set — starting backend only.
    docker compose up -d
) else (
    echo        TUNNEL_TOKEN found — starting backend + 2 cloudflared replicas
    echo        for high-throughput load balancing.
    REM Remove any leftover single-instance container before scaling up
    docker rm -f krexion-cloudflared > nul 2>&1
    docker compose --profile tunnel up -d --scale cloudflared=2
)

echo.
echo ╔════════════════════════════════════════╗
echo ║   Update complete!                     ║
echo ║                                        ║
echo ║   Status:                              ║
echo ╚════════════════════════════════════════╝
docker compose --profile tunnel ps

popd
endlocal
