=======================================================================

         R E A L F L O W   --   O N E - C L I C K   S E T U P

=======================================================================

HOW TO USE
----------

  1.  Double-click  Install.bat

  2.  Click "Yes" on the Admin permission popup.

  3.  Click the big blue "INSTALL" button.

  4.  Wait. (5-30 minutes first time, depending on internet speed.)

  5.  Click "OPEN REALFLOW" when done.

THAT'S IT.  No commands. No technical knowledge. No questions asked.


WHAT IT DOES (automatically)
----------------------------

  OK  Installs Docker Desktop  (downloads ~520 MB if not present)
  OK  Installs Git  (downloads ~50 MB if not present)
  OK  Configures WSL2 memory based on your RAM
     (8 GB PC ? 5 GB cap so Windows stays smooth)
  OK  Downloads the RealFlow code from GitHub
  OK  Generates a strong random admin password
  OK  Builds and starts the app (FastAPI + MongoDB + React)
  OK  Auto-detects 8 GB RAM and switches to Low-RAM profile
  OK  Creates a "RealFlow" shortcut on your Desktop
  OK  Opens http://localhost:3000 in your browser


REQUIREMENTS
------------

  * Windows 10 (64-bit, version 1903+) or Windows 11
  * 8 GB RAM (minimum) -- 16 GB recommended for heavy RUT use
  * 30 GB free disk space
  * Administrator account (UAC popup will appear)
  * Internet connection  (only for first install -- see "Offline" below)
  * Virtualization enabled in BIOS  (most modern PCs have it on)


OFFLINE / PORTABLE INSTALL (for the second PC and beyond)
---------------------------------------------------------

After the FIRST PC installs successfully, copy this entire folder
(RealFlow-Setup\) to a USB stick. The "bundle\" subfolder will now
contain:

   bundle\DockerDesktopInstaller.exe     (~520 MB, cached)
   bundle\Git-Installer.exe              (~50 MB,  cached)

On the second PC the wizard SKIPS those downloads and uses the
cached files -- install takes only ~5 minutes even with no internet.

You still need internet to "git clone" the code itself OR you can
pre-clone it into a local folder and tweak setup-engine.ps1 to use
the local path.


AFTER INSTALL
-------------

  Open in browser:        http://localhost:3000
  Admin login:            http://localhost:3000/admin-login
  Email:                  admin@realflow.local
  Password:               (shown by the wizard + saved in
                           C:\realflow\.env  ?  ADMIN_PASSWORD)

  Desktop shortcut "RealFlow" ? opens http://localhost:3000


DAILY USE
---------

  * Start your PC.
  * Docker Desktop starts automatically.
  * Double-click the "RealFlow" desktop shortcut.
  * Done.

  To STOP:  open  C:\realflow\  and double-click  LOCAL-STOP.bat
  To LOGS:  double-click  REALFLOW-LOGS.bat
  To UPGRADE later: re-run  Install.bat  (auto-backs-up Mongo,
                                          pulls latest code,
                                          rebuilds)


TROUBLESHOOTING
---------------

  X "I double-click Install.bat and a CMD window flashes
     for 1 second then closes -- nothing happens"
       ? This means PowerShell exited before showing the wizard.
       ? Run  Debug.bat  (next to Install.bat) instead. It keeps
         the window open and prints diagnostics + the exact error.
       ? Most common causes:
           1. Antivirus quarantined setup-engine.ps1.
              Open AV ? quarantine ? restore + add this folder
              to the exclusion list.
           2. PowerShell ExecutionPolicy locked by Group Policy.
              Run as Admin in PowerShell:
                Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
           3. .NET Desktop Runtime missing on Windows 10 LTSC.
              Install from https://dotnet.microsoft.com/download
           4. You only extracted Install.bat -- not the whole folder.
              Re-extract the entire RealFlow-Setup folder.

  * "Docker engine did not start"
       ? Open Docker Desktop manually from Start menu
       ? Wait for the whale icon to stop animating
       ? Re-run Install.bat

  * "INSTALL fails halfway through"
       ? Read the wizard log:  setup.log  (next to Install.bat)
       ? 90% of failures are Docker not ready -- fix above

  * Forgot admin password
       ? Open  C:\realflow\.env  in Notepad
       ? Look for the line:  ADMIN_PASSWORD=........

  * Want to wipe and re-install
       ? Delete  C:\realflow\  folder
       ? Delete  .resume-stage  file from this folder
       ? Double-click Install.bat again


SUPPORT
-------

  Detailed Urdu guide:    C:\realflow\DEPLOY-README-URDU.md
  8 GB tuning guide:      C:\realflow\DYNABOOK-8GB-GUIDE.md
  GitHub:                 https://github.com/ronaldsexedwards40-glitch/dynabook

=======================================================================
