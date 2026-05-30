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



# ── 2026-05: Rich element metadata capture for robust replay ────────────
# Every recorded step that targets a specific element (click form_fill,
# check, select, fill) now ALSO embeds a `fallbacks` dict describing the
# element by multiple complementary strategies:
#   • xpath_stable — xpath using stable attrs (id, name) where available,
#                    so a sibling reorder elsewhere on the page can't
#                    break it.
#   • xpath_abs    — full root-to-element xpath (fragile but precise
#                    when the page structure is identical to recording).
#   • text         — visible text content (trimmed, ≤80 chars).
#   • tag          — element tag (button, input, etc.) — used to scope
#                    text-based fallbacks so we don't accidentally
#                    match a stray <div> with the same words.
#   • attrs        — {id, name, type, placeholder, aria-label, role,
#                    data-testid, autocomplete, …} all surviving attrs.
#
# At REPLAY time, real_user_traffic.py's `_step_fallbacks(step)` reads
# this dict and FEEDS each strategy as an additional selector
# alternative into `_smart_wait_for_selector`. So the resolution
# pipeline becomes:
#   1. exact selector (recorded)
#   2. step.fallbacks.xpath_stable
#   3. step.fallbacks.xpath_abs
#   4. attribute-derived combos
#   5. text-based scoped to tag
#   6. user-aliased selectors (self-healing store)
#   7. token-derived & field-type fallbacks (legacy)
#
# Existing recordings WITHOUT a `fallbacks` dict keep working exactly
# as before — pure additive, zero-risk to old JSONs.
_RICH_ELEMENT_CAPTURE_JS = r"""
([x,y]) => {
  var el = document.elementFromPoint(x, y);
  if (!el) return null;

  // Walk up to find a meaningful clickable ancestor (same heuristic
  // as the legacy capture so behavior is identical to before).
  var depth = 0;
  while (el && el.parentElement && el.parentElement.tagName !== 'BODY' && depth < 5) {
    var txt = ((el.innerText || el.textContent || el.value || '') + '').trim();
    var isInteractive = /^(A|BUTTON|INPUT|SELECT|TEXTAREA|LABEL)$/.test(el.tagName);
    if (isInteractive || (txt.length > 0 && txt.length < 400)) break;
    el = el.parentElement;
    depth++;
  }

  var r = el.getBoundingClientRect();
  var text = ((el.innerText || el.textContent || el.value || '') + '').replace(/\s+/g, ' ').trim().slice(0, 200);

  // Capture ALL attributes so the replay can try [data-testid=x],
  // [role=button], etc. without us hardcoding a whitelist that misses
  // tomorrow's custom-attr. Values capped at 120 chars.
  var attrs = {};
  if (el.attributes) {
    for (var i = 0; i < el.attributes.length; i++) {
      var a = el.attributes[i];
      if (a && a.name) {
        var v = (a.value || '') + '';
        if (v.length > 120) v = v.slice(0, 120);
        attrs[a.name] = v;
      }
    }
  }

  // Absolute xpath
  function absXPath(e) {
    if (e.nodeType !== 1) return '';
    var parts = [];
    while (e && e.nodeType === 1 && e.tagName !== 'HTML') {
      var idx = 1, sib = e.previousElementSibling;
      while (sib) {
        if (sib.tagName === e.tagName) idx++;
        sib = sib.previousElementSibling;
      }
      parts.unshift(e.tagName.toLowerCase() + '[' + idx + ']');
      e = e.parentElement;
    }
    return '/html/' + parts.join('/');
  }

  // Stable xpath — anchors on the FIRST stable attribute encountered
  // walking from the element toward <html>. Falls back to '' if none.
  function stableXPath(e) {
    if (e.nodeType !== 1) return '';
    var STABLE_ATTRS = ['id', 'data-testid', 'name', 'aria-label', 'placeholder'];
    var node = e;
    var suffix = '';
    while (node && node.nodeType === 1 && node.tagName !== 'HTML') {
      for (var k = 0; k < STABLE_ATTRS.length; k++) {
        var att = STABLE_ATTRS[k];
        var val = node.getAttribute && node.getAttribute(att);
        if (val) {
          val = val.replace(/'/g, "&apos;");
          var head = '//' + node.tagName.toLowerCase() + "[@" + att + "='" + val + "']";
          return head + suffix;
        }
      }
      var idx = 1, sib = node.previousElementSibling;
      while (sib) {
        if (sib.tagName === node.tagName) idx++;
        sib = sib.previousElementSibling;
      }
      suffix = '/' + node.tagName.toLowerCase() + '[' + idx + ']' + suffix;
      node = node.parentElement;
    }
    return '';
  }

  function siblingIndex(e) {
    var idx = 1, sib = e.previousElementSibling;
    while (sib) {
      if (sib.tagName === e.tagName) idx++;
      sib = sib.previousElementSibling;
    }
    return idx;
  }

  return {
    tag: el.tagName,
    text: text,
    placeholder: el.getAttribute && el.getAttribute('placeholder'),
    name: el.getAttribute && el.getAttribute('name'),
    id: el.id || '',
    type: el.type || '',
    aria: el.getAttribute && el.getAttribute('aria-label'),
    x: r.left + r.width / 2,
    y: r.top + r.height / 2,
    xpath_abs: absXPath(el),
    xpath_stable: stableXPath(el),
    attrs: attrs,
    nth_of_type: siblingIndex(el),
    tag_lower: el.tagName.toLowerCase(),
  };
}
"""


def _build_fallbacks(info: Dict[str, Any]) -> Dict[str, Any]:
    """Distil rich element-capture `info` into a compact `fallbacks`
    dict that the replay engine reads via `_step_fallbacks()`.

    Keep it tight (≤ ~600 bytes typical) so JSON exports stay readable.
    Returns `{}` if `info` is missing or has no usable fields — the
    caller can attach it unconditionally (RUT engine treats empty dict
    same as absent).
    """
    if not isinstance(info, dict):
        return {}
    fb: Dict[str, Any] = {}

    xs = (info.get("xpath_stable") or "").strip()
    xa = (info.get("xpath_abs") or "").strip()
    if xs:
        fb["xpath"] = xs
    if xa and xa != xs:
        fb["xpath_abs"] = xa

    txt = (info.get("text") or "").strip()
    if txt and 3 <= len(txt) <= 80:
        fb["text"] = txt

    tag = (info.get("tag") or "").lower()
    if tag:
        fb["tag"] = tag

    nth = info.get("nth_of_type")
    if isinstance(nth, int) and nth > 0:
        fb["nth"] = nth

    attrs_in = info.get("attrs") or {}
    if isinstance(attrs_in, dict) and attrs_in:
        keep_keys = (
            "id", "name", "data-testid", "data-test", "data-cy",
            "data-qa", "data-id", "placeholder", "aria-label",
            "aria-describedby", "role", "type", "autocomplete",
            "for", "href", "title", "alt",
        )
        a: Dict[str, str] = {}
        for k in keep_keys:
            v = attrs_in.get(k)
            if isinstance(v, str) and v and len(v) <= 120:
                a[k] = v
        if a:
            fb["attrs"] = a

    return fb


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
    # 2026-01 (additive): live progress feed for live_test. Polled by the
    # frontend at ~400ms intervals to show real-time step execution
    # ("step #5 click button.submit — running…", "step #5 ok in 230ms").
    # Reset at the start of every live_test invocation.
    live_progress: List[Dict[str, Any]] = field(default_factory=list)
    live_progress_running: bool = False
    live_progress_started_at: Optional[float] = None
    live_progress_finished_at: Optional[float] = None
    # ── 2026-05: Auto-fix history for Undo support ──
    # Each entry: {kind, at_step, summary, applied_at, snapshot_before}
    # where snapshot_before is a deep-copy of `steps` BEFORE that fix
    # was applied. Capped at 20 entries (LRU) so memory stays bounded
    # even for sessions where the user spams Auto-fix-all repeatedly.
    fix_history: List[Dict[str, Any]] = field(default_factory=list)

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

    # 2026-01 — initial auto wait_for_load(60000) + wait(2000) removed
    # per user request. The runtime engine's own page.goto(target_url,
    # wait_until="domcontentloaded") already ensures the page is loaded
    # before playback begins; pre-pending these two steps to the recorded
    # JSON only burned watchdog seconds without adding reliability.
    # Users who want an explicit settle delay can insert a wait step
    # from the recorder UI right after starting.

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


def list_user_sessions(user_id: str) -> List[Dict[str, Any]]:
    """Return metadata for all active sessions belonging to this user.
    Used by the UI to render the "Active Sessions" panel so the user can
    see which recorders are running, switch between them, or stop the
    ones they no longer need (frees up slots toward the
    MAX_CONCURRENT_SESSIONS=5 cap).
    """
    now = time.time()
    out: List[Dict[str, Any]] = []
    for sid, s in _SESSIONS.items():
        if s.user_id != user_id:
            continue
        # Try to read current page url (cheap, no awaits). Falls back to
        # the initial session URL if the live page isn't available yet.
        page_url = ""
        page_title = ""
        try:
            if s.page is not None:
                page_url = s.page.url or ""
        except Exception:
            page_url = ""
        out.append({
            "session_id": sid,
            "url": s.url,
            "current_url": page_url or s.url,
            "title": page_title,
            "state": s.state,
            "error_message": s.error_message or "",
            "step_count": len(s.steps),
            "elapsed_seconds": int(now - s.created_at),
            "idle_seconds": int(now - s.last_activity),
            "viewport": {"width": s.viewport[0], "height": s.viewport[1]},
        })
    # Newest first so the most recent session is on top.
    out.sort(key=lambda x: x["elapsed_seconds"])
    return out


def get_global_session_stats() -> Dict[str, int]:
    """Lightweight global counters so the UI can show "X/5 in use"."""
    return {
        "total_running": len(_SESSIONS),
        "max_concurrent": MAX_CONCURRENT_SESSIONS,
    }


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
        # 2026-05 — Use the shared `_RICH_ELEMENT_CAPTURE_JS` so click,
        # form_fill, dropdown and check all get the same xpath_stable /
        # xpath_abs / attrs / nth_of_type / tag metadata. The
        # `_build_fallbacks(info)` helper turns this into the
        # backward-compatible `fallbacks` dict that the RUT replay
        # engine reads (older recordings without `fallbacks` keep
        # working — `_step_fallbacks` returns [] for them).
        info = await sess.page.evaluate(
            _RICH_ELEMENT_CAPTURE_JS,
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
        # 2026-05: `check` mode handles its OWN click via the resolution
        # JS below (label→checkbox walk) so the live page reflects the
        # actual toggled state — a blind mouse.click() at coords could
        # land on a hidden input and do nothing.
        if mode not in ("random", "check"):
            try:
                await sess.page.mouse.click(info["x"], info["y"])
            except Exception:
                pass

        # For dropdown mode we also need to pull the option list out of
        # the element (or its nearest <select> ancestor) BEFORE leaving
        # the page lock so the DOM is in the state the user just saw.
        #
        # 2026-05 — Also DETECT whether the <select> is hidden behind a
        # custom dropdown UI (Bootstrap-Select, Select2, Chosen, React-
        # Select, etc). When detected we add `state: "attached"` and
        # `prefer_js_set: true` hints to the recorded `select` step so
        # the RUT replay engine skips the (futile) visibility wait and
        # goes straight to the JS-driven select path. This eliminates
        # the 5s+ pre-wait per dropdown for every visit of every job
        # using this automation.
        dropdown_options: List[Dict[str, str]] = []
        dropdown_selector: str = ""
        dropdown_wrapper_kind: str = ""   # "bootstrap-select"|"select2"|"chosen"|"react-select"|""
        dropdown_is_hidden: bool = False
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

                        // ── Detect hidden / custom-UI wrapping ──
                        var cs = window.getComputedStyle(sel);
                        var rect = sel.getBoundingClientRect();
                        var isHidden = (
                            cs.display === 'none' ||
                            cs.visibility === 'hidden' ||
                            parseFloat(cs.opacity || '1') < 0.05 ||
                            rect.width < 4 || rect.height < 4 ||
                            rect.left < -2000 || rect.top < -2000
                        );
                        // Climb ancestors looking for known wrapper class names
                        var wrapperKind = '';
                        var p = sel.parentElement;
                        var depth = 0;
                        while(p && depth < 6 && !wrapperKind){
                            var c = (p.className || '') + '';
                            var cl = c.toLowerCase();
                            if(/(^|\\s)bootstrap-select(\\s|$|--)/.test(cl)) wrapperKind = 'bootstrap-select';
                            else if(/select2(-container|-selection|-hidden|-dropdown)/.test(cl)) wrapperKind = 'select2';
                            else if(/(^|\\s)chosen-container/.test(cl)) wrapperKind = 'chosen';
                            else if(/react-select__(control|container|value-container)/.test(cl)) wrapperKind = 'react-select';
                            else if(/(^|\\s)nice-select(\\s|$)/.test(cl)) wrapperKind = 'nice-select';
                            else if(/(^|\\s)selectric/.test(cl)) wrapperKind = 'selectric';
                            else if(/(^|\\s)multiselect(\\s|$|-)/.test(cl)) wrapperKind = 'multiselect';
                            p = p.parentElement; depth++;
                        }
                        // If <select> is hidden but no known wrapper class, still
                        // treat as custom UI — the user clearly clicked SOMETHING
                        // visible above the hidden select.
                        if(isHidden && !wrapperKind) wrapperKind = 'generic-custom';

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
                            isHidden: isHidden,
                            wrapperKind: wrapperKind,
                        };
                    }""",
                    [int(x), int(y)],
                )
                if opts and opts.get("options"):
                    dropdown_options = opts["options"]
                    dropdown_is_hidden = bool(opts.get("isHidden"))
                    dropdown_wrapper_kind = (opts.get("wrapperKind") or "") if dropdown_is_hidden else (opts.get("wrapperKind") or "")
                    # Build the same selector style as form_fill so the
                    # downstream `select` action can find the element.
                    dropdown_selector = _make_selector_for_input({
                        "tag": "SELECT",
                        "name": opts.get("name") or "",
                        "id": opts.get("id") or "",
                    })
            except Exception:
                pass

        # ── 2026-05: `check` mode — resolve actual checkbox + toggle it live ──
        # The user clicks the VISIBLE checkbox UI (which may be the
        # underlying <input type=checkbox>, OR a wrapping <label>, OR
        # a CSS-styled sibling <span>/<div>). We resolve to the real
        # <input type=checkbox> via three strategies:
        #   1. Clicked element IS the checkbox.
        #   2. Clicked element is a <label for="X"> — find element by id.
        #   3. Clicked element is INSIDE a <label> that wraps a checkbox.
        # Then we toggle it via the wrapping label.click() (proper user
        # flow) so the live preview shows the checked state.
        check_info: Dict[str, Any] = {}
        if mode == "check":
            try:
                cbinfo = await sess.page.evaluate(
                    """([x,y])=>{
                        var el = document.elementFromPoint(x, y);
                        if(!el) return null;
                        var cb = null;
                        // Strategy 1: direct hit
                        if(el.tagName==='INPUT' && el.type==='checkbox') cb = el;
                        // Strategy 2: <label for="X">
                        if(!cb && el.tagName==='LABEL' && el.htmlFor) {
                            cb = document.getElementById(el.htmlFor);
                            if(cb && cb.type !== 'checkbox') cb = null;
                        }
                        // Strategy 3: walk up to nearest <label>, find inner checkbox
                        if(!cb) {
                            var lbl = el.closest && el.closest('label');
                            if(lbl) {
                                cb = lbl.querySelector('input[type=checkbox]');
                                if(!cb && lbl.htmlFor) {
                                    var found = document.getElementById(lbl.htmlFor);
                                    if(found && found.type === 'checkbox') cb = found;
                                }
                            }
                        }
                        // Strategy 4: walk up looking for any checkbox child
                        if(!cb) {
                            var p = el;
                            for(var i=0; i<4 && p; i++) {
                                var found = p.querySelector && p.querySelector('input[type=checkbox]');
                                if(found) { cb = found; break; }
                                p = p.parentElement;
                            }
                        }
                        if(!cb) return null;
                        // Toggle via the proper user-flow: click wrapping label
                        var lbl = cb.closest('label');
                        var beforeChecked = cb.checked;
                        try {
                            if(lbl) lbl.click();
                            if(cb.checked === beforeChecked) cb.click();
                        } catch(e) {}
                        return {
                            id: cb.id || '',
                            name: cb.getAttribute('name') || '',
                            class: cb.className || '',
                            checked: cb.checked,
                            tag: 'INPUT',
                            type: 'checkbox',
                            text: (lbl ? (lbl.innerText || '').trim().slice(0, 80) : ''),
                        };
                    }""",
                    [int(x), int(y)],
                )
                if cbinfo:
                    check_info = cbinfo
                    # Override `info` so build-step gets the resolved
                    # checkbox attributes (not the wrapping label/span).
                    info["id"] = cbinfo.get("id") or info.get("id") or ""
                    info["name"] = cbinfo.get("name") or info.get("name") or ""
                    info["tag"] = "INPUT"
                    info["type"] = "checkbox"
                    if cbinfo.get("text"):
                        info["text"] = cbinfo["text"]
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
            # 2026-05 — attach rich fallbacks so RUT replay can rescue
            # this fill if `sel` stops matching (renamed id/name, etc.)
            _fb = _build_fallbacks(info)
            if _fb:
                step["fallbacks"] = _fb
            # 2026-05 — also stash the fallbacks under this selector so
            # the subsequent /type call (which doesn't re-capture rich
            # metadata) can attach the SAME fallbacks to its fill step.
            try:
                if not hasattr(sess, "_form_fill_fallbacks"):
                    sess._form_fill_fallbacks = {}  # type: ignore[attr-defined]
                if _fb:
                    sess._form_fill_fallbacks[sel] = _fb  # type: ignore[attr-defined]
            except Exception:
                pass
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
        # 2026-05: Also surface custom-UI detection hints so the picker
        # shows a badge ("Bootstrap-Select detected") and so bind_dropdown
        # can stamp the right state/JS hints onto the recorded step.
        step = None
        extra["selector"] = dropdown_selector or _make_selector_for_input(info)
        extra["options"] = dropdown_options
        if dropdown_wrapper_kind:
            extra["wrapper_kind"] = dropdown_wrapper_kind
        # 2026-05 — stash fallbacks for the upcoming /dropdown-bind call
        # so the recorded `select` step gets attribute/xpath/text rescue
        # paths same as click & check do.
        try:
            _fb_dd = _build_fallbacks(info)
            if _fb_dd:
                if not hasattr(sess, "_pending_dropdown_fallbacks"):
                    sess._pending_dropdown_fallbacks = {}  # type: ignore[attr-defined]
                sess._pending_dropdown_fallbacks[extra["selector"]] = _fb_dd  # type: ignore[attr-defined]
        except Exception:
            pass
        if dropdown_is_hidden:
            extra["is_hidden_select"] = True
            # Stash on the session so /dropdown-bind picks it up
            sess._pending_dropdown_meta = {  # type: ignore[attr-defined]
                "selector": dropdown_selector,
                "wrapper_kind": dropdown_wrapper_kind,
                "is_hidden_select": True,
            }
        else:
            # Clear any stale meta from a previous dropdown click
            try:
                if hasattr(sess, "_pending_dropdown_meta"):
                    delattr(sess, "_pending_dropdown_meta")
            except Exception:
                pass
        if not dropdown_options:
            extra["warning"] = (
                "No <select> element found at that point — pick the dropdown "
                "control itself (the one that opens the option list)."
            )
    elif mode == "check":
        # 2026-05: dedicated checkbox recording. The user clicked the
        # visible UI (label / styled span / the input itself); we
        # already resolved to the real <input type=checkbox> above and
        # toggled it via wrapping-label click in the live page.
        # Build a robust selector preferring #id → [name="X"] →
        # input[type=checkbox][name="X"]. The RUT engine routes this
        # through _smart_check_with_fallback at replay time, which
        # additionally handles CSS-styled hidden checkboxes (display:none
        # with sibling-span proxy) — so even if the page changes its
        # ID after recording, the visit will still succeed.
        sel: str = ""
        if info.get("id"):
            sel = f"#{info['id']}"
        elif info.get("name"):
            sel = f"input[name='{info['name']}']"
        else:
            sel = "input[type='checkbox']"  # last-resort
        extra["selector"] = sel
        extra["checked_after"] = bool(check_info.get("checked")) if check_info else None
        if not check_info:
            extra["warning"] = (
                "No checkbox found at that point — click directly on the "
                "checkbox (or the label / red box around it)."
            )
            step = None
        else:
            step = {
                "action": "check",
                "selector": sel,
                "timeout": 8000,
                "optional": True,
            }
            # 2026-05 — attach rich fallbacks so check step survives
            # selector drift between recording and replay.
            _fb_chk = _build_fallbacks(info)
            if _fb_chk:
                step["fallbacks"] = _fb_chk
    elif mode == "final":
        # Captured separately by /mark-final endpoint
        step = None
    else:
        step = _build_text_click_evaluate(text) if text else None

    if step is not None:
        sess.steps.append(step)
        # 2026-01 — auto waits removed per user request. Earlier this added
        # wait(1500) + wait_for_load(60000) + wait(2000) after every click,
        # which combined with the stuck-watchdog (60s URL-change threshold)
        # caused legitimate visits to be aborted while waiting for the
        # page-load event that never fires between clicks on the same form.
        # If a click triggers a real navigation, the next action in the
        # recorded sequence will naturally wait via its own selector
        # resolution / fill timeout. For deliberate post-click pauses the
        # user can manually add a wait step from the recorder UI
        # (Insert → Wait / Wait for page load).

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


# ── 2026-05: User-requested explicit "close browser" recording step ──
# Why this exists:
#   The user noticed visits in the Live Visual Grid keep their browser
#   tile populated for a few seconds after the final recorded step,
#   while the per-visit Playwright context is still being torn down by
#   the outer finally-block. On medium-RAM VPSes this stacks (each
#   visit holds ~150-300 MB until its finally fires), so concurrent
#   workers were sometimes starved of RAM and the next worker booted
#   slowly. With this `close` step the operator can mark "browser
#   work is done here, free it NOW" at any point in the recording —
#   typically right after the conversion-confirmation screenshot.
#   The RUT runner already handles this action (see real_user_traffic.
#   py / `elif action in ("close", "close_browser", ...)`).
#
# Notes:
#   • optional=False on purpose — close is a final step; if it can't
#     run (e.g. page already gone), we WANT to know about it in the
#     diagnostics so the recording isn't silently incomplete.
#   • No selector / no timeout — it's a pure browser-lifecycle action.
async def add_close_browser_step(sess: RecorderSession) -> Dict[str, Any]:
    """Insert a 'close' action step at the current position. The RUT
    runner will close the per-visit page+context as soon as it reaches
    this step, releasing RAM/proxy slot for the next worker."""
    sess.touch()
    step = {
        "action": "close",
        # No timeout/selector — pure lifecycle step. Not marked optional
        # because if the runner can't reach it, the operator should see
        # it in the diagnostics report (silently skipping a close would
        # leak the very resource this step exists to free).
    }
    sess.steps.append(step)
    return {"recorded": True, "step": step}


async def live_test(
    sess: RecorderSession,
    sample_row: Optional[Dict[str, Any]] = None,
    fresh_page: bool = False,
    start_index: int = 0,
) -> Dict[str, Any]:
    """Run the current recorded steps end-to-end against the live page,
    returning per-step timing + ok/error + a static-analysis diagnostic
    summary. This is the "Run Live Test" button in the recorder.

    `start_index` (2026-01) — skip the first N steps and pick up replay
    from step `start_index` onwards. Powers the "Replay from here"
    button on the Live Test results panel: when step #15 fails, the
    user fixes it and re-runs from #15 — the browser is already on the
    correct page state (because the previous test got us there), so we
    DO NOT open a fresh page and we DO NOT execute steps 0..14 again.
    This makes the debug loop ~5-10× faster vs. re-running the whole
    automation each time.

    Strategy:
      • Open a fresh page (default) so we mirror what a RUT visit would
        actually see — fresh cookies, fresh DOM, fresh JS state. If the
        user wants to replay on the CURRENT page (e.g. to debug only
        the last few steps), they can pass fresh_page=False.
      • Substitute {{header}} placeholders with values from `sample_row`
        (defaults to the session's sample_row).
      • Reuse `_execute_automation_steps` with collect_timings=True so
        every step gets {idx, action, selector, ok, error, ms}.
      • Layer a static-analysis pass on the steps array for
        anti-patterns / wrapper-kind summary / top-3 slowest hints.

    Returns:
      {
        ok: bool,
        total_ms: int,
        executed_steps: int,
        error: str|None,
        step_results: [{idx, action, selector, ok, error, ms, optional, self_healed?}, ...],
        diagnostics: {
          slowest: [{idx, action, ms}, ...3],
          anti_patterns: [str, ...],
          wrapper_summary: {bootstrap-select: 3, ...} | {},
          recommendations: [str, ...],
        },
        final_url: str,
      }
    """
    sess.touch()
    if sess.state != "ready" or sess.page is None:
        return {"ok": False, "error": "Recorder session not ready"}
    if not sess.steps:
        return {"ok": False, "error": "No steps recorded yet — record at least one step before running Live Test."}

    # Lazy import to avoid the visual_recorder ↔ real_user_traffic
    # circular import at module-load time. real_user_traffic also
    # depends on small helpers in this module via runtime calls.
    try:
        from real_user_traffic import _execute_automation_steps
    except Exception as e:  # pragma: no cover
        return {"ok": False, "error": f"Engine import failed: {e}"}

    row = dict(sample_row or sess.sample_row or {})

    # 2026-01: "Replay from here" — slice steps when start_index > 0.
    # The browser stays on its current state (no fresh_page) so the
    # remaining steps pick up exactly where the previous run failed.
    # We re-index the per-step results back to the ORIGINAL indices
    # before returning so the UI panel highlights the right rows.
    full_steps = list(sess.steps)
    if start_index < 0:
        start_index = 0
    if start_index >= len(full_steps):
        return {"ok": False, "error": f"start_index {start_index} ≥ total steps {len(full_steps)}"}
    steps_to_run = full_steps[start_index:]
    if start_index > 0:
        # Forcing fresh_page=False — the WHOLE POINT of replay-from-here
        # is to preserve the post-failure browser state. Override any
        # accidental fresh_page=True from the caller.
        fresh_page = False

    # 2026-01 (additive): reset live-progress feed at the start of every
    # live_test invocation. The callback below appends one event per
    # step transition (running → ok / failed) so the UI can show a
    # live "step #N — running…" / "step #N ok in 230ms" feed.
    sess.live_progress = []
    sess.live_progress_running = True
    sess.live_progress_started_at = time.time()
    sess.live_progress_finished_at = None

    async def _progress_cb(event: Dict[str, Any]) -> None:
        try:
            # Re-map sliced idx back to ORIGINAL recording idx so the UI
            # highlights the right row when start_index > 0.
            if start_index > 0 and "idx" in event:
                try:
                    event = dict(event)
                    event["idx"] = int(event["idx"]) + start_index
                except (TypeError, ValueError):
                    pass
            sess.live_progress.append(event)
            # 2026-01: memory optimization — drop heavy screenshot_b64
            # payload from all but the most recent 8 events. UI only
            # ever shows the LATEST frame in the live view, so older
            # screenshots are dead weight. Keeps memory bounded
            # regardless of automation length.
            if len(sess.live_progress) > 8:
                for old in sess.live_progress[:-8]:
                    if old.get("screenshot_b64"):
                        old["screenshot_b64"] = ""  # strip image bytes
            # Cap event count — keep last 500 events.
            if len(sess.live_progress) > 500:
                sess.live_progress = sess.live_progress[-500:]
        except Exception:
            pass

    async with sess.lock:
        # Optionally open a fresh page for an honest end-to-end test.
        # We DO NOT close the recorder's existing page — the user is
        # mid-recording and switching back to it should still work.
        page = sess.page
        fresh_ctx = None
        fresh_page_obj = None
        if fresh_page and sess.context is not None:
            try:
                fresh_page_obj = await sess.context.new_page()
                if sess.url:
                    await fresh_page_obj.goto(sess.url, timeout=45000, wait_until="domcontentloaded")
                page = fresh_page_obj
            except Exception as e:
                # Fresh-page setup failed — fall back to current page so
                # the live-test still returns useful timing data.
                if fresh_page_obj is not None:
                    try:
                        await fresh_page_obj.close()
                    except Exception:
                        pass
                fresh_page_obj = None
                page = sess.page
                logger.warning(f"[live-test] fresh-page setup failed, using recorder page: {e}")

        try:
            res = await _execute_automation_steps(
                page=page,
                row=row,
                steps=steps_to_run,
                skip_captcha=True,
                self_heal=False,  # IMPORTANT: no AI healing during test — user wants to see RAW failures
                collect_timings=True,
                user_id=sess.user_id,   # enable self-healing aliases (2026-01)
                on_step_progress=_progress_cb,  # 2026-01: real-time step feed
            )
        except Exception as e:
            res = {"status": "failed", "error": f"Live test crashed: {e}", "executed_steps": 0, "step_results": []}
        finally:
            # Best-effort close of the fresh page (if any)
            if fresh_page_obj is not None:
                try:
                    await fresh_page_obj.close()
                except Exception:
                    pass
            # 2026-01: mark live progress feed as finished
            sess.live_progress_running = False
            sess.live_progress_finished_at = time.time()

        final_url = ""
        try:
            final_url = sess.page.url or ""
        except Exception:
            pass

    # ── Layer the static-analysis diagnostic pass on top of timings ──
    step_results = res.get("step_results") or []

    # 2026-01: when start_index > 0 ("Replay from here"), the runtime
    # indices in step_results are 0..N relative to the sliced steps —
    # re-map them to the ORIGINAL recording's indices so the UI shows
    # the right rows highlighted in red/green.
    if start_index > 0:
        for sr_item in step_results:
            if isinstance(sr_item, dict) and "idx" in sr_item:
                try:
                    sr_item["idx"] = int(sr_item["idx"]) + start_index
                except (TypeError, ValueError):
                    pass

    diagnostics = analyse_steps(sess.steps, step_results)

    # Same re-map for failed_at_idx
    failed_at = res.get("failed_at_idx")
    if failed_at is not None and start_index > 0:
        try:
            failed_at = int(failed_at) + start_index
        except (TypeError, ValueError):
            pass

    return {
        "ok": res.get("status") == "ok",
        "status": res.get("status"),
        "error": res.get("error"),
        "executed_steps": res.get("executed_steps", 0),
        "total_ms": res.get("total_ms"),
        "step_results": step_results,
        "diagnostics": diagnostics,
        "final_url": final_url,
        "failed_at_idx": failed_at,
        "total_steps": len(sess.steps),
        "fresh_page": bool(fresh_page),
        "start_index": start_index,
    }


def analyse_steps(
    steps: List[Dict[str, Any]],
    step_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Smart Replay Diagnostics — static analysis on the steps array,
    optionally combined with runtime per-step timings.

    Detects:
      • Top-3 slowest steps (if runtime timings provided)
      • Anti-patterns:
          - click → fill/select on different selector with no wait
          - wait_for_selector state="visible" without wrapper hint
            (dropdown landmines from older recordings)
          - long sequence with no screenshot for debug visibility
          - hard wait of >5000ms (flag for replacement with
            wait_for_load_state or wait_for_selector)
          - select step on dropdown without match_by clarification
      • Wrapper-kind summary (count of bootstrap-select / select2 etc)
      • Recommendations (actionable, one-liner each)
    """
    steps = list(steps or [])
    sr = list(step_results or [])

    # ── Wrapper-kind summary ─────────────────────────────────────────
    wrapper_summary: Dict[str, int] = {}
    for s in steps:
        wk = (s.get("wrapper_kind") or "").strip()
        if wk:
            wrapper_summary[wk] = wrapper_summary.get(wk, 0) + 1
    native_selects = sum(1 for s in steps if (s.get("action") == "select") and not s.get("wrapper_kind"))
    if native_selects > 0:
        wrapper_summary.setdefault("native", 0)
        wrapper_summary["native"] += native_selects

    # ── Top-3 slowest steps (needs runtime data) ─────────────────────
    slowest: List[Dict[str, Any]] = []
    if sr:
        ranked = sorted(
            [{"idx": r.get("idx"), "action": r.get("action"), "selector": r.get("selector"), "ms": int(r.get("ms") or 0)} for r in sr if r.get("ms") is not None],
            key=lambda r: r["ms"], reverse=True,
        )
        slowest = ranked[:3]

    # ── Anti-pattern detection ───────────────────────────────────────
    # Two-tier output:
    #   `anti` / `recs` — legacy string lists for the existing UI panels
    #   `findings`      — structured records the new Auto-fix endpoint
    #                     can act on. Each finding has:
    #                       kind:          stable id (e.g. "hard_wait_too_long")
    #                       at_step:       0-indexed step the fix targets
    #                       message:       human-readable description
    #                       fix_summary:   what the auto-fix WILL do
    #                       auto_fixable:  bool (false means user must re-record)
    #                       extra:         per-kind data the apply step needs
    anti: List[str] = []
    recs: List[str] = []
    findings: List[Dict[str, Any]] = []

    # 1. wait_for_selector state="visible" on a dropdown-like selector
    #    without wrapper_kind hint (legacy recording pattern → may 25s
    #    timeout on hidden-behind-custom-UI selects).
    for i, s in enumerate(steps):
        if s.get("action") == "wait_for_selector" and (s.get("state") or "visible") == "visible":
            sel = (s.get("selector") or "").lower()
            if any(k in sel for k in ("select", "month", "year", "day", "country", "state", "gender", "dob")):
                # Look at next non-wait step for a select action
                for j in range(i + 1, min(i + 3, len(steps))):
                    if steps[j].get("action") == "select":
                        msg = (
                            f"Step #{i+1} `wait_for_selector` with state=\"visible\" before a `select` — "
                            f"if the underlying <select> is hidden behind a custom dropdown, this could "
                            f"25s-timeout on replay."
                        )
                        rec = f"Switch step #{i+1}'s state from 'visible' to 'attached'."
                        anti.append(msg + " (Newer iteration-4 helper now auto-falls back, but re-recording stamps the hint cleanly.)")
                        recs.append(
                            f"Re-record step #{i+1}'s dropdown — the recorder now auto-detects custom UIs "
                            f"and stamps state=\"attached\" + wrapper_kind for instant matching."
                        )
                        findings.append({
                            "kind": "wait_for_visible_before_select",
                            "at_step": i,
                            "message": msg,
                            "fix_summary": rec,
                            "auto_fixable": True,
                            "extra": {},
                        })
                        break

    # 2. Click immediately followed by fill/select on a DIFFERENT selector,
    #    with no wait_for_selector / wait between them.
    for i, s in enumerate(steps[:-1]):
        if s.get("action") == "click":
            nxt = steps[i + 1]
            if nxt.get("action") in ("fill", "select", "type") and nxt.get("selector") and s.get("selector") != nxt.get("selector"):
                msg = (
                    f"Step #{i+1} click → step #{i+2} {nxt.get('action')} on a different selector with no "
                    f"wait between them. If the click triggers DOM changes (e.g. step-2 of a multi-page form), "
                    f"the next step may race the DOM update."
                )
                rec = f"Insert a wait_for_selector('{nxt.get('selector')}') between steps #{i+1} and #{i+2}."
                anti.append(msg)
                recs.append(f"Insert a 'Wait for navigation' or 'Wait for selector' between steps #{i+1} and #{i+2}.")
                findings.append({
                    "kind": "click_then_action_no_wait",
                    "at_step": i,
                    "message": msg,
                    "fix_summary": rec,
                    "auto_fixable": True,
                    "extra": {"next_selector": nxt.get("selector"), "next_action": nxt.get("action")},
                })

    # 3. Hard wait > 5s — usually a sign the recording is over-cautious
    for i, s in enumerate(steps):
        if s.get("action") == "wait":
            ms = int(s.get("ms") or 0)
            if ms > 5000:
                # Find the NEXT actionable step (fill/click/select/type/check)
                # so we can replace the hard wait with wait_for_selector on it.
                next_sel = None
                next_action_idx = None
                for j in range(i + 1, min(i + 6, len(steps))):
                    sj = steps[j]
                    if sj.get("action") in ("fill", "click", "select", "type", "check", "uncheck") and sj.get("selector"):
                        next_sel = sj.get("selector")
                        next_action_idx = j
                        break
                msg = f"Step #{i+1} hard wait of {ms}ms (>5s). Hard waits inflate every visit's runtime."
                if next_sel:
                    rec = f"Replace step #{i+1}'s hard {ms}ms wait with wait_for_selector('{next_sel}', timeout={max(8000, ms)}ms) — saves ~{(ms - 1500) / 1000:.1f}s per visit."
                    fixable = True
                else:
                    rec = f"Replace step #{i+1}'s hard wait with wait_for_selector — but no actionable step follows it within 5 steps. Manual review needed."
                    fixable = False
                anti.append(msg)
                recs.append(
                    f"Replace step #{i+1}'s hard wait with `wait_for_selector` on whatever element you're "
                    f"actually waiting for. Saves ~{(ms - 1500) / 1000:.1f}s per visit."
                )
                findings.append({
                    "kind": "hard_wait_too_long",
                    "at_step": i,
                    "message": msg,
                    "fix_summary": rec,
                    "auto_fixable": fixable,
                    "extra": {"ms": ms, "next_selector": next_sel, "next_action_idx": next_action_idx},
                })

    # 4. select step with no match_by — may match the wrong option on
    #    forms with duplicate labels (e.g. "Other" appearing twice).
    for i, s in enumerate(steps):
        if s.get("action") == "select" and not s.get("match_by"):
            msg = (
                f"Step #{i+1} select without match_by — defaults to 'label' which may match the wrong "
                f"option on forms with duplicate visible text."
            )
            rec = f"Set step #{i+1}'s match_by to 'label' explicitly."
            anti.append(msg)
            recs.append(f"Re-bind step #{i+1} via the dropdown picker so match_by is explicitly set.")
            findings.append({
                "kind": "select_missing_match_by",
                "at_step": i,
                "message": msg,
                "fix_summary": rec,
                "auto_fixable": True,
                "extra": {},
            })

    # 5. Long automation with no screenshots — hard to debug a failed visit
    if len(steps) >= 12 and not any(s.get("action") == "screenshot" for s in steps):
        # Find the LAST click (likely the submit) to insert screenshot just before it.
        last_click_idx = None
        for i in range(len(steps) - 1, -1, -1):
            if steps[i].get("action") == "click":
                last_click_idx = i
                break
        anti.append(
            "No screenshot steps in a long automation — when a visit fails in production "
            "you'll have nothing to look at."
        )
        recs.append(
            "Add a Screenshot step right before the submit click (Insert → Screenshot) so "
            "failed visits surface the form state."
        )
        if last_click_idx is not None:
            findings.append({
                "kind": "long_automation_no_screenshot",
                "at_step": last_click_idx,
                "message": "Long automation with no screenshot — failed visits won't have a debug image.",
                "fix_summary": f"Insert a screenshot step right before step #{last_click_idx+1} (the last click).",
                "auto_fixable": True,
                "extra": {"insert_before_idx": last_click_idx},
            })

    return {
        "slowest": slowest,
        "anti_patterns": anti,
        "wrapper_summary": wrapper_summary,
        "recommendations": recs,
        "findings": findings,
        "auto_fixable_count": sum(1 for f in findings if f.get("auto_fixable")),
        "total_steps": len(steps),
        "has_runtime_data": bool(sr),
    }


def apply_auto_fix(
    steps: List[Dict[str, Any]],
    kind: str,
    at_step: int,
    extra: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Apply a single auto-fix to a steps array. Returns the NEW steps
    array + a human-readable description of what was changed.

    Pure function — does not mutate the input array. Caller is
    responsible for persisting the result (e.g. `sess.steps = new_steps`).

    Supported kinds (must match analyse_steps `findings[*].kind`):
      • `wait_for_visible_before_select` — flip state="visible" → "attached"
      • `hard_wait_too_long` — replace hard wait with wait_for_selector
        on the next actionable step's selector
      • `select_missing_match_by` — set match_by="label" on the select step
      • `click_then_action_no_wait` — insert wait_for_selector for the
        following step's selector AFTER the click
      • `long_automation_no_screenshot` — insert a screenshot step
        immediately before the last click (the "submit")

    Returns (new_steps, change_summary). If kind is unknown or at_step
    is out of range, raises ValueError so the caller can surface a
    clear error to the user.
    """
    if not isinstance(steps, list) or at_step < 0 or at_step >= len(steps):
        raise ValueError(f"Invalid step index {at_step} for {len(steps)} steps")

    new_steps = [dict(s) for s in steps]  # deep-ish copy of each step dict
    extra = extra or {}

    if kind == "wait_for_visible_before_select":
        s = new_steps[at_step]
        if s.get("action") != "wait_for_selector":
            raise ValueError(f"Step #{at_step+1} is not a wait_for_selector — cannot apply fix")
        s["state"] = "attached"
        return new_steps, f"Step #{at_step+1}: changed state from 'visible' → 'attached' (handles dropdowns hidden behind custom UIs)."

    if kind == "hard_wait_too_long":
        s = new_steps[at_step]
        if s.get("action") != "wait":
            raise ValueError(f"Step #{at_step+1} is not a wait — cannot apply fix")
        next_sel = extra.get("next_selector")
        if not next_sel:
            # Re-derive from following steps in case extra is missing.
            for j in range(at_step + 1, min(at_step + 6, len(new_steps))):
                sj = new_steps[j]
                if sj.get("action") in ("fill", "click", "select", "type", "check", "uncheck") and sj.get("selector"):
                    next_sel = sj.get("selector")
                    break
        if not next_sel:
            raise ValueError(f"No actionable step follows step #{at_step+1} within 5 steps — fix not applicable.")
        original_ms = int(s.get("ms") or 0)
        # Replace in place with a wait_for_selector. Timeout: use the
        # original wait ms (capped at 25s) so a slow page that needed
        # 8s still gets up to 8s before failing — but the wait ends as
        # soon as the element appears, saving the rest.
        new_steps[at_step] = {
            "action": "wait_for_selector",
            "selector": next_sel,
            "state": "attached",
            "timeout": min(max(8000, original_ms), 25000),
            "optional": True,
            "_auto_fix": "hard_wait_too_long",
        }
        saved = max(0, (original_ms - 1500) / 1000)
        return new_steps, f"Step #{at_step+1}: replaced {original_ms}ms hard wait with wait_for_selector('{next_sel}', state='attached'). Saves up to ~{saved:.1f}s/visit."

    if kind == "select_missing_match_by":
        s = new_steps[at_step]
        if s.get("action") != "select":
            raise ValueError(f"Step #{at_step+1} is not a select — cannot apply fix")
        s["match_by"] = "label"
        return new_steps, f"Step #{at_step+1}: set match_by='label' explicitly (default behavior, but now defensive against future engine changes)."

    if kind == "click_then_action_no_wait":
        s = new_steps[at_step]
        if s.get("action") != "click":
            raise ValueError(f"Step #{at_step+1} is not a click — cannot apply fix")
        next_sel = extra.get("next_selector")
        if not next_sel:
            if at_step + 1 < len(new_steps):
                next_sel = new_steps[at_step + 1].get("selector")
        if not next_sel:
            raise ValueError(f"Next step has no selector — fix not applicable.")
        # Insert a wait_for_selector RIGHT AFTER the click.
        wait_step = {
            "action": "wait_for_selector",
            "selector": next_sel,
            "state": "attached",
            "timeout": 15000,
            "optional": True,
            "_auto_fix": "click_then_action_no_wait",
        }
        new_steps.insert(at_step + 1, wait_step)
        return new_steps, f"Inserted wait_for_selector('{next_sel}') right after step #{at_step+1}'s click. Eliminates the race condition."

    if kind == "long_automation_no_screenshot":
        # Insert a screenshot step BEFORE the at_step (which is the last click)
        screenshot_step = {
            "action": "screenshot",
            "name": f"before-step-{at_step+1}",
            "_auto_fix": "long_automation_no_screenshot",
        }
        new_steps.insert(at_step, screenshot_step)
        return new_steps, f"Inserted screenshot step right before step #{at_step+1} (your submit click). Failed visits will now have a debug image."

    raise ValueError(f"Unknown auto-fix kind: {kind!r}")


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
    # 2026-05 — attach fallbacks stashed by the dropdown click.
    try:
        _fb_map = getattr(sess, "_pending_dropdown_fallbacks", None)
        if isinstance(_fb_map, dict):
            _fb_sel = _fb_map.get(selector)
            if _fb_sel:
                step["fallbacks"] = _fb_sel
            # one-shot — drop entry so the next dropdown starts clean
            _fb_map.pop(selector, None)
    except Exception:
        pass
    # ── 2026-05: Carry custom-UI hints from the dropdown click ──
    # If the <select> is hidden behind Bootstrap-Select / Select2 / etc,
    # the recording-time click stashed metadata on the session. We copy
    # it onto the step so the RUT replay engine can skip the (useless)
    # visibility pre-wait and go straight to the JS-driven select path
    # — saves ~5s of phase-1 wait time per dropdown per visit.
    meta = getattr(sess, "_pending_dropdown_meta", None)
    if meta and meta.get("selector") == selector:
        if meta.get("is_hidden_select"):
            # Engine reads this and routes wait_for_selector to
            # state="attached" (vs default "visible") for THIS step,
            # AND skips the visibility pre-wait entirely.
            step["state"] = "attached"
            step["prefer_js_set"] = True
        if meta.get("wrapper_kind"):
            step["wrapper_kind"] = meta["wrapper_kind"]
        # one-shot — clear after use so the next dropdown click starts clean
        try:
            delattr(sess, "_pending_dropdown_meta")
        except Exception:
            pass
    sess.steps.append(step)
    # 2026-01 — auto wait(500) removed per user request.
    # Brief settle wait so subsequent steps see the post-change DOM
    # is no longer auto-appended. User can insert a wait manually if needed.

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
    # 2026-05 — attach fallbacks captured by the earlier form_fill click
    # for THIS selector (if any). Without this, the second /type call
    # would lose the rich rescue paths and skip on a renamed input.
    try:
        _fb_map = getattr(sess, "_form_fill_fallbacks", None)
        if isinstance(_fb_map, dict):
            _fb_sel = _fb_map.get(selector)
            if _fb_sel:
                step["fallbacks"] = _fb_sel
    except Exception:
        pass
    sess.steps.append(step)
    # 2026-01 — auto wait removed per user request (was wait(800) here).
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
    # 2026-01 — auto wait(500) after scroll removed per user request.
    return {"recorded": True, "step": step}


async def navigate_to(sess: RecorderSession, url: str) -> Dict[str, Any]:
    """Navigate the page to a new URL. Records a `goto` step ONLY — auto
    wait_for_load / wait steps are no longer appended (2026-01 — per user
    request). The runtime engine's own goto already waits for
    domcontentloaded; add an explicit wait step from the recorder UI if a
    specific page needs a longer settle delay."""
    sess.touch()
    async with sess.lock:
        try:
            await sess.page.goto(url, wait_until="load", timeout=45000)
        except Exception as e:
            logger.warning(f"navigate failed: {e}")
    # NOTE: previously auto-appended _build_wait_load(60000) + _build_wait(2000)
    # here — removed per user request to prevent over-padded playback that
    # blew past the stuck-watchdog window.
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
    # 2026-01 — auto wait(2000) + wait_for_load(60000) + wait(2500) after
    # random-pick removed per user request. The random-pick JS itself
    # navigates the page when it clicks an <a> with href; subsequent
    # steps' selector timeouts will naturally wait for the new DOM.
    sess._pending_random = []
    return {"recorded": True, "step": step, "items": take}


async def navigate_only_click(sess: RecorderSession, x: int, y: int) -> Dict[str, Any]:
    """Perform a real click at (x, y) on the live page WITHOUT
    appending any step to the recording.

    Use case (2026-01): the Random Pick step contains its own random-
    button-click JavaScript; at recording time the user still needs
    to advance the live browser to the next page so they can record
    subsequent steps. Clicking with the normal "Click" tool would
    add an extra (unwanted) step. This endpoint performs the click
    purely for navigation purposes.
    """
    sess.touch()
    async with sess.lock:
        try:
            await sess.page.mouse.click(int(x), int(y))
        except Exception as e:  # noqa: BLE001
            return {"clicked": False, "error": f"{type(e).__name__}: {e}"}
    return {"clicked": True, "recorded": False}


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


def move_step_to(sess: RecorderSession, from_index: int, to_index: int) -> Dict[str, Any]:
    """2026-01 (additive): drag-and-drop reorder. Removes the step at
    `from_index` and re-inserts it at `to_index`. Both indices are
    clamped to the current array length. Returns updated total + new
    position, or no-op if from == to."""
    sess.touch()
    n = len(sess.steps)
    if not (0 <= from_index < n):
        return {"moved": False, "reason": f"from_index {from_index} out of range (have {n} steps)"}
    # Clamp to_index (drag-drop UI may overshoot by 1 when dropping at end)
    to_idx = max(0, min(int(to_index), n - 1))
    if from_index == to_idx:
        return {"moved": False, "reason": "from == to"}
    step = sess.steps.pop(from_index)
    sess.steps.insert(to_idx, step)
    return {"moved": True, "from": from_index, "to": to_idx, "total": len(sess.steps)}


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


# Fields that the UI is allowed to patch on an existing recorded step.
# We deliberately do NOT allow changing `action` (that would break replay
# semantics — user should delete + record a new step instead). The
# `humanize` flag (new 2026-01) lets the user opt OUT of slow per-char
# human typing for individual fill/type steps when speed matters more
# than stealth (e.g. live-test debugging, internal forms).
_EDITABLE_STEP_FIELDS = {
    "selector", "value", "timeout", "key", "ms",
    "state", "delay", "match_by", "humanize", "name",
    # 2026-01 additive — new step type fields
    "text", "contains", "equals", "pattern",
    "store_key", "var", "attribute", "regex",
    "retry", "retry_delay", "if_exists", "if_exists_timeout",
    "case_insensitive", "wait_nav", "optional",
    "max_iterations", "iteration_wait_ms", "stop_on_host",
}


def update_step(sess: RecorderSession, index: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Update one or more whitelisted fields on an existing step.
    Used by the new "Edit step" UI modal in the Visual Recorder when a
    live-test reveals a wrong selector / too-low timeout / etc. Does NOT
    re-execute the step against the live browser — the new values take
    effect on the NEXT Live Test or RUT run.

    Whitelisted fields: see `_EDITABLE_STEP_FIELDS`.
    `action` is intentionally read-only (changing it would break replay).

    Returns include `alias_saved` flag (True iff a selector rename was
    persisted to the global Selector Aliases store for self-healing
    future replays).
    """
    sess.touch()
    if not (0 <= index < len(sess.steps)):
        return {"updated": False, "reason": "index out of range"}
    if not isinstance(patch, dict):
        return {"updated": False, "reason": "patch must be a dict"}

    step = sess.steps[index]
    old_selector = step.get("selector") or ""
    applied: Dict[str, Any] = {}
    for k, v in patch.items():
        if k not in _EDITABLE_STEP_FIELDS:
            continue
        # Normalise empty strings to None for optional text fields so the
        # downstream replay doesn't see "" and try to act on it.
        if isinstance(v, str):
            v_clean = v.strip()
            if k in ("value", "name", "match_by", "state"):
                step[k] = v_clean or None
            elif k in ("selector", "key"):
                # Selector / key are required-ish — keep as empty string
                # if user explicitly cleared (caller's responsibility to
                # validate before saving in the UI).
                step[k] = v_clean
            else:
                step[k] = v_clean
            applied[k] = step[k]
        elif k in ("timeout", "ms", "delay") and v is not None:
            try:
                step[k] = max(0, int(v))
                applied[k] = step[k]
            except (TypeError, ValueError):
                continue
        elif k == "humanize":
            step[k] = bool(v)
            applied[k] = step[k]
        else:
            step[k] = v
            applied[k] = v
    return {"updated": True, "applied": applied, "step": step, "_old_selector": old_selector}


async def update_step_with_alias(sess: RecorderSession, index: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Async wrapper around `update_step` that ALSO persists a selector
    alias when the user changed the selector — the cornerstone of
    self-healing replay. Saves under (sess.user_id, sess.url domain,
    old_selector → new_selector). Best-effort: if the aliases store is
    unreachable, the edit still succeeds and we just skip the save."""
    result = update_step(sess, index, patch)
    if not result.get("updated"):
        return result

    old_sel = result.pop("_old_selector", "") or ""
    new_sel = (result.get("applied") or {}).get("selector")
    alias_saved = False
    if new_sel and old_sel and new_sel.strip() != old_sel.strip():
        try:
            import selector_aliases as _sa
            domain = _sa.extract_domain(sess.url or "")
            if domain and sess.user_id:
                alias_saved = await _sa.save_alias(sess.user_id, domain, old_sel, new_sel)
        except Exception:
            alias_saved = False
    result["alias_saved"] = alias_saved
    return result


# Whitelisted action types for "manual add step" — these can be added
# without browser interaction (just appended to sess.steps). Replay
# happens during Live Test / RUT run. We don't allow `goto` from
# manual-add since that's better done by starting a new recording at
# the new URL.
_MANUAL_STEP_ACTIONS = {
    "wait_for_selector", "click", "fill", "type", "select", "press",
    "wait", "wait_for_load", "wait_for_navigation", "wait_for_networkidle",
    "hover", "check", "uncheck", "screenshot",
    # 2026-01 additive — new step types from automation_extensions
    "wait_for_text", "wait_for_url", "extract", "dismiss_popups",
    "auto_continue", "auto_continue_survey",
}


def add_manual_step(sess: RecorderSession, step: Dict[str, Any], position: Optional[int] = None) -> Dict[str, Any]:
    """Append (or insert at `position`) a manually-authored step into the
    recorder session. Used by the new "Add Manual Step" UI button when
    the user needs to inject a step that the auto-recorder didn't pick
    up (e.g., hidden field needing an XPath selector). Validates the
    action type against the whitelist; selector / value pass-through
    unchanged so the user can supply BOTH CSS (`#x`, `[name=x]`) and
    XPath (`//input[@name="x"]`, `xpath=//div`) — Playwright auto-
    detects xpath at replay time. Returns the inserted step + new
    index."""
    sess.touch()
    if not isinstance(step, dict):
        return {"added": False, "reason": "step must be a dict"}
    action = (step.get("action") or "").strip().lower()
    if action not in _MANUAL_STEP_ACTIONS:
        return {
            "added": False,
            "reason": f"action '{action}' not allowed for manual add. "
                      f"Allowed: {sorted(_MANUAL_STEP_ACTIONS)}",
        }

    # Build a clean step dict — only keep known fields, normalise types.
    clean: Dict[str, Any] = {"action": action}
    for k in ("selector", "value", "key", "state", "match_by", "name",
              # 2026-01 additive — new step type fields
              "text", "contains", "equals", "pattern",
              "store_key", "var", "attribute", "regex"):
        v = step.get(k)
        if v is not None and str(v).strip() != "":
            clean[k] = str(v).strip()
    for k in ("timeout", "ms", "delay",
              # 2026-01 additive — retry config + per-iteration tunables
              "retry", "retry_delay", "if_exists_timeout",
              "max_iterations", "iteration_wait_ms"):
        v = step.get(k)
        if v is not None:
            try:
                clean[k] = max(0, int(v))
            except (TypeError, ValueError):
                pass
    if "humanize" in step:
        clean["humanize"] = bool(step["humanize"])
    if "if_exists" in step:
        clean["if_exists"] = bool(step["if_exists"])
    if "case_insensitive" in step:
        clean["case_insensitive"] = bool(step["case_insensitive"])
    if "wait_nav" in step:
        clean["wait_nav"] = bool(step["wait_nav"])
    if "optional" in step:
        clean["optional"] = bool(step["optional"])
    # Tag this step so the UI can show a small "manual" badge — purely
    # cosmetic, doesn't affect replay.
    clean["source"] = "manual"

    # Default timeouts so users don't have to set them every time.
    if action in ("wait_for_selector", "click", "fill", "type", "select", "hover", "check", "uncheck") and "timeout" not in clean:
        clean["timeout"] = 8000
    if action == "wait" and "ms" not in clean:
        clean["ms"] = 1000
    if action in ("wait_for_text", "wait_for_url", "extract") and "timeout" not in clean:
        clean["timeout"] = 15000

    # Insert at position (clamped to valid range) or append.
    n = len(sess.steps)
    if position is None or not isinstance(position, int):
        idx = n
    else:
        idx = max(0, min(int(position), n))
    sess.steps.insert(idx, clean)
    return {"added": True, "step": clean, "index": idx, "total": len(sess.steps)}


def import_steps(sess: RecorderSession, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bulk-replace the session's steps with the provided list (used
    when the user clicks "Live Visual Test" on the finalized Recording
    Complete screen: a fresh recorder session is spawned with the same
    url/proxy/UA, then the saved JSON is imported here, then a live
    test is fired so the user can visually verify the full automation
    step by step). Validates each step is a dict with a known action
    type; otherwise rejects the import to prevent runtime crashes."""
    sess.touch()
    if not isinstance(steps, list):
        return {"imported": False, "reason": "steps must be a list"}
    # Light validation — accept any dict with `action` string, since the
    # replay engine handles unknown actions defensively.
    cleaned: List[Dict[str, Any]] = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        action = (s.get("action") or "").strip().lower()
        if not action:
            continue
        # Copy the step so we don't mutate the caller's data
        cleaned.append(dict(s))
    sess.steps = cleaned
    return {"imported": True, "total": len(cleaned)}


def update_session_data(sess: RecorderSession, *, sample_row: Optional[Dict[str, Any]] = None,
                         headers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Update the sample row / headers on an active session — used when
    the "Live Visual Test" reuses a finalized bundle and needs to push
    the same sample data into the new session before replay."""
    sess.touch()
    if sample_row is not None and isinstance(sample_row, dict):
        sess.sample_row = sample_row
    if headers is not None and isinstance(headers, list):
        sess.headers = [str(h) for h in headers if h]
    return {"ok": True, "headers": sess.headers, "sample_row": getattr(sess, "sample_row", None)}


async def suggest_selectors(sess: RecorderSession, failed_selector: str, limit: int = 8) -> Dict[str, Any]:
    """Smart Selector Suggester (2026-01) — when a step fails because
    the recorded selector no longer matches the page, query the LIVE
    DOM for nearby candidates that look similar and rank them.

    Used by the Edit-step modal's "🔍 Find similar selectors" button.
    Returns a list of candidate selectors with metadata so the user can
    one-click swap the failed selector for the right one.

    Strategy:
      1. Extract identifier tokens from the failed selector
         (e.g., `#birth_month` → ["birth", "month"];
          `[name="dob_year"]` → ["dob", "year"];
          `//input[@id='first']` → ["first"]).
      2. In a single page.evaluate() call, scan all form-relevant
         elements (input/select/textarea/button) and score each by
         how many tokens appear in its id/name/class/aria-label/
         placeholder/label text.
      3. Return top `limit` candidates sorted by score, each with a
         ready-to-paste CSS selector + tag + visible label preview.
    """
    sess.touch()
    if sess.state != "ready" or not sess.page:
        return {"suggestions": [], "error": f"Session not ready ({sess.state})"}

    sel = (failed_selector or "").strip()
    if not sel:
        return {"suggestions": [], "error": "empty selector"}

    # ── Token extraction (handles CSS id/name attr + xpath patterns) ─
    import re as _re
    tokens: List[str] = []

    # #id
    for m in _re.finditer(r"#([\w\-]+)", sel):
        tokens.append(m.group(1))
    # [name="x"], [id="x"], [name=x], [id=x]
    for m in _re.finditer(r"\[(?:name|id)\s*=\s*[\"']?([\w\-]+)[\"']?\]", sel):
        tokens.append(m.group(1))
    # xpath @id='x' / @name='x'
    for m in _re.finditer(r"@(?:name|id)\s*=\s*[\"']([\w\-]+)[\"']", sel):
        tokens.append(m.group(1))
    # If the selector itself is a bare word (no special chars), use it
    if not tokens and _re.match(r"^[\w\-]+$", sel):
        tokens.append(sel)

    # Sub-tokens (split on _ - space camelCase)
    sub: List[str] = []
    for t in tokens:
        for piece in _re.split(r"[_\-\s]+", t):
            if piece and len(piece) >= 2:
                sub.append(piece.lower())
        # camelCase → snake-ish
        for piece in _re.findall(r"[A-Z]?[a-z]+", t):
            if piece and len(piece) >= 2:
                sub.append(piece.lower())
    # Dedup preserving order
    seen: set = set()
    search_tokens: List[str] = []
    for t in sub:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            search_tokens.append(tl)
    if not search_tokens:
        return {"suggestions": [], "error": "could not extract tokens from selector", "tokens": []}

    # ── Run DOM scan in browser ──────────────────────────────────────
    js = """
    (params) => {
      const tokens = params.tokens.map(t => t.toLowerCase());
      const candidates = [];
      const els = document.querySelectorAll('input, select, textarea, button, [contenteditable=true]');
      function visibleLabel(el) {
        // Linked <label for=id>
        const id = el.getAttribute('id');
        if (id) {
          const lab = document.querySelector('label[for="' + CSS.escape(id) + '"]');
          if (lab && lab.innerText) return lab.innerText.trim().slice(0, 60);
        }
        // Ancestor <label> wrapping the field
        const parentLab = el.closest('label');
        if (parentLab && parentLab.innerText) return parentLab.innerText.trim().slice(0, 60);
        // aria-label
        const aria = el.getAttribute('aria-label');
        if (aria) return aria.trim().slice(0, 60);
        // placeholder fallback
        const ph = el.getAttribute('placeholder');
        if (ph) return ph.trim().slice(0, 60);
        return '';
      }
      function isVisible(el) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) return false;
        const cs = window.getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
        return true;
      }
      els.forEach(el => {
        const id = (el.getAttribute('id') || '').toLowerCase();
        const name = (el.getAttribute('name') || '').toLowerCase();
        const cls = (el.getAttribute('class') || '').toLowerCase();
        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
        const ph = (el.getAttribute('placeholder') || '').toLowerCase();
        const type = (el.getAttribute('type') || '').toLowerCase();
        const label = visibleLabel(el).toLowerCase();
        const haystack = [id, name, cls, aria, ph, label].join(' | ');
        let score = 0;
        let matched = [];
        tokens.forEach(t => {
          if (!t) return;
          if (id === t) { score += 10; matched.push(t); return; }
          if (name === t) { score += 8; matched.push(t); return; }
          if (id.includes(t) || name.includes(t)) { score += 5; matched.push(t); return; }
          if (aria.includes(t) || ph.includes(t) || label.includes(t)) { score += 3; matched.push(t); return; }
          if (cls.includes(t)) { score += 1; matched.push(t); return; }
        });
        if (score <= 0) return;
        // Build a stable selector — prefer #id, then [name=], then nth-of-type tag
        let suggested = '';
        if (id) {
          suggested = '#' + id;
        } else if (name) {
          suggested = el.tagName.toLowerCase() + '[name="' + name + '"]';
        } else if (aria) {
          suggested = el.tagName.toLowerCase() + '[aria-label="' + el.getAttribute('aria-label') + '"]';
        } else {
          // fallback: nth-of-type within parent
          const parent = el.parentElement;
          if (parent) {
            const sibs = Array.from(parent.children).filter(c => c.tagName === el.tagName);
            const idx = sibs.indexOf(el);
            suggested = el.tagName.toLowerCase() + ':nth-of-type(' + (idx + 1) + ')';
          } else {
            suggested = el.tagName.toLowerCase();
          }
        }
        candidates.push({
          selector: suggested,
          tag: el.tagName.toLowerCase(),
          input_type: type || null,
          id: id || null,
          name: name || null,
          label: visibleLabel(el) || null,
          placeholder: el.getAttribute('placeholder') || null,
          visible: isVisible(el),
          matched_tokens: matched,
          score: score,
        });
      });
      // Sort by score DESC, then visible first
      candidates.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return (b.visible ? 1 : 0) - (a.visible ? 1 : 0);
      });
      return candidates.slice(0, params.limit);
    }
    """

    try:
        async with sess.lock:
            results = await sess.page.evaluate(js, {"tokens": search_tokens, "limit": int(limit)})
    except Exception as e:
        return {"suggestions": [], "error": f"DOM scan failed: {e}", "tokens": search_tokens}

    return {
        "suggestions": results or [],
        "tokens": search_tokens,
        "failed_selector": sel,
    }


async def selector_bbox(sess: RecorderSession, selector: str) -> Dict[str, Any]:
    """Return the bounding box of the first element matching `selector`
    on the LIVE page, in CSS pixel coordinates relative to the
    viewport. Used by the Edit modal's "hover-to-preview" feature
    to draw a blue outline overlay on the screenshot.

    Returns:
      { found: bool, x, y, width, height,
        viewport: {width, height}, error?: str }
    """
    sess.touch()
    if sess.state != "ready" or not sess.page:
        return {"found": False, "error": f"Session not ready ({sess.state})"}
    sel = (selector or "").strip()
    if not sel:
        return {"found": False, "error": "empty selector"}

    # Playwright auto-detects XPath when selector starts with `//`, `..`,
    # or `xpath=` — no special handling needed here. We just call
    # query_selector and bounding_box; both work for CSS + XPath.
    try:
        async with sess.lock:
            el = await sess.page.query_selector(sel)
            if el is None:
                # Get viewport size for debugging
                vp = sess.page.viewport_size or {"width": 0, "height": 0}
                return {"found": False, "error": "Element not found", "viewport": vp}
            bbox = await el.bounding_box()
            vp = sess.page.viewport_size or {"width": 0, "height": 0}
            if bbox is None:
                return {"found": False, "error": "Element has no bounding box (likely hidden)", "viewport": vp}
            return {
                "found": True,
                "x": float(bbox.get("x", 0)),
                "y": float(bbox.get("y", 0)),
                "width": float(bbox.get("width", 0)),
                "height": float(bbox.get("height", 0)),
                "viewport": vp,
            }
    except Exception as e:
        return {"found": False, "error": str(e)}


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


# ─────────────────────────────────────────────────────────────────────
# 2026-01: Pre-flight lint + quick step builders
# ─────────────────────────────────────────────────────────────────────
def lint_session(sess: RecorderSession) -> Dict[str, Any]:
    """Pre-flight lint on the current session's steps. Returns:
        {
          ok: bool,                      # True iff no `error` issues
          issues: [
            {level, at_step, code, message}, ...
          ],
          summary: {errors: N, warnings: N, infos: N}
        }
    """
    sess.touch()
    try:
        from automation_extensions import lint_steps
        issues = lint_steps(sess.steps)
    except Exception as e:  # pragma: no cover
        return {"ok": False, "issues": [{"level": "error", "at_step": -1,
                "code": "lint_unavailable", "message": str(e)}],
                "summary": {"errors": 1, "warnings": 0, "infos": 0}}
    errors = sum(1 for i in issues if i.get("level") == "error")
    warnings = sum(1 for i in issues if i.get("level") == "warn")
    infos = sum(1 for i in issues if i.get("level") == "info")
    return {
        "ok": errors == 0,
        "issues": issues,
        "summary": {"errors": errors, "warnings": warnings, "infos": infos},
    }


def add_wait_for_text_step(sess: RecorderSession, text: str,
                           timeout: int = 15000,
                           case_insensitive: bool = True,
                           optional: bool = False) -> Dict[str, Any]:
    """Append a `wait_for_text` step (e.g. wait for "Thank you")."""
    sess.touch()
    if not text:
        return {"recorded": False, "error": "text required"}
    step = {
        "action": "wait_for_text",
        "text": str(text),
        "timeout": max(1000, int(timeout)),
        "case_insensitive": bool(case_insensitive),
    }
    if optional:
        step["optional"] = True
    sess.steps.append(step)
    return {"recorded": True, "step": step}


def add_wait_for_url_step(sess: RecorderSession,
                          contains: Optional[str] = None,
                          equals: Optional[str] = None,
                          pattern: Optional[str] = None,
                          timeout: int = 15000,
                          optional: bool = False) -> Dict[str, Any]:
    """Append a `wait_for_url` step (e.g. wait until URL contains '/success')."""
    sess.touch()
    if not (contains or equals or pattern):
        return {"recorded": False, "error": "contains/equals/pattern required"}
    step = {
        "action": "wait_for_url",
        "timeout": max(1000, int(timeout)),
    }
    if contains: step["contains"] = str(contains)
    if equals:   step["equals"]   = str(equals)
    if pattern:  step["pattern"]  = str(pattern)
    if optional: step["optional"] = True
    sess.steps.append(step)
    return {"recorded": True, "step": step}


def add_extract_step(sess: RecorderSession,
                     selector: str, store_key: str,
                     attribute: Optional[str] = None,
                     regex: Optional[str] = None,
                     timeout: int = 10000,
                     optional: bool = False) -> Dict[str, Any]:
    """Append an `extract` step — captures text/attribute from a selector
    into a variable usable in subsequent steps via `{{store_key}}`."""
    sess.touch()
    if not selector or not store_key:
        return {"recorded": False, "error": "selector + store_key required"}
    step = {
        "action": "extract",
        "selector": str(selector),
        "store_key": str(store_key),
        "timeout": max(1000, int(timeout)),
    }
    if attribute: step["attribute"] = str(attribute)
    if regex:     step["regex"]     = str(regex)
    if optional:  step["optional"]  = True
    sess.steps.append(step)
    return {"recorded": True, "step": step}


def add_dismiss_popups_step(sess: RecorderSession) -> Dict[str, Any]:
    """Append a `dismiss_popups` step (auto-clicks cookie/GDPR banners)."""
    sess.touch()
    step = {"action": "dismiss_popups", "optional": True}
    sess.steps.append(step)
    return {"recorded": True, "step": step}


def get_live_progress(sess: RecorderSession, since_idx: int = 0) -> Dict[str, Any]:
    """Return the current live-progress feed for an in-flight or recently
    completed live_test. Frontend polls this every ~400ms.

    Args:
        since_idx: only return events with array index >= since_idx
            (lets the frontend do incremental fetches).

    Returns:
        {
          running: bool,        # True while live_test is executing
          started_at: float,    # epoch seconds
          finished_at: float | None,
          total_events: int,
          events: [{idx, action, selector, status, ms?, error?, friendly_hint?, timestamp_ms}, ...],
        }
    """
    sess.touch()
    all_events = sess.live_progress or []
    since = max(0, int(since_idx or 0))
    return {
        "running": bool(sess.live_progress_running),
        "started_at": sess.live_progress_started_at,
        "finished_at": sess.live_progress_finished_at,
        "total_events": len(all_events),
        "events": all_events[since:],
    }


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
