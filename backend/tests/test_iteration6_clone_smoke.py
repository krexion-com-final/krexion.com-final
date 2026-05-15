"""
Iteration 6 - Fresh-clone backend smoke test for Krexion / dynabook.
Covers: diagnostics, admin login, license module, user register/login/approve, links.
Uses REACT_APP_BACKEND_URL from frontend/.env so we hit the same edge-routed URL the UI uses.
"""
import os
import time
import uuid
import pytest
import requests

# Resolve BASE_URL from frontend/.env (same URL the user sees)
def _resolve_base_url():
    env = os.environ.get("REACT_APP_BACKEND_URL")
    if env:
        return env.rstrip("/")
    # fallback: read frontend/.env
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _resolve_base_url()
ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/admin/login",
                 json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                 timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:300]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in response: {r.text[:200]}"
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------------- Diagnostics ----------------

class TestDiagnostics:
    def test_health_200_and_mongo_ok(self, api):
        r = api.get(f"{BASE_URL}/api/diagnostics/health", timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # mongodb status lives under checks.mongodb.status (iter-5 note)
        checks = data.get("checks") or {}
        mongo = checks.get("mongodb") or {}
        mongo_status = mongo.get("status") or data.get("mongodb")
        assert mongo_status in ("ok", "healthy", "up", True), f"mongo not ok: {data}"

    def test_hardware_profile(self, api):
        r = api.get(f"{BASE_URL}/api/diagnostics/hardware-profile", timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # Tier surfaced under recommended_tier (LOW/MID/HIGH/ULTRA)
        tier = data.get("recommended_tier") or data.get("tier") or data.get("hardware_tier")
        assert tier, f"no tier field: {data}"
        # Detected resources sanity
        detected = data.get("detected") or {}
        assert detected.get("cpu_cores") or detected.get("cpu_count") or detected.get("total_ram_gb"), \
            f"detected block missing resource fields: {detected}"


# ---------------- Admin auth ----------------

class TestAdminAuth:
    def test_admin_login_returns_jwt(self, api):
        r = api.post(f"{BASE_URL}/api/admin/login",
                     json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                     timeout=15)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        tok = body.get("access_token") or body.get("token")
        assert tok and isinstance(tok, str) and len(tok) > 20

    def test_admin_login_bad_credentials(self, api):
        r = api.post(f"{BASE_URL}/api/admin/login",
                     json={"email": ADMIN_EMAIL, "password": "wrong_password_xyz"},
                     timeout=15)
        assert r.status_code in (400, 401, 403), f"expected 401-ish, got {r.status_code}"


# ---------------- License module ----------------

class TestLicense:
    def test_public_license_config(self, api):
        r = api.get(f"{BASE_URL}/api/license/config", timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # Should be a dict with at least one config flag
        assert isinstance(data, dict) and len(data) > 0

    def test_admin_license_list_requires_jwt(self, api):
        r = api.get(f"{BASE_URL}/api/admin/license/list", timeout=15)
        assert r.status_code in (401, 403), f"expected auth required, got {r.status_code}"

    def test_admin_license_list_with_jwt(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/license/list", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # Accept either a list or a dict containing a list
        if isinstance(data, dict):
            assert any(isinstance(v, list) for v in data.values()), f"no list in response: {list(data.keys())}"
        else:
            assert isinstance(data, list)


# ---------------- User auth + Links ----------------

@pytest.fixture(scope="session")
def test_user(api, admin_headers):
    """Register a TEST_ user, approve via admin, log in, return token + id."""
    uniq = uuid.uuid4().hex[:8]
    email = f"TEST_clone_{uniq}@example.com"
    password = "TestPass123!"
    name = f"TEST clone {uniq}"

    # Register
    r = api.post(f"{BASE_URL}/api/auth/register",
                 json={"email": email, "password": password, "name": name},
                 timeout=15)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:300]}"

    # Find user via admin
    list_r = api.get(f"{BASE_URL}/api/admin/users", headers=admin_headers, timeout=15)
    assert list_r.status_code == 200, list_r.text[:300]
    users_payload = list_r.json()
    users = users_payload if isinstance(users_payload, list) else users_payload.get("users", [])
    user = next((u for u in users if u.get("email") == email), None)
    assert user, f"newly registered user not in /api/admin/users"
    uid = user.get("id") or user.get("_id") or user.get("user_id")
    assert uid

    # Approve + enable links feature
    appr = api.put(f"{BASE_URL}/api/admin/users/{uid}",
                   headers=admin_headers,
                   json={"status": "active", "features": {"links": True}},
                   timeout=15)
    assert appr.status_code in (200, 204), f"approve failed: {appr.status_code} {appr.text[:300]}"

    # Login as user
    login = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": email, "password": password},
                     timeout=15)
    assert login.status_code == 200, f"user login failed: {login.status_code} {login.text[:300]}"
    body = login.json()
    token = body.get("access_token") or body.get("token")
    assert token

    return {"id": uid, "email": email, "password": password, "token": token,
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}}


class TestUserAuth:
    def test_register_login_and_jwt(self, test_user):
        assert test_user["token"]
        assert test_user["email"].startswith("TEST_")

    def test_login_bad_password(self, api, test_user):
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": test_user["email"], "password": "bad_pw_999"},
                     timeout=15)
        assert r.status_code in (400, 401, 403)

    def test_register_duplicate_email_rejected(self, api, test_user):
        r = api.post(f"{BASE_URL}/api/auth/register",
                     json={"email": test_user["email"], "password": "AnotherPass1!",
                           "name": "dup"},
                     timeout=15)
        assert r.status_code in (400, 409, 422), f"expected duplicate rejection, got {r.status_code}"


class TestLinks:
    def test_links_requires_jwt(self, api):
        r = api.get(f"{BASE_URL}/api/links", timeout=15)
        assert r.status_code in (401, 403), f"expected auth required, got {r.status_code}"

    def test_links_list_with_jwt(self, api, test_user):
        r = api.get(f"{BASE_URL}/api/links", headers=test_user["headers"], timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # accept list or {"links": [...]}
        if isinstance(data, dict):
            assert "links" in data or any(isinstance(v, list) for v in data.values())
        else:
            assert isinstance(data, list)
