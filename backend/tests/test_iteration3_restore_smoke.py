"""
Iteration 3 — Restore-from-GitHub smoke test.
Verifies core backend surface after fresh dependency install:
  - health
  - admin login (seeded credentials)
  - user register + login
  - links CRUD (auth-gated)
  - cpi offers (admin-gated)
  - license config / start-trial / checkout (410)
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback for in-container run when REACT_APP_BACKEND_URL isn't exported
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "admin123"

RUN_TAG = uuid.uuid4().hex[:8]
USER_EMAIL = f"TEST_user_{RUN_TAG}@example.com"
USER_PASSWORD = "Passw0rd!123"
TRIAL_EMAIL = f"TEST_trial_{RUN_TAG}@example.com"


# ---------- shared fixtures ----------
@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(http):
    r = http.post(
        f"{BASE_URL}/api/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("is_admin") is True
    assert isinstance(data.get("access_token"), str) and len(data["access_token"]) > 10
    return data["access_token"]


@pytest.fixture(scope="module")
def user_token(http):
    # register
    r = http.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": USER_EMAIL, "password": USER_PASSWORD, "name": f"Test User {RUN_TAG}"},
        timeout=15,
    )
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    body = r.json()
    # Some flows return token immediately, some require login
    if isinstance(body, dict) and body.get("access_token"):
        return body["access_token"]

    r2 = http.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        timeout=15,
    )
    assert r2.status_code == 200, f"login failed: {r2.status_code} {r2.text}"
    tok = r2.json().get("access_token")
    assert tok, "no access_token in login response"
    return tok


# ---------- tests ----------
class TestHealth:
    def test_health_returns_200_mongo_ok(self, http):
        r = http.get(f"{BASE_URL}/api/diagnostics/health", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["checks"]["mongodb"]["status"] == "ok"


class TestAdminLogin:
    def test_admin_login_returns_token_and_flag(self, admin_token):
        # validated inside fixture; presence here proves fixture didn't skip
        assert isinstance(admin_token, str)


class TestUserAuth:
    def test_register_creates_user(self, http):
        email = f"TEST_reg_{uuid.uuid4().hex[:6]}@example.com"
        r = http.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": USER_PASSWORD, "name": "Test Reg"},
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body.get("access_token"), "no access_token in register response"
        assert body.get("user", {}).get("email") == email

    def test_login_with_module_user_returns_token(self, user_token):
        assert isinstance(user_token, str) and len(user_token) > 10


class TestLinks:
    def test_links_requires_auth(self, http):
        r = http.get(f"{BASE_URL}/api/links", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_links_list_authenticated(self, http, user_token):
        r = http.get(
            f"{BASE_URL}/api/links",
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=15,
        )
        # 200 OK or 403 if user is pending-approval — record both, but expect 200
        assert r.status_code in (200, 403), f"unexpected: {r.status_code} {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, (list, dict))

    def test_links_create_authenticated(self, http, user_token):
        payload = {
            "offer_url": "https://example.com/landing",
            "name": f"TEST_link_{RUN_TAG}",
        }
        r = http.post(
            f"{BASE_URL}/api/links",
            json=payload,
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=15,
        )
        # 200/201 success; 403 if account requires admin approval first
        assert r.status_code in (200, 201, 403), f"unexpected: {r.status_code} {r.text}"
        if r.status_code in (200, 201):
            body = r.json()
            # Verify reasonable response shape
            assert isinstance(body, dict)
            # Common keys: short_id/slug/short_code/id
            assert any(
                k in body for k in ("short_id", "slug", "short_code", "id", "_id", "short_url")
            ), f"no link-id-like key in response: {body}"


class TestCpiOffers:
    """Note: /api/cpi/offers requires an *authenticated user with the CPI feature flag*,
    NOT admin. The problem-statement spec was inaccurate — see _require_cpi_user in
    cpi_module.py. We test with the regular user token; a 403 is acceptable if the
    feature flag is off for new users by default."""

    def test_cpi_offers_requires_auth(self, http):
        r = http.get(f"{BASE_URL}/api/cpi/offers", timeout=15)
        assert r.status_code in (401, 403), r.status_code

    def test_cpi_offers_user_auth(self, http, user_token):
        r = http.get(
            f"{BASE_URL}/api/cpi/offers",
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=15,
        )
        assert r.status_code in (200, 403), f"unexpected: {r.status_code} {r.text}"
        if r.status_code == 200:
            assert isinstance(r.json(), list)

    def test_cpi_offers_admin_token_user_not_found(self, http, admin_token):
        """Admin token is NOT a regular user — cpi endpoints must reject it cleanly (401),
        not 500. Documents current behaviour."""
        r = http.get(
            f"{BASE_URL}/api/cpi/offers",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code in (401, 403), f"unexpected: {r.status_code} {r.text}"


class TestLicense:
    def test_license_config(self, http):
        r = http.get(f"{BASE_URL}/api/license/config", timeout=15)
        assert r.status_code == 200
        body = r.json()
        # Pricing/trial fields presence
        text = str(body).lower()
        assert any(k in text for k in ("price", "trial", "amount"))

    def test_license_start_trial(self, http):
        r = http.post(
            f"{BASE_URL}/api/license/start-trial",
            json={"email": TRIAL_EMAIL},
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert "license_key" in body and isinstance(body["license_key"], str)
        assert len(body["license_key"]) >= 8

    def test_license_checkout_returns_410(self, http):
        # CheckoutRequest schema requires license_key + origin_url; send valid body
        # so we reach the endpoint logic (which always raises 410 by design).
        r = http.post(
            f"{BASE_URL}/api/license/checkout",
            json={
                "license_key": f"TEST-{RUN_TAG}-KEY",
                "origin_url": "https://example.com",
            },
            timeout=15,
        )
        assert r.status_code == 410, f"expected 410 Gone, got {r.status_code} {r.text}"
        body = r.json()
        assert "disabled" in str(body).lower() or "gone" in str(body).lower()
