"""
Krexion — Desktop Companion Endpoints
=====================================
Serves the locally-running PyWebView dashboard (desktop/krexion_dashboard.py)
with the live stats it needs to render its widgets.

These endpoints intentionally only do anything meaningful on the
CUSTOMER's local backend (KREXION_MODE=native). On the cloud edge
(krexion.com) they're still mounted — but they return a clear "not
applicable here" payload so any accidental hit from the wrong place
doesn't leak host stats.

Endpoints:

  GET  /api/desktop/stats        Live snapshot for the dashboard
  POST /api/desktop/run-update   Triggers desktop.updater.apply_update()
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("krexion.desktop_module")

# In the NATIVE Windows bundle the `desktop/` package sits at
# {app}/bin/app/desktop and `app/` is on sys.path via python311._pth.
# In the dev container the repo root holds it at /app/desktop. We add
# the repo root once so `from desktop.system_info import ...` succeeds
# in both layouts without an env-var dance.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

desktop_router = APIRouter(prefix="/api/desktop", tags=["desktop"])

# Bound by server.py on startup
_db: Any = None
_get_bridge_stats: Any = None


def _bind(*, main_db, get_bridge_stats=None) -> None:
    global _db, _get_bridge_stats
    _db = main_db
    _get_bridge_stats = get_bridge_stats


# ── Helpers ─────────────────────────────────────────────────────────

def _is_local_mode() -> bool:
    return (os.environ.get("KREXION_MODE") or "local").lower().strip() in {"local", "native"}


def _read_license_summary() -> dict:
    """Best-effort license info read. The desktop dashboard shows it as a
    pure visual indicator — never used for auth decisions here."""
    info = {"active": False, "email": None, "expires_at": None}
    try:
        # Imports kept lazy so the cloud edge (where this module is also
        # loaded) doesn't pull in license_module at import time.
        from license_module import _LICENSE_KEY_CACHE  # type: ignore
        cached = _LICENSE_KEY_CACHE or {}
        if cached:
            info["active"] = bool(cached.get("active", True))
            info["email"] = cached.get("email")
            info["expires_at"] = cached.get("expires_at")
    except Exception:  # noqa: BLE001
        pass
    return info


def _read_version() -> str:
    try:
        return (Path(__file__).parent / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return "0.0.0"


async def _db_health() -> dict:
    """Returns {connected, collections, last_error}. Wraps in a 2 s
    timeout so a dead Mongo never hangs the dashboard."""
    if _db is None:
        return {"connected": False, "collections": 0, "last_error": "db not bound"}
    try:
        names = await asyncio.wait_for(_db.list_collection_names(), timeout=2.0)
        return {"connected": True, "collections": len(names), "last_error": None}
    except Exception as exc:  # noqa: BLE001
        return {"connected": False, "collections": 0, "last_error": str(exc)[:200]}


async def _cloud_link_status() -> dict:
    """Reads the last heartbeat ack time from the sync_client side. On
    local installs `sync_client.py` updates a tiny status file each
    successful heartbeat — we read that here instead of doing an HTTP
    round-trip every 2 s."""
    status_file = Path(os.environ.get("KREXION_SYNC_STATUS_FILE", "/tmp/krexion-sync-status.json"))
    try:
        if status_file.exists():
            d = json.loads(status_file.read_text(encoding="utf-8"))
            last = d.get("last_heartbeat_at")
            if last:
                age_sec = int(time.time() - float(last))
                return {"connected": age_sec < 120, "last_sync_age": age_sec}
    except Exception:  # noqa: BLE001
        pass
    return {"connected": False, "last_sync_age": None}


async def _active_and_recent_jobs() -> dict:
    """Pulls active + recent heavy jobs from the bridge_jobs collection
    (which is what sync_client.py pulls from)."""
    out = {"active": [], "recent": [], "throughput": {"jobs_per_hour": 0, "success_rate_pct": 0}}
    if _db is None:
        return out
    try:
        # 1. Active jobs (running or queued on this PC)
        cursor = _db.bridge_jobs.find(
            {"status": {"$in": ["pending", "running"]}},
            projection={"_id": 0, "kind": 1, "status": 1, "started_at": 1, "created_at": 1, "detail": 1},
            sort=[("created_at", -1)],
            limit=10,
        )
        now = datetime.now(timezone.utc)
        async for doc in cursor:
            start_iso = doc.get("started_at") or doc.get("created_at")
            ago = _humanise_age(start_iso, now)
            out["active"].append({
                "kind": doc.get("kind") or "job",
                "status": doc.get("status") or "running",
                "detail": (doc.get("detail") or "")[:80],
                "started_ago": ago,
            })

        # 2. Recent completed (last 8)
        cursor = _db.bridge_jobs.find(
            {"status": {"$in": ["completed", "failed", "error"]}},
            projection={"_id": 0, "kind": 1, "status": 1, "finished_at": 1, "detail": 1},
            sort=[("finished_at", -1)],
            limit=8,
        )
        async for doc in cursor:
            finished = doc.get("finished_at")
            out["recent"].append({
                "kind": doc.get("kind") or "job",
                "status": doc.get("status") or "completed",
                "detail": (doc.get("detail") or "")[:80],
                "started_ago": _humanise_age(finished, now),
            })

        # 3. Throughput — last hour
        try:
            from datetime import timedelta
            since = now - timedelta(hours=1)
            since_iso = since.isoformat()
            total = await _db.bridge_jobs.count_documents({"finished_at": {"$gte": since_iso}})
            ok = await _db.bridge_jobs.count_documents({
                "finished_at": {"$gte": since_iso}, "status": "completed",
            })
            out["throughput"] = {
                "jobs_per_hour": total,
                "success_rate_pct": (100.0 * ok / total) if total else 0.0,
            }
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"job stats query failed: {exc}")
    return out


def _humanise_age(iso_value, now) -> str:
    if not iso_value:
        return ""
    try:
        if isinstance(iso_value, str):
            ts = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        else:
            ts = iso_value
        delta = (now - ts).total_seconds()
        if delta < 60:
            return f"{int(delta)}s ago"
        if delta < 3600:
            return f"{int(delta // 60)}m ago"
        if delta < 86400:
            return f"{int(delta // 3600)}h ago"
        return f"{int(delta // 86400)}d ago"
    except Exception:  # noqa: BLE001
        return ""


# ── Routes ──────────────────────────────────────────────────────────

@desktop_router.get("/stats")
async def desktop_stats():
    """One-shot snapshot the PyWebView dashboard polls every 2s. We
    keep it heterogeneous (system + license + jobs + cloud-link) so
    the dashboard makes ONE request, not five.
    """
    # Lazy import — keeps the cloud edge clean (system_info is shipped
    # with the desktop bundle, not necessarily present in production
    # Docker containers).
    try:
        from desktop.system_info import get_specs  # type: ignore
        system = get_specs()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"system_info unavailable on this host: {exc}")
        system = {
            "ram_gb": 0, "cpu_cores": 0, "ram_used_gb": 0, "ram_used_pct": 0,
            "cpu_pct": 0, "tier": "unknown", "max_concurrent_heavy_jobs": 2,
            "detected_by": "fallback",
        }

    db_health = await _db_health()
    cloud_link = await _cloud_link_status()
    jobs = await _active_and_recent_jobs() if _is_local_mode() else {
        "active": [], "recent": [],
        "throughput": {"jobs_per_hour": 0, "success_rate_pct": 0},
    }

    return {
        "ok": True,
        "mode": (os.environ.get("KREXION_MODE") or "local").lower(),
        "backend_version": _read_version(),
        "system": system,
        "database": db_health,
        "cloud": cloud_link,
        "license": _read_license_summary(),
        "jobs": jobs,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@desktop_router.post("/run-update")
async def desktop_run_update(request: Request):
    """Triggered when the customer clicks the "Update Now" banner in
    the dashboard. Calls `desktop.updater.apply_update()` which:
      1. Downloads the latest Krexion-Setup.exe to %TEMP%
      2. Launches it with /VERYSILENT /SUPPRESSMSGBOXES
      3. Installer stops services, swaps files, restarts services
    """
    if not _is_local_mode():
        # Refuse on cloud edge — VPS doesn't run an installer
        raise HTTPException(400, "Updates only run on the customer's local install.")

    body = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        pass
    target_version = (body or {}).get("target_version")

    try:
        from desktop.updater import apply_update  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Updater module unavailable: {exc}")

    # apply_update is sync (subprocess + requests) — run in thread pool
    # so we don't block the asyncio loop while downloading 400 MB.
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, apply_update, target_version)
    return result


@desktop_router.get("/specs")
async def desktop_specs():
    """Tiny read-only endpoint a future Settings tab could call. Same
    payload as the `system` block in /stats — exposed separately so the
    settings page can display the install-time specs without polling
    the full live snapshot.

    On the cloud edge (where the `desktop` package isn't mounted into
    the backend Docker container), we degrade gracefully and return a
    fallback payload rather than 500 — the cloud frontend never calls
    this endpoint anyway, but better to be quiet than noisy.
    """
    try:
        from desktop.system_info import get_specs  # type: ignore
        return get_specs()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"system_info unavailable on this host: {exc}")
        return {
            "ram_gb": 0,
            "cpu_cores": 0,
            "ram_used_gb": 0,
            "ram_used_pct": 0,
            "cpu_pct": 0,
            "tier": "unknown",
            "max_concurrent_heavy_jobs": 2,
            "detected_by": "fallback",
            "note": "desktop package not available on this host (cloud edge)",
        }
