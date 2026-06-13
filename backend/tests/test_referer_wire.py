"""Regression test for the 2026-06-12 Referer-header bug.

Background
----------
Chromium's NetworkService SILENTLY DROPS the "Referer" entry from
`browser_context.extra_http_headers` on the initial page navigation —
it considers Referer an internally-managed header. The ONLY supported
way to set Referer for the very first request is the `referer=`
keyword argument of `page.goto(...)`.

Before the fix, real_user_traffic.py only set Referer via
`extra_http_headers`. Result: every Referrer-override mode (TikTok UA
auto-detect, custom URL, platform pool, …) silently arrived at the
target with an EMPTY Referer header — the customer reported this as
"referrer system has not been working".

This test re-validates the fix by:
  1. Calling `_resolve_visit_referer(ua, cfg)` directly
  2. Spinning up Chromium with the SAME context-args + goto-kwargs the
     engine now uses (referer kwarg on goto + Referer in
     extra_http_headers for follow-up requests)
  3. Hitting an external echo service (postman-echo.com/headers)
  4. Asserting the ACTUAL wire-level Referer the server received
     matches what the resolver returned.

Run:  cd /app/backend && \
        PLAYWRIGHT_BROWSERS_PATH=/pw-browsers \
        python3 -m pytest tests/test_referer_wire.py -v

Skipped automatically when Chromium isn't installed (e.g. cloud CI
without the browser bundle).
"""
import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Skip the entire module when Playwright Chromium isn't reachable —
# CI environments without the browser bundle should not fail here.
_PW_DIR = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/pw-browsers"
_PW_AVAILABLE = os.path.exists(_PW_DIR) and any(
    f.startswith("chromium") for f in os.listdir(_PW_DIR)
) if os.path.isdir(_PW_DIR) else False
if not _PW_AVAILABLE:
    pytest.skip(
        "Playwright Chromium not installed in this environment — "
        "skipping wire-level Referer regression test.",
        allow_module_level=True,
    )

from real_user_traffic import _resolve_visit_referer  # noqa: E402
from playwright.async_api import async_playwright       # noqa: E402

ECHO_URL = "https://postman-echo.com/headers"


async def _capture_wire_referer(ua: str, cfg):
    """Run a single mini-visit through the same context+goto pattern the
    engine uses and return (expected, received) Referer pair."""
    ref, _plat, _esp, _extras = _resolve_visit_referer(ua, cfg)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            headers = {"Accept-Language": "en-US,en;q=0.9"}
            if ref:
                headers["Referer"] = ref
            ctx = await browser.new_context(user_agent=ua, extra_http_headers=headers)
            page = await ctx.new_page()
            goto_kw = {"referer": ref} if ref else {}
            await page.goto(ECHO_URL, wait_until="domcontentloaded", timeout=30000, **goto_kw)
            text = await page.evaluate("() => document.body.innerText")
            obj = json.loads(text)
            received = (
                obj.get("headers", {}).get("referer")
                or obj.get("headers", {}).get("Referer")
                or ""
            )
            return ref, received
        finally:
            await browser.close()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Test cases ──────────────────────────────────────────────────────────


def test_tiktok_ua_auto_referer():
    ua = (
        "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile "
        "Safari/537.36 trill_2023400030 musical_ly_27.4.0"
    )
    expected, received = _run(_capture_wire_referer(ua, None))
    assert expected == "https://www.tiktok.com/", f"resolver returned {expected!r}"
    assert received == expected, f"wire received {received!r} (expected {expected!r})"


def test_custom_url_override():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"
    custom = "https://my-affiliate-site.com/landing/abc?utm_source=fb"
    expected, received = _run(_capture_wire_referer(
        ua, {"enabled": True, "mode": "custom", "value": custom}
    ))
    assert expected == custom
    assert received == custom, f"wire received {received!r}"


def test_direct_mode_no_referer():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"
    expected, received = _run(_capture_wire_referer(
        ua, {"enabled": True, "mode": "direct"}
    ))
    assert expected == ""
    assert received == "", f"expected NO Referer; wire received {received!r}"


def test_platform_pool_tiktok():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"
    expected, received = _run(_capture_wire_referer(
        ua, {"enabled": True, "mode": "platform_pool", "platform_pool": "tiktok"}
    ))
    assert "tiktok.com" in expected
    assert received == expected


def test_google_search_mode():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"
    expected, received = _run(_capture_wire_referer(
        ua, {"enabled": True, "mode": "google_search", "value": "best car insurance"}
    ))
    assert "google.com/search?q=" in expected
    assert received == expected


def test_random_list_single_entry():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"
    expected, received = _run(_capture_wire_referer(
        ua, {"enabled": True, "mode": "random_list",
             "value": "https://www.instagram.com/p/abc/"}
    ))
    assert expected == "https://www.instagram.com/p/abc/"
    assert received == expected
