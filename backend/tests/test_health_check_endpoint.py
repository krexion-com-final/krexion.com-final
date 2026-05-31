"""Regression tests for the 2026-06 Health Check / Preflight Trace endpoint.

The endpoint:
    POST /api/real-user-traffic/health-check

  • Validates an automation_json against a target URL on ONE browser
  • Returns per-step trace (idx, action, ok, ms, note, error, friendly_hint)
  • Does NOT write to DB, consume proxies, or use leads
  • Surfaces `note` for evaluate steps showing native-click frame match

Run:
    cd /app/backend && python3 -m pytest tests/test_health_check_endpoint.py -v
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from real_user_traffic import run_health_check


async def _run_simple_check():
    """Happy path: 2 simple steps on example.com → all ok."""
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")
    steps = [
        {"action": "wait", "ms": 300},
        {"action": "screenshot", "name": "final", "optional": True},
    ]
    result = await run_health_check(
        target_url="https://example.com",
        automation_steps=steps,
        timeout_sec=40,
    )
    assert result["ok"] is True, f"Expected ok=True, got: {result}"
    assert result["executed_steps"] == 2
    assert result["total_steps"] == 2
    assert result["failed_at_idx"] is None
    assert len(result["step_results"]) == 2
    for sr in result["step_results"]:
        assert sr["ok"] is True
        assert sr["ms"] >= 0
    return result


def test_health_check_happy_path():
    result = asyncio.run(_run_simple_check())
    print(f"\n[HEALTH CHECK happy path] {result['duration_ms']}ms, "
          f"steps={result['executed_steps']}, final={result['final_url']}")


async def _run_failure_check():
    """Failure path: click a selector that doesn't exist → failed."""
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")
    steps = [
        {"action": "wait", "ms": 200},
        {"action": "click", "selector": "#nonexistent-xyz-abc-99", "timeout": 1500},
    ]
    result = await run_health_check(
        target_url="https://example.com",
        automation_steps=steps,
        timeout_sec=40,
    )
    assert result["ok"] is False
    assert result["failed_at_idx"] == 1
    assert result["error"]
    # First step (wait) should have succeeded
    assert result["step_results"][0]["ok"] is True
    # Second step (click) should have failed
    failed_step = result["step_results"][1]
    assert failed_step["ok"] is False
    assert failed_step["error"]
    return result


def test_health_check_failure_path():
    result = asyncio.run(_run_failure_check())
    print(f"\n[HEALTH CHECK failure path] failed_at={result['failed_at_idx']}, "
          f"error={(result['error'] or '')[:80]}")


async def _run_evaluate_with_note():
    """Confirm evaluate steps that hit the native-click path surface a
    `note` field on the step_result so the operator can see WHICH text
    was picked and WHICH frame it matched.
    """
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")
    # Script with a random-pick pattern. example.com has no such buttons
    # so native click will fail → falls back to JS → note still shows
    # the native-click attempt outcome.
    js = (
        "(function(){var labels=['Super Low Prices','Trendy Styles','Free Returns'];"
        "var pick=labels[Math.floor(Math.random()*labels.length)];})();"
    )
    steps = [
        {"action": "wait", "ms": 200},
        {"action": "evaluate", "script": js},
    ]
    result = await run_health_check(
        target_url="https://example.com",
        automation_steps=steps,
        timeout_sec=40,
    )
    # The evaluate step succeeded (the JS is a no-op after picking, no error)
    evaluate_sr = result["step_results"][1]
    assert evaluate_sr["action"] == "evaluate"
    # The native-click pre-processor should have run and pushed a note
    assert "note" in evaluate_sr, f"Expected note field, got: {evaluate_sr}"
    assert "native_click" in evaluate_sr["note"], f"Expected native_click in note, got: {evaluate_sr['note']}"
    return result


def test_health_check_evaluate_note_field():
    result = asyncio.run(_run_evaluate_with_note())
    note = result["step_results"][1].get("note", "")
    print(f"\n[HEALTH CHECK evaluate note] '{note[:120]}'")
