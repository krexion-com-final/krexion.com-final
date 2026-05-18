"""
Krexion AdsPower Module - Bulk Profile Creator
================================================

UI on krexion.com cloud. Heavy lifting (AdsPower local API call) is
silently bridged to the customer's PC via existing bridge_jobs queue +
KrexionHeartbeat-style PowerShell scheduled task.

Multi-config support: customer can save many AdsPower API keys, switch
between them, delete unwanted ones.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_db: Any = None


def _bind(*, main_db) -> None:
    global _db
    _db = main_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────
# UA templates + US states
# ──────────────────────────────────────────────────────────────────────
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


def gen_ua(key: str) -> str:
    pool = UA_TEMPLATES.get(key) or UA_TEMPLATES["windows_chrome"]
    return random.choice(pool).format(
        v=random.choice(CHROME_VERSIONS),
        m=random.randint(0, 6),
        n=random.randint(100, 999),
    )


def gen_mixed_uas(count: int, keys: list[str]) -> list[str]:
    if not keys:
        keys = ["windows_chrome"]
    return [gen_ua(random.choice(keys)) for _ in range(count)]


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


# ──────────────────────────────────────────────────────────────────────
# ProxyJet sticky-session builder + IP rotation
# ──────────────────────────────────────────────────────────────────────
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


async def _ip_via_proxy(proxy_url: str, timeout: int = 12) -> str | None:
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=timeout, follow_redirects=True) as c:
            r = await c.get("https://api.ipify.org?format=json")
            if r.status_code == 200:
                ip = (r.json() or {}).get("ip")
                if ip and re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
                    return ip
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[adspower] ip fetch fail: {e}")
    return None


async def allocate_unique_ips(user: dict, base_user: str, base_pass: str, state: str, count: int) -> list[dict]:
    found: list[dict] = []
    attempts = 0
    max_attempts = count * 4 + 5
    while len(found) < count and attempts < max_attempts:
        attempts += 1
        p = build_proxy(base_user, base_pass, state)
        ip = await _ip_via_proxy(p["url_http"])
        if not ip:
            continue
        if any(f["ip"] == ip for f in found):
            continue
        if await _db.adspower_used_ips.find_one({"user_id": user["id"], "ip": ip}):
            continue
        found.append({"ip": ip, "proxy": p})
    return found


# ──────────────────────────────────────────────────────────────────────
# CRUD - configs / proxy creds
# ──────────────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────────
# Main: generate
# ──────────────────────────────────────────────────────────────────────
async def start_generate(user: dict, body: dict) -> dict:
    count = int(body.get("count") or 0)
    if count < 1 or count > 100:
        raise HTTPException(400, "count must be 1-100")
    state = (body.get("state") or "California").strip()
    if state not in US_STATES:
        raise HTTPException(400, "invalid state")
    config_id = body.get("config_id")
    if not config_id:
        raise HTTPException(400, "config_id required")
    ua_keys = body.get("ua_templates") or ["windows_chrome"]
    name_prefix = (body.get("name_prefix") or "krexion").strip()[:32] or "krexion"

    cfg = await _db.adspower_configs.find_one({"id": config_id, "user_id": user["id"]}, {"_id": 0})
    if not cfg:
        raise HTTPException(404, "AdsPower config not found")

    settings = await _db.adspower_settings.find_one({"user_id": user["id"]}, {"_id": 0})
    if not settings or not settings.get("proxy_base_user"):
        raise HTTPException(400, "ProxyJet credentials not saved")
    base_user = settings["proxy_base_user"]
    base_pass = settings["proxy_base_pass"]

    job_id = uuid.uuid4().hex
    await _db.adspower_jobs.insert_one({
        "id": job_id, "user_id": user["id"], "email": user.get("email"),
        "type": "adspower_bulk_create", "count": count, "state": state,
        "config_id": config_id, "name_prefix": name_prefix, "ua_templates": ua_keys,
        "status": "allocating_ips", "progress": 0, "total": count,
        "profiles": [], "errors": [], "created_at": _now(),
    })
    asyncio.create_task(
        _run_job(job_id, user, cfg, base_user, base_pass, state, count, ua_keys, name_prefix)
    )
    return {"job_id": job_id, "status": "started", "count": count}


async def _run_job(job_id, user, cfg, base_user, base_pass, state, count, ua_keys, name_prefix):
    async def upd(fields):
        await _db.adspower_jobs.update_one({"id": job_id}, {"$set": fields})
    try:
        await upd({"status": "allocating_ips", "progress": 0})
        ips = await allocate_unique_ips(user, base_user, base_pass, state, count)
        if len(ips) < count:
            await upd({"status": "failed", "errors": [f"Only {len(ips)}/{count} unique IPs allocated. Try smaller count or different state."]})
            return
        uas = gen_mixed_uas(count, ua_keys)
        await upd({"status": "creating_profiles", "progress": 0})

        created: list[dict] = []
        errors: list[str] = []
        for idx, (ipinfo, ua) in enumerate(zip(ips, uas), start=1):
            seq = f"{idx:03d}"
            pname = f"{name_prefix}-{state.replace('_', '')}-{seq}"
            payload = {
                "host": cfg["host"],
                "api_key": cfg["api_key"],
                "name": pname,
                "user_agent": ua,
                "proxy": {
                    "proxy_soft": "other",
                    "proxy_type": "http",
                    "proxy_host": ipinfo["proxy"]["host"],
                    "proxy_port": ipinfo["proxy"]["port"],
                    "proxy_user": ipinfo["proxy"]["username"],
                    "proxy_password": ipinfo["proxy"]["password"],
                },
                "fingerprint_config": {
                    "automatic_timezone": "1",
                    "language": ["en-US", "en"],
                    "screen_resolution": random.choice(["1920_1080", "1536_864", "1440_900", "1366_768"]),
                },
            }

            bj_id = uuid.uuid4().hex
            await _db.bridge_jobs.insert_one({
                "id": bj_id, "user_id": user["id"], "email": user.get("email"),
                "feature": "adspower/create", "payload": payload,
                "status": "pending", "result": None, "error": None,
                "created_at": _now(), "started_at": None, "completed_at": None, "claimed_by": None,
            })

            deadline = asyncio.get_event_loop().time() + 60
            res = None
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(2)
                bj = await _db.bridge_jobs.find_one({"id": bj_id}, {"_id": 0})
                if bj and bj.get("status") in ("done", "failed"):
                    res = bj
                    break

            if res and res.get("status") == "done":
                ads = res.get("result") or {}
                pid = None
                if isinstance(ads.get("data"), dict):
                    pid = ads["data"].get("id") or ads["data"].get("user_id")
                pid = pid or ads.get("user_id")
                await _db.adspower_profiles.insert_one({
                    "id": uuid.uuid4().hex, "user_id": user["id"],
                    "config_id": cfg["id"], "adspower_profile_id": pid,
                    "name": pname, "ip": ipinfo["ip"], "state": state,
                    "user_agent": ua, "proxy_session": ipinfo["proxy"]["session_id"],
                    "created_at": _now(),
                })
                await _db.adspower_used_ips.insert_one({
                    "user_id": user["id"], "ip": ipinfo["ip"],
                    "profile_name": pname, "created_at": _now(),
                })
                created.append({"name": pname, "ip": ipinfo["ip"], "adspower_id": pid})
            else:
                errors.append(f"{pname}: {(res or {}).get('error') or 'Timeout - bridge worker missing'}")
            await upd({"progress": idx, "profiles": created, "errors": errors})

        await upd({"status": "done" if created else "failed", "completed_at": _now()})
    except Exception as e:  # noqa: BLE001
        logger.error(f"[adspower] job {job_id} crashed: {e}")
        await upd({"status": "failed", "errors": [f"Internal: {e}"], "completed_at": _now()})


async def get_job(user_id: str, job_id: str) -> dict:
    j = await _db.adspower_jobs.find_one({"id": job_id, "user_id": user_id}, {"_id": 0})
    if not j:
        raise HTTPException(404, "Job not found")
    return j


async def list_profiles_for(user_id: str, limit: int = 200) -> list:
    return await _db.adspower_profiles.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).limit(min(limit, 500)).to_list(500)
