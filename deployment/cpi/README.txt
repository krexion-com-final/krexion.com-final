RealFlow CPI Worker — Deployment scripts (Windows 11)
═══════════════════════════════════════════════════════

Files in this folder
──────────────────────

REALFLOW-CPI-SETUP.ps1
    One-click installer. Run as Administrator on a fresh Windows 11 PC.
    Installs Python, Node, Appium, libimobiledevice, ADB, iTunes drivers,
    creates a venv, installs Python deps, bootstraps config.yaml.

REALFLOW-CPI-WORKER-START.bat
    Starts the worker in foreground. Press Ctrl+C to stop.

REALFLOW-CPI-WORKER-STOP.bat
    Kills any running worker process.

REALFLOW-CPI-DOCTOR.ps1
    Health check — verifies tooling, devices, backend reachability.

INSTALL-WORKER-AS-SERVICE.ps1
    Optional: registers the worker as a Windows service that auto-starts on
    boot. Uses NSSM under the hood.

Order of operations
───────────────────

  1. SETUP        →  Run REALFLOW-CPI-SETUP.ps1 once (Administrator)
  2. CONFIGURE    →  Edit ..\..\realflow-cpi-worker\config.yaml
                     • api.token = your RealFlow JWT
  3. CONNECT      →  Plug in Android phone (USB debugging ON)
                     Plug in iPhone (Trust Computer when prompted)
  4. VERIFY       →  REALFLOW-CPI-DOCTOR.ps1
  5. RUN          →  REALFLOW-CPI-WORKER-START.bat
  6. AUTO-START   →  INSTALL-WORKER-AS-SERVICE.ps1 (optional)

Troubleshooting
───────────────

• "adb not found"
  → Reopen PowerShell after running SETUP. The PATH is updated only for new shells.

• "Device unauthorized" in `adb devices`
  → On the phone, allow the RSA key prompt. Settings → Developer options → USB debugging.

• "iPhone not appearing in tidevice3 list"
  → 1) Open iTunes (just to trigger Apple drivers loading), then close it.
  → 2) On the iPhone, tap "Trust This Computer".
  → 3) Re-run REALFLOW-CPI-DOCTOR.ps1.

• Worker logs into wrong account / "auth failed"
  → JWT expired. On https://realflow.online, login again, copy fresh token,
    paste into config.yaml under api.token. Restart worker.

• Devices show "offline" in RealFlow web UI
  → Worker is not running, or its IP cannot reach api.realflow.online.
  → Check INSTALL-WORKER-AS-SERVICE service status: `nssm status RealFlowCPIWorker`
  → Check worker.err.log for connection errors.

For more help see ../../CPI-FAQ-URDU.md
