@echo off
REM ╔══════════════════════════════════════════════════════════════════╗
REM ║                                                                  ║
REM ║         R E A L F L O W   —   S E T U P   W I Z A R D            ║
REM ║                                                                  ║
REM ║  Just double-click this file.                                    ║
REM ║                                                                  ║
REM ║  A wizard window opens with one big "INSTALL" button.            ║
REM ║  Click it once.  Sit back.  Watch the progress bar.              ║
REM ║                                                                  ║
REM ║  No commands. No technical knowledge. No questions.              ║
REM ║                                                                  ║
REM ╚══════════════════════════════════════════════════════════════════╝

setlocal

REM ─── Auto-elevate to Administrator ─────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

title RealFlow Setup
cd /d "%~dp0"

REM ─── Launch the WinForms wizard ─────────────────────────────────
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0setup-engine.ps1"

endlocal
