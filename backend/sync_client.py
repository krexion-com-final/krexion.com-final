"""
Krexion — Local Sync Client (runs only on customer's PC, KREXION_MODE=local)
============================================================================
Runs in the background of the local Krexion install, talking to the cloud
edge at KREXION_CLOUD_URL (default https://krexion.com) every SYNC_INTERVAL
seconds:

  1. Heartbeat   — "I'm online"
  2. Push links  — make sure cloud's /r/xxx redirects to the right URL
  3. Pull clicks — drain any clicks the cloud captured while we were offline

Cloud authenticates via the customer's `LICENSE_KEY` env var.
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

_running = False


def _headers() -> dict:
    return {
        "X-Krexion-License": LICENSE_KEY,
        "Content-Type": "application/json",
        "User-Agent": "Krexion-Local/1.0.1",
    }


async def _heartbeat() -> None:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                f"{CLOUD_URL}/api/sync/heartbeat",
                json={
                    "hostname": socket.gethostname(),
                    "version": "1.0.1",
                    "platform": "docker",
                },
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
    """Pull clicks the cloud captured. Insert into local clicks collection,
    then ack so cloud doesn't return them again."""
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

                # Insert into local DB (idempotent on 'id')
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

                # Update cursor
                last_ts = clicks[-1].get("created_at") or clicks[-1].get("timestamp") or since
                await user_db.cloud_sync_meta.update_one(
                    {"key": "last_click_pull"},
                    {"$set": {"key": "last_click_pull", "ts": last_ts}},
                    upsert=True,
                )

                # Ack to cloud
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


async def _sync_loop(main_db, get_db_for_user) -> None:
    global _running, LICENSE_KEY
    _running = True
    logger.info(
        f"[sync] daemon started — cloud={CLOUD_URL}, interval={SYNC_INTERVAL}s"
    )

    while _running:
        try:
            # Re-read license key from DB each cycle (so wizard activation
            # is picked up without restart).
            if not LICENSE_KEY:
                try:
                    lic_doc = await main_db.licenses.find_one(
                        {"status": {"$in": ["active", "issued"]}},
                        sort=[("created_at", -1)],
                        projection={"_id": 0, "license_key": 1},
                    )
                    if lic_doc and lic_doc.get("license_key"):
                        LICENSE_KEY = lic_doc["license_key"]
                        logger.info(f"[sync] license key resolved from DB ({LICENSE_KEY[:12]}…)")
                except Exception:
                    pass

            if not LICENSE_KEY:
                # nothing to sync yet
                await asyncio.sleep(SYNC_INTERVAL)
                continue

            # Heartbeat
            await _heartbeat()

            # Resolve user from license
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
                            f"[sync] cycle ok — pushed={pushed} pulled={pulled}"
                        )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[sync] loop error: {e}")

        await asyncio.sleep(SYNC_INTERVAL)


def start_if_local(main_db, get_db_for_user) -> bool:
    """Called from server.py on startup. No-op if not configured for sync."""
    if KREXION_MODE != "local":
        logger.info("[sync] disabled — KREXION_MODE != local")
        return False
    if not CLOUD_URL:
        logger.info("[sync] disabled — missing KREXION_CLOUD_URL")
        return False
    try:
        asyncio.create_task(_sync_loop(main_db, get_db_for_user))
        if not LICENSE_KEY:
            logger.info(
                "[sync] no LICENSE_KEY env — daemon will pick it up from "
                "the licenses collection once the user activates."
            )
        return True
    except RuntimeError:
        # No running loop yet — caller should re-invoke from a startup hook
        logger.warning("[sync] no running loop — schedule from startup event")
        return False
