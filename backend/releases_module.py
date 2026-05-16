"""
Krexion — App Releases & Auto-Update Module
============================================
Admin publishes releases at https://krexion.com → customer's local install
polls for updates → shows a "New version available" banner → one-click apply.

Endpoints:
  Admin (cloud, JWT-required):
    POST   /api/admin/releases                — create a release
    GET    /api/admin/releases                — list all releases
    PATCH  /api/admin/releases/{id}           — edit notes / severity
    DELETE /api/admin/releases/{id}           — remove a release

  Customer (license-auth):
    GET    /api/system/latest-version         — newest published release
    GET    /api/system/version                — current local version (no-auth)

  Customer (local-only, JWT-required):
    POST   /api/system/install-update         — write flag file so the host
                                                updater script picks it up

A `VERSION` file at /app/backend/VERSION holds the running version on each
install (cloud OR local). Updater compares semver strings.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

logger = logging.getLogger(__name__)
releases_router = APIRouter(tags=["releases"])

# Bound from server.py
_db: Any = None
_get_current_admin: Any = None
_get_current_user: Any = None

VERSION_FILE = Path(__file__).parent / "VERSION"
UPDATE_FLAG_FILE = Path("/data/update_requested.flag")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[.-].+)?$")


def _bind(*, main_db, get_current_admin, get_current_user) -> None:
    global _db, _get_current_admin, _get_current_user
    _db = main_db
    _get_current_admin = get_current_admin
    _get_current_user = get_current_user


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_version() -> str:
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    except Exception:  # noqa: BLE001
        pass
    return "0.0.0"


def _parse(v: str) -> tuple:
    m = SEMVER_RE.match((v or "").strip())
    if not m:
        return (0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def is_newer(remote: str, local: str) -> bool:
    return _parse(remote) > _parse(local)


# ─── License → user resolver (shared with sync module) ────────────────
async def _validate_license(license_key: Optional[str]):
    if not license_key:
        raise HTTPException(status_code=401, detail="Missing X-Krexion-License header")
    lic = await _db.licenses.find_one({"license_key": license_key.strip()}, {"_id": 0})
    if not lic:
        raise HTTPException(status_code=401, detail="Invalid license key")
    if lic.get("status") and lic["status"] not in ("active", "issued"):
        raise HTTPException(status_code=403, detail=f"License is {lic['status']}")
    return lic


# ─── Admin endpoints ──────────────────────────────────────────────────
@releases_router.post("/api/admin/releases")
async def create_release(body: dict, admin: dict = Depends(lambda: None)):
    # Lazy admin check
    if _get_current_admin is None:
        raise HTTPException(503, "Admin auth not configured")
    # Actually we'll re-implement clean — use real admin dep
    raise HTTPException(500, "wired below")


# We need real admin dependency injection - we'll register handlers
# dynamically after _bind() is called from server.py. To keep it simple,
# define handlers that accept `admin` via the late-bound dependency.

def _build_admin_endpoints(get_admin_dep):
    """Register the actual admin endpoints with the correct admin dep."""
    router = APIRouter(tags=["releases-admin"])

    @router.post("/api/admin/releases")
    async def create(body: dict, admin: dict = Depends(get_admin_dep)):
        ver = (body.get("version") or "").strip()
        if not SEMVER_RE.match(ver):
            raise HTTPException(400, "version must be semver like 1.2.3")
        existing = await _db.app_releases.find_one({"version": ver})
        if existing:
            raise HTTPException(409, f"Version {ver} already exists")
        doc = {
            "id": str(uuid.uuid4()),
            "version": ver,
            "title": body.get("title", f"Krexion {ver}"),
            "notes": body.get("notes", ""),
            "severity": body.get("severity", "recommended"),  # info|recommended|critical
            "download_url": body.get("download_url", ""),
            "min_required_version": body.get("min_required_version", ""),
            "published": bool(body.get("published", True)),
            "created_at": _now_iso(),
            "created_by": admin.get("email") or admin.get("id"),
        }
        await _db.app_releases.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/api/admin/releases")
    async def list_releases(admin: dict = Depends(get_admin_dep)):
        items = await _db.app_releases.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"releases": items, "current_version": current_version()}

    @router.patch("/api/admin/releases/{rid}")
    async def patch_release(rid: str, body: dict, admin: dict = Depends(get_admin_dep)):
        allowed = {"title", "notes", "severity", "download_url", "published", "min_required_version"}
        upd = {k: v for k, v in body.items() if k in allowed}
        if not upd:
            raise HTTPException(400, "No editable fields supplied")
        upd["updated_at"] = _now_iso()
        r = await _db.app_releases.update_one({"id": rid}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(404, "Release not found")
        return {"updated": True}

    @router.delete("/api/admin/releases/{rid}")
    async def delete_release(rid: str, admin: dict = Depends(get_admin_dep)):
        r = await _db.app_releases.delete_one({"id": rid})
        if r.deleted_count == 0:
            raise HTTPException(404, "Release not found")
        return {"deleted": True}

    return router


def _build_customer_endpoints(get_user_dep):
    """Register customer-facing endpoints."""
    router = APIRouter(tags=["releases-customer"])

    @router.get("/api/system/version")
    async def get_version():
        """Public — returns the running version of this install."""
        return {
            "version": current_version(),
            "mode": (os.environ.get("KREXION_MODE") or "local").lower(),
        }

    @router.get("/api/system/latest-version")
    async def latest_version(x_krexion_license: Optional[str] = Header(None)):
        """License-authenticated — returns the latest published release plus
        whether the caller is behind."""
        await _validate_license(x_krexion_license)
        local = current_version()
        rel = await _db.app_releases.find_one(
            {"published": True}, sort=[("created_at", -1)], projection={"_id": 0}
        )
        if not rel:
            return {"current": local, "latest": None, "update_available": False}
        return {
            "current": local,
            "latest": rel,
            "update_available": is_newer(rel["version"], local),
        }

    @router.get("/api/system/public-latest")
    async def public_latest():
        """No-auth lite endpoint for the local dashboard banner so it can
        decide whether to nag the user — does not expose download URL."""
        rel = await _db.app_releases.find_one(
            {"published": True},
            sort=[("created_at", -1)],
            projection={"_id": 0, "version": 1, "title": 1, "severity": 1, "created_at": 1, "notes": 1},
        )
        local = current_version()
        if not rel:
            return {"current": local, "latest": None, "update_available": False}
        return {
            "current": local,
            "latest": rel,
            "update_available": is_newer(rel["version"], local),
        }

    @router.post("/api/system/install-update")
    async def trigger_update(user: dict = Depends(get_user_dep)):
        """Customer (must be admin/owner of the local install) clicks
        Update → we drop a flag file the host updater script picks up.
        Only enabled on LOCAL mode."""
        mode = (os.environ.get("KREXION_MODE") or "local").lower()
        if mode != "local":
            raise HTTPException(403, "Self-update is only available on local installs")
        if not user.get("is_admin"):
            raise HTTPException(403, "Only the admin user can trigger updates")
        try:
            UPDATE_FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "requested_at": _now_iso(),
                "requested_by": user.get("email") or user.get("id"),
                "current_version": current_version(),
            }
            UPDATE_FLAG_FILE.write_text(json.dumps(payload), encoding="utf-8")
            logger.info(f"[update] flag written: {UPDATE_FLAG_FILE} by {payload['requested_by']}")
        except Exception as e:  # noqa: BLE001
            raise HTTPException(500, f"Could not write update flag: {e}")
        return {
            "ok": True,
            "flag_path": str(UPDATE_FLAG_FILE),
            "message": (
                "Update requested. The host updater will pull the new release "
                "and rebuild containers within 60 seconds. Krexion will be "
                "briefly unavailable during the swap."
            ),
        }

    return router
