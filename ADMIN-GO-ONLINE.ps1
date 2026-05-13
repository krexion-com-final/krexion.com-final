# ============================================================
#  RealFlow ADMIN GO-ONLINE  -  ADMIN ONLY
# ============================================================
#  Makes YOUR (admin's) RealFlow accessible from anywhere via
#  a public HTTPS URL, with deep-link to /admin-login.
#
#  Customers do NOT need this file. They use GO-ONLINE.bat.
#
#  This file:
#    - Verifies your RealFlow is running locally
#    - Reads YOUR admin credentials from .env
#    - Starts a Cloudflare Quick Tunnel
#    - Opens a control-panel-style popup with everything you need:
#         - Direct link to /admin-login
#         - Admin email + password ready to copy
#         - QR code so you can scan with phone
#         - WhatsApp share for self
# ============================================================

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"

$ScriptDir       = Split-Path -Parent $MyInvocation.MyCommand.Path
$CloudflaredExe  = Join-Path $ScriptDir "cloudflared.exe"
$CloudflaredUrl  = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
$LocalAppUrl     = "http://localhost:3000"
$AdminPath       = "/admin-login"

function Write-Big {
    param([string]$Text, [string]$Color = "Magenta")
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor $Color
    Write-Host "  $Text" -ForegroundColor $Color
    Write-Host "============================================================" -ForegroundColor $Color
    Write-Host ""
}

function Show-Error {
    param([string]$Title, [string]$Detail, [string]$Fix)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  $Title" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    if ($Detail) { Write-Host "  $Detail" -ForegroundColor Yellow; Write-Host "" }
    if ($Fix)    { Write-Host "  WHAT TO DO:" -ForegroundColor Cyan; Write-Host "  $Fix" -ForegroundColor White; Write-Host "" }
    Read-Host "  Press ENTER to close"
    exit 1
}

# ============================================================
#  Read admin credentials from .env
# ============================================================
function Get-EnvValue {
    param([string]$Key)
    # Look for .env in script dir first, then C:\realflow\.env, then /app/backend/.env
    $candidates = @(
        (Join-Path $ScriptDir ".env"),
        "C:\realflow\.env",
        (Join-Path $ScriptDir "backend\.env")
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) {
            $line = Get-Content $p | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -First 1
            if ($line) {
                $val = $line -replace "^\s*$Key\s*=\s*", ""
                $val = $val.Trim().Trim('"').Trim("'")
                return $val
            }
        }
    }
    return $null
}

$adminEmail = Get-EnvValue "ADMIN_EMAIL"
$adminPass  = Get-EnvValue "ADMIN_PASSWORD"
if (-not $adminEmail) { $adminEmail = "admin@realflow.local" }

# ============================================================
#  Step 1 -- Verify RealFlow is running
# ============================================================
Clear-Host
Write-Big "ADMIN GO-ONLINE -- Step 1 of 3" "Magenta"
Write-Host "  Checking your admin server is running..." -ForegroundColor White

$realflowUp = $false
try {
    $r = Invoke-WebRequest $LocalAppUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    if ($r.StatusCode -eq 200) { $realflowUp = $true }
} catch {}

if (-not $realflowUp) {
    Show-Error `
        "RealFlow is NOT running on this PC" `
        "Could not reach $LocalAppUrl" `
        "1. Open Docker Desktop, wait for whale icon to be steady`r`n  2. Open Command Prompt -> cd C:\realflow -> docker compose up -d`r`n  3. Wait 30 sec`r`n  4. Run ADMIN-GO-ONLINE.bat again"
}
Write-Host "  OK -- admin server is running at $LocalAppUrl" -ForegroundColor Green

# ============================================================
#  Step 2 -- cloudflared.exe
# ============================================================
Write-Big "Step 2 of 3 -- Tunnel software" "Magenta"

if (-not (Test-Path $CloudflaredExe)) {
    Write-Host "  Downloading cloudflared.exe (~25 MB, one-time)..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri $CloudflaredUrl -OutFile $CloudflaredExe -UseBasicParsing -TimeoutSec 600
        Write-Host "  Downloaded" -ForegroundColor Green
    } catch {
        Show-Error "Could not download cloudflared.exe" $_.Exception.Message `
            "Check internet. Or manually download from: $CloudflaredUrl -> save as $CloudflaredExe"
    }
} else {
    Write-Host "  cloudflared.exe ready" -ForegroundColor Green
}

# ============================================================
#  Step 3 -- Start tunnel
# ============================================================
Write-Big "Step 3 of 3 -- Opening admin tunnel" "Magenta"

Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 1

$tunnelLog = Join-Path $env:TEMP "realflow-admin-tunnel.log"
if (Test-Path $tunnelLog) { Remove-Item $tunnelLog -Force }

$proc = Start-Process -FilePath $CloudflaredExe `
    -ArgumentList "tunnel","--url",$LocalAppUrl,"--no-autoupdate","--logfile",$tunnelLog `
    -PassThru -WindowStyle Hidden

if (-not $proc -or $proc.HasExited) {
    Show-Error "cloudflared.exe failed to start" "" "Run ADMIN-GO-ONLINE.bat as Administrator"
}

Write-Host "  Connecting to Cloudflare..." -ForegroundColor White
$publicBase = $null
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep 1
    if (Test-Path $tunnelLog) {
        $content = Get-Content $tunnelLog -Raw -ErrorAction SilentlyContinue
        if ($content -match "https://([a-z0-9-]+)\.trycloudflare\.com") {
            $publicBase = "https://" + $Matches[1] + ".trycloudflare.com"
            break
        }
    }
    if ($i % 5 -eq 0) { Write-Host "    still connecting ... ($i sec)" -ForegroundColor Gray }
    if ($proc.HasExited) {
        Show-Error "cloudflared exited unexpectedly" "" "Try again. Check internet."
    }
}

if (-not $publicBase) {
    try { $proc | Stop-Process -Force } catch {}
    Show-Error "Could not get a tunnel URL from Cloudflare after 90 seconds" "" `
        "Try a different network / hotspot."
}

# Deep-link to admin
$adminUrl  = $publicBase + $AdminPath

# ============================================================
#  Build pretty admin control-panel HTML page
# ============================================================
$qrApi  = "https://api.qrserver.com/v1/create-qr-code/?size=380x380&color=4f46e5&data=" + [uri]::EscapeDataString($adminUrl)
$waText = [uri]::EscapeDataString("RealFlow admin panel: $adminUrl")
$waUrl  = "https://wa.me/?text=$waText"

$passHtml = if ($adminPass) { $adminPass } else { "(check C:\realflow\.env file)" }

$htmlFile = Join-Path $env:TEMP "realflow-admin-online.html"
$htmlContent = @"
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>RealFlow Admin -- ONLINE</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin:0; min-height:100vh;
  font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:
    radial-gradient(ellipse at top, #312e81 0%, transparent 40%),
    radial-gradient(ellipse at bottom, #831843 0%, transparent 40%),
    #0a0a0f;
  color: #fff;
  display:flex; align-items:center; justify-content:center; padding:24px;
}
.card {
  max-width:780px; width:100%;
  background: rgba(20,16,40,0.7);
  border:1px solid rgba(168,85,247,0.3);
  border-radius:24px; padding:44px 40px;
  backdrop-filter: blur(24px);
  box-shadow: 0 20px 80px rgba(168,85,247,0.25);
}
.badge {
  display:inline-flex; align-items:center; gap:8px;
  background: linear-gradient(135deg, #a855f7, #ec4899);
  color:#fff;
  padding:7px 16px; border-radius:999px;
  font-size:12px; font-weight:800; letter-spacing:1px;
  margin-bottom:24px;
}
.badge::before {
  content:''; width:8px; height:8px; border-radius:50%;
  background:#fff; animation: pulse 1.5s infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
h1 { margin:0 0 6px; font-size:36px; font-weight:800; letter-spacing:-0.5px;
     background: linear-gradient(135deg, #fff, #c4b5fd);
     -webkit-background-clip: text; background-clip: text;
     -webkit-text-fill-color: transparent;
}
.sub { color:#a3a3c2; font-size:15px; margin-bottom:32px; }

.urlbox {
  background: linear-gradient(135deg, rgba(168,85,247,0.15), rgba(236,72,153,0.1));
  border:2px solid #a855f7; border-radius:14px;
  padding:18px 20px; font-family:'Consolas','SF Mono',monospace;
  font-size:16px; word-break:break-all;
  display:flex; align-items:center; justify-content:space-between; gap:12px;
  margin-bottom:18px;
}
.urlbox a { color:#c4b5fd; text-decoration:none; flex:1; }
.urlbox a:hover { color:#fff; text-decoration:underline; }
.copybtn {
  background: linear-gradient(135deg, #a855f7, #ec4899);
  color:#fff; border:0; padding:10px 18px;
  border-radius:10px; font-weight:700; cursor:pointer;
  font-size:14px; white-space:nowrap;
}
.copybtn:hover { transform: translateY(-1px); }
.copybtn.ok { background:#10b981; }

.creds {
  background: rgba(0,0,0,0.4);
  border:1px solid rgba(255,255,255,0.1);
  border-radius:14px; padding:20px 22px;
  margin-bottom:24px;
}
.creds-title { font-size:11px; letter-spacing:1px; color:#a855f7; font-weight:800; margin-bottom:10px; }
.cred-row { display:flex; align-items:center; gap:12px; margin:8px 0; font-family:'Consolas',monospace; }
.cred-label { color:#a3a3c2; min-width:90px; font-size:13px; }
.cred-val { flex:1; color:#fff; font-size:15px; word-break:break-all; }
.cred-copy {
  background:rgba(168,85,247,0.2); color:#c4b5fd; border:0;
  padding:5px 12px; border-radius:8px; font-size:12px; cursor:pointer;
}
.cred-copy.ok { background:#10b981; color:#fff; }

.row { display:flex; gap:20px; align-items:center; flex-wrap:wrap; }
.qrwrap {
  background:#fff; padding:14px; border-radius:14px;
  display:inline-block;
}
.qrwrap img { display:block; width:200px; height:200px; }
.right { flex:1; min-width:240px; }
.action {
  display:inline-flex; align-items:center; gap:8px;
  background: linear-gradient(135deg, #a855f7, #ec4899);
  color:#fff; padding:14px 22px;
  border-radius:12px; font-weight:700; font-size:15px;
  text-decoration:none; margin:6px 8px 6px 0;
}
.action:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(168,85,247,0.4); }
.action.alt {
  background: rgba(255,255,255,0.08);
  border:1px solid rgba(255,255,255,0.15);
}
.action.alt:hover { background: rgba(255,255,255,0.14); }

.warn {
  margin-top:30px; padding:16px 18px; border-left:4px solid #ec4899;
  background:rgba(236,72,153,0.08); border-radius:8px;
  font-size:13px; color:#fbcfe8;
}
.tag { color:#c4b5fd; font-weight:700; }

@media (max-width:560px) {
  body { padding:14px; }
  .card { padding:28px 22px; }
  h1 { font-size:26px; }
  .urlbox { font-size:13px; padding:14px; }
  .qrwrap img { width:160px; height:160px; }
  .cred-label { min-width:70px; }
}
</style>
</head>
<body>
<div class="card">
  <div class="badge">ADMIN PANEL -- LIVE</div>
  <h1>Your admin server is online</h1>
  <p class="sub">Mobile, laptop, anywhere -- log in and manage your customers, licenses, settings.</p>

  <div class="urlbox">
    <a href="$adminUrl" target="_blank" id="theurl">$adminUrl</a>
    <button class="copybtn" id="copybtn">Copy</button>
  </div>

  <div class="creds">
    <div class="creds-title">YOUR ADMIN CREDENTIALS</div>
    <div class="cred-row">
      <span class="cred-label">Email:</span>
      <span class="cred-val" id="emailVal">$adminEmail</span>
      <button class="cred-copy" id="emailCopy">Copy</button>
    </div>
    <div class="cred-row">
      <span class="cred-label">Password:</span>
      <span class="cred-val" id="passVal">$passHtml</span>
      <button class="cred-copy" id="passCopy">Copy</button>
    </div>
  </div>

  <div class="row">
    <div class="qrwrap">
      <img src="$qrApi" alt="QR code">
    </div>
    <div class="right">
      <a class="action" href="$adminUrl" target="_blank">Open Admin Panel &rarr;</a><br>
      <a class="action alt" href="$waUrl" target="_blank">Send to my WhatsApp</a>
      <p style="color:#a3a3c2; font-size:13px; margin-top:14px; line-height:1.6;">
        <span class="tag">Tip:</span> Scan QR with mobile camera to open admin panel on phone.
      </p>
    </div>
  </div>

  <div class="warn">
    <strong>This is YOUR control panel</strong> -- keep this admin URL private.
    Close the console window on your PC to take admin offline.
    Customers using their own RealFlow installs are NOT affected -- their apps
    keep running normally on their own PCs.
  </div>
</div>

<script>
function bindCopy(btnId, valId) {
  const btn = document.getElementById(btnId);
  const val = document.getElementById(valId);
  btn.onclick = async () => {
    try {
      await navigator.clipboard.writeText(val.textContent.trim());
      const old = btn.textContent;
      btn.textContent = 'Copied!';
      btn.classList.add('ok');
      setTimeout(() => { btn.textContent = old; btn.classList.remove('ok'); }, 1600);
    } catch(e) {
      prompt('Copy:', val.textContent.trim());
    }
  };
}
bindCopy('copybtn','theurl');
bindCopy('emailCopy','emailVal');
bindCopy('passCopy','passVal');
</script>
</body>
</html>
"@

Set-Content -Path $htmlFile -Value $htmlContent -Encoding UTF8
Start-Process $htmlFile

# ============================================================
#  Console status display
# ============================================================
Clear-Host
Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "                                                            " -ForegroundColor Magenta
Write-Host "         REALFLOW ADMIN -- ONLINE NOW                       " -ForegroundColor Magenta
Write-Host "                                                            " -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  YOUR ADMIN URL (bookmark on phone):" -ForegroundColor White
Write-Host "    $adminUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "  YOUR LOGIN:" -ForegroundColor White
Write-Host "    Email    : $adminEmail" -ForegroundColor Yellow
if ($adminPass) {
    Write-Host "    Password : $adminPass" -ForegroundColor Yellow
} else {
    Write-Host "    Password : (check C:\realflow\.env -> ADMIN_PASSWORD)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Status of your business:" -ForegroundColor White
Write-Host "    - Customers using their own RealFlow installs: UNAFFECTED" -ForegroundColor Green
Write-Host "    - Their apps keep running on their own PCs" -ForegroundColor Green
Write-Host "    - Closing this window only affects YOUR admin access" -ForegroundColor Green
Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  IMPORTANT:" -ForegroundColor Yellow
Write-Host "    - Keep this URL PRIVATE (it's your admin access)" -ForegroundColor Yellow
Write-Host "    - URL is TEMPORARY (changes each time you start)" -ForegroundColor Yellow
Write-Host "    - Tunnel works only while this window is OPEN" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  To STOP: Close this window or press Ctrl + C" -ForegroundColor Gray
Write-Host ""

# Keep alive
try {
    while (-not $proc.HasExited) {
        Start-Sleep 5
    }
    Write-Host ""
    Write-Host "  Tunnel exited unexpectedly." -ForegroundColor Yellow
} finally {
    try { $proc | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}
    Write-Host ""
    Write-Host "  Admin panel is now OFFLINE (customers UNAFFECTED)." -ForegroundColor Red
    Start-Sleep 3
}
