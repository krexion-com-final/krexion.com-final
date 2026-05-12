@echo off
setlocal EnableExtensions EnableDelayedExpansion
title RealFlow Diagnose
color 0E

cd /d "%~dp0"
set "OUT=%~dp0diagnose-output.txt"
if exist "%OUT%" del /F /Q "%OUT%" >nul 2>&1

echo Diagnose chal raha hai... output is file mein save hoga:
echo    %OUT%
echo.

(
    echo ==========================================
    echo  RealFlow Diagnose Report
    echo  Date: %DATE% %TIME%
    echo ==========================================
    echo.

    echo === 1. Latest commits ^(top 3^) ===
    git log --oneline -3 2^>^&1
    echo.

    echo === 2. Fix string in server.py? ===
    findstr /C:"Skipping user without id" "backend\server.py" 2^>^&1
    if errorlevel 1 echo    [NOT FOUND] Fix code abhi server.py mein nahi hai
    echo.

    echo === 3. Backend container status ===
    docker ps --filter "name=realflow-backend" --format "{{.Names}} | {{.Status}} | {{.Image}}" 2^>^&1
    echo.

    echo === 4. Mongo container status ===
    docker ps --filter "name=realflow-mongo" --format "{{.Names}} | {{.Status}}" 2^>^&1
    echo.

    echo === 5. Cloudflared container status ===
    docker ps --filter "name=realflow-cloudflared" --format "{{.Names}} | {{.Status}}" 2^>^&1
    echo.

    echo === 6. Backend last 40 log lines ===
    docker logs --tail 40 realflow-backend 2^>^&1
    echo.
) >> "%OUT%"

REM ── Login + API tests via PowerShell ──
powershell -NoProfile -Command ^
    "$out = '%OUT%';" ^
    "Add-Content $out '=== 7. LOCAL Login test ===';" ^
    "try {" ^
        "$body = @{email='admin@realflow.local';password='admin123'} | ConvertTo-Json;" ^
        "$tok = (Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/admin/login' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 10).access_token;" ^
        "Add-Content $out ('   TOKEN OK: ' + $tok.Substring(0,25) + '...');" ^
        "" ^
        "Add-Content $out '';" ^
        "Add-Content $out '=== 8. Stats endpoint ===';" ^
        "$s = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/admin/stats' -Headers @{Authorization=('Bearer ' + $tok)} -TimeoutSec 10;" ^
        "Add-Content $out ($s | ConvertTo-Json);" ^
        "" ^
        "Add-Content $out '';" ^
        "Add-Content $out '=== 9. LOCAL Users list ===';" ^
        "try {" ^
            "$u = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/admin/users' -Headers @{Authorization=('Bearer ' + $tok)} -TimeoutSec 15;" ^
            "Add-Content $out ('   COUNT: ' + $u.Count);" ^
            "Add-Content $out ($u | Select-Object email,name,status,created_at,id | ConvertTo-Json);" ^
        "} catch {" ^
            "Add-Content $out ('   USERS API FAIL: ' + $_.Exception.Message);" ^
            "if ($_.Exception.Response) {" ^
                "$rs = $_.Exception.Response.GetResponseStream();" ^
                "$sr = New-Object IO.StreamReader($rs);" ^
                "Add-Content $out ('   BODY: ' + $sr.ReadToEnd())" ^
            "}" ^
        "};" ^
        "" ^
        "Add-Content $out '';" ^
        "Add-Content $out '=== 10. PUBLIC Users list ===';" ^
        "try {" ^
            "$u2 = Invoke-RestMethod -Uri 'https://api.realflow.online/api/admin/users' -Headers @{Authorization=('Bearer ' + $tok)} -TimeoutSec 20;" ^
            "Add-Content $out ('   PUBLIC COUNT: ' + $u2.Count);" ^
        "} catch {" ^
            "Add-Content $out ('   PUBLIC FAIL: ' + $_.Exception.Message)" ^
        "};" ^
    "} catch {" ^
        "Add-Content $out ('   LOGIN FAIL: ' + $_.Exception.Message)" ^
    "}"

echo.
echo Done. Report file: %OUT%
echo.
echo Notepad mein khol raha hun...
timeout /t 2 /nobreak >nul
notepad "%OUT%"
echo.
pause
endlocal
