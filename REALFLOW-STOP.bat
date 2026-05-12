@echo off
REM Stop all RealFlow services (backend, mongo, cloudflared)
setlocal
pushd "%~dp0"
echo Stopping RealFlow services...
docker compose --profile tunnel down
echo.
echo All RealFlow services stopped.
echo (Mongo data is preserved in the named volume.)
popd
endlocal
