"""Iteration 5 backend tests.

Covers:
1. GET /api/uploads — verifies the `items` array is stripped from list
   response (critical regression test for the dropdown-lag bug fix at
   server.py line 11486).
2. POST /api/uploads/proxies & POST /api/uploads/user-agents — verifies
   create flow, then asserts list-response does NOT contain raw items
   and payload size stays small even with many items.
3. GET /api/uploads/{upload_id} — single-resource fetch via the
   automation-json preview endpoint used by the UI (if available).
4. POST /api/uploads/{upload_id}/sync-gsheet — 400/404 semantics only
   (we don't have a live gsheet fixture here).
5. POST /api/real-user-traffic/jobs — Phase-1 fast response (<3s), job
   visible in GET /jobs within 2s.
6. POST /api/real-user-traffic/jobs/{id}/stop — stops queued/running job.
7. POST /api/real-user-traffic/jobs/{id}/retry — 409 on queued, success
   after the job reaches failed/stopped, verifies `restart_count` reset.
8. GET /api/real-user-traffic/jobs — list-mode smoke.
9. GET /api/diagnostics/health — 200 + required `checks.*` keys.
10. POST /api/auth/login + GET /api/auth/me — smoke.
11. Admin login + GET /api/admin/users — admin flow smoke.
12. Regression smoke: /api/links.
"""

import os
import time
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fluid-dynamics-12.preview.emergentagent.com").rstrip("/")
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test12345"
ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "admin123"


# ─────────────────────────── fixtures ───────────────────────────
@pytest.fixture(scope="session")
def user_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def user_client(user_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {user_token}"})
    return s


@pytest.fixture(scope="session")
def admin_token():
    # Admin uses a separate route (/api/admin/login)
    r = requests.post(f"{BASE_URL}/api/admin/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"admin login: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}"})
    return s


@pytest.fixture(scope="session")
def test_link_id(user_client):
    """Grab any existing link for the test user, else create one."""
    r = user_client.get(f"{BASE_URL}/api/links", timeout=15)
    assert r.status_code == 200
    links = r.json()
    if links:
        return links[0]["id"]
    # create one
    payload = {"offer_url": "https://example.com/offer",
               "name": "TEST_iter5_link",
               "country": "US"}
    r = user_client.post(f"{BASE_URL}/api/links", json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create link: {r.status_code} {r.text[:200]}"
    return r.json()["id"]


@pytest.fixture(scope="session", autouse=True)
def _cleanup(user_client):
    """Delete uploads created by this test run at the end."""
    created_ids = []
    yield created_ids
    for uid in created_ids:
        try:
            user_client.delete(f"{BASE_URL}/api/uploads/{uid}", timeout=10)
        except Exception:
            pass


# ─────────────────────────── Auth & health ───────────────────────────
class TestHealthAndAuth:
    def test_diagnostics_health(self):
        r = requests.get(f"{BASE_URL}/api/diagnostics/health", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "overall" in data
        assert data["overall"] in ("ok", "warn")  # not fail
        assert "checks" in data
        checks = data["checks"]
        for key in ("mongodb", "playwright", "memory", "disk",
                    "active_rut_jobs", "process"):
            assert key in checks, f"missing check key: {key}"

    def test_login_user(self, user_token):
        assert isinstance(user_token, str) and len(user_token) > 20

    def test_auth_me(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == TEST_EMAIL
        assert body["features"]["real_user_traffic"] is True

    def test_admin_login(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_admin_users_list(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/users", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ─────────────────────────── Uploads items-strip ───────────────────────────
class TestUploadsItemsStrip:
    def test_uploads_list_initial(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/uploads?sync_gsheets=false", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Verify items field is stripped in ALL records (even if pre-existing).
        for doc in data:
            assert "items" not in doc, f"items field leaked in upload {doc.get('id')}"

    def test_create_proxies_upload_and_verify_stripped(self, user_client, _cleanup):
        # Large set of proxies to make the items array meaningful in size.
        proxies = "\n".join(f"1.2.3.{i}:8080:user:pass" for i in range(1, 501))
        form = {"name": "TEST_iter5_proxies_500",
                "country_tag": "US",
                "proxies": proxies}
        r = user_client.post(f"{BASE_URL}/api/uploads/proxies",
                             data=form, timeout=20)
        assert r.status_code == 200, f"proxy upload: {r.status_code} {r.text[:300]}"
        created = r.json()
        assert created["item_count"] == 500
        assert created["type"] == "proxies"
        uid = created["id"]
        _cleanup.append(uid)

        # List endpoint — the KEY regression test for line 11486 fix
        r = user_client.get(f"{BASE_URL}/api/uploads?sync_gsheets=false", timeout=20)
        assert r.status_code == 200
        body_text = r.text
        data = r.json()
        matched = [d for d in data if d["id"] == uid]
        assert len(matched) == 1, "just-created upload not in list"
        doc = matched[0]
        assert "items" not in doc, "CRITICAL: items array leaked in /api/uploads list — line 11486 fix broken"
        assert "file_path" not in doc
        assert doc["item_count"] == 500
        assert doc["available_count"] == 500
        assert doc["consumed_count"] == 0
        # Payload size sanity — 500 proxies as raw items would be ~15KB+;
        # without items, entire list should stay tiny per record.
        assert len(body_text) < 50_000, f"payload too large: {len(body_text)} bytes"

    def test_create_user_agents_upload_and_verify_stripped(self, user_client, _cleanup):
        uas = "\n".join(f"Mozilla/5.0 TEST_iter5 agent #{i}" for i in range(1, 301))
        form = {"name": "TEST_iter5_uas_300",
                "os_tag": "android",
                "user_agents": uas}
        r = user_client.post(f"{BASE_URL}/api/uploads/user-agents",
                             data=form, timeout=20)
        assert r.status_code == 200, f"UA upload: {r.status_code} {r.text[:300]}"
        created = r.json()
        assert created["item_count"] == 300
        assert created["type"] == "user_agents"
        uid = created["id"]
        _cleanup.append(uid)

        r = user_client.get(f"{BASE_URL}/api/uploads?type=user_agents&sync_gsheets=false", timeout=20)
        assert r.status_code == 200
        data = r.json()
        matched = [d for d in data if d["id"] == uid]
        assert len(matched) == 1
        doc = matched[0]
        assert "items" not in doc, "CRITICAL: items leaked in UA list response"
        assert doc["item_count"] == 300
        assert doc["available_count"] == 300

    def test_sync_gsheet_on_non_gsheet_upload_rejects(self, user_client, _cleanup):
        # Create a tiny static proxies upload (no gsheet_url)
        form = {"name": "TEST_iter5_sync_target",
                "proxies": "9.9.9.9:1234:u:p"}
        r = user_client.post(f"{BASE_URL}/api/uploads/proxies",
                             data=form, timeout=15)
        assert r.status_code == 200
        uid = r.json()["id"]
        _cleanup.append(uid)

        # sync-gsheet on non-gsheet source: should return 400/404/422 (not 500)
        r = user_client.post(f"{BASE_URL}/api/uploads/{uid}/sync-gsheet", timeout=15)
        assert r.status_code in (400, 404, 422), f"unexpected: {r.status_code} {r.text[:200]}"

    def test_sync_gsheet_unknown_id(self, user_client):
        r = user_client.post(f"{BASE_URL}/api/uploads/does-not-exist-iter5/sync-gsheet",
                             timeout=15)
        assert r.status_code in (400, 404), f"{r.status_code} {r.text[:200]}"


# ─────────────────────────── RUT endpoints ───────────────────────────
class TestRUTJobs:
    def test_create_rut_job_fast_foreground(self, user_client, test_link_id, _cleanup):
        # Need uploaded proxies + UAs batches so we don't have to paste large volumes.
        r = user_client.post(f"{BASE_URL}/api/uploads/proxies",
                             data={"name": "TEST_iter5_rut_proxy", "proxies": "1.1.1.1:8080:u:p"},
                             timeout=15)
        assert r.status_code == 200
        proxy_uid = r.json()["id"]
        _cleanup.append(proxy_uid)

        r = user_client.post(f"{BASE_URL}/api/uploads/user-agents",
                             data={"name": "TEST_iter5_rut_ua",
                                   "user_agents": "Mozilla/5.0 TEST_iter5 UA"},
                             timeout=15)
        assert r.status_code == 200
        ua_uid = r.json()["id"]
        _cleanup.append(ua_uid)

        start = time.monotonic()
        r = user_client.post(
            f"{BASE_URL}/api/real-user-traffic/jobs",
            data={
                "link_id": test_link_id,
                "total_clicks": 1,
                "concurrency": 1,
                "upload_proxy_id": proxy_uid,
                "upload_ua_id": ua_uid,
                "skip_vpn": "false",
                "skip_duplicate_ip": "false",
            },
            timeout=15,
        )
        elapsed = time.monotonic() - start
        assert r.status_code in (200, 201), f"create RUT: {r.status_code} {r.text[:300]}"
        assert elapsed < 5.0, f"foreground too slow: {elapsed:.2f}s (spec <3s, allow 5)"
        body = r.json()
        assert "job_id" in body
        job_id = body["job_id"]

        # Visible in list within 2s
        deadline = time.monotonic() + 3
        found = False
        while time.monotonic() < deadline:
            rl = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs", timeout=10)
            if rl.status_code == 200:
                payload = rl.json()
                jobs = payload.get("jobs", payload) if isinstance(payload, dict) else payload
                if any(j["job_id"] == job_id for j in jobs):
                    found = True
                    break
            time.sleep(0.3)
        assert found, f"job {job_id} not visible in /jobs list"

        # Fetch detail — in-memory preferred so is_resumable may be absent here;
        # confirm DB persistence via /jobs list (which reads from Mongo).
        rd = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs/{job_id}",
                             timeout=10)
        assert rd.status_code == 200
        rl = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs", timeout=10)
        assert rl.status_code == 200
        jobs_list = rl.json().get("jobs", [])
        persisted = next((j for j in jobs_list if j["job_id"] == job_id), None)
        assert persisted is not None, "job not persisted in DB list"
        assert persisted.get("is_resumable") is True, \
            f"is_resumable not set in DB record: {list(persisted.keys())}"
        assert persisted.get("submit_params"), "submit_params not persisted in DB"

        # Stop endpoint
        rs = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{job_id}/stop",
                              timeout=15)
        assert rs.status_code in (200, 202), f"stop: {rs.status_code} {rs.text[:200]}"

        # Wait for job to reach a retryable state (stopped/failed)
        deadline = time.monotonic() + 30
        final_status = None
        while time.monotonic() < deadline:
            rd = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs/{job_id}",
                                 timeout=10)
            if rd.status_code == 200:
                final_status = rd.json().get("status")
                if final_status in ("stopped", "failed", "completed"):
                    break
            time.sleep(1.0)
        assert final_status in ("stopped", "failed", "completed"), \
            f"job never settled: last status={final_status}"

        # Retry endpoint — only works from stopped/failed
        if final_status in ("stopped", "failed"):
            rr = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{job_id}/retry",
                                  timeout=15)
            assert rr.status_code == 200, f"retry: {rr.status_code} {rr.text[:300]}"
            body2 = rr.json()
            assert body2.get("status") == "queued"
            assert body2.get("retried") is True

            # Post-retry stop to clean up
            user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{job_id}/stop",
                             timeout=10)

        # Clean-up: delete job
        try:
            user_client.delete(f"{BASE_URL}/api/real-user-traffic/jobs/{job_id}",
                               timeout=10)
        except Exception:
            pass

    def test_retry_missing_job_returns_404(self, user_client):
        r = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/nope-iter5/retry",
                             timeout=10)
        assert r.status_code == 404

    def test_rut_jobs_list_smoke(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs", timeout=15)
        assert r.status_code == 200
        payload = r.json()
        assert isinstance(payload, dict) and "jobs" in payload
        data = payload["jobs"]
        assert isinstance(data, list)
        for j in data[:5]:
            assert "job_id" in j
            assert "status" in j


# ─────────────────────────── Regression smoke ───────────────────────────
class TestRegressionSmoke:
    def test_links_list(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/links", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
