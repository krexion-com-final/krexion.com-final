"""
Performance optimization regression tests (iteration_1)
Tests for:
- async TTL cache + single-flight for load_rows_from_google_sheet
- GZip middleware
- per-user-DB lazy index bootstrap on /api/uploads
- new admin/debug endpoints: /api/gsheet/cache-stats, /api/gsheet/cache-invalidate
"""
import os
import time
import concurrent.futures

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://flow-engine-15.preview.emergentagent.com").rstrip("/")
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test12345"


# ─────────────────────────── fixtures ───────────────────────────
@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(api_client):
    r = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ─────────────────────────── health / login ───────────────────────────
class TestBasics:
    def test_health_reachable(self, api_client):
        # /health is exposed at root; /api/health may also exist. Try both.
        r = api_client.get(f"{BASE_URL}/health", timeout=10)
        if r.status_code == 404:
            r = api_client.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200, f"health check failed: {r.status_code} {r.text[:200]}"

    def test_auth_login_returns_token(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 20


# ─────────────────────────── uploads + gzip + shape ───────────────────────────
class TestUploadsEndpoint:
    def test_uploads_returns_200(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/uploads", headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"uploads failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data, list)
        # no _id leak if any docs
        for doc in data:
            assert "_id" not in doc, f"Mongo _id leaked: {doc}"

    def test_uploads_gzip_encoded(self, auth_token):
        # Explicitly request gzip; requests.raw with stream=True shows raw content-encoding
        h = {
            "Authorization": f"Bearer {auth_token}",
            "Accept-Encoding": "gzip",
        }
        r = requests.get(f"{BASE_URL}/api/uploads", headers=h, timeout=15)
        assert r.status_code == 200
        # Content-Encoding gzip only if response >= 512 bytes (middleware minimum_size=512)
        body_len = len(r.content)
        ce = r.headers.get("Content-Encoding", "").lower()
        if body_len >= 512:
            assert "gzip" in ce, (
                f"Expected gzip encoding for {body_len}-byte response, got Content-Encoding={ce!r}"
            )
        else:
            # Small body — middleware may skip gzip. Just log.
            print(f"[info] uploads response is {body_len} bytes < 512, gzip skipped (ce={ce!r})")

    def test_uploads_unauth_rejected(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/uploads", timeout=10)
        assert r.status_code in (401, 403)


# ─────────────────────────── cache-stats ───────────────────────────
class TestCacheStats:
    REQUIRED_KEYS = {
        "ttl_seconds",
        "entries",
        "fresh_entries",
        "locks",
        "hits",
        "misses",
        "single_flight_waits",
        "invalidations",
        "hit_ratio",
    }

    def test_cache_stats_shape(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/gsheet/cache-stats", headers=auth_headers, timeout=10)
        assert r.status_code == 200, f"cache-stats failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        missing = self.REQUIRED_KEYS - set(data.keys())
        assert not missing, f"cache-stats missing keys: {missing}; got {data}"
        assert isinstance(data["ttl_seconds"], (int, float))
        assert isinstance(data["entries"], int)
        assert isinstance(data["hit_ratio"], (int, float))

    def test_cache_stats_unauth_rejected(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/gsheet/cache-stats", timeout=10)
        assert r.status_code in (401, 403)


# ─────────────────────────── cache-invalidate ───────────────────────────
class TestCacheInvalidate:
    def test_invalidate_all(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/gsheet/cache-invalidate", headers=auth_headers, timeout=10
        )
        assert r.status_code == 200, f"invalidate-all failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data.get("ok") is True
        assert "removed" in data
        assert isinstance(data["removed"], int)

    def test_invalidate_specific_url(self, auth_headers):
        fake_url = "https://docs.google.com/spreadsheets/d/FAKE/edit"
        r = requests.post(
            f"{BASE_URL}/api/gsheet/cache-invalidate",
            headers=auth_headers,
            params={"url": fake_url},
            timeout=10,
        )
        assert r.status_code == 200, f"invalidate(url) failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data.get("ok") is True
        assert "removed" in data


# ─────────────────────────── concurrent burst ───────────────────────────
class TestConcurrentBurst:
    def test_ten_parallel_uploads_ok(self, auth_token):
        headers = {"Authorization": f"Bearer {auth_token}"}

        def _one():
            t0 = time.time()
            try:
                r = requests.get(f"{BASE_URL}/api/uploads", headers=headers, timeout=15)
                return (r.status_code, time.time() - t0, None)
            except Exception as e:
                return (0, time.time() - t0, str(e))

        t_start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(lambda _: _one(), range(10)))
        total = time.time() - t_start

        codes = [s for s, _, _ in results]
        errs = [e for _, _, e in results if e]
        assert all(c == 200 for c in codes), f"Some requests failed: {codes}, errs={errs}"
        # loose bound — preview may be slow but nothing should be >10s
        assert total < 15.0, f"10 parallel uploads took {total:.2f}s (expected <15s)"
        print(f"[info] 10 parallel /api/uploads completed in {total:.2f}s")

    def test_cache_stats_after_burst(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/gsheet/cache-stats", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("entries", -1) >= 0


# ─────────────────────────── gsheet tabs graceful on bogus url ─────
class TestGsheetTabsBogus:
    def test_bogus_url_returns_4xx_or_5xx_gracefully(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/gsheet/tabs",
            params={"url": "https://bogus.invalid/not-a-sheet"},
            headers=auth_headers,
            timeout=15,
        )
        # Must not hang / crash. Acceptable:
        #   - 4xx/5xx with JSON error body, or
        #   - 200 with empty tabs list (graceful fallback)
        assert 200 <= r.status_code < 600, f"unexpected status: {r.status_code}"
        try:
            body = r.json()
        except Exception as e:
            pytest.fail(f"bogus gsheet/tabs response not JSON: {e}, body={r.text[:200]}")
        if r.status_code == 200:
            # Must be the documented shape with empty tabs (not crash)
            assert isinstance(body, dict)
            assert body.get("tabs") == [] or body.get("tabs") is None, (
                f"bogus URL produced non-empty tabs: {body}"
            )


# ─────────────────────────── regression: existing endpoints ─────────
class TestRegression:
    def test_links_endpoint(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/links", headers=auth_headers, timeout=15)
        # 200 (feature on) or 403 (feature off) both acceptable per spec
        assert r.status_code in (200, 403), f"/api/links unexpected: {r.status_code} {r.text[:200]}"

    def test_cpi_jobs_endpoint(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/cpi/jobs", headers=auth_headers, timeout=15)
        assert r.status_code in (200, 403), (
            f"/api/cpi/jobs unexpected: {r.status_code} {r.text[:200]}"
        )

    def test_form_filler_jobs_endpoint(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/form-filler/jobs", headers=auth_headers, timeout=15)
        assert r.status_code in (200, 403), (
            f"/api/form-filler/jobs unexpected: {r.status_code} {r.text[:200]}"
        )
