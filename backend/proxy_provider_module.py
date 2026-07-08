"""
proxy_provider_module.py — Multi-provider proxy source manager
════════════════════════════════════════════════════════════════════════

Every customer can add multiple proxy providers of 4 kinds:
  1. rotating_gateway  — single sticky/rotating gateway (e.g. Bright Data,
                          Oxylabs, Soax, IPRoyal Gateway).
                          Config: gateway_host, gateway_port, username,
                                  password, proxy_type (http/https/socks5)
  2. api_endpoint      — an API that returns a fresh proxy on demand
                          (SmartProxy, Webshare, custom).
                          Config: api_url, method (GET/POST), headers,
                                  body_json, response_path (JSON key
                                  or regex to pluck the proxy from response),
                                  proxy_type
  3. manual_list       — user-uploaded list of static proxies (one per line).
                          Config: lines: List[str], proxy_type
  4. native_proxyjet   — Krexion's built-in ProxyJet with per-provider
                          country + state overrides (existing engine).
                          Config: country, state (optional), gateway (opt)

Anywhere in the app that currently accepts a `proxy` param can now
accept `proxy_provider_id` instead — the caller resolves it via
`get_proxy_from_provider(user_id, provider_id)`.

BACKWARD COMPAT
───────────────
- 100% opt-in. If the customer never adds any providers, every legacy
  path (RUT, Browser Profile launch, Click Proxy, CPI Job, ProxiesPage
  bulk test) uses its existing default flow.
- The dropdown always includes a "(default — existing behavior)" option
  which resolves to None → legacy path.
"""
from __future__ import annotations

import re
import uuid
import json
import random
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
import httpx

logger = logging.getLogger("proxy_provider_module")

_db = None
_get_current_user_dep = None

SUPPORTED_KINDS = ("rotating_gateway", "api_endpoint", "manual_list", "native_proxyjet")
SUPPORTED_TYPES = ("http", "https", "socks5", "socks5h", "socks4")


# ─── Pydantic Models ─────────────────────────────────────────────────
class ProxyProviderCreate(BaseModel):
    name: str
    kind: str  # one of SUPPORTED_KINDS
    proxy_type: str = "http"  # http|https|socks5|socks5h|socks4
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)


class ProxyProviderUpdate(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    proxy_type: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


# ─── DB helpers ──────────────────────────────────────────────────────
async def _list(user_id: str) -> List[Dict[str, Any]]:
    docs = await _db.user_proxy_providers.find({"user_id": user_id}, {"_id": 0}).to_list(None)
    docs.sort(key=lambda d: (0 if d.get("enabled") else 1, d.get("created_at", "")))
    return docs


async def _get(user_id: str, provider_id: str) -> Optional[Dict[str, Any]]:
    return await _db.user_proxy_providers.find_one(
        {"id": provider_id, "user_id": user_id}, {"_id": 0}
    )


async def _create(user_id: str, data: ProxyProviderCreate) -> Dict[str, Any]:
    if data.kind not in SUPPORTED_KINDS:
        raise HTTPException(400, f"kind must be one of {SUPPORTED_KINDS}")
    if data.proxy_type not in SUPPORTED_TYPES:
        raise HTTPException(400, f"proxy_type must be one of {SUPPORTED_TYPES}")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": data.name.strip() or f"{data.kind}-{now[-8:]}",
        "kind": data.kind,
        "proxy_type": data.proxy_type,
        "enabled": bool(data.enabled),
        "config": data.config or {},
        "created_at": now,
        "last_used_at": None,
        "use_count": 0,
    }
    await _db.user_proxy_providers.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


async def _update(user_id: str, provider_id: str, data: ProxyProviderUpdate) -> Dict[str, Any]:
    updates = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(400, "No fields to update")
    if "kind" in updates and updates["kind"] not in SUPPORTED_KINDS:
        raise HTTPException(400, f"kind must be one of {SUPPORTED_KINDS}")
    if "proxy_type" in updates and updates["proxy_type"] not in SUPPORTED_TYPES:
        raise HTTPException(400, f"proxy_type must be one of {SUPPORTED_TYPES}")
    res = await _db.user_proxy_providers.update_one(
        {"id": provider_id, "user_id": user_id},
        {"$set": updates},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Provider not found")
    doc = await _get(user_id, provider_id)
    return doc  # type: ignore


async def _delete(user_id: str, provider_id: str) -> None:
    res = await _db.user_proxy_providers.delete_one({"id": provider_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Provider not found")


# ─── Proxy string resolver ───────────────────────────────────────────
def _format_gateway_line(cfg: Dict[str, Any], proxy_type: str) -> Optional[str]:
    host = str(cfg.get("gateway_host") or "").strip()
    port = str(cfg.get("gateway_port") or "").strip()
    user = str(cfg.get("username") or "").strip()
    pwd = str(cfg.get("password") or "").strip()
    if not host or not port:
        return None
    scheme = proxy_type or "http"
    if user and pwd:
        return f"{scheme}://{user}:{pwd}@{host}:{port}"
    return f"{scheme}://{host}:{port}"


def _pick_from_manual_list(cfg: Dict[str, Any]) -> Optional[str]:
    lines_raw = cfg.get("lines") or ""
    if isinstance(lines_raw, list):
        lines = [str(l).strip() for l in lines_raw if str(l).strip()]
    else:
        lines = [ln.strip() for ln in str(lines_raw).splitlines() if ln.strip()]
    if not lines:
        return None
    return random.choice(lines)


async def _pick_from_api(cfg: Dict[str, Any], proxy_type: str) -> Optional[str]:
    api_url = str(cfg.get("api_url") or "").strip()
    if not api_url:
        return None
    method = str(cfg.get("method") or "GET").upper()
    headers = cfg.get("headers") or {}
    if isinstance(headers, str):
        try:
            headers = json.loads(headers)
        except Exception:
            headers = {}
    body = cfg.get("body")
    if isinstance(body, str) and body.strip().startswith(("{", "[")):
        try:
            body = json.loads(body)
        except Exception:
            pass
    response_path = str(cfg.get("response_path") or "").strip()  # e.g. "data.0.proxy" or "proxy"

    try:
        async with httpx.AsyncClient(timeout=8) as c:
            if method == "POST":
                r = await c.post(api_url, headers=headers, json=body if isinstance(body, (dict, list)) else None,
                                 data=body if isinstance(body, (str, bytes)) else None)
            else:
                r = await c.get(api_url, headers=headers, params=body if isinstance(body, dict) else None)
            if r.status_code != 200:
                logger.warning(f"[proxy-api] provider api returned {r.status_code}")
                return None
            text = r.text
            # Try JSON path first
            if response_path:
                try:
                    j = r.json()
                    val: Any = j
                    for key in response_path.split("."):
                        if key.isdigit() and isinstance(val, list):
                            val = val[int(key)]
                        elif isinstance(val, dict):
                            val = val.get(key)
                        else:
                            val = None
                        if val is None:
                            break
                    if val:
                        line = str(val).strip()
                        if not re.match(r"^[a-zA-Z]+://", line):
                            line = f"{proxy_type}://{line}"
                        return line
                except Exception:
                    pass
            # Fallback: first non-empty line that looks like proxy
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if re.search(r"[a-zA-Z0-9\.]+:\d+", line):
                    if not re.match(r"^[a-zA-Z]+://", line):
                        line = f"{proxy_type}://{line}"
                    return line
            return None
    except Exception as e:
        logger.warning(f"[proxy-api] provider fetch failed: {e}")
        return None


async def get_proxy_from_provider(user_id: str, provider_id: str) -> Dict[str, Any]:
    """
    Returns {"proxy": "<scheme>://user:pass@host:port", "proxy_type": "...",
             "kind": "...", "provider_id": "...", "provider_name": "..."}
    or {"proxy": None, "error": "..."} on failure.
    Special kind='native_proxyjet' returns {"proxy": None, "use_proxyjet": True,
                                            "country": "...", "state": "..."}
    which the caller should feed into the existing ProxyJet auto flow.
    """
    if not provider_id:
        return {"proxy": None, "error": "no provider_id supplied"}
    provider = await _get(user_id, provider_id)
    if not provider:
        return {"proxy": None, "error": "provider not found"}
    if not provider.get("enabled"):
        return {"proxy": None, "error": "provider is disabled"}

    kind = provider.get("kind")
    cfg = provider.get("config") or {}
    proxy_type = provider.get("proxy_type") or "http"
    ret_common = {
        "provider_id": provider.get("id"),
        "provider_name": provider.get("name"),
        "kind": kind,
        "proxy_type": proxy_type,
    }

    if kind == "rotating_gateway":
        proxy = _format_gateway_line(cfg, proxy_type)
        await _bump_use(user_id, provider["id"])
        return {"proxy": proxy, **ret_common} if proxy else {"proxy": None, "error": "gateway_host/port missing", **ret_common}

    if kind == "manual_list":
        proxy = _pick_from_manual_list(cfg)
        if proxy and not re.match(r"^[a-zA-Z]+://", proxy):
            proxy = f"{proxy_type}://{proxy}"
        await _bump_use(user_id, provider["id"])
        return {"proxy": proxy, **ret_common} if proxy else {"proxy": None, "error": "manual list empty", **ret_common}

    if kind == "api_endpoint":
        proxy = await _pick_from_api(cfg, proxy_type)
        await _bump_use(user_id, provider["id"])
        return {"proxy": proxy, **ret_common} if proxy else {"proxy": None, "error": "api call failed", **ret_common}

    if kind == "native_proxyjet":
        await _bump_use(user_id, provider["id"])
        return {
            "proxy": None,
            "use_proxyjet": True,
            "country": cfg.get("country") or "US",
            "state": cfg.get("state") or "",
            "gateway": cfg.get("gateway") or "",
            **ret_common,
        }

    return {"proxy": None, "error": f"unknown kind: {kind}", **ret_common}


async def _bump_use(user_id: str, provider_id: str) -> None:
    try:
        await _db.user_proxy_providers.update_one(
            {"id": provider_id, "user_id": user_id},
            {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"use_count": 1}},
        )
    except Exception:
        pass


# ─── Router factory ──────────────────────────────────────────────────
def init_router(main_db, get_current_user_dep) -> APIRouter:
    global _db, _get_current_user_dep
    _db = main_db
    _get_current_user_dep = get_current_user_dep

    router = APIRouter(prefix="/proxy-providers", tags=["proxy-providers"])

    @router.get("")
    async def list_providers(user=Depends(_get_current_user_dep)):
        return await _list(user["id"])

    @router.post("")
    async def create_provider(body: ProxyProviderCreate, user=Depends(_get_current_user_dep)):
        return await _create(user["id"], body)

    @router.get("/{provider_id}")
    async def get_provider(provider_id: str, user=Depends(_get_current_user_dep)):
        doc = await _get(user["id"], provider_id)
        if not doc:
            raise HTTPException(404, "Not found")
        return doc

    @router.put("/{provider_id}")
    async def update_provider(provider_id: str, body: ProxyProviderUpdate,
                              user=Depends(_get_current_user_dep)):
        return await _update(user["id"], provider_id, body)

    @router.delete("/{provider_id}")
    async def delete_provider(provider_id: str, user=Depends(_get_current_user_dep)):
        await _delete(user["id"], provider_id)
        return {"ok": True}

    @router.post("/{provider_id}/test")
    async def test_provider(provider_id: str, user=Depends(_get_current_user_dep)):
        """Attempt to fetch one proxy from the provider and return the result."""
        result = await get_proxy_from_provider(user["id"], provider_id)
        if result.get("proxy") or result.get("use_proxyjet"):
            return {"ok": True, "sample": result}
        return {"ok": False, "error": result.get("error") or "unknown"}

    @router.get("/_meta/kinds")
    async def kinds_meta():
        """Metadata for the frontend Add Provider dialog."""
        return {
            "kinds": [
                {
                    "key": "rotating_gateway",
                    "label": "Rotating Gateway",
                    "description": "Single sticky/rotating gateway URL (Bright Data, Oxylabs, IPRoyal Gateway, Soax, etc.)",
                    "fields": [
                        {"key": "gateway_host", "label": "Gateway host", "placeholder": "gate.brightdata.com", "type": "text"},
                        {"key": "gateway_port", "label": "Port", "placeholder": "7000", "type": "text"},
                        {"key": "username", "label": "Username (optional)", "placeholder": "brd-customer-xxx-zone-resi", "type": "text"},
                        {"key": "password", "label": "Password (optional)", "placeholder": "•••••••", "type": "password"},
                    ],
                },
                {
                    "key": "api_endpoint",
                    "label": "API Endpoint",
                    "description": "REST API that returns a proxy on demand (SmartProxy, Webshare, custom).",
                    "fields": [
                        {"key": "api_url", "label": "API URL", "placeholder": "https://provider.example.com/proxies?token=xxx", "type": "text"},
                        {"key": "method", "label": "Method", "placeholder": "GET", "type": "text"},
                        {"key": "headers", "label": "Headers (JSON, optional)", "placeholder": '{"Authorization":"Bearer xxx"}', "type": "textarea"},
                        {"key": "body", "label": "Body / Params (JSON, optional)", "placeholder": '{"country":"US"}', "type": "textarea"},
                        {"key": "response_path", "label": "Response path (JSON key/dot, optional)", "placeholder": "data.0.proxy", "type": "text"},
                    ],
                },
                {
                    "key": "manual_list",
                    "label": "Manual List",
                    "description": "Paste static proxies (one per line). Any HTTP/HTTPS/SOCKS format.",
                    "fields": [
                        {"key": "lines", "label": "Proxies (one per line)", "placeholder": "user:pass@host:port\nsocks5://host:port", "type": "textarea"},
                    ],
                },
                {
                    "key": "native_proxyjet",
                    "label": "Native ProxyJet (Krexion built-in)",
                    "description": "Uses your existing Krexion ProxyJet with per-provider country/state override.",
                    "fields": [
                        {"key": "country", "label": "Country code (ISO-2)", "placeholder": "US", "type": "text"},
                        {"key": "state", "label": "State (US only, optional)", "placeholder": "CA", "type": "text"},
                    ],
                },
            ],
            "proxy_types": list(SUPPORTED_TYPES),
        }

    logger.info("Proxy provider module wired — /api/proxy-providers/*")
    return router
