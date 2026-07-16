"""
Krexion — Traffic Source Presets (user-saved) module
=====================================================
2026-07 — v2.6.7 Task: allow each customer to customise the built-in
Traffic Source Preset (Social Media Ads / Search Engine Ads / …) and
save their customised configuration as a NAMED preset they can pick
next time — exactly like saved JSON automation profiles.

Storage
-------
MongoDB collection `traffic_source_presets` — one doc per saved preset.
Documents are scoped by `user_id` so each account sees only its own
presets.

Schema
------
{
  "id":            "<uuid>",
  "user_id":       "<user uuid>",
  "name":          "My TikTok-Only",
  "base_preset":   "social_media_ads",
  "config":        { …the resolved RUT config dict… },
  "created_at":    "2026-07-16T20:45:00Z",
  "updated_at":    "2026-07-16T20:45:00Z"
}

The `config` payload is opaque to the backend — whatever the frontend
sends is stored verbatim and returned verbatim. This keeps the backend
forward-compatible with new frontend fields (weights, source URL,
per-platform sub-options) without needing a schema migration for every
new toggle.

Endpoints (all under `/api/referrer-pro/my-presets`)
----------------------------------------------------
  GET    /                → list current user's saved presets
  POST   /                → create a new preset
  PUT    /{preset_id}     → update an existing preset
  DELETE /{preset_id}     → delete a preset
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("traffic_source_presets_module")

router = APIRouter(prefix="/api/referrer-pro/my-presets", tags=["referrer-pro"])

# Bound at import time by server.py
_DB: Any = None
_GET_USER: Any = None


def bind_deps(*, db, get_current_user) -> None:
    global _DB, _GET_USER
    _DB = db
    _GET_USER = get_current_user
    logger.info("Traffic-source-presets module wired — /api/referrer-pro/my-presets/*")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


async def _resolve_user(request: Request) -> Dict[str, Any]:
    if _GET_USER is None:
        raise HTTPException(status_code=503, detail="Traffic presets: auth not bound")
    user = await _GET_USER(request)
    if not user or not (user.get("id") if isinstance(user, dict) else getattr(user, "id", None)):
        raise HTTPException(status_code=401, detail="Unauthenticated")
    return user  # type: ignore[return-value]


def _user_id(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("id") or user.get("user_id") or user.get("email") or "")
    return str(getattr(user, "id", "") or getattr(user, "email", "") or "")


# ── Schemas ────────────────────────────────────────────────────────────
class PresetPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    base_preset: str = Field(..., min_length=1, max_length=64)
    config: Dict[str, Any] = Field(default_factory=dict)


class PresetOut(BaseModel):
    id: str
    name: str
    base_preset: str
    config: Dict[str, Any]
    created_at: str
    updated_at: str


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "name": doc.get("name") or "",
        "base_preset": doc.get("base_preset") or "custom",
        "config": doc.get("config") or {},
        "created_at": doc.get("created_at") or "",
        "updated_at": doc.get("updated_at") or "",
    }


# ── Endpoints ──────────────────────────────────────────────────────────
@router.get("", response_model=List[PresetOut])
async def list_presets(request: Request):
    user = await _resolve_user(request)
    user_id = _user_id(user)
    cursor = _DB.traffic_source_presets.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("updated_at", -1)
    docs = await cursor.to_list(length=200)
    return [_serialize(d) for d in docs]


@router.post("", response_model=PresetOut)
async def create_preset(request: Request, payload: PresetPayload):
    user = await _resolve_user(request)
    user_id = _user_id(user)

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name required")

    existing = await _DB.traffic_source_presets.find_one(
        {"user_id": user_id, "name": name}, {"_id": 0, "id": 1}
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A preset named '{name}' already exists. Rename it or update the existing one.",
        )

    now = _now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": name,
        "base_preset": (payload.base_preset or "custom").strip() or "custom",
        "config": payload.config or {},
        "created_at": now,
        "updated_at": now,
    }
    await _DB.traffic_source_presets.insert_one(doc)
    return _serialize(doc)


@router.put("/{preset_id}", response_model=PresetOut)
async def update_preset(request: Request, preset_id: str, payload: PresetPayload):
    user = await _resolve_user(request)
    user_id = _user_id(user)

    existing = await _DB.traffic_source_presets.find_one(
        {"id": preset_id, "user_id": user_id}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Preset not found")

    new_name = (payload.name or existing.get("name") or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Preset name required")

    if new_name != existing.get("name"):
        clash = await _DB.traffic_source_presets.find_one(
            {"user_id": user_id, "name": new_name, "id": {"$ne": preset_id}},
            {"_id": 0, "id": 1},
        )
        if clash:
            raise HTTPException(
                status_code=409,
                detail=f"A preset named '{new_name}' already exists.",
            )

    updated = {
        "name": new_name,
        "base_preset": (payload.base_preset or existing.get("base_preset") or "custom").strip() or "custom",
        "config": payload.config or {},
        "updated_at": _now_iso(),
    }
    await _DB.traffic_source_presets.update_one(
        {"id": preset_id, "user_id": user_id},
        {"$set": updated},
    )
    merged = {**existing, **updated}
    return _serialize(merged)


@router.delete("/{preset_id}")
async def delete_preset(request: Request, preset_id: str):
    user = await _resolve_user(request)
    user_id = _user_id(user)

    res = await _DB.traffic_source_presets.delete_one(
        {"id": preset_id, "user_id": user_id}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"ok": True, "deleted": preset_id}


__all__ = ["router", "bind_deps"]
