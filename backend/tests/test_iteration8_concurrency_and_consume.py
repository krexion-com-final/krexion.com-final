"""
Iteration 8 — Backend verification for:
  (a) RUT memory-leak fix (smoke: jobs list still loads, engine status OK)
  (b) Uploaded Things physical row deletion when consumed by RUT
  (c) Concurrency boundary 1..50 (was 20) — 50 OK, 51 → 4xx
  (d) Overall backend health (auth, dashboard, links, clicks, conversions,
      proxies, uploads listing).

NOTE on endpoint names: the review request mentioned
`/api/rut/jobs` and `/api/uploaded-resources`. Those paths do NOT
exist in server.py — actual routes are
`/api/real-user-traffic/jobs` and `/api/uploads`. We use the real
ones and call this out in the test report.
"""
import os
import sys
import time
import uuid
import asyncio

import httpx
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    # Fall back to the frontend .env which is the source of truth for the
    # public preview URL (required for SPA route smoke checks).
    try:
        for line in open("/app/frontend/.env").read().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break
    except Exception:
        pass
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
USER_EMAIL = "vrtest@test.local"
USER_PASSWORD = "TestPass2026!"

sys.path.insert(0, "/app/backend")


@pytest.fixture(scope="module")
def shared_loop():
    """Single event loop reused across tests so motor's IOLoop binding stays valid."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


def _run_consume(loop, user_id, upload_id, *, proxies=None, uas=None):
    from server import _consume_uploads
    return loop.run_until_complete(
        _consume_uploads(
            user_id, [upload_id],
            used_proxy_raws=proxies or [],
            used_ua_strings=uas or [],
        )
    )


# ─────────────────── shared fixtures ───────────────────
@pytest.fixture(scope="module")
def auth_token():
    r = httpx.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"auth/login failed: {r.status_code} {r.text}"
    body = r.json()
    assert "access_token" in body and isinstance(body["access_token"], str)
    assert "user" in body
    feats = (body["user"].get("features") or {})
    assert feats.get("real_user_traffic") is True, f"real_user_traffic not enabled: {feats}"
    return body["access_token"]


@pytest.fixture(scope="module")
def H(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def user_id(auth_token):
    r = httpx.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ─────────────────── 1. Auth + dashboard health ───────────────────
def test_login_returns_token_and_user(auth_token):
    assert isinstance(auth_token, str) and len(auth_token) > 20


def test_dashboard_stats_shape(H):
    r = httpx.get(f"{BASE_URL}/api/dashboard/stats", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("total_clicks", "total_conversions"):
        assert k in data, f"missing {k} in {data}"
    assert isinstance(data["total_clicks"], int)
    assert isinstance(data["total_conversions"], int)


@pytest.mark.parametrize("path", [
    "/api/links",
    "/api/clicks",
    "/api/conversions",
    "/api/proxies",
    "/api/uploads",
])
def test_basic_list_endpoints(H, path):
    r = httpx.get(f"{BASE_URL}{path}", headers=H, timeout=30)
    assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:200]}"
    assert isinstance(r.json(), list)


def test_rut_jobs_list_loads(H):
    """Smoke: GC/cleanup additions in real_user_traffic.py didn't break import."""
    r = httpx.get(f"{BASE_URL}/api/real-user-traffic/jobs", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    # Endpoint returns either a list or {jobs:[...]}
    if isinstance(body, dict):
        assert "jobs" in body
        assert isinstance(body["jobs"], list)
    else:
        assert isinstance(body, list)


def test_rut_engine_status(H):
    r = httpx.get(f"{BASE_URL}/api/real-user-traffic/engine-status", headers=H, timeout=30)
    assert r.status_code == 200, r.text


# ─────────────────── 2. Concurrency boundary 1..50 ───────────────────
def _create_link(H):
    """Create a simple link to use as link_id for RUT job validation."""
    payload = {
        "offer_url": "https://example.com",
        "name": f"TEST_iter8_link_{int(time.time())}_{uuid.uuid4().hex[:6]}",
    }
    r = httpx.post(f"{BASE_URL}/api/links", json=payload, headers=H, timeout=30)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
def link_id(H):
    return _create_link(H)


def _post_rut_form(H, link_id, *, concurrency, target_clicks=1):
    data = {
        "link_id": link_id,
        "target_url": "https://example.com",
        "proxies": "1.2.3.4:8080",
        "user_agents": "Mozilla/5.0 TestUA-iter8",
        "total_clicks": str(target_clicks),
        "concurrency": str(concurrency),
        "duration_minutes": "0",
        "target_mode": "clicks",
        "skip_duplicate_ip": "false",
        "skip_vpn": "false",
        "follow_redirect": "false",
        "form_fill_enabled": "false",
        "use_stored_proxies": "false",
        "auto_resume_enabled": "false",
    }
    return httpx.post(
        f"{BASE_URL}/api/real-user-traffic/jobs",
        headers=H,
        data=data,
        timeout=30,
    )


def test_rut_concurrency_51_rejected(H, link_id):
    r = _post_rut_form(H, link_id, concurrency=51)
    assert r.status_code in (400, 422), \
        f"concurrency=51 should be rejected, got {r.status_code} {r.text[:300]}"
    body = (r.text or "").lower()
    assert "concurrency" in body or "1..50" in body or "50" in body


def test_rut_concurrency_50_accepted(H, link_id):
    r = _post_rut_form(H, link_id, concurrency=50)
    # 200/201 = job queued; 400 with anything OTHER than concurrency
    # validation = also acceptable (e.g. proxy validation downstream).
    if r.status_code in (200, 201):
        body = r.json()
        assert "job_id" in body or "id" in body
    else:
        # Make sure the failure isn't about concurrency
        assert r.status_code in (400, 422), r.text[:300]
        assert "concurrency" not in (r.text or "").lower(), \
            f"concurrency=50 unexpectedly rejected: {r.text[:300]}"


def test_rut_concurrency_1_accepted(H, link_id):
    r = _post_rut_form(H, link_id, concurrency=1)
    if r.status_code in (200, 201):
        body = r.json()
        assert "job_id" in body or "id" in body
    else:
        assert r.status_code in (400, 422), r.text[:300]
        assert "concurrency" not in (r.text or "").lower()


def test_rut_concurrency_0_rejected(H, link_id):
    r = _post_rut_form(H, link_id, concurrency=0)
    assert r.status_code in (400, 422)
    assert "concurrency" in (r.text or "").lower() or "1" in (r.text or "")


# ─────────── 3. _consume_uploads physical row deletion ───────────
def test_consume_uploads_removes_rows_and_marks_depleted(H, user_id, shared_loop):
    """Create proxy upload with 2 items → call _consume_uploads with both →
    GET /api/uploads must show item_count=0, depleted=true, db entry kept."""
    raw_lines = [
        f"u_iter8a:p@10.20.30.{int(time.time()) % 250}:8080",
        f"u_iter8b:p@10.20.30.{(int(time.time()) + 1) % 250}:9090",
    ]
    r = httpx.post(
        f"{BASE_URL}/api/uploads/proxies",
        headers=H,
        data={
            "name": f"TEST_iter8_{uuid.uuid4().hex[:8]}",
            "country_tag": "US",
            "proxies": "\n".join(raw_lines),
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    doc = r.json()
    upload_id = doc["id"]
    assert doc["item_count"] == 2
    assert doc["depleted"] is False

    # Invoke production helper directly (shared loop keeps motor binding valid)
    _run_consume(shared_loop, user_id, upload_id, proxies=raw_lines)

    # Verify state via API — db entry preserved, items[] emptied, depleted=true
    r = httpx.get(f"{BASE_URL}/api/uploads?type=proxies", headers=H, timeout=30)
    assert r.status_code == 200
    items = r.json()
    survivor = next((x for x in items if x["id"] == upload_id), None)
    assert survivor is not None, "upload was physically deleted — should be preserved"
    assert survivor["item_count"] == 0, f"item_count not 0: {survivor}"
    assert survivor["depleted"] is True, f"depleted flag not set: {survivor}"
    assert survivor.get("depleted_at"), "depleted_at not set"
    assert survivor["consumed_count"] >= 2

    # Cleanup
    httpx.delete(f"{BASE_URL}/api/uploads/{upload_id}", headers=H, timeout=30)


def test_consume_uploads_partial_keeps_remaining_rows(H, user_id, shared_loop):
    """3 proxies, consume 1 → item_count=2, depleted=false."""
    raw_lines = [
        f"p_iter8x:y@10.40.50.{i}:8080" for i in (101, 102, 103)
    ]
    r = httpx.post(
        f"{BASE_URL}/api/uploads/proxies",
        headers=H,
        data={
            "name": f"TEST_iter8_partial_{uuid.uuid4().hex[:8]}",
            "country_tag": "US",
            "proxies": "\n".join(raw_lines),
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    upload_id = r.json()["id"]

    _run_consume(shared_loop, user_id, upload_id, proxies=[raw_lines[0]])

    r = httpx.get(f"{BASE_URL}/api/uploads?type=proxies", headers=H, timeout=30)
    survivor = next((x for x in r.json() if x["id"] == upload_id), None)
    assert survivor is not None
    assert survivor["item_count"] == 2
    assert survivor["depleted"] is False
    assert survivor["consumed_count"] == 1

    httpx.delete(f"{BASE_URL}/api/uploads/{upload_id}", headers=H, timeout=30)


# ─────────────────── 4. Frontend smoke ───────────────────
def test_frontend_login_returns_html():
    # SPA route — Cloudflare ingress occasionally hiccups; retry up to 3 times.
    last = None
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        for _ in range(3):
            r = c.get(f"{BASE_URL}/login")
            last = r
            if r.status_code == 200:
                break
            time.sleep(1.0)
    assert last is not None and last.status_code == 200, \
        f"got {last.status_code if last else 'no response'}"
    body = last.text.lower()
    assert "<!doctype html" in body or "<html" in body
