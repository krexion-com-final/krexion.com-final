@echo off
REM Krexion CPI Worker — Stop
REM Kills any running worker.py processes.

setlocal
echo Stopping Krexion CPI Worker...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq worker.py*" 2>nul
wmic process where "CommandLine like '%%worker.py%%' and Name='python.exe'" delete 2>nul
echo Done.
endlocal
