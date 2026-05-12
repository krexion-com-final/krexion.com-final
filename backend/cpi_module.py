"""
CPI (Cost-Per-Install) Module for RealFlow
==========================================

Purpose:
  Cloud-orchestrated CPI install pipeline that runs alongside the existing
  RUT (Real User Traffic) and Form Filler engines. The orchestrator (this
  module) runs in the home-PC backend; actual Android/iOS install execution
  is performed by a separate `realflow-cpi-worker` process which polls jobs
  from this orchestrator and reports results back.

Phase 1 (this file) covers:
  • Mongo models + per-user database scoping (matches existing pattern)
  • CRUD APIs for offers, jobs, devices, smart-links
  • SmartLink OS-routing public redirect with click tracking
  • Worker protocol: poll, claim, report (stateless HTTP, simple to scale)
  • Live install-attempts log for the UI dashboard
  • Earnings / conversion-rate aggregation for dashboard cards

Conversion model (per user request):
  We DO NOT receive postbacks from CPI networks. Instead the worker reports
  "install + behavior simulation completed" → backend marks the attempt as
  `conversion_likely` after a configurable settle delay. The user verifies
  real conversion on the network panel themselves. This keeps zero
  network-side footprint (no postback URL leak).
"""
from __future__ import annotations

import os
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, Body
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ConfigDict
from user_agents import parse as parse_ua

logger = logging.getLogger("cpi")

# These will be injected by server.py at import time via _bind()
_main_db = None
_get_db_for_user = None
_get_current_user = None
_get_current_user_with_fresh_data = None
_check_user_feature = None
def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bind(main_db, get_db_for_user, get_current_user, get_current_user_with_fresh_data,
          check_user_feature, get_user_db=None, load_upload_items=None,
          consume_uploads=None):
    """Inject server.py dependencies once at startup."""
    global _main_db, _get_db_for_user, _get_current_user
    global _get_current_user_with_fresh_data, _check_user_feature
    global _get_user_db, _load_upload_items, _consume_uploads
    _main_db = main_db
    _get_db_for_user = get_db_for_user
    _get_current_user = get_current_user
    _get_current_user_with_fresh_data = get_current_user_with_fresh_data
    _check_user_feature = check_user_feature
    _get_user_db = get_user_db
    _load_upload_items = load_upload_items
    _consume_uploads = consume_uploads


# Optional helpers (set by _bind) — used for "use Uploaded Things" integration
_get_user_db = None
_load_upload_items = None
_consume_uploads = None


# ────────────────────────────────────────────────────────────────────────
# Models
# ────────────────────────────────────────────────────────────────────────

class CPIOfferIn(BaseModel):
    name: str
    network: Optional[str] = ""
    target_os: str = "android"  # "android" | "ios" | "both"
    tracker_url: str
    smart_link_code: Optional[str] = None
    apk_url: Optional[str] = None       # Android direct-APK
    ipa_url: Optional[str] = None       # iOS sideload IPA
    package_name: Optional[str] = None
    ios_app_id: Optional[str] = None
    payout: float = 0.0
    geo: Optional[str] = ""             # comma-separated ISO-2 codes
    daily_cap: int = 0
    notes: Optional[str] = ""
    status: str = "active"              # "active" | "paused"


class CPIOffer(CPIOfferIn):
    id: str
    user_id: str
    created_at: str
    updated_at: str
    total_clicks: int = 0
    total_installs: int = 0
    total_conversions: int = 0
    total_earnings: float = 0.0


class CPIJobIn(BaseModel):
    offer_id: str
    target_count: int = 10
    concurrency: int = 2
    delay_min_seconds: int = 60
    delay_max_seconds: int = 300
    proxies: List[str] = Field(default_factory=list)        # "ip:port:user:pass"
    user_agents: List[str] = Field(default_factory=list)
    leads: List[Dict[str, str]] = Field(default_factory=list)  # [{email,first,last,phone}, ...]
    settle_seconds: int = 45                                # wait after install before marking "conversion_likely"
    # Pull from Uploaded Things (RealFlow's existing resource pool)
    upload_proxy_id: Optional[str] = None
    upload_ua_id: Optional[str] = None
    # Auto-consume used resources after job completes (mirrors RUT behavior)
    auto_consume: bool = True


class CPIJob(BaseModel):
    id: str
    user_id: str
    offer_id: str
    offer_name: str
    target_os: str
    target_count: int
    concurrency: int
    delay_min_seconds: int
    delay_max_seconds: int
    settle_seconds: int
    proxies_count: int
    uas_count: int
    leads_count: int
    status: str = "queued"        # queued | running | paused | completed | stopped | failed
    completed: int = 0
    failed: int = 0
    in_progress: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str


class CPIInstallAttempt(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    job_id: str
    offer_id: str
    user_id: str
    device_id: Optional[str] = None
    device_label: Optional[str] = None
    proxy_used: Optional[str] = None
    ua_used: Optional[str] = None
    lead_used: Optional[Dict[str, str]] = None
    click_id: Optional[str] = None
    status: str = "queued"        # queued | running | installed | completed | failed | conversion_likely
    failure_reason: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)  # worker reports staged progress
    created_at: str


class CPIDeviceRegister(BaseModel):
    device_id: str                # worker-generated stable ID (e.g., adb serial / iOS UDID)
    device_type: str              # "android_real" | "android_genymotion" | "ios_real"
    label: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    worker_token: Optional[str] = None  # worker authenticates to backend with this


class CPIDevice(BaseModel):
    id: str
    user_id: str
    device_id: str
    device_type: str
    label: str
    model: Optional[str] = None
    os_version: Optional[str] = None
    status: str = "offline"        # online | busy | offline | error | needs_attention
    last_heartbeat: Optional[str] = None
    last_install_at: Optional[str] = None
    total_installs: int = 0
    successful_installs: int = 0
    needs_action: Optional[str] = None  # "2fa_pending" | "apple_id_locked" etc.
    created_at: str


class CPISmartLinkIn(BaseModel):
    name: str
    offer_id: Optional[str] = None
    android_url: Optional[str] = None
    ios_url: Optional[str] = None
    desktop_url: Optional[str] = None
    fallback_url: Optional[str] = "https://www.google.com/"


class CPISmartLink(CPISmartLinkIn):
    id: str
    user_id: str
    code: str
    total_clicks: int = 0
    android_clicks: int = 0
    ios_clicks: int = 0
    desktop_clicks: int = 0
    created_at: str


# ────────────────────────────────────────────────────────────────────────
# Router
# ────────────────────────────────────────────────────────────────────────

cpi_router = APIRouter(prefix="/api/cpi", tags=["cpi"])

FEATURE_KEY = "cpi"


def _new_id() -> str:
    return secrets.token_hex(12)


def _short_code(n: int = 8) -> str:
    return secrets.token_urlsafe(n)[:n]


async def _require_cpi_user(request: Request) -> dict:
    """Authenticated user with CPI feature flag enabled."""
    user = await _get_current_user_with_fresh_data(request)
    _check_user_feature(user, FEATURE_KEY)
    return user


def _detect_os_from_ua(ua_string: str) -> str:
    if not ua_string:
        return "unknown"
    try:
        ua = parse_ua(ua_string)
        if ua.os.family.lower().startswith("ios") or ua.os.family.lower() == "ios":
            return "ios"
        if "iphone" in ua_string.lower() or "ipad" in ua_string.lower():
            return "ios"
        if "android" in ua_string.lower():
            return "android"
        if ua.is_pc or ua.is_bot or "windows" in ua_string.lower() or "mac os" in ua_string.lower():
            return "desktop"
        return "unknown"
    except Exception:
        return "unknown"


# ────────────────────────────────────────────────────────────────────────
# OFFERS
# ────────────────────────────────────────────────────────────────────────

@cpi_router.post("/offers", response_model=CPIOffer)
async def create_offer(payload: CPIOfferIn, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    now = _iso_now()
    offer_id = _new_id()
    doc = {
        **payload.model_dump(),
        "id": offer_id,
        "user_id": user["id"],
        "created_at": now,
        "updated_at": now,
        "total_clicks": 0,
        "total_installs": 0,
        "total_conversions": 0,
        "total_earnings": 0.0,
    }
    if not doc.get("smart_link_code"):
        doc["smart_link_code"] = _short_code(10)
    await db.cpi_offers.insert_one(doc)
    doc.pop("_id", None)
    return doc


@cpi_router.get("/offers", response_model=List[CPIOffer])
async def list_offers(request: Request, status: Optional[str] = None):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    q = {"user_id": user["id"]}
    if status:
        q["status"] = status
    cursor = db.cpi_offers.find(q, {"_id": 0}).sort("created_at", -1)
    return [doc async for doc in cursor]


@cpi_router.get("/offers/{offer_id}", response_model=CPIOffer)
async def get_offer(offer_id: str, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    doc = await db.cpi_offers.find_one({"id": offer_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Offer not found")
    return doc


@cpi_router.put("/offers/{offer_id}", response_model=CPIOffer)
async def update_offer(offer_id: str, payload: CPIOfferIn, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    update = {**payload.model_dump(), "updated_at": _iso_now()}
    res = await db.cpi_offers.find_one_and_update(
        {"id": offer_id, "user_id": user["id"]},
        {"$set": update},
        return_document=True,
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(status_code=404, detail="Offer not found")
    return res


@cpi_router.delete("/offers/{offer_id}")
async def delete_offer(offer_id: str, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    await db.cpi_offers.delete_one({"id": offer_id, "user_id": user["id"]})
    return {"ok": True}


# ────────────────────────────────────────────────────────────────────────
# SMART LINKS  (public redirect + click tracking)
# ────────────────────────────────────────────────────────────────────────

@cpi_router.post("/smartlinks", response_model=CPISmartLink)
async def create_smartlink(payload: CPISmartLinkIn, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    code = _short_code(10)
    while await db.cpi_smartlinks.find_one({"code": code}):
        code = _short_code(10)
    doc = {
        **payload.model_dump(),
        "id": _new_id(),
        "user_id": user["id"],
        "code": code,
        "total_clicks": 0,
        "android_clicks": 0,
        "ios_clicks": 0,
        "desktop_clicks": 0,
        "created_at": _iso_now(),
    }
    await db.cpi_smartlinks.insert_one(doc)
    doc.pop("_id", None)
    return doc


@cpi_router.get("/smartlinks", response_model=List[CPISmartLink])
async def list_smartlinks(request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    cursor = db.cpi_smartlinks.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
    return [doc async for doc in cursor]


@cpi_router.delete("/smartlinks/{sl_id}")
async def delete_smartlink(sl_id: str, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    await db.cpi_smartlinks.delete_one({"id": sl_id, "user_id": user["id"]})
    return {"ok": True}


@cpi_router.get("/sl/{code}")
async def smartlink_redirect(code: str, request: Request):
    """PUBLIC: Hit by users / our worker. Detects OS, redirects, logs click."""
    # Search across ALL user dbs by indexing on the smart-links collection.
    # For now we mirror the row in main_db at creation time? Simpler: scan user
    # databases via list of users. The expected hit volume is low (worker
    # mostly bypasses this and goes direct to tracker_url) so we accept the
    # cost. Fast path: cache the lookup in-memory.
    cache = smartlink_redirect.__dict__.setdefault("_cache", {})
    entry = cache.get(code)
    if entry is None or (datetime.now(timezone.utc).timestamp() - entry["t"]) > 60:
        # find it
        users = [u async for u in _main_db.users.find({}, {"id": 1, "_id": 0})]
        sl_doc = None
        owner_id = None
        for u in users:
            udb = _get_db_for_user(u)
            d = await udb.cpi_smartlinks.find_one({"code": code}, {"_id": 0})
            if d:
                sl_doc = d
                owner_id = u["id"]
                break
        cache[code] = {"t": datetime.now(timezone.utc).timestamp(), "doc": sl_doc, "owner": owner_id}
        entry = cache[code]
    sl_doc = entry.get("doc")
    if not sl_doc:
        raise HTTPException(status_code=404, detail="Smart-link not found")
    owner_id = entry["owner"]

    ua = request.headers.get("user-agent", "")
    os_kind = _detect_os_from_ua(ua)
    target_url = (
        sl_doc.get("android_url") if os_kind == "android"
        else sl_doc.get("ios_url") if os_kind == "ios"
        else sl_doc.get("desktop_url") if os_kind == "desktop"
        else None
    ) or sl_doc.get("fallback_url") or "https://www.google.com/"

    # Log click (non-blocking, best-effort)
    try:
        owner = {"id": owner_id, "is_sub_user": False}
        udb = _get_db_for_user(owner)
        await udb.cpi_smartlinks.update_one(
            {"id": sl_doc["id"]},
            {"$inc": {
                "total_clicks": 1,
                f"{os_kind}_clicks": 1 if os_kind in ("android", "ios", "desktop") else 0,
            }},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[cpi-sl] click log failed: {e}")

    return RedirectResponse(target_url, status_code=302)


# ────────────────────────────────────────────────────────────────────────
# DEVICES (worker registers here)
# ────────────────────────────────────────────────────────────────────────

@cpi_router.post("/devices/register", response_model=CPIDevice)
async def register_device(payload: CPIDeviceRegister, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    existing = await db.cpi_devices.find_one(
        {"device_id": payload.device_id, "user_id": user["id"]}, {"_id": 0}
    )
    if existing:
        await db.cpi_devices.update_one(
            {"id": existing["id"]},
            {"$set": {
                "device_type": payload.device_type,
                "label": payload.label or existing["label"],
                "model": payload.model or existing.get("model"),
                "os_version": payload.os_version or existing.get("os_version"),
                "status": "online",
                "last_heartbeat": _iso_now(),
            }},
        )
        existing.update({"status": "online", "last_heartbeat": _iso_now()})
        return existing
    doc = {
        "id": _new_id(),
        "user_id": user["id"],
        "device_id": payload.device_id,
        "device_type": payload.device_type,
        "label": payload.label or payload.device_id[:12],
        "model": payload.model,
        "os_version": payload.os_version,
        "status": "online",
        "last_heartbeat": _iso_now(),
        "last_install_at": None,
        "total_installs": 0,
        "successful_installs": 0,
        "needs_action": None,
        "created_at": _iso_now(),
    }
    await db.cpi_devices.insert_one(doc)
    doc.pop("_id", None)
    return doc


@cpi_router.post("/devices/{device_id}/heartbeat")
async def device_heartbeat(device_id: str, request: Request, payload: Dict[str, Any] = Body(default={})):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    update = {"last_heartbeat": _iso_now()}
    if "status" in payload:
        update["status"] = payload["status"]
    if "needs_action" in payload:
        update["needs_action"] = payload["needs_action"]
    res = await db.cpi_devices.update_one(
        {"id": device_id, "user_id": user["id"]}, {"$set": update}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True}


@cpi_router.get("/devices", response_model=List[CPIDevice])
async def list_devices(request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    # Auto-mark devices offline if heartbeat older than 90 seconds
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
    await db.cpi_devices.update_many(
        {"user_id": user["id"], "last_heartbeat": {"$lt": cutoff}, "status": {"$in": ["online", "busy"]}},
        {"$set": {"status": "offline"}},
    )
    cursor = db.cpi_devices.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
    return [doc async for doc in cursor]


@cpi_router.delete("/devices/{device_id}")
async def delete_device(device_id: str, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    await db.cpi_devices.delete_one({"id": device_id, "user_id": user["id"]})
    return {"ok": True}


# ────────────────────────────────────────────────────────────────────────
# JOBS
# ────────────────────────────────────────────────────────────────────────

_INTERNAL_PROJECTION = {
    "_id": 0, "_proxies": 0, "_user_agents": 0, "_leads": 0,
    "_proxies_used": 0, "_uas_used": 0,
    "_consume_upload_ids": 0, "_auto_consume": 0,
}


@cpi_router.post("/jobs", response_model=CPIJob)
async def create_job(payload: CPIJobIn, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    offer = await db.cpi_offers.find_one({"id": payload.offer_id, "user_id": user["id"]}, {"_id": 0})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    # Resolve resource pools — paste wins, else load from Uploaded Things
    proxies = list(payload.proxies)
    user_agents = list(payload.user_agents)
    consume_upload_ids: List[str] = []

    if not proxies and payload.upload_proxy_id and _load_upload_items:
        items = await _load_upload_items(user["id"], payload.upload_proxy_id, "proxies")
        proxies = items
        if items and payload.auto_consume:
            consume_upload_ids.append(payload.upload_proxy_id)

    if not user_agents and payload.upload_ua_id and _load_upload_items:
        items = await _load_upload_items(user["id"], payload.upload_ua_id, "user_agents")
        user_agents = items
        if items and payload.auto_consume:
            consume_upload_ids.append(payload.upload_ua_id)

    if not proxies:
        raise HTTPException(status_code=400, detail="At least one proxy is required (paste or pick from Uploaded Things)")
    if not user_agents:
        raise HTTPException(status_code=400, detail="At least one user-agent is required (paste or pick from Uploaded Things)")

    job = {
        "id": _new_id(),
        "user_id": user["id"],
        "offer_id": offer["id"],
        "offer_name": offer["name"],
        "target_os": offer.get("target_os", "android"),
        "target_count": payload.target_count,
        "concurrency": payload.concurrency,
        "delay_min_seconds": payload.delay_min_seconds,
        "delay_max_seconds": payload.delay_max_seconds,
        "settle_seconds": payload.settle_seconds,
        "proxies_count": len(proxies),
        "uas_count": len(user_agents),
        "leads_count": len(payload.leads),
        "status": "queued",
        "completed": 0,
        "failed": 0,
        "in_progress": 0,
        "started_at": None,
        "completed_at": None,
        "created_at": _iso_now(),
        # Internal pools (NOT returned via the response_model below)
        "_proxies": proxies,
        "_user_agents": user_agents,
        "_leads": payload.leads,
        "_proxies_used": [],
        "_uas_used": [],
        "_consume_upload_ids": consume_upload_ids,
        "_auto_consume": bool(payload.auto_consume),
    }
    await db.cpi_jobs.insert_one(job)

    # Pre-create attempt placeholders (queued)
    attempts = [
        {
            "id": _new_id(),
            "job_id": job["id"],
            "offer_id": offer["id"],
            "user_id": user["id"],
            "device_id": None,
            "device_label": None,
            "proxy_used": None,
            "ua_used": None,
            "lead_used": None,
            "click_id": None,
            "status": "queued",
            "failure_reason": None,
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
            "steps": [],
            "created_at": _iso_now(),
        }
        for _ in range(payload.target_count)
    ]
    if attempts:
        await db.cpi_install_attempts.insert_many(attempts)

    job.pop("_id", None)
    # Return without internal pools
    job_safe = {k: v for k, v in job.items() if not k.startswith("_")}
    return job_safe


@cpi_router.get("/jobs", response_model=List[CPIJob])
async def list_jobs(request: Request, status: Optional[str] = None, limit: int = 100):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    q = {"user_id": user["id"]}
    if status:
        q["status"] = status
    cursor = (
        db.cpi_jobs.find(q, _INTERNAL_PROJECTION)
        .sort("created_at", -1)
        .limit(limit)
    )
    return [doc async for doc in cursor]


@cpi_router.get("/jobs/{job_id}", response_model=CPIJob)
async def get_job(job_id: str, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    doc = await db.cpi_jobs.find_one(
        {"id": job_id, "user_id": user["id"]},
        _INTERNAL_PROJECTION,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
    return doc


@cpi_router.post("/jobs/{job_id}/start")
async def start_job(job_id: str, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    res = await db.cpi_jobs.find_one_and_update(
        {"id": job_id, "user_id": user["id"], "status": {"$in": ["queued", "paused"]}},
        {"$set": {"status": "running", "started_at": _iso_now()}},
        return_document=True,
        projection=_INTERNAL_PROJECTION,
    )
    if not res:
        raise HTTPException(status_code=400, detail="Job cannot be started (not queued/paused or not found)")
    return res


@cpi_router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    res = await db.cpi_jobs.find_one_and_update(
        {"id": job_id, "user_id": user["id"], "status": "running"},
        {"$set": {"status": "paused"}},
        return_document=True,
        projection=_INTERNAL_PROJECTION,
    )
    if not res:
        raise HTTPException(status_code=400, detail="Job not running")
    return res


@cpi_router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    res = await db.cpi_jobs.find_one_and_update(
        {"id": job_id, "user_id": user["id"], "status": {"$in": ["running", "paused", "queued"]}},
        {"$set": {"status": "stopped", "completed_at": _iso_now()}},
        return_document=True,
        projection=_INTERNAL_PROJECTION,
    )
    if not res:
        raise HTTPException(status_code=400, detail="Job is not active")
    # Mark queued attempts as cancelled
    await db.cpi_install_attempts.update_many(
        {"job_id": job_id, "status": "queued"},
        {"$set": {"status": "failed", "failure_reason": "job_stopped", "completed_at": _iso_now()}},
    )
    return res


@cpi_router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    await db.cpi_jobs.delete_one({"id": job_id, "user_id": user["id"]})
    await db.cpi_install_attempts.delete_many({"job_id": job_id, "user_id": user["id"]})
    return {"ok": True}


@cpi_router.get("/jobs/{job_id}/attempts", response_model=List[CPIInstallAttempt])
async def list_job_attempts(job_id: str, request: Request, limit: int = 200):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    cursor = (
        db.cpi_install_attempts.find(
            {"job_id": job_id, "user_id": user["id"]}, {"_id": 0}
        )
        .sort("created_at", 1)
        .limit(limit)
    )
    return [doc async for doc in cursor]


# ────────────────────────────────────────────────────────────────────────
# WORKER PROTOCOL
# ────────────────────────────────────────────────────────────────────────

@cpi_router.post("/worker/poll")
async def worker_poll(request: Request, payload: Dict[str, Any] = Body(default={})):
    """Worker calls this every few seconds. We claim ONE queued attempt
    that matches the worker's available device types and return the full
    install instructions."""
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    available_types = payload.get("device_types") or ["android_real", "android_genymotion", "ios_real"]
    device_id_db = payload.get("device_id")  # optional: lock to this device

    # Find a running job that has queued attempts
    running_jobs_cursor = db.cpi_jobs.find(
        {"user_id": user["id"], "status": "running"},
        {"_id": 0},
    ).sort("created_at", 1)
    running_jobs = [j async for j in running_jobs_cursor]
    for job in running_jobs:
        # Skip if target_os incompatible with worker's available types
        target_os = job.get("target_os", "android")
        if target_os == "android" and not any(t.startswith("android") for t in available_types):
            continue
        if target_os == "ios" and "ios_real" not in available_types:
            continue
        # "both" → prefer android (cheaper) if available
        # Atomic claim: queued → running, attach device
        attempt = await db.cpi_install_attempts.find_one_and_update(
            {"job_id": job["id"], "status": "queued"},
            {"$set": {
                "status": "running",
                "started_at": _iso_now(),
                "device_id": device_id_db,
            }},
            return_document=True,
            projection={"_id": 0},
        )
        if not attempt:
            continue
        # Pick proxy + UA + lead (round-robin via job pool)
        full_job = await db.cpi_jobs.find_one({"id": job["id"]}, {"_id": 0})
        proxies = full_job.get("_proxies") or []
        uas = full_job.get("_user_agents") or []
        leads = full_job.get("_leads") or []
        used_count = full_job.get("completed", 0) + full_job.get("in_progress", 0)
        proxy = proxies[used_count % len(proxies)] if proxies else None
        ua = uas[used_count % len(uas)] if uas else None
        lead = leads[used_count % len(leads)] if leads else None

        await db.cpi_install_attempts.update_one(
            {"id": attempt["id"]},
            {"$set": {"proxy_used": proxy, "ua_used": ua, "lead_used": lead}},
        )
        await db.cpi_jobs.update_one({"id": job["id"]}, {"$inc": {"in_progress": 1}})

        # Pull offer for full instructions
        offer = await db.cpi_offers.find_one({"id": job["offer_id"]}, {"_id": 0}) or {}
        return {
            "has_work": True,
            "attempt": {**attempt, "proxy_used": proxy, "ua_used": ua, "lead_used": lead},
            "job": {k: v for k, v in full_job.items() if not k.startswith("_")},
            "offer": offer,
        }

    return {"has_work": False}


@cpi_router.post("/worker/result")
async def worker_result(request: Request, payload: Dict[str, Any] = Body(...)):
    """Worker reports completion (success or failure)."""
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)
    attempt_id = payload.get("attempt_id")
    success = bool(payload.get("success"))
    failure_reason = payload.get("failure_reason")
    duration = payload.get("duration_seconds")
    steps = payload.get("steps") or []
    click_id = payload.get("click_id")
    device_id = payload.get("device_id")
    device_label = payload.get("device_label")

    attempt = await db.cpi_install_attempts.find_one(
        {"id": attempt_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    new_status = "conversion_likely" if success else "failed"
    update = {
        "status": new_status,
        "failure_reason": failure_reason,
        "duration_seconds": duration,
        "completed_at": _iso_now(),
        "steps": steps,
        "click_id": click_id,
        "device_id": device_id or attempt.get("device_id"),
        "device_label": device_label,
    }
    await db.cpi_install_attempts.update_one({"id": attempt_id}, {"$set": update})

    inc = {"in_progress": -1}
    if success:
        inc["completed"] = 1
    else:
        inc["failed"] = 1
    update_ops: Dict[str, Any] = {"$inc": inc}

    # Track which proxy / UA actually got used (for selective auto-consume of
    # the originating Uploaded Things batch — same logic RUT uses).
    push_ops: Dict[str, Any] = {}
    if attempt.get("proxy_used"):
        push_ops["_proxies_used"] = attempt["proxy_used"]
    if attempt.get("ua_used"):
        push_ops["_uas_used"] = attempt["ua_used"]
    if push_ops:
        update_ops["$push"] = {k: v for k, v in push_ops.items()}

    job = await db.cpi_jobs.find_one_and_update(
        {"id": attempt["job_id"]},
        update_ops,
        return_document=True,
    )

    # Auto-complete + auto-consume Uploaded Things when all attempts settled
    if job and (job.get("completed", 0) + job.get("failed", 0)) >= job["target_count"] and job.get("in_progress", 0) <= 0:
        await db.cpi_jobs.update_one(
            {"id": job["id"]},
            {"$set": {"status": "completed", "completed_at": _iso_now()}},
        )
        # Auto-consume — selectively prune ONLY actually-used items from the
        # originating Uploaded Things batches. Mirrors RUT/Form Filler behavior.
        if (job.get("_auto_consume") and _consume_uploads
                and job.get("_consume_upload_ids")):
            try:
                await _consume_uploads(
                    user_id=user["id"],
                    upload_ids=job["_consume_upload_ids"],
                    used_proxy_raws=job.get("_proxies_used") or [],
                    used_ua_strings=job.get("_uas_used") or [],
                    pending_leads_path=None,
                )
                logger.info(f"[cpi] auto-consumed uploads for job {job['id']}")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[cpi] auto-consume failed for job {job['id']}: {e}")

    # Update offer counters
    if success:
        await db.cpi_offers.update_one(
            {"id": attempt["offer_id"]},
            {"$inc": {"total_installs": 1, "total_conversions": 1}},
        )
        offer = await db.cpi_offers.find_one({"id": attempt["offer_id"]}, {"_id": 0})
        if offer and offer.get("payout"):
            await db.cpi_offers.update_one(
                {"id": attempt["offer_id"]},
                {"$inc": {"total_earnings": float(offer["payout"])}},
            )

    # Update device counters
    if device_id:
        device_inc = {"total_installs": 1}
        if success:
            device_inc["successful_installs"] = 1
        await db.cpi_devices.update_one(
            {"device_id": device_id, "user_id": user["id"]},
            {"$inc": device_inc, "$set": {"last_install_at": _iso_now(), "status": "online"}},
        )

    return {"ok": True, "status": new_status}


# ────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ────────────────────────────────────────────────────────────────────────

@cpi_router.get("/dashboard/stats")
async def dashboard_stats(request: Request, period: str = "today"):
    user = await _require_cpi_user(request)
    db = _get_db_for_user(user)

    if period == "today":
        cutoff = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)).isoformat()
    elif period == "week":
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    elif period == "month":
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    else:
        cutoff = "1970-01-01"

    # Aggregate per offer
    pipeline = [
        {"$match": {"user_id": user["id"], "completed_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
        }},
    ]
    by_status = {}
    async for row in db.cpi_install_attempts.aggregate(pipeline):
        by_status[row["_id"]] = row["count"]

    completed = by_status.get("conversion_likely", 0)
    failed = by_status.get("failed", 0)
    running = by_status.get("running", 0)
    total = completed + failed + running

    # Earnings: pull from offers' payout × completed-in-period
    earn_pipeline = [
        {"$match": {"user_id": user["id"], "status": "conversion_likely",
                    "completed_at": {"$gte": cutoff}}},
        {"$lookup": {
            "from": "cpi_offers", "localField": "offer_id",
            "foreignField": "id", "as": "offer"
        }},
        {"$unwind": "$offer"},
        {"$group": {
            "_id": None,
            "earnings": {"$sum": "$offer.payout"},
        }},
    ]
    earnings = 0.0
    async for row in db.cpi_install_attempts.aggregate(earn_pipeline):
        earnings = float(row.get("earnings") or 0)

    devices_online = await db.cpi_devices.count_documents(
        {"user_id": user["id"], "status": {"$in": ["online", "busy"]}}
    )
    active_jobs = await db.cpi_jobs.count_documents(
        {"user_id": user["id"], "status": "running"}
    )

    return {
        "period": period,
        "completed_installs": completed,
        "failed_installs": failed,
        "running_installs": running,
        "total_attempts": total,
        "success_rate": round((completed / total) * 100, 1) if total else 0.0,
        "earnings": round(earnings, 2),
        "devices_online": devices_online,
        "active_jobs": active_jobs,
    }
