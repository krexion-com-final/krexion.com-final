@echo off
REM Stop all Krexion services (backend, mongo, cloudflared)
setlocal
pushd "%~dp0"
echo Stopping Krexion services...
docker compose --profile tunnel down
echo.
echo All Krexion services stopped.
echo (Mongo data is preserved in the named volume.)
popd
endlocal
