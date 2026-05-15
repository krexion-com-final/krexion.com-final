"""
Visual Recorder — interactive Playwright session manager that records the
user's clicks/typing as a Krexion automation JSON.

Workflow:
1. /api/visual-recorder/start — launches a headless Chromium with the
   user's chosen proxy + UA, opens the URL, returns a session_id.
2. The frontend polls /screenshot every ~700ms to render a live preview.
3. Each user interaction (click, type, wait, navigate) is forwarded to
   /click, /type, /wait, /navigate which:
     a. Performs the action inside Playwright.
     b. Captures a robust selector of the affected element.
     c. Appends a step to the in-memory `steps` array.
4. /mark-final captures the current screenshot as the conversion target.
5. /finalize stops the browser, returns the assembled JSON + the saved
   target screenshot (path).

Sessions auto-cleanup if idle >45 min. There is NO total-time cap
(per user requirement).
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("visual_recorder")

# ── Tunables ────────────────────────────────────────────────────────────
IDLE_TIMEOUT_S = 45 * 60        # 45 min idle → auto-stop session
REAPER_INTERVAL_S = 60          # check every minute
DEFAULT_VIEWPORT = (412, 914)   # Pixel-8 mobile (matches RUT mobile profile)
MAX_CONCURRENT_SESSIONS = 5     # prevent runaway memory
SCREENSHOT_QUALITY = 60         # JPEG quality for stream
SCREENSHOT_TYPE = "jpeg"
# Total time we allow for: playwright start + browser launch + new_context +
# initial goto. Bad/slow proxies otherwise hang the recorder forever.
STARTUP_TIMEOUT_S = 45          # Increased to 45s for slow proxies
LAUNCH_TIMEOUT_S = 15           # browser launch + context only
GOTO_TIMEOUT_MS = 35_000        # Increased to 35s for initial page.goto with slow proxies

# Persistent storage for finalized recordings
SESSIONS_ROOT = Path(__file__).parent / "visual_recorder_sessions"
SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)


# ── Step builders ───────────────────────────────────────────────────────
def _build_text_click_evaluate(text: str) -> Dict[str, Any]:
    """JS that finds an element by visible text and clicks it.

    Robust against re-renders because it re-queries every replay.
    Matches buttons, anchors, divs, spans whose innerText (trimmed,
    case-insensitive) equals the given text.
    """
    safe = text.replace("\\", "\\\\").replace("'", "\\'")
    script = (
        "(function(){var t='" + safe + "'.toLowerCase();"
        "var els=Array.from(document.querySelectorAll('button,a,div,span,label,input[type=submit]'))"
        ".filter(function(e){var s=window.getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden')return false;"
        "var x=((e.innerText||e.textContent||e.value||'')+'').trim().toLowerCase();return x===t;});"
        "if(els.length){els[0].scrollIntoView({block:'center'});els[0].click();}})();"
    )
    return {"action": "evaluate", "script": script}


def _build_random_pick_evaluate(texts: List[str]) -> Dict[str, Any]:
    """Pick one of N elements (by visible text) at random and click."""
    safe = [t.replace("\\", "\\\\").replace("'", "\\'") for t in texts]
    arr = "['" + "','".join(safe) + "']"
    script = (
        "(function(){var labels=" + arr + ";"
        "var pick=labels[Math.floor(Math.random()*labels.length)].toLowerCase();"
        "var els=Array.from(document.querySelectorAll('button,a,div,span,label'))"
        ".filter(function(e){var s=window.getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden')return false;"
        "var x=((e.innerText||e.textContent||'')+'').trim().toLowerCase();return x===pick;});"
        "if(els.length){els[0].scrollIntoView({block:'center'});els[0].click();}})();"
    )
    return {"action": "evaluate", "script": script}


def _build_fill_step(selector: str, value: str) -> Dict[str, Any]:
    return {"action": "fill", "selector": selector, "value": value, "timeout": 6000, "optional": True}


def _build_wait(ms: int) -> Dict[str, Any]:
    return {"action": "wait", "ms": int(max(100, min(ms, 120000)))}


def _build_wait_load(timeout_ms: int = 60000) -> Dict[str, Any]:
    return {"action": "wait_for_load", "timeout": int(timeout_ms)}


def _build_scroll(y: int) -> Dict[str, Any]:
    return {"action": "scroll", "y": int(y)}


# ── Session state ───────────────────────────────────────────────────────
@dataclass
class RecorderSession:
    session_id: str
    user_id: str
    url: str
    proxy: Optional[str]
    user_agent: Optional[str]
    headers: List[str]                          # Excel column names for form-fill binding
    viewport: Tuple[int, int] = DEFAULT_VIEWPORT
    steps: List[Dict[str, Any]] = field(default_factory=list)
    last_activity: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    target_screenshot_path: Optional[str] = None
    final_url: Optional[str] = None
    final_text_snippet: Optional[str] = None
    # Connection lifecycle: starting | ready | error | stopped
    state: str = "starting"
    error_message: str = ""
    ready_at: Optional[float] = None
    # Playwright handles (set once state == "ready")
    playwright: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    # Lock to serialize actions on the same browser
    lock: Optional[asyncio.Lock] = None
    # Background startup task (so we can cancel it on stop)
    startup_task: Any = None

    def touch(self):
        self.last_activity = time.time()


# Global registry
_SESSIONS: Dict[str, RecorderSession] = {}
_REAPER_TASK: Optional[asyncio.Task] = None


# ── Lifecycle ───────────────────────────────────────────────────────────
async def start_session(
    user_id: str,
    url: str,
    proxy: Optional[str] = None,
    user_agent: Optional[str] = None,
    headers: Optional[List[str]] = None,
) -> RecorderSession:
    """Create a session and kick off browser launch in the background.

    Returns IMMEDIATELY with state="starting". The caller (frontend) should
    poll `/state` until `state` becomes "ready" or "error". This avoids
    tying up a request thread for 30+ seconds while a slow residential
    proxy negotiates a TCP tunnel.
    """
    if len(_SESSIONS) >= MAX_CONCURRENT_SESSIONS:
        # Reap before refusing
        await _reap_idle()
        if len(_SESSIONS) >= MAX_CONCURRENT_SESSIONS:
            raise RuntimeError(
                f"Max {MAX_CONCURRENT_SESSIONS} concurrent recorder sessions running. "
                "Wait for one to free or stop yours first."
            )

    sid = str(uuid.uuid4())
    sess = RecorderSession(
        session_id=sid,
        user_id=user_id,
        url=url,
        proxy=proxy,
        user_agent=user_agent or (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
        headers=headers or [],
    )
    sess.lock = asyncio.Lock()
    sess.state = "starting"

    _SESSIONS[sid] = sess
    _ensure_reaper()

    # Fire-and-forget background init. Wrapped with overall timeout so a
    # dead proxy can never hang us forever.
    sess.startup_task = asyncio.create_task(_init_browser_bg(sess))
    logger.info(f"Visual recorder session created (starting): {sid} (url={url[:60]})")
    return sess


async def _init_browser_bg(sess: RecorderSession) -> None:
    """Background task: launch Playwright + open URL with strict timeout.

    On success: state="ready". On any failure / timeout: state="error" with
    error_message set, and Playwright handles cleaned up.
    """
    sid = sess.session_id
    try:
        await asyncio.wait_for(_init_browser_inner(sess), timeout=STARTUP_TIMEOUT_S)
        sess.state = "ready"
        sess.ready_at = time.time()
        sess.touch()
        logger.info(f"Visual recorder session ready: {sid}")
    except asyncio.TimeoutError:
        sess.state = "error"
        sess.error_message = (
            f"Connection timed out after {STARTUP_TIMEOUT_S}s. "
            "The proxy or target URL is too slow / unreachable. "
            "Try a different proxy or remove the proxy field."
        )
        logger.warning(f"Visual recorder startup timeout: {sid}")
        await _cleanup_handles(sess)
    except Exception as e:
        sess.state = "error"
        sess.error_message = f"Startup failed: {type(e).__name__}: {str(e)[:240]}"
        logger.warning(f"Visual recorder startup failed {sid}: {e}")
        await _cleanup_handles(sess)


async def _init_browser_inner(sess: RecorderSession) -> None:
    """The actual launch sequence. Wrapped by `_init_browser_bg` for timeout."""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    sess.playwright = pw

    launch_opts: Dict[str, Any] = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-renderer-backgrounding",
        ],
        "timeout": LAUNCH_TIMEOUT_S * 1000,  # Playwright launch budget
    }
    if sess.proxy:
        proxy_str = sess.proxy if sess.proxy.startswith(("http://", "socks5://", "https://")) else f"http://{sess.proxy}"
        launch_opts["proxy"] = {"server": proxy_str}

    sess.browser = await pw.chromium.launch(**launch_opts)
    sess.context = await sess.browser.new_context(
        viewport={"width": sess.viewport[0], "height": sess.viewport[1]},
        user_agent=sess.user_agent,
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        locale="en-US",
        timezone_id="America/New_York",
    )
    sess.page = await sess.context.new_page()

    # Block font files to prevent font loading delays
    # This prevents Playwright screenshot from hanging on fonts.ready
    await sess.page.route("**/*.{woff,woff2,ttf,otf,eot}", lambda route: route.abort())

    # Override document.fonts.ready to prevent screenshot hanging
    # This must be done via page.add_init_script so it runs on every page load
    await sess.page.add_init_script("""
        Object.defineProperty(document.fonts, 'ready', {
            get: () => Promise.resolve(),
            configurable: true
        });
    """)

    # First steps in the recorded JSON
    sess.steps.append(_build_wait_load(60000))
    sess.steps.append(_build_wait(2000))

    # Navigate (best-effort — even if goto fails we keep the session
    # so the user can navigate manually via /navigate).
    # Use networkidle for better compatibility with slow proxies
    try:
        await sess.page.goto(sess.url, wait_until="networkidle", timeout=GOTO_TIMEOUT_MS)
    except Exception as e:
        logger.warning(f"Initial goto failed for {sess.session_id}: {e}")
        # If networkidle fails, try with just domcontentloaded as fallback
        try:
            await sess.page.goto(sess.url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
        except Exception as e2:
            logger.warning(f"Fallback goto also failed for {sess.session_id}: {e2}")


async def _cleanup_handles(sess: RecorderSession) -> None:
    """Close any partially-opened Playwright handles. Safe to call twice."""
    try:
        if sess.browser:
            await sess.browser.close()
    except Exception:
        pass
    try:
        if sess.playwright:
            await sess.playwright.stop()
    except Exception:
        pass
    sess.browser = None
    sess.context = None
    sess.page = None
    sess.playwright = None


async def stop_session(session_id: str) -> bool:
    sess = _SESSIONS.pop(session_id, None)
    if not sess:
        return False
    # Cancel pending startup if it's still running
    try:
        if sess.startup_task and not sess.startup_task.done():
            sess.startup_task.cancel()
    except Exception:
        pass
    await _cleanup_handles(sess)
    sess.state = "stopped"
    logger.info(f"Visual recorder session stopped: {session_id}")
    return True


def get_session(session_id: str, user_id: str) -> RecorderSession:
    sess = _SESSIONS.get(session_id)
    if not sess or sess.user_id != user_id:
        raise KeyError("Session not found")
    return sess


# ── Idle reaper ─────────────────────────────────────────────────────────
def _ensure_reaper():
    global _REAPER_TASK
    if _REAPER_TASK is None or _REAPER_TASK.done():
        try:
            _REAPER_TASK = asyncio.create_task(_reaper_loop())
        except RuntimeError:
            pass


async def _reaper_loop():
    while True:
        try:
            await asyncio.sleep(REAPER_INTERVAL_S)
            await _reap_idle()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Visual recorder reaper error: {e}")


async def _reap_idle():
    now = time.time()
    to_kill = [sid for sid, s in _SESSIONS.items() if now - s.last_activity > IDLE_TIMEOUT_S]
    for sid in to_kill:
        logger.info(f"Reaping idle visual recorder session {sid}")
        await stop_session(sid)


# ── Actions ─────────────────────────────────────────────────────────────
async def take_screenshot(sess: RecorderSession) -> bytes:
    sess.touch()
    if sess.state != "ready" or sess.page is None:
        return b""
    async with sess.lock:
        try:
            # Override fonts.ready immediately before screenshot
            # This is more reliable than add_init_script for already-loaded pages
            try:
                await sess.page.evaluate("""
                    Object.defineProperty(document.fonts, 'ready', {
                        get: () => Promise.resolve(),
                        configurable: true,
                        writable: true
                    });
                """)
            except Exception:
                pass  # Ignore if already overridden or page not ready
            
            # Screenshot with reasonable timeout - fonts are now handled properly
            data = await sess.page.screenshot(
                type=SCREENSHOT_TYPE, 
                quality=SCREENSHOT_QUALITY, 
                full_page=False,
                timeout=30000,  # 30s timeout - fonts no longer block
                animations="disabled"
            )
        except Exception as e:
            logger.warning(f"screenshot failed for {sess.session_id}: {e}")
            return b""
    return data


async def get_page_meta(sess: RecorderSession) -> Dict[str, Any]:
    sess.touch()
    if sess.state != "ready" or sess.page is None:
        return {"url": "", "title": "", "viewport": {"width": sess.viewport[0], "height": sess.viewport[1]}}
    async with sess.lock:
        try:
            url = sess.page.url
            title = await sess.page.title()
            vp = sess.page.viewport_size or {"width": sess.viewport[0], "height": sess.viewport[1]}
        except Exception:
            url, title, vp = "", "", {"width": sess.viewport[0], "height": sess.viewport[1]}
    return {"url": url, "title": title, "viewport": vp}


async def click_at(sess: RecorderSession, x: int, y: int, mode: str = "default", header_name: Optional[str] = None, group_id: Optional[str] = None) -> Dict[str, Any]:
    """Forward a click at (x, y) onto the page. Captures the element and
    appends a step. Modes:
      - default:   normal text-based click
      - form_fill: click + remember field for next /type call (Excel header binding)
      - random:    add this element to a "random pick" group (group_id required)
      - final:     mark current page as conversion target
    """
    sess.touch()
    async with sess.lock:
        # Find element at point + extract a robust label/selector
        info = await sess.page.evaluate(
            """([x,y])=>{
                var el = document.elementFromPoint(x, y);
                if(!el) return null;
                while(el && el.tagName==='SPAN' && el.parentElement && el.parentElement.tagName!=='BODY'){el = el.parentElement; if((el.innerText||el.textContent||'').trim().length>0) break;}
                var r = el.getBoundingClientRect();
                var text = ((el.innerText || el.textContent || '') + '').trim().slice(0, 80);
                var ph = el.getAttribute && el.getAttribute('placeholder');
                var name = el.getAttribute && el.getAttribute('name');
                var id = el.id || '';
                var tag = el.tagName;
                var type = el.type || '';
                var aria = el.getAttribute && el.getAttribute('aria-label');
                return {tag, text, placeholder: ph, name, id, type, aria, x: r.left + r.width/2, y: r.top + r.height/2};
            }""",
            [int(x), int(y)],
        )
        if not info:
            # fall back to plain click at coords
            await sess.page.mouse.click(x, y)
            return {"recorded": False, "warning": "No element at that point — clicked anyway, no step recorded"}

        # Perform the click
        try:
            await sess.page.mouse.click(info["x"], info["y"])
        except Exception:
            pass

    # Build & append step (outside lock to keep it short)
    step: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = {"element": info}

    text = info.get("text") or ""
    if mode == "default":
        if text:
            step = _build_text_click_evaluate(text)
        else:
            # No text — can't build a robust click. Fall back to coord.
            step = {"action": "evaluate", "script": f"(function(){{var el=document.elementFromPoint({int(x)},{int(y)}); if(el){{el.scrollIntoView({{block:'center'}}); el.click();}}}})();"}
    elif mode == "form_fill":
        # Build a selector for the input
        sel = _make_selector_for_input(info)
        # If a header is mapped, the actual fill step is added later via /type
        # Here we just record a "wait_for_selector" + "click" so the input is focused
        step = {"action": "wait_for_selector", "selector": sel, "timeout": 8000, "optional": True}
        extra["selector"] = sel
        extra["header_name"] = header_name
    elif mode == "random":
        # Don't add a step — caller will batch via /group-random
        extra["pending_random_text"] = text
        extra["group_id"] = group_id
    elif mode == "final":
        # Captured separately by /mark-final endpoint
        step = None
    else:
        step = _build_text_click_evaluate(text) if text else None

    if step is not None:
        sess.steps.append(step)
        # Auto wait+wait_for_load after clicks (real-world feels more reliable)
        sess.steps.append(_build_wait(1500))
        sess.steps.append(_build_wait_load(60000))
        sess.steps.append(_build_wait(2000))

    return {"recorded": step is not None, "step": step, "element": info, "mode": mode, **{k: v for k, v in extra.items() if k != "element"}}


def _make_selector_for_input(info: Dict[str, Any]) -> str:
    """Build a CSS selector for an input given its DOM info."""
    name = info.get("name") or ""
    placeholder = info.get("placeholder") or ""
    id_ = info.get("id") or ""
    aria = info.get("aria") or ""
    type_ = info.get("type") or ""
    if id_:
        return f"#{id_}"
    if name:
        return f"input[name='{name}']"
    if placeholder:
        return f"input[placeholder='{placeholder}']"
    if aria:
        return f"input[aria-label='{aria}']"
    if type_:
        return f"input[type='{type_}']"
    return "input"


async def type_text(sess: RecorderSession, selector: str, value: str, header_name: Optional[str] = None) -> Dict[str, Any]:
    """Type into the element matched by `selector`. If header_name is set,
    the recorded step uses `{{header_name}}` placeholder so the RUT engine
    substitutes from the Excel row at runtime.
    """
    sess.touch()
    async with sess.lock:
        try:
            await sess.page.fill(selector, value, timeout=6000)
        except Exception as e:
            logger.warning(f"type fill failed selector={selector}: {e}")

    template = f"{{{{{header_name}}}}}" if header_name else value
    step = _build_fill_step(selector, template)
    sess.steps.append(step)
    sess.steps.append(_build_wait(800))
    return {"recorded": True, "step": step, "header_name": header_name}


async def add_wait_step(sess: RecorderSession, ms: int) -> Dict[str, Any]:
    sess.touch()
    step = _build_wait(ms)
    sess.steps.append(step)
    return {"recorded": True, "step": step}


async def add_wait_load_step(sess: RecorderSession, timeout_ms: int = 60000) -> Dict[str, Any]:
    sess.touch()
    step = _build_wait_load(timeout_ms)
    sess.steps.append(step)
    return {"recorded": True, "step": step}


async def add_scroll_step(sess: RecorderSession, y: int) -> Dict[str, Any]:
    sess.touch()
    async with sess.lock:
        try:
            await sess.page.mouse.wheel(0, int(y))
        except Exception:
            pass
    step = _build_scroll(y)
    sess.steps.append(step)
    sess.steps.append(_build_wait(500))
    return {"recorded": True, "step": step}


async def navigate_to(sess: RecorderSession, url: str) -> Dict[str, Any]:
    """Navigate the page to a new URL. Records a wait_for_load step."""
    sess.touch()
    async with sess.lock:
        try:
            await sess.page.goto(url, wait_until="load", timeout=45000)
        except Exception as e:
            logger.warning(f"navigate failed: {e}")
    sess.steps.append(_build_wait_load(60000))
    sess.steps.append(_build_wait(2000))
    return {"recorded": True, "url": url}


async def mark_final(sess: RecorderSession) -> Dict[str, Any]:
    """Capture the current screenshot as the conversion target."""
    sess.touch()
    folder = SESSIONS_ROOT / sess.session_id
    folder.mkdir(parents=True, exist_ok=True)
    target_path = folder / "target_screenshot.png"
    async with sess.lock:
        try:
            await sess.page.screenshot(path=str(target_path), type="png", full_page=False)
            sess.target_screenshot_path = str(target_path)
            sess.final_url = sess.page.url
            try:
                txt = await sess.page.evaluate("() => (document.body.innerText || '').slice(0, 280)")
                sess.final_text_snippet = (txt or "").strip()
            except Exception:
                sess.final_text_snippet = None
        except Exception as e:
            logger.warning(f"mark_final failed: {e}")
            return {"recorded": False, "error": str(e)}
    return {
        "recorded": True,
        "target_screenshot_path": sess.target_screenshot_path,
        "final_url": sess.final_url,
        "final_text_snippet": sess.final_text_snippet,
    }


async def group_last_as_random(sess: RecorderSession, count: int) -> Dict[str, Any]:
    """Replace the last `count` element-click steps with one random-pick
    step. (Use this AFTER clicking N candidate buttons in `mode=random`.)
    NOTE: in `mode=random` we DO NOT append individual steps — the texts
    are stored in a pending list. This call just builds & appends the
    random_pick step from those texts.
    """
    sess.touch()
    pending = getattr(sess, "_pending_random", None) or []
    if not pending:
        return {"recorded": False, "error": "No pending random elements — use mode=random click first"}
    take = pending[-int(count):]
    step = _build_random_pick_evaluate(take)
    sess.steps.append(step)
    sess.steps.append(_build_wait(2000))
    sess.steps.append(_build_wait_load(60000))
    sess.steps.append(_build_wait(2500))
    sess._pending_random = []
    return {"recorded": True, "step": step, "items": take}


def remove_step(sess: RecorderSession, index: int) -> Dict[str, Any]:
    sess.touch()
    if 0 <= index < len(sess.steps):
        removed = sess.steps.pop(index)
        return {"removed": removed, "remaining": len(sess.steps)}
    return {"removed": None, "remaining": len(sess.steps)}


def get_steps(sess: RecorderSession) -> List[Dict[str, Any]]:
    return sess.steps


async def finalize(sess: RecorderSession) -> Dict[str, Any]:
    """Stop the session and return the recording bundle."""
    sess.touch()
    out = {
        "session_id": sess.session_id,
        "url": sess.url,
        "proxy": sess.proxy,
        "user_agent": sess.user_agent,
        "headers": sess.headers,
        "automation_json": sess.steps,
        "target_screenshot_path": sess.target_screenshot_path,
        "final_url": sess.final_url,
        "final_text_snippet": sess.final_text_snippet,
        "step_count": len(sess.steps),
    }
    # Persist to disk before stopping
    try:
        folder = SESSIONS_ROOT / sess.session_id
        folder.mkdir(parents=True, exist_ok=True)
        import json as _json
        with open(folder / "automation.json", "w") as f:
            _json.dump(sess.steps, f, indent=2)
        with open(folder / "meta.json", "w") as f:
            _json.dump({k: v for k, v in out.items() if k != "automation_json"}, f, indent=2)
    except Exception as e:
        logger.warning(f"finalize persist failed: {e}")
    await stop_session(sess.session_id)
    return out
