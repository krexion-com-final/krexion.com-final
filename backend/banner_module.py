"""
Krexion — Banner / Announcement module
======================================

Admin can post promotional banners (discounts, offers, updates) that
customers see on their dashboard. Supports:
  • Multiple active banners (priority-ordered)
  • Color theme (info / success / warning / promo / danger)
  • Optional CTA button (label + URL)
  • Optional start/end dates (auto show/hide)
  • Dismissible flag (per-user dismissal stored in localStorage on frontend)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# We build the router LATER inside `_bind` so we can wire the auth
# dependency function the server uses (`get_current_admin`).
_state: Dict[str, Any] = {
    "db": None,
    "router": None,
}


def _doc_to_dict(doc: dict) -> dict:
    if not doc:
        return {}
    doc.pop("_id", None)
    return doc


def _is_visible_now(banner: dict) -> bool:
    if not banner.get("is_active", True):
        return False
    now = datetime.now(timezone.utc)
    s = banner.get("starts_at")
    e = banner.get("ends_at")
    try:
        if s:
            sd = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
            if sd > now:
                return False
        if e:
            ed = datetime.fromisoformat(str(e).replace("Z", "+00:00"))
            if ed < now:
                return False
    except Exception:
        pass
    return True


# ── Models ────────────────────────────────────────────────────────────
class BannerCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    theme: str = Field(default="info")
    cta_label: Optional[str] = Field(default=None, max_length=40)
    cta_url: Optional[str] = Field(default=None, max_length=500)
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    is_active: bool = True
    priority: int = 0
    dismissible: bool = True
    show_on_pages: List[str] = Field(default_factory=list)


class BannerUpdate(BaseModel):
    message: Optional[str] = Field(default=None, max_length=500)
    theme: Optional[str] = None
    cta_label: Optional[str] = Field(default=None, max_length=40)
    cta_url: Optional[str] = Field(default=None, max_length=500)
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    dismissible: Optional[bool] = None
    show_on_pages: Optional[List[str]] = None


def build_router(get_current_admin):
    """Build router with admin auth wired in."""
    router = APIRouter(prefix="/api", tags=["banners"])

    @router.post("/admin/banners")
    async def create_banner(payload: BannerCreate, _admin=Depends(get_current_admin)):
        db = _state["db"]
        if db is None:
            raise HTTPException(status_code=500, detail="DB not bound")
        now_iso = datetime.now(timezone.utc).isoformat()
        doc = payload.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        await db.banners.insert_one(doc.copy())
        return _doc_to_dict(doc)

    @router.get("/admin/banners")
    async def list_banners_admin(_admin=Depends(get_current_admin)):
        db = _state["db"]
        if db is None:
            raise HTTPException(status_code=500, detail="DB not bound")
        cursor = db.banners.find({}, {"_id": 0}).sort([("priority", -1), ("created_at", -1)])
        return await cursor.to_list(length=500)

    @router.patch("/admin/banners/{banner_id}")
    async def update_banner(banner_id: str, payload: BannerUpdate, _admin=Depends(get_current_admin)):
        db = _state["db"]
        if db is None:
            raise HTTPException(status_code=500, detail="DB not bound")
        updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await db.banners.update_one({"id": banner_id}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Banner not found")
        doc = await db.banners.find_one({"id": banner_id}, {"_id": 0})
        return doc

    @router.delete("/admin/banners/{banner_id}")
    async def delete_banner(banner_id: str, _admin=Depends(get_current_admin)):
        db = _state["db"]
        if db is None:
            raise HTTPException(status_code=500, detail="DB not bound")
        r = await db.banners.delete_one({"id": banner_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Banner not found")
        return {"deleted": True, "id": banner_id}

    # Public (no-auth) endpoint — banners shown to anyone
    @router.get("/banners/active")
    async def active_banners():
        db = _state["db"]
        if db is None:
            raise HTTPException(status_code=500, detail="DB not bound")
        cursor = db.banners.find({"is_active": True}, {"_id": 0}).sort(
            [("priority", -1), ("created_at", -1)]
        )
        all_active = await cursor.to_list(length=200)
        visible = [b for b in all_active if _is_visible_now(b)]
        return visible

    return router


def _bind(*, main_db, get_current_admin):
    _state["db"] = main_db
    router = build_router(get_current_admin)
    _state["router"] = router
    return router
