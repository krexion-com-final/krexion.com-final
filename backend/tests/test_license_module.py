"""
Krexion License Module — backend test suite (iteration 2)
Tests the new /api/license/* (public) and /api/admin/license/* (admin)
endpoints introduced in license_module.py.

Run:
    pytest /app/backend/tests/test_license_module.py -v \\
        --junitxml=/app/test_reports/pytest/pytest_results.xml
"""
from __future__ import annotations

import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    # Fall back ONLY for local pytest runs — public URL also matches.
    "https://dynabook-dev.preview.emergentagent.com",
).rstrip("/")

ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "admin123"

# Unique prefix so we don't collide with prior trial licenses
RUN_TAG = uuid.uuid4().hex[:8]

# Cross-test state (avoids AttributeError when an earlier test fails)
STATE: dict = {
    "trial_key_A": None,
    "trial_email_A": None,
    "machine_a": None,
    "checkout_session_id": None,
    "issued_key": None,
    "orig_price": None,
    "orig_trial_days": None,
    "orig_enabled": None,
}


# ─────────────────────────── Fixtures ────────────────────────────────
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api):
    r = api.post(
        f"{BASE_URL}/api/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("is_admin") is True
    token = data["access_token"]
    assert isinstance(token, str) and len(token) > 20
    return token


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def user_token(api):
    """A regular (non-admin) auth token for negative tests on admin endpoints."""
    email = f"TEST_user_{RUN_TAG}@example.com"
    password = "Password123!"
    # Try register, ignore if already exists
    api.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": "Test User"},
        timeout=15,
    )
    r = api.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Could not create regular user token: {r.status_code} {r.text}")
    return r.json().get("access_token") or r.json().get("token")


# ─────────────────────── Public: /license/config ─────────────────────
class TestPublicConfig:
    def test_get_public_config(self, api):
        r = api.get(f"{BASE_URL}/api/license/config", timeout=10)
        assert r.status_code == 200
        d = r.json()
        # Schema
        for k in ("product_name", "monthly_price", "currency",
                  "trial_days", "max_pcs_per_license", "enabled"):
            assert k in d, f"Missing key '{k}' in public config"
        # No internal leakage
        assert "_id" not in d
        assert "updated_at" not in d  # public should be lean
        assert isinstance(d["monthly_price"], (int, float))
        assert isinstance(d["enabled"], bool)
        assert d["max_pcs_per_license"] >= 1


# ─────────────────────── Public: start-trial ─────────────────────────
class TestStartTrial:
    def test_start_trial_creates_license(self, api):
        email = f"TEST_trial_{RUN_TAG}_a@example.com"
        r = api.post(
            f"{BASE_URL}/api/license/start-trial",
            json={"email": email},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("reused") is False
        assert d.get("license_key", "").startswith("RFLW-")
        assert d.get("trial_ends_at")
        # Stash for later tests
        STATE['trial_key_A'] = d["license_key"]
        STATE['trial_email_A'] = email

    def test_start_trial_same_email_reuses(self, api):
        email = STATE['trial_email_A']
        r = api.post(
            f"{BASE_URL}/api/license/start-trial",
            json={"email": email},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("reused") is True
        assert d.get("license_key") == STATE['trial_key_A']


# ─────────────────────── Public: activate (1-PC) ─────────────────────
class TestActivate:
    def test_activate_binds_machine(self, api):
        machine_a = f"MID-A-{RUN_TAG}"
        r = api.post(
            f"{BASE_URL}/api/license/activate",
            json={
                "license_key": STATE['trial_key_A'],
                "machine_id": machine_a,
                "machine_label": "Test PC A",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["license"]["machine_id"] == machine_a
        assert "_id" not in d["license"]
        STATE['machine_a'] = machine_a

    def test_activate_second_machine_returns_409(self, api):
        machine_b = f"MID-B-{RUN_TAG}"
        r = api.post(
            f"{BASE_URL}/api/license/activate",
            json={
                "license_key": STATE['trial_key_A'],
                "machine_id": machine_b,
                "machine_label": "Test PC B",
            },
            timeout=15,
        )
        assert r.status_code == 409, (
            f"Expected 409 for 1-PC policy violation, got {r.status_code}: {r.text}"
        )

    def test_activate_same_machine_idempotent(self, api):
        # Re-activating with the SAME machine_id must succeed (idempotent)
        r = api.post(
            f"{BASE_URL}/api/license/activate",
            json={
                "license_key": STATE['trial_key_A'],
                "machine_id": STATE['machine_a'],
                "machine_label": "Test PC A (re-run)",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True


# ─────────────────────── Public: validate ────────────────────────────
class TestValidate:
    def test_validate_correct_machine(self, api):
        r = api.post(
            f"{BASE_URL}/api/license/validate",
            json={"license_key": STATE['trial_key_A'],
                  "machine_id": STATE['machine_a']},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["status"] in ("trial", "active")

    def test_validate_wrong_machine(self, api):
        r = api.post(
            f"{BASE_URL}/api/license/validate",
            json={"license_key": STATE['trial_key_A'],
                  "machine_id": f"WRONG-{RUN_TAG}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is False
        assert d["status"] == "wrong_machine"


# ─────────────────────── Public: checkout + status ───────────────────
class TestCheckout:
    def test_checkout_creates_session(self, api):
        r = api.post(
            f"{BASE_URL}/api/license/checkout",
            json={
                "license_key": STATE['trial_key_A'],
                "origin_url": BASE_URL,
            },
            timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("checkout_url", "").startswith("http")
        assert d.get("session_id")
        STATE['checkout_session_id'] = d["session_id"]

    def test_status_returns_stripe_session(self, api):
        r = api.get(
            f"{BASE_URL}/api/license/status/{STATE['checkout_session_id']}",
            timeout=20,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("status", "payment_status", "amount_total", "currency"):
            assert k in d, f"Missing '{k}' in status response: {d}"
        # Test mode session: not yet paid
        assert d["payment_status"] in ("unpaid", "paid", "no_payment_required")
        assert d["currency"] in ("usd", None)

    def test_status_unknown_session(self, api):
        r = api.get(
            f"{BASE_URL}/api/license/status/cs_test_unknown_{RUN_TAG}",
            timeout=15,
        )
        # Stripe call itself may 4xx, but our handler returns 404 for unknown txn
        assert r.status_code in (400, 404, 500), r.text


# ─────────────────────── Admin: config GET/PUT ───────────────────────
class TestAdminConfig:
    def test_admin_get_config(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/license/config",
                    headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("id") == "global"
        assert "_id" not in d
        # Stash originals so we can restore them
        STATE['orig_price'] = d["monthly_price"]
        STATE['orig_trial_days'] = d["trial_days"]
        STATE['orig_enabled'] = d["enabled"]

    def test_admin_put_updates_and_public_reflects(self, api, admin_headers):
        new_price = 49.0
        new_trial = 14
        r = api.put(
            f"{BASE_URL}/api/admin/license/config",
            headers=admin_headers,
            json={"monthly_price": new_price, "trial_days": new_trial},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["monthly_price"] == new_price
        assert d["trial_days"] == new_trial

        # Public endpoint must reflect the change
        time.sleep(0.5)
        rp = api.get(f"{BASE_URL}/api/license/config", timeout=10)
        assert rp.status_code == 200
        pd = rp.json()
        assert pd["monthly_price"] == new_price
        assert pd["trial_days"] == new_trial

        # Restore original values
        api.put(
            f"{BASE_URL}/api/admin/license/config",
            headers=admin_headers,
            json={"monthly_price": STATE['orig_price'],
                  "trial_days": STATE['orig_trial_days']},
            timeout=15,
        )


# ─────────────────────── Admin: list + search ────────────────────────
class TestAdminList:
    def test_list_paginated(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/license/list?skip=0&limit=10",
                    headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "total" in d and "items" in d
        assert isinstance(d["items"], list)
        for row in d["items"]:
            assert "_id" not in row

    def test_list_search_by_email(self, api, admin_headers):
        r = api.get(
            f"{BASE_URL}/api/admin/license/list?q={STATE['trial_email_A']}",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["total"] >= 1
        assert any(it["license_key"] == STATE['trial_key_A'] for it in d["items"])


# ─────────────────────── Admin: issue / extend / revoke ──────────────
class TestAdminIssueExtendRevoke:
    def test_admin_issue(self, api, admin_headers):
        email = f"TEST_issued_{RUN_TAG}@example.com"
        r = api.post(
            f"{BASE_URL}/api/admin/license/issue?email={email}&days=31",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["license_key"].startswith("RFLW-")
        assert d.get("subscription_ends_at")
        STATE['issued_key'] = d["license_key"]

    def test_admin_extend(self, api, admin_headers):
        r = api.post(
            f"{BASE_URL}/api/admin/license/extend/{STATE['issued_key']}?days=31",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d.get("subscription_ends_at")

    def test_admin_revoke_then_validate_says_revoked(self, api, admin_headers):
        # Bind the issued license to a machine first so we can validate
        machine = f"MID-ISSUED-{RUN_TAG}"
        r0 = api.post(
            f"{BASE_URL}/api/license/activate",
            json={"license_key": STATE['issued_key'],
                  "machine_id": machine, "machine_label": "Issued PC"},
            timeout=15,
        )
        assert r0.status_code == 200, r0.text

        # Revoke
        r = api.post(
            f"{BASE_URL}/api/admin/license/revoke/{STATE['issued_key']}",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

        # Validate should now report revoked
        rv = api.post(
            f"{BASE_URL}/api/license/validate",
            json={"license_key": STATE['issued_key'], "machine_id": machine},
            timeout=15,
        )
        assert rv.status_code == 200, rv.text
        d = rv.json()
        assert d["ok"] is False
        assert d["status"] == "revoked"

    def test_admin_revoke_unknown_404(self, api, admin_headers):
        r = api.post(
            f"{BASE_URL}/api/admin/license/revoke/RFLW-NOPE-NOPE-NOPE-NOPE",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 404


# ─────────────────────── Admin: transactions ─────────────────────────
class TestAdminTransactions:
    def test_admin_transactions_returns_list(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/license/transactions",
                    headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "total" in d and "items" in d
        assert isinstance(d["items"], list)
        # Our /checkout in TestCheckout should have inserted at least 1
        assert d["total"] >= 1
        for row in d["items"]:
            assert "_id" not in row


# ─────────────────────── Master switch (enabled=false) ───────────────
class TestMasterSwitch:
    def test_disable_blocks_activate(self, api, admin_headers):
        # Flip OFF
        r = api.put(
            f"{BASE_URL}/api/admin/license/config",
            headers=admin_headers, json={"enabled": False}, timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is False

        # Public config must mirror the switch
        rp = api.get(f"{BASE_URL}/api/license/config", timeout=10)
        assert rp.status_code == 200
        assert rp.json()["enabled"] is False

        # /license/activate should refuse
        try:
            r2 = api.post(
                f"{BASE_URL}/api/license/activate",
                json={"license_key": STATE['trial_key_A'],
                      "machine_id": STATE['machine_a']},
                timeout=15,
            )
            assert r2.status_code == 403, (
                f"Expected 403 when disabled, got {r2.status_code}: {r2.text}"
            )
            assert "disabled" in r2.text.lower()
        finally:
            # ALWAYS restore — even if asserts above failed
            api.put(
                f"{BASE_URL}/api/admin/license/config",
                headers=admin_headers, json={"enabled": True}, timeout=15,
            )

    def test_master_switch_restored(self, api):
        r = api.get(f"{BASE_URL}/api/license/config", timeout=10)
        assert r.status_code == 200
        assert r.json()["enabled"] is True, (
            "Master switch was NOT restored — subsequent test runs may fail!"
        )


# ─────────────────────── Admin auth: 401/403 negative tests ──────────
class TestAdminAuth:
    ADMIN_PATHS = [
        ("GET", "/api/admin/license/config"),
        ("GET", "/api/admin/license/list"),
        ("GET", "/api/admin/license/transactions"),
        ("POST", "/api/admin/license/revoke/RFLW-X-X-X-X"),
        ("POST", "/api/admin/license/extend/RFLW-X-X-X-X?days=7"),
        ("POST", "/api/admin/license/issue?email=foo@bar.com&days=7"),
    ]

    def test_no_token_rejected(self, api):
        for method, path in self.ADMIN_PATHS:
            r = api.request(method, f"{BASE_URL}{path}", timeout=10)
            assert r.status_code in (401, 403), (
                f"{method} {path} should reject anonymous, got {r.status_code}"
            )

    def test_non_admin_token_rejected(self, api, user_token):
        h = {"Authorization": f"Bearer {user_token}",
             "Content-Type": "application/json"}
        for method, path in self.ADMIN_PATHS:
            r = api.request(method, f"{BASE_URL}{path}", headers=h, timeout=10)
            assert r.status_code in (401, 403), (
                f"{method} {path} should reject non-admin, got {r.status_code}"
            )

    def test_put_config_no_token_rejected(self, api):
        r = api.put(f"{BASE_URL}/api/admin/license/config",
                    json={"monthly_price": 1.0}, timeout=10)
        assert r.status_code in (401, 403)


# ─────────────────────── _id leakage scan ────────────────────────────
class TestNoMongoIdLeak:
    def test_no_id_in_public_endpoints(self, api):
        # Quickly hit every public response we have keys for
        endpoints = [
            ("GET", f"{BASE_URL}/api/license/config", None),
            ("POST", f"{BASE_URL}/api/license/validate",
             {"license_key": STATE['trial_key_A'],
              "machine_id": STATE['machine_a']}),
        ]
        for method, url, body in endpoints:
            r = (api.get(url, timeout=10) if method == "GET"
                 else api.post(url, json=body, timeout=10))
            assert r.status_code in (200, 404), f"{url} → {r.status_code}"
            if r.headers.get("content-type", "").startswith("application/json"):
                assert '"_id"' not in r.text, f"_id leak in {url}: {r.text[:200]}"
