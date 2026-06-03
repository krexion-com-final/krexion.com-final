# ─────────────────────────────────────────────────────────────────────
# Krexion — Adaptive System Specs Detector
# ─────────────────────────────────────────────────────────────────────
# Invoked once during install (from krexion-setup.iss [Run] section)
# *and* available for the auto-updater to call later. Detects:
#
#   - Total physical RAM (GB)
#   - Logical CPU core count
#   - Tier  : low / medium / high / extreme
#   - Max concurrent heavy jobs  (1 / 2 / 4 / 8)
#
# Writes the result as compact JSON to:
#   %PROGRAMDATA%\Krexion\system-specs.json
#
# The local Krexion backend reads this file on startup (via
# `desktop/system_info.py`) to size its heavy-job semaphore — so a 4 GB
# / 2 core customer never tries to run 8 jobs at once.
#
# Why PowerShell and not Inno Setup Pascal?
#   Inno Pascal Script does not expose TMemoryStatusEx / TSystemInfo
#   as built-in types — declaring them via DLL imports works but is
#   fragile across Inno versions. PowerShell is bundled with every
#   Windows 7 SP1+ install, has clean WMI access, and gives identical
#   results across language packs.
# ─────────────────────────────────────────────────────────────────────

param(
  [string]$OutDir = "$env:ProgramData\Krexion"
)

$ErrorActionPreference = 'Stop'

try {
  # Use CIM (modern, faster than WMI). Falls back to WMI on very old
  # Windows builds where CIM isn't present.
  try {
    $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
  } catch {
    $cs = Get-WmiObject Win32_ComputerSystem
  }

  $ramGB = [int][math]::Round($cs.TotalPhysicalMemory / 1GB)
  if ($ramGB -lt 1) { $ramGB = 8 }   # safe fallback if detection fails

  $cores = [int]$cs.NumberOfLogicalProcessors
  if ($cores -lt 1) { $cores = 4 }

  # Tier ladder — matches desktop/system_info.py exactly so the
  # installer and runtime never disagree.
  $tier = if     ($ramGB -le 4  -or $cores -le 2) { 'low' }
          elseif ($ramGB -le 8  -or $cores -le 4) { 'medium' }
          elseif ($ramGB -le 16 -or $cores -le 8) { 'high' }
          else                                    { 'extreme' }

  $maxJobs = switch ($tier) {
    'low'     { 1 }
    'medium'  { 2 }
    'high'    { 4 }
    'extreme' { 8 }
    default   { 2 }
  }

  if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
  }

  # ConvertTo-Json -Compress -> single-line, compact, no
  # unicode-escaped slashes etc. Set-Content -NoNewline keeps the file
  # byte-identical between runs so backup / file-watcher tools don't
  # see spurious changes.
  $payload = [pscustomobject]@{
    ram_gb                    = $ramGB
    cpu_cores                 = $cores
    tier                      = $tier
    max_concurrent_heavy_jobs = $maxJobs
    detected_by               = 'installer-powershell'
    detected_at               = (Get-Date).ToUniversalTime().ToString('o')
  }

  $json = $payload | ConvertTo-Json -Compress -Depth 4
  $path = Join-Path $OutDir 'system-specs.json'
  Set-Content -Path $path -Value $json -Encoding UTF8 -NoNewline

  Write-Host "Krexion specs detected: $ramGB GB / $cores cores -> tier '$tier' (max $maxJobs jobs)"
  Write-Host "Written to: $path"
  exit 0
}
catch {
  Write-Warning "Krexion specs detection failed: $($_.Exception.Message)"
  # Don't abort the installer — write a safe fallback so the backend
  # still has something to read.
  try {
    if (-not (Test-Path $OutDir)) {
      New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    }
    $fallback = '{"ram_gb":8,"cpu_cores":4,"tier":"medium","max_concurrent_heavy_jobs":2,"detected_by":"installer-fallback"}'
    Set-Content -Path (Join-Path $OutDir 'system-specs.json') -Value $fallback -Encoding UTF8 -NoNewline
  } catch {}
  exit 0
}
