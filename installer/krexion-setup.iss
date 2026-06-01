; ════════════════════════════════════════════════════════════════════════
; Krexion — Inno Setup Installer Script
; ════════════════════════════════════════════════════════════════════════
;
; Build with:
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\krexion-setup.iss
;
; Produces:  installer\Output\Krexion-Setup-<version>.exe
;
; What it installs (all in C:\Program Files\Krexion by default):
;   • bin\krexion-backend.exe        — Nuitka-compiled FastAPI backend
;   • bin\nssm.exe                   — Windows service wrapper
;   • mongo\                         — MongoDB Portable (no Docker!)
;   • chromium\                      — Bundled Playwright Chromium
;   • frontend\                      — Production React build
;   • krexion-tray.exe               — System tray app (replaces Docker icon)
;
; What it registers:
;   • Windows Service "KrexionBackend"   (auto-start)
;   • Windows Service "KrexionDatabase"  (auto-start, MongoDB)
;   • Start Menu shortcut "Krexion"
;   • Desktop shortcut "Krexion" (optional, customer-tickable)
;   • Krexion Tray app in HKCU Run (starts at login)
;
; UNINSTALL is clean — stops services, deletes them, removes all files.
;
; THIS DOES NOT INSTALL DOCKER. Customer sees "Krexion" everywhere, not Docker.
; ════════════════════════════════════════════════════════════════════════

#define AppName        "Krexion"
#define AppPublisher   "Krexion"
#define AppURL         "https://krexion.com"
#define AppExeBackend  "krexion-backend.exe"
#define AppExeTray     "krexion-tray.exe"
#ifndef AppVersion
  #define AppVersion "1.0.0"
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
; SetupIconFile=krexion.ico   ; <- Uncomment after you add installer/krexion.ico
UninstallDisplayIcon={app}\bin\{#AppExeBackend}
VersionInfoCompany={#AppPublisher}
VersionInfoProductName={#AppName}
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Krexion installer
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startupTray"; Description: "Start Krexion automatically when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Backend PyInstaller bundle (folder) — required
Source: "..\build\dist\krexion-backend.dist\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs createallsubdirs

; NSSM service wrapper — required
Source: "..\build\nssm-portable\nssm.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

; MongoDB Portable — required
Source: "..\build\mongo-portable\*"; DestDir: "{app}\mongo"; Flags: ignoreversion recursesubdirs createallsubdirs

; Playwright Chromium bundle — optional (backend self-installs if missing)
Source: "..\build\chromium-bundle\*"; DestDir: "{app}\chromium"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; Frontend production build — required
Source: "..\build\frontend-build\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs

; Tray app — optional
Source: "..\build\dist\krexion-tray.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Manifest + license shells — optional
Source: "..\build\krexion-manifest.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist


[Dirs]
Name: "{app}\data"
Name: "{app}\data\mongo"
Name: "{app}\logs"
Name: "{commonappdata}\Krexion"; Permissions: users-modify

[Icons]
Name: "{group}\Krexion"; Filename: "http://127.0.0.1:3000"; IconFilename: "{app}\bin\{#AppExeBackend}"
Name: "{group}\Krexion Logs"; Filename: "{app}\logs"
Name: "{group}\Uninstall Krexion"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Krexion"; Filename: "http://127.0.0.1:3000"; IconFilename: "{app}\bin\{#AppExeBackend}"; Tasks: desktopicon

[Registry]
; Auto-start Krexion Tray on login (per-user)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "Krexion"; ValueData: """{app}\{#AppExeTray}"""; \
  Tasks: startupTray; Flags: uninsdeletevalue

[Run]
; ─── Install + start MongoDB as Windows Service ─────────────────────────
Filename: "{app}\bin\nssm.exe"; \
  Parameters: "install KrexionDatabase ""{app}\mongo\bin\mongod.exe"" --dbpath ""{app}\data\mongo"" --port 27017 --bind_ip 127.0.0.1 --quiet"; \
  Flags: runhidden; StatusMsg: "Registering Krexion Database service..."

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionDatabase DisplayName ""Krexion Database"""; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionDatabase Description ""Krexion local MongoDB instance"""; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionDatabase Start SERVICE_AUTO_START"; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "start KrexionDatabase"; \
  Flags: runhidden; StatusMsg: "Starting Krexion Database..."

; ─── Install + start Krexion Backend as Windows Service ─────────────────
Filename: "{app}\bin\nssm.exe"; \
  Parameters: "install KrexionBackend ""{app}\bin\{#AppExeBackend}"""; \
  Flags: runhidden; StatusMsg: "Registering Krexion Backend service..."

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionBackend DisplayName ""Krexion Backend"""; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionBackend Description ""Krexion core service — runs FastAPI backend"""; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionBackend Start SERVICE_AUTO_START"; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionBackend AppEnvironmentExtra MONGO_URL=mongodb://127.0.0.1:27017 DB_NAME=krexion KREXION_MODE=native KREXION_BUILD_TYPE=binary PLAYWRIGHT_BROWSERS_PATH={app}\chromium"; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionBackend AppDirectory ""{app}\bin"""; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionBackend AppStdout ""{app}\logs\backend.stdout.log"""; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "set KrexionBackend AppStderr ""{app}\logs\backend.stderr.log"""; \
  Flags: runhidden

Filename: "{app}\bin\nssm.exe"; \
  Parameters: "start KrexionBackend"; \
  Flags: runhidden; StatusMsg: "Starting Krexion Backend..."

; ─── Optional: launch tray app + open dashboard at finish ───────────────
Filename: "{app}\{#AppExeTray}"; Flags: nowait postinstall skipifsilent skipifsourcedoesntexist; \
  Description: "Launch Krexion now"
Filename: "http://127.0.0.1:3000"; Flags: shellexec postinstall skipifsilent; \
  Description: "Open Krexion dashboard"

[UninstallRun]
; Stop + remove services BEFORE files are deleted
Filename: "{app}\bin\nssm.exe"; Parameters: "stop KrexionBackend"; Flags: runhidden; RunOnceId: "StopBackend"
Filename: "{app}\bin\nssm.exe"; Parameters: "remove KrexionBackend confirm"; Flags: runhidden; RunOnceId: "RemoveBackend"
Filename: "{app}\bin\nssm.exe"; Parameters: "stop KrexionDatabase"; Flags: runhidden; RunOnceId: "StopDatabase"
Filename: "{app}\bin\nssm.exe"; Parameters: "remove KrexionDatabase confirm"; Flags: runhidden; RunOnceId: "RemoveDatabase"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{commonappdata}\Krexion"

[Code]
function InitializeSetup(): Boolean;
begin
  // Future hardening hook — could check Windows version, RAM, etc.
  Result := True;
end;
