"""
Iteration 7 — Backend tests for the refactored Visual Recorder /start flow
(non-blocking + state lifecycle) and RUT live-steps endpoint contract.

Validates the changes described in the iteration-7 review request:
    1. /start returns immediately (<2s) with state="starting"
    2. /state transitions starting → ready within ~5s for direct conn to example.com
    3. /screenshot returns 202 while starting, 200 image/jpeg once ready
    4. Bad proxy: /start still returns immediately; state eventually error/ready
    5. Interaction endpoints return 409 when state != ready
    6. DELETE cleans up + cancels pending startup task
    7. RUT live-steps endpoint still exists & module imports cleanly
    8. /api/diagnostics/health returns 200 with mongodb=ok
"""

import os
import time
import pytest
import requests


# ── Resolve BASE_URL from frontend/.env (REACT_APP_BACKEND_URL) ──────────
def _read_base_url():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for ln in f:
                if ln.strip().startswith("REACT_APP_BACKEND_URL="):
                    return ln.strip().split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found in /app/frontend/.env")


BASE_URL = _read_base_url()
TEST_EMAIL = "vrtest@test.local"
TEST_PASSWORD = "TestPass2026!"


# ── Fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("access_token")
    assert tok, "No access_token in login response"
    return tok


@pytest.fixture(scope="session")
def auth_client(auth_token):
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    })
    return s


@pytest.fixture
def cleanup_sessions(auth_client):
    """Track session_ids created in each test and DELETE them after."""
    created = []
    yield created
    for sid in created:
        try:
            auth_client.delete(f"{BASE_URL}/api/visual-recorder/{sid}", timeout=10)
        except Exception:
            pass


# ── 0. Sanity health ─────────────────────────────────────────────────────
def test_health_mongo_and_playwright_ok():
    r = requests.get(f"{BASE_URL}/api/diagnostics/health", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["checks"]["mongodb"]["status"] == "ok"
    # Playwright must be installed for the VR /start to work end-to-end
    assert body["checks"]["playwright"]["status"] == "ok", body["checks"]["playwright"]


# ── 1. /start returns immediately with state=starting ────────────────────
def test_start_returns_in_under_2s_with_state_starting(auth_client, cleanup_sessions):
    t0 = time.monotonic()
    r = auth_client.post(
        f"{BASE_URL}/api/visual-recorder/start",
        json={"url": "https://example.com"},
        timeout=10,
    )
    elapsed = time.monotonic() - t0
    assert r.status_code == 200, r.text
    assert elapsed < 2.0, f"/start took {elapsed:.2f}s — must return in <2s"
    body = r.json()
    assert "session_id" in body and body["session_id"]
    assert body["state"] in ("starting", "ready"), body
    # error_message field MUST be present (even if empty)
    assert "error_message" in body
    cleanup_sessions.append(body["session_id"])


# ── 2. /state transitions starting → ready within ~10s for direct conn ───
def test_state_transitions_to_ready_for_example_com(auth_client, cleanup_sessions):
    r = auth_client.post(
        f"{BASE_URL}/api/visual-recorder/start",
        json={"url": "https://example.com"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    cleanup_sessions.append(sid)

    final_state = None
    deadline = time.monotonic() + 25.0  # generous
    while time.monotonic() < deadline:
        sr = auth_client.get(f"{BASE_URL}/api/visual-recorder/{sid}/state", timeout=10)
        assert sr.status_code == 200, sr.text
        body = sr.json()
        assert body["state"] in ("starting", "ready", "error", "stopped"), body
        assert "elapsed_seconds" in body
        if body["state"] in ("ready", "error"):
            final_state = body["state"]
            assert "error_message" in body
            if body["state"] == "ready":
                assert isinstance(body.get("page"), (dict, type(None)))
            break
        time.sleep(0.8)

    assert final_state == "ready", (
        f"Expected state to reach 'ready', got {final_state}. "
        "Direct connection to example.com should succeed within 25s."
    )


# ── 3. /screenshot 202 while starting, 200 jpeg once ready ───────────────
def test_screenshot_202_while_starting_then_200_when_ready(auth_client, cleanup_sessions):
    r = auth_client.post(
        f"{BASE_URL}/api/visual-recorder/start",
        json={"url": "https://example.com"},
        timeout=10,
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]
    cleanup_sessions.append(sid)

    # Immediate screenshot — likely 202 (state=starting). Even if the bg task
    # finished in <1ms, accept 200; the contract is "no 5xx, no hang".
    sc = auth_client.get(f"{BASE_URL}/api/visual-recorder/{sid}/screenshot", timeout=10)
    assert sc.status_code in (200, 202), sc.text
    if sc.status_code == 202:
        body = sc.json()
        assert body.get("state") in ("starting", "error"), body
        assert "error_message" in body

    # Now wait for ready and verify 200 image/jpeg
    deadline = time.monotonic() + 25.0
    is_ready = False
    while time.monotonic() < deadline:
        st = auth_client.get(f"{BASE_URL}/api/visual-recorder/{sid}/state", timeout=10).json()
        if st["state"] == "ready":
            is_ready = True
            break
        if st["state"] == "error":
            pytest.fail(f"Session went to error: {st.get('error_message')}")
        time.sleep(0.7)
    assert is_ready, "Session never reached 'ready' within 25s"

    sc2 = auth_client.get(f"{BASE_URL}/api/visual-recorder/{sid}/screenshot", timeout=15)
    assert sc2.status_code == 200, sc2.text
    assert sc2.headers.get("content-type", "").startswith("image/jpeg"), sc2.headers
    assert len(sc2.content) > 1000, f"Screenshot too small: {len(sc2.content)} bytes"


# ── 4. Bad proxy: /start still non-blocking, no hang, no 5xx ─────────────
def test_bad_proxy_start_does_not_hang(auth_client, cleanup_sessions):
    t0 = time.monotonic()
    r = auth_client.post(
        f"{BASE_URL}/api/visual-recorder/start",
        json={"url": "https://example.com", "proxy": "http://1.2.3.4:9999"},
        timeout=10,
    )
    elapsed = time.monotonic() - t0
    assert r.status_code == 200, r.text
    assert elapsed < 2.0, f"/start with bad proxy took {elapsed:.2f}s — must return immediately"
    body = r.json()
    assert body["state"] in ("starting", "error", "ready"), body
    sid = body["session_id"]
    cleanup_sessions.append(sid)

    # The state must eventually settle (within the 30s STARTUP_TIMEOUT_S +
    # buffer) to either 'ready' or 'error' — never hang at 'starting'.
    deadline = time.monotonic() + 45.0
    settled = None
    while time.monotonic() < deadline:
        st = auth_client.get(f"{BASE_URL}/api/visual-recorder/{sid}/state", timeout=10).json()
        if st["state"] in ("ready", "error", "stopped"):
            settled = st
            break
        time.sleep(1.0)
    assert settled is not None, "State never settled — /start background task hung"
    assert settled["state"] in ("ready", "error"), settled
    if settled["state"] == "error":
        assert settled.get("error_message"), "error state must have error_message"


# ── 5. Interaction endpoints return 409 in state=starting ────────────────
def test_interaction_returns_409_while_starting(auth_client, cleanup_sessions):
    """Use a bad proxy so the session stays in 'starting' long enough to test."""
    r = auth_client.post(
        f"{BASE_URL}/api/visual-recorder/start",
        json={"url": "https://example.com", "proxy": "http://1.2.3.4:9999"},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    sid = body["session_id"]
    cleanup_sessions.append(sid)

    # With a dead proxy the bg task spends up to 30s before timing out, so
    # state will be 'starting' for a while. Try interactions immediately.
    if body["state"] != "starting":
        pytest.skip(f"Session settled too quickly ({body['state']}) — can't test 'starting' 409")

    # Bodies must satisfy the Pydantic schemas (otherwise we'd 422 before 409)
    endpoints = [
        ("post", "/click", {"x": 10, "y": 10}),
        ("post", "/type", {"selector": "input", "value": "x"}),
        ("post", "/wait", {"ms": 1000}),
        ("post", "/wait-load", {}),
        ("post", "/scroll", {"y": 100}),
        ("post", "/navigate", {"url": "https://example.com"}),
        ("post", "/group-random", {"count": 2}),
        ("post", "/mark-final", {}),
    ]
    for method, path, payload in endpoints:
        url = f"{BASE_URL}/api/visual-recorder/{sid}{path}"
        resp = auth_client.request(method, url, json=payload, timeout=10)
        # Must reject with 409 — must not hang or 500
        assert resp.status_code == 409, (
            f"{method.upper()} {path} expected 409 in starting state, got "
            f"{resp.status_code}: {resp.text[:200]}"
        )
        detail = resp.json().get("detail", "")
        assert "connecting" in detail.lower() or "not ready" in detail.lower() \
            or "still" in detail.lower() or "failed" in detail.lower(), detail


# ── 6. DELETE stops session cleanly ──────────────────────────────────────
def test_delete_session_cancels_startup(auth_client):
    r = auth_client.post(
        f"{BASE_URL}/api/visual-recorder/start",
        json={"url": "https://example.com", "proxy": "http://1.2.3.4:9999"},
        timeout=10,
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]

    d = auth_client.delete(f"{BASE_URL}/api/visual-recorder/{sid}", timeout=15)
    assert d.status_code == 200, d.text
    assert d.json().get("stopped") in (True, False)  # bool

    # Subsequent /state must 404 (session removed) — give it a moment for cleanup
    time.sleep(0.5)
    sr = auth_client.get(f"{BASE_URL}/api/visual-recorder/{sid}/state", timeout=10)
    assert sr.status_code == 404, sr.text


# ── 7. /state on unknown session = 404 ───────────────────────────────────
def test_state_unknown_session_returns_404(auth_client):
    r = auth_client.get(
        f"{BASE_URL}/api/visual-recorder/00000000-0000-0000-0000-000000000000/state",
        timeout=10,
    )
    assert r.status_code == 404


# ── 8. RUT module loads (jobs list) and live-steps endpoint contract ─────
def test_rut_jobs_list_loads_module_cleanly(auth_client):
    """Hitting /jobs imports real_user_traffic.py — verifies no SyntaxError
    introduced by the new stage labels (landing/form_filled/post_submit/final)."""
    r = auth_client.get(f"{BASE_URL}/api/real-user-traffic/jobs", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    # iter6 confirmed shape: {"jobs":[...]}
    assert "jobs" in body and isinstance(body["jobs"], list), body


def test_rut_live_steps_endpoint_does_not_500(auth_client):
    """For a non-existent job_id the endpoint should return 404 (or 200 with
    empty steps), but NEVER 500."""
    fake_id = "TEST_iter7_nonexistent_job"
    r = auth_client.get(
        f"{BASE_URL}/api/real-user-traffic/jobs/{fake_id}/live-steps",
        timeout=15,
    )
    assert r.status_code in (200, 400, 404), (
        f"live-steps unexpected {r.status_code}: {r.text[:300]}"
    )
    if r.status_code == 200:
        body = r.json()
        # Should at least have a steps key
        assert "steps" in body or "running" in body, body


# ── 9. Source-grep: stage labels present in real_user_traffic.py ─────────
def test_source_has_four_stage_labels():
    """Sanity check that the 4 RUT stage labels are present in the module."""
    with open("/app/backend/real_user_traffic.py") as f:
        src = f.read()
    for label in ("landing", "form_filled", "post_submit", "final"):
        assert label in src, f"Stage label '{label}' missing from real_user_traffic.py"


# ── 10. Source-grep: VR state machine present ────────────────────────────
def test_source_has_vr_state_lifecycle():
    with open("/app/backend/visual_recorder.py") as f:
        src = f.read()
    assert "STARTUP_TIMEOUT_S" in src
    assert "asyncio.wait_for" in src
    assert "_init_browser_bg" in src
    for st in ('"starting"', '"ready"', '"error"', '"stopped"'):
        assert st in src, f"State literal {st} missing"
    with open("/app/backend/server.py") as f:
        srv = f.read()
    assert "_vr_require_ready" in srv
    assert "status_code=409" in srv
    assert "status_code=202" in srv  # JSONResponse(202) on /screenshot
