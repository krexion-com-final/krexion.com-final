"""
Krexion — Browser Profile Launcher (LOCAL DESKTOP execution)
==============================================================

Runs ONLY on the customer's local desktop / Electron host process where
Playwright is installed with a real Chromium binary. NOT used on the
cloud VPS (cloud edge just enqueues the bridge job — this file actually
opens the headed browser the customer interacts with).

Execution flow:
  1. sync_client.py pulls a bridge_jobs row with feature="browser-profile/launch"
  2. sync_client.py calls launch_profile_session(...) from THIS module
  3. We start a HEADED Playwright Chromium with the profile's config:
       • user_agent + viewport + device_scale_factor + locale + timezone
       • proxy (manual or ProxyJet-allocated)
       • storage_state (cookies + localStorage from previous sessions)
       • anti-detect script injected via add_init_script (same one RUT uses)
  4. Browser opens to start_url. Customer manually browses.
  5. When the customer closes the LAST page or the browser, we:
       • Export updated storage_state
       • POST to /api/browser-profiles/_bridge/session-update so the
         cloud profile record is updated with new cookies + duration.
  6. Function returns — sync_client marks the bridge job as completed.

This is a fully self-contained module — no FastAPI route. The local
backend invokes it directly via a thin endpoint or via sync_client.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("browser_profile_launcher")

# Track running sessions so the UI / stop endpoint can find them
_RUNNING_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def launch_profile_session(
    profile_config: Dict[str, Any],
    *,
    session_id: str,
    start_url: str,
    on_session_update: Optional[Any] = None,
) -> Dict[str, Any]:
    """Open a HEADED Chromium for manual browsing with all anti-detect
    layers applied. Blocks until the customer closes the browser.

    Args:
        profile_config: Full profile document from MongoDB
        session_id: Unique session id (also used to track stop signals)
        start_url: First URL to navigate to
        on_session_update: Optional async callback to report progress
                           (status, storage_state, duration_sec)

    Returns:
        {"ok": bool, "session_id": ..., "duration_sec": ..., "error": ...}
    """
    # ── 2026-07 (v2.1.59) crash-visibility wrapper ──────────────────────
    # Customer report: Browser Profile "Launch" pressed → card chip
    # stuck on "launching" forever, Chromium never opens. Root cause:
    # every failure path BEFORE the in-body `on_session_update("running")`
    # call (Playwright import error, browser launch crash, context
    # creation OOM, proxy probe explosion, etc.) just `return`ed or
    # raised — and since sync_client fires this function as a
    # `asyncio.create_task(...)`, the exception was silently swallowed
    # by the event loop. The cloud's `_bridge/session-update` endpoint
    # was therefore NEVER notified, so the profile status was wedged
    # at "launching" with no actionable error for the operator.
    #
    # Fix: outer try/except that ALWAYS notifies the cloud with the
    # actual error, plus guaranteed cleanup of `_RUNNING_SESSIONS`.
    profile_id = str(profile_config.get("id") or "")

    async def _notify_error(msg: str) -> None:
        """Best-effort cloud notification so the UI un-sticks from
        'launching' and shows the real reason. Failure here is logged
        but never re-raised — we already have an error to report."""
        logger.warning(f"[profile-launch] session={session_id[:8]} ERROR: {msg}")
        if on_session_update is None:
            return
        try:
            await on_session_update({
                "profile_id": profile_id,
                "session_id": session_id,
                "status": "error",
                "error_message": msg,
            })
        except Exception as _nerr:  # noqa: BLE001
            logger.warning(f"[profile-launch] error notify itself failed: {_nerr}")

    try:
        try:
            from playwright.async_api import async_playwright
        except ImportError as _ie:
            await _notify_error(
                "Playwright is not installed on this host. The Krexion "
                "desktop install should auto-bundle it; please reinstall "
                "or run `python -m playwright install chromium` manually."
            )
            return {"ok": False, "error": f"Playwright not installed: {_ie}"}

        # ── v2.1.59 Pre-flight: Chromium binary readiness check ─────────
        # On a fresh Krexion install the PowerShell installer tries to
        # download the pre-bundled Chromium ZIP from GitHub Releases —
        # when that step is skipped/fails it logs:
        #   "Krexion backend will auto-download Chromium on first launch"
        # The actual download is then kicked off in the backend's
        # startup hook (_ensure_playwright_chromium) and runs for ~60s.
        # If the customer clicks Launch on a Browser Profile DURING that
        # window, Playwright's `chromium.launch()` raises a cryptic
        # "Executable doesn't exist at ..." error. We pre-check the
        # binary HERE and surface a friendly status that the UI can
        # render — auto-triggering the install if it hasn't started yet,
        # so the customer's next click "just works" after ~60-90s.
        try:
            from real_user_traffic import get_engine_status, _ensure_chromium_available  # type: ignore
            engine = get_engine_status()
            estatus = (engine or {}).get("status") or "error"
            if estatus == "ready":
                pass  # All good — proceed to launch
            elif estatus == "installing":
                await _notify_error(
                    "Chromium browser engine is still downloading "
                    "(~150 MB). Please wait ~60 seconds and click "
                    "Launch again."
                )
                return {"ok": False, "session_id": session_id,
                        "error": "chromium_installing"}
            elif estatus == "missing":
                # Kick off the install in the background and tell the
                # operator to retry. We deliberately don't await here —
                # the download takes too long for a synchronous UI click.
                try:
                    asyncio.create_task(_ensure_chromium_available())
                except Exception:  # noqa: BLE001
                    pass
                await _notify_error(
                    "Chromium browser engine is missing — downloading "
                    "it now (~150 MB, takes ~60-90 seconds). Click "
                    "Launch again once this banner clears."
                )
                return {"ok": False, "session_id": session_id,
                        "error": "chromium_missing_install_started"}
            else:
                # 'error' or unknown — fall through to the actual launch
                # so Playwright surfaces its native error (better than
                # blocking on a metadata read glitch).
                logger.warning(
                    f"[profile-launch] chromium engine status='{estatus}' "
                    f"(msg={(engine or {}).get('message','')}); continuing anyway"
                )
        except ImportError:
            # real_user_traffic helper isn't available in this build —
            # not fatal, just skip the pre-check and let Playwright handle it.
            logger.debug("[profile-launch] engine status helper not importable; skipping pre-check")
        except Exception as _ge:  # noqa: BLE001
            logger.debug(f"[profile-launch] chromium pre-check skipped: {_ge}")

        started_at = time.time()
        _RUNNING_SESSIONS[session_id] = {
            "profile_id": profile_id,
            "started_at": started_at,
            "stop_requested": False,
        }

        try:
            return await _launch_profile_session_inner(
                profile_config,
                session_id=session_id,
                start_url=start_url,
                on_session_update=on_session_update,
                async_playwright=async_playwright,
                started_at=started_at,
                profile_id=profile_id,
            )
        except Exception as _inner_err:  # noqa: BLE001
            # Surface launch crash to the cloud + frontend UI
            import traceback as _tb
            tb_short = _tb.format_exc()[:600]
            logger.warning(
                f"[profile-launch] launch crashed: {type(_inner_err).__name__}: "
                f"{_inner_err}\n{tb_short}"
            )
            await _notify_error(
                f"{type(_inner_err).__name__}: {str(_inner_err)[:240]}"
            )
            return {"ok": False, "session_id": session_id, "error": str(_inner_err)}
    finally:
        # ALWAYS reclaim the session slot so a hard-crashing launch
        # doesn't leak _RUNNING_SESSIONS entries forever (used by the
        # /stop endpoint to find the right session).
        _RUNNING_SESSIONS.pop(session_id, None)


async def _launch_profile_session_inner(
    profile_config: Dict[str, Any],
    *,
    session_id: str,
    start_url: str,
    on_session_update: Optional[Any],
    async_playwright: Any,
    started_at: float,
    profile_id: str,
) -> Dict[str, Any]:
    """Real launch flow — kept separate so the outer wrapper can centralise
    crash-notification + cleanup. All previous behaviour preserved."""

    ua = profile_config.get("user_agent") or ""
    viewport = profile_config.get("viewport") or {"width": 1920, "height": 1080}
    is_mobile = bool(profile_config.get("is_mobile"))
    has_touch = bool(profile_config.get("has_touch") or is_mobile)
    dsf = float(profile_config.get("device_scale_factor") or (3.0 if is_mobile else 1.0))
    locale = profile_config.get("locale") or "en-US"
    timezone_id = profile_config.get("timezone") or "America/New_York"
    accept_lang = profile_config.get("accept_language") or f"{locale},en;q=0.9"
    storage_state = profile_config.get("storage_state") or None

    proxy_cfg = profile_config.get("proxy") or {}
    proxy_arg = None
    proxy_diag: Dict[str, Any] = {"requested": False, "server": "", "ok": None, "error": ""}
    if proxy_cfg.get("enabled") and proxy_cfg.get("server"):
        # ── 2026-06 — Normalize the proxy server URL ──────────────
        # Customer report: launching a profile errored with
        # ERR_TIMED_OUT on google.com. Root cause: ProxyJet returned
        # lines parsed correctly but the stored `server` value can
        # arrive WITHOUT an `http://` scheme (e.g. just "host:port")
        # which Chromium silently ignores when handed via the
        # `proxy` launch option. Then the browser falls through to
        # the OS direct connection — which on a locked-down Windows
        # host has no route to google.com and times out.
        # We now normalize to a Chromium-acceptable URL form.
        raw_server = str(proxy_cfg["server"]).strip()
        username = str(proxy_cfg.get("username") or "")
        password = str(proxy_cfg.get("password") or "")

        # 2026-06 (follow-up) — Defensive normalization for LEGACY
        # profiles created before the parser fix in
        # browser_profile_module.py.  Some stored proxies still have
        # the format `http://user:pass@host` (port stripped, creds
        # baked into URL) which Chromium silently defaults to port 80
        # for — causing the customer's "Proxy could not be reached"
        # within 10s on EVERY profile launch.  We rebuild the proxy
        # tuple from whatever shape was saved so old and new
        # profiles BOTH work.
        try:
            from urllib.parse import urlparse, urlunparse
            # 1. Ensure a scheme so urlparse can work.
            if "://" not in raw_server:
                # If creds are embedded without scheme (rare): user:pass@host[:port]
                raw_server = f"http://{raw_server}"
            parsed = urlparse(raw_server)
            host = parsed.hostname or ""
            port = parsed.port  # None when not specified
            # 2. Pull creds out of the URL if Chromium would otherwise
            #    see them inline (it ignores them when the separate
            #    `username`/`password` launch fields are also set, and
            #    sometimes mangles auth when both forms collide).
            if parsed.username and not username:
                username = parsed.username
            if parsed.password and not password:
                password = parsed.password
            # 3. Default port heuristics — the #1 root cause of the
            #    Proxy-could-not-be-reached error.  ProxyJet's gateways
            #    listen on port 1010; everything else gets the
            #    HTTP-proxy default of 8080 only when truly missing.
            if not port:
                lower_host = host.lower()
                if "proxy-jet.io" in lower_host:
                    port = 1010
                elif lower_host.endswith("smartproxy.com") or "smartproxy" in lower_host:
                    port = 7000
                elif "brightdata" in lower_host or "luminati" in lower_host:
                    port = 22225
                else:
                    # Leave port unset — Chromium uses 80 for http://
                    # and 443 for https://.  We can't guess better.
                    pass
            # 4. Rebuild the canonical scheme://host[:port] (no creds in URL).
            scheme = parsed.scheme or "http"
            if scheme not in ("http", "https", "socks5", "socks5h", "socks4"):
                scheme = "http"
            netloc = host if not port else f"{host}:{port}"
            raw_server = urlunparse((scheme, netloc, "", "", "", "")) if host else raw_server
        except Exception as _ne:
            logger.warning(f"[profile-launch] proxy URL normalize failed (using raw): {_ne}")
            if "://" not in raw_server:
                raw_server = f"http://{raw_server}"

        proxy_arg = {"server": raw_server}
        if username:
            proxy_arg["username"] = username
        if password:
            proxy_arg["password"] = password
        proxy_diag["requested"] = True
        proxy_diag["server"] = raw_server

    anti = profile_config.get("anti_detect") or {}
    master = bool(anti.get("master", True))

    async with async_playwright() as p:
        # Browser binary selection — prefer Chrome channel for realism,
        # fall back to bundled Chromium when not installed.
        launch_kwargs: Dict[str, Any] = {
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-default-browser-check",
                "--no-first-run",
                # Make the window non-obvious (no automation infobar)
                "--disable-infobars",
            ],
        }
        if proxy_arg:
            launch_kwargs["proxy"] = proxy_arg

        # Pick channel
        channel: Optional[str] = None
        variant = (anti.get("browser_variant") or "auto").lower()
        if variant in ("chrome", "rotate"):
            channel = "chrome"  # Falls back if not installed
        try:
            browser = await p.chromium.launch(channel=channel, **launch_kwargs) if channel else await p.chromium.launch(**launch_kwargs)
        except Exception:
            # Channel not present → fallback to bundled
            browser = await p.chromium.launch(**launch_kwargs)

        context_kwargs: Dict[str, Any] = {
            "user_agent": ua,
            "viewport": {"width": int(viewport.get("width", 1920)), "height": int(viewport.get("height", 1080))},
            "device_scale_factor": dsf,
            "is_mobile": is_mobile,
            "has_touch": has_touch,
            "locale": locale,
            "timezone_id": timezone_id,
            "extra_http_headers": {"Accept-Language": accept_lang},
        }
        if storage_state and (storage_state.get("cookies") or storage_state.get("origins")):
            context_kwargs["storage_state"] = storage_state

        context = await browser.new_context(**context_kwargs)

        # ── Inject anti-detect script (only when master toggle is ON) ──
        if master:
            try:
                # Reuse RUT's stealth builder so the SAME ~35 JS patches
                # land here. Falls back to a minimal stub if the import
                # ever fails (keeps the launcher usable in isolation).
                from real_user_traffic import _build_stealth_script
                fp = {
                    "viewport": context_kwargs["viewport"],
                    "device_scale_factor": dsf,
                    "is_mobile": is_mobile,
                    "has_touch": has_touch,
                    "os": profile_config.get("os") or ("ios" if is_mobile else "windows"),
                }
                geo = {
                    "locale": locale,
                    "timezone": timezone_id,
                    "accept_language": accept_lang,
                    "lat": 40.7128, "lon": -74.0060,
                }
                stealth_js = _build_stealth_script(fp, geo)
                await context.add_init_script(stealth_js)
            except Exception as e:
                logger.warning(f"anti-detect script injection failed: {e}")
                # Minimal fallback — at least hide webdriver flag
                await context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )

        page = await context.new_page()
        # ── 2026-06 — Proxy health pre-check + clear error diagnostic ──
        # Customer report: profile launch errored with "ERR_TIMED_OUT"
        # on google.com with no clue WHY. Most common root cause is
        # the proxy itself (ProxyJet credentials lapsed, IP allocated
        # to a region that's blocked, port unreachable from the
        # customer's local network, etc.). Rather than silently fail
        # the goto, we probe the proxy with a tiny timeout-bounded
        # HEAD-equivalent (`api.ipify.org`, served by Cloudflare) and
        # surface a meaningful diagnostic page if it fails. The user
        # then sees WHY the browser can't reach the target site and
        # can pick a different proxy / disable it / contact support.
        if proxy_arg is not None:
            try:
                import urllib.parse as _urlparse
                _parsed = _urlparse.urlparse(proxy_arg.get("server") or "")
                # Use Playwright's APIRequestContext (it honours the
                # browser context's proxy automatically). 10-second
                # ceiling — real proxies respond in <2s; anything
                # longer means it's effectively dead for interactive
                # browsing.
                _probe = await context.request.get(
                    "https://api.ipify.org?format=text",
                    timeout=10000,
                )
                _exit_ip = (await _probe.text()).strip()
                if _exit_ip and 7 <= len(_exit_ip) <= 45:
                    proxy_diag["ok"] = True
                    proxy_diag["exit_ip"] = _exit_ip
                    logger.info(
                        f"[profile-launch] proxy OK — exit IP {_exit_ip} "
                        f"via {_parsed.hostname or proxy_arg['server']}"
                    )
                else:
                    proxy_diag["ok"] = False
                    proxy_diag["error"] = f"proxy probe returned non-IP body: {_exit_ip[:80]}"
            except Exception as _pe:
                proxy_diag["ok"] = False
                proxy_diag["error"] = f"{type(_pe).__name__}: {str(_pe)[:200]}"
                logger.warning(
                    f"[profile-launch] proxy health probe failed: {proxy_diag['error']}"
                )

        # If proxy was REQUESTED but FAILED the probe, show a
        # diagnostic landing page INSTEAD of trying to load the real
        # start_url (which would just give ERR_TIMED_OUT). The
        # operator gets:
        #   • clear message about the proxy issue
        #   • the configured server + username (no password)
        #   • a "Continue without proxy" button via JS that just
        #     navigates to the start_url anyway (proxy-less)
        if proxy_diag["requested"] and proxy_diag["ok"] is False:
            try:
                _safe_server = str(proxy_diag.get("server") or "").replace("<", "&lt;").replace(">", "&gt;")
                _safe_err = str(proxy_diag.get("error") or "").replace("<", "&lt;").replace(">", "&gt;")
                _safe_start = str(start_url or "https://www.google.com/").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                _diag_html = (
                    "<!doctype html><html><head><meta charset='utf-8'>"
                    "<title>Krexion — Proxy unreachable</title>"
                    "<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
                    "background:#0b0b10;color:#e4e4e7;margin:0;padding:48px;"
                    "min-height:100vh;box-sizing:border-box}"
                    ".card{max-width:720px;margin:0 auto;background:#18181b;"
                    "border:1px solid #3f3f46;border-radius:12px;padding:32px}"
                    "h1{margin:0 0 8px;font-size:22px;color:#fb7185}"
                    "h2{margin:24px 0 8px;font-size:14px;color:#a1a1aa;font-weight:600;"
                    "text-transform:uppercase;letter-spacing:0.05em}"
                    "code{background:#0a0a0f;border:1px solid #27272a;padding:2px 6px;"
                    "border-radius:4px;font-size:13px;color:#fbbf24;word-break:break-all}"
                    ".btn{display:inline-block;margin-top:24px;padding:10px 20px;"
                    "background:#7c3aed;color:white;border:none;border-radius:6px;"
                    "font-size:14px;cursor:pointer;text-decoration:none}"
                    ".btn:hover{background:#6d28d9}"
                    ".muted{color:#71717a;font-size:13px;line-height:1.6}"
                    "</style></head><body><div class='card'>"
                    "<h1>⚠ Proxy could not be reached</h1>"
                    "<p class='muted'>Krexion tried to route this browser profile through the configured proxy, "
                    "but the connection failed within 10 seconds. The site would otherwise show ERR_TIMED_OUT with no explanation.</p>"
                    "<h2>Proxy server</h2><code>"+_safe_server+"</code>"
                    "<h2>Reason</h2><code>"+_safe_err+"</code>"
                    "<h2>What to try</h2><ul class='muted'>"
                    "<li>Verify your ProxyJet credentials are still active (Settings → ProxyJet)</li>"
                    "<li>Try a different country / state in the profile's proxy section</li>"
                    "<li>Switch to <code>No Proxy</code> if you only need a clean UA / viewport</li>"
                    "<li>Check that the desktop machine's firewall allows outbound HTTPS</li>"
                    "</ul>"
                    "<a class='btn' href='"+_safe_start+"'>Continue without proxy →</a>"
                    "</div></body></html>"
                )
                await page.set_content(_diag_html, timeout=5000)
            except Exception as _de:
                logger.warning(f"[profile-launch] diagnostic page render failed: {_de}")
        else:
            # ── 2026-06 — Robust goto with retry + clear failure UI ──
            # Customer report: "profile launch kr te hein to error
            # ata hai profile proper os ip k hisab se chalti ni hai".
            # Two failure modes seen:
            #   1. The proxy probe passes (api.ipify is fast + Cloudflare
            #      always reachable) but the actual start_url goto times
            #      out — often because residential proxies blacklist
            #      Google's automation patterns OR the user's local DNS
            #      resolver can't see the target host.
            #   2. The probe is run too early; some ProxyJet sticky
            #      sessions take ~2-5s extra to fully provision a fresh
            #      exit IP, so the probe lands on a partially-warm
            #      tunnel that succeeds but the next request stalls.
            # We now do TWO goto attempts with progressively longer
            # timeouts, and if both fail we set a diagnostic page with
            # the actual error + the configured proxy so the operator
            # can SEE what went wrong instead of staring at the generic
            # Chrome "This site can't be reached" screen.
            _goto_err: Optional[str] = None
            _target_url = start_url or "https://www.google.com/"
            for attempt in (1, 2):
                try:
                    _t_goto = 45000 if attempt == 1 else 75000
                    await page.goto(_target_url, timeout=_t_goto, wait_until="domcontentloaded")
                    _goto_err = None
                    break
                except Exception as e:
                    _goto_err = f"attempt {attempt}/2 ({_t_goto/1000:.0f}s): {type(e).__name__}: {str(e)[:160]}"
                    logger.warning(f"start URL goto failed — {_goto_err}")
                    if attempt == 2:
                        break
                    # Brief sleep before retry — gives slow proxies a
                    # chance to settle their tunnel.
                    await asyncio.sleep(2.0)

            if _goto_err is not None:
                # Both attempts failed — show a clear diagnostic page
                # so the user understands what's happening.
                try:
                    _safe_url = str(_target_url).replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                    _safe_err = str(_goto_err).replace("<", "&lt;").replace(">", "&gt;")
                    _safe_proxy = str((proxy_arg or {}).get("server") or "(none configured)").replace("<", "&lt;").replace(">", "&gt;")
                    _exit_ip_html = ""
                    if proxy_diag.get("exit_ip"):
                        _exit_ip_html = f"<h2>Last known proxy exit IP</h2><code>{proxy_diag['exit_ip']}</code>"
                    _diag_html = (
                        "<!doctype html><html><head><meta charset='utf-8'>"
                        "<title>Krexion — Page could not load</title>"
                        "<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
                        "background:#0b0b10;color:#e4e4e7;margin:0;padding:48px;"
                        "min-height:100vh;box-sizing:border-box}"
                        ".card{max-width:760px;margin:0 auto;background:#18181b;"
                        "border:1px solid #3f3f46;border-radius:12px;padding:32px}"
                        "h1{margin:0 0 8px;font-size:22px;color:#fbbf24}"
                        "h2{margin:24px 0 8px;font-size:13px;color:#a1a1aa;font-weight:600;"
                        "text-transform:uppercase;letter-spacing:0.05em}"
                        "code{background:#0a0a0f;border:1px solid #27272a;padding:2px 6px;"
                        "border-radius:4px;font-size:13px;color:#fbbf24;word-break:break-all;display:inline-block}"
                        ".muted{color:#71717a;font-size:13px;line-height:1.6}"
                        ".pill{display:inline-block;padding:3px 8px;background:#7c3aed;color:white;"
                        "border-radius:9999px;font-size:11px;margin-left:6px}"
                        "</style></head><body><div class='card'>"
                        "<h1>⚠ Could not load the start page<span class='pill'>profile is live — you can still type a URL above</span></h1>"
                        "<p class='muted'>The browser launched successfully but the first navigation timed out. "
                        "This usually means the proxy tunnel is alive enough to pass our quick probe but the destination host "
                        "isn't reachable through it (geo-blocked, captcha wall, or proxy DNS issue).</p>"
                        "<h2>Target URL</h2><code>"+_safe_url+"</code>"
                        "<h2>Configured proxy</h2><code>"+_safe_proxy+"</code>"
                        +_exit_ip_html+
                        "<h2>Error</h2><code>"+_safe_err+"</code>"
                        "<h2>Next steps</h2><ul class='muted'>"
                        "<li>You can still TYPE a different URL in the address bar above — the proxy stays active</li>"
                        "<li>If even known-good sites (e.g. <code>example.com</code>) fail, the proxy is broken — pick a different country/state in the profile and relaunch</li>"
                        "<li>If only the target site fails, that host is blocking your proxy's exit IP — try a residential pool</li>"
                        "<li>To browse without the proxy, close this profile and relaunch with proxy disabled</li>"
                        "</ul></div></body></html>"
                    )
                    await page.set_content(_diag_html, timeout=5000)
                except Exception as _de:
                    logger.warning(f"[profile-launch] post-goto diagnostic page render failed: {_de}")

        # Tell cloud the session is now RUNNING
        if on_session_update:
            try:
                await on_session_update({
                    "profile_id": profile_id, "session_id": session_id,
                    "status": "running",
                })
            except Exception:
                pass

        # ── Wait until the customer closes the browser ───────────────
        # We poll instead of using a single await so we can also respond
        # to a programmatic stop request from the cloud /stop endpoint.
        closed_event = asyncio.Event()

        def _on_disconnected():
            closed_event.set()

        browser.on("disconnected", lambda *_: _on_disconnected())

        while not closed_event.is_set():
            try:
                await asyncio.wait_for(closed_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                # Check for external stop signal
                sess = _RUNNING_SESSIONS.get(session_id) or {}
                if sess.get("stop_requested"):
                    try:
                        await context.close()
                    except Exception:
                        pass
                    try:
                        await browser.close()
                    except Exception:
                        pass
                    break

        # ── Save storage_state + push to cloud ────────────────────────
        new_storage: Dict[str, Any] = {}
        try:
            if not browser.is_connected():
                # Browser already closed — can't query storage. Skip.
                pass
            else:
                new_storage = await context.storage_state()
                await context.close()
                await browser.close()
        except Exception as e:
            logger.warning(f"storage_state export failed: {e}")

        duration = round(time.time() - started_at, 1)
        if on_session_update:
            try:
                await on_session_update({
                    "profile_id": profile_id,
                    "session_id": session_id,
                    "status": "closed",
                    "storage_state": new_storage,
                    "duration_sec": duration,
                })
            except Exception as e:
                logger.warning(f"final session update failed: {e}")

        _RUNNING_SESSIONS.pop(session_id, None)
        return {"ok": True, "session_id": session_id, "duration_sec": duration}


def request_stop(session_id: str) -> bool:
    """Mark a running session as stop-requested. Polled by the launch
    loop above; the browser is then closed and storage_state saved.
    """
    sess = _RUNNING_SESSIONS.get(session_id)
    if not sess:
        return False
    sess["stop_requested"] = True
    return True


def list_running() -> Dict[str, Dict[str, Any]]:
    """Return the dict of currently-running sessions (for debug / UI)."""
    return dict(_RUNNING_SESSIONS)


__all__ = ["launch_profile_session", "request_stop", "list_running"]
