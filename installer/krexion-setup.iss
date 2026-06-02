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

; Tray app — optional
Source: "..\build\dist\krexion-tray.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Manifest — optional
Source: "..\build\krexion-manifest.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist


[Dirs]
Name: "{app}\data"
Name: "{app}\data\db"
Name: "{app}\logs"
Name: "{commonappdata}\Krexion"; Permissions: users-modify

[Icons]
Name: "{group}\Krexion"; Filename: "{#AppURL}/login"; IconFilename: "{app}\krexion.ico"
Name: "{group}\Krexion Support"; Filename: "{#AppURL}/support"; IconFilename: "{app}\krexion.ico"
Name: "{group}\Buy / Renew License"; Filename: "{#AppURL}/pricing"; IconFilename: "{app}\krexion.ico"
Name: "{group}\Krexion Logs"; Filename: "{app}\logs"; IconFilename: "{app}\krexion.ico"
Name: "{group}\Uninstall Krexion"; Filename: "{uninstallexe}"; IconFilename: "{app}\krexion.ico"
Name: "{autodesktop}\Krexion"; Filename: "{#AppURL}/login"; IconFilename: "{app}\krexion.ico"; Tasks: desktopicon

[Registry]
; Auto-start Krexion Tray on login (per-user)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "Krexion"; ValueData: """{app}\{#AppExeTray}"""; \
  Tasks: startupTray; Flags: uninsdeletevalue

[Run]
; ─── Persist the license key the user entered in the wizard ────────────
; The license is written to %PROGRAMDATA%\Krexion\license-key.txt so the
; backend reads it via LICENSE_KEY_FILE env var. Customer never has to
; copy the key to .env manually — installer handles it.
Filename: "{cmd}"; \
  Parameters: "/C echo {code:GetLicenseKey} > ""{commonappdata}\Krexion\license-key.txt"""; \
  Flags: runhidden; StatusMsg: "Saving license key..."; \
  Check: HasLicenseKey

; ─── Install + start Krexion Database service ──────────────────────────
Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "install KrexionDatabase ""{app}\database\bin\mongod.exe"" --dbpath ""{app}\data\db"" --port 27017 --bind_ip 127.0.0.1 --quiet"; \
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

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "set KrexionBackend AppEnvironmentExtra MONGO_URL=mongodb://127.0.0.1:27017 DB_NAME=krexion KREXION_MODE=native KREXION_BUILD_TYPE=binary PLAYWRIGHT_BROWSERS_PATH={app}\browser-engine STRICT_CLOUD_HEAVY_BLOCK=false LICENSE_KEY_FILE={commonappdata}\Krexion\license-key.txt"; \
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

Filename: "{app}\bin\{#AppExeService}"; \
  Parameters: "start KrexionBackend"; \
  Flags: runhidden; StatusMsg: "Starting Krexion Backend..."

; ─── Optional: launch tray app + open dashboard at finish ──────────────
Filename: "{app}\{#AppExeTray}"; Flags: nowait postinstall skipifsilent skipifsourcedoesntexist; \
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
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{commonappdata}\Krexion"

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
  // Future hardening hook — Windows version / RAM checks could go here.
  Result := True;
end;
