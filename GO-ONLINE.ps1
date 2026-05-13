# ============================================================
#  RealFlow GO ONLINE  -  Quick Tunnel via Cloudflare
# ============================================================
#  Makes your local RealFlow accessible from anywhere in the
#  world via a public HTTPS URL.
#
#  How it works:
#    1. Downloads cloudflared.exe (one-time, ~25 MB)
#    2. Starts a "Quick Tunnel" -> Cloudflare gives a free URL
#    3. Shows that URL + QR code in a popup window
#    4. Tunnel runs as long as this window is open
#    5. Close the window -> app is offline again
#
#  Cost: FREE (forever)
#  Signup: NONE
#  Domain: NOT needed
# ============================================================

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"

$ScriptDir       = Split-Path -Parent $MyInvocation.MyCommand.Path
$CloudflaredExe  = Join-Path $ScriptDir "cloudflared.exe"
$CloudflaredUrl  = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
$LocalAppUrl     = "http://localhost:3000"

function Write-Big {
    param([string]$Text, [string]$Color = "Cyan")
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
#  Step 1 -- Verify RealFlow is running locally
# ============================================================
Clear-Host
Write-Big "RealFlow GO ONLINE -- Step 1 of 3"
Write-Host "  Checking that RealFlow is running on this PC..." -ForegroundColor White

$realflowUp = $false
try {
    $r = Invoke-WebRequest $LocalAppUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    if ($r.StatusCode -eq 200) { $realflowUp = $true }
} catch {}

if (-not $realflowUp) {
    Show-Error `
        "RealFlow is NOT running on this PC" `
        "Could not reach $LocalAppUrl" `
        "1. Open Docker Desktop -- wait until the whale icon stops animating`r`n  2. Open Command Prompt -> cd C:\realflow -> docker compose up -d`r`n  3. Wait 30 seconds`r`n  4. Double-click GO-ONLINE.bat again"
}
Write-Host "  OK -- RealFlow is running locally at $LocalAppUrl" -ForegroundColor Green
Start-Sleep -Seconds 1

# ============================================================
#  Step 2 -- Ensure cloudflared.exe is present
# ============================================================
Write-Big "Step 2 of 3 -- Setting up tunnel software"

if (-not (Test-Path $CloudflaredExe)) {
    Write-Host "  cloudflared.exe not found -- downloading from Cloudflare (~25 MB)..." -ForegroundColor Yellow
    Write-Host "  This is a ONE-TIME download." -ForegroundColor Gray
    Write-Host ""
    try {
        Invoke-WebRequest -Uri $CloudflaredUrl -OutFile $CloudflaredExe -UseBasicParsing -TimeoutSec 600
        Write-Host "  Downloaded ($([math]::Round((Get-Item $CloudflaredExe).Length/1MB,1)) MB)" -ForegroundColor Green
    } catch {
        Show-Error `
            "Could not download cloudflared.exe" `
            $_.Exception.Message `
            "1. Check your internet connection`r`n  2. Manually download from: $CloudflaredUrl`r`n  3. Save the file as: $CloudflaredExe`r`n  4. Run GO-ONLINE.bat again"
    }
} else {
    Write-Host "  cloudflared.exe is already present" -ForegroundColor Green
}
Start-Sleep -Seconds 1

# ============================================================
#  Step 3 -- Start the tunnel and capture the public URL
# ============================================================
Write-Big "Step 3 of 3 -- Starting public tunnel"
Write-Host "  Connecting to Cloudflare..." -ForegroundColor White
Write-Host "  (This takes 10-30 seconds.)" -ForegroundColor Gray
Write-Host ""

# Kill any previous cloudflared.exe so we don't have duplicates
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Start cloudflared as a background process, redirect stdout+stderr to a temp file
$tunnelLog = Join-Path $env:TEMP "realflow-tunnel.log"
if (Test-Path $tunnelLog) { Remove-Item $tunnelLog -Force }

$proc = Start-Process -FilePath $CloudflaredExe `
    -ArgumentList "tunnel","--url",$LocalAppUrl,"--no-autoupdate","--logfile",$tunnelLog `
    -PassThru -WindowStyle Hidden

if (-not $proc -or $proc.HasExited) {
    Show-Error "Could not start cloudflared.exe" "" "Try running GO-ONLINE.bat as Administrator"
}

# Poll the log for the trycloudflare.com URL (max 90 sec)
$publicUrl = $null
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $tunnelLog) {
        $content = Get-Content $tunnelLog -Raw -ErrorAction SilentlyContinue
        if ($content -match "https://([a-z0-9-]+)\.trycloudflare\.com") {
            $publicUrl = "https://" + $Matches[1] + ".trycloudflare.com"
            break
        }
    }
    if ($i % 5 -eq 0) {
        Write-Host "    still connecting ... ($i sec)" -ForegroundColor Gray
    }
    if ($proc.HasExited) {
        Show-Error `
            "cloudflared exited unexpectedly" `
            (Get-Content $tunnelLog -Tail 5 -ErrorAction SilentlyContinue | Out-String) `
            "Check your internet. Run GO-ONLINE.bat again."
    }
}

if (-not $publicUrl) {
    try { $proc | Stop-Process -Force } catch {}
    Show-Error `
        "Could not get a public URL from Cloudflare after 90 seconds" `
        "" `
        "1. Check your internet (some networks block Cloudflare)`r`n  2. Try a different network or hotspot`r`n  3. Run GO-ONLINE.bat again"
}

# ============================================================
#  Show beautiful HTML page with URL + QR code
# ============================================================
$qrApi = "https://api.qrserver.com/v1/create-qr-code/?size=380x380&data=" + [uri]::EscapeDataString($publicUrl)
$waText = [uri]::EscapeDataString("My RealFlow is online! Open this link: $publicUrl")
$waUrl  = "https://wa.me/?text=$waText"

$htmlFile = Join-Path $env:TEMP "realflow-online.html"
$htmlContent = @"
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>RealFlow is Online</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin:0; min-height:100vh;
  font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background: linear-gradient(135deg,#0f172a 0%,#1e3a8a 50%,#0f172a 100%);
  color: #fff;
  display:flex; align-items:center; justify-content:center; padding:24px;
}
.card {
  max-width:720px; width:100%;
  background: rgba(255,255,255,0.06);
  border:1px solid rgba(255,255,255,0.12);
  border-radius:24px; padding:48px 40px;
  backdrop-filter: blur(20px);
  box-shadow: 0 20px 60px rgba(0,0,0,0.4);
}
.badge {
  display:inline-flex; align-items:center; gap:8px;
  background:#10b981; color:#fff;
  padding:6px 14px; border-radius:999px;
  font-size:13px; font-weight:700; letter-spacing:0.5px;
  margin-bottom:24px;
}
.badge::before {
  content:''; width:8px; height:8px; border-radius:50%;
  background:#fff; animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
h1 { margin:0 0 8px; font-size:36px; font-weight:800; letter-spacing:-0.5px; }
.sub { color:#a3b5d1; font-size:15px; margin-bottom:32px; }
.urlbox {
  background:#0b1224; border:2px solid #3b5bf5; border-radius:14px;
  padding:18px 20px; font-family:'Consolas','SF Mono',monospace;
  font-size:18px; word-break:break-all; color:#fff;
  display:flex; align-items:center; justify-content:space-between; gap:12px;
  margin-bottom:24px;
}
.urlbox a { color:#60a5fa; text-decoration:none; flex:1; }
.urlbox a:hover { color:#93c5fd; text-decoration:underline; }
.copybtn {
  background:#3b5bf5; color:#fff; border:0; padding:10px 18px;
  border-radius:10px; font-weight:600; cursor:pointer;
  font-size:14px; white-space:nowrap;
}
.copybtn:hover { background:#5468ff; }
.copybtn.ok { background:#10b981; }
.row { display:flex; gap:20px; align-items:center; flex-wrap:wrap; }
.qrwrap {
  background:#fff; padding:14px; border-radius:14px;
  display:inline-block;
}
.qrwrap img { display:block; width:200px; height:200px; }
.right { flex:1; min-width:240px; }
.action {
  display:inline-flex; align-items:center; gap:8px;
  background:#10b981; color:#fff; padding:14px 22px;
  border-radius:12px; font-weight:700; font-size:16px;
  text-decoration:none; margin:6px 8px 6px 0;
}
.action:hover { background:#0ea771; }
.action.alt { background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.15); }
.action.alt:hover { background:rgba(255,255,255,0.16); }
.warn {
  margin-top:32px; padding:16px 18px; border-left:4px solid #f59e0b;
  background:rgba(245,158,11,0.1); border-radius:8px;
  font-size:14px; color:#fde68a;
}
.tag { color:#60a5fa; font-weight:700; }
@media (max-width:560px) {
  body { padding:14px; }
  .card { padding:28px 22px; }
  h1 { font-size:26px; }
  .urlbox { font-size:13px; padding:14px; }
  .qrwrap img { width:160px; height:160px; }
}
</style>
</head>
<body>
<div class="card">
  <div class="badge">LIVE -- ONLINE NOW</div>
  <h1>Your RealFlow is online</h1>
  <p class="sub">Open this URL on your mobile, laptop, tablet -- anywhere in the world.</p>

  <div class="urlbox">
    <a href="$publicUrl" target="_blank" id="theurl">$publicUrl</a>
    <button class="copybtn" id="copybtn">Copy</button>
  </div>

  <div class="row">
    <div class="qrwrap">
      <img src="$qrApi" alt="QR code">
    </div>
    <div class="right">
      <a class="action" href="$publicUrl" target="_blank">Open Now &rarr;</a><br>
      <a class="action alt" href="$waUrl" target="_blank">Share on WhatsApp</a>
      <p style="color:#cbd5e1; font-size:14px; margin-top:18px; line-height:1.6;">
        <span class="tag">Tip:</span> Scan the QR code with your mobile camera to open this URL on your phone instantly.
      </p>
    </div>
  </div>

  <div class="warn">
    <strong>Keep this window open</strong> -- the tunnel runs as long as the
    GO-ONLINE window stays open on your PC. Close that window and your app
    goes offline. Re-run GO-ONLINE.bat to get back online (new URL each time).
  </div>
</div>

<script>
const btn = document.getElementById('copybtn');
const url = '$publicUrl';
btn.onclick = async () => {
  try {
    await navigator.clipboard.writeText(url);
    btn.textContent = 'Copied!';
    btn.classList.add('ok');
    setTimeout(() => { btn.textContent='Copy'; btn.classList.remove('ok'); }, 1800);
  } catch (e) {
    prompt('Copy this URL:', url);
  }
};
</script>
</body>
</html>
"@

Set-Content -Path $htmlFile -Value $htmlContent -Encoding UTF8

# Open the page in default browser
Start-Process $htmlFile

# ============================================================
#  Console status display (foreground -- closing it kills tunnel)
# ============================================================
Clear-Host
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "                                                            " -ForegroundColor Green
Write-Host "         YOUR REALFLOW IS NOW ONLINE!                       " -ForegroundColor Green
Write-Host "                                                            " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Public URL:" -ForegroundColor White
Write-Host "    $publicUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Open this URL on your mobile / laptop / anywhere." -ForegroundColor White
Write-Host "  (Scan the QR code in the browser window for fast mobile access.)" -ForegroundColor Gray
Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  IMPORTANT:" -ForegroundColor Yellow
Write-Host "    - This URL is TEMPORARY (changes each time you start)" -ForegroundColor Yellow
Write-Host "    - Tunnel stays ON only while this window is OPEN" -ForegroundColor Yellow
Write-Host "    - Close this window to take RealFlow offline" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  To STOP: Close this window (Alt + F4) or Ctrl + C" -ForegroundColor Gray
Write-Host ""
Write-Host "  Tunnel status:" -ForegroundColor White
Write-Host "    cloudflared.exe is running in background (PID $($proc.Id))" -ForegroundColor DarkGray
Write-Host "    Log file: $tunnelLog" -ForegroundColor DarkGray
Write-Host ""

# Keep the window alive until user closes it OR cloudflared crashes
# We register a Ctrl+C handler so we can clean up
try {
    while (-not $proc.HasExited) {
        Start-Sleep -Seconds 5
    }
    Write-Host ""
    Write-Host "  Tunnel ended (cloudflared.exe exited)." -ForegroundColor Yellow
    Write-Host "  Run GO-ONLINE.bat again to reconnect." -ForegroundColor Yellow
} finally {
    try { $proc | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}
    Write-Host ""
    Write-Host "  RealFlow is now OFFLINE." -ForegroundColor Red
    Start-Sleep -Seconds 3
}
