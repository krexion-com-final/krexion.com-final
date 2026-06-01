"""
Regression test for 2026-06 strict-mode hardening.

Bug fixed:
  When STRICT_CLOUD_HEAVY_BLOCK=true and the customer's desktop app
  was heart-beating (PC online), the previous gate (`require_local_mode`)
  ALLOWED inline VPS execution of heavy endpoints (RUT, Form Filler,
  Visual Recorder). Result: the customer's "big job" loaded the VPS
  with 45+ Chromium browsers — exactly what strict mode was meant to
  prevent.

Fix:
  `require_local_mode` now refuses on cloud + strict, regardless of PC
  heartbeat status. The 503 detail carries `actionable_hint=use_desktop_app`
  when the PC IS online so the frontend modal copy is correct.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest


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
def db():
    from motor.motor_asyncio import AsyncIOMotorClient

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v)

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


def _run(coro):
    import asyncio
    return asyncio.run(coro)


# ── Tests ─────────────────────────────────────────────────────────────
def test_rut_job_creation_refuses_without_jwt():
    """Sanity check — the gate is mounted on the endpoint."""
    r = httpx.post(f"{API}/real-user-traffic/jobs", timeout=10.0)
    # Without auth, FastAPI returns 401 BEFORE the cloud gate runs.
    # We just want to confirm the route exists (not 404).
    assert r.status_code in (401, 422), f"unexpected: {r.status_code} {r.text[:200]}"


def test_form_filler_job_creation_refuses_without_jwt():
    """Sanity — form filler endpoint also exists + is auth-gated."""
    r = httpx.post(f"{API}/form-filler/jobs", timeout=10.0)
    assert r.status_code in (401, 422), f"unexpected: {r.status_code} {r.text[:200]}"


def test_visual_recorder_start_refuses_without_jwt():
    """Sanity — visual recorder endpoint exists + is auth-gated."""
    r = httpx.post(f"{API}/visual-recorder/start", json={}, timeout=10.0)
    assert r.status_code in (401, 422), f"unexpected: {r.status_code} {r.text[:200]}"


def test_strict_mode_blocks_even_when_pc_online(db):
    """The CRITICAL regression test:
      When STRICT_CLOUD_HEAVY_BLOCK=true AND the customer's PC heartbeat
      says ONLINE, the gate must still refuse inline cloud execution.
      Previously it allowed — that's exactly what caused the user's VPS
      overload incident.

    We register an active heartbeat for a fake user, then call a
    require_local_mode-gated endpoint. Expectation: 503 with
    actionable_hint=use_desktop_app.
    """
    import jwt

    async def _setup():
        # Create a test user + write a fresh heartbeat so the bridge
        # module sees them as online. We do this directly in Mongo so
        # the test doesn't depend on the full registration flow.
        uid = f"test-strict-{uuid.uuid4().hex[:8]}"
        email = f"{uid}@krexion-strict-test.local"
        await db.users.delete_many({"email": email})
        await db.local_pc_heartbeats.delete_many({"user_id": uid})
        await db.users.insert_one({
            "id": uid,
            "email": email,
            "name": "Strict Test",
            "role": "user",
            "status": "active",
            "is_sub_user": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            # Minimum features — RUT must be allowed by feature gate so we
            # exercise the strict-mode gate specifically, not the feature
            # gate.
            "features": {"real_user_traffic": True},
        })
        # Fresh heartbeat → PC counts as ONLINE.
        # NOTE: bridge_module reads collection `sync_heartbeats` and
        # parses `last_seen` via fromisoformat — so we MUST store an
        # ISO-8601 string, not a raw datetime.
        await db.sync_heartbeats.delete_many({"user_id": uid})
        await db.sync_heartbeats.insert_one({
            "user_id": uid,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "ram_gb": 32,
            "cpu_cores": 8,
            "platform": "Windows",
            "version": "1.1.20",
            "hostname": "strict-test-host",
        })
        return uid, email

    uid, email = _run(_setup())

    # Build a JWT the way the backend does — see SECRET_KEY/ALGORITHM.
    # The backend reads JWT_SECRET_KEY from env.
    secret = os.environ.get("JWT_SECRET_KEY") or "your-secret-key-change-in-production"
    token = jwt.encode(
        {"sub": email, "user_id": uid},
        secret,
        algorithm="HS256",
    )

    cleanup_done = {"v": False}
    async def _cleanup():
        try:
            # Use a FRESH motor client — the fixture's client is bound to
            # the asyncio event loop that `_run(_setup())` already closed.
            from motor.motor_asyncio import AsyncIOMotorClient
            c2 = AsyncIOMotorClient(os.environ["MONGO_URL"])
            d2 = c2[os.environ["DB_NAME"]]
            await d2.users.delete_many({"email": email})
            await d2.sync_heartbeats.delete_many({"user_id": uid})
            c2.close()
        finally:
            cleanup_done["v"] = True

    try:
        # The form-filler endpoint needs multipart — but we just want to
        # exercise the gate, which runs BEFORE the form validation. The
        # 503 from the gate happens before any 400/422 form validation.
        r = httpx.post(
            f"{API}/form-filler/jobs",
            headers={"Authorization": f"Bearer {token}"},
            data={"count": "1"},
            timeout=15.0,
        )
        # Expectation: 503 with the structured detail.
        assert r.status_code == 503, (
            f"expected 503 (gate refused), got {r.status_code}: {r.text[:300]}"
        )
        body = r.json()
        detail = body.get("detail", {})
        assert detail.get("code") == "local_pc_offline", detail
        assert detail.get("error") == "local_pc_required", detail
        # 2026-06: PC is online so hint should be use_desktop_app
        assert detail.get("actionable_hint") == "use_desktop_app", (
            f"expected use_desktop_app for online PC, got {detail.get('actionable_hint')}"
        )
        # The status payload must still report online (so the modal can
        # tell the customer "your PC is on, switch to the desktop app").
        assert detail.get("local_status", {}).get("online") is True, detail
    finally:
        if not cleanup_done["v"]:
            _run(_cleanup())
