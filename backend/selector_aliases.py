"""
Krexion — Selector Aliases (Permanent Memory)
==============================================

Self-healing automation: when the user fixes a wrong selector via the
Visual Recorder Edit modal (e.g. `#birth_month` → `#dob_month`), we
remember that mapping FOREVER for that user + domain. Future replays
(Live Test or RUT job) silently fall back to the alias when the
original selector fails — so a recording made 6 months ago keeps
working even after the target website renames its form fields.

Storage: MongoDB collection `selector_aliases`, one document per
(user_id, domain, original_selector). The `aliases` field is a list
so a single original can map to multiple historical renames (most
recent first; capped at 10).

Document shape:
  {
    user_id: str,
    domain: str,             # normalised host (lowercased, www. stripped)
    original: str,           # the failing selector
    aliases: [str, ...],     # alternative selectors to try (newest first)
    created_at: ISO datetime,
    updated_at: ISO datetime,
    hit_count: int,          # how many times an alias actually rescued a step
    last_used_at: ISO datetime | None,
    last_alias_used: str | None,
  }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Bound from server.py at startup via _bind()
_db: Any = None
COLLECTION = "selector_aliases"


def _bind(db: Any) -> None:
    """Wire the MongoDB handle from server.py."""
    global _db
    _db = db


def extract_domain(url: str) -> str:
    """Normalised domain extraction. `https://www.example.com/foo` → `example.com`.
    Returns "" for invalid / empty input."""
    if not url:
        return ""
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


async def save_alias(user_id: str, domain: str, original: str, alias: str) -> bool:
    """Upsert an alias mapping. If `original` already has aliases, the
    new one is pushed to the FRONT of the list (most-recent-first) and
    duplicates are removed first so we don't grow unbounded."""
    if _db is None or not user_id or not domain or not original or not alias:
        return False
    if original.strip() == alias.strip():
        return False

    now = datetime.now(timezone.utc).isoformat()
    coll = _db[COLLECTION]
    try:
        # Remove existing same-alias entry so it gets re-pushed to front
        await coll.update_one(
            {"user_id": user_id, "domain": domain, "original": original},
            {"$pull": {"aliases": alias}},
        )
        await coll.update_one(
            {"user_id": user_id, "domain": domain, "original": original},
            {
                "$push": {"aliases": {"$each": [alias], "$position": 0, "$slice": 10}},
                "$set": {"updated_at": now},
                "$setOnInsert": {"created_at": now, "hit_count": 0},
            },
            upsert=True,
        )
        logger.info(f"[selector_aliases] saved: user={user_id[:8]} domain={domain} {original} → {alias}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[selector_aliases] save failed: {e}")
        return False


async def get_aliases_for_domain(user_id: str, domain: str) -> Dict[str, List[str]]:
    """Return all alias mappings for a user+domain as {original: [aliases]}.
    Called at the start of a replay to pre-build the fallback map."""
    if _db is None or not user_id or not domain:
        return {}
    try:
        cursor = _db[COLLECTION].find({"user_id": user_id, "domain": domain})
        out: Dict[str, List[str]] = {}
        async for doc in cursor:
            o = doc.get("original")
            a = doc.get("aliases") or []
            if o and a:
                out[o] = list(a)
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[selector_aliases] load failed: {e}")
        return {}


async def record_hit(user_id: str, domain: str, original: str, alias_used: str) -> None:
    """Bump hit_count + last_used when an alias actually rescued a step
    during replay. Best-effort, never raises."""
    if _db is None or not user_id or not domain or not original:
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        await _db[COLLECTION].update_one(
            {"user_id": user_id, "domain": domain, "original": original},
            {
                "$inc": {"hit_count": 1},
                "$set": {"last_used_at": now, "last_alias_used": alias_used},
            },
        )
    except Exception:  # noqa: BLE001
        pass


async def list_all_for_user(user_id: str) -> List[Dict[str, Any]]:
    """Return every alias mapping owned by `user_id`, sorted by domain.
    Powers an optional settings UI page where the user can review /
    delete their aliases."""
    if _db is None or not user_id:
        return []
    try:
        cursor = _db[COLLECTION].find({"user_id": user_id})
        items: List[Dict[str, Any]] = []
        async for doc in cursor:
            doc["_id"] = str(doc.get("_id"))
            items.append(doc)
        items.sort(key=lambda d: (d.get("domain", ""), d.get("original", "")))
        return items
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[selector_aliases] list failed: {e}")
        return []


async def delete_alias(user_id: str, domain: str, original: str) -> bool:
    """Hard-delete a single alias mapping (used by the settings UI)."""
    if _db is None or not user_id or not domain or not original:
        return False
    try:
        r = await _db[COLLECTION].delete_one(
            {"user_id": user_id, "domain": domain, "original": original}
        )
        return r.deleted_count > 0
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[selector_aliases] delete failed: {e}")
        return False
