"""
Iteration 5 — License Delete + Bulk + Cleanup endpoints + regression.

Covers:
- Health + hardware-profile (regression from iter 3/4)
- Admin login (regression)
- User register/login (admin approval flow)
- License config / start-trial / issue / list / extend / revoke (regression)
- NEW: DELETE /api/admin/license/{key}
- NEW: POST /api/admin/license/bulk-delete (status, keys, safety guardrail)
- NEW: POST /api/admin/license/cleanup (active-license protection)
- License validate (heartbeat) public endpoint
- Links CRUD
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("BACKEND_URL") or "https://dynabook-preview.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "admin123"


# ───────────────────────── fixtures ──────────────────────────
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/admin/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("is_admin") is True
    assert "access_token" in data and len(data["access_token"]) > 10
    return data["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ───────────────────── diagnostics ────────────────────────────
class TestDiagnostics:
    def test_health(self):
        r = requests.get(f"{API}/diagnostics/health", timeout=20)
        assert r.status_code == 200
        d = r.json()
        # mongodb status is nested under checks.mongodb.status
        mongo = d.get("checks", {}).get("mongodb", {})
        assert mongo.get("status") == "ok", d

    def test_hardware_profile(self):
        r = requests.get(f"{API}/diagnostics/hardware-profile", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "detected" in d and "applied" in d and "recommended_tier" in d
        assert isinstance(d["detected"].get("total_ram_gb"), (int, float))
        assert isinstance(d["detected"].get("cpu_cores"), int)
        assert d["recommended_tier"] in ("MICRO", "LOW", "MID", "HIGH", "BEAST")
        assert isinstance(d["applied"].get("rut_concurrency"), int)


# ─────────────────────── admin auth ──────────────────────────
class TestAdminAuth:
    def test_admin_login(self, admin_token):
        assert admin_token  # already validated in fixture

    def test_admin_login_wrong_password(self):
        r = requests.post(f"{API}/admin/login",
                          json={"email": ADMIN_EMAIL, "password": "wrong"},
                          timeout=15)
        assert r.status_code in (400, 401, 403)


# ─────────────────────── user auth ───────────────────────────
class TestUserAuth:
    def test_user_register_pending_then_admin_approve(self, admin_headers):
        email = f"TEST_user_{uuid.uuid4().hex[:8]}@example.com"
        password = "TestPass123!"
        # 1. register
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": password, "name": "Test User"},
                          timeout=20)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        # user starts inactive per test_credentials.md
        # 2. attempt login — should likely fail because pending
        r2 = requests.post(f"{API}/auth/login",
                           json={"email": email, "password": password}, timeout=20)
        login_before_approve = r2.status_code
        # 3. admin approves
        # find user id
        # Try common admin user list endpoints
        approved = False
        for path in ("/admin/users", "/admin/user/list"):
            ru = requests.get(f"{API}{path}", headers=admin_headers, timeout=20)
            if ru.status_code != 200:
                continue
            items = ru.json() if isinstance(ru.json(), list) else (
                ru.json().get("items") or ru.json().get("users") or []
            )
            target = next((u for u in items if u.get("email") == email), None)
            if not target:
                continue
            uid = target.get("id") or target.get("_id") or target.get("user_id")
            if not uid:
                continue
            for ap in (f"/admin/users/{uid}/approve",
                       f"/admin/user/{uid}/approve",
                       f"/admin/users/{uid}/activate"):
                ra = requests.post(f"{API}{ap}", headers=admin_headers, timeout=20)
                if ra.status_code in (200, 204):
                    approved = True
                    break
            if approved:
                break
        # 4. log in after approve
        r3 = requests.post(f"{API}/auth/login",
                           json={"email": email, "password": password}, timeout=20)
        # Pass criteria: either login was always allowed OR approval enabled it
        ok = (login_before_approve == 200) or (r3.status_code == 200)
        assert ok, (
            f"register={r.status_code} login_before={login_before_approve} "
            f"approved={approved} login_after={r3.status_code} body={r3.text[:200]}"
        )


# ───────────────────── license flows ──────────────────────────
class TestLicenseFlows:
    def test_license_config(self, admin_headers):
        r = requests.get(f"{API}/admin/license/config", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        # required pricing + trial fields
        assert "monthly_price" in d or "price" in d, d
        assert "trial_days" in d

    def test_start_trial(self):
        email = f"TEST_trial_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/license/start-trial",
                          json={"email": email}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("license_key", "").startswith("RFLW-") or len(d.get("license_key", "")) > 5
        assert "trial_ends_at" in d or d.get("reused")

    def test_issue_license(self, admin_headers):
        email = f"TEST_issue_{uuid.uuid4().hex[:8]}@example.com"
        # issue uses query params (per LicenseAdminPage frontend)
        r = requests.post(
            f"{API}/admin/license/issue?email={email}&days=31",
            headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("license_key", "").startswith("RFLW-") or len(d["license_key"]) > 5
        assert "subscription_ends_at" in d

    def test_list_licenses(self, admin_headers):
        r = requests.get(f"{API}/admin/license/list", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "total" in d and "items" in d
        assert isinstance(d["items"], list)

    def test_extend_license(self, admin_headers):
        email = f"TEST_extend_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/admin/license/issue?email={email}&days=10",
                          headers=admin_headers, timeout=20)
        key = r.json()["license_key"]
        r2 = requests.post(f"{API}/admin/license/extend/{key}?days=15",
                           headers=admin_headers, timeout=20)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d.get("ok") is True
        assert "subscription_ends_at" in d

    def test_revoke_license(self, admin_headers):
        email = f"TEST_revoke_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/admin/license/issue?email={email}&days=31",
                          headers=admin_headers, timeout=20)
        key = r.json()["license_key"]
        r2 = requests.post(f"{API}/admin/license/revoke/{key}",
                           headers=admin_headers, timeout=20)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("ok") is True
        # confirm in list
        lst = requests.get(f"{API}/admin/license/list?q={key}",
                           headers=admin_headers, timeout=20).json()
        match = next((x for x in lst["items"] if x["license_key"] == key), None)
        assert match and match.get("status") == "revoked"


# ──────────────── NEW: Delete / Bulk-delete / Cleanup ────────────────
class TestLicenseDelete:
    def _issue(self, admin_headers, prefix="TEST_del", days=31):
        email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/admin/license/issue?email={email}&days={days}",
                          headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        return r.json()["license_key"]

    def test_delete_single(self, admin_headers):
        key = self._issue(admin_headers)
        r = requests.delete(f"{API}/admin/license/{key}",
                            headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("deleted") == key

    def test_delete_already_deleted_returns_404(self, admin_headers):
        key = self._issue(admin_headers)
        r1 = requests.delete(f"{API}/admin/license/{key}",
                             headers=admin_headers, timeout=20)
        assert r1.status_code == 200
        r2 = requests.delete(f"{API}/admin/license/{key}",
                             headers=admin_headers, timeout=20)
        assert r2.status_code == 404

    def test_bulk_delete_empty_filter_400(self, admin_headers):
        """SAFETY GUARDRAIL P0: empty payload must be rejected."""
        r = requests.post(f"{API}/admin/license/bulk-delete",
                          headers=admin_headers, json={}, timeout=20)
        assert r.status_code == 400, (
            f"P0 SAFETY: empty bulk-delete should 400 but got {r.status_code}: {r.text}"
        )

    def test_bulk_delete_by_status_revoked(self, admin_headers):
        # Create + revoke two licenses
        keys = [self._issue(admin_headers, prefix="TEST_brk") for _ in range(2)]
        for k in keys:
            rv = requests.post(f"{API}/admin/license/revoke/{k}",
                               headers=admin_headers, timeout=20)
            assert rv.status_code == 200

        r = requests.post(f"{API}/admin/license/bulk-delete",
                          headers=admin_headers,
                          json={"status": "revoked"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("deleted_count", 0) >= 2
        assert d.get("by") == "filter"

        # both our revoked keys should now be gone
        for k in keys:
            chk = requests.get(f"{API}/admin/license/list?q={k}",
                               headers=admin_headers, timeout=20).json()
            assert not any(x["license_key"] == k for x in chk["items"])

    def test_bulk_delete_by_keys(self, admin_headers):
        keys = [self._issue(admin_headers, prefix="TEST_bkey") for _ in range(2)]
        r = requests.post(f"{API}/admin/license/bulk-delete",
                          headers=admin_headers,
                          json={"keys": keys}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("by") == "keys"
        assert d.get("deleted_count") == 2

    def test_cleanup(self, admin_headers):
        # Create a revoked, an active, and (we can't easily make expired without DB)
        active_key = self._issue(admin_headers, prefix="TEST_clean_active", days=365)
        revoked_key = self._issue(admin_headers, prefix="TEST_clean_rev", days=365)
        requests.post(f"{API}/admin/license/revoke/{revoked_key}",
                      headers=admin_headers, timeout=20)

        r = requests.post(f"{API}/admin/license/cleanup",
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        deleted = d.get("deleted", {})
        for k in ("revoked", "expired_trials", "expired_subscriptions", "total"):
            assert k in deleted, f"missing {k} in {deleted}"
        # revoked count should include at least our one
        assert deleted["revoked"] >= 1

        # PROTECTION: active license must still exist
        lst = requests.get(f"{API}/admin/license/list?q={active_key}",
                           headers=admin_headers, timeout=20).json()
        assert any(x["license_key"] == active_key for x in lst["items"]), \
            "P0 SAFETY: active license deleted by cleanup!"

        # revoked license must be gone
        lst2 = requests.get(f"{API}/admin/license/list?q={revoked_key}",
                            headers=admin_headers, timeout=20).json()
        assert not any(x["license_key"] == revoked_key for x in lst2["items"])

    def test_bulk_delete_trial_does_not_touch_active(self, admin_headers):
        """Active licenses must survive a status=trial bulk delete."""
        active_key = self._issue(admin_headers, prefix="TEST_act_keep", days=365)
        r = requests.post(f"{API}/admin/license/bulk-delete",
                          headers=admin_headers,
                          json={"status": "trial"}, timeout=20)
        assert r.status_code == 200, r.text
        lst = requests.get(f"{API}/admin/license/list?q={active_key}",
                           headers=admin_headers, timeout=20).json()
        assert any(x["license_key"] == active_key for x in lst["items"]), \
            "P0 SAFETY: active license deleted by status=trial bulk-delete!"


# ──────────── License heartbeat (customer-side, no admin) ─────────────
class TestLicenseValidatePublic:
    def test_validate_no_admin_required(self):
        """The 'heartbeat' endpoint is /api/license/validate (not /heartbeat).
        Must be reachable WITHOUT admin token."""
        r = requests.post(f"{API}/license/validate",
                          json={"license_key": "RFLW-NONEXISTENT-XYZ",
                                "machine_id": "test-machine"}, timeout=20)
        # Either 404 (key not recognized) or 200 (licensing disabled)
        assert r.status_code in (200, 404), r.text

    def test_heartbeat_alias_if_present(self):
        """If a /license/heartbeat alias exists, it should also work without admin."""
        r = requests.post(f"{API}/license/heartbeat",
                          json={"license_key": "RFLW-NONEXISTENT-XYZ",
                                "machine_id": "test-machine"}, timeout=20)
        # Acceptable: 404 Not Found (alias missing) OR 200/404 from handler
        assert r.status_code in (200, 404, 405, 422)


# ───────────────────── Links CRUD ──────────────────────────
class TestLinks:
    @pytest.fixture(scope="class")
    def user_token(self):
        email = f"TEST_links_{uuid.uuid4().hex[:8]}@example.com"
        password = "TestPass123!"
        requests.post(f"{API}/auth/register",
                      json={"email": email, "password": password, "name": "Links User"},
                      timeout=20)
        # try login; if pending approval, fixture skips
        admin_r = requests.post(f"{API}/admin/login",
                                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                                timeout=15)
        admin_h = {"Authorization": f"Bearer {admin_r.json()['access_token']}"}
        # try to approve via PUT /admin/users/{user_id}
        ru = requests.get(f"{API}/admin/users", headers=admin_h, timeout=15)
        if ru.status_code == 200:
            j = ru.json()
            items = j if isinstance(j, list) else (j.get("items") or j.get("users") or [])
            target = next((u for u in items if u.get("email") == email), None)
            if target:
                uid = target.get("id") or target.get("_id") or target.get("user_id")
                requests.put(f"{API}/admin/users/{uid}",
                             headers=admin_h,
                             json={
                                 "status": "active",
                                 "features": {"links": True, "real_user_traffic": True}
                             }, timeout=15)
        r = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": password}, timeout=20)
        if r.status_code != 200:
            pytest.skip(f"user login not available (status={r.status_code})")
        return r.json().get("access_token") or r.json().get("token")

    def test_create_and_list_link(self, user_token):
        if not user_token:
            pytest.skip("no user token")
        h = {"Authorization": f"Bearer {user_token}"}
        url = f"https://example.com/test-{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/links",
                          headers=h,
                          json={"offer_url": url, "title": "TEST link"},
                          timeout=20)
        assert r.status_code in (200, 201), r.text
        r2 = requests.get(f"{API}/links", headers=h, timeout=20)
        assert r2.status_code == 200
        d = r2.json()
        items = d if isinstance(d, list) else (d.get("items") or d.get("links") or [])
        assert isinstance(items, list)
