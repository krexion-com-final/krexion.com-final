"""
Iteration 3 backend smoke tests for RealFlow.
Covers: admin auth, user register/login, admin user mgmt (approve + features),
protected endpoints (links, uploads, settings), CPI smoke (dashboard stats + smartlink).

Runs against EXTERNAL REACT_APP_BACKEND_URL so we exercise ingress + /api prefix.
"""

import os
import random
import string
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback - read from frontend .env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

ADMIN_EMAIL = "admin@realflow.local"
ADMIN_PASSWORD = "admin123"

TIMEOUT = 30


def _rand(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


TEST_USER_EMAIL = f"tester+{_rand()}@realflow.local"
TEST_USER_PASSWORD = "Test12345!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(
        f"{BASE_URL}/api/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def user_context(session):
    """Registers a fresh user and returns {email, password, token, user_id}."""
    r = session.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "name": "Tester Iter3",
        },
        timeout=TIMEOUT,
    )
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token")
    assert token, f"no access_token in register response: {data}"
    return {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "token": token,
        "user": data.get("user") or {},
    }


# -------------- Sanity --------------
class TestSanity:
    def test_auth_me_without_token_is_401(self, session):
        r = session.get(f"{BASE_URL}/api/auth/me", timeout=TIMEOUT)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"


# -------------- Admin Auth --------------
class TestAdminAuth:
    def test_admin_login_success(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 10

    def test_admin_login_wrong_password(self, session):
        r = session.post(
            f"{BASE_URL}/api/admin/login",
            json={"email": ADMIN_EMAIL, "password": "wrong-password-xyz"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"


# -------------- User Register/Login --------------
class TestUserAuth:
    def test_register_creates_user(self, user_context):
        assert user_context["token"]

    def test_register_duplicate_email(self, session, user_context):
        r = session.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": user_context["email"],
                "password": TEST_USER_PASSWORD,
                "name": "Dup",
            },
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 409), f"expected 400/409, got {r.status_code}: {r.text[:200]}"

    def test_login_success(self, session, user_context):
        r = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": user_context["email"], "password": user_context["password"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "access_token" in data

    def test_login_wrong_password(self, session, user_context):
        r = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": user_context["email"], "password": "wrong!!!"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"


# -------------- Admin User Management --------------
class TestAdminUserMgmt:
    def test_admin_list_users_contains_new_user(self, session, admin_token, user_context):
        r = session.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"list users failed: {r.status_code} {r.text[:200]}"
        users = r.json()
        assert isinstance(users, list)
        emails = [u.get("email") for u in users]
        assert user_context["email"] in emails, f"user not in admin list: {emails[:5]}..."
        # stash user_id on module-level dict for next tests
        for u in users:
            if u.get("email") == user_context["email"]:
                user_context["user_id"] = u.get("id") or u.get("_id")
                user_context["status_before"] = u.get("status")
                break
        assert user_context.get("user_id"), "could not find user id"

    def test_admin_approve_user(self, session, admin_token, user_context):
        uid = user_context["user_id"]
        # Endpoint is PUT /api/admin/users/{id} with body {"status": "active"}
        r = session.put(
            f"{BASE_URL}/api/admin/users/{uid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "active"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (200, 204), f"approve failed: {r.status_code} {r.text[:200]}"
        # verify via list
        r2 = session.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=TIMEOUT,
        )
        users = r2.json()
        for u in users:
            if u.get("email") == user_context["email"]:
                assert u.get("status") == "active", f"status after approve: {u.get('status')}"
                break

    def test_admin_assign_features(self, session, admin_token, user_context):
        uid = user_context["user_id"]
        # Features are assigned via the same PUT /api/admin/users/{id} with a features dict
        features = {
            "links": True,
            "clicks": True,
            "conversions": True,
            "real_traffic": True,
            "real_user_traffic": True,
            "cpi": True,
            "import_traffic": True,
            "settings": True,
            "max_links": 100,
            "max_clicks": 10000,
        }
        r = session.put(
            f"{BASE_URL}/api/admin/users/{uid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "active", "features": features},
            timeout=TIMEOUT,
        )
        assert r.status_code in (200, 204), f"assign features failed: {r.status_code} {r.text[:200]}"


# -------------- Protected endpoints (after approval+features) --------------
class TestProtectedEndpoints:
    def _user_token(self, session, user_context):
        # re-login after approval (some apps bake status into JWT)
        r = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": user_context["email"], "password": user_context["password"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        return r.json()["access_token"]

    def test_links_endpoint_returns_list(self, session, user_context):
        token = self._user_token(session, user_context)
        r = session.get(
            f"{BASE_URL}/api/links",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"/api/links failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        # allow list or dict with items
        assert isinstance(data, (list, dict))

    def test_uploads_endpoint_no_500(self, session, user_context):
        token = self._user_token(session, user_context)
        r = session.get(
            f"{BASE_URL}/api/uploads",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"/api/uploads failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_settings_endpoint_200(self, session, user_context):
        token = self._user_token(session, user_context)
        # try a few common settings paths
        candidates = ["/api/user/notification-settings", "/api/ai-settings", "/api/settings"]
        statuses = {}
        for path in candidates:
            r = session.get(
                f"{BASE_URL}{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIMEOUT,
            )
            statuses[path] = r.status_code
            if r.status_code == 200:
                return
        pytest.fail(f"No settings endpoint returned 200: {statuses}")


# -------------- CPI Smoke --------------
class TestCPISmoke:
    def _user_token(self, session, user_context):
        r = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": user_context["email"], "password": user_context["password"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        return r.json()["access_token"]

    def test_cpi_dashboard_stats(self, session, user_context):
        token = self._user_token(session, user_context)
        r = session.get(
            f"{BASE_URL}/api/cpi/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"/api/cpi/dashboard/stats: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data, dict)

    def test_cpi_smartlinks_crud_smoke(self, session, user_context):
        token = self._user_token(session, user_context)
        # LIST
        r = session.get(
            f"{BASE_URL}/api/cpi/smartlinks",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"GET smartlinks: {r.status_code} {r.text[:300]}"
        # CREATE - best-effort; structure may vary. Test that endpoint doesn't 500.
        payload = {
            "name": f"TEST_sl_{_rand()}",
            "destination_url": "https://example.com",
            "target_url": "https://example.com",
        }
        r2 = session.post(
            f"{BASE_URL}/api/cpi/smartlinks",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=TIMEOUT,
        )
        assert r2.status_code != 500, f"POST smartlinks 500: {r2.text[:300]}"
        # if created, try the public redirect
        if r2.status_code in (200, 201):
            body = r2.json()
            code = body.get("code") or body.get("short_code") or body.get("slug")
            if code:
                r3 = session.get(
                    f"{BASE_URL}/api/sl/{code}",
                    allow_redirects=False,
                    timeout=TIMEOUT,
                )
                assert r3.status_code in (200, 301, 302, 303, 307, 308, 404), (
                    f"redirect unexpected status {r3.status_code}: {r3.text[:200]}"
                )
