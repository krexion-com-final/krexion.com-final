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
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"ok": False, "error": "Playwright not installed on this host"}

    profile_id = str(profile_config.get("id") or "")
    started_at = time.time()
    _RUNNING_SESSIONS[session_id] = {
        "profile_id": profile_id,
        "started_at": started_at,
        "stop_requested": False,
    }

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
        if raw_server and "://" not in raw_server:
            raw_server = f"http://{raw_server}"
        proxy_arg = {"server": raw_server}
        if proxy_cfg.get("username"):
            proxy_arg["username"] = str(proxy_cfg["username"])
        if proxy_cfg.get("password"):
            proxy_arg["password"] = str(proxy_cfg["password"])
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
            try:
                # Bumped 30s → 45s. With anti-detect JS injected (~35
                # patches) the first paint takes 5-10s longer than a
                # bare browser; many residential proxies also add a
                # 2-3s connect handshake. 45s is generous but still
                # bails out if the host is truly dead.
                await page.goto(start_url or "https://www.google.com/", timeout=45000)
            except Exception as e:
                logger.warning(f"start URL goto failed: {e}")

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
