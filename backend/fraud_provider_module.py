"""
fraud_provider_module.py — Multi-account fraud detection service manager
════════════════════════════════════════════════════════════════════════

Lets each customer add MULTIPLE api-key accounts per fraud service
(Scamalytics, IPQualityScore, IPHub, ProxyCheck, custom). When one
account hits its quota limit or gets rate-limited, the next enabled
account for the same service is automatically used.

BACKWARD COMPAT (CRITICAL):
- If the user has NOT enabled personal fraud filter, this module is
  100% skipped and the existing admin-panel `check_vpn_detailed(ip)`
  behavior is preserved unchanged.
- If personal filter is ON but no accounts are configured, we fall
  back to the admin defaults (unless the user explicitly disables the
  fallback in their fraud settings).
- No existing endpoint / signature / response shape changes.

Data model
──────────
  user_fraud_settings  (per-user document):
    { user_id: str,
      personal_filter_enabled: bool,   # master switch
      fallback_to_defaults: bool,      # if all my accounts fail → use admin defaults
      updated_at: iso                 }

  user_fraud_accounts  (per-user, one row per account):
    { id: str (uuid),
      user_id: str,
      service: str,          # scamalytics | ipqualityscore | iphub | proxycheck | custom
      account_name: str,     # user-friendly label, e.g. "Primary US"
      api_key: str,
      api_user: str,         # some services need username too (e.g. scamalytics)
      endpoint: str,         # optional override (for custom)
      enabled: bool,
      priority: int,         # lower = tried first (default 100)
      quota_daily: int,      # 0 = unlimited
      quota_used: int,       # resets every 24h
      quota_reset_at: iso,   # next reset timestamp
      rate_limited_until: iso | None,
      created_at: iso,
      last_used_at: iso | None }

Public API
──────────
  init_router(main_db, existing_check_vpn_fn) -> APIRouter
    Wires the collection ref, registers routes under /api/fraud/*.

  check_ip_for_user(user_id, ip) -> dict
    Async. Respects user's fraud settings. Returns same shape as the
    existing check_vpn_detailed():
      {is_vpn: bool, vpn_score: int, risk: str, source: str, ...}
"""
from __future__ import annotations

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Callable, Awaitable

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
import httpx

logger = logging.getLogger("fraud_provider_module")


# ─── Module-level state (populated by init_router) ───────────────────
_db = None                          # main_db from server.py
_existing_check_vpn = None          # fallback function pointer
_get_current_user_dep = None        # FastAPI dep resolver (from server.py)


# ─── Models ──────────────────────────────────────────────────────────
class FraudSettings(BaseModel):
    personal_filter_enabled: bool = False
    fallback_to_defaults: bool = True


class FraudAccountCreate(BaseModel):
    service: str = Field(..., description="scamalytics|ipqualityscore|iphub|proxycheck|custom")
    account_name: str
    api_key: str
    api_user: str = ""
    endpoint: str = ""
    enabled: bool = True
    priority: int = 100
    quota_daily: int = 0  # 0 = unlimited


class FraudAccountUpdate(BaseModel):
    account_name: Optional[str] = None
    api_key: Optional[str] = None
    api_user: Optional[str] = None
    endpoint: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    quota_daily: Optional[int] = None


# ─── Built-in endpoints per service (used if account.endpoint is blank) ─
_SERVICE_DEFAULT_ENDPOINT = {
    "scamalytics": "https://api11.scamalytics.com/{user}/",
    "ipqualityscore": "https://ipqualityscore.com/api/json/ip/",
    "iphub": "http://v2.api.iphub.info/ip/",
    "proxycheck": "http://proxycheck.io/v2/",
}


# ─── DB helpers ──────────────────────────────────────────────────────
async def _get_settings(user_id: str) -> Dict[str, Any]:
    doc = await _db.user_fraud_settings.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        return {"personal_filter_enabled": False, "fallback_to_defaults": True}
    return doc


async def _set_settings(user_id: str, settings: FraudSettings) -> None:
    await _db.user_fraud_settings.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "personal_filter_enabled": settings.personal_filter_enabled,
            "fallback_to_defaults": settings.fallback_to_defaults,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


async def _list_accounts(user_id: str, service: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"user_id": user_id}
    if service:
        q["service"] = service
    docs = await _db.user_fraud_accounts.find(q, {"_id": 0}).to_list(None)
    docs.sort(key=lambda d: (d.get("priority", 100), d.get("created_at", "")))
    return docs


async def _create_account(user_id: str, data: FraudAccountCreate) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "service": data.service.strip().lower(),
        "account_name": data.account_name.strip() or f"{data.service}-{now.strftime('%H%M%S')}",
        "api_key": data.api_key,
        "api_user": data.api_user,
        "endpoint": data.endpoint.strip(),
        "enabled": bool(data.enabled),
        "priority": int(data.priority),
        "quota_daily": max(0, int(data.quota_daily)),
        "quota_used": 0,
        "quota_reset_at": (now + timedelta(days=1)).isoformat(),
        "rate_limited_until": None,
        "created_at": now.isoformat(),
        "last_used_at": None,
    }
    await _db.user_fraud_accounts.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


async def _update_account(user_id: str, account_id: str, data: FraudAccountUpdate) -> Dict[str, Any]:
    updates = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(400, "No fields to update")
    res = await _db.user_fraud_accounts.update_one(
        {"id": account_id, "user_id": user_id},
        {"$set": updates},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Account not found")
    doc = await _db.user_fraud_accounts.find_one({"id": account_id, "user_id": user_id}, {"_id": 0})
    return doc  # type: ignore


async def _delete_account(user_id: str, account_id: str) -> None:
    res = await _db.user_fraud_accounts.delete_one({"id": account_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Account not found")


async def _record_usage(user_id: str, account_id: str, ok: bool, rate_limited: bool) -> None:
    now = datetime.now(timezone.utc)
    updates: Dict[str, Any] = {"last_used_at": now.isoformat()}
    if ok:
        updates["$inc"] = {"quota_used": 1}
    if rate_limited:
        updates["rate_limited_until"] = (now + timedelta(minutes=10)).isoformat()

    upd_doc: Dict[str, Any] = {"$set": {"last_used_at": now.isoformat()}}
    if ok:
        upd_doc["$inc"] = {"quota_used": 1}
    if rate_limited:
        upd_doc["$set"]["rate_limited_until"] = (now + timedelta(minutes=10)).isoformat()
    await _db.user_fraud_accounts.update_one(
        {"id": account_id, "user_id": user_id}, upd_doc
    )


def _is_quota_exhausted(acc: Dict[str, Any]) -> bool:
    q = int(acc.get("quota_daily") or 0)
    if q <= 0:
        return False
    used = int(acc.get("quota_used") or 0)
    reset_iso = acc.get("quota_reset_at")
    if reset_iso:
        try:
            reset_dt = datetime.fromisoformat(reset_iso.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) >= reset_dt:
                return False  # reset overdue, treat as fresh
        except Exception:
            pass
    return used >= q


def _is_rate_limited(acc: Dict[str, Any]) -> bool:
    until = acc.get("rate_limited_until")
    if not until:
        return False
    try:
        dt = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < dt
    except Exception:
        return False


# ─── Per-service HTTP calls ──────────────────────────────────────────
async def _call_scamalytics(ip: str, acc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    user = acc.get("api_user") or ""
    key = acc.get("api_key") or ""
    if not user or not key:
        return None
    endpoint = acc.get("endpoint") or _SERVICE_DEFAULT_ENDPOINT["scamalytics"].format(user=user)
    url = f"{endpoint.rstrip('/')}/{ip}"
    params = {"key": key}
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(url, params=params)
            if r.status_code == 429:
                return {"__rate_limited": True}
            if r.status_code != 200:
                return None
            data = r.json()
            score = int(data.get("score", data.get("fraud_score", 0)) or 0)
            risk = str(data.get("risk", "")).lower()
            is_vpn = score >= 50 or risk in ("high", "very high")
            return {
                "is_vpn": is_vpn,
                "vpn_score": score,
                "risk": "high" if score >= 66 else ("medium" if score >= 33 else "low"),
                "source": f"scamalytics:{acc.get('account_name')}",
                "raw": {"score": score, "risk": risk},
            }
    except Exception as e:
        logger.debug("scamalytics call failed: %s", e)
        return None


async def _call_ipqualityscore(ip: str, acc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = acc.get("api_key") or ""
    if not key:
        return None
    endpoint = acc.get("endpoint") or _SERVICE_DEFAULT_ENDPOINT["ipqualityscore"]
    url = f"{endpoint.rstrip('/')}/{key}/{ip}"
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(url)
            if r.status_code == 429:
                return {"__rate_limited": True}
            if r.status_code != 200:
                return None
            data = r.json()
            score = int(data.get("fraud_score", 0) or 0)
            is_vpn = bool(data.get("vpn") or data.get("proxy") or data.get("tor"))
            return {
                "is_vpn": is_vpn,
                "vpn_score": score,
                "risk": "high" if score >= 75 else ("medium" if score >= 40 else "low"),
                "source": f"ipqualityscore:{acc.get('account_name')}",
                "raw": data,
            }
    except Exception as e:
        logger.debug("ipqualityscore call failed: %s", e)
        return None


async def _call_iphub(ip: str, acc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = acc.get("api_key") or ""
    if not key:
        return None
    endpoint = acc.get("endpoint") or _SERVICE_DEFAULT_ENDPOINT["iphub"]
    url = f"{endpoint.rstrip('/')}/{ip}"
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(url, headers={"X-Key": key})
            if r.status_code == 429:
                return {"__rate_limited": True}
            if r.status_code != 200:
                return None
            data = r.json()
            block = int(data.get("block", 0) or 0)
            score = 100 if block == 2 else (60 if block == 1 else 0)
            return {
                "is_vpn": block >= 1,
                "vpn_score": score,
                "risk": "high" if block == 2 else ("medium" if block == 1 else "low"),
                "source": f"iphub:{acc.get('account_name')}",
                "raw": data,
            }
    except Exception as e:
        logger.debug("iphub call failed: %s", e)
        return None


async def _call_proxycheck(ip: str, acc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = acc.get("api_key") or ""
    endpoint = acc.get("endpoint") or _SERVICE_DEFAULT_ENDPOINT["proxycheck"]
    url = f"{endpoint.rstrip('/')}/{ip}"
    params: Dict[str, Any] = {"vpn": 1, "risk": 1}
    if key:
        params["key"] = key
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(url, params=params)
            if r.status_code == 429:
                return {"__rate_limited": True}
            if r.status_code != 200:
                return None
            data = r.json()
            entry = data.get(ip) or {}
            proxy = str(entry.get("proxy", "no")).lower() == "yes"
            risk = int(entry.get("risk", 0) or 0)
            score = risk if risk else (100 if proxy else 0)
            return {
                "is_vpn": proxy or risk >= 66,
                "vpn_score": score,
                "risk": "high" if score >= 66 else ("medium" if score >= 33 else "low"),
                "source": f"proxycheck:{acc.get('account_name')}",
                "raw": entry,
            }
    except Exception as e:
        logger.debug("proxycheck call failed: %s", e)
        return None


_SERVICE_CALLERS = {
    "scamalytics": _call_scamalytics,
    "ipqualityscore": _call_ipqualityscore,
    "iphub": _call_iphub,
    "proxycheck": _call_proxycheck,
}


# ─── Core public function ────────────────────────────────────────────
async def check_ip_for_user(user_id: str, ip: str) -> Dict[str, Any]:
    """
    Fraud-check `ip` respecting the user's personal fraud settings.

    Fallback chain:
      1. If personal_filter_enabled == False → delegate to existing
         admin-level check_vpn_detailed(ip)  (existing behavior).
      2. If enabled but no accounts → same delegate  (safe default).
      3. Otherwise walk through user's enabled accounts sorted by
         priority; skip quota-exhausted / rate-limited; return the
         FIRST successful result. If all fail and
         fallback_to_defaults == True → delegate to existing check.
      4. If fallback disabled and all fail → return neutral "unknown".
    """
    settings = await _get_settings(user_id)
    if not settings.get("personal_filter_enabled"):
        return await _existing_check_vpn(ip)

    accounts = await _list_accounts(user_id)
    usable = [a for a in accounts if a.get("enabled") and not _is_quota_exhausted(a) and not _is_rate_limited(a)]

    if not usable:
        if settings.get("fallback_to_defaults", True):
            res = await _existing_check_vpn(ip)
            res["source"] = f"admin-fallback:{res.get('source','')}"
            return res
        return {"is_vpn": False, "vpn_score": 0, "risk": "unknown", "source": "user-fallback-disabled"}

    for acc in usable:
        service = acc.get("service", "")
        caller = _SERVICE_CALLERS.get(service)
        if not caller:
            continue
        result = await caller(ip, acc)
        if result and result.get("__rate_limited"):
            await _record_usage(user_id, acc["id"], ok=False, rate_limited=True)
            continue
        if result:
            await _record_usage(user_id, acc["id"], ok=True, rate_limited=False)
            return result

    # All accounts failed
    if settings.get("fallback_to_defaults", True):
        res = await _existing_check_vpn(ip)
        res["source"] = f"admin-fallback:{res.get('source','')}"
        return res
    return {"is_vpn": False, "vpn_score": 0, "risk": "unknown", "source": "all-accounts-failed"}


# ─── Router factory ──────────────────────────────────────────────────
def init_router(main_db, existing_check_vpn_fn: Callable[[str], Awaitable[Dict[str, Any]]],
                get_current_user_dep) -> APIRouter:
    """
    Called from server.py after startup. Wires the module state and
    returns an APIRouter that MUST be included with `/api` prefix.
    """
    global _db, _existing_check_vpn, _get_current_user_dep
    _db = main_db
    _existing_check_vpn = existing_check_vpn_fn
    _get_current_user_dep = get_current_user_dep

    router = APIRouter(prefix="/fraud", tags=["fraud"])

    @router.get("/settings")
    async def get_settings(user=Depends(_get_current_user_dep)):
        return await _get_settings(user["id"])

    @router.put("/settings")
    async def update_settings(body: FraudSettings, user=Depends(_get_current_user_dep)):
        await _set_settings(user["id"], body)
        return await _get_settings(user["id"])

    @router.get("/accounts")
    async def list_accounts(service: Optional[str] = None, user=Depends(_get_current_user_dep)):
        return await _list_accounts(user["id"], service)

    @router.post("/accounts")
    async def create_account(body: FraudAccountCreate, user=Depends(_get_current_user_dep)):
        return await _create_account(user["id"], body)

    @router.put("/accounts/{account_id}")
    async def update_account(account_id: str, body: FraudAccountUpdate, user=Depends(_get_current_user_dep)):
        return await _update_account(user["id"], account_id, body)

    @router.delete("/accounts/{account_id}")
    async def delete_account(account_id: str, user=Depends(_get_current_user_dep)):
        await _delete_account(user["id"], account_id)
        return {"ok": True}

    @router.post("/accounts/{account_id}/test")
    async def test_account(account_id: str, body: Dict[str, Any] = Body(default={}),
                           user=Depends(_get_current_user_dep)):
        """Quick health-check: run this account against `1.1.1.1` (or user-provided ip)."""
        ip = str(body.get("ip") or "1.1.1.1")
        acc = await _db.user_fraud_accounts.find_one({"id": account_id, "user_id": user["id"]}, {"_id": 0})
        if not acc:
            raise HTTPException(404, "Account not found")
        caller = _SERVICE_CALLERS.get(acc.get("service"))
        if not caller:
            return {"ok": False, "reason": f"unsupported service: {acc.get('service')}"}
        result = await caller(ip, acc)
        if result and result.get("__rate_limited"):
            return {"ok": False, "reason": "rate limited"}
        if result:
            return {"ok": True, "result": result}
        return {"ok": False, "reason": "no response / auth failed"}

    @router.get("/services")
    async def list_services():
        """Static list of supported services + how many accounts the user has each."""
        return {
            "services": [
                {"key": "scamalytics", "name": "Scamalytics", "needs_user": True,
                 "signup_url": "https://scamalytics.com/ip/api"},
                {"key": "ipqualityscore", "name": "IPQualityScore", "needs_user": False,
                 "signup_url": "https://www.ipqualityscore.com/create-account"},
                {"key": "iphub", "name": "IPHub", "needs_user": False,
                 "signup_url": "https://iphub.info/register"},
                {"key": "proxycheck", "name": "ProxyCheck.io", "needs_user": False,
                 "signup_url": "https://proxycheck.io/dashboard/"},
            ]
        }

    logger.info("Fraud provider module wired — /api/fraud/*")
    return router
