; ════════════════════════════════════════════════════════════════════════
; Krexion — Inno Setup Installer Script (White-Label Edition)
; ════════════════════════════════════════════════════════════════════════
;
; Build with:
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\krexion-setup.iss
;
; Produces:  installer\Output\Krexion-Setup-<version>.exe
;
; What it installs (all in C:\Program Files\Krexion by default):
;   • bin\krexion-core.exe            — Krexion-branded core engine binary
;   • bin\krexion-service.exe         — Windows service wrapper (renamed NSSM)
;   • database\                       — Embedded local database engine
;   • browser-engine\                 — Bundled Chromium for anti-detect
;   • frontend\                       — Production React build
;   • krexion-tray.exe                — System tray app (optional)
;
; What it registers:
;   • Windows Service "KrexionBackend"   (auto-start)
;   • Windows Service "KrexionDatabase"  (auto-start)
;   • Start Menu shortcut "Krexion"
;   • Desktop shortcut "Krexion" (optional)
;   • Krexion auto-start at login (optional)
;
; NO third-party branding anywhere customer-visible — folder names, service
; names, registry keys, tray tooltip all say "Krexion".
; ════════════════════════════════════════════════════════════════════════

#define AppName        "Krexion"
#define AppPublisher   "Krexion"
#define AppURL         "https://krexion.com"
#define AppExeCore     "krexion-core.exe"
#define AppExeService  "krexion-service.exe"
#define AppExeTray     "krexion-tray.exe"
#define AppLauncherBat "krexion-tray.bat"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
; AppVersionNumeric is the strict X.X.X.X form (digits + dots only,
; max 4 parts) that Inno Setup's VersionInfoVersion field requires
; (it ultimately becomes the Windows EXE FILEVERSION resource). The
; GitHub Actions workflow derives it from the display tag — e.g.
; "v1.0.5" -> "1.0.5.0", "nightly-…" -> "0.0.0.0". When building
; locally without /DAppVersionNumeric, fall back to "1.0.0.0" so
; Inno Setup doesn't choke on a non-numeric AppVersion like "v1.0.0".
#ifndef AppVersionNumeric
  #define AppVersionNumeric "1.0.0.0"
#endif

[Setup]
AppId={{A4F5C3D2-7E91-4B6E-B0F1-KREXION0001}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/support
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\Krexion
DefaultGroupName=Krexion
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=Krexion-Setup-{#AppVersion}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
UninstallDisplayName={#AppName}
SetupIconFile=krexion.ico
UninstallDisplayIcon={app}\bin\{#AppExeCore}
VersionInfoCompany={#AppPublisher}
VersionInfoProductName={#AppName}
VersionInfoVersion={#AppVersionNumeric}
VersionInfoDescription=Krexion Real-User Traffic Engine
CloseApplications=force
RestartApplications=no
WizardImageStretch=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startupTray"; Description: "Start Krexion automatically when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Krexion brand icon — used for all Start Menu + Desktop shortcuts so
; the customer sees the Krexion "K" mark everywhere (not the default
; python.exe snake icon embedded in krexion-core.exe).
Source: "krexion.ico"; DestDir: "{app}"; Flags: ignoreversion

; Backend embedded-Python bundle — required
Source: "..\build\dist\krexion-backend.dist\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs createallsubdirs

; Service wrapper (NSSM, renamed to krexion-service.exe to hide third-party branding)
Source: "..\build\nssm-portable\nssm.exe"; DestDir: "{app}\bin"; DestName: "{#AppExeService}"; Flags: ignoreversion

; Local database engine (MongoDB Portable, folder renamed to `database`)
Source: "..\build\mongo-portable\*"; DestDir: "{app}\database"; Flags: ignoreversion recursesubdirs createallsubdirs

; Browser engine (Playwright Chromium, folder renamed to `browser-engine`)
Source: "..\build\chromium-bundle\*"; DestDir: "{app}\browser-engine"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Frontend production build — required
Source: "..\build\frontend-build\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs

; Tray / Dashboard app (PyWebView + pystray, renamed pythonw.exe)
; Bundled inside krexion-backend.dist as krexion-coreapp.exe — surfaced as
; krexion-tray.exe shortcut launcher for the customer.
Source: "..\desktop\krexion_tray_launcher.bat"; DestDir: "{app}"; DestName: "{#AppLauncherBat}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\desktop\*"; DestDir: "{app}\bin\app\desktop"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Manifest — optional
Source: "..\build\krexion-manifest.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Microsoft Visual C++ 2015-2022 Redistributable (x64) — REQUIRED by MongoDB
; 7.0.x. Without it mongod.exe silently crashes with VCRUNTIME140_1.dll
; missing. We ship it inline and run silently if not already present.
Source: "..\build\vcredist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist

; Microsoft Edge WebView2 Runtime — REQUIRED by PyWebView on Windows.
; Win11 ships it pre-installed, but a clean Win10 PC (especially LTSC
; / Server 2019 / older N-edition) often lacks it → pywebview's
; EdgeChromium backend silently fails to initialise and the Krexion
; dashboard window never appears (customer only sees krexion.com open
; in browser). We ship Microsoft's official Evergreen bootstrapper
; (~1.6 MB) which is idempotent: it checks if WebView2 is already
; present and exits 0 immediately if so.
Source: "..\build\webview2\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist

; Adaptive system-specs detector — invoked from the [Run] section to
; write %PROGRAMDATA%\Krexion\system-specs.json the backend reads on
; startup to size its heavy-job semaphore. Deleted after install.
Source: "detect-system-specs.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall


[Dirs]
; MongoDB data dir lives under %PROGRAMDATA% so NSSM's argv re-assembly
; never breaks on whitespace ("Program Files"). Data survives uninstall
; by default — customer's local DB persists across upgrades.
Name: "{commonappdata}\Krexion\data"; Permissions: users-modify
Name: "{commonappdata}\Krexion\data\db"; Permissions: users-modify
Name: "{app}\logs"
Name: "{commonappdata}\Krexion"; Permissions: users-modify

[Icons]
Name: "{group}\Krexion"; Filename: "{#AppURL}/login"; IconFilename: "{app}\krexion.ico"
Name: "{group}\Krexion Support"; Filename: "{#AppURL}/support"; IconFilename: "{app}\krexion.ico"
; The shortcut name MUST NOT contain "/" or "\" — Windows' file system
; treats both as path separators, so a name like "Buy / Renew License"
; makes Inno Setup try to create "Renew License.url" inside a missing
; "Buy " subfolder and abort with "The system cannot find the path
; specified." We use the word "or" (or an en-dash) which is shell-safe
; and reads identically to the user.
Name: "{group}\Buy or Renew License"; Filename: "{#AppURL}/pricing"; IconFilename: "{app}\krexion.ico"
Name: "{group}\Krexion Logs"; Filename: "{app}\logs"; IconFilename: "{app}\krexion.ico"
Name: "{group}\Uninstall Krexion"; Filename: "{uninstallexe}"; IconFilename: "{app}\krexion.ico"
Name: "{autodesktop}\Krexion"; Filename: "{#AppURL}/login"; IconFilename: "{app}\krexion.ico"; Tasks: desktopicon

[Registry]
; Auto-start Krexion Dashboard on login (per-user). Launches the
; PyWebView+tray app via a small .bat shim so customer sees Krexion's
; brand and not any python prompt window.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "Krexion"; ValueData: """{app}\{#AppLauncherBat}"""; \
  Tasks: startupTray; Flags: uninsdeletevalue

[Run]
; ─── Install Microsoft VC++ 2015-2022 Redistributable (silent, idempotent) ──
; MongoDB 7.0 needs VCRUNTIME140_1.dll which only ships with this runtime.
; /install /quiet /norestart returns exit code 1638 when the runtime is
; already installed (a NEWER version) — that's fine, we accept it.
Filename: "{tmp}\vc_redist.x64.exe"; \
  Parameters: "/install /quiet /norestart"; \
  Flags: runhidden waituntilterminated skipifdoesntexist; \
  StatusMsg: "Installing prerequisites (Visual C++ Runtime)..."

; ─── Install Microsoft Edge WebView2 Runtime (silent, idempotent) ──
; This is the runtime PyWebView uses to render the Krexion dashboard
; window. The MicrosoftEdgeWebview2Setup.exe bootstrapper is a small
; (~1.6 MB) Evergreen installer that:
;   1. Detects if WebView2 is already on this PC → exits 0 instantly
;   2. Otherwise downloads + installs the latest runtime silently
; /silent /install are Microsoft's documented switches. If the
; bootstrapper is missing from the bundle (older build) we skip
; gracefully — the Krexion dashboard has a Tkinter fallback that
; covers this case too, but having WebView2 means the customer sees
; the FULL dashboard, not the compatibility window.
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; \
  Parameters: "/silent /install"; \
  Flags: runhidden waituntilterminated skipifdoesntexist; \
  StatusMsg: "Installing prerequisites (Microsoft Edge WebView2)..."

; ─── Persist the license key the user entered in the wizard ────────────
; The license is written to %PROGRAMDATA%\Krexion\license-key.txt so the
; backend reads it via LICENSE_KEY_FILE env var. Customer never has to
; copy the key to .env manually — installer handles it.
Filename: "{cmd}"; \
  Parameters: "/C echo {code:GetLicenseKey} > ""{commonappdata}\Krexion\license-key.txt"""; \
  Flags: runhidden; StatusMsg: "Saving license key..."; \
  Check: HasLicenseKey

; ─── Persist detected hardware specs ──────────────────────────────────
; Runs detect-system-specs.ps1 which writes
; %PROGRAMDATA%\Krexion\system-specs.json. Backend reads this on
; startup to set adaptive concurrency limits for heavy jobs. The
; PowerShell script handles its own errors and never fails the
; installer — worst case it writes a safe medium-tier fallback.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{tmp}\detect-system-specs.ps1"" -OutDir ""{commonappdata}\Krexion"""; \
  Flags: runhidden waituntilterminated; StatusMsg: "Detecting your PC capacity..."

; ─── Install + start Krexion Database service ──────────────────────────
; Note the dbpath: we point at %PROGRAMDATA%\Krexion\data\db (no
; whitespace) so NSSM's argv re-assembly preserves the value intact.
; The previous v1.0.8 build used {app}\data\db which lives under
; "C:\Program Files\Krexion\data\db" — the space in "Program Files"
; got swallowed by Windows argv parsing and mongod received only
; "C:\Program" as its dbpath, then dumped its help text and exited
; immediately. That was the root cause of every "Krexion Database
; Paused" report.
Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "install KrexionDatabase ""{app}\database\bin\mongod.exe"" --dbpath {commonappdata}\Krexion\data\db --port 27017 --bind_ip 127.0.0.1 --quiet"; \
  Flags: runhidden; StatusMsg: "Registering Krexion Database service..."

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase DisplayName ""Krexion Database"""; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase Description ""Krexion local data engine"""; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase Start SERVICE_AUTO_START"; \
  Flags: runhidden

; Diagnostic logging — captures mongod stdout/stderr to {app}\logs\
; (without these, if mongod crashes the customer has zero visibility)
Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase AppDirectory ""{app}\database\bin"""; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase AppStdout ""{app}\logs\mongod.stdout.log"""; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase AppStderr ""{app}\logs\mongod.stderr.log"""; \
  Flags: runhidden

; Auto-restart on crash (NSSM AppExit Default Restart) + 5s cooldown
Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase AppExit Default Restart"; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase AppRestartDelay 5000"; \
  Flags: runhidden

; Rotate log files at 10 MB to prevent disk fill on long-running installs
Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase AppRotateFiles 1"; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionDatabase AppRotateBytes 10485760"; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "start KrexionDatabase"; \
  Flags: runhidden; StatusMsg: "Starting Krexion Database..."

; ─── Install + start Krexion Backend service ───────────────────────────
; Service runs via krexion-core.exe (white-labelled python.exe copy) so
; the customer's Task Manager + Services.msc only ever shows "Krexion".
Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "install KrexionBackend ""{app}\bin\{#AppExeCore}"" -m uvicorn server:app --host 127.0.0.1 --port 8001"; \
  Flags: runhidden; StatusMsg: "Registering Krexion Backend service..."

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend DisplayName ""Krexion Backend"""; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend Description ""Krexion core service — Real-User Traffic engine"""; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend Start SERVICE_AUTO_START"; \
  Flags: runhidden

; NSSM's `AppEnvironmentExtra` accepts multiple "NAME=VALUE" arguments
; in one call, but Windows command-line parsing splits on spaces — so
; values containing spaces (notably PLAYWRIGHT_BROWSERS_PATH when {app}
; resolves to "C:\Program Files\Krexion") would be torn into separate
; argv slots and NSSM would receive garbage. Result: NO env vars get
; set, the Python backend crashes with "MONGO_URL environment variable
; is required!", and NSSM throttles the service into the "Paused"
; state. We wrap EVERY "NAME=VALUE" pair in literal quotes (Inno Setup
; doubles "" -> ") so each one arrives at NSSM as a single argv entry,
; regardless of the install path the customer picks.
Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend AppEnvironmentExtra ""MONGO_URL=mongodb://127.0.0.1:27017"" ""DB_NAME=krexion"" ""KREXION_MODE=native"" ""KREXION_BUILD_TYPE=binary"" ""PLAYWRIGHT_BROWSERS_PATH={app}\browser-engine"" ""STRICT_CLOUD_HEAVY_BLOCK=false"" ""LICENSE_KEY_FILE={commonappdata}\Krexion\license-key.txt"""; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend AppDirectory ""{app}\bin\app"""; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend AppStdout ""{app}\logs\backend.stdout.log"""; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend AppStderr ""{app}\logs\backend.stderr.log"""; \
  Flags: runhidden

; Auto-restart on crash (NSSM AppExit Default Restart) + 5s cooldown
Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend AppExit Default Restart"; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend AppRestartDelay 5000"; \
  Flags: runhidden

; Rotate log files at 10 MB
Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend AppRotateFiles 1"; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend AppRotateBytes 10485760"; \
  Flags: runhidden

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "start KrexionBackend"; \
  Flags: runhidden; StatusMsg: "Starting Krexion Backend..."

; ─── Auto-launch desktop dashboard at finish ──────────────────────────
; The dashboard window stays open until the customer right-clicks the
; tray icon → Quit. Closing the X minimises to tray. Polls local
; backend at 127.0.0.1:8001 for live CPU/RAM/job stats and shows
; auto-update banner when admin publishes a new release.
Filename: "{app}\{#AppLauncherBat}"; Flags: nowait postinstall skipifsilent skipifdoesntexist; \
  Description: "Launch Krexion now"
Filename: "{#AppURL}/login"; Flags: shellexec postinstall skipifsilent; \
  Description: "Open Krexion dashboard at krexion.com"

[UninstallRun]
; Stop + remove services BEFORE files are deleted
Filename: "{app}\bin\{#AppExeService}"; Parameters: "stop KrexionBackend"; Flags: runhidden; RunOnceId: "StopBackend"
Filename: "{app}\bin\{#AppExeService}"; Parameters: "remove KrexionBackend confirm"; Flags: runhidden; RunOnceId: "RemoveBackend"
Filename: "{app}\bin\{#AppExeService}"; Parameters: "stop KrexionDatabase"; Flags: runhidden; RunOnceId: "StopDatabase"
Filename: "{app}\bin\{#AppExeService}"; Parameters: "remove KrexionDatabase confirm"; Flags: runhidden; RunOnceId: "RemoveDatabase"

[UninstallDelete]
; Logs go on uninstall. The entire %PROGRAMDATA%\Krexion tree
; (license + data + system-specs) is PRESERVED on uninstall by
; default — that means a reinstall picks up where the customer left
; off, with their MongoDB data and license intact. Customer can
; manually delete `C:\ProgramData\Krexion` if they want a full purge.
Type: filesandordirs; Name: "{app}\logs"

[Code]
var
  LicensePage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  // Custom wizard page — collect the customer's license key BEFORE
  // installation begins. The value is later piped into license-key.txt
  // by the [Run] section.
  LicensePage := CreateInputQueryPage(
    wpWelcome,
    'License Activation',
    'Enter your Krexion license key',
    'Paste the KRX-XXXX-XXXX-XXXX-XXXX key from your purchase email.' + #13#10 +
    'You can leave this blank and add it later from the Krexion dashboard.'
  );
  LicensePage.Add('License key:', False);
  LicensePage.Values[0] := '';
end;

function GetLicenseKey(Param: string): string;
var
  Raw: string;
begin
  Raw := Trim(LicensePage.Values[0]);
  // Strip stray whitespace + uppercase so it matches the canonical
  // KRX-XXXX-XXXX-XXXX-XXXX format the backend expects.
  StringChangeEx(Raw, ' ', '', True);
  Result := Uppercase(Raw);
end;

function HasLicenseKey: Boolean;
begin
  Result := Length(GetLicenseKey('')) > 0;
end;

function InitializeSetup(): Boolean;
begin
  // Future hook for OS version / disk space pre-flight checks.
  Result := True;
end;
