# ════════════════════════════════════════════════════════════════════
#   Krexion v1.0.8 → v1.0.8+ Fix-It Tool
# ════════════════════════════════════════════════════════════════════
# Fixes the "KrexionDatabase Paused" issue in-place WITHOUT requiring
# a full reinstall. Root cause:
#
#   The v1.0.8 installer registered MongoDB's data path as
#   `C:\Program Files\Krexion\data\db`. NSSM (the service wrapper)
#   stores AppParameters verbatim — but when Windows re-parses argv
#   at service-start time, the *unquoted* whitespace in
#   "Program Files" splits the path into two tokens. mongod.exe sees
#   `--dbpath C:\Program` followed by `Files\Krexion\data\db` as a
#   stray positional arg, prints help, and exits within 4 seconds.
#   NSSM's AppExit=Restart restarts it every 5 sec → permanent loop.
#
# This script:
#   1. Stops both Krexion services
#   2. Creates the new (whitespace-free) data dir at
#      %PROGRAMDATA%\Krexion\data\db
#   3. Migrates any existing data from the old path
#   4. Removes the old KrexionDatabase service registration
#   5. Re-registers KrexionDatabase pointing at the new path
#   6. Starts both services
#   7. Verifies backend health
#
# Usage (PowerShell — MUST be Administrator):
#   irm https://raw.githubusercontent.com/dennisedmaartins9-sudo/krexion.com/main/installer/Krexion-Fix-v108.ps1 | iex
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = 'Continue'

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      Krexion v1.0.8 — Database Path Fix-It Tool            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Admin check ─────────────────────────────────────────────────
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script must be run as Administrator." -ForegroundColor Red
    Write-Host ""
    Write-Host "Please:" -ForegroundColor Yellow
    Write-Host "  1. Close this PowerShell window"
    Write-Host "  2. Open Start menu, search 'PowerShell'"
    Write-Host "  3. Right-click 'Windows PowerShell' -> 'Run as administrator'"
    Write-Host "  4. Click 'Yes' on the UAC prompt"
    Write-Host "  5. Paste the same one-liner command again"
    Write-Host ""
    pause
    return
}

$Krexion = 'C:\Program Files\Krexion'
$NSSM = Join-Path $Krexion 'bin\krexion-service.exe'
$Mongod = Join-Path $Krexion 'database\bin\mongod.exe'
$OldDataDir = Join-Path $Krexion 'data\db'
$NewDataDir = 'C:\ProgramData\Krexion\data\db'

# Sanity checks
if (-not (Test-Path $NSSM))    { Write-Host "ERROR: $NSSM not found." -ForegroundColor Red; pause; return }
if (-not (Test-Path $Mongod))  { Write-Host "ERROR: $Mongod not found." -ForegroundColor Red; pause; return }

# ── Step 1: Stop services + kill zombies ─────────────────────
Write-Host "[1/8] Stopping Krexion services + killing any zombies..." -ForegroundColor Yellow
foreach ($svc in @('KrexionBackend','KrexionDatabase')) {
    try {
        $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
        if ($s -and $s.Status -ne 'Stopped') {
            Stop-Service -Name $svc -Force -ErrorAction SilentlyContinue
            Write-Host "   stopped: $svc" -ForegroundColor Gray
        } else {
            Write-Host "   already stopped: $svc" -ForegroundColor Gray
        }
    } catch {}
}
Start-Sleep -Seconds 2

# Zombie cleanup — when the v1.0.8 backend crash-looped, every uvicorn
# exit left a krexion-core.exe holding port 8001 in TIME_WAIT. Killing
# the parent NSSM service does NOT always cascade to its python child.
# If we don't sweep them now, the freshly-started backend hits
# 'Errno 10048 only one usage of each socket address is permitted'.
$zombiesKilled = 0
Get-Process | Where-Object { $_.Path -and $_.Path -like '*Krexion*' } | ForEach-Object {
    try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue; $zombiesKilled++ } catch {}
}
if ($zombiesKilled -gt 0) {
    Write-Host "   killed $zombiesKilled lingering Krexion process(es)" -ForegroundColor Gray
}
try {
    Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "   freed port 8001 from PID $($_.OwningProcess)" -ForegroundColor Gray
        } catch {}
    }
} catch {}
Start-Sleep -Seconds 3

# ── Step 2: Create new data dir ───────────────────────────────
Write-Host "[2/8] Creating new data directory at $NewDataDir ..." -ForegroundColor Yellow
if (-not (Test-Path $NewDataDir)) {
    New-Item -ItemType Directory -Force -Path $NewDataDir | Out-Null
    Write-Host "   created" -ForegroundColor Gray
} else {
    Write-Host "   already exists" -ForegroundColor Gray
}

# ── Step 3: Migrate any existing data ─────────────────────────
Write-Host "[3/8] Checking for data to migrate..." -ForegroundColor Yellow
if (Test-Path $OldDataDir) {
    $existing = Get-ChildItem $OldDataDir -ErrorAction SilentlyContinue
    if ($existing.Count -gt 0) {
        Write-Host "   migrating $($existing.Count) items from $OldDataDir" -ForegroundColor Gray
        Copy-Item -Path "$OldDataDir\*" -Destination $NewDataDir -Recurse -Force
    } else {
        Write-Host "   old data dir empty (expected — DB never started)" -ForegroundColor Gray
    }
} else {
    Write-Host "   old data dir does not exist (good)" -ForegroundColor Gray
}

# ── Step 4: Remove old KrexionDatabase service ────────────────
Write-Host "[4/8] Removing old KrexionDatabase service registration..." -ForegroundColor Yellow
& $NSSM remove KrexionDatabase confirm 2>&1 | Out-Null
Start-Sleep -Seconds 2
Write-Host "   removed" -ForegroundColor Gray

# ── Step 5: Re-register KrexionDatabase with new path ─────────
Write-Host "[5/8] Re-registering KrexionDatabase with fixed dbpath..." -ForegroundColor Yellow
& $NSSM install KrexionDatabase $Mongod 2>&1 | Out-Null
& $NSSM set KrexionDatabase AppParameters "--dbpath $NewDataDir --port 27017 --bind_ip 127.0.0.1 --quiet" 2>&1 | Out-Null
& $NSSM set KrexionDatabase DisplayName 'Krexion Database' 2>&1 | Out-Null
& $NSSM set KrexionDatabase Description 'Krexion local data engine' 2>&1 | Out-Null
& $NSSM set KrexionDatabase Start SERVICE_AUTO_START 2>&1 | Out-Null
& $NSSM set KrexionDatabase AppDirectory (Join-Path $Krexion 'database\bin') 2>&1 | Out-Null
& $NSSM set KrexionDatabase AppStdout  (Join-Path $Krexion 'logs\mongod.stdout.log') 2>&1 | Out-Null
& $NSSM set KrexionDatabase AppStderr  (Join-Path $Krexion 'logs\mongod.stderr.log') 2>&1 | Out-Null
& $NSSM set KrexionDatabase AppExit Default Restart 2>&1 | Out-Null
& $NSSM set KrexionDatabase AppRestartDelay 5000 2>&1 | Out-Null
& $NSSM set KrexionDatabase AppRotateFiles 1 2>&1 | Out-Null
& $NSSM set KrexionDatabase AppRotateBytes 10485760 2>&1 | Out-Null
Write-Host "   registered with --dbpath = $NewDataDir" -ForegroundColor Gray

# ── Step 6: Quick dry-run of mongod (no service) ──────────────
Write-Host "[6/8] Verifying mongod accepts the new dbpath..." -ForegroundColor Yellow
$tempOut = [System.IO.Path]::GetTempFileName()
$tempErr = [System.IO.Path]::GetTempFileName()
$p = Start-Process -FilePath $Mongod -ArgumentList @('--dbpath', $NewDataDir, '--port', '27017', '--bind_ip', '127.0.0.1') `
    -PassThru -RedirectStandardOutput $tempOut -RedirectStandardError $tempErr -WindowStyle Hidden
Start-Sleep -Seconds 4
if ($p.HasExited) {
    Write-Host "   FAILED — mongod exited with code $($p.ExitCode)" -ForegroundColor Red
    Write-Host "   stdout tail:" -ForegroundColor Yellow
    Get-Content $tempOut -Tail 10 | ForEach-Object { Write-Host "      $_" -ForegroundColor Red }
} else {
    $p.Kill()
    Write-Host "   mongod ran cleanly for 4 sec — new dbpath is good." -ForegroundColor Green
}
Remove-Item $tempOut, $tempErr -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# ── Step 7: Start services ────────────────────────────────────
Write-Host "[7/8] Starting services..." -ForegroundColor Yellow
foreach ($svc in @('KrexionDatabase','KrexionBackend')) {
    try {
        Start-Service -Name $svc
        Start-Sleep -Seconds 3
        $s = Get-Service -Name $svc
        if ($s.Status -eq 'Running') {
            Write-Host "   started: $svc" -ForegroundColor Green
        } else {
            Write-Host "   $svc status = $($s.Status)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "   ERROR starting $svc : $($_.Exception.Message)" -ForegroundColor Red
    }
}

# ── Step 8: Backend health check ──────────────────────────────
Write-Host "[8/8] Verifying backend health (waiting 15 sec for startup)..." -ForegroundColor Yellow
Start-Sleep -Seconds 12
$ok = $false
for ($i = 1; $i -le 6; $i++) {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8001/api/system/version' -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) {
            $ok = $true
            Write-Host "   Backend RESPONDING. Version: $($r.Content)" -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "   attempt $i failed, retrying..." -ForegroundColor Gray
        Start-Sleep -Seconds 4
    }
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Cyan
if ($ok) {
    Write-Host "  SUCCESS!  Krexion is now fully operational." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Next steps:" -ForegroundColor White
    Write-Host "    1. Open https://krexion.com — top-right will show 'PC connected'"
    Write-Host "    2. Submit a heavy job (Visual Recorder / RUT / Form Filler)"
    Write-Host "    3. The job will now run successfully — local DB is up."
    Write-Host ""
    Write-Host "  To launch the desktop dashboard window manually:"
    Write-Host "    Double-click  C:\Program Files\Krexion\krexion-tray.bat"
} else {
    Write-Host "  Backend did not respond after 30 seconds." -ForegroundColor Red
    Write-Host "  Please check 'C:\Program Files\Krexion\logs\backend.stderr.log'"
    Write-Host "  and share the last 30 lines with the developer."
}
Write-Host "════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

pause
