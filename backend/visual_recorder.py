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


# ── Proxy parsing ───────────────────────────────────────────────────────
# Visual Recorder accepts the same flexible proxy string format used by
# the rest of Krexion (RUT, AdsPower, etc.):
#   host:port
#   host:port:user:pass
#   user:pass@host:port
#   http://user:pass@host:port
#   socks5://user:pass@host:port
# Returns Playwright's proxy dict ({server, username, password}) or None
# on invalid input. Without this, credentials were silently dropped and
# authenticated residential proxies returned ERR_TUNNEL_CONNECTION_FAILED
# (visible to the user as a blank live-preview).
def _parse_proxy_for_playwright(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    scheme = "http"
    for prefix, sch in (("http://", "http"), ("https://", "https"),
                        ("socks5://", "socks5"), ("socks4://", "socks4")):
        if s.lower().startswith(prefix):
            scheme = sch
            s = s[len(prefix):]
            break
    user, pwd = None, None
    if "@" in s:
        auth, s = s.rsplit("@", 1)
        if ":" in auth:
            user, pwd = auth.split(":", 1)
        else:
            user = auth
    parts = s.split(":")
    if len(parts) == 2:
        host, port = parts
    elif len(parts) == 4:
        # host:port:user:pass
        host, port, user, pwd = parts
    else:
        return None
    try:
        int(port)
    except ValueError:
        return None
    out: Dict[str, Any] = {"server": f"{scheme}://{host}:{port}"}
    if user:
        out["username"] = user
    if pwd:
        out["password"] = pwd
    return out


# ── Step builders ───────────────────────────────────────────────────────
def _build_text_click_evaluate(text: str) -> Dict[str, Any]:
    """JS that finds an element by visible text and clicks it.

    Robust against re-renders because it re-queries every replay.

    ── 2026-05 (revised) ──
    PRIORITISE ANCHORS. Many offer-page CTAs are anchors wrapped in
    DIV/SPAN containers (e.g. `<div class="text-center"><a href="...">
    Unlock Now</a></div>`). The naive "all elements" query matched the
    outer DIV first because its visible innerText was the SAME as the
    anchor's. Clicking the DIV did nothing useful (no href, no submit
    handler). We now search anchors first; if an `<a>` with matching
    text is found we navigate via `window.location.assign(el.href)`
    which is deterministic in headless Chromium + residential proxy
    (where the synthetic .click() event on anchors was being lost).

    For non-anchor matches we ALSO peek inside for a descendant `<a>`
    — common pattern in card-style CTAs. Falls back to a plain
    `.click()` for true buttons / input[type=submit] / React onClick
    spans.

    ── 2026-05 #2 (submit-button fix) ──
    For `input[type=submit]` and `button[type=submit]`, calling
    `el.click()` in JS does NOT always navigate (the browser's submit
    dispatcher may be skipped under headless + residential proxy).
    We now also call `form.submit()` 150ms after .click() as a safety
    net. Double-submits are de-duplicated server-side by the offer
    page's antispam token; the small delay lets any onclick analytics
    fire before the forced submit.
    """
    safe = text.replace("\\", "\\\\").replace("'", "\\'")
    script = (
        "(function(){var t='" + safe + "'.replace(/\\s+/g,' ').trim().toLowerCase();"
        "var match=function(e){var s=window.getComputedStyle(e);"
        "if(s.display==='none'||s.visibility==='hidden')return false;"
        # 2026-01: Normalize whitespace + use CONTAINS match for long text.
        # Exact-match was too brittle — pages add trailing words like
        # "below." or wrap CTAs in extra <span> children that break === .
        # We use word-aware contains so we don't false-match short tokens.
        "var x=((e.innerText||e.textContent||e.value||'')+'').replace(/\\s+/g,' ').trim().toLowerCase();"
        "if(!x)return false;"
        "if(x===t)return true;"
        "if(t.length>=12&&x.indexOf(t)!==-1)return true;"
        "if(t.length>=12&&x.length>=8&&t.indexOf(x)!==-1)return true;"
        "return false;};"
        # 1. Prefer real anchors
        "var anchors=Array.from(document.querySelectorAll('a')).filter(match);"
        "if(anchors.length){var a=anchors[0];a.scrollIntoView({block:'center'});"
        "if(a.href&&!a.target){window.location.assign(a.href);}else{a.click();}return;}"
        # 2. Fall back to other clickable elements (added input + label-for handling)
        "var els=Array.from(document.querySelectorAll('button,div,span,label,input,[role=button],[role=checkbox]')).filter(match);"
        "if(els.length){var el=els[0];el.scrollIntoView({block:'center'});"
        # 2026-01: If matched element is a LABEL with `for=`, click the
        # actual control it points to (fixes checkbox text-click failures
        # where the visible text is in a <label> but the real input is
        # a separate <input type=checkbox>).
        "if(el.tagName==='LABEL'&&el.htmlFor){var ctl=document.getElementById(el.htmlFor);if(ctl){ctl.scrollIntoView({block:'center'});ctl.click();return;}}"
        # Peek inside for a wrapped anchor (CTA-card pattern)
        "var inner=el.querySelector&&el.querySelector('a[href]');"
        "if(inner&&inner.href&&!inner.target){window.location.assign(inner.href);return;}"
        # 2026-01: If matched element contains a checkbox / radio, click that
        "var box=el.querySelector&&el.querySelector('input[type=checkbox],input[type=radio]');"
        "if(box&&!box.checked){box.click();return;}"
        # Otherwise plain click
        "el.click();"
        # If this was a submit button, force the form submission as a safety net
        "var isSubmit=(el.tagName==='INPUT'||el.tagName==='BUTTON')&&(el.type==='submit'||el.getAttribute&&el.getAttribute('type')==='submit');"
        "if(isSubmit){var f=el.form||(el.closest&&el.closest('form'));"
        "if(f){setTimeout(function(){try{if(!f._krx_submitted){f._krx_submitted=true;f.submit();}}catch(e){}},150);}}"
        "}})();"
    )
    return {"action": "evaluate", "script": script}


def _build_random_pick_evaluate(texts: List[str]) -> Dict[str, Any]:
    """Pick one of N elements (by visible text) at random and click.

    Same anchor-first priority + submit-button force-submit safety net
    as _build_text_click_evaluate.
    """
    safe = [t.replace("\\", "\\\\").replace("'", "\\'") for t in texts]
    arr = "['" + "','".join(safe) + "']"
    script = (
        "(function(){var labels=" + arr + ";"
        "var pick=labels[Math.floor(Math.random()*labels.length)].replace(/\\s+/g,' ').trim().toLowerCase();"
        "var match=function(e){var s=window.getComputedStyle(e);"
        "if(s.display==='none'||s.visibility==='hidden')return false;"
        # 2026-01: same whitespace-normalised + contains match as
        # _build_text_click_evaluate so random survey picks aren't
        # broken by trailing "below." / extra <span> children.
        "var x=((e.innerText||e.textContent||e.value||'')+'').replace(/\\s+/g,' ').trim().toLowerCase();"
        "if(!x)return false;"
        "if(x===pick)return true;"
        "if(pick.length>=12&&x.indexOf(pick)!==-1)return true;"
        "if(pick.length>=12&&x.length>=8&&pick.indexOf(x)!==-1)return true;"
        "return false;};"
        "var anchors=Array.from(document.querySelectorAll('a')).filter(match);"
        "if(anchors.length){var a=anchors[0];a.scrollIntoView({block:'center'});"
        "if(a.href&&!a.target){window.location.assign(a.href);}else{a.click();}return;}"
        "var els=Array.from(document.querySelectorAll('button,div,span,label,input,[role=button],[role=checkbox]')).filter(match);"
        "if(els.length){var el=els[0];el.scrollIntoView({block:'center'});"
        "if(el.tagName==='LABEL'&&el.htmlFor){var ctl=document.getElementById(el.htmlFor);if(ctl){ctl.scrollIntoView({block:'center'});ctl.click();return;}}"
        "var inner=el.querySelector&&el.querySelector('a[href]');"
        "if(inner&&inner.href&&!inner.target){window.location.assign(inner.href);return;}"
        "var box=el.querySelector&&el.querySelector('input[type=checkbox],input[type=radio]');"
        "if(box&&!box.checked){box.click();return;}"
        "el.click();"
        "var isSubmit=(el.tagName==='INPUT'||el.tagName==='BUTTON')&&(el.type==='submit'||el.getAttribute&&el.getAttribute('type')==='submit');"
        "if(isSubmit){var f=el.form||(el.closest&&el.closest('form'));"
        "if(f){setTimeout(function(){try{if(!f._krx_submitted){f._krx_submitted=true;f.submit();}}catch(e){}},150);}}"
        "}})();"
    )
    return {"action": "evaluate", "script": script}


def _build_fill_step(selector: str, value: str) -> Dict[str, Any]:
    return {"action": "fill", "selector": selector, "value": value, "timeout": 6000, "optional": True}


# ── 2026-01: Fallback sample data ──────────────────────────────────────
# When the user binds a form field to a column header (e.g. {{first}})
# but the recorder has NO sample_row (Excel not uploaded) OR the column
# is missing from the sample_row, the live browser input stays empty
# → form validation blocks CONTINUE → user can't record subsequent
# pages (survey / thank-you / etc.).
#
# This helper returns a sensible *temporary* value based on the column
# name so the live form passes validation. The recorded JSON step STILL
# uses the `{{header}}` placeholder — at RUT replay time the actual
# lead row substitutes via the engine's _substitute() function. Production
# behaviour is therefore unchanged; this only affects what's typed into
# the live browser during recording.
_FALLBACK_SAMPLES: Dict[str, str] = {
    # Names
    "first": "John", "firstname": "John", "first_name": "John", "fname": "John", "givenname": "John",
    "last": "Smith", "lastname": "Smith", "last_name": "Smith", "lname": "Smith", "surname": "Smith", "familyname": "Smith",
    "name": "John Smith", "fullname": "John Smith", "full_name": "John Smith",
    "middle": "A", "middlename": "A", "middle_name": "A", "mname": "A",
    # Contact
    "email": "john.smith@example.com", "emailaddress": "john.smith@example.com", "email_address": "john.smith@example.com", "mail": "john.smith@example.com",
    "phone": "5551234567", "phonenumber": "5551234567", "phone_number": "5551234567", "mobile": "5551234567", "tel": "5551234567", "telephone": "5551234567", "cell": "5551234567",
    # Address
    "address": "123 Main Street", "street": "123 Main Street", "streetaddress": "123 Main Street", "street_address": "123 Main Street", "address1": "123 Main Street", "addr": "123 Main Street",
    "address2": "Apt 4B", "apt": "4B", "unit": "4B", "suite": "4B",
    "city": "New York", "town": "New York",
    "state": "NY", "region": "NY", "province": "NY",
    "zip": "10001", "zipcode": "10001", "zip_code": "10001", "postal": "10001", "postalcode": "10001", "postal_code": "10001", "postcode": "10001",
    "country": "United States",
    # DOB
    "day": "15", "birth_day": "15", "birthday": "15", "dob_day": "15", "dday": "15", "bday": "15",
    "month": "6", "birth_month": "6", "birthmonth": "6", "dob_month": "6", "dmonth": "6", "bmonth": "6",
    "year": "1990", "birth_year": "1990", "birthyear": "1990", "dob_year": "1990", "dyear": "1990", "byear": "1990",
    "dob": "06/15/1990", "birthdate": "06/15/1990", "birth_date": "06/15/1990",
    "age": "34",
    # Misc
    "gender": "Male", "sex": "Male",
    "ssn": "123456789", "social": "123456789",
    "income": "50000", "salary": "50000",
    "password": "TempPass123!", "pwd": "TempPass123!", "passwd": "TempPass123!",
    "username": "johnsmith", "user": "johnsmith", "userid": "johnsmith",
    "company": "Acme Corp", "employer": "Acme Corp", "business": "Acme Corp",
}


def _get_fallback_sample_value(header_name: str) -> Optional[str]:
    """Return a temporary sample value for a header name so the live
    browser form fills with realistic data during recording.

    Match is case-insensitive AND tries substring matching as a last
    resort (e.g. "user_first_name" → "first" → "John").
    """
    if not header_name:
        return None
    key = str(header_name).strip().lower().replace("-", "_").replace(" ", "_")
    # Exact match
    if key in _FALLBACK_SAMPLES:
        return _FALLBACK_SAMPLES[key]
    # Try collapsed (no underscores)
    collapsed = key.replace("_", "")
    if collapsed in _FALLBACK_SAMPLES:
        return _FALLBACK_SAMPLES[collapsed]
    # Substring match — longest fallback key first
    for fk in sorted(_FALLBACK_SAMPLES.keys(), key=len, reverse=True):
        if fk in key or fk in collapsed:
            return _FALLBACK_SAMPLES[fk]
    return None


def _resolve_live_value(sess: "RecorderSession", header_name: str) -> Optional[str]:
    """Resolve the value to fill into the live browser for a header.

    Priority:
      1. sess.sample_row[header_name]  (user-uploaded Excel data)
      2. _get_fallback_sample_value()  (sensible default based on column name)
    """
    if not header_name:
        return None
    key = str(header_name).strip().lower()
    if key in sess.sample_row:
        raw = sess.sample_row[key]
        if raw is not None and str(raw).strip() != "":
            return str(raw)
    return _get_fallback_sample_value(header_name)


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
    # ── 2026-05 ──
    # Sample data row used DURING recording so the form fills with
    # realistic values (lets the user proceed past form validation
    # and record steps on the page that comes AFTER submit). At
    # replay time the RUT engine substitutes the actual lead row.
    sample_row: Dict[str, Any] = field(default_factory=dict)
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
    sample_row: Optional[Dict[str, Any]] = None,
) -> RecorderSession:
    """Create a session and kick off browser launch in the background.

    Returns IMMEDIATELY with state="starting". The caller (frontend) should
    poll `/state` until `state` becomes "ready" or "error". This avoids
    tying up a request thread for 30+ seconds while a slow residential
    proxy negotiates a TCP tunnel.

    `sample_row` (optional): one dict of Excel column → value used to
    populate form inputs DURING recording so the user can proceed past
    form validation and record steps on the post-submit page. At RUT
    replay time the actual lead row substitutes via `{{column}}`.
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
    # Normalise sample_row keys to lowercase for case-insensitive lookups
    norm_sample: Dict[str, Any] = {}
    if sample_row:
        for k, v in sample_row.items():
            if k is None:
                continue
            norm_sample[str(k).strip().lower()] = v
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
        sample_row=norm_sample,
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
        # 2026-05: Use full proxy parser so user:pass@host:port style
        # residential proxies (proxy-jet, brightdata, etc.) actually
        # authenticate. Previously credentials were silently dropped and
        # the recorder showed a blank preview because the proxy refused
        # the tunnel.
        parsed_proxy = _parse_proxy_for_playwright(sess.proxy)
        if parsed_proxy:
            launch_opts["proxy"] = parsed_proxy
        else:
            logger.warning(
                f"Visual recorder: could not parse proxy '{sess.proxy[:60]}'. "
                "Falling back to no-proxy mode."
            )

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

    # Navigate — proxy-friendly strategy:
    # 1. First try `domcontentloaded` with a SHORT timeout so the user
    #    gets a visible page within a few seconds even on slow
    #    residential proxies (was previously blocking on networkidle
    #    for the full 35s — looked like "page never loaded" to the
    #    customer).
    # 2. Then optionally chase `load` in the background (best-effort)
    #    so analytics scripts finish without blocking interaction.
    # ── 2026-05 (proxy fix) ──
    try:
        await sess.page.goto(sess.url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
    except Exception as e:
        logger.warning(f"Initial goto (domcontentloaded) failed for {sess.session_id}: {e}")
        # Last-resort: a bare `commit` so at least the URL changes and
        # the next /screenshot poll returns SOMETHING the user can see.
        try:
            await sess.page.goto(sess.url, wait_until="commit", timeout=GOTO_TIMEOUT_MS)
        except Exception as e2:
            logger.warning(f"Fallback goto also failed for {sess.session_id}: {e2}")

    # Best-effort: wait for `load` for up to 6s more so the page is
    # interactive. This runs AFTER domcontentloaded so a stuck
    # advertiser tracker can't block the initial preview.
    try:
        await sess.page.wait_for_load_state("load", timeout=6000)
    except Exception:
        pass


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
      - default:    normal text-based click
      - form_fill:  click + remember field for next /type call (Excel header binding)
      - random:     add this element to a "random pick" group (group_id required)
      - dropdown:   click a <select> element, return its <option> list so the
                    caller can bind an option (literal value/label) OR an
                    Excel column. No step is recorded until /dropdown-bind
                    is called (mirrors the form_fill → /type two-step flow).
      - final:      mark current page as conversion target
    """
    sess.touch()
    async with sess.lock:
        # Find element at point + extract a robust label/selector
        # 2026-01: enhanced text capture — also reads input.value (for
        # <input type=submit value="CONTINUE">), walks up the DOM for
        # any tag (not just SPAN) when current el has no text, and
        # captures up to 200 chars so multi-sentence consent labels
        # aren't truncated mid-sentence (which broke text-match clicks).
        info = await sess.page.evaluate(
            """([x,y])=>{
                var el = document.elementFromPoint(x, y);
                if(!el) return null;
                // Walk up to find a meaningful clickable ancestor:
                // any element whose direct text or value yields a
                // usable label, OR a known interactive tag.
                var depth = 0;
                while(el && el.parentElement && el.parentElement.tagName!=='BODY' && depth < 5){
                    var txt = ((el.innerText||el.textContent||el.value||'')+'').trim();
                    var isInteractive = /^(A|BUTTON|INPUT|SELECT|TEXTAREA|LABEL)$/.test(el.tagName);
                    if(isInteractive || (txt.length>0 && txt.length<400)) break;
                    el = el.parentElement; depth++;
                }
                var r = el.getBoundingClientRect();
                // Capture text from innerText, textContent, and value (for input[type=submit])
                var text = ((el.innerText || el.textContent || el.value || '') + '').replace(/\\s+/g,' ').trim().slice(0, 200);
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
        # ── 2026-01 fix ──
        # Skip the live click for `random` mode: in random mode the user
        # is just collecting candidate texts (or, in the new checklist
        # flow, even this path is bypassed by /detect-clickables). If we
        # click here the page navigates away before the user can add more
        # options to the random pool. Pure capture only — no side-effect.
        if mode != "random":
            try:
                await sess.page.mouse.click(info["x"], info["y"])
            except Exception:
                pass

        # For dropdown mode we also need to pull the option list out of
        # the element (or its nearest <select> ancestor) BEFORE leaving
        # the page lock so the DOM is in the state the user just saw.
        dropdown_options: List[Dict[str, str]] = []
        dropdown_selector: str = ""
        if mode == "dropdown":
            try:
                opts = await sess.page.evaluate(
                    """([x,y])=>{
                        var el = document.elementFromPoint(x, y);
                        if(!el) return null;
                        // Walk up to find the nearest <select> — works
                        // whether the user clicked the select directly or
                        // a styled wrapper around it.
                        var sel = el;
                        while(sel && sel.tagName !== 'SELECT'){
                            sel = sel.parentElement;
                        }
                        if(!sel || sel.tagName !== 'SELECT') return null;
                        var options = [];
                        for(var i=0; i<sel.options.length; i++){
                            var o = sel.options[i];
                            options.push({
                                value: String(o.value == null ? '' : o.value),
                                label: String(o.text || o.label || '').trim(),
                                index: i,
                                selected: !!o.selected,
                            });
                        }
                        return {
                            name: sel.getAttribute('name') || '',
                            id: sel.id || '',
                            options: options,
                        };
                    }""",
                    [int(x), int(y)],
                )
                if opts and opts.get("options"):
                    dropdown_options = opts["options"]
                    # Build the same selector style as form_fill so the
                    # downstream `select` action can find the element.
                    dropdown_selector = _make_selector_for_input({
                        "tag": "SELECT",
                        "name": opts.get("name") or "",
                        "id": opts.get("id") or "",
                    })
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
            # No text — can't build a robust click. Fall back to coord-based
            # click. Anchor-first priority (and inner-anchor peek) to handle
            # the common pattern of a DIV/SPAN wrapping the real <a href>.
            # Also force-submit if the clicked element is type=submit.
            step = {"action": "evaluate", "script": (
                f"(function(){{"
                f"var el=document.elementFromPoint({int(x)},{int(y)});"
                f"if(!el)return;"
                f"el.scrollIntoView({{block:'center'}});"
                f"if(el.tagName==='A'&&el.href&&!el.target){{window.location.assign(el.href);return;}}"
                f"var inner=el.querySelector&&el.querySelector('a[href]');"
                f"if(inner&&inner.href&&!inner.target){{window.location.assign(inner.href);return;}}"
                f"var up=el.closest&&el.closest('a[href]');"
                f"if(up&&up.href&&!up.target){{window.location.assign(up.href);return;}}"
                f"el.click();"
                f"var isSubmit=(el.tagName==='INPUT'||el.tagName==='BUTTON')&&(el.type==='submit'||el.getAttribute&&el.getAttribute('type')==='submit');"
                f"if(isSubmit){{var f=el.form||(el.closest&&el.closest('form'));"
                f"if(f){{setTimeout(function(){{try{{if(!f._krx_submitted){{f._krx_submitted=true;f.submit();}}}}catch(e){{}}}},150);}}}}"
                f"}})();"
            )}
    elif mode == "form_fill":
        # Build a selector for the input
        sel = _make_selector_for_input(info)
        extra["selector"] = sel
        extra["header_name"] = header_name

        # ── 2026-05 ──
        # If a header is mapped AND the recorder has a sample_row,
        # AUTO-FILL the live browser input with the sample value so
        # the user can move past form validation and record steps on
        # the NEXT page. The recorded step still uses the {{header}}
        # template — at RUT replay time the real lead row substitutes.
        # ── 2026-01 update ──
        # If sample_row is missing OR the column is not in it, fall
        # back to a sensible default (e.g. first→John, zip→10001)
        # so the live form still fills and CONTINUE works. The recorded
        # JSON step is unchanged; only the live browser uses the fallback.
        sample_val: Optional[str] = _resolve_live_value(sess, header_name) if header_name else None
        # Always emit a real `fill` step in the JSON so the runner
        # populates the input with the lead's value. The placeholder
        # `{{header_name}}` is substituted by the RUT engine's
        # _substitute() function. If no header is mapped yet, we still
        # add a wait_for_selector so the user can /type later.
        if header_name:
            step = {
                "action": "fill",
                "selector": sel,
                "value": "{{" + header_name + "}}",
                "optional": True,
            }
            # During recording, also fill the live browser with the
            # sample value so the page sees a populated field.
            if sample_val is not None:
                try:
                    await sess.page.fill(sel, sample_val, timeout=4000)
                    extra["filled_sample"] = sample_val[:30]
                except Exception as e:  # noqa: BLE001
                    extra["fill_warning"] = (
                        f"Selector did not match in the live page ({type(e).__name__}). "
                        "Step recorded anyway; verify the column name matches the field."
                    )
            else:
                extra["sample_hint"] = (
                    "No sample data for this column. Pass `sample_row` when "
                    "starting the recorder (or upload an Excel data file) so "
                    "forms fill automatically during recording."
                )
        else:
            step = {"action": "wait_for_selector", "selector": sel, "timeout": 8000, "optional": True}
    elif mode == "random":
        # Don't add a step — caller will batch via /group-random
        extra["pending_random_text"] = text
        extra["group_id"] = group_id
    elif mode == "dropdown":
        # We don't record the `select` step yet — the caller has to bind
        # it (literal option or Excel header) via /dropdown-bind first.
        # Surface the option list so the UI can render a picker.
        step = None
        extra["selector"] = dropdown_selector or _make_selector_for_input(info)
        extra["options"] = dropdown_options
        if not dropdown_options:
            extra["warning"] = (
                "No <select> element found at that point — pick the dropdown "
                "control itself (the one that opens the option list)."
            )
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


async def add_screenshot_marker(sess: RecorderSession, name: Optional[str] = None) -> Dict[str, Any]:
    """Insert a 'screenshot' action step at the current position. During
    the actual RUT job, the runner will take a real screenshot at this
    point and push it to the Live Activity panel so the customer can
    visually verify how far the visit progressed.

    Does NOT take a screenshot now — the live preview the customer is
    already polling from /screenshot covers the recording-time view.
    """
    sess.touch()
    safe_name = (name or f"Step {len(sess.steps) + 1}")[:60].strip() or f"Step {len(sess.steps) + 1}"
    step = {
        "action": "screenshot",
        "name": safe_name,
        # optional=True so a transient screenshot failure during job
        # execution (e.g. a closed page) doesn't fail the whole visit.
        "optional": True,
    }
    sess.steps.append(step)
    return {"recorded": True, "step": step}


async def bind_dropdown(
    sess: RecorderSession,
    selector: str,
    value: Optional[str] = None,
    header_name: Optional[str] = None,
    match_by: str = "label",
) -> Dict[str, Any]:
    """Finalise a dropdown binding started by a `mode='dropdown'` click.

    The caller passes EITHER:
      - `value`        — a literal option (e.g. "Male") to always select, OR
      - `header_name`  — an Excel column name; the row's value is used.

    `match_by` is either 'label' (visible text — default, most forgiving)
    or 'value' (the option's value attribute).

    ── 2026-05 ──
    During recording we ALSO call `page.select_option()` on the live
    browser so the dropdown VISIBLY changes and the form's onchange
    handlers fire. This is essential because many offer-page forms
    enable/show subsequent fields only after a dropdown is set, and
    server-side validation blocks submit if any required select is
    untouched. The placeholder `{{header}}` remains in the recorded
    step → RUT engine substitutes per-lead at replay time.
    """
    sess.touch()
    if not selector:
        return {"recorded": False, "error": "selector required"}
    if not value and not header_name:
        return {"recorded": False, "error": "either value or header_name required"}
    chosen = f"{{{{{header_name}}}}}" if header_name else str(value)
    match_by_norm = match_by if match_by in ("label", "value") else "label"
    step = {
        "action": "select",
        "selector": selector,
        "value": chosen,
        "match_by": match_by_norm,
    }
    sess.steps.append(step)
    # Brief settle wait so subsequent steps see the post-change DOM.
    sess.steps.append(_build_wait(500))

    # Live-browser select using literal value OR sample-row lookup
    # OR fallback faker (2026-01) so the dropdown always gets a value
    # during recording even when sample_row is empty or missing this col.
    live_val: Optional[str] = None
    if value:
        live_val = str(value)
    elif header_name:
        live_val = _resolve_live_value(sess, header_name)
    extra: Dict[str, Any] = {}
    if live_val is not None:
        async with sess.lock:
            ok, used = await _smart_select_option(sess.page, selector, live_val, match_by_norm)
            if ok:
                extra["selected_sample"] = (used or live_val)[:30]
            else:
                extra["select_warning"] = (
                    f"Live <select> did not accept '{live_val}' (tried multiple variants). "
                    "Step recorded anyway; verify the option matches one of the dropdown values."
                )
    else:
        extra["sample_hint"] = (
            "No sample data — provide a literal `value` or supply "
            "`sample_row` at session start so this dropdown gets a "
            "value during recording (so you can submit the form and "
            "continue recording on the NEXT page)."
        )
    return {"recorded": True, "step": step, **extra}


_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


async def _smart_select_option(page: Any, selector: str, live_val: str, match_by: str) -> Tuple[bool, Optional[str]]:
    """Try selecting an <option> using multiple value variants so common
    date / numeric dropdowns work even when the recorded value format
    doesn't exactly match the option attribute.

    Variants tried (in order):
      - the live_val as-is (label, then value, then by index for digits)
      - zero-padded version  ("6" → "06")
      - un-padded version    ("06" → "6")
      - month-name variants  ("6" → "June", "Jun")
      - month-number from name ("June" → "6", "06")

    Returns (success, variant_used).
    """
    val = str(live_val).strip()
    if not val:
        return False, None

    candidates: List[str] = [val]
    # Numeric variants (zero-pad / un-pad)
    if val.isdigit():
        n = int(val)
        padded = f"{n:02d}"
        unpadded = str(n)
        for v in (padded, unpadded):
            if v not in candidates:
                candidates.append(v)
        # Month: number → name (full + abbrev)
        if 1 <= n <= 12:
            full = _MONTH_NAMES[n - 1]
            abbrev = full[:3]
            for v in (full, abbrev, full.lower(), abbrev.lower(), full.upper(), abbrev.upper()):
                if v not in candidates:
                    candidates.append(v)
    else:
        # Month name → number variants
        lower = val.lower()
        for i, m in enumerate(_MONTH_NAMES, start=1):
            if lower == m.lower() or lower == m.lower()[:3]:
                for v in (str(i), f"{i:02d}"):
                    if v not in candidates:
                        candidates.append(v)
                break

    primary_modes = ("label", "value") if match_by == "label" else ("value", "label")

    for candidate in candidates:
        for mode in primary_modes:
            try:
                if mode == "label":
                    await page.select_option(selector, label=candidate, timeout=2000)
                else:
                    await page.select_option(selector, value=candidate, timeout=2000)
                return True, candidate
            except Exception:
                continue
    return False, None


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

    ── 2026-05 ──
    If `value` is empty AND a `header_name` is set, automatically fill
    the live browser with the value from `sample_row[header_name]` so
    the user can navigate to the next page without manually typing.
    This makes one-click "bind to column" recording workflow feasible.
    """
    sess.touch()
    # ── 2026-05 (defense-in-depth) ──
    # Some older clients send `value="{{first}}"` (the literal
    # placeholder) when binding to a header — that string was then
    # typed into the live form, the field failed validation, and the
    # user couldn't submit. We detect a `{{...}}` placeholder in
    # `value` and treat it as a binding marker — the live browser is
    # filled with the resolved sample value, not the literal text.
    import re
    placeholder_match = re.fullmatch(r"\s*\{\{\s*([^}]+?)\s*\}\}\s*", value or "")
    if placeholder_match and not header_name:
        header_name = placeholder_match.group(1).strip()
    if placeholder_match:
        value = ""  # treat as empty so the sample-row branch fires
    # Resolve the value to ACTUALLY type into the live browser. The
    # recorded JSON step still uses the `{{header}}` placeholder so
    # RUT replays with the real lead's data.
    # 2026-01: fall back to faker default when sample_row missing the col
    # so the live form fills even without Excel data uploaded.
    live_val = value
    if (not live_val) and header_name:
        live_val = _resolve_live_value(sess, header_name)
    extra: Dict[str, Any] = {}
    async with sess.lock:
        if live_val:
            try:
                await sess.page.fill(selector, live_val, timeout=6000)
                extra["filled_sample"] = live_val[:30]
            except Exception as e:
                logger.warning(f"type fill failed selector={selector}: {e}")
                extra["fill_warning"] = f"{type(e).__name__}: {str(e)[:100]}"
        elif header_name:
            extra["sample_hint"] = (
                f"No sample value for column '{header_name}'. Upload an "
                "Excel file BEFORE starting the recorder so the live form "
                "fills automatically (you'll be able to submit and "
                "continue recording on the next page)."
            )

    template = f"{{{{{header_name}}}}}" if header_name else value
    step = _build_fill_step(selector, template)
    sess.steps.append(step)
    sess.steps.append(_build_wait(800))
    return {"recorded": True, "step": step, "header_name": header_name, **extra}


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


async def group_last_as_random(
    sess: RecorderSession,
    count: int,
    texts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build & append one random-pick step.

    Two input modes:
      1. Legacy (click-to-pool): caller has clicked N candidate buttons
         in mode=random and they're sitting in ``sess._pending_random``.
         Pass ``texts=None`` and we'll use the last ``count`` of them.
      2. NEW (checklist flow, 2026-01): caller passes ``texts`` directly
         (selected from /detect-clickables) — we skip the pending list
         entirely. This avoids the user having to click each button
         on the live page (which would navigate it forward and break
         the recording).

    Either way, the resulting JSON step is identical and the playback
    behaviour (``_build_random_pick_evaluate``) is unchanged.
    """
    sess.touch()
    # ── 2026-01 checklist path ─────────────────────────────────────
    if texts:
        take = [str(t).strip() for t in texts if str(t).strip()]
        if not take:
            return {"recorded": False, "error": "No non-empty texts supplied"}
    else:
        pending = getattr(sess, "_pending_random", None) or []
        if not pending:
            return {"recorded": False, "error": "No pending random elements — use mode=random click first OR pass texts directly"}
        take = pending[-int(count):]
    step = _build_random_pick_evaluate(take)
    sess.steps.append(step)
    sess.steps.append(_build_wait(2000))
    sess.steps.append(_build_wait_load(60000))
    sess.steps.append(_build_wait(2500))
    sess._pending_random = []
    return {"recorded": True, "step": step, "items": take}


async def detect_clickables(sess: RecorderSession) -> Dict[str, Any]:
    """Detect every visible clickable element on the current page and
    return their visible text + bounding box. Used by the new "Random
    Pick" checklist UI so the user doesn't have to click each candidate
    button on the live page (which would navigate it away).

    Selectors covered: <a>, <button>, <input type=submit/button/reset>,
    elements with role=button / role=link / role=checkbox / role=radio,
    <label> elements, and any element with onclick / cursor:pointer.

    De-duped by trimmed text + tag (so the same "Continue" button isn't
    listed twice). Hidden (display:none / visibility:hidden / zero-size)
    elements are skipped.
    """
    sess.touch()
    async with sess.lock:
        try:
            items = await sess.page.evaluate(
                r"""
                () => {
                    const SEL = 'a, button, input[type=submit], input[type=button], input[type=reset], [role=button], [role=link], [role=checkbox], [role=radio], label, [onclick]';
                    const candidates = Array.from(document.querySelectorAll(SEL));
                    // Add elements with cursor:pointer that haven't already
                    // been picked up by the selector above.
                    const all = Array.from(document.body ? document.body.querySelectorAll('*') : []);
                    for (const el of all) {
                        if (candidates.indexOf(el) !== -1) continue;
                        try {
                            const cs = window.getComputedStyle(el);
                            if (cs && cs.cursor === 'pointer' && el.children.length === 0) {
                                candidates.push(el);
                            }
                        } catch (e) {}
                    }
                    const seen = new Set();
                    const out = [];
                    for (const el of candidates) {
                        try {
                            const cs = window.getComputedStyle(el);
                            if (!cs || cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') < 0.05) continue;
                            const r = el.getBoundingClientRect();
                            if (r.width < 4 || r.height < 4) continue;
                            // Off-screen (above viewport top by more than its own height)? Still include — user may scroll.
                            const rawText = (el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim();
                            if (!rawText) continue;
                            const text = rawText.slice(0, 200);
                            const tag = el.tagName;
                            const key = tag + '||' + text.toLowerCase();
                            if (seen.has(key)) continue;
                            seen.add(key);
                            out.push({
                                text: text,
                                tag: tag,
                                role: el.getAttribute('role') || '',
                                type: el.type || '',
                                href: (el.getAttribute && el.getAttribute('href')) || '',
                                x: Math.round(r.left + r.width / 2),
                                y: Math.round(r.top + r.height / 2),
                                width: Math.round(r.width),
                                height: Math.round(r.height),
                                top: Math.round(r.top),
                            });
                        } catch (e) {}
                    }
                    // Sort by visual order (top → bottom, left → right)
                    out.sort((a, b) => (a.top - b.top) || (a.x - b.x));
                    return out;
                }
                """
            )
        except Exception as e:  # noqa: BLE001
            return {"items": [], "error": f"detect failed: {type(e).__name__}: {e}"}
    return {"items": items or [], "count": len(items or [])}


def remove_step(sess: RecorderSession, index: int) -> Dict[str, Any]:
    sess.touch()
    if 0 <= index < len(sess.steps):
        removed = sess.steps.pop(index)
        return {"removed": removed, "remaining": len(sess.steps)}
    return {"removed": None, "remaining": len(sess.steps)}


def move_step(sess: RecorderSession, index: int, direction: str) -> Dict[str, Any]:
    """Move a step up or down in the recorded list. `direction` ∈ {'up','down'}.
    Returns the swap result + new index, or no-op if out of bounds."""
    sess.touch()
    n = len(sess.steps)
    if not (0 <= index < n):
        return {"moved": False, "reason": "index out of range"}
    target = index - 1 if direction == "up" else index + 1
    if not (0 <= target < n):
        return {"moved": False, "reason": "edge"}
    sess.steps[index], sess.steps[target] = sess.steps[target], sess.steps[index]
    return {"moved": True, "from": index, "to": target}


def duplicate_step(sess: RecorderSession, index: int) -> Dict[str, Any]:
    """Insert a deep copy of the step at `index` right after it."""
    sess.touch()
    if not (0 <= index < len(sess.steps)):
        return {"duplicated": False, "reason": "index out of range"}
    import copy as _copy
    clone = _copy.deepcopy(sess.steps[index])
    sess.steps.insert(index + 1, clone)
    return {"duplicated": True, "step": clone, "new_index": index + 1}


def rename_step(sess: RecorderSession, index: int, name: str) -> Dict[str, Any]:
    """Set / update the `name` field of an existing step (purely a label,
    surfaced by the UI + Live Activity panel during the job run)."""
    sess.touch()
    if not (0 <= index < len(sess.steps)):
        return {"renamed": False, "reason": "index out of range"}
    sess.steps[index]["name"] = (name or "").strip() or None
    return {"renamed": True, "name": sess.steps[index].get("name")}


async def press_key(sess: RecorderSession, key: str) -> Dict[str, Any]:
    """Send a single keyboard key press to the page (Enter, Tab, Escape,
    Backspace, ArrowLeft, ArrowRight, ArrowUp, ArrowDown, PageDown, etc.).
    Step is recorded so it replays during the RUT run."""
    sess.touch()
    if sess.state != "ready" or not sess.page:
        return {"recorded": False, "error": f"Session not ready ({sess.state})"}
    safe_key = (key or "").strip()
    if not safe_key:
        return {"recorded": False, "error": "key required"}
    try:
        await sess.page.keyboard.press(safe_key)
    except Exception as e:
        return {"recorded": False, "error": f"Key press failed: {e}"}
    step = {"action": "press", "key": safe_key}
    sess.steps.append(step)
    return {"recorded": True, "step": step}


async def hover_at(sess: RecorderSession, x: int, y: int) -> Dict[str, Any]:
    """Hover the mouse over an (x,y) page coordinate. Useful for menus
    that only reveal on hover. Step is recorded so it replays."""
    sess.touch()
    if sess.state != "ready" or not sess.page:
        return {"recorded": False, "error": f"Session not ready ({sess.state})"}
    try:
        await sess.page.mouse.move(int(x), int(y))
    except Exception as e:
        return {"recorded": False, "error": f"Hover failed: {e}"}
    step = {
        "action": "evaluate",
        "script": (
            "(function(){var el=document.elementFromPoint("
            + str(int(x)) + "," + str(int(y)) +
            ");if(el){el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
            "el.dispatchEvent(new MouseEvent('mouseenter',{bubbles:true}));}})();"
        ),
        "name": f"Hover @ ({int(x)},{int(y)})",
    }
    sess.steps.append(step)
    return {"recorded": True, "step": step}


async def wait_for_selector(
    sess: RecorderSession, selector: str, timeout_ms: int = 15000
) -> Dict[str, Any]:
    """Wait until a CSS selector becomes visible on the page (max
    `timeout_ms`). Useful when an offer takes a variable time to load
    a CTA. Step is recorded — RUT will wait the same way at replay."""
    sess.touch()
    if sess.state != "ready" or not sess.page:
        return {"recorded": False, "error": f"Session not ready ({sess.state})"}
    sel = (selector or "").strip()
    if not sel:
        return {"recorded": False, "error": "selector required"}
    timeout_ms = max(500, min(int(timeout_ms or 15000), 120000))
    try:
        await sess.page.wait_for_selector(sel, state="visible", timeout=timeout_ms)
    except Exception as e:
        return {"recorded": False, "error": f"Selector did not appear within {timeout_ms}ms: {e}"}
    step = {"action": "wait_for_selector", "selector": sel, "timeout": timeout_ms}
    sess.steps.append(step)
    return {"recorded": True, "step": step}


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
