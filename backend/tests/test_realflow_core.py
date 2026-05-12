"""
RealFlow backend core smoke tests.

Coverage (per review_request):
  - GET  /api/diagnostics/health
  - POST /api/admin/login           (admin@realflow.local / admin123)
  - POST /api/auth/register
  - POST /api/auth/login
  - GET  /api/links                 (regular user)
  - POST /api/links                 (regular user, after admin enables `links` + status=active)
  - GET  /api/cpi/offers            (regular user, after admin enables `cpi`)
  - General smoke: no critical 500s on the routes hit above.

Notes:
  * Newly-registered users start with status="pending" and all feature flags
    disabled, so /api/links and /api/cpi/offers will return 403 until the
    admin activates them + flips the feature flag. We test both states.
"""

import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://dynabook-dev.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@realflow.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


# ───────────────────────────── fixtures ─────────────────────────────

@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(session):
    r = session.post(
        f"{BASE_URL}/api/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "access_token" in data and isinstance(data["access_token"], str) and data["access_token"]
    assert data.get("is_admin") is True
    return data["access_token"]


@pytest.fixture(scope="session")
def test_user(session):
    """Register a fresh test user and return (email, password, token, user_id)."""
    unique = uuid.uuid4().hex[:10]
    email = f"TEST_{unique}@realflow.local"
    password = "Test1234!"
    name = f"TEST User {unique}"
    r = session.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": name},
        timeout=15,
    )
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "access_token" in data and data["access_token"]
    assert data["user"]["email"] == email
    assert data["user"]["name"] == name
    return {
        "email": email,
        "password": password,
        "name": name,
        "token": data["access_token"],
        "id": data["user"]["id"],
        "status": data["user"]["status"],
    }


# ───────────────────────────── tests ─────────────────────────────

# Diagnostics module
class TestDiagnostics:
    def test_health_ok(self, session):
        r = session.get(f"{BASE_URL}/api/diagnostics/health", timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # Per server.py /api/diagnostics/health returns a dict with checks
        assert isinstance(data, dict)
        # Either explicit "checks" key, or at least some keys present
        assert "checks" in data or len(data) > 0


# Admin auth module
class TestAdminAuth:
    def test_admin_login_success(self, session):
        r = session.post(
            f"{BASE_URL}/api/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["token_type"] == "bearer"
        assert data["is_admin"] is True
        assert isinstance(data["access_token"], str) and len(data["access_token"]) > 10

    def test_admin_login_invalid(self, session):
        r = session.post(
            f"{BASE_URL}/api/admin/login",
            json={"email": ADMIN_EMAIL, "password": "wrong-password"},
            timeout=15,
        )
        assert r.status_code in (400, 401, 403), r.text[:300]


# User auth module
class TestUserAuth:
    def test_register_and_login(self, session, test_user):
        # Already registered via fixture; just verify login works for same creds
        r = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["access_token"]
        assert data["user"]["email"] == test_user["email"]
        assert data["user"]["is_sub_user"] is False

    def test_register_duplicate_rejected(self, session, test_user):
        r = session.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
                "name": test_user["name"],
            },
            timeout=15,
        )
        assert r.status_code == 400, r.text[:300]

    def test_login_invalid_password(self, session, test_user):
        r = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": test_user["email"], "password": "totally-wrong"},
            timeout=15,
        )
        assert r.status_code == 401, r.text[:300]


# Links module (gated by `links` feature + status=active)
class TestLinks:
    def test_links_blocked_for_pending_user(self, session, test_user):
        """Freshly-registered users are status=pending → /api/links must 403."""
        r = session.get(
            f"{BASE_URL}/api/links",
            headers={"Authorization": f"Bearer {test_user['token']}"},
            timeout=15,
        )
        assert r.status_code == 403, r.text[:300]

    def test_links_unauthorized_without_token(self, session):
        r = session.get(f"{BASE_URL}/api/links", timeout=15)
        assert r.status_code in (401, 403), r.text[:300]

    def test_links_after_admin_activates_user(self, session, admin_token, test_user):
        # Admin activates user and enables links feature
        upd = session.put(
            f"{BASE_URL}/api/admin/users/{test_user['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "status": "active",
                "features": {
                    "links": True,
                    "clicks": True,
                    "conversions": True,
                    "max_links": 100,
                    "max_clicks": 100000,
                    "cpi": True,  # used by next test class
                },
            },
            timeout=15,
        )
        assert upd.status_code == 200, upd.text[:300]
        body = upd.json()
        assert body["user"]["status"] == "active"
        assert body["user"]["features"]["links"] is True

        # Now /api/links should return 200 with empty list
        r = session.get(
            f"{BASE_URL}/api/links",
            headers={"Authorization": f"Bearer {test_user['token']}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, list)
        assert data == []

    def test_create_link_then_list(self, session, test_user):
        payload = {
            "offer_url": "https://example.com/offer?aff=TEST_realflow",
            "status": "active",
            "name": "TEST_link_smoke",
        }
        r = session.post(
            f"{BASE_URL}/api/links",
            headers={"Authorization": f"Bearer {test_user['token']}"},
            json=payload,
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        created = r.json()
        assert "id" in created and "short_code" in created
        assert created["offer_url"] == payload["offer_url"]
        assert created["name"] == "TEST_link_smoke"
        link_id = created["id"]

        # GET to verify persistence
        r = session.get(
            f"{BASE_URL}/api/links/{link_id}",
            headers={"Authorization": f"Bearer {test_user['token']}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        fetched = r.json()
        assert fetched["id"] == link_id
        assert fetched["short_code"] == created["short_code"]

        # Cleanup
        r = session.delete(
            f"{BASE_URL}/api/links/{link_id}",
            headers={"Authorization": f"Bearer {test_user['token']}"},
            timeout=15,
        )
        assert r.status_code in (200, 204), r.text[:300]


# CPI module
class TestCPI:
    def test_cpi_offers_listable_after_feature_enabled(self, session, test_user):
        # Feature already enabled in TestLinks.test_links_after_admin_activates_user
        r = session.get(
            f"{BASE_URL}/api/cpi/offers",
            headers={"Authorization": f"Bearer {test_user['token']}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, list)

    def test_cpi_unauthorized(self, session):
        r = session.get(f"{BASE_URL}/api/cpi/offers", timeout=15)
        assert r.status_code in (401, 403), r.text[:300]


# Smoke: ensure none of the touched endpoints return 5xx
class TestNoCriticalErrors:
    @pytest.mark.parametrize("path", [
        "/api/diagnostics/health",
        "/api/admin/login",
        "/api/auth/login",
        "/api/auth/register",
        "/api/links",
        "/api/cpi/offers",
    ])
    def test_no_5xx_on_core_paths(self, session, path):
        # We don't care about the body or 4xx auth errors — only 5xx is fatal.
        if path in ("/api/admin/login", "/api/auth/login"):
            r = session.post(f"{BASE_URL}{path}", json={"email": "x@x.x", "password": "x"}, timeout=15)
        elif path == "/api/auth/register":
            r = session.post(
                f"{BASE_URL}{path}",
                json={"email": "x@x.x", "password": "x", "name": "x"},
                timeout=15,
            )
        else:
            r = session.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code < 500, f"{path} → {r.status_code}: {r.text[:300]}"


# ───────────────────────────── teardown ─────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def cleanup(session, request):
    yield
    # Best-effort cleanup: delete the TEST_ user via admin
    try:
        admin_r = session.post(
            f"{BASE_URL}/api/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10,
        )
        if admin_r.status_code != 200:
            return
        admin_tok = admin_r.json()["access_token"]
        # Find any TEST_ users (best-effort)
        users_r = session.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_tok}"},
            timeout=10,
        )
        if users_r.status_code == 200:
            for u in users_r.json():
                if u.get("email", "").startswith("TEST_"):
                    session.delete(
                        f"{BASE_URL}/api/admin/users/{u['id']}",
                        headers={"Authorization": f"Bearer {admin_tok}"},
                        timeout=10,
                    )
    except Exception:
        pass
