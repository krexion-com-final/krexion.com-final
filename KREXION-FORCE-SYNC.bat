@echo off
REM ════════════════════════════════════════════════════════════════════
REM   Krexion — Force Sync from GitHub + Clean Rebuild
REM   ────────────────────────────────────────────────
REM   Use this when a regular `docker compose up -d --build` doesn't
REM   pick up the latest code (typically because the folder was
REM   originally extracted from a ZIP, not `git clone`d — so `git pull`
REM   was a no-op, AND Docker's COPY layer cache stayed stale).
REM
REM   What this script does:
REM     1. Ensures the current folder is a git repo pointing at the
REM        canonical remote `https://github.com/lenovogen03/lenovo-krexion.git`
REM     2. Fetches + HARD RESETS to origin/main (overwrites any local edits)
REM     3. Rebuilds the backend image with --no-cache (bypasses the stale
REM        COPY layer) and forces container recreation.
REM
REM   After this, future updates can use plain `KREXION-UPDATE.bat`.
REM ════════════════════════════════════════════════════════════════════

setlocal ENABLEDELAYEDEXPANSION
pushd "%~dp0"

echo.
echo ============================================================
echo   Krexion — Force Sync from GitHub + Clean Rebuild
echo ============================================================
echo.

REM -- Verify Docker is running -----------------------------------------
docker info > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running. Start it and retry.
    pause
    exit /b 1
)

REM -- Verify git is installed ------------------------------------------
git --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] git is not installed or not on PATH.
    echo         Install from https://git-scm.com/download/win then retry.
    pause
    exit /b 1
)

set "REPO_URL=https://github.com/lenovogen03/lenovo-krexion.git"

REM -- Step 1: Ensure folder is a git repo with correct remote ----------
echo [1/5] Checking git repository state...

if not exist ".git" (
    echo        .git folder missing — initializing new repo...
    git init
    git remote add origin %REPO_URL%
) else (
    for /f "tokens=* usebackq" %%u in (`git remote get-url origin 2^>nul`) do set "CURRENT_REMOTE=%%u"
    if "!CURRENT_REMOTE!"=="" (
        echo        origin remote missing — adding...
        git remote add origin %REPO_URL%
    ) else if /I not "!CURRENT_REMOTE!"=="%REPO_URL%" (
        echo        origin points to !CURRENT_REMOTE! — fixing to %REPO_URL%
        git remote set-url origin %REPO_URL%
    ) else (
        echo        origin already set correctly.
    )
)

REM -- Step 2: Fetch + hard reset to origin/main ------------------------
echo.
echo [2/5] Fetching latest code from origin/main...
git fetch origin main
if errorlevel 1 (
    echo [ERROR] git fetch failed — check your internet connection.
    pause
    exit /b 1
)

echo.
echo [3/5] HARD RESET to origin/main (local edits will be discarded)...
git reset --hard origin/main
if errorlevel 1 (
    echo [ERROR] git reset failed.
    pause
    exit /b 1
)

REM Print current commit so user can confirm it matches GitHub
for /f "tokens=* usebackq" %%h in (`git log -1 --pretty^=format^:"%%h %%s"`) do echo        On commit: %%h

REM -- Step 3.5: Auto-install Google Sheets Service Account JSON --------
REM The gsheets-sa.json file is .gitignore'd (security) so it's never
REM in the repo. We auto-download it from the artifact URL provided
REM during setup. If you rotate the key, replace the URL below OR drop
REM a fresh gsheets-sa.json into backend\secrets\ and this step is
REM skipped (the file already exists check). Without this step the
REM live Google Sheet row-delete feature falls back to read-only mode.
echo.
echo [3.5/5] Ensuring Google Sheets SA JSON is in place...
if not exist "backend\secrets" (
    mkdir "backend\secrets"
)
if exist "backend\secrets\gsheets-sa.json" (
    echo        SA JSON already present — skipping download.
) else (
    echo        SA JSON missing — downloading from artifact URL...
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://customer-assets.emergentagent.com/job_fluid-dynamics-12/artifacts/kt820qb4_gsheets-sa.json' -OutFile 'backend\secrets\gsheets-sa.json' -UseBasicParsing -TimeoutSec 30 } catch { Write-Host '[WARN] SA download failed:' $_.Exception.Message ; exit 0 }"
    if exist "backend\secrets\gsheets-sa.json" (
        echo        SA JSON downloaded successfully.
    ) else (
        echo [WARN] SA JSON download failed — live gsheet row-delete will be DISABLED.
        echo        You can manually drop a fresh JSON at backend\secrets\gsheets-sa.json
        echo        and re-run this script. Continuing without it.
    )
)

REM -- Step 4: Rebuild backend image WITHOUT CACHE ----------------------
echo.
echo [4/5] Rebuilding backend image with --no-cache (bypasses stale COPY layer)...
docker compose build --no-cache backend
if errorlevel 1 (
    echo [ERROR] Docker build failed — check the output above.
    pause
    exit /b 1
)

REM -- Step 5: Restart backend (and cloudflared 2-replica if tunnel) ----
echo.
echo [5/5] Restarting containers...
findstr /R "^TUNNEL_TOKEN=." .env > nul 2>&1
if errorlevel 1 (
    echo        TUNNEL_TOKEN not set — starting backend only ^(no tunnel^).
    docker compose up -d --force-recreate --no-deps backend
) else (
    echo        TUNNEL_TOKEN found — starting backend + 2 cloudflared replicas
    echo        ^(Cloudflare auto-load-balances incoming requests across both^).
    REM Recreate backend first so it's healthy before cloudflared starts
    docker compose up -d --force-recreate --no-deps backend
    REM Then bring up 2 cloudflared instances. --scale overrides the
    REM swarm-only deploy.replicas spec for plain Compose. Removing any
    REM lingering single-instance container with the old container_name
    REM first to avoid a name collision on the very first scale-up.
    docker rm -f krexion-cloudflared > nul 2>&1
    docker compose --profile tunnel up -d --scale cloudflared=2 --force-recreate cloudflared
)

echo.
echo ============================================================
echo   Force sync complete!
echo ============================================================
echo.
echo Verify the new target-screenshot endpoint is live by running:
echo    curl -X POST https://api.krexion.com/api/uploads/target-screenshot
echo Expected: HTTP 401 "Not authenticated"   ^(NOT 405 "Method Not Allowed"^)
echo.
echo Verify cloudflared 2-replica setup by running:
echo    docker compose --profile tunnel ps cloudflared
echo Expected: TWO rows  ^(krexion-cloudflared-1, krexion-cloudflared-2^)
echo.
docker compose --profile tunnel ps

popd
endlocal
