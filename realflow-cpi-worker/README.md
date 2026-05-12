# RealFlow CPI Worker

Polls the RealFlow backend (`api.realflow.online`) for queued install attempts
and executes them on locally-attached Android phones, Genymotion emulators,
and iPhones (via libimobiledevice + WebDriverAgent on Windows).

Runs on the user's home PC alongside the existing `realflow-backend` Docker stack.

## Quick start (Windows 11)

1. Install dependencies:
   ```powershell
   # Run as Administrator
   .\deployment\cpi\REALFLOW-CPI-SETUP.ps1
   ```

2. Copy `config.example.yaml` → `config.yaml` and edit:
   - `api.base_url` = your `https://api.realflow.online`
   - `api.token`    = JWT from RealFlow web (Profile → Copy Token)

3. Start:
   ```powershell
   .\deployment\cpi\REALFLOW-CPI-WORKER-START.bat
   ```

4. (Optional) Install as Windows service so it auto-starts on boot:
   ```powershell
   .\deployment\cpi\INSTALL-WORKER-AS-SERVICE.ps1
   ```

## Architecture

```
┌─ orchestrator ─┐   ┌─ android_engine ─┐
│  poll backend  │ → │  adb + Magisk    │ → Real Android phone / LDPlayer / Genymotion
│  claim job     │   │  + Frida hooks   │
└────────────────┘   └──────────────────┘
        │
        │            ┌─ ios_engine ─────┐
        └──────────→ │  libimobiledevice│ → iPhone via USB
                     │  + WDA + tidevice│
                     └──────────────────┘
```

## Anti-detect features (Android)

- Per-install GAID, Android ID, build fingerprint randomization
- Magisk Props Config (when root available)
- Frida hooks: sensor noise, battery curve, locale override
- HTTP proxy via Proxy Jet (per-install rotation)
- Locale + timezone matched to proxy geo
- Realistic behavior simulation: random taps/scrolls/swipes

## Anti-detect features (iOS — limited without jailbreak)

- Locale + timezone override via libimobiledevice
- Per-install Apple ID rotation pool
- Behavior simulation via WebDriverAgent
- Battery / screen brightness randomization

## Operating modes

- **Connected**: workers poll cloud backend, fully cloud-controlled
- **Disconnected**: workers run last-cached job (rarely used)

The worker is stateless; safe to restart anytime.
