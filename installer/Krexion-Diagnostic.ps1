# ════════════════════════════════════════════════════════════════════
#   Krexion Self-Diagnostic Tool (PowerShell version)
# ════════════════════════════════════════════════════════════════════
# Why a PS1 sibling to the .bat?
#   Customer-side Windows Defender / SmartScreen silently kills .bat
#   files downloaded from raw GitHub URLs. PowerShell scripts launched
#   via `irm | iex` are not subject to the same Mark-of-the-Web block,
#   so this is the more reliable diagnostic delivery vector.
#
# Usage (one liner the customer pastes into an *elevated* PowerShell):
#   irm https://raw.githubusercontent.com/dennisedmaartins9-sudo/krexion.com/main/installer/Krexion-Diagnostic.ps1 | iex
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = 'Continue'

$OutFile = Join-Path $env:USERPROFILE 'Desktop\krexion-diagnostic.txt'
$Krexion = 'C:\Program Files\Krexion'

function Write-Section {
    param([string]$Title)
    Add-Content -Path $OutFile -Value "`r`n--- $Title ---" -Encoding UTF8
}

function Write-Line {
    param([string]$Text)
    Add-Content -Path $OutFile -Value $Text -Encoding UTF8
}

function Capture-Command {
    param([scriptblock]$Block)
    try {
        $output = & $Block 2>&1 | Out-String
        Write-Line $output.TrimEnd()
    } catch {
        Write-Line ("ERROR: " + $_.Exception.Message)
    }
}

Write-Host "Krexion Self-Diagnostic Tool" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host "Output -> $OutFile" -ForegroundColor Gray
Write-Host ""

# Initialise file
Set-Content -Path $OutFile -Value "Krexion Diagnostic Report" -Encoding UTF8
Write-Line "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Line "Computer:  $env:COMPUTERNAME    User: $env:USERNAME"
Write-Line ('=' * 60)

# ── 1. Windows version ─────────────────────────────────────────
Write-Host "[1/11] Windows version"
Write-Section "1. Windows version"
Capture-Command { [System.Environment]::OSVersion }
Capture-Command { (Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture | Format-List) }

# ── 2. Install folder contents ────────────────────────────────
Write-Host "[2/11] Install folder contents"
Write-Section "2. Krexion install folder"
if (Test-Path $Krexion) {
    Write-Line "Install dir: $Krexion"
    Write-Line ""
    Write-Line "TOP-LEVEL items:"
    Capture-Command { Get-ChildItem -Path $Krexion -Force | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize | Out-String -Width 200 }

    Write-Line "bin contents (looking for krexion-core/coreapp.exe):"
    Capture-Command { Get-ChildItem -Path (Join-Path $Krexion 'bin') -Filter '*.exe' -ErrorAction SilentlyContinue | Select-Object Name, Length | Format-Table -AutoSize }
    Capture-Command { Get-ChildItem -Path (Join-Path $Krexion 'bin') -Filter '*._pth' -ErrorAction SilentlyContinue | Select-Object Name, Length | Format-Table -AutoSize }

    Write-Line "bin\app\desktop contents:"
    $deskPath = Join-Path $Krexion 'bin\app\desktop'
    if (Test-Path $deskPath) {
        Capture-Command { Get-ChildItem $deskPath -Recurse -File | Select-Object FullName | Format-Table -AutoSize -Wrap | Out-String -Width 200 }
    } else {
        Write-Line "  MISSING - bin\app\desktop folder not found"
    }

    Write-Line "database\bin contents:"
    $dbPath = Join-Path $Krexion 'database\bin'
    if (Test-Path $dbPath) {
        Capture-Command { Get-ChildItem $dbPath -Filter '*.exe' | Select-Object Name, Length | Format-Table -AutoSize }
    } else {
        Write-Line "  MISSING - database\bin folder not found"
    }
} else {
    Write-Line "MISSING! Install folder $Krexion does not exist."
}

# ── 3. Data + config ──────────────────────────────────────────
Write-Host "[3/11] Data + config"
Write-Section "3. Krexion data + config"
Write-Line "data\db folder:"
$dbDataPath = Join-Path $Krexion 'data\db'
if (Test-Path $dbDataPath) {
    Capture-Command { Get-ChildItem $dbDataPath -Force -ErrorAction SilentlyContinue | Select-Object Name, Length | Format-Table -AutoSize }
} else {
    Write-Line "  MISSING - data\db folder not found"
}

Write-Line ""
Write-Line "C:\ProgramData\Krexion contents:"
if (Test-Path 'C:\ProgramData\Krexion') {
    Capture-Command { Get-ChildItem 'C:\ProgramData\Krexion' -Force | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize }
} else {
    Write-Line "  MISSING - C:\ProgramData\Krexion folder not found"
}

Write-Line ""
Write-Line "system-specs.json content:"
$specsFile = 'C:\ProgramData\Krexion\system-specs.json'
if (Test-Path $specsFile) {
    Capture-Command { Get-Content $specsFile -Raw }
} else {
    Write-Line "  MISSING - PowerShell specs detection did not write the file"
}

# ── 4. Services ───────────────────────────────────────────────
Write-Host "[4/11] Service status"
Write-Section "4. Service status"
foreach ($svc in @('KrexionBackend','KrexionDatabase')) {
    Write-Line "$svc :"
    Capture-Command { sc.exe query $svc }
}
Write-Line ""
Write-Line "NSSM dump for KrexionDatabase:"
$nssm = Join-Path $Krexion 'bin\krexion-service.exe'
if (Test-Path $nssm) {
    Capture-Command { & $nssm dump KrexionDatabase }
} else {
    Write-Line "  krexion-service.exe missing!"
}

# ── 5. Logs ───────────────────────────────────────────────────
Write-Host "[5/11] Log files"
Write-Section "5. Log files"
$logDir = Join-Path $Krexion 'logs'
if (Test-Path $logDir) {
    Write-Line "logs folder content:"
    Capture-Command { Get-ChildItem $logDir | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize }
    foreach ($log in @('mongod.stderr.log','mongod.stdout.log','backend.stderr.log','backend.stdout.log')) {
        $fp = Join-Path $logDir $log
        Write-Line ""
        Write-Line ("=== $log (last 40 lines) ===")
        if (Test-Path $fp) {
            Capture-Command { Get-Content $fp -Tail 40 }
        } else {
            Write-Line "  (file not present)"
        }
    }
} else {
    Write-Line "  MISSING - logs folder does not exist"
}

# ── 6. VC++ runtime ───────────────────────────────────────────
Write-Host "[6/11] Visual C++ runtime DLLs"
Write-Section "6. VC++ runtime"
foreach ($dll in @('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll')) {
    $sys = Join-Path $env:SystemRoot "System32\$dll"
    if (Test-Path $sys) {
        $v = (Get-Item $sys).VersionInfo.FileVersion
        Write-Line ("  FOUND  $dll  (version $v)")
    } else {
        Write-Line ("  MISSING  $dll  (this breaks MongoDB)")
    }
}

# ── 7. mongod direct test ─────────────────────────────────────
Write-Host "[7/11] mongod direct test"
Write-Section "7. mongod direct invocation"
$mongod = Join-Path $Krexion 'database\bin\mongod.exe'
if (Test-Path $mongod) {
    Write-Line "Running mongod --version :"
    Capture-Command { & $mongod --version }
    Write-Line ""
    Write-Line "Running mongod --dbpath check (5 sec timeout, dryRun) :"
    # Try a 5 second start and capture output
    try {
        $args = @('--dbpath', (Join-Path $Krexion 'data\db'), '--port', '27017', '--bind_ip', '127.0.0.1')
        $p = Start-Process -FilePath $mongod -ArgumentList $args -PassThru -RedirectStandardOutput "$env:TEMP\mongod.out.tmp" -RedirectStandardError "$env:TEMP\mongod.err.tmp" -WindowStyle Hidden
        Start-Sleep -Seconds 4
        if (!$p.HasExited) {
            $p.Kill()
            Write-Line "  mongod stayed alive for 4 seconds — looks healthy"
        } else {
            Write-Line ("  mongod exited within 4 seconds. ExitCode=" + $p.ExitCode)
        }
        Write-Line ""
        Write-Line "  STDOUT:"
        if (Test-Path "$env:TEMP\mongod.out.tmp") { Write-Line ((Get-Content "$env:TEMP\mongod.out.tmp" -Tail 25) -join "`r`n") }
        Write-Line ""
        Write-Line "  STDERR:"
        if (Test-Path "$env:TEMP\mongod.err.tmp") { Write-Line ((Get-Content "$env:TEMP\mongod.err.tmp" -Tail 25) -join "`r`n") }
    } catch {
        Write-Line ("  ERROR: " + $_.Exception.Message)
    }
} else {
    Write-Line "mongod.exe MISSING from $mongod"
}

# ── 8. Dashboard launch test ──────────────────────────────────
Write-Host "[8/11] Dashboard launch test"
Write-Section "8. Dashboard launch test"
$gui = Join-Path $Krexion 'bin\krexion-coreapp.exe'
$core = Join-Path $Krexion 'bin\krexion-core.exe'
Write-Line ("krexion-coreapp.exe (GUI interpreter):   " + (if (Test-Path $gui) { 'FOUND' } else { 'MISSING — dashboard cannot launch' }))
Write-Line ("krexion-core.exe    (console interp.):   " + (if (Test-Path $core) { 'FOUND' } else { 'MISSING' }))

if (Test-Path $core) {
    $appDir = Join-Path $Krexion 'bin\app'
    $modFile = Join-Path $appDir 'desktop\krexion_dashboard.py'
    if (Test-Path $modFile) {
        Write-Line ""
        Write-Line "Trying 'import desktop.krexion_dashboard' :"
        Push-Location $appDir
        try {
            Capture-Command { & $core -c "import desktop.krexion_dashboard; print('IMPORT OK')" }
        } finally {
            Pop-Location
        }
    } else {
        Write-Line "desktop\krexion_dashboard.py MISSING in bin\app\"
    }
}

# ── 9. Tray launcher .bat ─────────────────────────────────────
Write-Host "[9/11] Tray launcher"
Write-Section "9. Tray launcher"
$trayBat = Join-Path $Krexion 'krexion-tray.bat'
if (Test-Path $trayBat) {
    Write-Line "Found at $trayBat. Content:"
    Capture-Command { Get-Content $trayBat -Raw }
} else {
    Write-Line "MISSING — krexion-tray.bat is supposed to be at install root"
}

# ── 10. Autostart registry ────────────────────────────────────
Write-Host "[10/11] Autostart registry key"
Write-Section "10. Autostart registry key"
Capture-Command { reg query 'HKCU\Software\Microsoft\Windows\CurrentVersion\Run' /v Krexion }

# ── 11. Backend health ────────────────────────────────────────
Write-Host "[11/11] Backend health"
Write-Section "11. Backend health"
foreach ($url in @('http://127.0.0.1:8001/api/system/version','http://127.0.0.1:8001/api/desktop/stats')) {
    Write-Line ""
    Write-Line "GET $url :"
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        Write-Line ("HTTP " + $r.StatusCode)
        Write-Line $r.Content
    } catch {
        Write-Line ("ERROR: " + $_.Exception.Message)
    }
}

Write-Line ""
Write-Line ('=' * 60)
Write-Line "END OF DIAGNOSTIC"
Write-Line ('=' * 60)

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Diagnostic complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Output file: $OutFile"
Write-Host ""
Write-Host "  Next steps:"
Write-Host "   1. Open the file on your Desktop"
Write-Host "   2. Select All (Ctrl+A) and Copy (Ctrl+C)"
Write-Host "   3. Paste into the Emergent chat"
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""

# Also try to open the file for the user
try {
    Start-Process notepad.exe $OutFile -ErrorAction SilentlyContinue
} catch { }
