# REDIRECT: This script has been deprecated.
# Use CPI-ONE-CLICK.bat from the project root instead.

Write-Host ""
Write-Host "================================================================" -ForegroundColor Yellow
Write-Host "  Ye file ab use nahi hoti. Naya setup file use karein:" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Project ROOT folder mein jao:" -ForegroundColor Cyan
Write-Host "  F:\online\real flow\lenovo real flow\lenovo-krexion-main\lenovo-krexion-main\" -ForegroundColor White
Write-Host ""
Write-Host "  Wahan ye file dhundo:" -ForegroundColor Cyan
Write-Host "  CPI-ONE-CLICK.bat" -ForegroundColor Green
Write-Host ""
Write-Host "  Right-click -> Run as Administrator" -ForegroundColor Cyan
Write-Host ""
Write-Host "================================================================" -ForegroundColor Yellow
Write-Host ""

# Auto-launch the correct file if found
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$batFile = Join-Path $root "CPI-ONE-CLICK.bat"
if (Test-Path $batFile) {
    Write-Host "  Auto-launching: $batFile" -ForegroundColor Green
    Start-Process -FilePath $batFile -Verb RunAs
} else {
    Write-Host "  [WARN] CPI-ONE-CLICK.bat nahi mila. Manually root folder mein jao." -ForegroundColor Red
}

Write-Host ""
Read-Host "Press Enter to close"
