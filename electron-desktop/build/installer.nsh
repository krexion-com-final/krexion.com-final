; ──────────────────────────────────────────────────────────────────────────
; Krexion Desktop — NSIS custom hooks (electron-builder)
; ──────────────────────────────────────────────────────────────────────────
; This file is included by electron-builder's NSIS template via the
; `nsis.include: build/installer.nsh` setting in electron-builder.yml.
; It adds four behaviours on top of the default electron-builder installer:
;
;   1. Windows Firewall: allows the bundled MongoDB (127.0.0.1:27117) and
;      Python backend (127.0.0.1:8088) to bind their loopback ports without
;      tripping the public firewall (loopback-only rule, no inbound public).
;
;   2. Auto-append the product name to the chosen install directory. The
;      stock electron-builder Browse dialog lets the customer pick e.g.
;      "D:\" and then drops Krexion's files directly into the drive root
;      — which is confusing and crashes if D:\ is not writable for non-
;      admin users. We hook the directory page LEAVE callback so picking
;      "D:\" silently becomes "D:\Krexion Desktop\" before installation
;      starts.  Matches the behaviour customers expect from every other
;      Windows installer.
;
;   3. Pre-flight free-space check (TEMP drive) at the very start of the
;      installer. Krexion Desktop's NSIS bundle unpacks an ~3 GB 7-Zip
;      archive into %TEMP% before copying anything to the install folder,
;      so a near-full system drive produces the cryptic NSIS error:
;          "Extract: error writing to file ...\Temp\....tmp\app-64.7z"
;      We replace that with a clear, actionable message BEFORE any UI is
;      shown — customer immediately knows to free up C: space.
;
;   4. Pre-flight free-space check (install drive) on the directory page
;      leave — catches the case where TEMP and install dir are on
;      different drives.
; ──────────────────────────────────────────────────────────────────────────

!include "FileFunc.nsh"
!include "LogicLib.nsh"

; Approximate uncompressed size required, in MB. Slightly conservative —
; current build is ~2.9 GB on disk; we ask for 3200 MB to leave headroom
; for the .7z extraction and the final copy.
!define KREXION_REQUIRED_MB 3200

; ── customHeader ───────────────────────────────────────────────────────────
; Inserted at the very top of the installer template (before MUI page
; macros), so any `!define` here is picked up by the subsequent
; `!insertmacro MUI_PAGE_DIRECTORY`.
!macro customHeader
  !define MUI_PAGE_CUSTOMFUNCTION_LEAVE krexionDirectoryPageLeave
!macroend

; ── customInit ─────────────────────────────────────────────────────────────
; Runs before any UI is shown. Checks the TEMP drive for free space.
!macro customInit
  Push $0
  Push $1

  ; $TEMP is something like C:\Users\X\AppData\Local\Temp. We need free
  ; space on its DRIVE for the .7z extraction.
  ${GetRoot} "$TEMP" $0
  ${DriveSpace} "$0\" "/D=F /S=M" $1

  ${If} $1 < ${KREXION_REQUIRED_MB}
    MessageBox MB_ICONSTOP|MB_OK \
      "Not enough free space on your $0 drive to install Krexion Desktop.$\r$\n\
$\r$\n\
Krexion Desktop needs about ${KREXION_REQUIRED_MB} MB of TEMPORARY space on $0 (for unpacking) and roughly the same amount on the drive you choose to install onto.$\r$\n\
$\r$\n\
Currently available on $0: $1 MB$\r$\n\
Required (temporary):      ${KREXION_REQUIRED_MB} MB$\r$\n\
$\r$\n\
Please free up space on $0 (empty Recycle Bin, clean Downloads / Temp folder, uninstall unused programs) and run the installer again."
    Pop $1
    Pop $0
    Abort
  ${EndIf}

  Pop $1
  Pop $0
!macroend

; ── customInstall ──────────────────────────────────────────────────────────
; Allow MongoDB / backend to bind 127.0.0.1 ports without a UAC popup.
!macro customInstall
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="Krexion Desktop"'
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="Krexion Desktop" dir=in action=allow protocol=TCP localport=27117,8088 remoteip=127.0.0.1 profile=any'
!macroend

!macro customUnInstall
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="Krexion Desktop"'
!macroend

; ── Directory-page LEAVE callback ──────────────────────────────────────────
; Called once when the user clicks "Install" on the "Choose Install Location"
; page. We:
;   (a) ensure the chosen path ends with "\Krexion Desktop" so picking a
;       drive root becomes "<drive>:\Krexion Desktop\";
;   (b) re-check free space on the chosen DESTINATION drive (could be
;       different from TEMP drive — e.g. TEMP on C:, install on D:).
;
; Defined at script-top-level so it's available when the customHeader macro
; references it via !define MUI_PAGE_CUSTOMFUNCTION_LEAVE.
Function krexionDirectoryPageLeave
  Push $0
  Push $1
  Push $2
  Push $3

  ; ── (a) auto-append product name ────────────────────────────────────────
  StrLen $0 "${PRODUCT_NAME}"        ; length of "Krexion Desktop"
  StrCpy $1 "$INSTDIR" "" -$0        ; last $0 chars of $INSTDIR

  ${If} $1 != "${PRODUCT_NAME}"
    ; Trim a single trailing backslash if present so we never produce
    ; "X:\\Krexion Desktop".
    StrCpy $2 "$INSTDIR" "" -1
    ${If} $2 == "\"
      StrCpy $INSTDIR "$INSTDIR${PRODUCT_NAME}"
    ${Else}
      StrCpy $INSTDIR "$INSTDIR\${PRODUCT_NAME}"
    ${EndIf}
  ${EndIf}

  ; ── (b) free-space check on install drive ────────────────────────────────
  ${GetRoot} "$INSTDIR" $0
  ${DriveSpace} "$0\" "/D=F /S=M" $1
  ${If} $1 < ${KREXION_REQUIRED_MB}
    MessageBox MB_ICONSTOP|MB_OK \
      "Not enough free space on $0 to install Krexion Desktop.$\r$\n\
$\r$\n\
This drive currently has $1 MB free, but Krexion Desktop needs about ${KREXION_REQUIRED_MB} MB on the install drive.$\r$\n\
$\r$\n\
Please pick a drive with more free space, or free up space on $0 and try again."
    ; Abort the page-leave: stays on the directory selection page so the
    ; user can pick a different folder/drive without restarting the
    ; installer.
    Pop $3
    Pop $2
    Pop $1
    Pop $0
    Abort
  ${EndIf}

  Pop $3
  Pop $2
  Pop $1
  Pop $0
FunctionEnd
