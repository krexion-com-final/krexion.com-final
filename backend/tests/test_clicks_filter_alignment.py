"""
Regression test for 2026-06 clicks count/list/export filter alignment.

Bug:
  /clicks (list)    + frontend "This Month" → sent start_date=startOfMonth(now)
                                              → calendar month
  /clicks/count     + frontend "This Month" → sent filter_type=month
                                              → backend = last 30 days
  /clicks/export    + frontend "This Month" → sent filter_type=month
                                              → backend = last 30 days

  Result: top stats showed 8118 (last 30 days), table showed 0
  (current calendar month only). Export had similar mismatch.

Fix:
  Both /clicks/count and /clicks/export now accept explicit
  start_date + end_date that win over filter_type. Frontend now sends
  the same date range it sends to the list endpoint.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
import pytest
import jwt


def _backend_url() -> str:
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", ".env")
    env_path = os.path.abspath(env_path)
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL missing from frontend/.env")


BASE = _backend_url()
API = f"{BASE}/api"


@pytest.fixture
def setup_clicks():
    """Insert 3 clicks into a fresh tenant DB:
      - one 60 days ago (outside calendar month + outside 30-day window)
      - one 20 days ago (inside 30-day window, OUTSIDE current calendar month if today < 21)
      - one today (inside both windows)
    Returns (user_id, token, link_id, expected_counts_dict)."""
    import asyncio

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v)

    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    main_db = client[os.environ["DB_NAME"]]

    uid = f"clicks-test-{uuid.uuid4().hex[:8]}"
    email = f"{uid}@krexion-clicks-test.local"
    link_id = f"link-{uuid.uuid4().hex[:8]}"
    short_code = f"sc{uuid.uuid4().hex[:6]}"
    tenant_db_name = f"krexion_user_{uid.replace('-', '_')[:20]}"

    now = datetime.now(timezone.utc)
    far_past = now - timedelta(days=60)
    middle = now - timedelta(days=20)
    today = now

    async def _setup():
        # User
        await main_db.users.delete_many({"email": email})
        await main_db.users.insert_one({
            "id": uid,
            "email": email,
            "role": "user",
            "status": "active",
            "is_sub_user": False,
            "features": {"clicks": True, "real_user_traffic": True},
            "created_at": now.isoformat(),
        })
        # Link owned by user
        await main_db.links.delete_many({"id": link_id})
        await main_db.links.insert_one({
            "id": link_id,
            "user_id": uid,
            "short_code": short_code,
            "name": "Clicks Filter Test Link",
            "url": "https://example.com",
            "created_at": now.isoformat(),
        })
        # Clicks in user's tenant DB
        tenant_db = client[tenant_db_name]
        await tenant_db.clicks.delete_many({"link_id": link_id})
        for ts, ip in [(far_past, "1.1.1.1"), (middle, "2.2.2.2"), (today, "3.3.3.3")]:
            await tenant_db.clicks.insert_one({
                "id": str(uuid.uuid4()),
                "click_id": str(uuid.uuid4()),
                "link_id": link_id,
                "user_id": uid,
                "ip_address": ip,
                "ipv4": ip,
                "created_at": ts.isoformat(),
                "country": "US",
                "browser": "Chrome",
            })
        return tenant_db_name

    asyncio.run(_setup())

    secret = os.environ.get("JWT_SECRET_KEY") or "your-secret-key-change-in-production"
    token = jwt.encode({"sub": email, "user_id": uid}, secret, algorithm="HS256")

    yield uid, token, link_id, far_past, middle, today, tenant_db_name

    # Teardown — fresh client to avoid loop binding
    async def _cleanup():
        client2 = AsyncIOMotorClient(os.environ["MONGO_URL"])
        await client2[os.environ["DB_NAME"]].users.delete_many({"email": email})
        await client2[os.environ["DB_NAME"]].links.delete_many({"id": link_id})
        await client2[tenant_db_name].clicks.delete_many({"link_id": link_id})
        client2.close()

    asyncio.run(_cleanup())


def test_count_with_explicit_date_range_overrides_filter_type(setup_clicks):
    """When the frontend sends explicit start_date/end_date, the count
    endpoint must use THAT window — not the filter_type fallback.

    We send a tight window covering only the last 10 days. Inside this
    window only the "today" click should be counted (1), even though
    `filter_type=month` would return 2 (last 30 days = today + middle).
    """
    uid, token, link_id, far_past, middle, today, _ = setup_clicks

    start = (today - timedelta(days=10)).isoformat()
    end = today.isoformat()

    r = httpx.get(
        f"{API}/clicks/count",
        params={
            "start_date": start,
            "end_date": end,
            "filter_type": "month",   # would return 2 if used
            "link_id": link_id,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1, (
        f"explicit 10-day window should override filter_type=month "
        f"(should count today only). Got {body}"
    )


def test_count_falls_back_to_filter_type_when_no_dates(setup_clicks):
    """Backwards-compat — when no start_date/end_date is sent, the legacy
    filter_type=month (last 30 days) semantics still works. Should
    include both `today` and `middle` (20 days ago), but NOT `far_past`
    (60 days ago)."""
    uid, token, link_id, far_past, middle, today, _ = setup_clicks

    r = httpx.get(
        f"{API}/clicks/count",
        params={"filter_type": "month", "link_id": link_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2, (
        f"filter_type=month (last 30d) should include today + middle "
        f"= 2 clicks. Got {body}"
    )


def test_export_with_explicit_date_range_matches_list(setup_clicks):
    """The CSV export endpoint must honour explicit start/end the same
    way the list endpoint does — so the CSV file content matches what
    the user sees in the on-screen table."""
    uid, token, link_id, far_past, middle, today, _ = setup_clicks

    start = (today - timedelta(days=10)).isoformat()
    end = today.isoformat()

    r = httpx.get(
        f"{API}/clicks/export",
        params={
            "start_date": start,
            "end_date": end,
            "filter_type": "month",
            "link_id": link_id,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1, (
        f"explicit window should give 1 click (today only). "
        f"Got {body['total']}"
    )
    assert len(body["clicks"]) == 1
