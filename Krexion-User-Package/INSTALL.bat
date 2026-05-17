@echo off
REM ###################################################################
REM #                                                                 #
REM #          KREXION - AAP KA INSTALLER                            #
REM #                                                                 #
REM #  Bas yeh file pe DOUBLE-CLICK karein. Bas.                      #
REM #                                                                 #
REM #  - UAC popup aaye to "YES" click karein                         #
REM #  - 20-30 minute wait karein                                     #
REM #  - Browser khud khulega https://krexion.com pe                  #
REM #                                                                 #
REM #  Window ABHI band NAHI hogi. Agar koi error aaye to             #
REM #  aap easily padh paayenge.                                      #
REM #                                                                 #
REM ###################################################################
setlocal EnableDelayedExpansion

REM ─── Setup transcript file on Desktop so customer always sees logs ──
set "DESKTOP=%USERPROFILE%\Desktop"
if not exist "%DESKTOP%" set "DESKTOP=%PUBLIC%\Desktop"
set "LOG=%DESKTOP%\Krexion-Install-Log.txt"

REM Make the BAT log everything by piping to tee-like behaviour later
title Krexion Installer
mode con: cols=100 lines=40
color 0B
cls

REM ───────────────────────────────────────────────────────────────────
REM  CHECK 1: Are we running from inside a ZIP / temp folder?
REM  Windows extracts ZIP contents to %TEMP%\Temp1_xxx when user
REM  double-clicks BAT *inside* the ZIP. That sandbox path makes the
REM  install fail mid-way because files vanish. Detect + tell customer.
REM ───────────────────────────────────────────────────────────────────
echo %~dp0| findstr /I /C:"\Temp1_" /C:"\Temp\Temp" /C:"\AppData\Local\Temp" >nul
if %errorlevel% equ 0 (
    cls
    color 0C
    echo.
    echo  ###################################################################
    echo  #                                                                 #
    echo  #              ZIP FILE EXTRACT NAHI KI!                         #
    echo  #                                                                 #
    echo  ###################################################################
    echo.
    echo   Aap ne ZIP file ke ANDAR se INSTALL.bat click kiya hai.
    echo   Yeh ZIP ke andar nahi chalta. Pehle PROPERLY extract karein:
    echo.
    echo     1. Krexion-User-Package.zip pe RIGHT-CLICK karein
    echo     2. "Extract All..." click karein
    echo     3. "Extract" button click karein
    echo     4. Naye folder ke ANDER jayein
    echo     5. PHIR INSTALL.bat double-click karein
    echo.
    echo  ===================================================
    echo   Yeh window khuli rahegi - jab samajh aa jaye
    echo   to koi bhi key dabayein band karne ke liye.
    echo  ===================================================
    echo.
    pause
    exit /b 1
)

REM ───────────────────────────────────────────────────────────────────
REM  CHECK 2: Admin rights via UAC.
REM  We use net session as it's the most reliable admin-detection
REM  primitive that works on every Windows 10/11 SKU.
REM ───────────────────────────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ===================================================
    echo   Administrator rights chahiye.
    echo   UAC popup pe "YES" / "Haan" click karein.
    echo  ===================================================
    echo.
    echo   Agar koi popup nahi aata, ya "No" press kiya gaya:
    echo     1. INSTALL.bat pe RIGHT-CLICK karein
    echo     2. "Run as administrator" select karein
    echo.
    echo  Window 8 second mein UAC trigger karegi...
    timeout /t 4 /nobreak >nul

    REM Self-elevate via PowerShell
    powershell -NoProfile -Command "try { Start-Process -FilePath '%~f0' -Verb RunAs -ErrorAction Stop } catch { exit 1 }"
    if !errorlevel! neq 0 (
        echo.
        color 0C
        echo  ===================================================
        echo   UAC popup cancel kiya gaya - install ruk gaya.
        echo  ===================================================
        echo.
        echo  Solution:
        echo    1. INSTALL.bat pe RIGHT-CLICK karein
        echo    2. "Run as administrator" select karein
        echo    3. UAC popup pe "YES" / "Haan" click karein
        echo.
        echo  Yeh window khuli rahegi. Koi bhi key dabayein band karne ke liye.
        echo.
        pause
    )
    exit /b 0
)

REM We are now elevated. Start logging from here onwards.
echo Krexion installer started: %DATE% %TIME% > "%LOG%" 2>nul
echo Folder: %~dp0 >> "%LOG%" 2>nul

cls
echo.
echo  ###################################################################
echo  #                                                                 #
echo  #              KREXION                                            #
echo  #              Aap Ka Installer                                   #
echo  #                                                                 #
echo  ###################################################################
echo.
echo   Sab kuch khud install ho jayega.
echo.
echo     [1] System engine setup
echo     [2] Krexion runtime install
echo     [3] Krexion application download + setup
echo     [4] Aap ke PC ke liye optimized configuration
echo     [5] Browser auto-open https://krexion.com/login
echo.
echo  ===================================================
echo   Total time: 20-30 minute
echo   Coffee/Chai piyen, sab automatic hai.
echo  ===================================================
echo.
echo   Detailed log:  %LOG%
echo.
timeout /t 5 /nobreak >nul

REM ───────────────────────────────────────────────────────────────────
REM  CHECK 3: Internet connectivity
REM ───────────────────────────────────────────────────────────────────
echo  [..] Internet check kar raha hun...
ping -n 1 github.com >nul 2>&1
set "INET=%errorlevel%"
echo Internet check exit code: %INET% >> "%LOG%"

if %INET% neq 0 (
    color 0C
    echo.
    echo  ===================================================
    echo   ERROR: Internet connection nahi hai!
    echo  ===================================================
    echo.
    echo  Solution:
    echo    1. WiFi check karein
    echo    2. Mobile hotspot try karein
    echo    3. Browser kholein, kuch bhi load karein
    echo    4. Phir dobara INSTALL.bat chalayein
    echo.
    echo  Yeh window khuli rahegi. Koi bhi key dabayein band karne ke liye.
    echo.
    pause
    exit /b 1
)
echo  [OK] Internet working
echo.

REM ───────────────────────────────────────────────────────────────────
REM  CHECK 4: install-master.ps1 file present
REM ───────────────────────────────────────────────────────────────────
set "PS_FILE=%~dp0install-master.ps1"

if not exist "%PS_FILE%" (
    color 0C
    echo.
    echo  ===================================================
    echo   ERROR: install-master.ps1 file missing!
    echo  ===================================================
    echo.
    echo  Aap ka folder: %~dp0
    echo.
    echo  Yeh file aap ke folder mein honi chahiye:
    echo    - INSTALL.bat
    echo    - install-master.ps1   ^<-- yeh missing hai
    echo.
    echo  Solution:
    echo    1. https://krexion.com/download se naya ZIP download karein
    echo    2. Right-click → "Extract All..." → Extract
    echo    3. Extract hue folder mein jaayein
    echo    4. INSTALL.bat double-click karein
    echo.
    echo  Yeh window khuli rahegi. Koi bhi key dabayein band karne ke liye.
    echo.
    pause
    exit /b 1
)
echo  [OK] Installer files found
echo.

REM ───────────────────────────────────────────────────────────────────
REM  CHECK 5 (REMOVED): PowerShell execution pre-check.
REM  The pre-check was blocking customers whose PowerShell actually
REM  works fine. If PowerShell is truly broken, install-master.ps1
REM  itself will fail and we capture its EXITCODE below — that gives
REM  the customer a real error from PowerShell instead of a false
REM  positive from the >nul redirection.
REM ───────────────────────────────────────────────────────────────────

echo  ===================================================
echo   Ab installer chal raha hai...
echo   Please wait 20-30 minutes
echo  ===================================================
echo.

REM ───────────────────────────────────────────────────────────────────
REM  Run install-master.ps1 in CUSTOMER MODE
REM  We log stderr+stdout to the desktop log file via PowerShell so
REM  customer never has to find a hidden TEMP file when troubleshooting.
REM ───────────────────────────────────────────────────────────────────
echo Calling install-master.ps1... >> "%LOG%"
echo PS_FILE=%PS_FILE% >> "%LOG%"

REM Try the standard PowerShell first; if it fails to even launch
REM (errorlevel 9009 = "not recognized as a command"), fall back to
REM pwsh.exe (PowerShell 7) which some users have installed.
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { try { & '%PS_FILE%' -CustomerMode *>&1 | Tee-Object -FilePath '%LOG%' -Append; exit $LASTEXITCODE } catch { Write-Host ('FATAL: ' + $_.Exception.Message); exit 99 } }"
set "EXITCODE=%errorlevel%"

if %EXITCODE% equ 9009 (
    echo PowerShell not found at default path, trying pwsh.exe... >> "%LOG%"
    pwsh -NoProfile -ExecutionPolicy Bypass -Command "& { try { & '%PS_FILE%' -CustomerMode *>&1 | Tee-Object -FilePath '%LOG%' -Append; exit $LASTEXITCODE } catch { Write-Host ('FATAL: ' + $_.Exception.Message); exit 99 } }"
    set "EXITCODE=!errorlevel!"
)

echo. >> "%LOG%"
echo Installer exited: code=%EXITCODE% at %DATE% %TIME% >> "%LOG%"

if %EXITCODE% neq 0 (
    color 0C
    echo.
    echo  ===================================================
    echo   Installation problem hui ^(error code: %EXITCODE%^)
    echo  ===================================================
    echo.
    echo   Detailed log Desktop pe save hua hai:
    echo     %LOG%
    echo.
    echo   Support contact:  https://krexion.com/support
    echo   Email karein:     support@krexion.com
    echo   Yeh "Krexion-Install-Log.txt" file Desktop se attach karein.
    echo.
    echo  Window khuli rahegi. Koi bhi key dabayein band karne ke liye.
    echo.
    pause
    exit /b %EXITCODE%
)

cls
color 0A
echo.
echo  ###################################################################
echo  #                                                                 #
echo  #              MUBARAK HO! KREXION READY HAI                     #
echo  #                                                                 #
echo  #   Browser khud khul gaya hai - https://krexion.com pe          #
echo  #                                                                 #
echo  #   1. Welcome email mein jo email + password mile,               #
echo  #      wahi krexion.com pe daal kar login karein.                 #
echo  #                                                                 #
echo  #   2. Sab kuch online manage hota hai - links 24/7 live.        #
echo  #                                                                 #
echo  #   3. Heavy features (Proxy/RUT/Form Filler) aap ke PC pe       #
echo  #      silently chalein gay - krexion.com se control hoga.       #
echo  #                                                                 #
echo  #   License nahi hai? Khareedein:                                 #
echo  #      https://krexion.com/pricing                                #
echo  #                                                                 #
echo  ###################################################################
echo.
echo  Detailed log Desktop pe save hua hai (delete kar sakte hain):
echo    %LOG%
echo.
echo  Yeh window 30 second mein khud band ho jaayegi.
timeout /t 30 /nobreak >nul
exit /b 0
