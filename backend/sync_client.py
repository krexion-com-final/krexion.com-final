"""
Krexion - Local Sync Client (runs only on customer's PC, KREXION_MODE=local)
============================================================================
Background daemon that talks to the cloud edge at KREXION_CLOUD_URL
(default https://krexion.com) every SYNC_INTERVAL seconds:

  1. Heartbeat        - "I'm online" + RAM/CPU info for load tuning
  2. Push links       - cloud's /r/xxx redirects know about our links
  3. Pull clicks      - drain clicks the cloud captured while we were offline
  4. Pull bridge jobs - heavy features (proxy check, RUT, form filler)
                        queued on the cloud get executed locally

Auth: customer's `LICENSE_KEY` env var, sent in X-Krexion-License header.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CLOUD_URL = (os.environ.get("KREXION_CLOUD_URL") or "").rstrip("/")
LICENSE_KEY = (os.environ.get("LICENSE_KEY") or "").strip()
SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL_SEC", "30") or 30)
KREXION_MODE = (os.environ.get("KREXION_MODE") or "local").lower().strip()
# Bridge-job pulling cycles faster than the main sync loop so heavy
# features feel responsive (user clicks proxy-check on krexion.com cloud
# UI → max ~5s before local PC picks it up).
JOB_PULL_INTERVAL = int(os.environ.get("BRIDGE_JOB_PULL_SEC", "5") or 5)
LOCAL_API_BASE = (os.environ.get("LOCAL_API_BASE") or "http://localhost:8001").rstrip("/")

_running = False


def _headers() -> dict:
    return {
        "X-Krexion-License": LICENSE_KEY,
        "Content-Type": "application/json",
        "User-Agent": "Krexion-Local/1.1.0",
    }


def _hardware_info() -> dict:
    """Detect customer PC hardware so the cloud knows how much load it
    can route to this machine. RAM/cores -> recommended concurrency."""
    info: dict = {}
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        info["ram_gb"] = round(vm.total / (1024 ** 3), 1)
        info["cpu_cores"] = psutil.cpu_count(logical=True) or 1
    except Exception:
        pass
    # Recommended concurrency:
    #   - At minimum 8
    #   - About 16 parallel per 8GB of RAM
    #   - Capped at 256 (anything more saturates an average residential link)
    ram_gb = info.get("ram_gb", 8) or 8
    info["recommended_concurrency"] = max(8, min(256, int(ram_gb * 16 / 8)))
    return info


async def _heartbeat() -> None:
    try:
        body = {
            "hostname": socket.gethostname(),
            "version": "1.1.0",
            "platform": "docker",
        }
        body.update(_hardware_info())
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                f"{CLOUD_URL}/api/sync/heartbeat",
                json=body,
                headers=_headers(),
            )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[sync] heartbeat failed: {e}")


async def _push_links(user_db: Any) -> int:
    try:
        links = await user_db.links.find(
            {"status": "active"}, {"_id": 0}
        ).limit(2000).to_list(2000)
        if not links:
            return 0
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{CLOUD_URL}/api/sync/links",
                json={"links": links},
                headers=_headers(),
            )
            if r.status_code == 200:
                return int(r.json().get("upserted", 0))
            logger.warning(f"[sync] push_links {r.status_code}: {r.text[:200]}")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[sync] push_links error: {e}")
    return 0


async def _pull_clicks(user_db: Any) -> int:
    try:
        meta = await user_db.cloud_sync_meta.find_one({"key": "last_click_pull"}) or {}
        since = meta.get("ts", "")
        total = 0
        for _ in range(10):  # max 10 batches per cycle = 5000 clicks
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(
                    f"{CLOUD_URL}/api/sync/clicks/pull",
                    params={"since": since, "limit": 500},
                    headers=_headers(),
                )
                if r.status_code != 200:
                    logger.warning(f"[sync] pull {r.status_code}: {r.text[:200]}")
                    break
                data = r.json()
                clicks = data.get("clicks") or []
                if not clicks:
                    break
                ack_ids = []
                for c in clicks:
                    cid = c.get("id")
                    if not cid:
                        continue
                    try:
                        await user_db.clicks.update_one(
                            {"id": cid},
                            {"$setOnInsert": c},
                            upsert=True,
                        )
                        ack_ids.append(cid)
                    except Exception as e:  # noqa: BLE001
                        logger.debug(f"[sync] insert click {cid}: {e}")
                last_ts = clicks[-1].get("created_at") or clicks[-1].get("timestamp") or since
                await user_db.cloud_sync_meta.update_one(
                    {"key": "last_click_pull"},
                    {"$set": {"key": "last_click_pull", "ts": last_ts}},
                    upsert=True,
                )
                if ack_ids:
                    try:
                        await client.post(
                            f"{CLOUD_URL}/api/sync/clicks/ack",
                            json={"click_ids": ack_ids},
                            headers=_headers(),
                        )
                    except Exception:  # noqa: BLE001
                        pass
                total += len(clicks)
                since = last_ts
                if not data.get("has_more"):
                    break
        return total
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[sync] pull_clicks error: {e}")
    return 0


# ─────────────────────────────────────────────────────────────────────
# BRIDGE: pull pending heavy-feature jobs from the cloud and execute
# them locally against this install's own backend.
# ─────────────────────────────────────────────────────────────────────
async def _execute_job_locally(job: dict, jwt_token: str | None = None) -> dict:
    """Run the job's feature against the local backend. Returns a result
    dict ready to POST back to the cloud."""
    feature = job.get("feature") or ""
    payload = job.get("payload") or {}

    # Map feature name to local backend route
    # Format: METHOD /api/<route>
    feature_routes = {
        "proxies/bulk-test": ("POST", "/api/proxies/bulk-test"),
        "proxies/test-single": ("POST", "/api/proxies/test-single"),
        "rut/start": ("POST", "/api/rut/start"),
        "rut/status": ("GET", "/api/rut/status"),
        "form-filler/start": ("POST", "/api/form-filler/start"),
        "form-filler/status": ("GET", "/api/form-filler/status"),
    }
    if feature not in feature_routes:
        return {"status": "failed", "error": f"unknown feature: {feature}"}

    method, route = feature_routes[feature]
    url = f"{LOCAL_API_BASE}{route}"
    headers = {"Content-Type": "application/json"}
    # Forward the user's JWT if we have one cached, otherwise rely on local
    # license-key based auth fallback (most local endpoints accept either)
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    headers["X-Krexion-License"] = LICENSE_KEY
    headers["X-Krexion-Bridge-Job"] = job.get("id", "")

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            if method == "POST":
                r = await client.post(url, json=payload, headers=headers)
            else:
                r = await client.get(url, params=payload, headers=headers)
        if r.status_code < 400:
            try:
                return {"status": "done", "result": r.json()}
            except Exception:
                return {"status": "done", "result": {"text": r.text[:50000]}}
        return {"status": "failed", "error": f"local backend {r.status_code}: {r.text[:500]}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "error": f"local execution error: {e}"}


async def _pull_and_run_jobs() -> int:
    """Pull up to 5 pending jobs from cloud, execute each locally, post
    result back. Returns count of jobs processed."""
    if not (CLOUD_URL and LICENSE_KEY):
        return 0
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{CLOUD_URL}/api/sync/jobs/pull",
                params={"limit": 5, "hostname": socket.gethostname()},
                headers=_headers(),
            )
        if r.status_code != 200:
            return 0
        jobs = (r.json() or {}).get("jobs") or []
        if not jobs:
            return 0
        logger.info(f"[bridge] pulled {len(jobs)} job(s) from cloud")

        async def _run_one(job: dict) -> None:
            result = await _execute_job_locally(job)
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    await client.post(
                        f"{CLOUD_URL}/api/sync/jobs/result",
                        json={"job_id": job.get("id"), **result},
                        headers=_headers(),
                    )
                logger.info(
                    f"[bridge] job {(job.get('id') or '')[:8]} -> {result.get('status')}"
                )
            except Exception as e:  # noqa: BLE001
                logger.debug(f"[bridge] result post failed: {e}")

        await asyncio.gather(*[_run_one(j) for j in jobs], return_exceptions=True)
        return len(jobs)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[bridge] pull/run cycle failed: {e}")
        return 0


async def _bridge_loop() -> None:
    """Faster cycle dedicated to bridge job pulling for responsive UX."""
    global _running
    while _running:
        try:
            if LICENSE_KEY:
                await _pull_and_run_jobs()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[bridge] loop error: {e}")
        await asyncio.sleep(JOB_PULL_INTERVAL)


async def _sync_loop(main_db, get_db_for_user) -> None:
    global _running, LICENSE_KEY
    _running = True
    logger.info(
        f"[sync] daemon started - cloud={CLOUD_URL}, interval={SYNC_INTERVAL}s, "
        f"bridge_pull={JOB_PULL_INTERVAL}s"
    )

    while _running:
        try:
            if not LICENSE_KEY:
                try:
                    lic_doc = await main_db.licenses.find_one(
                        {"status": {"$in": ["active", "issued"]}},
                        sort=[("created_at", -1)],
                        projection={"_id": 0, "license_key": 1},
                    )
                    if lic_doc and lic_doc.get("license_key"):
                        LICENSE_KEY = lic_doc["license_key"]
                        logger.info(f"[sync] license key resolved from DB ({LICENSE_KEY[:12]}...)")
                except Exception:
                    pass

            if not LICENSE_KEY:
                await asyncio.sleep(SYNC_INTERVAL)
                continue

            await _heartbeat()

            lic = await main_db.licenses.find_one(
                {"license_key": LICENSE_KEY}, {"_id": 0}
            )
            if lic:
                user = await main_db.users.find_one(
                    {"email": lic["email"]}, {"_id": 0}
                )
                if user:
                    user_db = get_db_for_user(user)
                    pushed = await _push_links(user_db)
                    pulled = await _pull_clicks(user_db)
                    if pushed or pulled:
                        logger.info(
                            f"[sync] cycle ok - pushed={pushed} pulled={pulled}"
                        )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[sync] loop error: {e}")

        await asyncio.sleep(SYNC_INTERVAL)


def start_if_local(main_db, get_db_for_user) -> bool:
    """Called from server.py on startup. No-op if not configured for sync."""
    if KREXION_MODE != "local":
        logger.info("[sync] disabled - KREXION_MODE != local")
        return False
    if not CLOUD_URL:
        logger.info("[sync] disabled - missing KREXION_CLOUD_URL")
        return False
    try:
        asyncio.create_task(_sync_loop(main_db, get_db_for_user))
        asyncio.create_task(_bridge_loop())
        if not LICENSE_KEY:
            logger.info(
                "[sync] no LICENSE_KEY env - daemon will pick it up from "
                "the licenses collection once the user activates."
            )
        return True
    except RuntimeError:
        logger.warning("[sync] no running loop - schedule from startup event")
        return False
