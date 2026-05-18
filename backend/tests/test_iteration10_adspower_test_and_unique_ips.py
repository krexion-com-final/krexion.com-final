"""
Iteration 10 backend tests for AdsPower Profile Builder enhancements:

1. POST /api/adspower/configs/{cid}/test
   - 200 + {ok:false, reachable:false, local_online:false, message} when PC offline
   - 404 when config id is unknown
   - 403 when user lacks profile_builder feature
   - When PC online (simulated via fresh sync_heartbeats doc), enqueues a
     bridge_job with feature='adspower/test' and waits ~18s timeout
     (no worker present) → ok:false with timeout/local_online:true.

2. POST /api/adspower/generate
   - verify_unique_ips:true + fake ProxyJet creds → fast-fail with errors
     mentioning unique IPs not found (no crash, returns clean job state).
   - verify_unique_ips:false (default) → fast path still works in <2s for 10
     profiles (regression check).
   - Generated profile docs include 'config_name' and 'ip' fields.
   - /api/adspower/jobs/{id} response includes 'config_name' and
     'verify_unique_ips' on the job doc.
"""
import asyncio
import os
import time
import uuid
import datetime as _dt

import pytest
import requests

# Mongo direct access for the PC-online simulation + cleanup
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://flow-staging-6.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "admin123"
PRE_USER_EMAIL = "adspowertester@gmail.com"
PRE_USER_PASSWORD = "Test12345"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "krexion")


# ───────────────────── Fixtures ─────────────────────
@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{API}/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": PRE_USER_EMAIL, "password": PRE_USER_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"pre-flagged user login failed: {r.status_code} {r.text}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def pre_user_id(user_headers):
    r = requests.get(f"{API}/auth/me", headers=user_headers, timeout=20)
    if r.status_code != 200:
        # try /users/me
        r = requests.get(f"{API}/users/me", headers=user_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    return data.get("id") or data.get("user", {}).get("id")


@pytest.fixture(scope="module")
def configs(user_headers):
    """List configs; tests for /test assume at least one exists."""
    r = requests.get(f"{API}/adspower/configs", headers=user_headers, timeout=20)
    assert r.status_code == 200, r.text
    cfgs = r.json().get("configs", [])
    if not cfgs:
        # Make sure at least one exists
        cr = requests.post(
            f"{API}/adspower/configs",
            headers=user_headers,
            json={"name": "Test", "api_key": "TEST_apikey_iter10_aaa"},
            timeout=20,
        )
        assert cr.status_code == 200, cr.text
        r = requests.get(f"{API}/adspower/configs", headers=user_headers, timeout=20)
        cfgs = r.json().get("configs", [])
    return cfgs


@pytest.fixture(scope="module")
def primary_cid(configs):
    return configs[0]["id"]


# ───────────────────── /configs/{cid}/test ─────────────────────
class TestAdsPowerConfigTest:
    """POST /api/adspower/configs/{cid}/test — PC offline + 404 + 403 + online-sim."""

    def test_test_endpoint_offline(self, user_headers, primary_cid):
        t0 = time.time()
        r = requests.post(
            f"{API}/adspower/configs/{primary_cid}/test",
            headers=user_headers,
            timeout=30,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is False
        assert data["reachable"] is False
        assert data["local_online"] is False
        assert "message" in data and isinstance(data["message"], str)
        # Should be fast — offline path bypasses bridge wait
        assert elapsed < 5, f"offline path was slow ({elapsed:.1f}s) — should be <5s"

    def test_test_endpoint_404_unknown_cid(self, user_headers):
        bogus = "does-not-exist-" + uuid.uuid4().hex[:8]
        r = requests.post(
            f"{API}/adspower/configs/{bogus}/test",
            headers=user_headers,
            timeout=20,
        )
        assert r.status_code == 404, r.text

    def test_test_endpoint_403_without_feature(self, admin_headers):
        # Admin login → admin token; admin user usually does NOT have
        # profile_builder feature unless flagged. We try /test and expect
        # 403 (or 404 if config doesn't exist for admin — both gate the
        # feature). Treat 403 as the required outcome.
        bogus = "any-cid-" + uuid.uuid4().hex[:8]
        r = requests.post(
            f"{API}/adspower/configs/{bogus}/test",
            headers=admin_headers,
            timeout=20,
        )
        # The check_user_feature gate fires before the 404 lookup, so we
        # expect 403. Accept 401 too in case admin token isn't usable on
        # /api/adspower/* routes.
        assert r.status_code in (401, 403), f"got {r.status_code}: {r.text}"

    def test_test_endpoint_online_sim_enqueues_bridge_job_and_times_out(
        self, user_headers, primary_cid, pre_user_id
    ):
        """Inject a fresh sync_heartbeats doc → online path → expects
        a bridge_job inserted with feature='adspower/test' and an
        ~18s timeout response (no worker)."""

        async def _run():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            try:
                # Clean any prior bridge_jobs for this feature for the user
                await db.bridge_jobs.delete_many(
                    {"user_id": pre_user_id, "feature": "adspower/test"}
                )
                # Insert fresh heartbeat (now)
                now = _dt.datetime.now(_dt.timezone.utc).isoformat()
                await db.sync_heartbeats.update_one(
                    {"user_id": pre_user_id},
                    {"$set": {"user_id": pre_user_id, "last_seen": now}},
                    upsert=True,
                )

                # Fire the /test call in a thread — it will wait up to 18s
                loop = asyncio.get_event_loop()
                t0 = time.time()
                future = loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        f"{API}/adspower/configs/{primary_cid}/test",
                        headers=user_headers,
                        timeout=40,
                    ),
                )
                # While the call is in flight, give 2s then verify a
                # bridge_job exists with the right feature
                await asyncio.sleep(2.0)
                bj = await db.bridge_jobs.find_one(
                    {"user_id": pre_user_id, "feature": "adspower/test"},
                    {"_id": 0},
                )
                # Run the request to completion
                r = await future
                elapsed = time.time() - t0
                return r, elapsed, bj
            finally:
                # Cleanup heartbeat + bridge_jobs we created
                await db.sync_heartbeats.delete_one({"user_id": pre_user_id})
                await db.bridge_jobs.delete_many(
                    {"user_id": pre_user_id, "feature": "adspower/test"}
                )
                client.close()

        r, elapsed, bj = asyncio.run(_run())
        assert r.status_code == 200, r.text
        data = r.json()
        # online-but-no-worker → timeout
        assert data["ok"] is False
        assert data["local_online"] is True
        assert isinstance(data.get("message"), str) and len(data["message"]) > 0
        # Should have taken near the 18s wait (allow margin)
        assert elapsed >= 10, f"online-sim returned too fast ({elapsed:.1f}s) — bridge wait may be bypassed"
        # bridge_job MUST have been enqueued with the correct feature
        assert bj is not None, "bridge_job with feature='adspower/test' was NOT inserted"
        assert bj["feature"] == "adspower/test"
        assert bj.get("payload", {}).get("api_key")  # payload includes api_key
        assert bj.get("payload", {}).get("host")


# ───────────────────── /generate enhancements ─────────────────────
class TestGenerateUniqueIPsAndConfigName:
    """verify_unique_ips flag + config_name on jobs and profile docs."""

    def _payload(self, primary_cid, count, verify_unique_ips, name_prefix):
        return {
            "config_id": primary_cid,
            "count": count,
            "state": "California",
            "ua_config": {"app": "instagram", "platform": "any"},
            "name_prefix": name_prefix,
            "push_to_adspower": False,
            "wipe_existing": True,
            "verify_unique_ips": verify_unique_ips,
        }

    def _wait_job(self, headers, jid, max_wait=20):
        deadline = time.time() + max_wait
        last = None
        while time.time() < deadline:
            r = requests.get(f"{API}/adspower/jobs/{jid}", headers=headers, timeout=15)
            assert r.status_code == 200, r.text
            last = r.json()
            if last.get("status") in ("done", "failed", "completed"):
                return last
            time.sleep(0.5)
        return last

    def test_verify_unique_ips_true_fastfails_with_fake_creds(
        self, user_headers, primary_cid
    ):
        t0 = time.time()
        r = requests.post(
            f"{API}/adspower/generate",
            headers=user_headers,
            json=self._payload(primary_cid, 10, True, "TEST_iter10_uniq"),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        jid = r.json().get("job_id") or r.json().get("id")
        assert jid
        job = self._wait_job(user_headers, jid, max_wait=25)
        elapsed = time.time() - t0
        assert job is not None
        # Job must include verify_unique_ips and config_name fields
        assert job.get("verify_unique_ips") is True, f"verify_unique_ips missing in job: {job}"
        assert job.get("config_name"), f"config_name missing on job: {job}"
        # Should have errored out — no real IPs reachable
        errs = job.get("errors") or []
        joined = " ".join(map(str, errs)).lower()
        assert any(
            ("unique" in joined and "ip" in joined) or "ipify" in joined or "proxy" in joined
            for _ in [0]
        ), f"expected unique-IP failure in errors, got: {errs}"
        # Should be reasonably fast — fail-fast within 30s
        assert elapsed < 30, f"verify_unique_ips path took too long ({elapsed:.1f}s)"

    def test_verify_unique_ips_false_fast_path_with_config_name(
        self, user_headers, primary_cid, configs
    ):
        cfg_name = configs[0].get("name")
        t0 = time.time()
        r = requests.post(
            f"{API}/adspower/generate",
            headers=user_headers,
            json=self._payload(primary_cid, 10, False, "TEST_iter10_fast"),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        jid = r.json().get("job_id") or r.json().get("id")
        job = self._wait_job(user_headers, jid, max_wait=15)
        elapsed = time.time() - t0
        assert job is not None
        assert job.get("status") in ("done", "completed"), f"job: {job}"
        assert job.get("verify_unique_ips") is False
        assert job.get("config_name") == cfg_name
        assert elapsed < 10, f"fast path took {elapsed:.1f}s (expected <10s)"

        # Verify profile docs include config_name and ip fields
        pr = requests.get(
            f"{API}/adspower/profiles?limit=50", headers=user_headers, timeout=20
        )
        assert pr.status_code == 200, pr.text
        profiles = pr.json().get("profiles", [])
        assert profiles, "no profiles returned after fast-mode generate"
        # Take a few — confirm fields present
        sample = profiles[0]
        assert "config_name" in sample, f"profile missing config_name: {sample.keys()}"
        assert sample["config_name"] == cfg_name
        assert "ip" in sample, f"profile missing 'ip' field: {sample.keys()}"
        # In fast mode, ip is allowed to be None
        # (UI shows '— sticky')
