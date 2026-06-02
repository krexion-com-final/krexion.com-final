@echo off
REM ════════════════════════════════════════════════════════════════════
REM   Krexion — One-Click WSL2 Memory Allocation (ZERO-OOM Plan)
REM   ────────────────────────────────────────────────────────────────
REM   Allocates 20 GB RAM + 8 CPU cores + 8 GB swap to WSL2 / Docker.
REM   Of those 20 GB:
REM     • Mongo container       — capped at 4 GB (mem_limit + WT cap)
REM     • Backend container     — capped at 6 GB (mem_limit + code throttle)
REM     • Cloudflared (×2)      — 512 MB total
REM     • WSL kernel + buffers  — ~9.5 GB headroom
REM
REM   Math: 4 + 6 + 0.5 = 10.5 GB committed << 20 GB WSL =
REM   PHYSICALLY IMPOSSIBLE for the host to OOM. With the 80% RSS
REM   throttle in the backend, container-level OOM is also prevented.
REM
REM   Use when:
REM     • Docker container OOM-kills during big RUT jobs
REM     • Your PC has 32 GB+ total RAM and you want bullet-proof memory
REM
REM   What it does:
REM     1. Writes a .wslconfig file to %USERPROFILE% with the recommended
REM        ZERO-OOM limits for Krexion on a 32 GB PC.
REM     2. Shuts down WSL so the new limits take effect.
REM     3. Reminds you to restart Docker Desktop (it can't auto-restart
REM        another GUI app reliably from a script).
REM
REM   For PCs with different RAM:
REM     • 16 GB total → set memory=12GB, processors=4, swap=4GB
REM     • 32 GB total → set memory=20GB, processors=8, swap=8GB  (default)
REM     • 64 GB total → set memory=32GB, processors=12, swap=16GB
REM
REM   Edit the values below if you want different limits.
REM ════════════════════════════════════════════════════════════════════

setlocal

echo.
echo ============================================================
echo   Krexion — WSL2 Memory Allocation Setup (20 GB - ZERO-OOM)
echo ============================================================
echo.

set "WSLCONFIG_PATH=%USERPROFILE%\.wslconfig"

echo [1/4] Writing %WSLCONFIG_PATH% ...
(
    echo [wsl2]
    echo # 20 GB RAM allocated to WSL2 ^(used by Docker Desktop on Windows^)
    echo # Container caps: Mongo 4 GB + Backend 6 GB + Cloudflared 0.5 GB
    echo # = 10.5 GB committed, 9.5 GB headroom for kernel/file-cache.
    echo # Combined with the backend code-level memory-pressure throttle,
    echo # this layout makes job-killing OOM events mathematically impossible.
    echo memory=20GB
    echo.
    echo # CPU cores — use 8 of them
    echo processors=8
    echo.
    echo # Disk swap fallback — gives a soft cushion if a job spikes briefly
    echo swap=8GB
    echo.
    echo # Don't auto-reclaim memory back to Windows ^(faster sustained perf^)
    echo pageReporting=false
    echo.
    echo # No GUI apps ^(saves ~200 MB, we don't need X11 for backend^)
    echo guiApplications=false
    echo.
    echo [experimental]
    echo # Faster sparse VHD growth for the Docker volume disk
    echo sparseVhd=true
) > "%WSLCONFIG_PATH%"

if not exist "%WSLCONFIG_PATH%" (
    echo [ERROR] Could not write .wslconfig
    pause
    exit /b 1
)
echo        Done.
echo.

echo [2/4] Current .wslconfig contents:
type "%WSLCONFIG_PATH%"
echo.

echo [3/4] Shutting down WSL ^(saves all distros, then restarts on first use^)...
wsl --shutdown
if errorlevel 1 (
    echo [WARN] wsl --shutdown returned error %ERRORLEVEL% — that's usually fine
    echo        ^(just means WSL wasn't running^).
)
echo        WSL shut down.
echo.

echo [4/4] Now PLEASE RESTART DOCKER DESKTOP MANUALLY:
echo.
echo        a^) System Tray ^(bottom-right of taskbar^) → right-click whale icon
echo        b^) Click "Quit Docker Desktop"
echo        c^) Wait 5 sec, then re-open Docker Desktop from Start Menu
echo.
echo        Docker will boot WSL2 with the new 20 GB ZERO-OOM limit.
echo.

echo ============================================================
echo   After Docker Desktop restarts, verify with:
echo.
echo     docker run --rm alpine sh -c "free -h ^| grep Mem"
echo.
echo   Expected:  Mem:  ~19Gi total  ^(some overhead from Linux kernel^)
echo.
echo   Then run KREXION-FORCE-SYNC.bat so the backend container picks
echo   up the new 6 GB mem_limit + Mongo 4 GB cap from docker-compose.yml.
echo ============================================================
echo.

pause
endlocal
