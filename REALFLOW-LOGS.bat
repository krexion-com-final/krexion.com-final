@echo off
REM Live logs from RealFlow backend
setlocal
pushd "%~dp0"
echo Following backend logs (Ctrl+C to exit)...
docker compose logs -f --tail 100 backend
popd
endlocal
