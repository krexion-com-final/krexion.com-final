"""
Regression test — v2.6.16 duplicate-IP definitive fix.

Ensures the pre-flight reachability probe (`_probe_proxy_target_reachable`)
is SKIPPED for tracker targets (any host in `_bypass_hosts()` or matching
via `_url_host_matches_bypass()`), so that the browser goto becomes the
SOLE HTTP touch on the affiliate offer's edge from the proxy exit IP.

Runs on plain pytest, no network / Playwright required.
"""

import re
from pathlib import Path

import pytest


RUT_FILE = Path(__file__).resolve().parents[1] / "real_user_traffic.py"


def _rut_source() -> str:
    return RUT_FILE.read_text(encoding="utf-8")


def test_version_bumped_to_2_6_16():
    """VERSION file must be bumped."""
    version = (RUT_FILE.parent / "VERSION").read_text().strip()
    assert version == "2.6.16", f"Expected 2.6.16, got {version!r}"


def test_tracker_target_skips_reachability_probe():
    """Ensure the pre-flight probe is gated behind `if not _is_tracker_target`."""
    src = _rut_source()
    # The fix inserts an `if _is_tracker_target:` branch that emits a
    # "skipping pre-flight reachability probe" step and puts the
    # `_probe_proxy_target_reachable` call inside the `else` branch.
    assert "skipping pre-flight reachability probe to avoid duplicate-IP burn" in src, (
        "v2.6.16 fix marker not found — the tracker-target skip branch is missing."
    )

    # And the probe call for the non-tracker branch must exist.
    m = re.search(
        r"else:\s*\n"
        r".*?# Non-tracker direct offer URL.*?\n"
        r".*?_reach_ok, _reach_diag = await _probe_proxy_target_reachable\(",
        src,
        re.DOTALL,
    )
    assert m, "Non-tracker fallback branch (probe still runs) not found."


def test_second_probe_still_disabled():
    """v2.6.15 disabled the second `_probe_offer_duplicate_via_proxy` probe.
    v2.6.16 must NOT re-enable it."""
    src = _rut_source()
    # Look for the guarded call — must still be `if False and ...`
    assert re.search(
        r"if False and _can_retry_offer_block:\s*\n\s+try:\s*\n\s+_pre_blk, _pre_reason, _pre_snip = await _probe_offer_duplicate_via_proxy",
        src,
    ), "v2.6.15's `if False and _can_retry_offer_block:` gate is missing / regressed."


def test_is_tracker_target_matches_subdomain():
    """The tracker-detection helper must catch parent-domain matches
    (api.krexion.com and krexion.com both match when bypass contains
    krexion.com or api.krexion.com)."""
    import importlib
    import sys

    sys.path.insert(0, str(RUT_FILE.parent))
    rut = importlib.import_module("real_user_traffic")

    assert rut._url_host_matches_bypass("https://krexion.com/api/t/samsclub01") is True
    assert rut._url_host_matches_bypass("https://api.krexion.com/api/t/x") is True
    assert rut._url_host_matches_bypass("https://sub.krexion.com/foo") is True
    assert rut._url_host_matches_bypass("https://track.traxun.online/") is False
    assert rut._url_host_matches_bypass("https://google.com/") is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
