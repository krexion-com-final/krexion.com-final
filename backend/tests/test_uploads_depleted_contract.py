"""
Iteration-2 tests for the per-row consume + DEPLETED batch-survival
contract. Complements `/app/tests/test_uploads_per_row_consume.py`
(which is the pre-existing reference test) by adding API-contract,
schema, idempotency, multipart, and legacy-doc edge cases.

Focus:
  - Upload creation endpoints expose the new schema fields
    (original_item_count / consumed_count / available_count /
    depleted / depleted_at).
  - GET /api/uploads list reflects the same fields.
  - JSON automation templates are NEVER mutated by _consume_uploads
    even after multiple invocations.
  - Idempotency: consuming the same proxy lines twice does not
    double-count consumed_count.
  - Multipart Excel upload to /api/uploads/data-file populates the
    new fields and counts rows correctly.
  - Static data_file → consume all rows → on-disk file deleted but
    DB entry survives with depleted=True.
  - Legacy docs missing `original_item_count` get backfilled in the
    response by `_upload_doc_to_response`.
"""
import io
import os
import sys
import time
import uuid
import asyncio
from pathlib import Path

import httpx
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@realflow.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Ensure backend importable for direct _consume_uploads invocation
sys.path.insert(0, "/app/backend")


# ─────────────────── shared fixtures ───────────────────
@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(
        f"{BASE_URL}/api/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def test_user(admin_token):
    """Provision a fresh test user with the right feature flags."""
    email = f"TEST_depletedctr_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    password = "TestPass1234!"
    # Register
    r = httpx.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": "Depleted Tester"},
        timeout=30,
    )
    assert r.status_code in (200, 201, 400), r.text
    # Approve + grant features
    rh = {"Authorization": f"Bearer {admin_token}"}
    users = httpx.get(f"{BASE_URL}/api/admin/users", headers=rh, timeout=30).json()
    target = next((u for u in users if u["email"] == email), None)
    assert target, "registered user not found"
    uid = target["id"]
    r = httpx.put(
        f"{BASE_URL}/api/admin/users/{uid}",
        headers=rh,
        json={
            "status": "active",
            "features": {"real_user_traffic": True, "form_filler": True},
        },
        timeout=30,
    )
    assert r.status_code in (200, 204), r.text
    # Login as user
    r = httpx.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return {"id": uid, "email": email, "token": r.json()["access_token"]}


@pytest.fixture
def auth_headers(test_user):
    return {"Authorization": f"Bearer {test_user['token']}"}


def _consume_sync(user_id, upload_ids, used_proxy_raws=None, used_ua_strings=None):
    """Run the live _consume_uploads helper (production code path)."""
    from server import _consume_uploads
    asyncio.get_event_loop().run_until_complete(
        _consume_uploads(
            user_id,
            upload_ids,
            used_proxy_raws=used_proxy_raws or [],
            used_ua_strings=used_ua_strings or [],
        )
    )


def _list(type_, headers):
    r = httpx.get(f"{BASE_URL}/api/uploads?type={type_}", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────── 1. proxy upload schema ───────────────────
def test_proxy_upload_response_schema(auth_headers):
    """POST /api/uploads/proxies — verify all new fields populated."""
    raw = "\n".join([f"u{i}:p@10.0.0.{i}:8080" for i in range(1, 4)])
    r = httpx.post(
        f"{BASE_URL}/api/uploads/proxies",
        headers=auth_headers,
        data={"name": "TEST_proxy_schema", "country_tag": "US", "proxies": raw},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    for k in (
        "id", "user_id", "type", "name", "item_count",
        "original_item_count", "consumed_count", "available_count",
        "depleted", "depleted_at", "created_at",
    ):
        assert k in d, f"missing key {k} in response: {d}"
    assert d["type"] == "proxies"
    assert d["item_count"] == 3
    assert d["original_item_count"] == 3
    assert d["consumed_count"] == 0
    assert d["available_count"] == 3
    assert d["depleted"] is False
    assert d["depleted_at"] is None


# ─────────────────── 2. UA upload schema ───────────────────
def test_user_agents_upload_response_schema(auth_headers):
    raw = "\n".join([f"Mozilla/5.0 SchemaUA-{i}" for i in range(1, 4)])
    r = httpx.post(
        f"{BASE_URL}/api/uploads/user-agents",
        headers=auth_headers,
        data={"name": "TEST_ua_schema", "os_tag": "android", "user_agents": raw},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["type"] == "user_agents"
    assert d["item_count"] == 3
    assert d["original_item_count"] == 3
    assert d["consumed_count"] == 0
    assert d["available_count"] == 3
    assert d["depleted"] is False


# ─────────────────── 3. multipart Excel data-file upload ───────────────────
def test_data_file_multipart_upload_schema(auth_headers, tmp_path):
    """Upload a real .xlsx via multipart, expect item_count=row_count + new fields."""
    pd = pytest.importorskip("pandas")
    rows = [
        {"first_name": "A", "last_name": "X", "email": "a@x.com"},
        {"first_name": "B", "last_name": "Y", "email": "b@y.com"},
        {"first_name": "C", "last_name": "Z", "email": "c@z.com"},
        {"first_name": "D", "last_name": "W", "email": "d@w.com"},
    ]
    xlsx_path = tmp_path / "leads.xlsx"
    pd.DataFrame(rows).to_excel(xlsx_path, index=False)
    with open(xlsx_path, "rb") as f:
        files = {"file": ("leads.xlsx", f.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = httpx.post(
        f"{BASE_URL}/api/uploads/data-file",
        headers=auth_headers,
        data={"name": "TEST_data_schema"},
        files=files,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["type"] == "data_file"
    assert d["item_count"] == 4
    assert d["original_item_count"] == 4
    assert d["consumed_count"] == 0
    assert d["available_count"] == 4
    assert d["depleted"] is False
    assert d["file_name"] == "leads.xlsx"


# ─────────────────── 4. automation_json never depleted ───────────────────
def test_automation_json_response_and_immune_to_consume(test_user, auth_headers):
    body = '[{"action":"wait","ms":50},{"action":"click","selector":"#a"}]'
    r = httpx.post(
        f"{BASE_URL}/api/uploads/automation-json",
        headers=auth_headers,
        data={"name": "TEST_json_immune", "automation_json": body},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    json_id = d["id"]
    # Schema fields (original_item_count is computed from item_count when missing)
    assert d["type"] == "automation_json"
    assert d["item_count"] == 2
    assert d["original_item_count"] == 2
    assert d["consumed_count"] == 0
    assert d["depleted"] is False
    # Now invoke _consume_uploads multiple times with the JSON id —
    # this MUST be a no-op for automation_json regardless.
    for _ in range(3):
        _consume_sync(
            test_user["id"], [json_id],
            used_proxy_raws=["irrelevant"],
            used_ua_strings=["irrelevant-ua"],
        )
    items = _list("automation_json", auth_headers)
    survivor = next((x for x in items if x["id"] == json_id), None)
    assert survivor is not None, "JSON template was deleted!"
    assert survivor["item_count"] == 2, "JSON item_count mutated!"
    assert survivor["depleted"] is False, "JSON wrongly marked depleted!"
    assert survivor["consumed_count"] == 0


# ─────────────────── 5. GET /api/uploads list schema ───────────────────
def test_list_uploads_exposes_new_fields(auth_headers):
    """Hit /api/uploads (no filter) and assert every doc carries the new fields."""
    r = httpx.get(f"{BASE_URL}/api/uploads", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list)
    assert len(items) > 0, "expected at least the uploads created in this run"
    required = {"original_item_count", "consumed_count", "available_count", "depleted", "depleted_at"}
    for it in items:
        missing = required - set(it.keys())
        assert not missing, f"upload {it.get('id')} type={it.get('type')} missing {missing}"
        # available_count must equal item_count for non-gsheet uploads
        if not it.get("gsheet_url"):
            assert it["available_count"] == it["item_count"]


# ─────────────────── 6. idempotency on proxy consume ───────────────────
def test_consume_proxies_is_idempotent(test_user, auth_headers):
    """Consuming the same proxy raws twice must not double-decrement."""
    raw_lines = [f"id{i}:pw@5.5.5.{i}:8080" for i in range(1, 6)]  # 5 proxies
    r = httpx.post(
        f"{BASE_URL}/api/uploads/proxies",
        headers=auth_headers,
        data={"name": "TEST_idempo_proxies", "country_tag": "US",
              "proxies": "\n".join(raw_lines)},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    # First consume — 3 lines
    _consume_sync(test_user["id"], [pid], used_proxy_raws=raw_lines[:3])
    d1 = next(x for x in _list("proxies", auth_headers) if x["id"] == pid)
    assert d1["item_count"] == 2
    assert d1["consumed_count"] == 3
    assert d1["depleted"] is False
    # Second consume — same 3 lines (already gone). consumed_count must NOT
    # increase, item_count must NOT decrease.
    _consume_sync(test_user["id"], [pid], used_proxy_raws=raw_lines[:3])
    d2 = next(x for x in _list("proxies", auth_headers) if x["id"] == pid)
    assert d2["item_count"] == 2, "item_count drifted on idempotent re-consume"
    assert d2["consumed_count"] == 3, f"consumed_count double-counted: {d2['consumed_count']}"
    assert d2["depleted"] is False


# ─────────────────── 7. data_file consume-all → file deleted, DB survives ───
def test_data_file_full_consume_deletes_file_keeps_db(test_user, auth_headers, tmp_path):
    """Static data_file → all rows consumed → on-disk file removed but DB
    entry preserved with depleted=True and file_path=None.
    Uses the production _consume_uploads via a 0-row pending file."""
    pd = pytest.importorskip("pandas")
    rows = [{"email": f"r{i}@t.com", "first_name": f"F{i}"} for i in range(1, 4)]
    xlsx_path = tmp_path / "leads_full.xlsx"
    pd.DataFrame(rows).to_excel(xlsx_path, index=False)
    with open(xlsx_path, "rb") as f:
        files = {"file": ("leads_full.xlsx", f.read(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = httpx.post(
        f"{BASE_URL}/api/uploads/data-file",
        headers=auth_headers,
        data={"name": "TEST_data_fullconsume"},
        files=files,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    did = r.json()["id"]

    # Locate stored file on disk via the saved doc
    from server import get_user_db  # noqa: E402
    user_db = get_user_db(test_user["id"])
    loop = asyncio.get_event_loop()
    doc = loop.run_until_complete(
        user_db["uploaded_resources"].find_one({"id": did}, {"_id": 0})
    )
    fp = doc["file_path"]
    assert Path(fp).exists(), "uploaded data file missing on disk"

    # Build empty pending leads file → signals "all rows consumed"
    empty_path = tmp_path / "pending_empty.xlsx"
    pd.DataFrame(columns=["email", "first_name"]).to_excel(empty_path, index=False)

    from server import _consume_uploads
    loop.run_until_complete(_consume_uploads(
        test_user["id"], [did],
        pending_leads_path=str(empty_path),
    ))

    # DB entry must still exist
    items = _list("data_file", auth_headers)
    survivor = next((x for x in items if x["id"] == did), None)
    assert survivor is not None, "data_file DB entry was deleted!"
    assert survivor["item_count"] == 0
    assert survivor["depleted"] is True
    assert survivor["depleted_at"]
    assert survivor["consumed_count"] == 3
    # On-disk file must be removed to free space
    assert not Path(fp).exists(), "on-disk file should have been deleted"


# ─────────────────── 8. legacy doc backfill ───────────────────
def test_legacy_doc_without_original_item_count(test_user, auth_headers):
    """Insert a legacy upload doc directly (mimicking pre-feature data) — no
    `original_item_count`, `consumed_count`, or `depleted` keys — and assert
    the list endpoint synthesises them from item_count."""
    from server import get_user_db  # noqa: E402
    user_db = get_user_db(test_user["id"])
    legacy_id = str(uuid.uuid4())
    legacy_doc = {
        "id": legacy_id,
        "user_id": test_user["id"],
        "type": "user_agents",
        "name": "TEST_legacy_no_ocount",
        "items": ["UA-A", "UA-B"],
        "item_count": 2,
        "file_name": None,
        "created_at": "2024-01-01T00:00:00+00:00",
        # NOTE: no original_item_count / consumed_count / depleted
    }
    asyncio.get_event_loop().run_until_complete(
        user_db["uploaded_resources"].insert_one(legacy_doc)
    )
    items = _list("user_agents", auth_headers)
    found = next((x for x in items if x["id"] == legacy_id), None)
    assert found is not None
    assert found["item_count"] == 2
    assert found["original_item_count"] == 2  # backfilled from item_count
    assert found["consumed_count"] == 0
    assert found["available_count"] == 2
    assert found["depleted"] is False
    assert found["depleted_at"] is None


# ─────────────────── 9. UA depleted_at format check ───────────────────
def test_depleted_at_iso_timestamp(test_user, auth_headers):
    raw = "Mozilla/5.0 IsoUA-only"
    r = httpx.post(
        f"{BASE_URL}/api/uploads/user-agents",
        headers=auth_headers,
        data={"name": "TEST_iso_ua", "os_tag": "android", "user_agents": raw},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    _consume_sync(test_user["id"], [uid], used_ua_strings=[raw])
    items = _list("user_agents", auth_headers)
    d = next(x for x in items if x["id"] == uid)
    assert d["depleted"] is True
    # Should look like an ISO timestamp
    ts = d["depleted_at"]
    assert isinstance(ts, str) and "T" in ts and len(ts) >= 19, ts
