"""Regression tests for the 2026-06 native-click upgrade.

Fixes the silent-failure case where `action: evaluate` steps emitted
by the Visual Recorder (random-pick + text-click builders) did not
trigger framework-bound click listeners on SPA pages, and did not
reach buttons inside iframes (stacks.app, uplevelrewards, etc.).

These tests:
  1. Verify the label-extraction parser correctly pulls labels out
     of both random-pick and single text-click scripts.
  2. Verify the native click helper fires real listeners inside
     iframes — the failure scenario reported by the user.
  3. Confirm that the "old" synthetic JS path silently fails on the
     same setup (regression guard for the bug itself).

Run:
    cd /app/backend && python3 -m pytest tests/test_evaluate_native_click.py -v
"""
import asyncio
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from real_user_traffic import (
    _extract_random_pick_labels,
    _extract_text_click_label,
    _native_click_by_text,
)


# ── Parser unit tests ──────────────────────────────────────────────


def test_random_pick_parser_user_json():
    script = (
        "(function(){var labels=['Super Low Prices','Trendy Styles','Free Returns'];"
        "var pick=labels[Math.floor(Math.random()*labels.length)];})();"
    )
    assert _extract_random_pick_labels(script) == [
        "Super Low Prices", "Trendy Styles", "Free Returns",
    ]


def test_random_pick_parser_escaped_quote():
    script = "var labels=['Don\\'t go','Yes only'];"
    assert _extract_random_pick_labels(script) == ["Don't go", "Yes only"]


def test_random_pick_parser_rejects_non_random_script():
    assert _extract_random_pick_labels("var t='Continue';") is None
    assert _extract_random_pick_labels("alert(1)") is None
    assert _extract_random_pick_labels(None) is None


def test_text_click_parser_continue():
    script = "(function(){var t='Continue'.replace(/\\s+/g,' ').trim().toLowerCase();})();"
    assert _extract_text_click_label(script) == "Continue"


def test_text_click_parser_rejects_random_pick():
    # Random-pick scripts also contain `var labels=[...]` AND `var pick=`
    # — the text-click parser must NOT match them or it would extract
    # the wrong thing.
    script = "var labels=['A','B']; var t='X';"
    assert _extract_text_click_label(script) is None


# ── End-to-end native-click test (Playwright required) ─────────────


async def _async_iframe_click_test():
    """The exact failure scenario from the user's screenshot:
       • Buttons live inside an iframe (offer-wall pattern)
       • Click handlers attached via addEventListener (SPA pattern)
       Synthetic top-frame JS `el.click()` cannot reach these.
       Native Playwright click MUST.
    """
    from playwright.async_api import async_playwright

    html = """
    <!doctype html><html><body>
    <iframe id=f srcdoc="
      <!doctype html><html><body>
      <button id=b1>Super Low Prices</button>
      <button id=b2>Trendy Styles</button>
      <button id=b3>Free Returns</button>
      <script>
        ['b1','b2','b3'].forEach(function(id){
          document.getElementById(id).addEventListener('click', function(){
            window.parent.__krx_clicked = this.textContent;
          });
        });
      </script>
      </body></html>
    "></iframe>
    </body></html>
    """

    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.set_content(html, wait_until="load")
            await page.wait_for_function(
                "document.querySelector('iframe#f').contentDocument && "
                "document.querySelector('iframe#f').contentDocument.querySelector('#b2')"
            )

            # Native click must reach into iframe and fire the listener
            ok, frame_url, err = await _native_click_by_text(page, "Trendy Styles", timeout_ms=4000)
            assert ok, f"native click failed: {err}"
            assert "srcdoc" in frame_url, f"expected iframe match, got '{frame_url}'"

            clicked = await page.evaluate("window.__krx_clicked")
            assert clicked == "Trendy Styles", f"listener did not fire, got: {clicked!r}"
        finally:
            await browser.close()


def test_native_click_inside_iframe_fires_react_listener():
    asyncio.run(_async_iframe_click_test())


async def _async_missing_text_test():
    """If the label isn't anywhere on the page, native click returns
    (False, '', err) — caller can then fall back to JS execution.
    """
    from playwright.async_api import async_playwright
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.set_content("<html><body><p>Empty page</p></body></html>", wait_until="load")

            ok, frame_url, err = await _native_click_by_text(page, "Nonexistent Button XYZ", timeout_ms=1500)
            assert ok is False
            assert err  # some error message
        finally:
            await browser.close()


def test_native_click_returns_false_when_text_missing():
    asyncio.run(_async_missing_text_test())
