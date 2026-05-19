"""
Krexion Profile Builder — Bulk AdsPower-Compatible Profile Generator
=====================================================================

The cloud generates everything needed for AdsPower in seconds:
  • A unique ProxyJet sticky session per profile (no IP verification needed
    because each session = unique IP by design; verification was killing
    perf — 12s round-trips through ProxyJet were the bottleneck).
  • A realistic User-Agent via the same rich generator that powers the
    "User Agent Generator" page (full app/platform/device/version control).
  • Fingerprint config (screen resolution, language, timezone).

Results are saved in `adspower_profiles` and can be:
  1. Exported as XLSX/CSV/JSON for manual AdsPower bulk import.
  2. Optionally pushed live into AdsPower via `bridge_jobs` IF the customer
     has the local sync_client worker online. This now runs in the
     BACKGROUND — the job itself completes in seconds, push happens after.

Multi-config support: customer can save many AdsPower API keys, switch
between them, delete unwanted ones.
"""

from __future__ import annotations

import asyncio
import io
import logging
import random
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Response

logger = logging.getLogger(__name__)

_db: Any = None
_ua_generate_func: Any = None  # bound to server.py's generate_user_agents


def _bind(*, main_db, ua_generate_func=None) -> None:
    global _db, _ua_generate_func
    _db = main_db
    if ua_generate_func is not None:
        _ua_generate_func = ua_generate_func


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────
# US states + legacy UA template fallback (used only if UA generator
# fails or is not bound)
# ─────────────────────────────────────────────────────────────────────
UA_TEMPLATES = {
    "windows_chrome": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36",
    ],
    "windows_edge": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36 Edg/{v}.0.0.0",
    ],
    "mac_chrome": [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36",
    ],
    "mac_safari": [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.{m}.{n} Safari/605.1.15",
    ],
    "iphone_safari": [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_{m}_{n} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    ],
    "android_chrome": [
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Mobile Safari/537.36",
    ],
}

CHROME_VERSIONS = [126, 127, 128, 129, 130, 131]


def _fallback_ua(key: str) -> str:
    pool = UA_TEMPLATES.get(key) or UA_TEMPLATES["windows_chrome"]
    return random.choice(pool).format(
        v=random.choice(CHROME_VERSIONS),
        m=random.randint(0, 6),
        n=random.randint(100, 999),
    )


US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New_Hampshire", "New_Jersey", "New_Mexico", "New_York",
    "North_Carolina", "North_Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode_Island", "South_Carolina", "South_Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West_Virginia", "Wisconsin", "Wyoming",
]


# ─────────────────────────────────────────────────────────────────────
# ProxyJet sticky-session builder
# ─────────────────────────────────────────────────────────────────────
def build_proxy(base_user: str, base_pass: str, state: str, sid: str | None = None) -> dict:
    sid = sid or "krx" + secrets.token_hex(4)
    username = f"{base_user}-resi_region-US_{state}-session-{sid}-sessTime-30"
    return {
        "host": "ca.proxy-jet.io",
        "port": 1010,
        "username": username,
        "password": base_pass,
        "session_id": sid,
        "url_http": f"http://{username}:{base_pass}@ca.proxy-jet.io:1010",
    }


# ─────────────────────────────────────────────────────────────────────
# Parallel unique-IP allocator — fetches the real exit IP for each
# sticky session via api.ipify.org, skips duplicates against the user's
# adspower_used_ips history. Concurrency-capped so we don't melt the
# proxy pool. Roughly 50 profiles ≈ 8-15s instead of 600s sequential.
# ─────────────────────────────────────────────────────────────────────
import httpx  # local import keeps the module light when unused

_IP_PROBE_URLS = [
    "https://api.ipify.org?format=json",
    "https://ifconfig.me/ip",
]


async def _probe_ip(proxy_url: str, timeout: int = 10) -> str | None:
    """Try each probe URL once, fastest wins."""
    import re
    for url in _IP_PROBE_URLS:
        try:
            async with httpx.AsyncClient(
                proxy=proxy_url, timeout=timeout, follow_redirects=True,
            ) as c:
                r = await c.get(url)
                if r.status_code != 200:
                    continue
                txt = r.text.strip()
                if txt.startswith("{"):
                    try:
                        txt = (r.json() or {}).get("ip") or ""
                    except Exception:
                        continue
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", txt):
                    return txt
        except Exception:  # noqa: BLE001
            continue
    return None


async def allocate_unique_ips(
    user_id: str,
    base_user: str,
    base_pass: str,
    state: str,
    count: int,
    *,
    concurrency: int = 15,
    max_attempts_factor: int = 4,
    on_progress=None,
) -> tuple[list[dict], list[str]]:
    """Returns (allocated, errors). Each allocated entry has {ip, proxy}.

    Skips IPs that already exist in `adspower_used_ips` for this user, and
    skips duplicates within the same batch. Caps probe attempts so we don't
    loop forever for users with depleted ProxyJet pools.
    """
    sem = asyncio.Semaphore(concurrency)
    found: list[dict] = []
    errors: list[str] = []
    seen_ips: set[str] = set()

    # Preload user's historical IPs (best-effort)
    try:
        cursor = _db.adspower_used_ips.find(
            {"user_id": user_id, "ip": {"$exists": True}},
            {"_id": 0, "ip": 1},
        )
        async for doc in cursor:
            if doc.get("ip"):
                seen_ips.add(doc["ip"])
    except Exception:  # noqa: BLE001
        pass

    max_attempts = max(count * max_attempts_factor, count + 5)
    attempts_left = max_attempts

    async def one_probe() -> dict | None:
        async with sem:
            p = build_proxy(base_user, base_pass, state)
            ip = await _probe_ip(p["url_http"])
            if not ip:
                return None
            if ip in seen_ips:
                return {"duplicate": True, "ip": ip}
            seen_ips.add(ip)
            return {"ip": ip, "proxy": p}

    # Fire probes in waves until we have enough or run out of attempts
    while len(found) < count and attempts_left > 0:
        batch_size = min(attempts_left, max(concurrency, count - len(found) + 3))
        attempts_left -= batch_size
        results = await asyncio.gather(*[one_probe() for _ in range(batch_size)])
        for r in results:
            if not r:
                continue
            if r.get("duplicate"):
                continue
            found.append({"ip": r["ip"], "proxy": r["proxy"]})
            if on_progress:
                try:
                    await on_progress(len(found), count)
                except Exception:
                    pass
            if len(found) >= count:
                break

    if len(found) < count:
        errors.append(
            f"Only {len(found)}/{count} unique IPs found after {max_attempts - attempts_left} probes. "
            "Try a different state or smaller count."
        )
    return found[:count], errors


# ─────────────────────────────────────────────────────────────────────
# AdsPower API connection test — bridges to local PC via bridge_jobs
# ─────────────────────────────────────────────────────────────────────
async def test_adspower_config(user: dict, cid: str, *, wait_timeout: int = 18) -> dict:
    cfg = await _db.adspower_configs.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    if not cfg:
        raise HTTPException(404, "AdsPower config not found")

    # Check if user has a local heartbeat (PC online)
    hb = await _db.sync_heartbeats.find_one({"user_id": user["id"]}, {"_id": 0})
    online = False
    if hb and hb.get("last_seen"):
        try:
            last = datetime.fromisoformat(str(hb["last_seen"]).replace("Z", "+00:00"))
            online = (datetime.now(timezone.utc) - last).total_seconds() <= 120
        except Exception:
            online = False

    if not online:
        return {
            "ok": False,
            "reachable": False,
            "message": (
                "AdsPower is not connected yet. Open AdsPower on the same "
                "computer where Krexion is installed, then click Test again."
            ),
            "local_online": False,
        }

    # Enqueue a bridge_job for adspower/test
    bj_id = uuid.uuid4().hex
    await _db.bridge_jobs.insert_one({
        "id": bj_id, "user_id": user["id"], "email": user.get("email"),
        "feature": "adspower/test",
        "payload": {"host": cfg["host"], "api_key": cfg["api_key"]},
        "status": "pending", "result": None, "error": None,
        "created_at": _now(), "started_at": None, "completed_at": None, "claimed_by": None,
    })
    deadline = asyncio.get_event_loop().time() + wait_timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.5)
        bj = await _db.bridge_jobs.find_one({"id": bj_id}, {"_id": 0})
        if bj and bj.get("status") in ("done", "failed"):
            if bj["status"] == "done":
                return {
                    "ok": True, "reachable": True, "local_online": True,
                    "message": "AdsPower API connected successfully on your PC.",
                    "raw": bj.get("result"),
                }
            return {
                "ok": False, "reachable": False, "local_online": True,
                "message": bj.get("error") or "AdsPower test failed",
            }
    return {
        "ok": False, "reachable": False, "local_online": True,
        "message": "Timeout — your PC did not respond within 18s. Make sure AdsPower is running and Krexion sync_client is active.",
    }


# ─────────────────────────────────────────────────────────────────────
# CRUD - configs / proxy creds
# ─────────────────────────────────────────────────────────────────────
async def list_configs(user_id: str) -> list:
    docs = await _db.adspower_configs.find({"user_id": user_id}, {"_id": 0}).to_list(50)
    for c in docs:
        if c.get("api_key"):
            c["api_key_masked"] = c["api_key"][:6] + "..." + c["api_key"][-4:]
            c.pop("api_key", None)
    return docs


async def save_config(user_id: str, body: dict) -> dict:
    name = (body.get("name") or "Default").strip()[:80]
    host = (body.get("host") or "http://local.adspower.net:50325").strip()
    api_key = (body.get("api_key") or "").strip()
    if not api_key:
        raise HTTPException(400, "api_key required")
    doc = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "name": name,
        "host": host,
        "api_key": api_key,
        "created_at": _now(),
    }
    await _db.adspower_configs.insert_one(doc)
    out = {k: v for k, v in doc.items() if k != "_id" and k != "api_key"}
    out["api_key_masked"] = api_key[:6] + "..." + api_key[-4:]
    return out


async def delete_config(user_id: str, cid: str) -> dict:
    res = await _db.adspower_configs.delete_one({"id": cid, "user_id": user_id})
    return {"deleted": res.deleted_count}


async def save_proxy_creds(user_id: str, body: dict) -> dict:
    bu = (body.get("base_user") or "").strip()
    bp = (body.get("base_pass") or "").strip()
    if not bu or not bp:
        raise HTTPException(400, "base_user and base_pass required")
    await _db.adspower_settings.update_one(
        {"user_id": user_id},
        {"$set": {"proxy_base_user": bu, "proxy_base_pass": bp, "updated_at": _now()}},
        upsert=True,
    )
    return {"saved": True}


async def get_proxy_creds_status(user_id: str) -> dict:
    s = await _db.adspower_settings.find_one({"user_id": user_id}, {"_id": 0})
    if not s or not s.get("proxy_base_user"):
        return {"has_creds": False}
    return {"has_creds": True, "base_user_masked": s["proxy_base_user"][:6] + "..."}


# ─────────────────────────────────────────────────────────────────────
# Profile management: clear all, list, export
# ─────────────────────────────────────────────────────────────────────
async def clear_all_profiles(user_id: str) -> dict:
    p = await _db.adspower_profiles.delete_many({"user_id": user_id})
    u = await _db.adspower_used_ips.delete_many({"user_id": user_id})
    j = await _db.adspower_jobs.delete_many({"user_id": user_id})
    return {
        "deleted_profiles": p.deleted_count,
        "deleted_used_ips": u.deleted_count,
        "deleted_jobs": j.deleted_count,
    }


async def list_profiles_for(user_id: str, limit: int = 200) -> list:
    return await _db.adspower_profiles.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).limit(min(limit, 1000)).to_list(1000)


async def export_profiles_xlsx(user_id: str) -> Response:
    profiles = await _db.adspower_profiles.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50000)

    rows = []
    for p in profiles:
        proxy = p.get("proxy") or {}
        rows.append({
            "name": p.get("name"),
            "state": p.get("state"),
            "user_agent": p.get("user_agent"),
            "device": p.get("device_label"),
            "platform": p.get("ua_platform"),
            "app": p.get("ua_app"),
            "resolution": p.get("resolution"),
            "language": p.get("language"),
            "timezone": p.get("timezone"),
            "proxy_host": proxy.get("host"),
            "proxy_port": proxy.get("port"),
            "proxy_username": proxy.get("username"),
            "proxy_password": proxy.get("password"),
            "proxy_url": proxy.get("url_http"),
            "session_id": proxy.get("session_id"),
            "adspower_id": p.get("adspower_profile_id") or "",
            "created_at": p.get("created_at"),
        })

    import pandas as pd
    cols = [
        "name", "state", "user_agent", "device", "platform", "app",
        "resolution", "language", "timezone",
        "proxy_host", "proxy_port", "proxy_username", "proxy_password",
        "proxy_url", "session_id", "adspower_id", "created_at",
    ]
    df = pd.DataFrame(rows, columns=cols)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Profiles", index=False)
    output.seek(0)
    filename = f"krexion_profiles_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Profile-Count": str(len(rows)),
            "Access-Control-Expose-Headers": "X-Profile-Count, Content-Disposition",
        },
    )


# ─────────────────────────────────────────────────────────────────────
# UA generation — reuse the rich UA Generator if available, otherwise
# fall back to legacy 6-template randomiser.
# ─────────────────────────────────────────────────────────────────────
async def _gen_uas(user: dict, ua_cfg: dict, count: int) -> list[dict]:
    """Return a list of {user_agent, device_label, platform, app, resolution}.

    `ua_cfg` mirrors a subset of UAGenerateRequest fields:
        app, platform, brand, device_id, device_ids, app_version,
        app_versions, os_version, os_versions, region, regions,
        resolution, resolutions, ua_templates (legacy fallback).
    """
    legacy_keys = ua_cfg.get("ua_templates")
    if _ua_generate_func is None or not (ua_cfg.get("app") or ua_cfg.get("platform")):
        # legacy random-template fallback
        keys = legacy_keys or ["windows_chrome"]
        return [
            {
                "user_agent": _fallback_ua(random.choice(keys)),
                "device_label": "",
                "platform": random.choice(keys),
                "app": None,
                "resolution": None,
            }
            for _ in range(count)
        ]

    try:
        # Build a UAGenerateRequest-shaped payload object dynamically
        class _P:
            pass

        p = _P()
        p.app = ua_cfg.get("app") or "instagram"
        p.platform = ua_cfg.get("platform") or "any"
        p.brand = ua_cfg.get("brand")
        p.device_id = ua_cfg.get("device_id")
        p.device_ids = ua_cfg.get("device_ids")
        p.app_version = ua_cfg.get("app_version")
        p.app_versions = ua_cfg.get("app_versions")
        p.os_version = ua_cfg.get("os_version")
        p.os_versions = ua_cfg.get("os_versions")
        p.region = ua_cfg.get("region")
        p.regions = ua_cfg.get("regions")
        p.resolution = ua_cfg.get("resolution")
        p.resolutions = ua_cfg.get("resolutions")
        p.count = count
        p.format = "json"

        result = await _ua_generate_func(p, user)
        items = (result or {}).get("user_agents") or []
        out = []
        for it in items:
            out.append({
                "user_agent": it.get("user_agent", ""),
                "device_label": it.get("device", ""),
                "platform": it.get("platform", ""),
                "app": it.get("app"),
                "resolution": it.get("resolution"),
            })
        # If UA generator returned fewer than asked, pad with fallback
        while len(out) < count:
            keys = legacy_keys or ["windows_chrome"]
            out.append({
                "user_agent": _fallback_ua(random.choice(keys)),
                "device_label": "",
                "platform": "fallback",
                "app": None,
                "resolution": None,
            })
        return out[:count]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[profile-builder] UA generator failed, fallback: {e}")
        keys = legacy_keys or ["windows_chrome"]
        return [
            {
                "user_agent": _fallback_ua(random.choice(keys)),
                "device_label": "",
                "platform": random.choice(keys),
                "app": None,
                "resolution": None,
            }
            for _ in range(count)
        ]


# ─────────────────────────────────────────────────────────────────────
# Main: generate (fast path)
# ─────────────────────────────────────────────────────────────────────
_LANG_BY_STATE_DEFAULT = ["en-US", "en"]
_TZ_BY_STATE = {
    "California": "America/Los_Angeles", "Oregon": "America/Los_Angeles",
    "Washington": "America/Los_Angeles", "Nevada": "America/Los_Angeles",
    "Arizona": "America/Phoenix", "Colorado": "America/Denver",
    "Utah": "America/Denver", "New_Mexico": "America/Denver",
    "Texas": "America/Chicago", "Illinois": "America/Chicago",
    "Florida": "America/New_York", "New_York": "America/New_York",
    "Georgia": "America/New_York", "Pennsylvania": "America/New_York",
}


async def start_generate(user: dict, body: dict) -> dict:
    count = int(body.get("count") or 0)
    if count < 1 or count > 200:
        raise HTTPException(400, "count must be 1-200")
    state = (body.get("state") or "California").strip()
    if state not in US_STATES:
        raise HTTPException(400, "invalid state")
    config_id = body.get("config_id")
    if not config_id:
        raise HTTPException(400, "config_id required")
    name_prefix = (body.get("name_prefix") or "krexion").strip()[:32] or "krexion"
    wipe_existing = bool(body.get("wipe_existing") or False)
    push_to_adspower = bool(body.get("push_to_adspower") or False)
    verify_unique_ips = bool(body.get("verify_unique_ips") or False)
    ua_cfg = body.get("ua_config") or {}
    # legacy fallback if user only sent ua_templates
    if not ua_cfg and body.get("ua_templates"):
        ua_cfg = {"ua_templates": body["ua_templates"]}

    cfg = await _db.adspower_configs.find_one({"id": config_id, "user_id": user["id"]}, {"_id": 0})
    if not cfg:
        raise HTTPException(404, "AdsPower config not found")

    settings = await _db.adspower_settings.find_one({"user_id": user["id"]}, {"_id": 0})
    if not settings or not settings.get("proxy_base_user"):
        raise HTTPException(400, "ProxyJet credentials not saved")
    base_user = settings["proxy_base_user"]
    base_pass = settings["proxy_base_pass"]

    # Wipe existing if requested
    wiped = None
    if wipe_existing:
        wiped = await clear_all_profiles(user["id"])

    job_id = uuid.uuid4().hex
    await _db.adspower_jobs.insert_one({
        "id": job_id, "user_id": user["id"], "email": user.get("email"),
        "type": "profile_builder", "count": count, "state": state,
        "config_id": config_id, "config_name": cfg.get("name"),
        "name_prefix": name_prefix,
        "ua_config": ua_cfg,
        "wipe_existing": wipe_existing, "push_to_adspower": push_to_adspower,
        "verify_unique_ips": verify_unique_ips,
        "status": "running", "progress": 0, "total": count,
        "profiles": [], "errors": [], "created_at": _now(),
    })
    asyncio.create_task(_run_job_fast(
        job_id, user, cfg, base_user, base_pass, state, count, ua_cfg,
        name_prefix, push_to_adspower, verify_unique_ips,
    ))
    return {"job_id": job_id, "status": "started", "count": count, "wiped": wiped}


async def _run_job_fast(job_id, user, cfg, base_user, base_pass, state, count, ua_cfg, name_prefix, push_to_adspower, verify_unique_ips=False):
    """Fast path: generate everything on cloud in seconds. Optionally verifies
    unique IPs via parallel ipify probes. Optional push to local AdsPower
    runs in BACKGROUND afterwards."""
    async def upd(fields):
        await _db.adspower_jobs.update_one({"id": job_id}, {"$set": fields})

    try:
        # Step 1 — allocate proxies. Either verify-unique (slow but real
        # IPs) or generate sticky sessions instantly (no IP captured).
        allocated_proxies: list[dict] = []
        if verify_unique_ips:
            await upd({"status": "allocating_ips", "progress": 0})

            async def _ip_progress(done: int, total: int):
                await upd({"progress": done})

            allocated, ip_errors = await allocate_unique_ips(
                user["id"], base_user, base_pass, state, count,
                on_progress=_ip_progress,
            )
            if len(allocated) < count:
                await upd({
                    "status": "failed",
                    "errors": ip_errors or [f"Only {len(allocated)}/{count} unique IPs available"],
                    "completed_at": _now(),
                })
                return
            allocated_proxies = allocated  # each: {ip, proxy}
        else:
            # Instant: unique session IDs = unique IPs by design (no verify)
            allocated_proxies = [
                {"ip": None, "proxy": build_proxy(base_user, base_pass, state)}
                for _ in range(count)
            ]

        # Step 2 — generate UAs
        uas = await _gen_uas(user, ua_cfg, count)
        await upd({"status": "creating_profiles", "progress": 0})

        created: list[dict] = []
        bridge_job_ids: list[tuple[str, dict]] = []

        for idx in range(1, count + 1):
            ua_info = uas[idx - 1] if idx - 1 < len(uas) else uas[-1]
            pinfo = allocated_proxies[idx - 1]
            proxy = pinfo["proxy"]
            ip = pinfo.get("ip")
            seq = f"{idx:03d}"
            pname = f"{name_prefix}-{state.replace('_', '')}-{seq}"
            resolution = (ua_info.get("resolution") or "").replace("x", "_") or random.choice([
                "1920_1080", "1536_864", "1440_900", "1366_768"
            ])
            timezone_str = _TZ_BY_STATE.get(state, "America/New_York")
            language = _LANG_BY_STATE_DEFAULT

            profile_doc = {
                "id": uuid.uuid4().hex,
                "user_id": user["id"],
                "config_id": cfg["id"],
                "config_name": cfg.get("name"),
                "adspower_profile_id": None,
                "name": pname,
                "state": state,
                "ip": ip,
                "user_agent": ua_info.get("user_agent"),
                "device_label": ua_info.get("device_label"),
                "ua_platform": ua_info.get("platform"),
                "ua_app": ua_info.get("app"),
                "resolution": resolution.replace("_", "x"),
                "language": ",".join(language),
                "timezone": timezone_str,
                "proxy": proxy,
                "proxy_session": proxy["session_id"],
                "created_at": _now(),
                "pushed_to_adspower": False,
                "push_status": "skipped" if not push_to_adspower else "queued",
            }
            await _db.adspower_profiles.insert_one(profile_doc)
            await _db.adspower_used_ips.insert_one({
                "user_id": user["id"],
                "session_id": proxy["session_id"],
                "ip": ip,
                "profile_name": pname,
                "state": state,
                "created_at": _now(),
            })

            profile_summary = {
                "name": pname,
                "session": proxy["session_id"],
                "ip": ip,
                "user_agent": ua_info.get("user_agent", "")[:120],
                "device": ua_info.get("device_label", ""),
            }
            created.append(profile_summary)

            if push_to_adspower:
                bj_id = uuid.uuid4().hex
                # Build proper AdsPower v1 body via shared helper so the
                # generate-flow and retry-flow always produce identical
                # (and correct) shapes.
                payload = _build_bridge_payload(
                    cfg,
                    {
                        "name": pname,
                        "user_agent": ua_info.get("user_agent"),
                        "language": ",".join(language) if isinstance(language, list) else language,
                        "resolution": resolution,
                        "proxy": {
                            "host": proxy["host"],
                            "port": proxy["port"],
                            "username": proxy["username"],
                            "password": proxy["password"],
                        },
                        "ua_app": ua_cfg.get("app") if isinstance(ua_cfg, dict) else None,
                    },
                )
                await _db.bridge_jobs.insert_one({
                    "id": bj_id, "user_id": user["id"], "email": user.get("email"),
                    "feature": "adspower/create", "payload": payload,
                    "status": "pending", "result": None, "error": None,
                    "created_at": _now(), "started_at": None,
                    "completed_at": None, "claimed_by": None,
                    "profile_id": profile_doc["id"],
                })
                bridge_job_ids.append((bj_id, profile_doc))

            await upd({"progress": idx, "profiles": created})

        final_status = "done"
        await upd({"status": final_status, "completed_at": _now()})

        # Background: if push_to_adspower, watch bridge jobs
        if push_to_adspower and bridge_job_ids:
            asyncio.create_task(_watch_bridge_jobs(job_id, bridge_job_ids))
    except Exception as e:  # noqa: BLE001
        logger.error(f"[profile-builder] job {job_id} crashed: {e}")
        await upd({"status": "failed", "errors": [f"Internal: {e}"], "completed_at": _now()})


async def _watch_bridge_jobs(job_id: str, bridge_job_ids: list[tuple[str, dict]]) -> None:
    """Background watcher — updates profile docs as bridge workers finish.
    Times out per job after 120s to avoid hanging. Never raises."""
    try:
        deadline = asyncio.get_event_loop().time() + 180
        pending = {bj_id: prof for bj_id, prof in bridge_job_ids}
        while pending and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(3)
            for bj_id in list(pending):
                bj = await _db.bridge_jobs.find_one({"id": bj_id}, {"_id": 0})
                if not bj:
                    continue
                if bj.get("status") in ("done", "failed"):
                    prof = pending.pop(bj_id)
                    if bj.get("status") == "done":
                        ads = bj.get("result") or {}
                        pid = None
                        if isinstance(ads.get("data"), dict):
                            pid = ads["data"].get("id") or ads["data"].get("user_id")
                        pid = pid or ads.get("user_id")
                        await _db.adspower_profiles.update_one(
                            {"id": prof["id"]},
                            {"$set": {
                                "adspower_profile_id": pid,
                                "pushed_to_adspower": True,
                                "push_status": "success",
                            }},
                        )
                    else:
                        await _db.adspower_profiles.update_one(
                            {"id": prof["id"]},
                            {"$set": {
                                "pushed_to_adspower": False,
                                "push_status": f"failed: {bj.get('error') or 'bridge error'}",
                            }},
                        )
        # Mark any remaining as timed out
        for prof in pending.values():
            await _db.adspower_profiles.update_one(
                {"id": prof["id"]},
                {"$set": {
                    "push_status": "timeout: local PC bridge worker did not pick up",
                }},
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[profile-builder] watcher {job_id} non-fatal error: {e}")


async def get_job(user_id: str, job_id: str) -> dict:
    j = await _db.adspower_jobs.find_one({"id": job_id, "user_id": user_id}, {"_id": 0})
    if not j:
        raise HTTPException(404, "Job not found")
    return j


# ─────────────────────────────────────────────────────────────────────
# AdsPower request body builder
# ─────────────────────────────────────────────────────────────────────
# Maps the user's "target app" choice to a sensible default domain so
# AdsPower opens the right site when the profile is launched.
_APP_TO_DOMAIN = {
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "tiktok": "tiktok.com",
    "youtube": "youtube.com",
    "whatsapp": "web.whatsapp.com",
    "gsearch": "google.com",
    "gchrome": "google.com",
    "pinterest": "pinterest.com",
    "snapchat": "snapchat.com",
    "chrome": "google.com",
}


def _normalize_resolution(res: str) -> str:
    """AdsPower expects screen_resolution as 'WIDTH_HEIGHT' (underscore).
    We may receive it as '1080x1920' or '1080_1920' — normalise it."""
    if not res:
        return "1080_1920"
    return str(res).replace("x", "_")


def _build_adspower_create_body(cfg: dict, profile: dict, app: str | None = None) -> dict:
    """Build the body sent to AdsPower's POST /api/v1/user/create.

    Must match AdsPower v1 API spec exactly:
      • group_id  (required)
      • name      (required)
      • user_proxy_config (NOT 'proxy')
      • fingerprint_config.ua (NOT a top-level 'user_agent')
    """
    proxy = profile.get("proxy") or {}
    user_proxy_config = {
        "proxy_soft": "other",
        "proxy_type": "http",
        "proxy_host": str(proxy.get("host", "")),
        "proxy_port": str(proxy.get("port", "")),
        "proxy_user": str(proxy.get("username", "")),
        "proxy_password": str(proxy.get("password", "")),
    } if proxy else {"proxy_soft": "no_proxy"}

    fingerprint_config = {
        "automatic_timezone": "1",
        "language": (profile.get("language") or "en-US").split(","),
        "screen_resolution": _normalize_resolution(profile.get("resolution") or ""),
        "ua": profile.get("user_agent") or "",
    }
    domain = _APP_TO_DOMAIN.get((app or profile.get("ua_app") or "").lower(), "google.com")
    return {
        "name": profile.get("name") or "krexion-profile",
        "group_id": "0",          # 0 = default "Ungrouped" — always exists
        "domain_name": domain,
        "user_proxy_config": user_proxy_config,
        "fingerprint_config": fingerprint_config,
    }


def _build_bridge_payload(cfg: dict, profile: dict, app: str | None = None) -> dict:
    """Wrap an AdsPower create body with the host/api_key the bridge
    worker needs to actually reach AdsPower on the customer's PC."""
    return {
        "host": cfg["host"],
        "api_key": cfg["api_key"],
        **_build_adspower_create_body(cfg, profile, app),
    }


# ─────────────────────────────────────────────────────────────────────
# Retry pushing stuck/failed profiles to AdsPower
# ─────────────────────────────────────────────────────────────────────
async def retry_push_to_adspower(user: dict, body: dict) -> dict:
    """Re-enqueue bridge jobs for profiles whose push didn't land.

    Body:
      cid (optional)         — AdsPower config id; defaults to first one
      profile_ids (optional) — explicit profile ids to retry
                               (if omitted, retries every profile that is
                                not yet successfully pushed)

    Returns the count of jobs re-enqueued plus the job ids so the UI can
    poll for completion (handled by the persistent sweeper below).
    """
    # Resolve AdsPower config to use
    cid = (body or {}).get("cid")
    if cid:
        cfg = await _db.adspower_configs.find_one({"id": cid, "user_id": user["id"]}, {"_id": 0})
    else:
        cfg = await _db.adspower_configs.find_one({"user_id": user["id"]}, {"_id": 0})
    if not cfg:
        raise HTTPException(400, "No AdsPower config found — add an API key first.")

    # Pick profiles to retry
    explicit_ids = (body or {}).get("profile_ids")
    query: dict = {"user_id": user["id"]}
    if explicit_ids and isinstance(explicit_ids, list):
        query["id"] = {"$in": explicit_ids}
    else:
        # Anything not successfully pushed = candidate
        query["$or"] = [
            {"pushed_to_adspower": {"$ne": True}},
            {"pushed_to_adspower": {"$exists": False}},
        ]
    profiles = await _db.adspower_profiles.find(query, {"_id": 0}).to_list(2000)
    if not profiles:
        return {"retried": 0, "job_ids": [], "message": "Nothing to retry — all profiles are already pushed."}

    enqueued: list[str] = []
    for prof in profiles:
        # Skip if a still-pending bridge_job already exists for this
        # profile — avoid duplicates piling up in the queue.
        existing = await _db.bridge_jobs.find_one(
            {"profile_id": prof["id"], "status": {"$in": ["pending", "running"]}},
            {"_id": 0, "id": 1},
        )
        if existing:
            enqueued.append(existing["id"])
            continue

        bj_id = uuid.uuid4().hex
        # Build the *correct* AdsPower v1 body (group_id, user_proxy_config,
        # fingerprint_config.ua — not the legacy bug-shaped one).
        payload = _build_bridge_payload(cfg, prof)
        await _db.bridge_jobs.insert_one({
            "id": bj_id, "user_id": user["id"], "email": user.get("email"),
            "feature": "adspower/create", "payload": payload,
            "status": "pending", "result": None, "error": None,
            "created_at": _now(), "started_at": None,
            "completed_at": None, "claimed_by": None,
            "profile_id": prof["id"],
        })
        await _db.adspower_profiles.update_one(
            {"id": prof["id"]},
            {"$set": {"push_status": "queued"}},
        )
        enqueued.append(bj_id)

    return {
        "retried": len(enqueued),
        "job_ids": enqueued,
        "message": f"Re-queued {len(enqueued)} profile(s). Bridge worker will pick them up within seconds.",
    }


# ─────────────────────────────────────────────────────────────────────
# Persistent sweeper — reconciles 'queued' profiles with their
# bridge_jobs status. Runs every 30 s in the background. Survives
# server restarts (unlike the per-job _watch_bridge_jobs task).
# ─────────────────────────────────────────────────────────────────────
_sweeper_started: bool = False


async def _sweep_queued_profiles_loop() -> None:
    """Background reconciliation loop. Picks up profiles stuck in
    'queued' status and updates them based on their bridge_jobs status."""
    logger.info("[profile-builder] sweeper started — reconciling queued profiles every 30s")
    while True:
        try:
            stuck = await _db.adspower_profiles.find(
                {"pushed_to_adspower": {"$ne": True},
                 "push_status": {"$nin": ["skipped", "success"]}},
                {"_id": 0, "id": 1, "user_id": 1, "created_at": 1, "push_status": 1},
            ).limit(500).to_list(500)
            for prof in stuck:
                bj = await _db.bridge_jobs.find_one(
                    {"profile_id": prof["id"]},
                    {"_id": 0},
                    sort=[("created_at", -1)],
                )
                if not bj:
                    continue
                status = bj.get("status")
                if status == "done":
                    ads = bj.get("result") or {}
                    pid = None
                    if isinstance(ads.get("data"), dict):
                        pid = ads["data"].get("id") or ads["data"].get("user_id")
                    pid = pid or ads.get("user_id")
                    await _db.adspower_profiles.update_one(
                        {"id": prof["id"]},
                        {"$set": {
                            "adspower_profile_id": pid,
                            "pushed_to_adspower": True,
                            "push_status": "success",
                        }},
                    )
                elif status == "failed":
                    await _db.adspower_profiles.update_one(
                        {"id": prof["id"]},
                        {"$set": {
                            "pushed_to_adspower": False,
                            "push_status": f"failed: {bj.get('error') or 'bridge error'}",
                        }},
                    )
                else:
                    # Still pending/running — mark as timeout if the
                    # bridge job is older than 10 minutes (gives the
                    # local PC plenty of time to pick it up, even if
                    # AdsPower was briefly closed).
                    try:
                        created = datetime.fromisoformat(
                            str(bj.get("created_at", "")).replace("Z", "+00:00")
                        )
                        age = (datetime.now(timezone.utc) - created).total_seconds()
                        if age > 600 and prof.get("push_status") != "timeout: local PC bridge worker did not pick up":
                            await _db.adspower_profiles.update_one(
                                {"id": prof["id"]},
                                {"$set": {
                                    "push_status": "timeout: local PC bridge worker did not pick up — re-pair PC and click Retry push",
                                }},
                            )
                    except Exception:  # noqa: BLE001
                        pass
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[profile-builder] sweeper iteration error: {e}")
        await asyncio.sleep(30)


def start_sweeper_once() -> None:
    """Idempotent — called from server.py on startup. Safe to call
    multiple times (only spawns the task on the first call)."""
    global _sweeper_started
    if _sweeper_started:
        return
    try:
        asyncio.create_task(_sweep_queued_profiles_loop())
        _sweeper_started = True
    except RuntimeError:
        # No running loop yet — caller should call again from a
        # startup event handler. Don't mark started.
        pass
