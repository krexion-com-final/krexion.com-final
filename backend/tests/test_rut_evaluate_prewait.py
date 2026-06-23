"""
Unit tests for the v2.1.60 RUT evaluate-step race-condition fix.

User report (Urdu/Hinglish): "job chalai es mein bht se visit pr error a
rha … step ni mile pr step add hai already kuch pr step thk kaam kie
hein pr kuch pr error a raha hai" — translation: same job, same step
config, some visits succeed, others fail at evaluate steps with
"REQUIRED step N of M (evaluate ...) did not complete".

Root cause: visual-recorder-emitted evaluate scripts contain literal
`document.querySelector('#submit-btn').click()` style code that runs
without first waiting for the selector to exist in the DOM. On fast
page loads the element is already there. On slow proxies / SPA
re-renders / slow mobile sims the element arrives a few hundred ms
later → querySelector returns null → .click() throws TypeError → step
fails as REQUIRED.

Fix: pre-extract selectors from the JS script and call
`page.wait_for_selector(state="attached")` before running evaluate().
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Stub the third-party deps that real_user_traffic imports at top-level.
# We only need the two pure helper functions for these unit tests.
sys.modules.setdefault("user_agents", types.ModuleType("user_agents"))
sys.modules["user_agents"].parse = lambda *a, **k: None  # type: ignore[attr-defined]

# IMPORTANT: A sibling test file (test_dependency_health.py) installs
# its own bare `playwright.async_api` stub that LACKS `async_playwright`,
# `Page`, etc. — `real_user_traffic`'s top-level `from playwright.async_api
# import async_playwright, Page, BrowserContext, Browser` then ImportError's.
# We FORCE-replace the stub (not setdefault) with a complete one so
# the real-module import succeeds regardless of which test ran first.
sys.modules["playwright"] = types.ModuleType("playwright")
_pw_async = types.ModuleType("playwright.async_api")
class _StubPage: ...
class _StubBrowser: ...
class _StubContext: ...
_pw_async.Page = _StubPage  # type: ignore[attr-defined]
_pw_async.Browser = _StubBrowser  # type: ignore[attr-defined]
_pw_async.BrowserContext = _StubContext  # type: ignore[attr-defined]
_pw_async.async_playwright = lambda: None  # type: ignore[attr-defined]
sys.modules["playwright.async_api"] = _pw_async

# A sibling file (test_dependency_health.py) also intentionally replaces
# `real_user_traffic` in sys.modules with a fake. Evict it so we get
# the real module from disk.
sys.modules.pop("real_user_traffic", None)

import pytest

import real_user_traffic as rut


# ───────────────────────── _extract_selectors_from_evaluate_js ────────

def test_extract_returns_empty_for_empty_or_non_string():
    assert rut._extract_selectors_from_evaluate_js("") == []
    assert rut._extract_selectors_from_evaluate_js(None) == []  # type: ignore[arg-type]
    assert rut._extract_selectors_from_evaluate_js(123) == []   # type: ignore[arg-type]


def test_extract_picks_up_querySelector():
    js = "document.querySelector('#submit-btn').click();"
    assert rut._extract_selectors_from_evaluate_js(js) == ["#submit-btn"]


def test_extract_picks_up_getElementById_and_prepends_hash():
    js = "var el = document.getElementById('first-name'); el.value='John';"
    assert rut._extract_selectors_from_evaluate_js(js) == ["#first-name"]


def test_extract_picks_up_querySelectorAll():
    js = "var nodes = document.querySelectorAll('.cta-button'); nodes[0].click();"
    assert rut._extract_selectors_from_evaluate_js(js) == [".cta-button"]


def test_extract_complex_compound_selector():
    js = "document.querySelector('form#signup input[name=email]').focus();"
    assert rut._extract_selectors_from_evaluate_js(js) == ["form#signup input[name=email]"]


def test_extract_deduplicates_repeated_selectors():
    js = """
      document.querySelector('#submit-btn').click();
      setTimeout(() => document.querySelector('#submit-btn').click(), 500);
    """
    assert rut._extract_selectors_from_evaluate_js(js) == ["#submit-btn"]


def test_extract_caps_at_four_selectors():
    js = """
      document.querySelector('#a').click();
      document.querySelector('#b').click();
      document.querySelector('#c').click();
      document.querySelector('#d').click();
      document.querySelector('#e').click();
      document.querySelector('#f').click();
    """
    out = rut._extract_selectors_from_evaluate_js(js)
    assert len(out) == 4
    assert out == ["#a", "#b", "#c", "#d"]


def test_extract_skips_template_placeholders():
    """Unrendered {{var}} placeholders aren't valid CSS — skip them."""
    js = "document.querySelector('#{{btn_id}}').click();"
    assert rut._extract_selectors_from_evaluate_js(js) == []


def test_extract_mixed_helpers_preserve_order():
    js = """
      document.getElementById('first').value = 'X';
      document.querySelector('#second').click();
      document.querySelectorAll('.third')[0].click();
    """
    assert rut._extract_selectors_from_evaluate_js(js) == ["#first", "#second", ".third"]


def test_extract_handles_double_quotes():
    js = 'document.querySelector("#submit-btn").click();'
    assert rut._extract_selectors_from_evaluate_js(js) == ["#submit-btn"]


def test_extract_random_pick_script_returns_no_selectors():
    """Legacy random-pick scripts use `var labels=[...]` then walk all
    <a> tags — no querySelector references → empty list (the engine
    already routes these to native click)."""
    js = """
      var labels = ['Continue', 'Submit', 'Next'];
      var t = labels[Math.floor(Math.random()*labels.length)];
      Array.from(document.querySelectorAll('a, button')).find(e => e.textContent.includes(t))?.click();
    """
    # querySelectorAll('a, button') WILL be picked up; that's intentional
    # because pre-waiting for *any* <a, button> to exist is a cheap
    # sanity check before the walk.
    out = rut._extract_selectors_from_evaluate_js(js)
    assert out == ["a, button"]


# ───────────────────────── _pre_wait_for_evaluate_selectors ───────────

@pytest.mark.asyncio
async def test_pre_wait_no_selectors_is_noop():
    """When the JS has no recognisable selector pattern, the helper
    must NOT touch the page (no spurious wait_for_selector call)."""
    page = MagicMock()
    page.wait_for_selector = AsyncMock()
    await rut._pre_wait_for_evaluate_selectors(page, "console.log('hi');", 5000)
    page.wait_for_selector.assert_not_awaited()


@pytest.mark.asyncio
async def test_pre_wait_calls_wait_for_each_selector_attached():
    page = MagicMock()
    page.wait_for_selector = AsyncMock(return_value=MagicMock())
    js = """
      document.querySelector('#submit-btn').click();
      document.getElementById('email').value = 'x@y.com';
    """
    await rut._pre_wait_for_evaluate_selectors(page, js, 5000)
    assert page.wait_for_selector.await_count == 2
    selectors_called = [c.args[0] for c in page.wait_for_selector.await_args_list]
    assert "#submit-btn" in selectors_called
    assert "#email" in selectors_called
    # state must be 'attached' (not 'visible') — anti-detect overlays
    # often hide the real submit button.
    for call in page.wait_for_selector.await_args_list:
        assert call.kwargs.get("state") == "attached"


@pytest.mark.asyncio
async def test_pre_wait_caps_timeout_per_selector_at_12s():
    """A 60-second step timeout shouldn't let a single missing selector
    waste 60s of the visit — cap the per-selector wait at 12s."""
    page = MagicMock()
    page.wait_for_selector = AsyncMock()
    await rut._pre_wait_for_evaluate_selectors(
        page, "document.querySelector('#x').click()", timeout_ms=60_000
    )
    assert page.wait_for_selector.await_count == 1
    call_kwargs = page.wait_for_selector.await_args_list[0].kwargs
    assert call_kwargs["timeout"] == 12_000


@pytest.mark.asyncio
async def test_pre_wait_enforces_min_timeout_floor():
    """Don't pass a sub-500ms timeout — the proxy round-trip alone often
    exceeds that, leading to a useless instant timeout."""
    page = MagicMock()
    page.wait_for_selector = AsyncMock()
    await rut._pre_wait_for_evaluate_selectors(
        page, "document.querySelector('#x').click()", timeout_ms=100
    )
    call_kwargs = page.wait_for_selector.await_args_list[0].kwargs
    assert call_kwargs["timeout"] == 500


@pytest.mark.asyncio
async def test_pre_wait_swallows_timeout_so_visit_continues():
    """If the selector NEVER appears, the pre-wait must NOT raise —
    the real evaluate() below should run and surface its own error
    (preserves existing diagnostic strings)."""
    page = MagicMock()
    page.wait_for_selector = AsyncMock(side_effect=asyncio.TimeoutError("nope"))
    # Must not raise
    await rut._pre_wait_for_evaluate_selectors(
        page, "document.querySelector('#missing').click()", timeout_ms=5000
    )
    page.wait_for_selector.assert_awaited_once()


@pytest.mark.asyncio
async def test_pre_wait_swallows_generic_exception():
    page = MagicMock()
    page.wait_for_selector = AsyncMock(side_effect=RuntimeError("boom"))
    await rut._pre_wait_for_evaluate_selectors(
        page, "document.querySelector('#x').click()", timeout_ms=5000
    )
    page.wait_for_selector.assert_awaited_once()


@pytest.mark.asyncio
async def test_pre_wait_continues_after_one_selector_fails():
    """A failure on the FIRST selector must not abort the wait loop —
    later selectors should still be checked."""
    page = MagicMock()
    call_order = []

    async def _fake_wait(sel, **kw):
        call_order.append(sel)
        if sel == "#first":
            raise asyncio.TimeoutError()
        return MagicMock()

    page.wait_for_selector = AsyncMock(side_effect=_fake_wait)
    js = """
      document.querySelector('#first').click();
      document.querySelector('#second').click();
    """
    await rut._pre_wait_for_evaluate_selectors(page, js, 5000)
    assert call_order == ["#first", "#second"]


@pytest.mark.asyncio
async def test_pre_wait_handles_none_page_safely():
    # Defensive null-page check (some self-heal paths pass None when
    # context is destroyed).
    await rut._pre_wait_for_evaluate_selectors(None, "doc.querySelector('#x')", 5000)
    # No exception = pass
