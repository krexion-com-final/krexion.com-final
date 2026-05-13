# RealFlow — Hardware Detection & Performance Profile Picker (Windows)
#
# Outputs a single object with detected RAM, CPU cores, free disk +
# the recommended performance tier. Used by setup-engine.ps1 and
# RealFlow-RETUNE.bat to pick the right docker-compose override.
#
# Tiers:
#   MICRO  -- RAM <= 6 GB                  -- 1 RUT worker
#   LOW    -- RAM 7-10 GB                  -- 2 RUT workers
#   MID    -- RAM 11-16 GB (CPU >= 4)      -- 4 RUT workers
#   HIGH   -- RAM 17-32 GB (CPU >= 6)      -- 8 RUT workers
#   BEAST  -- RAM > 32  GB (CPU >= 8)      -- 16 RUT workers
#
# CPU cores are a HARD ceiling: actual concurrency = min(tier, cores*2)
# so on a fast 4-core / 32 GB box you still cap at 8, not 16.

function Get-RealFlowProfile {
    $totalRamGB  = [int][math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 0)
    $cpuCores    = (Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
    if (-not $cpuCores) { $cpuCores = [Environment]::ProcessorCount }

    $sysDrive    = $env:SystemDrive  # e.g. C:
    $disk        = Get-PSDrive -Name ($sysDrive.TrimEnd(':')) -ErrorAction SilentlyContinue
    $freeDiskGB  = if ($disk) { [int][math]::Round($disk.Free / 1GB, 0) } else { 0 }

    # Pick tier (RAM is primary, CPU is a downgrade-only gate)
    if     ($totalRamGB -le 6)   { $tier = "MICRO"; $rutMax = 1;  $mongoCap = "512m";  $beCap = "1536m"; $feCap = "128m"; $wslMem = "4GB"  }
    elseif ($totalRamGB -le 10)  { $tier = "LOW";   $rutMax = 2;  $mongoCap = "1g";    $beCap = "2560m"; $feCap = "192m"; $wslMem = "5GB"  }
    elseif ($totalRamGB -le 16)  { $tier = "MID";   $rutMax = 4;  $mongoCap = "2g";    $beCap = "4g";    $feCap = "256m"; $wslMem = "10GB" }
    elseif ($totalRamGB -le 32)  { $tier = "HIGH";  $rutMax = 8;  $mongoCap = "4g";    $beCap = "8g";    $feCap = "384m"; $wslMem = "20GB" }
    else                         { $tier = "BEAST"; $rutMax = 16; $mongoCap = "8g";    $beCap = "16g";   $feCap = "512m"; $wslMem = "32GB" }

    # CPU ceiling: never run more than cores*2 Playwright workers
    $cpuCeiling = [Math]::Max(1, $cpuCores * 2)
    if ($rutMax -gt $cpuCeiling) {
        $rutMax = $cpuCeiling
    }

    # Pick the docker-compose override filename
    $composeOverride = switch ($tier) {
        "MICRO" { "docker-compose.micro.yml"  }
        "LOW"   { "docker-compose.lowram.yml" }
        "MID"   { "docker-compose.mid.yml"    }
        "HIGH"  { "docker-compose.high.yml"   }
        "BEAST" { "docker-compose.beast.yml"  }
    }

    # WSL processors -- give as many cores to WSL as the box has,
    # but cap at 12 to leave headroom for Windows itself
    $wslCores = [Math]::Min($cpuCores, 12)

    return [PSCustomObject]@{
        Tier              = $tier
        TotalRamGB        = $totalRamGB
        CpuCores          = $cpuCores
        FreeDiskGB        = $freeDiskGB
        RutConcurrency    = $rutMax
        MongoMemLimit     = $mongoCap
        BackendMemLimit   = $beCap
        FrontendMemLimit  = $feCap
        WSLMemory         = $wslMem
        WSLProcessors     = $wslCores
        ComposeOverride   = $composeOverride
    }
}

# When dot-sourced this just defines the function. When run directly
# (e.g. `powershell -File detect-hardware.ps1`) print a summary.
if ($MyInvocation.InvocationName -ne ".") {
    $p = Get-RealFlowProfile
    Write-Host ""
    Write-Host "  ===== RealFlow Hardware Profile =====" -ForegroundColor Cyan
    Write-Host "  RAM total            : $($p.TotalRamGB) GB"
    Write-Host "  CPU logical cores    : $($p.CpuCores)"
    Write-Host "  System drive free    : $($p.FreeDiskGB) GB"
    Write-Host ""
    Write-Host "  >>> Selected tier    : $($p.Tier)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  RUT concurrency      : $($p.RutConcurrency) parallel browsers"
    Write-Host "  Mongo memory cap     : $($p.MongoMemLimit)"
    Write-Host "  Backend memory cap   : $($p.BackendMemLimit)"
    Write-Host "  Frontend memory cap  : $($p.FrontendMemLimit)"
    Write-Host "  WSL2 allocation      : memory=$($p.WSLMemory)  processors=$($p.WSLProcessors)"
    Write-Host "  Compose override     : $($p.ComposeOverride)"
    Write-Host ""
}
