"""
Iteration 12 - Backend feature-gating regression tests
=======================================================
Tests for check_user_feature() enforcement across customer-facing endpoints:
- When admin sets features.<flag>=False, the corresponding endpoints return 403
- When admin sets features.<flag>=True, the corresponding endpoints return 200/non-403

Reference: review_request features_or_bugs_to_test items 4 & 5
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://krexion-build-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "admin123"
USER_EMAIL = "test@krexion.local"
USER_PASSWORD = "test1234"
USER_ID = "6a0402d8-aa47-4924-a5e8-92b748e7a08b"

# Feature flag -> (HTTP method, endpoint) mapping. Only GET endpoints
# requiring no payload are used here to keep tests pure-read.
# Each entry: feature -> (method, path, json_body_or_None)
# Some features only gate POST endpoints, so we send empty/minimal payloads.
# The gating check runs BEFORE pydantic validation in these endpoints, so a
# disabled feature must still return 403 (NOT 422/400) for the test to pass.
FEATURE_ENDPOINTS = {
    "form_filler":       ("GET",  "/form-filler/jobs",          None),
    "email_checker":     ("POST", "/emails/check-profile-pics", {"emails": ["x@y.com"]}),
    "separate_data":     ("POST_FORM", "/emails/filter-rows",   None),
    "ua_generator":      ("POST", "/user-agents/check",         {"user_agent": "Mozilla/5.0"}),
    "conversions":       ("GET",  "/conversions",               None),
    "links":             ("GET",  "/links",                     None),
    "clicks":            ("GET",  "/clicks",                    None),
    "real_user_traffic": ("GET",  "/real-user-traffic/jobs",    None),
    "profile_builder":   ("GET",  "/adspower/profiles",         None),
    "proxies":           ("GET",  "/proxies",                   None),
    "import_traffic":    ("POST", "/clicks/import",             {}),
    "cpi":               ("GET",  "/cpi/offers",                None),
}


# ─── Fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _user_login():
    r = requests.post(f"{API}/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"User login failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def user_token():
    return _user_login()


def _set_features(admin_headers, features_dict):
    """PUT /api/admin/users/{user_id} to update feature flags."""
    payload = {"features": features_dict}
    r = requests.put(f"{API}/admin/users/{USER_ID}", headers=admin_headers, json=payload, timeout=15)
    assert r.status_code in (200, 204), f"Admin PUT failed: {r.status_code} {r.text[:300]}"
    return r


ALL_ENABLED = {
    "links": True, "clicks": True, "conversions": True, "proxies": True,
    "import_data": True, "import_traffic": True, "real_traffic": True,
    "ua_generator": True, "email_checker": True, "separate_data": True,
    "form_filler": True, "real_user_traffic": True, "settings": True,
    "profile_builder": True, "visual_recorder": True, "adspower": True,
    "uploaded_things": True, "traffic_sources": True, "cpi": True,
}


# ─── Sanity tests ────────────────────────────────────────────────────────
class TestAuthSmoke:
    def test_admin_login(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_user_login(self, user_token):
        assert isinstance(user_token, str) and len(user_token) > 20

    def test_admin_can_get_user(self, admin_headers):
        r = requests.get(f"{API}/admin/users/{USER_ID}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("id") == USER_ID or data.get("user", {}).get("id") == USER_ID or data.get("email") == USER_EMAIL


# ─── Feature gating disable→403 / enable→non-403 ────────────────────────
def _do_request(method, url, headers, body):
    if method == "POST_FORM":
        files = {"file": ("t.csv", b"a,b\n1,2\n", "text/csv")}
        return requests.post(url, headers=headers, files=files, data={"emails": "x@y.com"}, timeout=15)
    return requests.request(method, url, headers=headers, json=body, timeout=15)


@pytest.mark.parametrize("feature,method_ep", list(FEATURE_ENDPOINTS.items()))
def test_feature_disabled_returns_403(admin_headers, feature, method_ep):
    method, ep, body = method_ep
    feats = {**ALL_ENABLED, feature: False}
    _set_features(admin_headers, feats)
    time.sleep(0.3)
    token = _user_login()
    hdrs = {"Authorization": f"Bearer {token}"}
    r = _do_request(method, f"{API}{ep}", hdrs, body)
    _set_features(admin_headers, ALL_ENABLED)
    assert r.status_code == 403, (
        f"Feature '{feature}' disabled but {method} {ep} returned {r.status_code} "
        f"(expected 403). Body: {r.text[:300]}"
    )


@pytest.mark.parametrize("feature,method_ep", list(FEATURE_ENDPOINTS.items()))
def test_feature_enabled_returns_non_403(admin_headers, feature, method_ep):
    method, ep, body = method_ep
    _set_features(admin_headers, ALL_ENABLED)
    time.sleep(0.3)
    token = _user_login()
    hdrs = {"Authorization": f"Bearer {token}"}
    r = _do_request(method, f"{API}{ep}", hdrs, body)
    assert r.status_code != 403, (
        f"Feature '{feature}' enabled but {method} {ep} returned 403. Body: {r.text[:300]}"
    )
    assert r.status_code < 500, f"5xx for {method} {ep}: {r.status_code} {r.text[:200]}"


# ─── Restore final state ────────────────────────────────────────────────
def test_zz_restore_all_features(admin_headers):
    """Final test: ensure test user ends with ALL features enabled."""
    _set_features(admin_headers, ALL_ENABLED)
    token = _user_login()
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert me.status_code == 200
    feats = me.json().get("features", {})
    for k in ("links", "clicks", "conversions", "form_filler", "cpi", "real_user_traffic"):
        assert feats.get(k) is True, f"Feature {k} not restored to True (got {feats.get(k)})"
