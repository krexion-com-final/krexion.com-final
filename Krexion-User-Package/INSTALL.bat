@echo off
REM ###################################################################
REM #                                                                 #
REM #          KREXION - INSTALL KAREIN                              #
REM #                                                                 #
REM #  Bas yeh file double-click karein. Aur kuch nahi.               #
REM #                                                                 #
REM #  - UAC popup aaye to "YES" click karein                         #
REM #  - 20-30 minute wait karein                                     #
REM #  - Browser khud khulega                                         #
REM #  - Register page pe naya account banayein                       #
REM #                                                                 #
REM ###################################################################

REM Self-elevate to Admin
fltmc >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  ===================================================
    echo   Administrator rights chahiye.
    echo   UAC popup pe "YES" dabayein.
    echo  ===================================================
    echo.
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>&1
    if %errorLevel% neq 0 (
        echo.
        echo  UAC popup fail hua.
        echo  Solution: Right-click karein "Run as administrator"
        echo.
        pause
    )
    exit /b 0
)

title Krexion Installer - Wait Karein
mode con: cols=100 lines=40
color 0B
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
echo     [1] Windows Subsystem for Linux setup
echo     [2] Docker Desktop install
echo     [3] Krexion application download + setup
echo     [4] Aap ke PC ke liye optimized configuration
echo     [5] Browser auto-open Register page pe
echo.
echo  ===================================================
echo   Total time: 20-30 minute
echo   Coffee/Chai piyen, sab automatic hai
echo  ===================================================
echo.
timeout /t 5 /nobreak >nul

REM Check internet
echo  [..] Internet check kar raha hun...
ping -n 1 github.com >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  ===================================================
    echo   ERROR: Internet connection nahi hai!
    echo  ===================================================
    echo.
    echo  Solution:
    echo    1. WiFi check karein
    echo    2. Mobile hotspot try karein
    echo    3. Phir dobara INSTALL.bat chalayein
    echo.
    pause
    exit /b 1
)
echo  [OK] Internet working
echo.

REM Use bundled install-master.ps1 (in same folder)
set "PS_FILE=%~dp0install-master.ps1"

if not exist "%PS_FILE%" (
    echo.
    echo  ===================================================
    echo   ERROR: install-master.ps1 file missing!
    echo  ===================================================
    echo.
    echo  Yeh file aap ke folder mein honi chahiye.
    echo.
    echo  Solution:
    echo    1. ZIP file ko PROPERLY extract karein
    echo    2. Folder mein dono files honi chahiye:
    echo       - INSTALL.bat
    echo       - install-master.ps1
    echo    3. INSTALL.bat dobara chalayein
    echo.
    echo  Agar ZIP file kharab hai, admin se naya ZIP maangein.
    echo.
    pause
    exit /b 1
)

echo  [OK] Installer files found
echo.
echo  ===================================================
echo   Ab installer chal raha hai...
echo   Please wait 20-30 minutes
echo  ===================================================
echo.

REM Run the installer in CUSTOMER MODE
powershell -ExecutionPolicy Bypass -NoProfile -File "%PS_FILE%" -CustomerMode

set "EXITCODE=%errorlevel%"

if %EXITCODE% neq 0 (
    echo.
    echo  ===================================================
    echo   Installation problem hui ^(error code: %EXITCODE%^)
    echo  ===================================================
    echo.
    echo   Log files yahan hain:
    echo     %TEMP%\krexion-install.log
    echo     %TEMP%\krexion-transcript.log
    echo.
    echo   Yeh dono files admin ko WhatsApp pe bhejen
    echo   (jin se aap ne yeh package liya hai).
    echo.
    pause
    exit /b %EXITCODE%
)

echo.
echo  ###################################################################
echo  #                                                                 #
echo  #              SUCCESS! KREXION READY HAI                        #
echo  #                                                                 #
echo  #   Browser khud khul gayi hai - Register page pe                 #
echo  #                                                                 #
echo  #   1. Naya account banayein                                      #
echo  #   2. License key https://krexion.com/pricing se khareedein      #
echo  #      (USDT-TRC20 — 30 min mein email pe milegi)                 #
echo  #   3. License key Krexion mein daalein, ready!                   #
echo  #                                                                 #
echo  ###################################################################
echo.
pause
exit /b 0
