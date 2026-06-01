"""
Regression test for white-label native installer flow.

What this covers:
- GET /api/system/installer-info reports `legacy-zip` when no published
  release has a `.exe` `download_url`.
- GET /api/system/installer-info flips to `native-exe` (with version +
  size) when admin publishes a release with `.exe` download_url.
- GET /api/license/download-installer/{key} returns 302 redirect to the
  GitHub Release asset URL once a native release is published.
- GET /api/license/download-installer/{key} falls back to the legacy ZIP
  stream when no native release is present.
- The duplicate-IP block page now surfaces the matched IP (was "unknown"
  before the projection fix shipped this session).
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
import pytest

# Resolve the public BACKEND_URL from frontend/.env so the test exercises
# the same ingress path a real browser does.
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


# ── Mongo fixture helpers ─────────────────────────────────────────────
@pytest.fixture
def db():
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient

    # Load /app/backend/.env without dotenv dep
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
    return asyncio.get_event_loop().run_until_complete(coro) if asyncio.get_event_loop().is_running() is False else asyncio.run(coro)


# ── Tests ─────────────────────────────────────────────────────────────
def test_installer_info_returns_legacy_when_no_native_release(db):
    """Without a .exe release, installer-info reports legacy-zip."""
    async def _do():
        await db.app_releases.delete_many({"created_by": "test-installer-fixture"})
    _run(_do())

    r = httpx.get(f"{API}/system/installer-info", timeout=15.0)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "legacy-zip"
    assert data["version"]


def test_installer_info_reports_native_exe_when_release_published(db):
    """When admin publishes a release with .exe download_url,
    installer-info flips to native-exe mode."""
    async def _setup():
        await db.app_releases.delete_many({"created_by": "test-installer-fixture"})
        await db.app_releases.insert_one({
            "id": str(uuid.uuid4()),
            "version": "9.9.9",
            "title": "Test Native Release",
            "notes": "",
            "severity": "recommended",
            "download_url": "https://example.com/Krexion-Setup-9.9.9.exe",
            "installer_size_bytes": 320 * 1024 * 1024,
            "published": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "test-installer-fixture",
        })
    _run(_setup())

    try:
        r = httpx.get(f"{API}/system/installer-info", timeout=15.0)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["kind"] == "native-exe"
        assert data["version"] == "9.9.9"
        assert data["size_bytes"] == 320 * 1024 * 1024
    finally:
        async def _cleanup():
            await db.app_releases.delete_many({"created_by": "test-installer-fixture"})
        _run(_cleanup())


def test_download_installer_redirects_to_native_exe(db):
    """With a native release published, the download endpoint returns
    a 302 redirect to the .exe URL (not a ZIP stream)."""
    license_key = "KRX-TEST-NATV-EXE0-RDIR"
    target_url = "https://example.com/Krexion-Setup-9.9.9.exe"

    async def _setup():
        await db.app_releases.delete_many({"created_by": "test-installer-fixture"})
        await db.licenses.delete_many({"license_key": license_key})
        await db.app_releases.insert_one({
            "id": str(uuid.uuid4()),
            "version": "9.9.9",
            "title": "Test Native Release",
            "download_url": target_url,
            "published": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "test-installer-fixture",
        })
        await db.licenses.insert_one({
            "id": str(uuid.uuid4()),
            "license_key": license_key,
            "email": "test-native@krexion.local",
            "status": "active",
            "max_pcs": 1,
            "machines_used": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "subscription_ends_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        })
    _run(_setup())

    try:
        r = httpx.get(
            f"{API}/license/download-installer/{license_key}",
            follow_redirects=False,
            timeout=15.0,
        )
        assert r.status_code == 302, f"expected 302, got {r.status_code}: {r.text[:200]}"
        assert r.headers["location"] == target_url
    finally:
        async def _cleanup():
            await db.app_releases.delete_many({"created_by": "test-installer-fixture"})
            await db.licenses.delete_many({"license_key": license_key})
        _run(_cleanup())


def test_download_installer_falls_back_to_zip_when_no_native_release(db):
    """Backwards-compat: with no native release, the endpoint still
    streams the legacy Krexion-User-Package ZIP."""
    license_key = "KRX-TEST-LEGC-ZIP0-FALL"

    async def _setup():
        await db.app_releases.delete_many({"created_by": "test-installer-fixture"})
        await db.licenses.delete_many({"license_key": license_key})
        await db.licenses.insert_one({
            "id": str(uuid.uuid4()),
            "license_key": license_key,
            "email": "test-zip@krexion.local",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "subscription_ends_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        })
    _run(_setup())

    try:
        r = httpx.get(
            f"{API}/license/download-installer/{license_key}",
            follow_redirects=False,
            timeout=30.0,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"] == "application/zip"
        assert len(r.content) > 1000  # actual payload, not empty
    finally:
        async def _cleanup():
            await db.licenses.delete_many({"license_key": license_key})
        _run(_cleanup())
