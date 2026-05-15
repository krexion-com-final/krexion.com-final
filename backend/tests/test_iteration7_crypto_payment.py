"""
Iteration 7 — Crypto payment lifecycle + Resend email integration tests.
Covers all endpoints listed in the review request for the Krexion crypto module.
"""
import os
import re
import uuid
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback to frontend .env value
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE = ln.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "admin123"
WALLET_ENV = "TPT9ja87EdGhcRJz2bR6rqhFfrjm1edWTR"

LICENSE_KEY_RE = re.compile(r"^KRX-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}$")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(f"{BASE}/api/admin/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    })
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No token in admin login response: {data}"
    return tok


@pytest.fixture(scope="module")
def admin_session(session, admin_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    return s


# ─── Plans ─────────────────────────────────────────────────────────────
def test_list_plans_public(session):
    r = session.get(f"{BASE}/api/crypto/plans")
    assert r.status_code == 200
    data = r.json()
    assert "plans" in data
    plans = data["plans"]
    plan_ids = {p["id"] for p in plans}
    # Expected 4 seeded plans
    for expected in ("trial", "starter", "pro", "business"):
        assert expected in plan_ids, f"Missing plan {expected}; got {plan_ids}"
    # All enabled
    assert all(p.get("enabled") for p in plans)


# ─── Wallet ────────────────────────────────────────────────────────────
def test_active_wallet_matches_env(session):
    r = session.get(f"{BASE}/api/crypto/wallets/active")
    assert r.status_code == 200
    wallets = r.json().get("wallets", [])
    assert len(wallets) >= 1
    trc = [w for w in wallets if w["network"] == "TRC20" and w.get("enabled")]
    assert trc, "No active TRC20 wallet"
    assert any(w["address"] == WALLET_ENV for w in trc), \
        f"Wallet does not match env. Got {[w['address'] for w in trc]}"


# ─── Order create ──────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def created_order(session):
    payload = {
        "plan_id": "trial",
        "customer_name": "TEST Iter7 Customer",
        "customer_email": f"us9661626+test{uuid.uuid4().hex[:6]}@gmail.com",
        "network": "TRC20",
    }
    r = session.post(f"{BASE}/api/crypto/orders/create", json=payload)
    assert r.status_code == 200, f"order create failed {r.status_code} {r.text}"
    o = r.json()
    return o


def test_order_create_shape(created_order):
    o = created_order
    assert o["id"].startswith("ORD-")
    assert o["plan_id"] == "trial"
    assert o["plan_name"] == "Trial"
    assert o["status"] == "pending"
    assert o["wallet_address"] == WALLET_ENV
    assert o["amount_usdt"] == 3.0
    assert o["network"] == "TRC20"
    assert o["expires_at"]
    assert o["tx_id"] is None
    assert o["license_key"] is None


def test_order_create_invalid_plan(session):
    r = session.post(f"{BASE}/api/crypto/orders/create", json={
        "plan_id": "nonexistent-plan",
        "customer_name": "TEST Bad",
        "customer_email": "us9661626+test@gmail.com",
    })
    assert r.status_code == 404


def test_get_order_status(session, created_order):
    r = session.get(f"{BASE}/api/crypto/orders/{created_order['id']}")
    assert r.status_code == 200
    o = r.json()
    assert o["id"] == created_order["id"]
    assert o["status"] in ("pending", "submitted", "expired")


def test_get_order_not_found(session):
    r = session.get(f"{BASE}/api/crypto/orders/ORD-DOES-NOT-EXIST")
    assert r.status_code == 404


# ─── TxID submit ───────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def submitted_order(session, created_order):
    tx = "TEST-TX-" + uuid.uuid4().hex[:16].upper()
    r = session.post(
        f"{BASE}/api/crypto/orders/{created_order['id']}/submit-txid",
        json={"tx_id": tx}
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    o = r.json()
    assert o["status"] == "submitted"
    assert o["tx_id"] == tx
    assert o["submitted_at"]
    return o


def test_submit_txid_short_rejected(session, created_order):
    # min_length=10 — pydantic should return 422
    r = session.post(
        f"{BASE}/api/crypto/orders/{created_order['id']}/submit-txid",
        json={"tx_id": "abc"}
    )
    assert r.status_code == 422


def test_submit_txid_duplicate_rejected(session, submitted_order):
    # Create a second order and try to submit the same TxID
    r = session.post(f"{BASE}/api/crypto/orders/create", json={
        "plan_id": "trial",
        "customer_name": "TEST Dup",
        "customer_email": f"us9661626+dup{uuid.uuid4().hex[:4]}@gmail.com",
    })
    assert r.status_code == 200
    o2 = r.json()
    r2 = session.post(
        f"{BASE}/api/crypto/orders/{o2['id']}/submit-txid",
        json={"tx_id": submitted_order["tx_id"]}
    )
    assert r2.status_code == 409, f"Expected 409 got {r2.status_code} {r2.text}"


# ─── Admin: list / approve / reject ───────────────────────────────────
def test_admin_list_orders_requires_auth(session):
    r = session.get(f"{BASE}/api/admin/crypto/orders?status=submitted")
    assert r.status_code in (401, 403)


def test_admin_list_submitted(admin_session, submitted_order):
    r = admin_session.get(f"{BASE}/api/admin/crypto/orders?status=submitted")
    assert r.status_code == 200
    data = r.json()
    ids = {o["id"] for o in data.get("orders", [])}
    assert submitted_order["id"] in ids


def test_admin_approve_issues_license(admin_session, submitted_order):
    r = admin_session.post(
        f"{BASE}/api/admin/crypto/orders/{submitted_order['id']}/approve",
        json={}
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    o = r.json()
    assert o["status"] == "approved"
    assert o["license_key"], "license_key missing on approved order"
    assert LICENSE_KEY_RE.match(o["license_key"]), f"License key format invalid: {o['license_key']}"
    assert o["approved_at"]


def test_admin_approve_idempotent_rejects_double(admin_session, submitted_order):
    # already approved
    r = admin_session.post(
        f"{BASE}/api/admin/crypto/orders/{submitted_order['id']}/approve",
        json={}
    )
    assert r.status_code == 400


def test_admin_reject_with_reason(session, admin_session):
    # create + submit a new order
    r = session.post(f"{BASE}/api/crypto/orders/create", json={
        "plan_id": "starter",
        "customer_name": "TEST Reject",
        "customer_email": f"us9661626+rej{uuid.uuid4().hex[:4]}@gmail.com",
    })
    assert r.status_code == 200
    oid = r.json()["id"]
    tx = "TEST-REJ-" + uuid.uuid4().hex[:16].upper()
    rs = session.post(f"{BASE}/api/crypto/orders/{oid}/submit-txid", json={"tx_id": tx})
    assert rs.status_code == 200

    rr = admin_session.post(
        f"{BASE}/api/admin/crypto/orders/{oid}/reject",
        json={"reason": "TEST: payment not received on-chain"}
    )
    assert rr.status_code == 200, f"{rr.status_code} {rr.text}"
    o = rr.json()
    assert o["status"] == "rejected"
    assert o["reject_reason"] == "TEST: payment not received on-chain"
    assert o["rejected_at"]


def test_admin_can_filter_by_approved(admin_session, submitted_order):
    r = admin_session.get(f"{BASE}/api/admin/crypto/orders?status=approved")
    assert r.status_code == 200
    ids = {o["id"] for o in r.json().get("orders", [])}
    assert submitted_order["id"] in ids
