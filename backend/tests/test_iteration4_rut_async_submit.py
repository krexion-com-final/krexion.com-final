"""
Iteration 4 — RUT async-submit refactor verification.

Backend-only tests. Verifies:
  * GET /api/real-user-traffic/jobs (regression)
  * POST /api/real-user-traffic/jobs FAST submit (<3s, returns job_id)
  * Immediate visibility of new job_id in list (≤2s)
  * BG failure path (bad upload_proxy_id → status flips to 'failed' within ~3s)
  * Foreground 400 validations (missing proxies/UAs/excel/gsheet/total_clicks/concurrency)
  * 404 for wrong link_id
  * Concurrency stress (5 parallel POSTs all <5s wall-clock, distinct ids)
  * Stop / Delete endpoints regression (no 500)
  * GET /api/real-user-traffic/engine-status

Uses external REACT_APP_BACKEND_URL.
Test user is created and approved fresh per run (or reused if env credentials provided).
"""

from __future__ import annotations

import os
import time
import uuid
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pytest
import requests


# ---------------- backend URL resolver ----------------
def _load_backend_url() -> str:
    env_url = os.environ.get("REACT_APP_BACKEND_URL")
    if env_url:
        return env_url.rstrip("/")
    fe = Path("/app/frontend/.env")
    if fe.exists():
        for line in fe.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@krexion.local")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")

RAND = uuid.uuid4().hex[:8]
USER_EMAIL = f"test_iter4_{RAND}@krexion.local"
USER_PASSWORD = "Test12345!"

STATE: Dict[str, Any] = {}


# ---------------- helpers ----------------
def _ahdr() -> Dict[str, str]:
    return {"Authorization": f"Bearer {STATE['admin_token']}"}


def _uhdr() -> Dict[str, str]:
    return {"Authorization": f"Bearer {STATE['user_token']}"}


def _post_paste_job(
    s: requests.Session,
    *,
    overrides: Dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> requests.Response:
    """Build a minimal valid paste-mode RUT job submission and POST it."""
    form = {
        "link_id": STATE["link_id"],
        "proxies": "1.2.3.4:8080",
        "user_agents": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "total_clicks": "3",
        "concurrency": "1",
        "duration_minutes": "0",
        "skip_duplicate_ip": "false",
        "skip_vpn": "false",
        "form_fill_enabled": "false",
    }
    if overrides:
        for k, v in overrides.items():
            if v is None:
                form.pop(k, None)
            else:
                form[k] = v
    return s.post(
        f"{API}/real-user-traffic/jobs",
        data=form,
        headers=_uhdr(),
        timeout=timeout,
    )


# =========================================================================
# 1. Setup — admin login, register/approve test user, create link
# =========================================================================
class TestSetup:
    def test_admin_login(self):
        r = requests.post(
            f"{API}/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        STATE["admin_token"] = r.json()["access_token"]

    def test_register_user(self):
        r = requests.post(
            f"{API}/auth/register",
            json={"email": USER_EMAIL, "password": USER_PASSWORD, "name": "Iter4 Tester"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        STATE["user_id"] = r.json()["user"]["id"]

    def test_approve_user_with_features(self):
        r = requests.put(
            f"{API}/admin/users/{STATE['user_id']}",
            json={
                "status": "active",
                "features": {
                    "links": True,
                    "clicks": True,
                    "real_traffic": True,
                    "real_user_traffic": True,
                    "import_traffic": True,
                    "settings": True,
                    "form_filler": True,
                    "max_links": 100,
                    "max_clicks": 100000,
                },
            },
            headers=_ahdr(),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json()["user"]["features"]["real_user_traffic"] is True

    def test_user_login(self):
        r = requests.post(
            f"{API}/auth/login",
            json={"email": USER_EMAIL, "password": USER_PASSWORD},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        STATE["user_token"] = r.json()["access_token"]

    def test_create_link(self):
        r = requests.post(
            f"{API}/links",
            json={
                "offer_url": "https://example.com/iter4-target",
                "name": f"Iter4 Link {RAND}",
                "status": "active",
            },
            headers={**_uhdr(), "Content-Type": "application/json"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        STATE["link_id"] = r.json()["id"]


# =========================================================================
# 2. Regression: GET /jobs returns {jobs: [...]}
# =========================================================================
class TestJobsListRegression:
    def test_get_jobs_returns_jobs_key(self):
        r = requests.get(f"{API}/real-user-traffic/jobs", headers=_uhdr(), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # Spec says response is {jobs: [...]}
        assert isinstance(body, dict), f"expected dict, got {type(body)}: {body!r:.200}"
        assert "jobs" in body, f"missing 'jobs' key: {body}"
        assert isinstance(body["jobs"], list)


# =========================================================================
# 3. FAST submit returns < 3s with preparing=true and job_id; visible in list
# =========================================================================
class TestFastSubmit:
    def test_paste_mode_returns_within_3s(self):
        sess = requests.Session()
        t0 = time.time()
        r = _post_paste_job(sess, timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:400]}"
        assert elapsed < 3.0, f"foreground submit took {elapsed:.2f}s (>=3s) body={r.text[:200]}"
        body = r.json()
        assert "job_id" in body and isinstance(body["job_id"], str)
        STATE["fast_job_id"] = body["job_id"]
        STATE["fast_submit_elapsed"] = elapsed

    def test_job_visible_in_list_within_2s(self):
        deadline = time.time() + 2.0
        seen = False
        last_ids: List[str] = []
        while time.time() < deadline:
            r = requests.get(f"{API}/real-user-traffic/jobs", headers=_uhdr(), timeout=10)
            if r.status_code == 200:
                last_ids = [j.get("job_id") for j in r.json().get("jobs", [])]
                if STATE["fast_job_id"] in last_ids:
                    seen = True
                    break
            time.sleep(0.2)
        assert seen, f"job_id {STATE['fast_job_id']} not in list within 2s. ids={last_ids[:10]}"

    def test_job_detail_status_queued_or_running(self):
        r = requests.get(
            f"{API}/real-user-traffic/jobs/{STATE['fast_job_id']}",
            headers=_uhdr(),
            timeout=10,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        # preparing=true initially, may have already moved to running/failed
        assert j.get("status") in (
            "queued", "preparing", "running", "failed", "completed", "stopped", "pending"
        ), j


# =========================================================================
# 4. BG failure path — bad upload_proxy_id flips status to failed
# =========================================================================
class TestBgFailurePath:
    def test_bad_upload_proxy_id_returns_200_fast_then_fails(self):
        sess = requests.Session()
        t0 = time.time()
        r = _post_paste_job(
            sess,
            overrides={
                "upload_proxy_id": "non-existent-fake-id",
                # paste empty so we don't fall through to paste-mode
                "proxies": "",
            },
            timeout=10,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, f"expected 200 fast, got {r.status_code}: {r.text[:300]}"
        assert elapsed < 3.0, f"foreground took {elapsed:.2f}s"
        job_id = r.json()["job_id"]
        STATE["bg_fail_job_id"] = job_id

        # Poll detail up to 8s waiting for status=failed
        deadline = time.time() + 8.0
        final_status = None
        final_err = None
        while time.time() < deadline:
            r2 = requests.get(
                f"{API}/real-user-traffic/jobs/{job_id}", headers=_uhdr(), timeout=10
            )
            if r2.status_code == 200:
                j = r2.json()
                final_status = j.get("status")
                final_err = j.get("error_message") or j.get("error")
                if final_status == "failed":
                    break
            time.sleep(0.4)
        assert final_status == "failed", (
            f"job did not flip to 'failed' (got {final_status}); err={final_err}"
        )
        assert final_err and isinstance(final_err, str) and final_err.strip(), (
            f"error_message empty: {final_err!r}"
        )
        low = final_err.lower()
        assert ("proxy" in low) or ("upload" in low) or ("not found" in low), (
            f"error_message does not mention proxy/upload/not found: {final_err}"
        )


# =========================================================================
# 5. Foreground 400 validations (must be fast, <2s)
# =========================================================================
class TestValidations400:
    def _expect_400(self, overrides: Dict[str, Any], must_contain: List[str]) -> str:
        sess = requests.Session()
        t0 = time.time()
        r = _post_paste_job(sess, overrides=overrides, timeout=10)
        elapsed = time.time() - t0
        assert elapsed < 2.0, f"validation took {elapsed:.2f}s (>=2s)"
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"
        detail = (r.json().get("detail") or "").lower()
        for tok in must_contain:
            assert tok.lower() in detail, f"detail missing '{tok}': {detail}"
        return detail

    def test_missing_proxies(self):
        self._expect_400({"proxies": ""}, ["proxy"])

    def test_missing_user_agents(self):
        self._expect_400({"user_agents": ""}, ["user agent"])

    def test_form_fill_excel_no_file(self):
        self._expect_400(
            {"form_fill_enabled": "true", "data_source": "excel"},
            ["excel"],
        )

    def test_form_fill_gsheet_empty_url(self):
        self._expect_400(
            {"form_fill_enabled": "true", "data_source": "gsheet", "gsheet_url": ""},
            ["gsheet_url"],
        )

    def test_total_clicks_zero(self):
        self._expect_400({"total_clicks": "0"}, ["total_clicks"])

    def test_concurrency_99(self):
        self._expect_400({"concurrency": "99"}, ["concurrency"])

    def test_wrong_link_id_returns_404(self):
        sess = requests.Session()
        r = _post_paste_job(sess, overrides={"link_id": "non-existent-link"}, timeout=10)
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text[:300]}"


# =========================================================================
# 6. Concurrency stress — 5 parallel submits, all <5s total, distinct ids
# =========================================================================
class TestConcurrencyStress:
    def test_5_parallel_submits(self):
        results: List[Tuple[int, float, Any]] = []
        errors: List[str] = []

        def submit(idx: int):
            sess = requests.Session()
            t0 = time.time()
            try:
                r = _post_paste_job(sess, timeout=15)
                el = time.time() - t0
                results.append((idx, el, r))
            except Exception as e:
                errors.append(f"#{idx}: {e}")

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(5)]
        wall_t0 = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        wall = time.time() - wall_t0

        assert not errors, f"thread errors: {errors}"
        assert len(results) == 5, f"only got {len(results)} results"
        for idx, el, r in results:
            assert r.status_code == 200, f"#{idx} status={r.status_code} body={r.text[:200]}"
        assert wall <= 5.0, f"wall-clock {wall:.2f}s exceeded 5s"
        ids = [r.json()["job_id"] for _, _, r in results]
        assert len(set(ids)) == 5, f"duplicate job_ids: {ids}"
        STATE["stress_ids"] = ids

    def test_all_5_visible_in_list_within_2s(self):
        deadline = time.time() + 2.0
        all_seen = False
        last_ids: List[str] = []
        while time.time() < deadline:
            r = requests.get(f"{API}/real-user-traffic/jobs", headers=_uhdr(), timeout=10)
            if r.status_code == 200:
                last_ids = [j.get("job_id") for j in r.json().get("jobs", [])]
                if all(jid in last_ids for jid in STATE["stress_ids"]):
                    all_seen = True
                    break
            time.sleep(0.2)
        missing = [jid for jid in STATE["stress_ids"] if jid not in last_ids]
        assert all_seen, f"missing from list within 2s: {missing}"


# =========================================================================
# 7. Stop endpoint regression — no 500 on a queued/preparing job
# =========================================================================
class TestStopRegression:
    def test_stop_does_not_500(self):
        # use the fast_job_id created earlier
        jid = STATE.get("fast_job_id")
        assert jid, "fast_job_id missing"
        r = requests.post(
            f"{API}/real-user-traffic/jobs/{jid}/stop", headers=_uhdr(), timeout=15
        )
        assert r.status_code != 500, f"stop returned 500: {r.text[:300]}"
        assert r.status_code in (200, 404, 409), f"unexpected status {r.status_code}: {r.text[:200]}"


# =========================================================================
# 8. DELETE regression — should work in any state
# =========================================================================
class TestDeleteRegression:
    def test_delete_fast_job(self):
        jid = STATE.get("fast_job_id")
        r = requests.delete(
            f"{API}/real-user-traffic/jobs/{jid}", headers=_uhdr(), timeout=15
        )
        assert r.status_code == 200, f"delete failed: {r.status_code} {r.text[:200]}"

    def test_delete_bg_failed_job(self):
        jid = STATE.get("bg_fail_job_id")
        r = requests.delete(
            f"{API}/real-user-traffic/jobs/{jid}", headers=_uhdr(), timeout=15
        )
        assert r.status_code == 200, f"delete failed: {r.status_code} {r.text[:200]}"

    def test_delete_stress_jobs(self):
        for jid in STATE.get("stress_ids", []):
            r = requests.delete(
                f"{API}/real-user-traffic/jobs/{jid}", headers=_uhdr(), timeout=15
            )
            # Some may still be running — backend should still allow delete
            assert r.status_code == 200, f"delete {jid} failed: {r.status_code} {r.text[:200]}"


# =========================================================================
# 9. Engine status
# =========================================================================
class TestEngineStatus:
    def test_engine_status_200(self):
        r = requests.get(
            f"{API}/real-user-traffic/engine-status", headers=_uhdr(), timeout=15
        )
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("status", "message", "expected_revision"):
            assert k in body, f"engine-status missing {k}: {body}"


# =========================================================================
# 10. Cleanup
# =========================================================================
class TestCleanup:
    def test_delete_link(self):
        if STATE.get("link_id"):
            requests.delete(
                f"{API}/links/{STATE['link_id']}", headers=_uhdr(), timeout=15
            )

    def test_delete_user(self):
        if STATE.get("user_id"):
            r = requests.delete(
                f"{API}/admin/users/{STATE['user_id']}", headers=_ahdr(), timeout=15
            )
            assert r.status_code in (200, 204, 404), r.text
