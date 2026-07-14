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

# 2026-07 v2.5.3 — Session token auto-rotation for Rotating Gateway.
# Popular residential/rotating gateway providers embed a session id in
# the username. Keeping the same session id → the gateway returns the
# SAME sticky IP on every connection. To get a fresh IP per visit,
# the session id must change. We auto-detect the common patterns so
# customers don't have to add {sid} placeholders manually.
#
# Supported tokens (case-insensitive, match the numeric/alnum value
# right after the token name, up to the next '-' or '_'):
#   -session-XXXX          (Bright Data, BestGo, IPRoyal, SmartProxy)
#   -sessid-XXXX           (Oxylabs alternate)
#   -sessionid-XXXX        (Soax)
#   -sess-XXXX             (short-form)
#   -sessionduration-XXX   (NOT rotated — this is duration, not id)
# Placeholder overrides:
#   {sid}  → replaced with a fresh random id per line
_SESSION_TOKEN_RE = re.compile(
    r"(-(?:session(?:id)?|sessid|sess)-)([A-Za-z0-9]+)",
    re.IGNORECASE,
)


def _make_session_id() -> str:
    """Generate a fresh random session id (8-digit numeric — matches
    the format BestGo/Bright Data/IPRoyal accept)."""
    return str(random.randint(10**7, 10**9 - 1))


def _rotate_session_in_username(username: str) -> str:
    """Return `username` with any embedded session token replaced by a
    fresh random id. If no known token is present:
      • honour `{sid}` placeholder if the user added one manually
      • otherwise return the string unchanged (caller may still emit
        multiple identical lines — the gateway may rotate on its own
        without a session param, e.g. per-connect rotation providers).
    """
    if not username:
        return username
    if "{sid}" in username:
        return username.replace("{sid}", _make_session_id())
    if _SESSION_TOKEN_RE.search(username):
        return _SESSION_TOKEN_RE.sub(
            lambda m: f"{m.group(1)}{_make_session_id()}",
            username,
            count=1,
        )
    return username


def _format_gateway_line(cfg: Dict[str, Any], proxy_type: str,
                        rotate_session: bool = False) -> Optional[str]:
    host = str(cfg.get("gateway_host") or "").strip()
    port = str(cfg.get("gateway_port") or "").strip()
    user = str(cfg.get("username") or "").strip()
    pwd = str(cfg.get("password") or "").strip()
    if not host or not port:
        return None
    if rotate_session and user:
        user = _rotate_session_in_username(user)
    scheme = proxy_type or "http"
    if user and pwd:
        return f"{scheme}://{user}:{pwd}@{host}:{port}"
    return f"{scheme}://{host}:{port}"


def _pick_from_manual_list(cfg: Dict[str, Any]) -> Optional[str]:
    lines_raw = cfg.get("lines") or ""
    if isinstance(lines_raw, list):
        lines = [str(x).strip() for x in lines_raw if str(x).strip()]
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


# ─── Smart proxy string parser (Task 1) ──────────────────────────────
# Understand ANY proxy string a customer may paste in.
# Supported input shapes (case-insensitive scheme prefix optional):
#   • http://host:port
#   • http://user:pass@host:port
#   • https://user:pass@host:port
#   • socks5://user:pass@host:port
#   • socks5h://user:pass@host:port
#   • socks4://host:port
#   • user:pass@host:port                (scheme = auto/http default)
#   • host:port                          (scheme = auto/http default)
#   • host:port:user:pass                (Webshare / common list style)
#   • user:pass:host:port                (alt style)
#   • host,port,user,pass                (comma-separated)
# Returns dict per line:
#   {"raw", "ok", "proxy_type", "host", "port", "username", "password",
#    "normalized"}  — normalized is `<scheme>://user:pass@host:port` or
#                     `<scheme>://host:port`.
_SCHEME_ALIASES = {
    "http": "http", "https": "https",
    "socks5": "socks5", "socks5h": "socks5h", "socks4": "socks4",
    "socks": "socks5",  # user shorthand
    "s5": "socks5", "s4": "socks4",
}


def _looks_like_host(s: str) -> bool:
    if not s:
        return False
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", s):
        return True
    if re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,253}[a-zA-Z0-9])?$", s):
        return "." in s or s in ("localhost",)
    return False


def _looks_like_port(s: str) -> bool:
    if not s or not s.isdigit():
        return False
    n = int(s)
    return 1 <= n <= 65535


def parse_proxy_string(raw: str, default_type: str = "http") -> Dict[str, Any]:
    """Auto-detect any common proxy string layout."""
    result = {
        "raw": raw,
        "ok": False,
        "proxy_type": default_type,
        "host": "",
        "port": "",
        "username": "",
        "password": "",
        "normalized": "",
        "error": "",
    }
    if not raw:
        result["error"] = "empty"
        return result
    line = raw.strip().strip("'\"")
    if not line:
        result["error"] = "empty"
        return result

    # 1) Strip and detect scheme
    scheme = default_type
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9]*)://(.+)$", line)
    if m:
        raw_scheme = m.group(1).lower()
        scheme = _SCHEME_ALIASES.get(raw_scheme, raw_scheme)
        if scheme not in SUPPORTED_TYPES:
            scheme = default_type
        line = m.group(2)

    user = pwd = host = port = ""

    # 2) Handle user:pass@host:port pattern
    if "@" in line:
        auth, hostpart = line.rsplit("@", 1)
        if ":" in auth:
            user, pwd = auth.split(":", 1)
        else:
            user = auth
        if ":" in hostpart:
            host, port = hostpart.split(":", 1)
        else:
            host = hostpart
    else:
        # 3) Handle colon/comma-separated flat lists (host:port[:user:pass] or reverse)
        sep = "," if "," in line and ":" not in line else ":"
        parts = [p.strip() for p in line.split(sep) if p.strip()]
        if len(parts) == 2:
            host, port = parts[0], parts[1]
        elif len(parts) == 4:
            # ambiguous: could be host:port:user:pass OR user:pass:host:port
            a, b, c, d = parts
            if _looks_like_host(a) and _looks_like_port(b):
                host, port, user, pwd = a, b, c, d
            elif _looks_like_host(c) and _looks_like_port(d):
                user, pwd, host, port = a, b, c, d
            else:
                # fallback: assume host:port:user:pass
                host, port, user, pwd = a, b, c, d
        elif len(parts) == 3:
            # host:port:user  (no password)  — rare but possible
            host, port, user = parts[0], parts[1], parts[2]
        else:
            result["error"] = f"unrecognised format ({len(parts)} parts)"
            return result

    # Cleanup
    host = host.strip().strip("/")
    port = port.strip()
    user = user.strip()
    pwd = pwd.strip()

    if not _looks_like_host(host):
        result["error"] = f"invalid host '{host}'"
        return result
    if not _looks_like_port(port):
        result["error"] = f"invalid port '{port}'"
        return result

    result.update({
        "ok": True,
        "proxy_type": scheme,
        "host": host,
        "port": port,
        "username": user,
        "password": pwd,
    })
    if user and pwd:
        result["normalized"] = f"{scheme}://{user}:{pwd}@{host}:{port}"
    elif user:
        result["normalized"] = f"{scheme}://{user}@{host}:{port}"
    else:
        result["normalized"] = f"{scheme}://{host}:{port}"
    return result


def _bulk_parse(strings: List[str], default_type: str = "http") -> Dict[str, Any]:
    """Parse a list of strings; return per-line results + summary."""
    lines = []
    for raw in strings:
        if isinstance(raw, str):
            for chunk in raw.splitlines():
                chunk = chunk.strip()
                if chunk:
                    lines.append(chunk)
    parsed = [parse_proxy_string(ln, default_type) for ln in lines]
    ok = [p for p in parsed if p["ok"]]
    # Detect dominant proxy_type (majority wins)
    type_votes: Dict[str, int] = {}
    for p in ok:
        type_votes[p["proxy_type"]] = type_votes.get(p["proxy_type"], 0) + 1
    dominant = default_type
    if type_votes:
        dominant = sorted(type_votes.items(), key=lambda x: -x[1])[0][0]

    # Suggest a provider config:
    # - If exactly 1 line with credentials → suggest rotating_gateway (one host)
    # - Else → suggest manual_list with all normalized lines
    suggested_kind = "manual_list"
    suggested_config: Dict[str, Any] = {}
    if len(ok) == 1 and ok[0]["username"] and ok[0]["password"]:
        suggested_kind = "rotating_gateway"
        suggested_config = {
            "gateway_host": ok[0]["host"],
            "gateway_port": ok[0]["port"],
            "username": ok[0]["username"],
            "password": ok[0]["password"],
        }
    else:
        suggested_config = {"lines": "\n".join(p["normalized"] for p in ok)}

    return {
        "parsed": parsed,
        "ok_count": len(ok),
        "fail_count": len(parsed) - len(ok),
        "dominant_type": dominant,
        "suggested_kind": suggested_kind,
        "suggested_proxy_type": dominant,
        "suggested_config": suggested_config,
    }


async def _bump_use(user_id: str, provider_id: str) -> None:
    try:
        await _db.user_proxy_providers.update_one(
            {"id": provider_id, "user_id": user_id},
            {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"use_count": 1}},
        )
    except Exception:
        pass


# 2026-07 v2.5.3 — Bulk resolver for jobs that need many unique lines.
async def get_proxy_lines_from_provider(
    user_id: str, provider_id: str, count: int,
) -> Dict[str, Any]:
    """
    Fetch `count` proxy lines from a single provider. Rotating-gateway
    kind auto-rotates the session token per line so the customer gets
    a fresh sticky-IP per visit (critical for RUT `no_repeated_proxy`
    mode — before this fix, rotating gateways emitted ONE line and RUT
    aborted with "No more proxies available" after visit #1).

    Return shape:
      { "lines": ["scheme://user:pass@host:port", ...],
        "kind":  "...",
        "provider_id": "...",
        "provider_name": "...",
        "proxy_type": "...",
        "use_proxyjet": bool          (native_proxyjet kind only)
        "country": "US" (native_proxyjet kind only)
        "state": "CA"  (native_proxyjet kind only, may be "")
        "error": "..." (only when nothing usable came back)
      }
    """
    if not provider_id:
        return {"lines": [], "error": "no provider_id supplied"}
    provider = await _get(user_id, provider_id)
    if not provider:
        return {"lines": [], "error": "provider not found"}
    if not provider.get("enabled"):
        return {"lines": [], "error": "provider is disabled"}

    kind = provider.get("kind")
    cfg = provider.get("config") or {}
    proxy_type = provider.get("proxy_type") or "http"
    ret_common = {
        "provider_id": provider.get("id"),
        "provider_name": provider.get("name"),
        "kind": kind,
        "proxy_type": proxy_type,
    }

    try:
        count = max(1, int(count))
    except Exception:
        count = 1
    count = min(count, 5000)  # hard cap

    if kind == "rotating_gateway":
        host = str(cfg.get("gateway_host") or "").strip()
        port = str(cfg.get("gateway_port") or "").strip()
        if not host or not port:
            return {"lines": [], "error": "gateway_host/port missing", **ret_common}
        lines: List[str] = []
        for _ in range(count):
            ln = _format_gateway_line(cfg, proxy_type, rotate_session=True)
            if ln:
                lines.append(ln)
        await _bump_use(user_id, provider["id"])
        return {"lines": lines, **ret_common}

    if kind == "manual_list":
        lines_raw = cfg.get("lines") or ""
        if isinstance(lines_raw, list):
            pool = [str(x).strip() for x in lines_raw if str(x).strip()]
        else:
            pool = [ln.strip() for ln in str(lines_raw).splitlines() if ln.strip()]
        if not pool:
            return {"lines": [], "error": "manual list empty", **ret_common}
        def _prefix(x: str) -> str:
            return x if re.match(r"^[a-zA-Z]+://", x) else f"{proxy_type}://{x}"
        shuffled = pool[:]
        random.shuffle(shuffled)
        lines = shuffled[:count] if count <= len(shuffled) else []
        if not lines:
            bucket: List[str] = []
            cur = shuffled[:]
            while len(bucket) < count:
                if not cur:
                    cur = pool[:]
                    random.shuffle(cur)
                bucket.append(cur.pop())
            lines = bucket
        lines = [_prefix(ln) for ln in lines]
        await _bump_use(user_id, provider["id"])
        return {"lines": lines, **ret_common}

    if kind == "api_endpoint":
        lines: List[str] = []
        attempts = 0
        max_attempts = count * 2
        while len(lines) < count and attempts < max_attempts:
            attempts += 1
            p = await _pick_from_api(cfg, proxy_type)
            if p:
                lines.append(p)
        if not lines:
            return {"lines": [], "error": "api_endpoint returned no proxies", **ret_common}
        await _bump_use(user_id, provider["id"])
        return {"lines": lines, **ret_common}

    if kind == "native_proxyjet":
        await _bump_use(user_id, provider["id"])
        return {
            "lines": [],
            "use_proxyjet": True,
            "country": cfg.get("country") or "US",
            "state": cfg.get("state") or "",
            "gateway": cfg.get("gateway") or "",
            **ret_common,
        }

    return {"lines": [], "error": f"unknown kind: {kind}", **ret_common}



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

    # ── 2026-01 v2.5.0 — Provider-agnostic on-demand batch generator ─
    # Wraps ProxyJet's per-user unique batch generation for ANY selected
    # provider kind. Frontend "Auto Mode" toggle + Proxies page batch
    # generator both hit this single endpoint so customers no longer
    # need ProxyJet credentials specifically — whichever provider they
    # picked in Settings › Proxy Providers becomes the batch source.
    #
    # Behavior per kind:
    #   • native_proxyjet     → uses ProxyJet's existing generate_unique_proxies()
    #   • rotating_gateway    → generates N gateway lines. When cfg has
    #                           `session_param` (username token e.g.
    #                           "-session-{sid}"), each line rotates the
    #                           token so the gateway rotates IPs per
    #                           session. Otherwise returns N identical
    #                           gateway lines (still correct — the
    #                           gateway rotates IPs on every connect).
    #   • api_endpoint        → calls the API N times (with small retry
    #                           per failure).
    #   • manual_list         → random samples from user's list. If the
    #                           user asks for more than the list size,
    #                           picks with replacement (shuffled).
    #
    # Request body (all optional except count):
    #   {
    #     "count": 10,
    #     "country": "US",          // hint for providers that support geo
    #     "state":   "CA",          // ProxyJet & any provider that supports geo
    #     "sticky_minutes": null,   // ProxyJet only
    #     "proxy_type": "socks5"    // override scheme prefix on the output
    #                               //   accepted: http/https/socks5/socks5h/socks4
    #   }
    @router.post("/{provider_id}/generate-batch")
    async def provider_generate_batch(
        provider_id: str,
        body: Dict[str, Any] = Body(default_factory=dict),
        user=Depends(_get_current_user_dep),
    ):
        try:
            count = int(body.get("count") or 10)
        except Exception:
            count = 10
        count = max(1, min(count, 5000))
        country = str(body.get("country") or "").strip().upper() or None
        state = str(body.get("state") or "").strip().upper() or None
        sticky_minutes = body.get("sticky_minutes")
        try:
            sticky_minutes = int(sticky_minutes) if sticky_minutes else None
        except Exception:
            sticky_minutes = None
        proxy_type_override = str(body.get("proxy_type") or "").strip().lower() or None
        if proxy_type_override and proxy_type_override not in SUPPORTED_TYPES:
            proxy_type_override = None

        provider = await _get(user["id"], provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")
        if not provider.get("enabled"):
            raise HTTPException(400, "Provider is disabled")

        kind = provider.get("kind")
        cfg = provider.get("config") or {}
        proxy_type = proxy_type_override or provider.get("proxy_type") or "http"

        def _apply_scheme(line: str) -> str:
            """Ensure the returned proxy string has the requested scheme
            prefix. Strips any existing scheme first so the caller-
            chosen format wins."""
            if not line:
                return line
            m = re.match(r"^([a-zA-Z][a-zA-Z0-9+\-.]*)://(.*)$", line)
            body_part = m.group(2) if m else line
            return f"{proxy_type}://{body_part}"

        out: List[str] = []

        if kind == "native_proxyjet":
            # Delegate to the existing ProxyJet generator (with per-user
            # session dedup). Merge provider's saved country/state as
            # defaults when the request didn't specify them.
            try:
                import proxyjet_module as _pj  # local import to avoid cycles
            except Exception as e:  # noqa: BLE001
                raise HTTPException(500, f"ProxyJet module unavailable: {e}")
            try:
                out = await _pj.generate_unique_proxies(
                    _db,
                    user["id"],
                    count=count,
                    country=country or (cfg.get("country") or "US").upper(),
                    state=state or ((cfg.get("state") or "").upper() or None),
                    sticky_minutes=sticky_minutes,
                )
            except RuntimeError as e:
                raise HTTPException(400, str(e))
            # Apply proxy_type override on top of ProxyJet's user:pass@host:port
            # string (ProxyJet returns bare user:pass@host:port with no scheme,
            # so _apply_scheme just prepends).
            if proxy_type_override:
                out = [_apply_scheme(ln) for ln in out]

        elif kind == "rotating_gateway":
            # Build gateway lines. Support optional `session_param`
            # template so power users can force per-line rotation by
            # tokenising their username (e.g.
            #   "brd-customer-XXX-zone-Y-session-{sid}"
            # becomes 10 unique session-suffixed usernames when count=10).
            # 2026-07 v2.5.3 — Auto-detect common session tokens
            # (-session-XXX, -sessid-XXX, -sessionid-XXX, -sess-XXX)
            # so customers don't have to add {sid} placeholders.
            host = str(cfg.get("gateway_host") or "").strip()
            port = str(cfg.get("gateway_port") or "").strip()
            username_tpl = str(cfg.get("username") or "").strip()
            pwd = str(cfg.get("password") or "").strip()
            if not host or not port:
                raise HTTPException(400, "gateway_host / gateway_port not configured")
            for _ in range(count):
                user_final = _rotate_session_in_username(username_tpl)
                if user_final and pwd:
                    line = f"{proxy_type}://{user_final}:{pwd}@{host}:{port}"
                else:
                    line = f"{proxy_type}://{host}:{port}"
                out.append(line)
            await _bump_use(user["id"], provider["id"])

        elif kind == "manual_list":
            lines_raw = cfg.get("lines") or ""
            if isinstance(lines_raw, list):
                lines = [str(x).strip() for x in lines_raw if str(x).strip()]
            else:
                lines = [ln.strip() for ln in str(lines_raw).splitlines() if ln.strip()]
            if not lines:
                raise HTTPException(400, "manual_list is empty")
            random.shuffle(lines)
            if count <= len(lines):
                out = lines[:count]
            else:
                # more requested than available → cycle with reshuffle
                out = []
                pool = lines[:]
                while len(out) < count:
                    if not pool:
                        pool = lines[:]
                        random.shuffle(pool)
                    out.append(pool.pop())
            # apply scheme override
            out = [_apply_scheme(ln) for ln in out]
            await _bump_use(user["id"], provider["id"])

        elif kind == "api_endpoint":
            # Call the provider API `count` times. Best-effort — skip
            # failures so a slow API doesn't abort the whole batch.
            fetched = 0
            attempts = 0
            max_attempts = count * 2  # simple safety cap
            while fetched < count and attempts < max_attempts:
                attempts += 1
                proxy = await _pick_from_api(cfg, proxy_type)
                if proxy:
                    out.append(_apply_scheme(proxy))
                    fetched += 1
            if not out:
                raise HTTPException(400, "api_endpoint returned no proxies")
            await _bump_use(user["id"], provider["id"])

        else:
            raise HTTPException(400, f"unknown provider kind: {kind}")

        return {
            "ok": True,
            "count": len(out),
            "proxies": out,
            "provider_id": provider["id"],
            "provider_name": provider["name"],
            "kind": kind,
            "proxy_type": proxy_type,
        }

    @router.post("/_smart-parse")
    async def smart_parse(
        body: Dict[str, Any] = Body(default_factory=dict),
        user=Depends(_get_current_user_dep),
    ):
        """Parse ANY pasted proxy strings (1-N lines, any format) and
        return per-line normalized results + a suggested provider
        config (rotating_gateway for a single credentialed line, or
        manual_list for many)."""
        strings = body.get("strings") or []
        if isinstance(strings, str):
            strings = [strings]
        default_type = str(body.get("default_type") or "http").lower()
        if default_type not in SUPPORTED_TYPES:
            default_type = "http"
        result = _bulk_parse(list(strings), default_type=default_type)
        return result

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
                    "label": "Manual List / Paste Strings",
                    "description": "Paste ANY proxy strings — the tool auto-detects http/https/socks5 etc. Use the Smart Paste button above to bulk-import.",
                    "fields": [
                        {"key": "lines", "label": "Proxies (one per line, any format)", "placeholder": "socks5://user:pass@host:port\nhttp://host:port\nuser:pass@host:port\nhost:port:user:pass", "type": "textarea"},
                    ],
                },
                # v2.6.2 — Native ProxyJet kind removed from the picker.
                # Any provider (rotating gateway / API endpoint / manual
                # list) is enough — customers no longer have to configure
                # a special "ProxyJet" entry.
            ],
            "proxy_types": list(SUPPORTED_TYPES),
        }

    logger.info("Proxy provider module wired — /api/proxy-providers/*")
    return router
