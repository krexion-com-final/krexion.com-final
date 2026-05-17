"""
Krexion — Sync Module (Phase 2 of the Hybrid Architecture)
==========================================================

The customer's local Krexion install talks to the cloud edge
(krexion.com) through these endpoints. Authentication is via the
license key issued at purchase (sent in the `X-Krexion-License` header).

Endpoints (all under `/api/sync/`):
  POST /links            — local pushes its link config to cloud
                           (so cloud's /r/<short_code> redirects work)
  GET  /clicks/pull      — local pulls clicks captured by the cloud edge
                           (i.e. when someone clicked /r/xxx while the
                            customer's PC was offline)
  POST /clicks/ack       — local marks pulled clicks as stored locally
  POST /heartbeat        — local announces itself ("I'm online")
  GET  /status           — local checks what cloud knows about it
"""

from __future__ import annotations

import logging
import socket
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)
sync_router = APIRouter(prefix="/api/sync", tags=["sync"])

# Bound by server.py on startup
_db: Any = None
_get_db_for_user: Any = None


def _bind(*, main_db, get_db_for_user) -> None:
    global _db, _get_db_for_user
    _db = main_db
    _get_db_for_user = get_db_for_user


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _validate_license(license_key: Optional[str]):
    if not license_key:
        raise HTTPException(status_code=401, detail="Missing X-Krexion-License header")
    license_key = license_key.strip()
    lic = await _db.licenses.find_one({"license_key": license_key}, {"_id": 0})
    if not lic:
        raise HTTPException(status_code=401, detail="Invalid license key")
    if lic.get("status") and lic["status"] not in ("active", "issued"):
        raise HTTPException(status_code=403, detail=f"License is {lic['status']}")
    # Expiry check
    exp = lic.get("expires_at")
    if exp:
        try:
            expires = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > expires:
                raise HTTPException(status_code=403, detail="License expired")
        except (ValueError, AttributeError):
            pass
    user = await _db.users.find_one({"email": lic["email"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=403, detail="No user account for this license")
    return lic, user


# ─── Endpoints ────────────────────────────────────────────────────────
@sync_router.post("/links")
async def push_links(
    body: dict,
    x_krexion_license: Optional[str] = Header(None),
):
    """Local install pushes link configs so cloud `/r/xxx` redirects work."""
    _, user = await _validate_license(x_krexion_license)
    user_id = user["id"]
    links = body.get("links") or []
    if not isinstance(links, list):
        raise HTTPException(status_code=400, detail="`links` must be a list")

    upserted = 0
    for link in links[:5000]:  # safety cap
        sc = link.get("short_code")
        offer = link.get("offer_url") or link.get("destination_url")
        if not sc or not offer:
            continue
        update = {
            "id": link.get("id") or f"sync_{sc}",
            "user_id": user_id,
            "short_code": sc,
            "offer_url": offer,
            "name": link.get("name", ""),
            "status": link.get("status", "active"),
            "allowed_countries": link.get("allowed_countries", []),
            "allowed_os": link.get("allowed_os", []),
            "block_vpn": bool(link.get("block_vpn", False)),
            "updated_at": _now_iso(),
            "synced_from_local": True,
        }
        await _db.links.update_one(
            {"short_code": sc, "user_id": user_id},
            {
                "$set": update,
                "$setOnInsert": {
                    "created_at": _now_iso(),
                    "clicks": 0,
                    "conversions": 0,
                    "revenue": 0.0,
                },
            },
            upsert=True,
        )
        upserted += 1
    return {"upserted": upserted, "received": len(links)}


@sync_router.get("/clicks/pull")
async def pull_clicks(
    since: str = "",
    limit: int = 500,
    x_krexion_license: Optional[str] = Header(None),
):
    """Local pulls new clicks captured by the cloud edge."""
    _, user = await _validate_license(x_krexion_license)
    if not _get_db_for_user:
        raise HTTPException(status_code=503, detail="Sync not fully configured")

    user_db = _get_db_for_user(user)
    q: dict = {"sync_pulled": {"$ne": True}}
    if since:
        q["created_at"] = {"$gt": since}

    limit = max(1, min(int(limit or 500), 2000))
    cursor = user_db.clicks.find(q, {"_id": 0}).sort("created_at", 1).limit(limit)
    items = await cursor.to_list(limit)
    return {
        "clicks": items,
        "count": len(items),
        "has_more": len(items) >= limit,
    }


@sync_router.post("/clicks/ack")
async def ack_clicks(
    body: dict,
    x_krexion_license: Optional[str] = Header(None),
):
    """Local says these click IDs have been written into its local DB."""
    _, user = await _validate_license(x_krexion_license)
    user_db = _get_db_for_user(user)
    ids = body.get("click_ids") or []
    if not isinstance(ids, list) or not ids:
        return {"acked": 0}
    res = await user_db.clicks.update_many(
        {"id": {"$in": ids[:2000]}},
        {"$set": {"sync_pulled": True, "sync_pulled_at": _now_iso()}},
    )
    return {"acked": res.modified_count}


@sync_router.post("/heartbeat")
async def heartbeat(
    body: dict,
    request: Request,
    x_krexion_license: Optional[str] = Header(None),
):
    lic, user = await _validate_license(x_krexion_license)
    update_doc = {
        "license_key": lic["license_key"],
        "email": user["email"],
        "user_id": user["id"],
        "hostname": (body.get("hostname") or "")[:120],
        "version": (body.get("version") or "")[:32],
        "platform": (body.get("platform") or "")[:60],
        "ip": (request.client.host if request.client else "")[:60],
        "last_seen": _now_iso(),
    }
    # Hardware info for cloud-orchestrated load tuning (bridge module)
    if body.get("ram_gb") is not None:
        try:
            update_doc["ram_gb"] = float(body.get("ram_gb"))
        except (TypeError, ValueError):
            pass
    if body.get("cpu_cores") is not None:
        try:
            update_doc["cpu_cores"] = int(body.get("cpu_cores"))
        except (TypeError, ValueError):
            pass
    if body.get("recommended_concurrency") is not None:
        try:
            update_doc["recommended_concurrency"] = int(body.get("recommended_concurrency"))
        except (TypeError, ValueError):
            pass
    await _db.sync_heartbeats.update_one(
        {"license_key": lic["license_key"]},
        {"$set": update_doc},
        upsert=True,
    )
    return {"ok": True, "server_time": _now_iso()}


@sync_router.get("/status")
async def sync_status(
    x_krexion_license: Optional[str] = Header(None),
):
    lic, user = await _validate_license(x_krexion_license)
    user_db = _get_db_for_user(user)
    pending = await user_db.clicks.count_documents({"sync_pulled": {"$ne": True}})
    total = await user_db.clicks.count_documents({})
    links_cnt = await _db.links.count_documents({"user_id": user["id"]})
    last_hb = await _db.sync_heartbeats.find_one(
        {"license_key": lic["license_key"]}, {"_id": 0}
    )
    return {
        "user_id": user["id"],
        "email": user["email"],
        "license_key": lic["license_key"],
        "license_status": lic.get("status"),
        "expires_at": lic.get("expires_at"),
        "links_in_cloud": links_cnt,
        "pending_clicks": pending,
        "total_clicks": total,
        "last_heartbeat": (last_hb or {}).get("last_seen"),
    }


@sync_router.get("/ping")
async def sync_ping():
    """Public no-auth health endpoint so the local daemon can probe reach."""
    return {"ok": True, "server_time": _now_iso()}
