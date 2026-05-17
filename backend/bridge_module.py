"""
Krexion - Bridge Module (Cloud-Orchestrated Local Execution)
=============================================================

When a user is logged into the krexion.com cloud dashboard and clicks a
HEAVY feature (proxy bulk-test, RUT, form filler, visual recorder), this
module:

  1. Detects whether their local PC install is online (heartbeat < 90s).
  2. If ONLINE → enqueues the job into Mongo collection `bridge_jobs`,
     returns 202 + job_id to the frontend.
  3. If OFFLINE → returns 503 with a friendly "turn on your PC" message.

The local PC's sync_client.py pulls pending jobs every ~5s, executes
them against its own local backend, and posts the result back. The
frontend polls /api/bridge/jobs/{id} for the final result.

This means:
  - UI stays on krexion.com (no redirect to localhost)
  - Heavy CPU/RAM load runs on the customer's own machine
  - Cloud server stays light (just orchestrates)
  - Light features (links, clicks DB, redirects) stay 100% cloud
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

logger = logging.getLogger(__name__)

bridge_router = APIRouter(prefix="/api/bridge", tags=["bridge"])
bridge_sync_router = APIRouter(prefix="/api/sync", tags=["bridge-sync"])

# Bound by server.py on startup
_db: Any = None
_get_current_user: Any = None
_validate_license: Any = None

# Online threshold - heartbeat must be within this many seconds.
ONLINE_WINDOW_SEC = int(os.environ.get("BRIDGE_ONLINE_WINDOW_SEC", "90") or 90)

# How long a job can stay pending before we give up and tell the user.
JOB_TIMEOUT_SEC = int(os.environ.get("BRIDGE_JOB_TIMEOUT_SEC", "1800") or 1800)


def _bind(*, main_db, get_current_user, validate_license) -> None:
    global _db, _get_current_user, _validate_license
    _db = main_db
    _get_current_user = get_current_user
    _validate_license = validate_license


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


# ─────────────────────────────────────────────────────────────────────
# Helpers used by server.py heavy endpoints
# ─────────────────────────────────────────────────────────────────────
async def is_user_local_online(user_id: str) -> dict:
    """Returns {online: bool, hostname, ram_gb, last_seen_sec_ago}."""
    hb = await _db.sync_heartbeats.find_one({"user_id": user_id}, {"_id": 0})
    if not hb or not hb.get("last_seen"):
        return {"online": False, "reason": "no_heartbeat_ever"}
    try:
        last = datetime.fromisoformat(str(hb["last_seen"]).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return {"online": False, "reason": "bad_heartbeat_ts"}
    age = (_now() - last).total_seconds()
    online = age <= ONLINE_WINDOW_SEC
    return {
        "online": online,
        "hostname": hb.get("hostname") or "",
        "ram_gb": hb.get("ram_gb"),
        "cpu_cores": hb.get("cpu_cores"),
        "platform": hb.get("platform") or "",
        "version": hb.get("version") or "",
        "last_seen": hb.get("last_seen"),
        "last_seen_sec_ago": int(age),
        "reason": None if online else "stale_heartbeat",
    }


async def enqueue_bridge_job(
    user: dict,
    feature: str,
    payload: dict,
    *,
    wait_for_result: bool = False,
    wait_timeout: int = 25,
) -> dict:
    """Create a pending job for the user's local PC to execute.

    If `wait_for_result` is True we wait inline up to `wait_timeout`s for the
    local worker to complete the job (so the frontend gets a synchronous
    response for short jobs). Otherwise returns {job_id, status:'pending'}
    and the frontend polls /api/bridge/jobs/{id}.
    """
    status = await is_user_local_online(user["id"])
    if not status["online"]:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "local_pc_offline",
                "message": (
                    "Aap ka Krexion PC offline hai. Heavy features (proxy "
                    "check, RUT, form filler) tab kaam karte hain jab aap "
                    "ka PC on ho aur Krexion chal raha ho. PC on karein, "
                    "Krexion automatically connect ho jayega."
                ),
                "local_status": status,
            },
        )

    job_id = uuid.uuid4().hex
    now_iso = _now_iso()
    doc = {
        "id": job_id,
        "user_id": user["id"],
        "email": user.get("email"),
        "feature": feature,
        "payload": payload,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": now_iso,
        "started_at": None,
        "completed_at": None,
        "claimed_by": None,
    }
    await _db.bridge_jobs.insert_one(doc)
    logger.info(f"[bridge] enqueued job {job_id[:8]} feature={feature} user={user.get('email')}")

    if not wait_for_result:
        # Return without _id from MongoDB
        doc_clean = {k: v for k, v in doc.items() if k != "_id"}
        return {"job_id": job_id, "status": "pending", "local": status, "job": doc_clean}

    # Inline poll for short jobs
    deadline = asyncio.get_event_loop().time() + wait_timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.5)
        j = await _db.bridge_jobs.find_one({"id": job_id}, {"_id": 0})
        if j and j.get("status") in ("done", "failed"):
            return {"job_id": job_id, "status": j["status"], "result": j.get("result"), "error": j.get("error")}
    return {"job_id": job_id, "status": "pending", "local": status, "timeout": True}


# ─────────────────────────────────────────────────────────────────────
# Frontend-facing endpoints — REGISTERED FROM server.py
# (server.py has direct access to its JWT get_current_user dependency)
# Helper functions used by those routes are below.
# ─────────────────────────────────────────────────────────────────────
async def get_my_local_status_for(user_id: str) -> dict:
    return await is_user_local_online(user_id)


async def get_my_job(job_id: str, user_id: str) -> dict:
    j = await _db.bridge_jobs.find_one({"id": job_id, "user_id": user_id}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    if j.get("status") == "pending":
        try:
            created = datetime.fromisoformat(str(j["created_at"]).replace("Z", "+00:00"))
            if (_now() - created).total_seconds() > JOB_TIMEOUT_SEC:
                await _db.bridge_jobs.update_one(
                    {"id": job_id},
                    {"$set": {"status": "failed", "error": "timeout: local PC did not pick up job", "completed_at": _now_iso()}},
                )
                j["status"] = "failed"
                j["error"] = "timeout: local PC did not pick up job"
        except Exception:
            pass
    return j


async def list_jobs_for(user_id: str, limit: int = 50) -> list:
    cursor = _db.bridge_jobs.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(min(limit, 200))
    return await cursor.to_list(200)


# ─────────────────────────────────────────────────────────────────────
# Local-worker endpoints (auth = X-Krexion-License)
# ─────────────────────────────────────────────────────────────────────
@bridge_sync_router.get("/jobs/pull")
async def worker_pull_jobs(
    request: Request,
    x_krexion_license: Optional[str] = Header(None),
    limit: int = 5,
    hostname: Optional[str] = None,
):
    """Local sync_client pulls up to `limit` pending jobs for its user.
    Marks them as 'running' so other workers (if any) don't double-run."""
    if _validate_license is None:
        raise HTTPException(status_code=500, detail="Bridge not initialised")
    lic, user = await _validate_license(x_krexion_license)
    limit = max(1, min(limit, 20))

    claimed = []
    for _ in range(limit):
        # Atomic find-and-claim
        doc = await _db.bridge_jobs.find_one_and_update(
            {"user_id": user["id"], "status": "pending"},
            {
                "$set": {
                    "status": "running",
                    "started_at": _now_iso(),
                    "claimed_by": (hostname or "")[:120],
                }
            },
            sort=[("created_at", 1)],
            projection={"_id": 0},
        )
        if not doc:
            break
        claimed.append(doc)
    return {"jobs": claimed, "server_time": _now_iso()}


@bridge_sync_router.post("/jobs/result")
async def worker_post_result(
    body: dict,
    x_krexion_license: Optional[str] = Header(None),
):
    if _validate_license is None:
        raise HTTPException(status_code=500, detail="Bridge not initialised")
    lic, user = await _validate_license(x_krexion_license)
    job_id = body.get("job_id")
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id required")
    update = {
        "$set": {
            "status": body.get("status", "done"),
            "result": body.get("result"),
            "error": body.get("error"),
            "completed_at": _now_iso(),
        }
    }
    res = await _db.bridge_jobs.update_one(
        {"id": job_id, "user_id": user["id"], "status": {"$in": ["running", "pending"]}},
        update,
    )
    return {"updated": res.modified_count}
