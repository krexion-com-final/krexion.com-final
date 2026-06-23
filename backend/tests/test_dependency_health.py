"""
Unit tests for the v2.1.59 dependency health check.

Verifies that /api/desktop/stats now reports the install state of every
external dependency the customer's PC needs (Playwright, Chromium binary,
ADB) so the Native dashboard surfaces "downloading…" / "missing" /
"ready" badges BEFORE the customer hits Launch on a feature and gets
a cryptic error.

Run with:
    cd /app/krexion_repo/backend
    python -m pytest tests/test_dependency_health.py -v --asyncio-mode=auto
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

# Stub heavy dependencies that real_user_traffic imports — the test env
# only needs the function signatures we patch via mock, not the real impls.
# We stub `real_user_traffic` ENTIRELY so desktop_module's lazy import
# `from real_user_traffic import get_engine_status` resolves to our fake.
import types as _t
_fake_rut = _t.ModuleType("real_user_traffic")
_fake_rut.get_engine_status = lambda: {
    "status": "ready",
    "message": "Chromium ready (test stub)",
    "expected_revision": "1148",
}
sys.modules["real_user_traffic"] = _fake_rut
sys.modules.setdefault("playwright", _t.ModuleType("playwright"))
sys.modules.setdefault("playwright.async_api", _t.ModuleType("playwright.async_api"))

import desktop_module


@pytest.mark.asyncio
async def test_dependency_health_returns_all_known_keys():
    result = await desktop_module._dependency_health()
    # Three feature dependencies must always be reported (even when one
    # is in error state — the dashboard should never see a partial dict).
    assert set(result.keys()) >= {"playwright", "chromium", "adb"}


@pytest.mark.asyncio
async def test_chromium_ready_state_surfaces_to_dashboard():
    fake_engine = {
        "status": "ready",
        "message": "Chromium ready · using headless_shell rev 1148",
        "expected_revision": "1148",
    }
    with patch("real_user_traffic.get_engine_status", return_value=fake_engine):
        result = await desktop_module._dependency_health()
    chromium = result["chromium"]
    assert chromium["status"] == "ready"
    assert "1148" in chromium.get("expected_revision", "")


@pytest.mark.asyncio
async def test_chromium_installing_state_surfaces_to_dashboard():
    fake_engine = {
        "status": "installing",
        "message": "Downloading Chromium rev 1148…",
        "expected_revision": "1148",
    }
    with patch("real_user_traffic.get_engine_status", return_value=fake_engine):
        result = await desktop_module._dependency_health()
    chromium = result["chromium"]
    # Critical: "installing" must be passed through verbatim so the
    # dashboard can render the warning state and the user can click
    # Launch later with confidence instead of failing immediately.
    assert chromium["status"] == "installing"
    assert "Downloading" in chromium["message"]


@pytest.mark.asyncio
async def test_chromium_missing_state_surfaces_to_dashboard():
    fake_engine = {
        "status": "missing",
        "message": "Chromium rev 1148 not installed yet",
        "expected_revision": "1148",
    }
    with patch("real_user_traffic.get_engine_status", return_value=fake_engine):
        result = await desktop_module._dependency_health()
    chromium = result["chromium"]
    assert chromium["status"] == "missing"
    # Actionable message present
    assert chromium["message"]


@pytest.mark.asyncio
async def test_chromium_status_helper_unavailable_does_not_crash():
    """If the real_user_traffic helper itself fails to import / raise,
    the dependency health check must still return a dict with a clear
    error state — never raise into the /api/desktop/stats handler."""
    def _raise(*_a, **_k):
        raise RuntimeError("simulated engine probe failure")

    with patch("real_user_traffic.get_engine_status", side_effect=_raise):
        result = await desktop_module._dependency_health()
    chromium = result["chromium"]
    assert chromium["status"] == "error"
    assert "simulated engine probe failure" in chromium["message"]


@pytest.mark.asyncio
async def test_adb_detection_via_shutil_which():
    # Pretend adb is on PATH at a known location
    with patch("shutil.which", return_value="/usr/bin/adb"):
        result = await desktop_module._dependency_health()
    assert result["adb"]["status"] == "ok"
    assert "/usr/bin/adb" in result["adb"]["message"]


@pytest.mark.asyncio
async def test_adb_missing_returns_actionable_hint():
    with patch("shutil.which", return_value=None):
        result = await desktop_module._dependency_health()
    assert result["adb"]["status"] == "missing"
    # Message must include the install hint customers can act on
    msg_lower = result["adb"]["message"].lower()
    assert "adb" in msg_lower
    assert ("platform" in msg_lower) or ("cpi worker" in msg_lower)


@pytest.mark.asyncio
async def test_playwright_package_present_is_ok():
    """In this test env we stub Playwright at import time so the check
    must return status=ok with a non-empty message."""
    # Stub the package so import succeeds even on test hosts without
    # a real Playwright install (the previous test files already do this).
    import types as _t
    sys.modules.setdefault("playwright", _t.ModuleType("playwright"))
    sys.modules.setdefault(
        "playwright.async_api", _t.ModuleType("playwright.async_api")
    )
    result = await desktop_module._dependency_health()
    assert result["playwright"]["status"] == "ok"
