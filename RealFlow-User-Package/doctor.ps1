# ============================================================
# RealFlow Doctor - Self-Healing Diagnostic + Auto-Fix Tool
# ============================================================
# Customer ke liye - agar install kahin stuck ya broken hai
# to yeh khud sab kuch diagnose aur fix karega
# ============================================================

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$INSTALL_DIR = "C:\realflow"
$LOG_FILE = "$env:TEMP\realflow-doctor.log"
$REPO_ZIP_URL = "https://github.com/ronaldsexedwards40-glitch/dynabook/archive/refs/heads/main.zip"

function Log-It {
    param([string]$M, [string]$C = "White")
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host ("[" + $ts + "] " + $M) -ForegroundColor $C
    Add-Content -Path $LOG_FILE -Value ("[" + $ts + "] " + $M) -ErrorAction SilentlyContinue
}
function DOk { param($m) Log-It ("  [OK]    " + $m) "Green" }
function DWarn { param($m) Log-It ("  [WARN]  " + $m) "Yellow" }
function DErr { param($m) Log-It ("  [ERR]   " + $m) "Red" }
function DInfo { param($m) Log-It ("  [..]    " + $m) "Cyan" }
function DFix { param($m) Log-It ("  [FIX]   " + $m) "Magenta" }
function DSection {
    param($t)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Yellow
    Write-Host ("  " + $t) -ForegroundColor Yellow
    Write-Host ("=" * 70) -ForegroundColor Yellow
}

"=== Doctor started " + (Get-Date) + " ===" | Out-File -FilePath $LOG_FILE -Force

Clear-Host
Write-Host ""
Write-Host "  ===============================================" -ForegroundColor Yellow
Write-Host "  ||                                           ||" -ForegroundColor Yellow
Write-Host "  ||         REALFLOW DOCTOR                   ||" -ForegroundColor Yellow
Write-Host "  ||         Auto-Diagnose + Auto-Fix          ||" -ForegroundColor Yellow
Write-Host "  ||                                           ||" -ForegroundColor Yellow
Write-Host "  ===============================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Sab kuch khud check karta hun aur fix kar deta hun." -ForegroundColor White
Write-Host ""
Start-Sleep -Seconds 2

$problemsFound = 0
$fixesApplied = 0

# ============================================================
# CHECK 1: Internet
# ============================================================
DSection "CHECK 1/8: Internet Connection"
$internet = $false
try {
    $r = Invoke-WebRequest "https://github.com" -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -eq 200) { $internet = $true }
} catch { }

if ($internet) {
    DOk "Internet working"
} else {
    DErr "Internet nahi hai"
    DFix "WiFi check karein ya mobile hotspot try karein"
    $problemsFound++
}

# ============================================================
# CHECK 2: Docker Desktop Installed
# ============================================================
DSection "CHECK 2/8: Docker Desktop"
$dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $dockerExe) {
    DOk "Docker Desktop installed"
} else {
    DErr "Docker Desktop missing"
    DFix "INSTALL.bat dobara chalayein"
    $problemsFound++
}

# ============================================================
# CHECK 3: Docker Service Running
# ============================================================
DSection "CHECK 3/8: Docker Service"
$dockerWorking = $false
try {
    $null = & docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerWorking = $true }
} catch { }

if ($dockerWorking) {
    DOk "Docker engine running"
} else {
    DWarn "Docker not responding - trying to fix..."
    $problemsFound++

    # Auto-fix: Stop everything, restart
    DFix "Stopping Docker processes..."
    Get-Process "Docker Desktop","com.docker.backend","com.docker.proxy" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Stop-Service "com.docker.service" -Force -ErrorAction SilentlyContinue
    & wsl --shutdown 2>&1 | Out-Null
    Start-Sleep -Seconds 5

    DFix "Starting Docker Desktop..."
    Start-Service "com.docker.service" -ErrorAction SilentlyContinue
    if (Test-Path $dockerExe) {
        Start-Process -FilePath $dockerExe -WindowStyle Minimized -ArgumentList "-Autostart"
    }

    DInfo "Docker ready hone ka wait (max 3 min)..."
    $waited = 0
    while ($waited -lt 180) {
        Start-Sleep -Seconds 5
        $waited += 5
        try {
            $null = & docker info 2>&1
            if ($LASTEXITCODE -eq 0) { $dockerWorking = $true; break }
        } catch { }
        if (($waited % 30) -eq 0) {
            Write-Host ("      Wait... " + $waited + "s") -ForegroundColor DarkGray
        }
    }

    if ($dockerWorking) {
        DOk "Docker fixed and running!"
        $fixesApplied++
    } else {
        DErr "Docker fix nahi hua"
        DFix "Try karein: PC restart karein, phir is doctor ko dobara chalayein"

        # Try WSL kernel update
        DFix "WSL kernel update try kar raha hun..."
        & wsl --update 2>&1 | Out-Null
        & wsl --shutdown 2>&1 | Out-Null
        Start-Sleep -Seconds 3
        Start-Process -FilePath $dockerExe -WindowStyle Minimized -ArgumentList "-Autostart"
        Start-Sleep -Seconds 60
        try {
            $null = & docker info 2>&1
            if ($LASTEXITCODE -eq 0) {
                DOk "Docker fixed after WSL update!"
                $dockerWorking = $true
                $fixesApplied++
            }
        } catch { }
    }
}

# ============================================================
# CHECK 4: RealFlow Folder Exists
# ============================================================
DSection "CHECK 4/8: RealFlow Folder"
if (Test-Path $INSTALL_DIR) {
    DOk "RealFlow folder mojood hai"
} else {
    DErr "C:\realflow folder missing"
    DFix "INSTALL.bat dobara chalayein"
    $problemsFound++
    Write-Host ""
    Write-Host "  Doctor stop. INSTALL.bat dobara chalayein pehle." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# ============================================================
# CHECK 5: .env File
# ============================================================
DSection "CHECK 5/8: Configuration File"
$envPath = "$INSTALL_DIR\.env"
if (Test-Path $envPath) {
    DOk ".env file mojood hai"
} else {
    DErr ".env file missing"
    DFix "INSTALL.bat dobara chalayein"
    $problemsFound++
}

# ============================================================
# CHECK 6: Containers Running
# ============================================================
DSection "CHECK 6/8: RealFlow Containers"
if (-not $dockerWorking) {
    DWarn "Docker abhi running nahi - container check skip"
} else {
    Push-Location $INSTALL_DIR
    $containers = & docker compose ps --format json 2>&1 | Out-String

    $running = ($containers -match '"State":"running"')
    if ($running) {
        DOk "Containers chal rahe hain"
    } else {
        DWarn "Containers band hain - start kar raha hun..."
        $problemsFound++

        DFix "Containers up kar raha hun..."

        $composeArgs = @("-f", "docker-compose.yml")
        $os = Get-CimInstance Win32_OperatingSystem
        $ram = [math]::Round(($os.TotalVisibleMemorySize / 1MB), 1)
        if (($ram -le 10) -and (Test-Path "docker-compose.lowram.yml")) {
            $composeArgs += @("-f", "docker-compose.lowram.yml")
        } elseif (($ram -le 16) -and (Test-Path "docker-compose.mid.yml")) {
            $composeArgs += @("-f", "docker-compose.mid.yml")
        }

        & docker compose @composeArgs up -d 2>&1 | Out-String | Out-Null

        Start-Sleep -Seconds 10
        $containers2 = & docker compose ps --format json 2>&1 | Out-String
        if ($containers2 -match '"State":"running"') {
            DOk "Containers started!"
            $fixesApplied++
        } else {
            DWarn "Containers start mein issue - rebuild try kar raha hun..."
            DFix "Building containers fresh..."
            & docker compose @composeArgs build 2>&1 | Out-String | Out-Null
            & docker compose @composeArgs up -d 2>&1 | Out-String | Out-Null
            Start-Sleep -Seconds 30
            $containers3 = & docker compose ps --format json 2>&1 | Out-String
            if ($containers3 -match '"State":"running"') {
                DOk "Rebuild successful!"
                $fixesApplied++
            } else {
                DErr "Containers fix nahi hue"
                DFix "Try: 1) PC restart karein 2) INSTALL.bat dobara"
            }
        }
    }
    Pop-Location
}

# ============================================================
# CHECK 7: Web Server Responding
# ============================================================
DSection "CHECK 7/8: RealFlow Web Server"
$webOk = $false
for ($i = 0; $i -lt 12; $i++) {
    try {
        $r = Invoke-WebRequest "http://localhost:3000" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $webOk = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
    if (($i % 3) -eq 2) {
        Write-Host "      Wait kar raha hun..." -ForegroundColor DarkGray
    }
}

if ($webOk) {
    DOk "Web server chal raha hai - http://localhost:3000"
} else {
    DErr "Web server response nahi de raha"
    DFix "Containers restart kar raha hun..."
    $problemsFound++

    if ($dockerWorking) {
        Push-Location $INSTALL_DIR
        & docker compose restart 2>&1 | Out-String | Out-Null
        Pop-Location
        Start-Sleep -Seconds 30

        try {
            $r = Invoke-WebRequest "http://localhost:3000" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
            if ($r.StatusCode -eq 200) {
                DOk "Restart se fix ho gaya!"
                $webOk = $true
                $fixesApplied++
            }
        } catch { }
    }

    if (-not $webOk) {
        DErr "Web server fix nahi hua"
        DFix "Try: 1) PC restart 2) INSTALL.bat dobara"
    }
}

# ============================================================
# CHECK 8: Disk Space
# ============================================================
DSection "CHECK 8/8: Disk Space"
$drive = Get-PSDrive C
$freeGB = [math]::Round(($drive.Free / 1GB), 1)
if ($freeGB -lt 5) {
    DErr ("Disk space bohot kam - " + $freeGB + " GB free")
    DFix "Recycle bin empty karein + temp files delete karein"
    $problemsFound++
} elseif ($freeGB -lt 10) {
    DWarn ("Disk space kam - " + $freeGB + " GB free")
    DFix "20 GB free recommended hai"
} else {
    DOk ("Disk space OK - " + $freeGB + " GB free")
}

# ============================================================
# FINAL REPORT
# ============================================================
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Magenta
Write-Host "  DIAGNOSIS REPORT" -ForegroundColor Magenta
Write-Host ("=" * 70) -ForegroundColor Magenta
Write-Host ""

Write-Host ("  Problems detected: " + $problemsFound) -ForegroundColor White
Write-Host ("  Auto-fixes applied: " + $fixesApplied) -ForegroundColor Green
Write-Host ""

if ($webOk) {
    Write-Host "  ===============================================" -ForegroundColor Green
    Write-Host "    SUCCESS! Sab kuch theek hai." -ForegroundColor Green
    Write-Host "  ===============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  RealFlow chal raha hai:" -ForegroundColor White
    Write-Host "    http://localhost:3000" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Browser khud khol raha hun..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:3000"
} else {
    Write-Host "  ===============================================" -ForegroundColor Red
    Write-Host "    Kuch issues fix nahi ho sake" -ForegroundColor Red
    Write-Host "  ===============================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "  ANTIM SOLUTION (sirf agar yahan tak aaye):" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    1. PC restart karein (poori shutdown + start)" -ForegroundColor White
    Write-Host "    2. Login ke baad Docker Desktop kholein" -ForegroundColor White
    Write-Host "    3. Whale icon GREEN hone ka wait karein (3-5 min)" -ForegroundColor White
    Write-Host "    4. Yeh doctor dobara chalayein" -ForegroundColor White
    Write-Host ""
    Write-Host "  Agar phir bhi fail to admin ko yeh log file bhejen:" -ForegroundColor Yellow
    Write-Host ("    " + $LOG_FILE) -ForegroundColor White
    Write-Host ""
}

Write-Host ""
Write-Host "  Doctor log saved: $LOG_FILE" -ForegroundColor Gray
Write-Host ""
exit 0
