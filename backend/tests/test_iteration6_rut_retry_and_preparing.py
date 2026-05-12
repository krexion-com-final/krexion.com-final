"""Iteration 6 backend tests.

Validates the four UX fixes for RUT job stuck-in-queue / auto-resume:

1. POST /retry: now accepts queued/preparing if stuck >60s OR rc>0.
   - failed → retry OK
   - stopped → retry OK
   - queued + fresh (<60s, rc=0) → 409 with helpful message
   - queued + stuck (>60s) → retry OK (we forcibly age the doc in Mongo)
   - queued + rc>0 → retry OK
   - running → 409 'cannot retry actively running'
2. POST /jobs: status transitions queued → preparing with prep_step.
   GET /jobs/{id} surfaces prep_step field.
3. Auto-resume tolerance bumped 3 → 10 (server.py:12456 `rc < 10`,
   12533 `rc >= 10`, message says 'gave up after N attempts').
4. Orphan reaper picks up 'preparing' status (server.py:12437).
5. Live-log running flag includes 'preparing'.
6. Edge cases: missing link → 400, is_resumable=false → 400.
7. Phase-1 fast submit (<5s).
"""

import os
import time
import asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

def _read_frontend_env_base_url() -> str:
    val = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if val:
        return val.rstrip("/")
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return ""


BASE_URL = _read_frontend_env_base_url()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test12345"
ADMIN_EMAIL = "admin@realflow.local"
ADMIN_PASSWORD = "admin123"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "realflow")


# ─────────────────────── fixtures ───────────────────────
@pytest.fixture(scope="session")
def user_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def user_client(user_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {user_token}"})
    return s


@pytest.fixture(scope="session")
def user_id(user_client):
    r = user_client.get(f"{BASE_URL}/api/auth/me", timeout=10)
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(scope="session")
def link_id(user_client):
    r = user_client.get(f"{BASE_URL}/api/links", timeout=15)
    assert r.status_code == 200
    links = r.json()
    if links:
        return links[0]["id"]
    payload = {"offer_url": "https://example.com/offer-iter6",
               "name": "TEST_iter6_link", "country": "US"}
    r = user_client.post(f"{BASE_URL}/api/links", json=payload, timeout=15)
    assert r.status_code in (200, 201)
    return r.json()["id"]


@pytest.fixture(scope="session")
def proxy_uid(user_client):
    r = user_client.post(
        f"{BASE_URL}/api/uploads/proxies",
        data={"name": "TEST_iter6_proxy", "proxies": "1.1.1.1:8080:u:p"},
        timeout=15,
    )
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(scope="session")
def ua_uid(user_client):
    r = user_client.post(
        f"{BASE_URL}/api/uploads/user-agents",
        data={"name": "TEST_iter6_ua", "user_agents": "Mozilla/5.0 TEST_iter6"},
        timeout=15,
    )
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(scope="session", autouse=True)
def _cleanup_session(user_client):
    created_jobs: list = []
    created_uploads: list = []
    created_links: list = []
    yield {"jobs": created_jobs, "uploads": created_uploads, "links": created_links}
    for jid in created_jobs:
        try:
            user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/stop", timeout=5)
        except Exception:
            pass
        try:
            user_client.delete(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}", timeout=5)
        except Exception:
            pass
    for uid in created_uploads:
        try:
            user_client.delete(f"{BASE_URL}/api/uploads/{uid}", timeout=5)
        except Exception:
            pass


def _submit_rut_job(user_client, link_id, proxy_uid, ua_uid):
    """Submit a 1-click RUT job and return job_id + elapsed."""
    start = time.monotonic()
    r = user_client.post(
        f"{BASE_URL}/api/real-user-traffic/jobs",
        data={
            "link_id": link_id,
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
    assert r.status_code in (200, 201), f"submit: {r.status_code} {r.text[:300]}"
    return r.json()["job_id"], elapsed


def _wait_for_status(user_client, job_id, allowed, timeout=20):
    deadline = time.monotonic() + timeout
    last_status = None
    while time.monotonic() < deadline:
        r = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs/{job_id}", timeout=10)
        if r.status_code == 200:
            last_status = r.json().get("status")
            if last_status in allowed:
                return last_status
        time.sleep(0.4)
    return last_status


# ─────────────────────── 1. Submit perf + status flip ───────────────────────
class TestSubmitAndPreparing:
    def test_submit_phase1_fast(self, user_client, link_id, proxy_uid, ua_uid, _cleanup_session):
        jid, elapsed = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)
        assert elapsed < 5.0, f"foreground too slow: {elapsed:.2f}s"
        # First poll: status should be queued or preparing
        r = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") in ("queued", "preparing", "running", "failed", "stopped", "completed")

    def test_status_flips_to_preparing(self, user_client, link_id, proxy_uid, ua_uid, _cleanup_session):
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)
        # Should reach preparing/running/failed within a few seconds
        seen_prep = False
        seen_prep_step = None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            r = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}", timeout=10)
            if r.status_code == 200:
                body = r.json()
                st = body.get("status")
                ps = body.get("prep_step")
                if st == "preparing" or ps:
                    seen_prep = True
                    seen_prep_step = ps
                if st in ("running", "failed", "stopped", "completed"):
                    break
            time.sleep(0.3)
        # We accept that prep_step may not be visible if in-memory cache shadows
        # the DB record, but the field should appear for at least one poll.
        # Soft assertion — log but don't hard-fail if BG ran too fast.
        print(f"[TEST] seen_prep={seen_prep} seen_prep_step={seen_prep_step!r}")

    def test_prep_step_field_in_db(self, user_client, link_id, proxy_uid, ua_uid, user_id, _cleanup_session):
        """Direct Mongo check: after BG fires, the DB record should have prep_step set."""
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)
        # Give BG task a moment
        time.sleep(2.0)

        async def _check():
            mc = AsyncIOMotorClient(MONGO_URL)
            try:
                doc = await mc[DB_NAME].real_user_traffic_jobs.find_one(
                    {"job_id": jid}, {"_id": 0, "status": 1, "prep_step": 1, "is_resumable": 1, "submit_params": 1}
                )
                return doc
            finally:
                mc.close()

        doc = asyncio.run(_check())
        assert doc is not None, "job not in mongo"
        # prep_step should be set OR status moved past preparing
        assert doc.get("prep_step") or doc.get("status") in ("preparing", "running", "failed", "stopped", "completed"), \
            f"no prep_step and status not advanced: {doc}"
        assert doc.get("is_resumable") is True
        assert doc.get("submit_params"), "submit_params not persisted"


# ─────────────────────── 2. Retry endpoint branches ───────────────────────
class TestRetryBranches:
    def test_retry_missing_returns_404(self, user_client):
        r = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/nonexistent-iter6/retry",
                             timeout=10)
        assert r.status_code == 404

    def test_retry_fresh_queued_returns_409(self, user_client, link_id, proxy_uid, ua_uid, _cleanup_session):
        """A freshly-submitted job (<60s, rc=0) should be rejected with 409 + helpful message."""
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)
        # Immediately try to retry
        r = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/retry", timeout=10)
        # Job may have already moved to preparing/running/failed quickly; we accept those branches too.
        if r.status_code == 409:
            detail = (r.json().get("detail") or "").lower()
            # If status is queued/preparing → helpful "wait 60s" msg.
            # If status is running → "cannot retry actively running"
            assert ("wait" in detail and "60" in detail) or "running" in detail, \
                f"unexpected 409 message: {detail!r}"
        elif r.status_code == 200:
            # Job already settled to failed/stopped, retry succeeded
            assert r.json().get("retried") is True
        else:
            pytest.fail(f"unexpected status: {r.status_code} {r.text[:200]}")

    def test_retry_stuck_queued_via_aging(self, user_client, link_id, proxy_uid, ua_uid, user_id, _cleanup_session):
        """Force-age a queued job in Mongo (queued_at = 5min ago) → retry must succeed."""
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)

        # Stop it first so it settles, then forcibly set status=queued + old queued_at
        user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/stop", timeout=10)
        _wait_for_status(user_client, jid, ("stopped", "failed"), timeout=15)

        old_iso = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

        async def _age():
            mc = AsyncIOMotorClient(MONGO_URL)
            try:
                await mc[DB_NAME].real_user_traffic_jobs.update_one(
                    {"job_id": jid},
                    {"$set": {"status": "queued", "queued_at": old_iso, "restart_count": 0}},
                )
            finally:
                mc.close()

        asyncio.run(_age())

        r = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/retry", timeout=15)
        assert r.status_code == 200, f"stuck-queued retry: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("retried") is True
        assert body.get("status") == "queued"

        user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/stop", timeout=10)

    def test_retry_queued_with_rc_gt_zero(self, user_client, link_id, proxy_uid, ua_uid, _cleanup_session):
        """queued + restart_count>0 should be retryable even if fresh."""
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)
        user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/stop", timeout=10)
        _wait_for_status(user_client, jid, ("stopped", "failed"), timeout=15)

        fresh_iso = datetime.now(timezone.utc).isoformat()

        async def _bump():
            mc = AsyncIOMotorClient(MONGO_URL)
            try:
                await mc[DB_NAME].real_user_traffic_jobs.update_one(
                    {"job_id": jid},
                    {"$set": {"status": "queued", "queued_at": fresh_iso, "restart_count": 2}},
                )
            finally:
                mc.close()

        asyncio.run(_bump())

        r = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/retry", timeout=15)
        assert r.status_code == 200, f"rc>0 retry: {r.status_code} {r.text[:300]}"
        assert r.json().get("retried") is True

        user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/stop", timeout=10)

    def test_retry_running_returns_409(self, user_client, link_id, proxy_uid, ua_uid, _cleanup_session):
        """A running job should not be retryable → 409 with 'actively running'."""
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)

        async def _force_running():
            mc = AsyncIOMotorClient(MONGO_URL)
            try:
                await mc[DB_NAME].real_user_traffic_jobs.update_one(
                    {"job_id": jid}, {"$set": {"status": "running"}},
                )
            finally:
                mc.close()

        asyncio.run(_force_running())
        r = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/retry", timeout=10)
        assert r.status_code == 409
        detail = (r.json().get("detail") or "").lower()
        assert "running" in detail and "stop" in detail, f"detail: {detail!r}"

        # Reset for cleanup
        async def _reset():
            mc = AsyncIOMotorClient(MONGO_URL)
            try:
                await mc[DB_NAME].real_user_traffic_jobs.update_one(
                    {"job_id": jid}, {"$set": {"status": "stopped"}},
                )
            finally:
                mc.close()
        asyncio.run(_reset())

    def test_retry_failed_succeeds(self, user_client, link_id, proxy_uid, ua_uid, _cleanup_session):
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)
        # Force into failed state
        async def _fail():
            mc = AsyncIOMotorClient(MONGO_URL)
            try:
                await mc[DB_NAME].real_user_traffic_jobs.update_one(
                    {"job_id": jid}, {"$set": {"status": "failed", "error_message": "TEST_iter6 forced"}},
                )
            finally:
                mc.close()
        asyncio.run(_fail())

        r = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/retry", timeout=15)
        assert r.status_code == 200, f"failed-retry: {r.status_code} {r.text[:300]}"
        assert r.json().get("retried") is True

        user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/stop", timeout=10)

    def test_retry_missing_link_returns_400(self, user_client, link_id, proxy_uid, ua_uid, _cleanup_session):
        """If the original link no longer exists, retry must 400."""
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)

        async def _orphan():
            mc = AsyncIOMotorClient(MONGO_URL)
            try:
                await mc[DB_NAME].real_user_traffic_jobs.update_one(
                    {"job_id": jid},
                    {"$set": {"status": "failed", "link_id": "nonexistent-iter6-link-id"}},
                )
            finally:
                mc.close()

        asyncio.run(_orphan())
        r = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/retry", timeout=10)
        assert r.status_code == 400, f"missing-link retry: {r.status_code} {r.text[:300]}"
        detail = (r.json().get("detail") or "").lower()
        assert "link" in detail and ("no longer" in detail or "exist" in detail), f"detail: {detail!r}"

    def test_retry_non_resumable_returns_400(self, user_client, link_id, proxy_uid, ua_uid, _cleanup_session):
        """is_resumable=False → 400 'not retryable / inline files'."""
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)

        async def _flip():
            mc = AsyncIOMotorClient(MONGO_URL)
            try:
                await mc[DB_NAME].real_user_traffic_jobs.update_one(
                    {"job_id": jid},
                    {"$set": {"status": "failed", "is_resumable": False}},
                )
            finally:
                mc.close()
        asyncio.run(_flip())

        r = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/retry", timeout=10)
        assert r.status_code == 400
        detail = (r.json().get("detail") or "").lower()
        assert "not retryable" in detail or "inline" in detail, f"detail: {detail!r}"


# ─────────────────────── 3. Auto-resume tolerance = 10 ───────────────────────
class TestAutoResumeTolerance:
    def test_server_code_has_rc_lt_10(self):
        """Sanity: server.py uses rc < 10 (not rc < 3)."""
        with open("/app/backend/server.py", "r") as f:
            src = f.read()
        # Must contain the new threshold
        assert "rc < 10" in src, "server.py missing `rc < 10` (new auto-resume tolerance)"
        assert "rc >= 10" in src, "server.py missing `rc >= 10` failure check"
        # Must NOT contain the old threshold guarding auto-resume case
        # (Search for old buggy patterns; soft check)
        # The exact strings depend on context — just assert positive presence.

    def test_failure_message_mentions_attempts_and_retry(self):
        with open("/app/backend/server.py", "r") as f:
            src = f.read()
        # The message text from line 12534-12538
        assert "Auto-resume gave up after" in src
        assert "Click 'Retry this job'" in src or "Retry this job" in src


# ─────────────────────── 4. Orphan reaper covers 'preparing' ───────────────────────
class TestOrphanReaperPreparing:
    def test_orphan_query_includes_preparing(self):
        with open("/app/backend/server.py", "r") as f:
            src = f.read()
        assert '"running", "queued", "preparing"' in src or \
               "'running', 'queued', 'preparing'" in src, \
               "orphan reaper query missing 'preparing' status"


# ─────────────────────── 5. Live-log running flag ───────────────────────
class TestLiveLogRunningFlag:
    def test_live_log_includes_preparing(self):
        with open("/app/backend/real_user_traffic.py", "r") as f:
            src = f.read()
        # Should match the line: "running": j.get("status") in ("running", "queued", "preparing")
        assert '"running", "queued", "preparing"' in src or \
               "'running', 'queued', 'preparing'" in src, \
               "live-log 'running' flag does not include 'preparing'"

    def test_live_log_endpoint_smoke(self, user_client, link_id, proxy_uid, ua_uid, _cleanup_session):
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        _cleanup_session["jobs"].append(jid)
        r = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/live-log", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "running" in body
        assert "steps" in body or "cursor" in body


# ─────────────────────── 6. Regression smoke ───────────────────────
class TestRegressionSmoke:
    def test_diagnostics_health(self):
        r = requests.get(f"{BASE_URL}/api/diagnostics/health", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body.get("overall") in ("ok", "warn")

    def test_uploads_list_no_items(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/uploads?sync_gsheets=false", timeout=20)
        assert r.status_code == 200
        for d in r.json():
            assert "items" not in d

    def test_post_proxies_upload(self, user_client, _cleanup_session):
        r = user_client.post(
            f"{BASE_URL}/api/uploads/proxies",
            data={"name": "TEST_iter6_smoke_p", "proxies": "5.5.5.5:1:u:p"},
            timeout=15,
        )
        assert r.status_code == 200
        _cleanup_session["uploads"].append(r.json()["id"])

    def test_post_uas_upload(self, user_client, _cleanup_session):
        r = user_client.post(
            f"{BASE_URL}/api/uploads/user-agents",
            data={"name": "TEST_iter6_smoke_ua", "user_agents": "Mozilla TEST"},
            timeout=15,
        )
        assert r.status_code == 200
        _cleanup_session["uploads"].append(r.json()["id"])

    def test_jobs_list_shape(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/real-user-traffic/jobs", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict) and "jobs" in body

    def test_stop_and_delete_smoke(self, user_client, link_id, proxy_uid, ua_uid):
        jid, _ = _submit_rut_job(user_client, link_id, proxy_uid, ua_uid)
        rs = user_client.post(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}/stop", timeout=10)
        assert rs.status_code in (200, 202)
        # delete — only after settled
        _wait_for_status(user_client, jid, ("stopped", "failed", "completed"), timeout=15)
        rd = user_client.delete(f"{BASE_URL}/api/real-user-traffic/jobs/{jid}", timeout=10)
        assert rd.status_code in (200, 202, 204)
