"""
Iteration 8 backend tests: Profile Builder (AdsPower) feature gating + CRUD.
Tests:
- /api/adspower/* feature gating via `profile_builder` flag (403 when disabled, 200 when admin enables)
- Static endpoints: states (50), ua-templates (6)
- Validation on configs/generate
- Admin PUT to set profile_builder=true via UserFeatures with extra='allow'
- New registration defaults profile_builder=false
"""

import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://flow-staging-6.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "admin123"
PRE_USER_EMAIL = "adspowertester@gmail.com"
PRE_USER_PASSWORD = "Test12345"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def pre_user_token():
    # The user with profile_builder=true pre-configured
    r = requests.post(f"{API}/auth/login", json={"email": PRE_USER_EMAIL, "password": PRE_USER_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"pre-created user login failed: {r.status_code} {r.text}")
    data = r.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="session")
def pre_user_headers(pre_user_token):
    return {"Authorization": f"Bearer {pre_user_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def fresh_user_info(admin_headers):
    """Register a brand new user (no profile_builder), activate via admin (status=active) but keep profile_builder=false."""
    email = f"TEST_pb_{uuid.uuid4().hex[:8]}@krexion.test"
    password = "Test12345!"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "PB Test"}, timeout=20)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"

    # Find user via admin list
    lr = requests.get(f"{API}/admin/users", headers=admin_headers, timeout=20)
    assert lr.status_code == 200, lr.text
    payload = lr.json()
    users = payload if isinstance(payload, list) else payload.get("users", [])
    user_doc = next((u for u in users if u.get("email") == email), None)
    assert user_doc, f"new user not in admin list: {email}"
    user_id = user_doc.get("id") or user_doc.get("_id")

    # Verify profile_builder default = false
    features_default = user_doc.get("features") or {}
    pb_default = features_default.get("profile_builder", False)
    assert pb_default is False, f"new user default profile_builder must be False, got {pb_default}"

    # Activate WITHOUT profile_builder flag (so feature gating still applies)
    upd = {"status": "active", "features": {**features_default, "profile_builder": False}}
    ur = requests.put(f"{API}/admin/users/{user_id}", headers=admin_headers, json=upd, timeout=20)
    assert ur.status_code == 200, ur.text

    # Login as that user
    lr2 = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert lr2.status_code == 200, lr2.text
    tok = lr2.json().get("access_token") or lr2.json().get("token")
    return {"email": email, "password": password, "id": user_id, "token": tok, "features": features_default}


# ─────────────── Static endpoints ───────────────
class TestStatic:
    def test_states_returns_50(self):
        r = requests.get(f"{API}/adspower/states", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        states = data.get("states") or data
        assert isinstance(states, list)
        assert len(states) == 50, f"expected 50 states, got {len(states)}"
        assert "California" in states

    def test_ua_templates_keys(self):
        r = requests.get(f"{API}/adspower/ua-templates", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        keys = data.get("templates") or []
        assert isinstance(keys, list)
        assert len(keys) == 6, f"expected 6 UA template keys, got {len(keys)}: {keys}"


# ─────────────── Feature gating: disabled user → 403 ───────────────
class TestGatingDisabled:
    def _h(self, fresh_user_info):
        return {"Authorization": f"Bearer {fresh_user_info['token']}", "Content-Type": "application/json"}

    def test_configs_get_403(self, fresh_user_info):
        r = requests.get(f"{API}/adspower/configs", headers=self._h(fresh_user_info), timeout=20)
        assert r.status_code == 403, f"{r.status_code} {r.text}"

    def test_configs_post_403(self, fresh_user_info):
        r = requests.post(f"{API}/adspower/configs", headers=self._h(fresh_user_info), json={"api_key": "x"}, timeout=20)
        assert r.status_code == 403

    def test_proxy_creds_get_403(self, fresh_user_info):
        r = requests.get(f"{API}/adspower/proxy-creds", headers=self._h(fresh_user_info), timeout=20)
        assert r.status_code == 403

    def test_proxy_creds_post_403(self, fresh_user_info):
        r = requests.post(f"{API}/adspower/proxy-creds", headers=self._h(fresh_user_info), json={"base_user": "a", "base_pass": "b"}, timeout=20)
        assert r.status_code == 403

    def test_generate_403(self, fresh_user_info):
        r = requests.post(f"{API}/adspower/generate", headers=self._h(fresh_user_info), json={"count": 1, "state": "California", "config_id": "x"}, timeout=20)
        assert r.status_code == 403

    def test_jobs_403(self, fresh_user_info):
        r = requests.get(f"{API}/adspower/jobs/nonexistent", headers=self._h(fresh_user_info), timeout=20)
        assert r.status_code == 403

    def test_profiles_403(self, fresh_user_info):
        r = requests.get(f"{API}/adspower/profiles", headers=self._h(fresh_user_info), timeout=20)
        assert r.status_code == 403


# ─────────────── Admin toggle enables flag ───────────────
class TestAdminToggle:
    def test_admin_enables_profile_builder(self, admin_headers, fresh_user_info):
        # Enable profile_builder
        upd = {"status": "active", "features": {**fresh_user_info["features"], "profile_builder": True}}
        r = requests.put(f"{API}/admin/users/{fresh_user_info['id']}", headers=admin_headers, json=upd, timeout=20)
        assert r.status_code == 200, r.text

        # Re-login to pick up the new feature flag
        lr = requests.post(f"{API}/auth/login", json={"email": fresh_user_info["email"], "password": fresh_user_info["password"]}, timeout=20)
        assert lr.status_code == 200, lr.text
        new_tok = lr.json().get("access_token") or lr.json().get("token")
        fresh_user_info["token"] = new_tok

        # Now GET /configs should be 200
        h = {"Authorization": f"Bearer {new_tok}"}
        gr = requests.get(f"{API}/adspower/configs", headers=h, timeout=20)
        assert gr.status_code == 200, f"after admin toggle, expected 200, got {gr.status_code} {gr.text}"
        assert "configs" in gr.json()


# ─────────────── Enabled user: CRUD + validation ───────────────
class TestEnabledFlow:
    def _h(self, fresh_user_info):
        return {"Authorization": f"Bearer {fresh_user_info['token']}", "Content-Type": "application/json"}

    def test_config_missing_api_key_400(self, fresh_user_info):
        r = requests.post(f"{API}/adspower/configs", headers=self._h(fresh_user_info), json={"name": "x"}, timeout=20)
        assert r.status_code == 400, f"{r.status_code} {r.text}"

    def test_save_config_then_list(self, fresh_user_info):
        save = requests.post(
            f"{API}/adspower/configs",
            headers=self._h(fresh_user_info),
            json={"name": "TEST_cfg", "api_key": "TEST_apikey_abcdefghij"},
            timeout=20,
        )
        assert save.status_code == 200, save.text
        body = save.json()
        assert body.get("id")
        assert body.get("api_key_masked"), "api_key must be masked"
        assert "api_key" not in body, "raw api_key must NOT leak"

        lst = requests.get(f"{API}/adspower/configs", headers=self._h(fresh_user_info), timeout=20)
        assert lst.status_code == 200
        configs = lst.json().get("configs", [])
        assert any(c["id"] == body["id"] for c in configs)
        fresh_user_info["_cfg_id"] = body["id"]

    def test_save_proxy_creds(self, fresh_user_info):
        r = requests.post(
            f"{API}/adspower/proxy-creds",
            headers=self._h(fresh_user_info),
            json={"base_user": "TEST_baseuser_260202", "base_pass": "TEST_basepass"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("saved") is True

        st = requests.get(f"{API}/adspower/proxy-creds", headers=self._h(fresh_user_info), timeout=20)
        assert st.status_code == 200
        body = st.json()
        assert body.get("has_creds") is True
        assert "base_user_masked" in body

    def test_generate_validation_count_zero(self, fresh_user_info):
        r = requests.post(
            f"{API}/adspower/generate",
            headers=self._h(fresh_user_info),
            json={"count": 0, "state": "California", "config_id": fresh_user_info.get("_cfg_id", "x")},
            timeout=20,
        )
        assert r.status_code == 400, f"expected 400 for count=0, got {r.status_code} {r.text}"

    def test_generate_validation_count_too_high(self, fresh_user_info):
        r = requests.post(
            f"{API}/adspower/generate",
            headers=self._h(fresh_user_info),
            json={"count": 101, "state": "California", "config_id": fresh_user_info.get("_cfg_id", "x")},
            timeout=20,
        )
        assert r.status_code == 400

    def test_generate_validation_invalid_state(self, fresh_user_info):
        r = requests.post(
            f"{API}/adspower/generate",
            headers=self._h(fresh_user_info),
            json={"count": 1, "state": "Atlantis", "config_id": fresh_user_info.get("_cfg_id", "x")},
            timeout=20,
        )
        assert r.status_code == 400

    def test_generate_validation_missing_config_id(self, fresh_user_info):
        r = requests.post(
            f"{API}/adspower/generate",
            headers=self._h(fresh_user_info),
            json={"count": 1, "state": "California"},
            timeout=20,
        )
        assert r.status_code == 400

    def test_jobs_invalid_id_404(self, fresh_user_info):
        r = requests.get(f"{API}/adspower/jobs/nonexistent-id-xyz", headers=self._h(fresh_user_info), timeout=20)
        assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text}"

    def test_generate_returns_job_id(self, fresh_user_info):
        # Needs valid config_id
        cfg_id = fresh_user_info.get("_cfg_id")
        assert cfg_id, "no cfg_id from earlier test"
        r = requests.post(
            f"{API}/adspower/generate",
            headers=self._h(fresh_user_info),
            json={"count": 1, "state": "California", "config_id": cfg_id, "name_prefix": "TEST_"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("job_id")
        assert body.get("status") == "started"

    def test_delete_config(self, fresh_user_info):
        cfg_id = fresh_user_info.get("_cfg_id")
        if not cfg_id:
            pytest.skip("no cfg_id")
        r = requests.delete(f"{API}/adspower/configs/{cfg_id}", headers=self._h(fresh_user_info), timeout=20)
        assert r.status_code == 200, r.text
        lst = requests.get(f"{API}/adspower/configs", headers=self._h(fresh_user_info), timeout=20)
        ids = [c["id"] for c in lst.json().get("configs", [])]
        assert cfg_id not in ids


# ─────────────── Default features on register ───────────────
class TestRegistrationDefaults:
    def test_new_user_profile_builder_false(self, admin_headers):
        email = f"TEST_def_{uuid.uuid4().hex[:8]}@krexion.test"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test12345!", "name": "Def"}, timeout=20)
        assert r.status_code in (200, 201), r.text
        lr = requests.get(f"{API}/admin/users", headers=admin_headers, timeout=20)
        users = lr.json() if isinstance(lr.json(), list) else lr.json().get("users", [])
        u = next((x for x in users if x.get("email") == email), None)
        assert u, "user not found in admin list"
        assert (u.get("features") or {}).get("profile_builder", False) is False
