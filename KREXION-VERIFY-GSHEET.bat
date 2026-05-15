@echo off
REM ════════════════════════════════════════════════════════════════════
REM   Krexion — Verify Live Google Sheet Setup
REM   ─────────────────────────────────────────
REM   Run AFTER KREXION-FORCE-SYNC.bat to confirm:
REM     1. SA JSON file is mounted inside the backend container
REM     2. gsheet_writer.is_write_enabled() returns True
REM     3. The SA can READ + WRITE your actual Google Sheet
REM     4. Lists all your existing uploads + flags which ones have
REM        gsheet_url set (will live-delete) vs static (won't delete)
REM ════════════════════════════════════════════════════════════════════

setlocal
pushd "%~dp0"

echo.
echo ============================================================
echo   Krexion — Live Google Sheet Verification
echo ============================================================
echo.

docker info > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running.
    pause
    exit /b 1
)

docker ps --format "{{.Names}}" | findstr /B "krexion-backend" > nul
if errorlevel 1 (
    echo [ERROR] krexion-backend container is not running.
    echo         Run KREXION-FORCE-SYNC.bat or KREXION-UPDATE.bat first.
    pause
    exit /b 1
)

echo [1/4] Checking SA JSON file inside container...
docker exec krexion-backend ls -la /app/backend/secrets/gsheets-sa.json 2>nul
if errorlevel 1 (
    echo [FAIL] SA JSON file is NOT inside the container.
    echo        Check that backend\secrets\gsheets-sa.json exists on your PC,
    echo        and that docker-compose.yml mounts ./backend/secrets:/app/backend/secrets:ro
    goto :fail
)
echo        OK.

echo.
echo [2/4] Checking is_write_enabled() reports True...
for /f "tokens=*" %%a in ('docker exec krexion-backend python3 -c "from dotenv import load_dotenv; load_dotenv('/app/backend/.env'); import gsheet_writer; print(gsheet_writer.is_write_enabled())" 2^>nul') do set "WRITE_ENABLED=%%a"
echo        is_write_enabled = %WRITE_ENABLED%
if /I not "%WRITE_ENABLED%"=="True" (
    echo [FAIL] write_enabled is False. Common causes:
    echo         - GOOGLE_SHEETS_SA_PATH env not set (check .env)
    echo         - SA JSON is corrupted (re-download)
    echo         - python `google-auth` library missing (re-build image with --no-cache)
    goto :fail
)

echo.
echo [3/4] Probing read+write access to YOUR sheet...
docker exec krexion-backend python3 -c "from dotenv import load_dotenv; load_dotenv('/app/backend/.env'); import gsheet_writer; tabs = gsheet_writer.list_tabs('https://docs.google.com/spreadsheets/d/1HjxVWDyQUgqBkRt_uds7s5wM9Sk3PNqPPJEzXFuzIfU/edit'); print('TABS_FOUND=' + str(len(tabs)))"
if errorlevel 1 (
    echo [FAIL] Could not read your sheet. Did you share it as Editor with:
    echo        krexion-bot@rpa-data-test.iam.gserviceaccount.com
    goto :fail
)

echo.
echo [4/4] Listing your existing uploads (which ones will live-delete?)
docker exec krexion-backend python3 -c "import os; from pymongo import MongoClient; c = MongoClient(os.environ.get('MONGO_URL', 'mongodb://mongo:27017')); rows=[]; [rows.append((u.get('type','?'), (u.get('name','') or '')[:30], 'YES' if u.get('gsheet_url') else 'NO ', u.get('item_count',0))) for dbn in c.list_database_names() if dbn.startswith('krexion_user_') for u in c[dbn]['uploaded_resources'].find({}, {'_id':0,'name':1,'type':1,'gsheet_url':1,'item_count':1})]; print(f'Total uploads: {len(rows)}'); [print(f'  [{f}] type={t:10s} name={n:30s} items={i:>6d}') for (t,n,f,i) in rows]; ys=sum(1 for r in rows if r[2]=='YES'); ns=sum(1 for r in rows if r[2]=='NO '); print(); print(f'  WITH gsheet_url (live-delete capable): {ys}'); print(f'  WITHOUT gsheet_url (static, no live delete): {ns}')"

echo.
echo ============================================================
echo   ALL CHECKS PASSED
echo ============================================================
echo.
echo If any uploads above show [NO ], live-delete will NOT work for those.
echo To enable live-delete for them: open the panel - Uploaded Things -
echo delete the [NO ] uploads, then re-add them using the
echo "+ Live Google Sheet URL" option (paste your sheet's URL with the
echo correct gid for that tab).
echo.
echo Uploads with [YES] will live-delete from the source sheet during
echo every Real-User-Traffic job (works automatically, no further setup).
echo.

popd
endlocal
exit /b 0

:fail
echo.
echo ============================================================
echo   VERIFICATION FAILED — see error above
echo ============================================================
echo.
popd
endlocal
exit /b 1
