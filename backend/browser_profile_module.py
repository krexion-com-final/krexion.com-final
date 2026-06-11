"""
Krexion — Browser Profiles Module (2026-06-11)
================================================

AdsPower / GoLogin-style manual browsing profiles. Each profile stores:
  • Identity config (name, country, language, UA, viewport, device)
  • Anti-detect config (same flags as RUT jobs — auto-tuned by master toggle)
  • Referrer config (Pro Mode platform/email weights for outbound clicks)
  • Proxy assignment (manual or ProxyJet auto-allocated unique IP)
  • Persistent storage_state (cookies + localStorage across launches)

Customers use these profiles to MANUALLY browse the web with the same
professional-grade anti-detect stack used by RUT jobs. Typical use:
verify offer pages, login to ad accounts on alt identities, manual
research on competitor sites without burning your main IP.

Architecture:
  • Cloud mode (krexion.com)         → CRUD only. Launch returns a
                                       bridge_job that the customer's
                                       local desktop client picks up
                                       and opens HEADED Chromium with
                                       all anti-detect injected.
  • Desktop mode (Electron/native)   → CRUD + actual local launch.
                                       The Electron host process opens
                                       a Playwright headed context with
                                       full anti-detect script + the
                                       stored storage_state.

Storage:
  • Mongo collection: `browser_profiles`   (per-user records)
  • Mongo collection: `browser_profile_sessions`  (running launches)
  • Bridge jobs of kind="browser_profile_launch" relay to desktop.

Endpoints (all under /api/browser-profiles/*):
  GET    /                   List user's profiles
  POST   /                   Create profile (auto-gen UA + viewport optional)
  GET    /{id}               Get one profile (incl. storage_state stats)
  PUT    /{id}               Update profile config
  DELETE /{id}               Delete profile + its sessions
  POST   /{id}/clone         Duplicate (new id, name " (copy)")
  POST   /{id}/launch        Start a manual browse session
  POST   /{id}/stop          Stop a running session
  GET    /{id}/status        Is the session running?
  POST   /import-bulk        Bulk-create N profiles (range / list)
  GET    /export             Download all profiles as JSON
  POST   /generate-quick     One-click: create a profile with auto UA + proxy
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import secrets
import string
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("browser_profile_module")

# ─── Globals bound by server.py via _bind() ──────────────────────────
_DB: Any = None
_BRIDGE_QUEUE: Any = None
_GET_USER: Any = None
_UA_GEN: Any = None

router = APIRouter(prefix="/api/browser-profiles", tags=["browser-profiles"])


def _bind(*, db, get_current_user, bridge_enqueue=None, ua_generate_func=None):
    """Called once by server.py at import time."""
    global _DB, _BRIDGE_QUEUE, _GET_USER, _UA_GEN
    _DB = db
    _GET_USER = get_current_user
    _BRIDGE_QUEUE = bridge_enqueue
    _UA_GEN = ua_generate_func


# Wrapper used as FastAPI Depends — resolves to the bound real dep at
# request time (so router decorators can reference it even though it's
# set after import).
async def _auth(request: Any = None):
    if _GET_USER is None:
        raise HTTPException(status_code=503, detail="Browser Profiles: auth not bound")
    # FastAPI will resolve the bound dep on the actual handler via
    # Depends below; this stub is only used when no fancy dep injection
    # is wanted. We return a marker — actual user is extracted via
    # the wrapper pattern below in each endpoint.
    return None


# ──────────────────────────────────────────────────────────────────────
# Default UA + viewport pools for auto-gen
# ──────────────────────────────────────────────────────────────────────
_VIEWPORTS_DESKTOP = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 720},
    {"width": 2560, "height": 1440},
]
_VIEWPORTS_MOBILE = [
    {"width": 390, "height": 844},   # iPhone 15
    {"width": 393, "height": 852},   # iPhone 14 Pro
    {"width": 414, "height": 896},   # iPhone XR
    {"width": 360, "height": 780},   # Galaxy S22
    {"width": 412, "height": 915},   # Pixel 7
]

_FALLBACK_UAS_DESKTOP = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.7727.102 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.7727.102 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7656.84 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.7544.92 Safari/537.36 Edg/145.0.2917.71",
]
_FALLBACK_UAS_MOBILE = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36",
]


def _gen_random_ua(is_mobile: bool = False) -> str:
    return random.choice(_FALLBACK_UAS_MOBILE if is_mobile else _FALLBACK_UAS_DESKTOP)


def _gen_random_viewport(is_mobile: bool = False) -> Dict[str, int]:
    return random.choice(_VIEWPORTS_MOBILE if is_mobile else _VIEWPORTS_DESKTOP).copy()


# ──────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────
class ProxyConfig(BaseModel):
    enabled: bool = False
    server: str = ""            # http://host:port or socks5://host:port
    username: str = ""
    password: str = ""
    # ProxyJet auto-mode (uses customer's saved ProxyJet creds)
    use_proxyjet: bool = False
    proxyjet_country: str = "US"
    proxyjet_state: str = ""


class AntiDetectConfig(BaseModel):
    """Single master switch + same flags as RUT (auto-tuned)."""
    master: bool = True             # ⭐ master toggle (default ON for new profiles)
    tls_prewarm: bool = True
    behavioral_bio: bool = True
    ip_warmup: bool = False         # Heavy — opt in
    browser_variant: str = "rotate" # auto/rotate/chromium/brave/headless-shell
    identity_persist: bool = True   # Carry cookies+localStorage across launches
    paranoia_mode: bool = False     # Maximum anti-detect (slower)


class ReferrerProConfig(BaseModel):
    """Per-profile Referrer Pro config (used when this profile opens a
    new tab to a 3rd-party URL — engine injects matching Referer)."""
    enabled: bool = False
    pro_mode: bool = True
    platform_weights: Dict[str, float] = Field(default_factory=dict)
    email_weights: Dict[str, float] = Field(default_factory=dict)
    social_wrapper: bool = True
    inapp_deep_path: bool = True
    strip_search_path: bool = True
    network_click_chain: bool = False
    search_engine: str = "google"
    search_keywords: str = ""
    brand: str = ""


class ProfileBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    notes: str = Field(default="", max_length=2000)
    country: str = Field(default="us", max_length=8)
    language: str = Field(default="en-US", max_length=24)
    timezone: str = Field(default="America/New_York", max_length=64)
    device_type: str = Field(default="desktop")  # desktop | mobile
    os: str = Field(default="windows")
    user_agent: str = Field(default="", max_length=600)
    viewport: Dict[str, int] = Field(default_factory=lambda: {"width": 1920, "height": 1080})
    is_mobile: bool = False
    has_touch: bool = False
    device_scale_factor: float = 1.0
    locale: str = "en-US"
    accept_language: str = "en-US,en;q=0.9"
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    anti_detect: AntiDetectConfig = Field(default_factory=AntiDetectConfig)
    referrer: ReferrerProConfig = Field(default_factory=ReferrerProConfig)
    tags: List[str] = Field(default_factory=list)
    start_url: str = Field(default="https://www.google.com/", max_length=512)


class BulkCreateBody(BaseModel):
    count: int = Field(..., ge=1, le=200)
    name_prefix: str = Field(default="Profile", max_length=64)
    base: ProfileBody
    randomize_ua: bool = True
    randomize_viewport: bool = True
    auto_unique_proxy: bool = True


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _profile_doc(user_id: str, body: ProfileBody) -> Dict[str, Any]:
    """Convert ProfileBody → MongoDB document with metadata."""
    # Auto-fill UA + viewport if blank
    is_mobile = bool(body.is_mobile or body.device_type == "mobile")
    ua = body.user_agent.strip() or _gen_random_ua(is_mobile)
    viewport = body.viewport if body.viewport.get("width") else _gen_random_viewport(is_mobile)
    pid = str(uuid.uuid4())
    return {
        "id": pid,
        "user_id": user_id,
        "name": body.name.strip(),
        "notes": body.notes,
        "country": body.country.lower(),
        "language": body.language,
        "timezone": body.timezone,
        "device_type": body.device_type,
        "os": body.os,
        "user_agent": ua,
        "viewport": viewport,
        "is_mobile": is_mobile,
        "has_touch": bool(body.has_touch or is_mobile),
        "device_scale_factor": float(body.device_scale_factor or (3.0 if is_mobile else 1.0)),
        "locale": body.locale,
        "accept_language": body.accept_language,
        "proxy": body.proxy.dict() if hasattr(body.proxy, "dict") else dict(body.proxy or {}),
        "anti_detect": body.anti_detect.dict() if hasattr(body.anti_detect, "dict") else dict(body.anti_detect or {}),
        "referrer": body.referrer.dict() if hasattr(body.referrer, "dict") else dict(body.referrer or {}),
        "tags": body.tags or [],
        "start_url": body.start_url,
        "storage_state": {},   # cookies + localStorage persisted by desktop client
        "fingerprint_hash": "",  # set by desktop client on first launch
        "session_id": "",        # active session_id when launched
        "status": "idle",        # idle | launching | running | stopped | error
        "last_launched_at": "",
        "last_session_duration_sec": 0,
        "total_launches": 0,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }


def _public_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal-only fields for API responses."""
    d = dict(doc or {})
    d.pop("_id", None)
    # storage_state can be large — return only stats
    ss = d.get("storage_state") or {}
    d["storage_state_stats"] = {
        "has_cookies": bool(ss.get("cookies")),
        "cookie_count": len(ss.get("cookies") or []),
        "origin_count": len(ss.get("origins") or []),
    }
    d.pop("storage_state", None)
    return d


async def _resolve_user(request: Request) -> dict:
    """Module-internal helper — calls the bound get_current_user with the
    incoming request and returns the user dict (or raises 401)."""
    if _GET_USER is None:
        raise HTTPException(status_code=503, detail="Browser Profiles: auth not bound")
    user = await _GET_USER(request)
    if not user or not user.get("id"):
        raise HTTPException(status_code=401, detail="Unauthenticated")
    return user


def _resolve_user_or_401(user: dict) -> str:
    if not user or not user.get("id"):
        raise HTTPException(status_code=401, detail="Unauthenticated")
    return user["id"]


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────
@router.get("/")
async def list_profiles(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
    tag: Optional[str] = None,
):
    """List ALL profiles for the current user."""
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    q: Dict[str, Any] = {"user_id": uid}
    if tag:
        q["tags"] = tag
    cur = _DB.browser_profiles.find(q).sort("updated_at", -1).limit(limit)
    docs = await cur.to_list(length=limit)
    return {"profiles": [_public_view(d) for d in docs], "count": len(docs)}


@router.post("/")
async def create_profile(request: Request, body: ProfileBody):
    """Create a new browser profile."""
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    doc = _profile_doc(uid, body)
    await _DB.browser_profiles.insert_one(doc)
    return {"profile": _public_view(doc), "id": doc["id"]}


@router.get("/{profile_id}")
async def get_profile(request: Request, profile_id: str):
    """Get one profile."""
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    doc = await _DB.browser_profiles.find_one({"id": profile_id, "user_id": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"profile": _public_view(doc)}


@router.put("/{profile_id}")
async def update_profile(request: Request, profile_id: str, body: ProfileBody):
    """Update an existing profile's config (does NOT touch storage_state)."""
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    existing = await _DB.browser_profiles.find_one({"id": profile_id, "user_id": uid})
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")
    new_doc = _profile_doc(uid, body)
    new_doc["id"] = existing["id"]
    new_doc["created_at"] = existing["created_at"]
    new_doc["storage_state"] = existing.get("storage_state") or {}
    new_doc["total_launches"] = existing.get("total_launches", 0)
    new_doc["last_launched_at"] = existing.get("last_launched_at", "")
    new_doc["fingerprint_hash"] = existing.get("fingerprint_hash", "")
    new_doc["updated_at"] = _now_iso()
    await _DB.browser_profiles.replace_one({"id": profile_id, "user_id": uid}, new_doc)
    return {"profile": _public_view(new_doc)}


@router.delete("/{profile_id}")
async def delete_profile(request: Request, profile_id: str):
    """Delete a profile + any related sessions."""
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    res = await _DB.browser_profiles.delete_one({"id": profile_id, "user_id": uid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    await _DB.browser_profile_sessions.delete_many({"profile_id": profile_id, "user_id": uid})
    return {"deleted": True}


@router.post("/{profile_id}/clone")
async def clone_profile(request: Request, profile_id: str):
    """Duplicate a profile with a new id + ' (copy)' suffix."""
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    existing = await _DB.browser_profiles.find_one({"id": profile_id, "user_id": uid})
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")
    new_doc = dict(existing)
    new_doc.pop("_id", None)
    new_doc["id"] = str(uuid.uuid4())
    new_doc["name"] = (existing.get("name") or "Profile") + " (copy)"
    new_doc["storage_state"] = {}
    new_doc["fingerprint_hash"] = ""
    new_doc["total_launches"] = 0
    new_doc["last_launched_at"] = ""
    new_doc["status"] = "idle"
    new_doc["created_at"] = _now_iso()
    new_doc["updated_at"] = _now_iso()
    await _DB.browser_profiles.insert_one(new_doc)
    return {"profile": _public_view(new_doc), "id": new_doc["id"]}


@router.post("/{profile_id}/launch")
async def launch_profile(request: Request, profile_id: str,
                          start_url: Optional[str] = Body(default=None, embed=True)):
    """Queue a launch job for the customer's local desktop client."""
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    doc = await _DB.browser_profiles.find_one({"id": profile_id, "user_id": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="Profile not found")

    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "profile_id": profile_id,
        "user_id": uid,
        "started_at": _now_iso(),
        "status": "queued",
        "start_url": start_url or doc.get("start_url") or "https://www.google.com/",
    }
    await _DB.browser_profile_sessions.insert_one(session)

    await _DB.browser_profiles.update_one(
        {"id": profile_id, "user_id": uid},
        {"$set": {"status": "launching", "session_id": session_id,
                  "last_launched_at": _now_iso()},
         "$inc": {"total_launches": 1}},
    )

    bridge_job_id: Optional[str] = None
    desktop_available = False
    if _BRIDGE_QUEUE is not None:
        try:
            bridge_payload = {
                "kind": "browser_profile_launch",
                "user_id": uid,
                "profile_id": profile_id,
                "session_id": session_id,
                "profile_config": doc,
                "start_url": session["start_url"],
                "queued_at": _now_iso(),
            }
            bridge_job_id = await _BRIDGE_QUEUE(uid, bridge_payload)
            desktop_available = bool(bridge_job_id)
        except Exception as e:
            logger.warning(f"bridge enqueue failed: {e}")

    return {
        "session_id": session_id,
        "bridge_job_id": bridge_job_id,
        "desktop_available": desktop_available,
        "message": (
            "Launch queued — your Krexion desktop app will open the browser shortly."
            if desktop_available else
            "Profile is configured but launching requires the Krexion desktop app. "
            "Install or start it, then click Launch again."
        ),
        "profile": _public_view(doc),
    }


@router.post("/{profile_id}/stop")
async def stop_profile(request: Request, profile_id: str):
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    doc = await _DB.browser_profiles.find_one({"id": profile_id, "user_id": uid})
    if not doc:
        raise HTTPException(status_code=404, detail="Profile not found")
    sid = doc.get("session_id") or ""

    # Push a stop bridge job to the desktop so the headed browser closes
    if _BRIDGE_QUEUE is not None and sid:
        try:
            await _BRIDGE_QUEUE(uid, {
                "kind": "browser_profile_stop",
                "user_id": uid,
                "profile_id": profile_id,
                "session_id": sid,
                "feature_override": "browser-profile/stop",
            })
        except Exception as e:
            logger.warning(f"stop bridge enqueue failed: {e}")

    await _DB.browser_profiles.update_one(
        {"id": profile_id, "user_id": uid},
        {"$set": {"status": "stopped", "session_id": ""}},
    )
    await _DB.browser_profile_sessions.update_many(
        {"profile_id": profile_id, "user_id": uid, "status": {"$in": ["queued", "running"]}},
        {"$set": {"status": "stopped", "ended_at": _now_iso()}},
    )
    return {"stopped": True}


@router.get("/{profile_id}/status")
async def get_status(request: Request, profile_id: str):
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    doc = await _DB.browser_profiles.find_one(
        {"id": profile_id, "user_id": uid},
        {"id": 1, "status": 1, "session_id": 1, "last_launched_at": 1, "total_launches": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Profile not found")
    doc.pop("_id", None)
    return {"status": doc.get("status", "idle"),
            "session_id": doc.get("session_id", ""),
            "total_launches": doc.get("total_launches", 0),
            "last_launched_at": doc.get("last_launched_at", "")}


@router.post("/import-bulk")
async def import_bulk(request: Request, body: BulkCreateBody):
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    docs: List[Dict[str, Any]] = []
    pad = max(2, len(str(body.count)))
    for i in range(1, body.count + 1):
        profile_body = body.base.copy(deep=True) if hasattr(body.base, "copy") else body.base
        profile_body.name = f"{body.name_prefix} {str(i).zfill(pad)}"
        if body.randomize_ua:
            profile_body.user_agent = _gen_random_ua(profile_body.is_mobile or profile_body.device_type == "mobile")
        if body.randomize_viewport:
            profile_body.viewport = _gen_random_viewport(profile_body.is_mobile or profile_body.device_type == "mobile")
        doc = _profile_doc(uid, profile_body)
        docs.append(doc)
    if docs:
        await _DB.browser_profiles.insert_many(docs)
    return {"created": len(docs), "profiles": [_public_view(d) for d in docs]}


@router.get("/export/all")
async def export_all(request: Request):
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    cur = _DB.browser_profiles.find({"user_id": uid})
    docs = await cur.to_list(length=2000)
    out: List[Dict[str, Any]] = []
    for d in docs:
        d.pop("_id", None)
        d.pop("storage_state", None)
        out.append(d)
    return {"profiles": out, "count": len(out), "exported_at": _now_iso()}


@router.post("/quick-generate")
async def quick_generate(request: Request, body: Dict[str, Any] = Body(default_factory=dict)):
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    name = str(body.get("name") or "").strip() or f"Profile {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    country = str(body.get("country") or "us").lower()
    device_type = str(body.get("device_type") or "desktop").lower()
    is_mobile = device_type == "mobile"
    pb = ProfileBody(
        name=name,
        country=country,
        device_type=device_type,
        is_mobile=is_mobile,
        has_touch=is_mobile,
        device_scale_factor=3.0 if is_mobile else 1.0,
        user_agent=_gen_random_ua(is_mobile),
        viewport=_gen_random_viewport(is_mobile),
        os="ios" if is_mobile else "windows",
        anti_detect=AntiDetectConfig(master=True),
    )
    doc = _profile_doc(uid, pb)
    await _DB.browser_profiles.insert_one(doc)
    return {"profile": _public_view(doc), "id": doc["id"]}


@router.post("/_bridge/session-update")
async def bridge_session_update(request: Request, body: Dict[str, Any] = Body(...)):
    user = await _resolve_user(request)
    uid = _resolve_user_or_401(user)
    pid = str(body.get("profile_id") or "")
    sid = str(body.get("session_id") or "")
    status = str(body.get("status") or "running").lower()
    if not pid or not sid:
        raise HTTPException(status_code=400, detail="profile_id + session_id required")

    update: Dict[str, Any] = {"status": status}
    if status in ("closed", "stopped", "error"):
        update["session_id"] = ""
        update["status"] = "idle" if status == "closed" else status
    if "storage_state" in body and isinstance(body["storage_state"], dict):
        update["storage_state"] = body["storage_state"]
    if "fingerprint_hash" in body:
        update["fingerprint_hash"] = str(body["fingerprint_hash"])[:128]
    if "duration_sec" in body:
        try:
            update["last_session_duration_sec"] = float(body["duration_sec"])
        except Exception:
            pass

    await _DB.browser_profiles.update_one(
        {"id": pid, "user_id": uid}, {"$set": update}
    )
    await _DB.browser_profile_sessions.update_one(
        {"id": sid, "user_id": uid},
        {"$set": {"status": status,
                  "ended_at": _now_iso() if status in ("closed", "stopped", "error") else "",
                  "duration_sec": float(body.get("duration_sec") or 0)}},
    )
    return {"ok": True}


__all__ = ["router", "_bind"]
