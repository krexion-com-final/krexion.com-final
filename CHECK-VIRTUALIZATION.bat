@echo off
REM ============================================================
REM  Krexion VIRTUALIZATION DIAGNOSTIC - Quick Check
REM ============================================================
REM  Yeh tool 4 alag methods se check karta hai ki aap ke
REM  PC pe virtualization ENABLED hai ya DISABLED.
REM ============================================================

title Krexion Virtualization Check
color 0B

echo.
echo  ============================================================
echo   Krexion Virtualization Status Check
echo  ============================================================
echo.
echo   4 alag methods se test kar raha hai...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -Command ^
    "Write-Host '------------------------------------------------------------' -ForegroundColor Cyan;" ^
    "Write-Host '  METHOD 1: HyperVisor Present Check' -ForegroundColor Yellow;" ^
    "$ci = Get-ComputerInfo -Property HyperVisorPresent;" ^
    "if ($ci.HyperVisorPresent) { Write-Host '    [OK] Hypervisor active - Virtualization IS ENABLED' -ForegroundColor Green }" ^
    "else { Write-Host '    [--] No hypervisor detected (not conclusive)' -ForegroundColor Gray };" ^
    "Write-Host '';" ^
    "Write-Host '------------------------------------------------------------' -ForegroundColor Cyan;" ^
    "Write-Host '  METHOD 2: WSL Status Check' -ForegroundColor Yellow;" ^
    "$wsl = & wsl --status 2>&1 | Out-String;" ^
    "if ($LASTEXITCODE -eq 0) { Write-Host '    [OK] WSL is functional - Virtualization IS ENABLED' -ForegroundColor Green; Write-Host $wsl -ForegroundColor DarkGray }" ^
    "else { Write-Host '    [--] WSL not functional yet (not conclusive)' -ForegroundColor Gray };" ^
    "Write-Host '';" ^
    "Write-Host '------------------------------------------------------------' -ForegroundColor Cyan;" ^
    "Write-Host '  METHOD 3: systeminfo Detection' -ForegroundColor Yellow;" ^
    "$si = systeminfo 2>&1 | Out-String;" ^
    "$found = $false;" ^
    "if ($si -match 'A hypervisor has been detected') { Write-Host '    [OK] Hypervisor detected by systeminfo' -ForegroundColor Green; $found = $true };" ^
    "if ($si -match 'VM Monitor Mode Extensions:\s+Yes') { Write-Host '    [OK] VM Monitor Mode: Yes' -ForegroundColor Green; $found = $true };" ^
    "if ($si -match 'Virtualization Enabled In Firmware:\s+Yes') { Write-Host '    [OK] Firmware Virtualization: Yes' -ForegroundColor Green; $found = $true };" ^
    "if ($si -match 'Second Level Address Translation:\s+Yes') { Write-Host '    [OK] SLAT: Yes' -ForegroundColor Green; $found = $true };" ^
    "if (-not $found) { Write-Host '    [--] systeminfo shows no virt indicators' -ForegroundColor Gray };" ^
    "Write-Host '';" ^
    "Write-Host '------------------------------------------------------------' -ForegroundColor Cyan;" ^
    "Write-Host '  METHOD 4: CPU WMI Properties (least reliable on Win11 24H2)' -ForegroundColor Yellow;" ^
    "$cpu = Get-CimInstance Win32_Processor;" ^
    "Write-Host \"    VirtualizationFirmwareEnabled: $($cpu.VirtualizationFirmwareEnabled)\" -ForegroundColor White;" ^
    "Write-Host \"    VMMonitorModeExtensions: $($cpu.VMMonitorModeExtensions)\" -ForegroundColor White;" ^
    "Write-Host \"    SecondLevelAddressTranslationExtensions: $($cpu.SecondLevelAddressTranslationExtensions)\" -ForegroundColor White;" ^
    "Write-Host '';" ^
    "Write-Host '------------------------------------------------------------' -ForegroundColor Cyan;" ^
    "Write-Host '  METHOD 5: Windows Features State' -ForegroundColor Yellow;" ^
    "$wsl_feature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux;" ^
    "$vmp = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform;" ^
    "$hv = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -ErrorAction SilentlyContinue;" ^
    "Write-Host \"    WSL feature: $($wsl_feature.State)\" -ForegroundColor White;" ^
    "Write-Host \"    Virtual Machine Platform: $($vmp.State)\" -ForegroundColor White;" ^
    "if ($hv) { Write-Host \"    Hyper-V: $($hv.State)\" -ForegroundColor White };" ^
    "Write-Host '';" ^
    "Write-Host '============================================================' -ForegroundColor Cyan;" ^
    "Write-Host '  FINAL VERDICT' -ForegroundColor Cyan;" ^
    "Write-Host '============================================================' -ForegroundColor Cyan;" ^
    "Write-Host '';" ^
    "if ($ci.HyperVisorPresent -or ($LASTEXITCODE -eq 0) -or $found) {" ^
    "    Write-Host '    Virtualization is ENABLED' -ForegroundColor Green;" ^
    "    Write-Host '    Aap Krexion-ULTIMATE-INSTALL.bat normally chala sakte hain' -ForegroundColor Green" ^
    "} else {" ^
    "    Write-Host '    Status: UNCERTAIN (Win11 24H2 false-negative bug possible)' -ForegroundColor Yellow;" ^
    "    Write-Host '';" ^
    "    Write-Host '    Try karein:' -ForegroundColor Yellow;" ^
    "    Write-Host '    1. Krexion-FORCE-INSTALL.bat chalayein (virt check skip karta hai)' -ForegroundColor White;" ^
    "    Write-Host '    2. Agar Docker start nahi hota to BIOS mein virt enable karein' -ForegroundColor White" ^
    "}"

echo.
echo.
pause
exit /b 0
