# ============================================================
# Krexion Doctor - Self-Healing Diagnostic + Auto-Fix Tool
# ============================================================
# Customer ke liye - agar install kahin stuck ya broken hai
# to yeh khud sab kuch diagnose aur fix karega
# ============================================================

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$INSTALL_DIR = "C:\krexion"
$LOG_FILE = "$env:TEMP\krexion-doctor.log"
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
Write-Host "  ||         KREXION DOCTOR                   ||" -ForegroundColor Yellow
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
# CHECK 4: Krexion Folder Exists - AUTO-RECOVER if missing
# ============================================================
DSection "CHECK 4/8: Krexion Folder"
if (Test-Path $INSTALL_DIR) {
    DOk "Krexion folder mojood hai"
} else {
    DErr "C:\krexion folder missing"
    DFix "Khud download karke recovery kar raha hun (5-10 min)..."
    $problemsFound++

    # ----- Download source ZIP from GitHub (handles 301 redirects) -----
    $zipPath = "$env:TEMP\krexion-recover.zip"
    $extPath = "$env:TEMP\krexion-recover-ext"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force -ErrorAction SilentlyContinue }
    if (Test-Path $extPath) { Remove-Item $extPath -Recurse -Force -ErrorAction SilentlyContinue }

    $dlOk = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        DInfo ("Download attempt " + $attempt + "/3 - 50MB lagta hai 1-2 min")
        try {
            Invoke-WebRequest -Uri $REPO_ZIP_URL -OutFile $zipPath -UseBasicParsing -TimeoutSec 600 -MaximumRedirection 5
            if ((Test-Path $zipPath) -and ((Get-Item $zipPath).Length -gt 1000000)) {
                $dlOk = $true
                break
            }
        } catch {
            DWarn ("Attempt " + $attempt + " failed: " + $_.Exception.Message)
            Start-Sleep -Seconds 5
        }
    }

    if (-not $dlOk) {
        DErr "Download fail ho raha hai - internet check karein"
        DFix "WiFi restart karein, mobile hotspot try karein, phir Doctor chalayein"
        Write-Host ""
        Read-Host "Press Enter to close"
        exit 1
    }
    DOk "Download complete"

    # ----- Extract ZIP -----
    DInfo "Extract kar raha hun..."
    try {
        Expand-Archive -Path $zipPath -DestinationPath $extPath -Force -ErrorAction Stop
    } catch {
        DErr ("Extract failed: " + $_.Exception.Message)
        Read-Host "Press Enter to close"
        exit 1
    }

    $inner = Get-ChildItem $extPath -Directory | Select-Object -First 1
    if (-not $inner) {
        DErr "ZIP empty hai - corrupt download"
        Read-Host "Press Enter to close"
        exit 1
    }

    # ----- Move to C:\krexion -----
    try {
        Move-Item -Path $inner.FullName -Destination $INSTALL_DIR -Force -ErrorAction Stop
        DOk ("Folder created: " + $INSTALL_DIR)
    } catch {
        DErr ("Move failed: " + $_.Exception.Message)
        Read-Host "Press Enter to close"
        exit 1
    }
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    Remove-Item $extPath -Recurse -Force -ErrorAction SilentlyContinue

    # ----- Generate .env with random secrets -----
    DInfo "Configuration .env file bana raha hun..."
    function New-RandStr { param([int]$L=24)
        $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        -join (1..$L | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    }
    $envContent = @(
        "MONGO_URL=mongodb://mongo:27017",
        "DB_NAME=krexion",
        ("JWT_SECRET_KEY=" + (New-RandStr 32)),
        "ADMIN_EMAIL=admin@krexion.local",
        ("ADMIN_PASSWORD=" + (New-RandStr 16)),
        ("POSTBACK_TOKEN=" + (New-RandStr 24)),
        "CORS_ORIGINS=*",
        "RUT_MEM_LIMIT_MB=4096",
        "RUT_MAX_CONCURRENCY=4",
        "RESEND_API_KEY=",
        "SMTP_USER=",
        "SMTP_PASSWORD=",
        "GOOGLE_SHEETS_SA_PATH=",
        "LICENSE_SERVER_URL=https://krexion.com",
        "LICENSE_KEY=",
        "KREXION_MODE=local",
        "KREXION_CLOUD_URL=https://krexion.com",
        "IS_CUSTOMER_INSTALL=true"
    )
    $envContent | Set-Content -Path "$INSTALL_DIR\.env" -Encoding ASCII -Force
    DOk ".env file created"
    $fixesApplied++

    DInfo "Recovery complete - aage ke checks chalayein ge"
}

# ============================================================
# CHECK 5: .env File - auto-create if missing
# ============================================================
DSection "CHECK 5/8: Configuration File"
$envPath = "$INSTALL_DIR\.env"
if (Test-Path $envPath) {
    DOk ".env file mojood hai"
} else {
    DErr ".env file missing"
    DFix "Auto-generating .env with secure random secrets..."
    function New-RandStr2 { param([int]$L=24)
        $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        -join (1..$L | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    }
    @(
        "MONGO_URL=mongodb://mongo:27017",
        "DB_NAME=krexion",
        ("JWT_SECRET_KEY=" + (New-RandStr2 32)),
        "ADMIN_EMAIL=admin@krexion.local",
        ("ADMIN_PASSWORD=" + (New-RandStr2 16)),
        ("POSTBACK_TOKEN=" + (New-RandStr2 24)),
        "CORS_ORIGINS=*",
        "RUT_MEM_LIMIT_MB=4096",
        "RUT_MAX_CONCURRENCY=4",
        "LICENSE_SERVER_URL=https://krexion.com",
        "KREXION_MODE=local",
        "KREXION_CLOUD_URL=https://krexion.com",
        "IS_CUSTOMER_INSTALL=true"
    ) | Set-Content -Path $envPath -Encoding ASCII -Force
    DOk ".env file created"
    $fixesApplied++
}

# ============================================================
# CHECK 6: Containers Running - auto build + start with legacy cleanup
# ============================================================
DSection "CHECK 6/8: Krexion Containers"
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

        # ----- Legacy container cleanup (avoid name conflicts from old installs) -----
        DFix "Pehle purane legacy containers clean kar raha hun..."
        foreach ($proj in @("realflow", "krexion", "krexion-user-package")) {
            & docker compose -p $proj down --remove-orphans --volumes 2>&1 | Out-Null
        }
        $legacyContainers = @(
            "realflow-mongo","realflow-backend","realflow-frontend","realflow-caddy","realflow-redis","realflow-worker",
            "krexion-mongo","krexion-backend","krexion-frontend","krexion-caddy","krexion-redis","krexion-worker"
        )
        foreach ($n in $legacyContainers) { & docker rm -f $n 2>&1 | Out-Null }
        foreach ($net in @("realflow-net","krexion-net","realflow_realflow-net","krexion_krexion-net")) {
            & docker network rm $net 2>&1 | Out-Null
        }
        DOk "Legacy cleanup done"

        # ----- Detect RAM tier compose file -----
        $composeArgs = @("-f", "docker-compose.yml")
        $os = Get-CimInstance Win32_OperatingSystem
        $ram = [math]::Round(($os.TotalVisibleMemorySize / 1MB), 1)
        if (($ram -le 10) -and (Test-Path "docker-compose.lowram.yml")) {
            $composeArgs += @("-f", "docker-compose.lowram.yml")
            DInfo "Low-RAM profile use kar raha hun"
        } elseif (($ram -le 16) -and (Test-Path "docker-compose.mid.yml")) {
            $composeArgs += @("-f", "docker-compose.mid.yml")
            DInfo "Mid-tier profile use kar raha hun"
        } elseif (($ram -gt 32) -and (Test-Path "docker-compose.beast.yml")) {
            $composeArgs += @("-f", "docker-compose.beast.yml")
            DInfo "Beast profile use kar raha hun"
        } elseif (($ram -gt 16) -and (Test-Path "docker-compose.high.yml")) {
            $composeArgs += @("-f", "docker-compose.high.yml")
            DInfo "High-tier profile use kar raha hun"
        }

        # ----- Build (this is the long step: 5-15 min) -----
        DFix "Containers build kar raha hun - YEH 5-15 MIN LE SAKTA HAI..."
        & docker compose @composeArgs build 2>&1 | Out-String | Out-Null
        $buildExit = $LASTEXITCODE

        if ($buildExit -ne 0) {
            DErr "Build fail hua - PC restart karein phir doctor dobara"
            Pop-Location
            Read-Host "Press Enter to close"
            exit 1
        }
        DOk "Build complete"

        # ----- Start (with conflict-cleanup retry) -----
        DFix "Containers start kar raha hun..."
        & docker compose @composeArgs up -d 2>&1 | Out-String | Out-Null
        $upExit = $LASTEXITCODE
        if ($upExit -ne 0) {
            DWarn "First start fail - conflicting containers clean karke retry"
            foreach ($n in $legacyContainers) { & docker rm -f $n 2>&1 | Out-Null }
            Start-Sleep -Seconds 3
            & docker compose @composeArgs up -d 2>&1 | Out-String | Out-Null
        }

        Start-Sleep -Seconds 15
        $containers2 = & docker compose ps --format json 2>&1 | Out-String
        if ($containers2 -match '"State":"running"') {
            DOk "Containers started!"
            $fixesApplied++
        } else {
            DErr "Containers start nahi hue - PC restart karein phir doctor"
        }
    }
    Pop-Location
}

# ============================================================
# CHECK 7: Web Server Responding
# ============================================================
DSection "CHECK 7/8: Krexion Web Server"
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
    DOk "Krexion background service chal raha hai (ready for krexion.com)"
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
    Write-Host "  Krexion background service chal raha hai." -ForegroundColor White
    Write-Host "  Heavy features (Proxy / RUT / Form Filler) ready hain." -ForegroundColor White
    Write-Host ""
    Write-Host "  Apna dashboard kholein:" -ForegroundColor Cyan
    Write-Host "    https://krexion.com/login" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Browser khud khol raha hun krexion.com pe..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    Start-Process "https://krexion.com/login"
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
