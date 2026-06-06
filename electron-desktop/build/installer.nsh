; ──────────────────────────────────────────────────────────────────────────
; Krexion Desktop — NSIS custom hooks (electron-builder)
; ──────────────────────────────────────────────────────────────────────────
; Adds Windows Firewall exceptions for the bundled MongoDB and Python so
; the embedded backend can bind to 127.0.0.1 without a UAC firewall popup.
; ──────────────────────────────────────────────────────────────────────────

!macro customInstall
  ; Always allow loopback — no inbound public exposure.
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="Krexion Desktop"'
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="Krexion Desktop" dir=in action=allow protocol=TCP localport=27117,8088 remoteip=127.0.0.1 profile=any'
!macroend

!macro customUnInstall
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="Krexion Desktop"'
!macroend
