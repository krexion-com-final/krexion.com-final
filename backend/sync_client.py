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
import json
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CLOUD_URL = (os.environ.get("KREXION_CLOUD_URL") or "https://krexion.com").rstrip("/")


def _resolve_license_key() -> str:
    """v1.0.14: read LICENSE_KEY from env (highest priority), or from
    LICENSE_KEY_FILE (used by the installer's NSSM service env which
    sets LICENSE_KEY_FILE=%PROGRAMDATA%\\Krexion\\license-key.txt). The
    pre-1.0.14 sync_client only checked the LICENSE_KEY env var which
    was NEVER set by the installer, so the bridge worker had no key
    to authenticate with the cloud and silently exited every cycle.
    The fallback below is the actual reason customers' krexion.com
    link pill kept reading 'no recent heartbeat' even though the
    desktop install was running fine."""
    key = (os.environ.get("LICENSE_KEY") or "").strip()
    if key:
        return key
    key_file = os.environ.get("LICENSE_KEY_FILE")
    if key_file:
        try:
            from pathlib import Path
            p = Path(key_file)
            if p.exists():
                k = p.read_text(encoding="utf-8", errors="ignore").strip()
                if k:
                    return k
        except Exception:  # noqa: BLE001
            pass
    # Last resort: well-known native install location
    try:
        from pathlib import Path
        candidate = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Krexion" / "license-key.txt"
        if candidate.exists():
            k = candidate.read_text(encoding="utf-8", errors="ignore").strip()
            if k:
                return k
    except Exception:  # noqa: BLE001
        pass
    return ""


LICENSE_KEY = _resolve_license_key()
SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL_SEC", "30") or 30)
KREXION_MODE = (os.environ.get("KREXION_MODE") or "local").lower().strip()
# Bridge-job pulling cycles faster than the main sync loop so heavy
# features feel responsive (user clicks proxy-check on krexion.com cloud
# UI → max ~5s before local PC picks it up).
JOB_PULL_INTERVAL = int(os.environ.get("BRIDGE_JOB_PULL_SEC", "5") or 5)
LOCAL_API_BASE = (os.environ.get("LOCAL_API_BASE") or "http://localhost:8001").rstrip("/")

_running = False
_HB_FAILS = 0
_HB_OKS = 0


def _current_license_key() -> str:
    """v1.0.15: re-resolve the license on every request so a license
    activated AFTER the daemon started (or replaced via auto-takeover)
    is picked up automatically. Previously LICENSE_KEY was a module-
    level constant captured ONCE at import, so the daemon would
    heartbeat with an empty header forever and the cloud would
    return 401 every time -> dashboard's krexion.com link pill
    stuck on 'no recent heartbeat' until the customer restarted
    the backend service."""
    global LICENSE_KEY
    if not LICENSE_KEY:
        LICENSE_KEY = _resolve_license_key()
    return LICENSE_KEY


def _headers() -> dict:
    return {
        "X-Krexion-License": _current_license_key(),
        "Content-Type": "application/json",
        "User-Agent": "Krexion-Local/1.0.20",
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
    """v1.0.16 fix: previously logged failures at DEBUG which never made
    it to dashboard.log. Customers got stuck with 'no recent heartbeat'
    forever with no visible reason. Now logs the first 3 failures at
    INFO + a one-line root cause hint, then quiets down."""
    global _HB_FAILS, _HB_OKS
    key = _current_license_key()
    if not key:
        if _HB_FAILS < 3:
            logger.info(
                "[sync] heartbeat skipped: no license key found in env "
                "LICENSE_KEY/LICENSE_KEY_FILE/PROGRAMDATA. Wizard may "
                "not have written license-key.txt yet - will retry."
            )
        _HB_FAILS += 1
        return
    try:
        body = {
            "hostname": socket.gethostname(),
            "version": "1.0.20",
            "platform": "native-windows" if sys.platform.startswith("win") else "docker",
        }
        body.update(_hardware_info())
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                f"{CLOUD_URL}/api/sync/heartbeat",
                json=body,
                headers=_headers(),
            )
            if r.status_code >= 400:
                if _HB_FAILS < 3:
                    logger.info(
                        f"[sync] heartbeat returned HTTP {r.status_code}: "
                        f"{r.text[:200]}. License key tail "
                        f"...{key[-6:]}, cloud={CLOUD_URL}"
                    )
                _HB_FAILS += 1
            else:
                if _HB_OKS == 0:
                    logger.info(
                        f"[sync] heartbeat OK to {CLOUD_URL} - PC is now online "
                        f"in the cloud, heavy jobs will route here."
                    )
                _HB_OKS += 1
                _HB_FAILS = 0  # reset failure counter on success
                # v1.0.17: write the sync-status file the desktop dashboard
                # polls for the krexion.com link pill. desktop_module's
                # _cloud_link_status() reads last_heartbeat_at from this
                # file - pre-1.0.17 we never wrote it so the dashboard
                # always showed yellow 'no recent heartbeat' even when
                # the daemon was happily heart-beating.
                try:
                    status_path = Path(
                        os.environ.get("KREXION_SYNC_STATUS_FILE")
                        or (Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
                            / "Krexion" / "sync-status.json")
                    )
                    status_path.parent.mkdir(parents=True, exist_ok=True)
                    status_path.write_text(
                        json.dumps({
                            "last_heartbeat_at": time.time(),
                            "cloud_url": CLOUD_URL,
                            "version": "1.0.20",
                        }),
                        encoding="utf-8",
                    )
                except Exception:  # noqa: BLE001
                    pass
    except Exception as e:  # noqa: BLE001
        if _HB_FAILS < 3:
            logger.info(
                f"[sync] heartbeat exception: {type(e).__name__}: {e}. "
                f"Will retry every 30 s."
            )
        _HB_FAILS += 1


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
    #
    # 2026-05: corrected RUT/Form-Filler routes. The old "rut/start" and
    # "form-filler/start" paths pointed to endpoints that don't exist
    # in any release of the backend (legacy planning artefact). The
    # ACTUAL routes have always been:
    #   POST /api/real-user-traffic/jobs   (multipart form)
    #   POST /api/form-filler/jobs         (multipart form)
    # which is why RUT bridge jobs previously failed with 404 every time
    # the cloud edge enqueued one. Old desktop installs running the
    # pre-2026-05 sync_client will still 404, but self-update rolls
    # them forward automatically.
    feature_routes = {
        "proxies/bulk-test": ("POST", "/api/proxies/bulk-test"),
        "proxies/test-single": ("POST", "/api/proxies/test-single"),
        "rut/start": ("POST", "/api/real-user-traffic/jobs"),
        "rut/status": ("GET", "/api/real-user-traffic/jobs"),
        "form-filler/start": ("POST", "/api/form-filler/jobs"),
        "form-filler/status": ("GET", "/api/form-filler/jobs"),
        # Self-update — cloud UpdateBanner click ends up here so customer
        # never has to open localhost.
        "system/self-update": ("POST", "/api/system/install-update"),
        # AdsPower bulk profile creator (UI on cloud, executes locally)
        "adspower/create": ("POST", "__adspower_create__"),
        # AdsPower API connection test (UI on cloud, executes locally)
        "adspower/test": ("POST", "__adspower_test__"),
        # AdsPower bulk profile delete (UI on cloud, executes locally)
        "adspower/delete": ("POST", "__adspower_delete__"),
    }
    if feature not in feature_routes:
        # v1.0.14 NEW: generic passthrough for the require_local_mode
        # auto-route. server.py now enqueues any heavy-feature endpoint
        # with payload={"method": ..., "path": ..., "body": ..., "query": ...}.
        # The desktop bridge worker replays it against the LOCAL backend
        # (127.0.0.1:8001) which executes it (IS_CLOUD=false there) and
        # we ship the response body back to the cloud where the original
        # frontend request is waiting on it.
        if isinstance(payload, dict) and payload.get("method") and payload.get("path"):
            generic_method = str(payload["method"]).upper()
            generic_path = str(payload["path"])
            generic_body = payload.get("body") or {}
            generic_query = payload.get("query") or {}
            # v1.0.20: faithful raw-body + content-type + auth replay so
            # multipart/form-data heavy jobs (RUT, Form Filler) actually
            # execute on the desktop backend. Previously sync_client only
            # POSTed the parsed JSON body, which was always {} for
            # multipart requests, so the local backend 422'd every time.
            import base64 as _b64
            raw_b64 = payload.get("raw_body_b64") or ""
            content_type = (payload.get("content_type") or "").strip()
            auth_hdr = (payload.get("authorization") or "").strip()
            raw_body_bytes = b""
            if raw_b64:
                try:
                    raw_body_bytes = _b64.b64decode(raw_b64)
                except Exception:
                    raw_body_bytes = b""
            try:
                local_base = "http://127.0.0.1:8001"
                # Bridge worker is part of THIS process; we cannot make
                # a request to ourselves through httpx without an async
                # client + we want the X-Krexion-Bridge-Job header set
                # so require_local_mode lets the call through.
                headers = {
                    "X-Krexion-Bridge-Job": "1",
                }
                # Pass through user's JWT so local get_current_user works
                if auth_hdr:
                    headers["Authorization"] = auth_hdr
                # Pass through the original Content-Type when we have
                # raw bytes (multipart, urlencoded, etc.). For empty raw
                # body fall back to JSON.
                use_raw = bool(raw_body_bytes) and content_type and (
                    "multipart/form-data" in content_type.lower()
                    or "application/x-www-form-urlencoded" in content_type.lower()
                )
                if use_raw:
                    headers["Content-Type"] = content_type
                else:
                    headers["Content-Type"] = "application/json"
                logger.info(
                    f"[bridge] replay {generic_method} {generic_path} "
                    f"ct={headers.get('Content-Type','')[:40]} "
                    f"raw_bytes={len(raw_body_bytes)} json_body={bool(generic_body)}"
                )
                async with httpx.AsyncClient(timeout=600.0) as client:
                    if generic_method == "GET":
                        r = await client.get(
                            f"{local_base}{generic_path}",
                            headers=headers,
                            params=generic_query,
                        )
                    elif use_raw:
                        r = await client.request(
                            generic_method,
                            f"{local_base}{generic_path}",
                            headers=headers,
                            params=generic_query,
                            content=raw_body_bytes,
                        )
                    else:
                        r = await client.request(
                            generic_method,
                            f"{local_base}{generic_path}",
                            headers=headers,
                            params=generic_query,
                            json=generic_body,
                        )
                try:
                    body_back = r.json()
                except Exception:
                    # v1.0.20: when response isn't JSON (e.g.
                    # /visual-recorder/{id}/screenshot returns
                    # image/jpeg), base64-encode the raw bytes so the
                    # cloud can decode + forward as binary. Previously
                    # we stuffed r.text[:4000] which mangled any
                    # non-ASCII byte and broke screenshot bridging.
                    import base64 as _b64sub
                    body_back = {
                        "__binary_b64__": _b64sub.b64encode(r.content).decode("ascii"),
                        "__content_type__": r.headers.get("content-type", "application/octet-stream"),
                    }
                logger.info(
                    f"[bridge] replay → HTTP {r.status_code} for {generic_path}"
                )
                return {
                    "status": "done",
                    "result": {"status": r.status_code, "body": body_back},
                }
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[bridge] local replay failed for {generic_path}: {exc}")
                return {"status": "failed", "error": f"local replay failed: {exc}"}
        return {"status": "failed", "error": f"unknown feature: {feature}"}

    method, route = feature_routes[feature]

    # Helper: try Bearer + fallback URLs for AdsPower's local API.
    # AdsPower 8.4+ requires "Bearer <key>", older versions accept the raw
    # key. local.adspower.net may fail DNS on some machines → 127.0.0.1.
    async def _call_adspower(path: str, http_method: str, json_body: dict | None,
                             requested_host: str, api_key: str) -> dict:
        bases = [
            (requested_host or "http://local.adspower.net:50325").rstrip("/"),
            "http://127.0.0.1:50325",
        ]
        # dedupe while keeping order
        seen: set = set()
        bases = [b for b in bases if not (b in seen or seen.add(b))]
        auths = [f"Bearer {api_key}", api_key] if api_key else [""]
        last_err = None
        last_data: dict = {}
        async with httpx.AsyncClient(timeout=30) as client:
            for base in bases:
                for auth in auths:
                    try:
                        headers = {"Content-Type": "application/json"}
                        if auth:
                            headers["Authorization"] = auth
                        if http_method == "GET":
                            r = await client.get(f"{base}{path}", headers=headers, timeout=15)
                        else:
                            r = await client.post(f"{base}{path}", json=json_body, headers=headers, timeout=30)
                        try:
                            data = r.json()
                        except Exception:
                            data = {"text": r.text[:2000]}
                        last_data = data
                        if r.status_code >= 400:
                            last_err = f"AdsPower {r.status_code}: {data.get('msg') or data}"
                            continue
                        msg_l = str(data.get("msg", "")).lower()
                        if data.get("code") not in (0, None) and ("api-key" in msg_l or "api_key" in msg_l or "auth" in msg_l):
                            last_err = f"AdsPower rejected auth: {data.get('msg')}"
                            continue
                        return {"ok": True, "data": data}
                    except Exception as e:  # noqa: BLE001
                        last_err = str(e)
                        continue
        return {"ok": False, "error": last_err or "unreachable", "data": last_data}

    # Special handler: AdsPower API connection test
    if route == "__adspower_test__":
        host = payload.get("host") or "http://local.adspower.net:50325"
        api_key = payload.get("api_key") or ""
        res = await _call_adspower("/status", "GET", None, host, api_key)
        if res["ok"]:
            return {"status": "done", "result": {"reachable": True, "raw": res["data"]}}
        return {"status": "failed", "error": res["error"]}

    # Special handler: AdsPower local API call (not a local backend route)
    if route == "__adspower_create__":
        host = payload.get("host") or "http://local.adspower.net:50325"
        api_key = payload.get("api_key") or ""
        body = {k: v for k, v in payload.items() if k not in ("host", "api_key")}
        res = await _call_adspower("/api/v1/user/create", "POST", body, host, api_key)
        if res["ok"]:
            return {"status": "done", "result": res["data"]}
        return {"status": "failed", "error": res["error"]}

    # Special handler: AdsPower bulk delete
    if route == "__adspower_delete__":
        host = payload.get("host") or "http://local.adspower.net:50325"
        api_key = payload.get("api_key") or ""
        user_ids = payload.get("user_ids") or []
        if not user_ids:
            return {"status": "failed", "error": "no user_ids provided"}
        res = await _call_adspower(
            "/api/v1/user/delete", "POST",
            {"user_ids": user_ids}, host, api_key,
        )
        if res["ok"]:
            return {"status": "done", "result": res["data"]}
        return {"status": "failed", "error": res["error"]}

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
                params={"limit": 5, "hostname": socket.gethostname(), "worker_type": "python"},
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
    """Called from server.py on startup. No-op if not configured for sync.

    v1.0.14 fix: previously checked `KREXION_MODE == 'local'` strict-equal.
    But the actual NSSM service installer's `AppEnvironmentExtra` line
    in krexion-setup.iss sets `KREXION_MODE=native` (not "local").
    Result: every native customer install had the sync daemon DISABLED
    on startup, no heartbeats reached the cloud, the krexion.com link
    pill in the dashboard read 'no recent heartbeat' forever, AND every
    heavy job submitted from krexion.com was rejected with
    'local_pc_offline'. This is THE root cause of the v1.0.12-1.0.13
    'heavy jobs ni chal rahe' report.

    Now we treat ANY non-'cloud' mode as a customer install that needs
    to talk to the cloud. Only KREXION_MODE='cloud' (the VPS deploy)
    skips this path.
    """
    if KREXION_MODE == "cloud":
        logger.info("[sync] disabled - KREXION_MODE=cloud (this IS the cloud edge)")
        return False
    if not CLOUD_URL:
        logger.info("[sync] disabled - KREXION_CLOUD_URL not set")
        return False
    # v1.0.20: kill the legacy PowerShell `KrexionBridge` scheduled task
    # if it exists. Older installs (pre-native bundle, or PCs that ever
    # ran the cloud's "Pair my PC" PowerShell snippet) have a Scheduled
    # Task that polls /api/sync/jobs/pull every 5 s with NO feature
    # filter. It races the Python sync_client and atomically claims
    # heavy jobs like visual-recorder/start, only to immediately mark
    # them failed with "feature not supported by the PowerShell bridge
    # worker." That is exactly what the customer is reporting in
    # v1.0.20 logs. Deleting the task on startup is idempotent
    # (schtasks /Delete returns non-zero if task absent — fine).
    if sys.platform.startswith("win"):
        try:
            import subprocess as _sp
            for _task in ("KrexionBridge", "KrexionHeartbeat"):
                try:
                    _sp.run(
                        ["schtasks", "/Delete", "/TN", _task, "/F"],
                        capture_output=True,
                        timeout=10,
                        creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
                    )
                except Exception:  # noqa: BLE001
                    pass
            logger.info("[sync] legacy KrexionBridge / KrexionHeartbeat scheduled tasks cleaned up (if present)")
        except Exception as _cleanup_err:  # noqa: BLE001
            logger.debug(f"[sync] legacy task cleanup skipped: {_cleanup_err}")
    try:
        asyncio.create_task(_sync_loop(main_db, get_db_for_user))
        asyncio.create_task(_bridge_loop())
        logger.info(
            f"[sync] daemon enabled for mode={KREXION_MODE!r}, cloud={CLOUD_URL}, "
            f"license_key_present={bool(LICENSE_KEY)}"
        )
        if not LICENSE_KEY:
            logger.info(
                "[sync] no LICENSE_KEY env - daemon will pick it up from "
                "the licenses collection once the user activates."
            )
        return True
    except RuntimeError:
        logger.warning("[sync] no running loop - schedule from startup event")
        return False
