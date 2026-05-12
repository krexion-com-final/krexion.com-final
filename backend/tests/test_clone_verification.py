"""
RealFlow Clone Verification Smoke Test
Tests core flows after cloning the repo: admin login, user login, admin actions,
approval flow, RUT engine status, and basic CRUD/list endpoints for approved users.
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://amna-flow-test.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@realflow.local"
ADMIN_PASSWORD = "admin123"

TEST_USER_EMAIL = f"TEST_clone_{uuid.uuid4().hex[:8]}@test.com"
TEST_USER_PASSWORD = "test12345"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(f"{API}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("is_admin") is True
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def new_user(session):
    payload = {"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD, "name": "Clone Test User"}
    r = session.post(f"{API}/auth/register", json=payload)
    assert r.status_code in (200, 201), f"Register failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    assert data["user"]["email"] == TEST_USER_EMAIL
    assert data["user"]["status"] == "pending"
    return data["user"]


# ---------- Admin Auth ----------

class TestAdminAuth:
    def test_admin_login(self, admin_token):
        assert admin_token and len(admin_token) > 20

    def test_admin_login_bad_password(self, session):
        r = session.post(f"{API}/admin/login", json={"email": ADMIN_EMAIL, "password": "bad"})
        assert r.status_code in (400, 401, 403)


# ---------- User Auth ----------

class TestUserAuth:
    def test_register_creates_pending_user(self, new_user):
        assert new_user["status"] == "pending"

    def test_login_pending_user(self, session, new_user):
        r = session.post(f"{API}/auth/login", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email"] == TEST_USER_EMAIL

    def test_seed_test_user_login(self, session):
        # Pre-existing test user from seed
        r = session.post(f"{API}/auth/login", json={"email": "test@test.com", "password": "test12345"})
        assert r.status_code == 200, r.text


# ---------- Admin endpoints ----------

class TestAdminEndpoints:
    def test_list_users(self, session, admin_headers):
        r = session.get(f"{API}/admin/users", headers=admin_headers)
        assert r.status_code == 200, r.text
        users = r.json()
        assert isinstance(users, list)
        assert any(u.get("email") == TEST_USER_EMAIL for u in users)

    def test_users_stats(self, session, admin_headers):
        r = session.get(f"{API}/admin/users/stats/all", headers=admin_headers)
        assert r.status_code == 200, r.text

    def test_system_check(self, session, admin_headers):
        r = session.get(f"{API}/admin/system-check", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        # overall should be one of healthy/degraded; failed components soft-fail allowed
        assert "overall" in data or "status" in data
        # Print so the test report reflects it
        print("system-check:", data)

    def test_admin_stats(self, session, admin_headers):
        r = session.get(f"{API}/admin/stats", headers=admin_headers)
        assert r.status_code == 200, r.text


# ---------- Approval flow ----------

class TestApprovalFlow:
    def test_admin_approves_user_and_enables_features(self, session, admin_headers, new_user):
        user_id = new_user["id"]
        payload = {
            "status": "active",
            "features": {
                "links": True, "clicks": True, "conversions": True, "proxies": True,
                "import_data": True, "import_traffic": True, "real_traffic": True,
                "real_user_traffic": True,
                "ua_generator": True, "email_checker": True,
            }
        }
        r = session.put(f"{API}/admin/users/{user_id}", headers=admin_headers, json=payload)
        assert r.status_code == 200, r.text

    def test_user_can_login_after_approval(self, session):
        r = session.post(f"{API}/auth/login", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["status"] == "active"
        assert data["user"]["features"].get("real_traffic") is True


# ---------- Approved user endpoints ----------

@pytest.fixture(scope="module")
def user_token(session):
    # Ensure approved (covered by TestApprovalFlow run order)
    r = session.post(f"{API}/auth/login", json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}


class TestApprovedUserEndpoints:
    def test_auth_me(self, session, user_headers):
        r = session.get(f"{API}/auth/me", headers=user_headers)
        assert r.status_code == 200, r.text
        assert r.json()["email"] == TEST_USER_EMAIL

    def test_engine_status(self, session, user_headers):
        r = session.get(f"{API}/real-user-traffic/engine-status", headers=user_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        print("engine-status:", data)
        # Acceptable values: ready / installing / error - report status
        assert "status" in data

    def test_list_links(self, session, user_headers):
        r = session.get(f"{API}/links", headers=user_headers)
        assert r.status_code in (200, 404), r.text

    def test_list_clicks(self, session, user_headers):
        r = session.get(f"{API}/clicks", headers=user_headers)
        assert r.status_code in (200, 404), r.text

    def test_list_conversions(self, session, user_headers):
        r = session.get(f"{API}/conversions", headers=user_headers)
        assert r.status_code in (200, 404), r.text

    def test_list_proxies(self, session, user_headers):
        r = session.get(f"{API}/proxies", headers=user_headers)
        assert r.status_code in (200, 404), r.text

    def test_list_subusers(self, session, user_headers):
        r = session.get(f"{API}/sub-users", headers=user_headers)
        assert r.status_code == 200, r.text

    def test_list_rut_jobs(self, session, user_headers):
        r = session.get(f"{API}/real-user-traffic/jobs", headers=user_headers)
        assert r.status_code == 200, r.text


# ---------- Cleanup ----------

def test_zz_cleanup(session, admin_headers):
    """Delete the TEST_ user created during this run."""
    r = session.get(f"{API}/admin/users", headers=admin_headers)
    if r.status_code == 200:
        for u in r.json():
            if u.get("email") == TEST_USER_EMAIL:
                session.delete(f"{API}/admin/users/{u['id']}", headers=admin_headers)
