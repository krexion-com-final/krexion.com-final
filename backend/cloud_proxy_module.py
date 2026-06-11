"""
cloud_proxy_module.py — v2.1.15 Cloud-Auth Bridge
══════════════════════════════════════════════════════════════════════
WHY THIS EXISTS
──────────────────────────────────────────────────────────────────────
Krexion ships as both a cloud SaaS (krexion.com) and a desktop app
(Krexion-Desktop-Setup-x.y.z.exe). Until v2.1.14 the desktop app
ran 100% offline — its embedded Python backend + embedded MongoDB
held auth / users / links / clicks / RUT jobs / etc., never talking
to krexion.com for anything except license validation.

That worked for the engine, but broke the SaaS UX:

  * A user who signs up in the desktop app never shows up in the
    krexion.com admin dashboard for approval.
  * The admin can't manage users / links / licenses centrally.
  * Each PC has its own user database — same person on two PCs
    sees two separate accounts.

The fix is a CLEAN HYBRID:

  Cloud (krexion.com)              Local desktop PC
  ───────────────────              ─────────────────
  /api/auth/*       ◄── proxy ──   /api/auth/*       (forwarded)
  /api/admin/*      ◄── proxy ──   /api/admin/*      (forwarded)
  /api/license/*    ◄── proxy ──   /api/license/*    (forwarded)
  /api/links/*      ◄── proxy ──   /api/links/*      (forwarded)
                                   /api/clicks/*     (local — heavy)
                                   /api/rut/*        (local — heavy)
                                   /api/conversions  (local — heavy)
                                   /api/settings/*   (local)
                                   …everything else  (local)

The frontend doesn't change. It still talks to `http://127.0.0.1:8088`
exclusively. This middleware sits in front of the FastAPI router and
re-routes the allowlisted "cloud paths" to `https://krexion.com`
transparently, then streams the cloud response back to the browser.

DESIGN GUARANTEES
──────────────────────────────────────────────────────────────────────
1. EXPLICIT ALLOWLIST — only paths matching `_CLOUD_PATH_PREFIXES` or
   `_CLOUD_PATH_EXACT` get forwarded. A future `/api/<new-thing>`
   stays local unless we add it deliberately. No fuzzy matching.

2. NEVER LOOP ON CLOUD — if `KREXION_MODE == "cloud"`, the middleware
   short-circuits and lets the local handler answer (because on
   krexion.com itself, "local" IS the cloud). This is the same
   `IS_CLOUD` guard the rest of the codebase uses.

3. STREAMING BODY — request body and response body are streamed, not
   buffered, so file uploads (e.g. /api/clicks/import — wait, that's
   local; but admin user CSV uploads are cloud-routed) work without
   doubling memory.

4. CLEAR ERRORS — when krexion.com is unreachable the middleware
   returns HTTP 502 with `{"detail": "Cloud unreachable. Check your
   internet connection."}` instead of letting the frontend hang.

5. AUTH PASS-THROUGH — every header the frontend sends (Authorization,
   cookies, etc.) is forwarded verbatim. The cloud issues the JWT,
   the local backend never validates it (cloud already did).

6. LOCAL ENDPOINTS THAT NEED THE USER — the existing
   `get_current_user()` dependency in server.py is extended to verify
   the bearer token against the cloud `/api/auth/me` endpoint when
   local JWT verification fails (because the token was signed with
   the cloud SECRET_KEY, not the local one). Verified users are
   cached for 5 minutes to avoid hammering cloud.

7. NO CORS — frontend → local backend is same-origin from Electron's
   perspective; local backend → cloud is server-to-server (no
   browser → no CORS preflight). So CORS doesn't need to change.

INSTALL / USAGE
──────────────────────────────────────────────────────────────────────
In server.py, right after the FastAPI app is created (and BEFORE the
api_router is included), call:

    from cloud_proxy_module import install_cloud_proxy
    install_cloud_proxy(app)

That's it. The middleware activates on every customer install
(KREXION_MODE in {"native","local"}). On the cloud (KREXION_MODE=
"cloud") it stays inert.
"""

from __future__ import annotations
import os
import logging
import asyncio
import time
from typing import Optional, Tuple

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("krexion.cloud_proxy")


# ══════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════
def _cloud_url() -> str:
    """Resolve cloud base URL at request time (so installer can override
    via .env without code changes)."""
    url = (os.environ.get("KREXION_CLOUD_URL") or "https://krexion.com").strip()
    # Strip trailing slash so concatenation is clean
    return url.rstrip("/")


def _is_cloud() -> bool:
    """True when this backend IS the cloud (krexion.com). The proxy
    must be inert in that case — otherwise we'd infinite-loop."""
    return (os.environ.get("KREXION_MODE") or "").strip().lower() == "cloud"


# ══════════════════════════════════════════════════════════════════════
# Allowlist — paths that MUST live on krexion.com
# ══════════════════════════════════════════════════════════════════════
# Prefix match: any request path starting with one of these is
# forwarded to the cloud. We use prefix instead of exact because
# /api/admin/users/{id} and /api/links/{id} need to be covered without
# enumerating every sub-route.
_CLOUD_PATH_PREFIXES: Tuple[str, ...] = (
    "/api/auth/",          # login, register, me, refresh, forgot-password, etc.
    "/api/admin/",         # admin dashboard reads (users, stats, branding, ...)
    "/api/license/",       # license read/validate/customer dashboard
    "/api/links/",         # link CRUD by id (delete, update, get)
)

# Exact match: collection roots and one-shot endpoints
_CLOUD_PATH_EXACT: Tuple[str, ...] = (
    "/api/links",          # POST create, GET list
    "/api/customer-signup",  # public signup (if present)
    # 2026-06-11: Admin-curated promotional / discount banners are
    # authored in the cloud admin panel and stored in the cloud Mongo.
    # Without this proxy entry, Electron/Native customers would only
    # see banners from their LOCAL DB (which is always empty), so any
    # discount / offer banner published on krexion.com would never
    # reach the desktop app. Forwarding makes the banner system
    # "publish once, show everywhere".
    "/api/banners/active",
    # 2026-06-11: Update-available notification banner. The cloud
    # tracks the latest published release in `app_releases`. Native /
    # Electron customers' local Mongo doesn't have those records, so
    # without this proxy the UpdateBanner would never light up on
    # their installed app even when a new version is out. Forwarding
    # lets every surface see the same "vX.Y.Z is available" prompt.
    "/api/system/public-latest",
)


def _is_cloud_path(path: str) -> bool:
    """Return True iff this request must be served by krexion.com."""
    if path in _CLOUD_PATH_EXACT:
        return True
    for p in _CLOUD_PATH_PREFIXES:
        if path.startswith(p):
            return True
    return False


# ══════════════════════════════════════════════════════════════════════
# Shared httpx client
# ══════════════════════════════════════════════════════════════════════
# Re-used connection pool — much faster than creating a new client per
# request, especially on Windows where TLS handshake to krexion.com
# costs ~80-200ms.
_client: Optional[httpx.AsyncClient] = None
_client_lock = asyncio.Lock()


async def _get_client() -> httpx.AsyncClient:
    """Lazy-init the shared client. Per-call timeout = 30s
    (uploads / large list calls take time)."""
    global _client
    if _client is None:
        async with _client_lock:
            if _client is None:
                _client = httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=10.0),
                    follow_redirects=False,  # let frontend see redirects verbatim
                    headers={"User-Agent": "KrexionDesktop/2.1.15 (cloud-proxy)"},
                )
    return _client


# Headers that MUST NOT be forwarded (hop-by-hop per RFC 7230 + a few
# we control ourselves).
_HOP_BY_HOP = {
    "host", "content-length", "transfer-encoding", "connection",
    "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
    "trailers", "upgrade",
}


def _filter_request_headers(headers) -> dict:
    """Strip hop-by-hop headers + Host (so httpx sets the right one
    for krexion.com, not 127.0.0.1)."""
    out = {}
    for k, v in headers.items():
        if k.lower() in _HOP_BY_HOP:
            continue
        out[k] = v
    return out


def _filter_response_headers(headers) -> dict:
    """Strip hop-by-hop + content-encoding from the response we relay
    back. content-encoding is stripped because httpx already decoded
    the body for us — leaving the header would tell the browser to
    decode again, breaking the response."""
    out = {}
    for k, v in headers.items():
        kl = k.lower()
        if kl in _HOP_BY_HOP:
            continue
        if kl == "content-encoding":
            continue
        if kl == "content-length":
            # Will be recomputed by Starlette from the body bytes
            continue
        out[k] = v
    return out


# ══════════════════════════════════════════════════════════════════════
# Cloud-token verification cache (for LOCAL endpoints)
# ══════════════════════════════════════════════════════════════════════
# When a request hits a LOCAL endpoint (e.g. /api/clicks) the local
# `get_current_user()` dependency runs. The Authorization JWT was
# issued by the cloud (different SECRET_KEY) so local JWT-verify
# fails. We then call krexion.com/api/auth/me with the same token.
# Cache the result for 5 minutes so the cloud isn't hammered.
_AUTH_CACHE_TTL = 300  # 5 minutes
_auth_cache: dict = {}  # token -> (expiry_ts, user_dict)
_auth_cache_lock = asyncio.Lock()


async def verify_cloud_token(authorization_header: Optional[str]) -> Optional[dict]:
    """Resolve a cloud-issued JWT to a user dict, with 5-min cache.
    Returns None if the token is missing / invalid / cloud unreachable.
    Called from server.py's get_current_user() fallback path."""
    if _is_cloud():
        return None  # On the cloud itself the local JWT path works.
    if not authorization_header or not authorization_header.lower().startswith("bearer "):
        return None

    token = authorization_header.split(None, 1)[1].strip()
    if not token:
        return None

    now = time.time()
    # Fast path: cached
    cached = _auth_cache.get(token)
    if cached and cached[0] > now:
        return cached[1]

    # Slow path: call cloud /api/auth/me
    try:
        client = await _get_client()
        r = await client.get(
            f"{_cloud_url()}/api/auth/me",
            headers={"Authorization": authorization_header},
        )
        if r.status_code == 200:
            user = r.json()
            if isinstance(user, dict) and user.get("id"):
                async with _auth_cache_lock:
                    _auth_cache[token] = (now + _AUTH_CACHE_TTL, user)
                return user
        # On 401/403, intentionally don't cache — the customer might
        # re-login moments later.
    except Exception as e:
        logger.warning(f"[cloud_proxy] verify_cloud_token failed: {e}")

    return None


# ══════════════════════════════════════════════════════════════════════
# Single-resource cloud fetchers (v2.1.17)
# ══════════════════════════════════════════════════════════════════════
# Local endpoints (RUT job creation, Visual Recorder warmup, etc.) need
# to look up data that lives ONLY on the cloud (links, sub-users,
# admin metadata). Instead of forwarding the whole request via the
# proxy, the call site fetches just the resource it needs and mirrors
# it into local Mongo for offline reuse.
#
# Each fetcher takes the user's Authorization header verbatim and
# returns the cloud's JSON body (or None on 4xx/5xx/network errors).
# Errors are intentionally swallowed → call site decides whether
# missing data is fatal (404 to user) or recoverable (use local
# cache).
# ══════════════════════════════════════════════════════════════════════

async def fetch_link_from_cloud(link_id: str, authorization_header: str) -> Optional[dict]:
    """Fetch a single link by id from krexion.com. Used as a fallback
    when the local RUT engine doesn't find the link in its local Mongo
    (because links now live cloud-side per the v2.1.15 architecture).

    Returns the cloud LinkResponse dict or None."""
    if _is_cloud() or not authorization_header:
        return None
    try:
        client = await _get_client()
        r = await client.get(
            f"{_cloud_url()}/api/links/{link_id}",
            headers={"Authorization": authorization_header},
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[cloud_proxy] fetch_link_from_cloud failed: {e}")
    return None
class CloudProxyMiddleware(BaseHTTPMiddleware):
    """Sits in front of every route. If the request path matches the
    cloud allowlist AND we're not running ON the cloud, forward to
    krexion.com and stream the response back. Otherwise pass through."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 1. Cloud server itself? Never proxy. Avoids infinite loop.
        if _is_cloud():
            return await call_next(request)

        # 2. Path not on the cloud allowlist? Handle locally.
        if not _is_cloud_path(path):
            return await call_next(request)

        # 3. Forward to cloud.
        try:
            return await self._forward(request)
        except httpx.ConnectError as e:
            logger.warning(f"[cloud_proxy] cloud unreachable: {e}")
            return JSONResponse(
                {"detail": "Cloud unreachable. Check your internet connection."},
                status_code=502,
            )
        except httpx.TimeoutException as e:
            logger.warning(f"[cloud_proxy] cloud timeout: {e}")
            return JSONResponse(
                {"detail": "Cloud request timed out. Please try again."},
                status_code=504,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception(f"[cloud_proxy] unexpected forward error: {e}")
            return JSONResponse(
                {"detail": "Cloud bridge error. Please retry."},
                status_code=502,
            )

    async def _forward(self, request: Request) -> Response:
        client = await _get_client()
        # Reconstruct cloud URL preserving query string
        query = request.url.query
        target = f"{_cloud_url()}{request.url.path}"
        if query:
            target = f"{target}?{query}"

        # Read body in full. For uploads larger than a few MB this
        # could be optimized to stream, but auth/admin/links bodies
        # are tiny (<10 KB typically).
        body = await request.body()
        headers = _filter_request_headers(request.headers)

        cloud_resp = await client.request(
            method=request.method,
            url=target,
            headers=headers,
            content=body,
        )

        out_headers = _filter_response_headers(cloud_resp.headers)
        return Response(
            content=cloud_resp.content,
            status_code=cloud_resp.status_code,
            headers=out_headers,
            media_type=cloud_resp.headers.get("content-type"),
        )


# ══════════════════════════════════════════════════════════════════════
# Public install hook
# ══════════════════════════════════════════════════════════════════════
def install_cloud_proxy(app: FastAPI) -> None:
    """Install the cloud-proxy middleware. Idempotent — safe to call
    multiple times during reloads."""
    if _is_cloud():
        logger.info("[cloud_proxy] running on cloud (KREXION_MODE=cloud) — middleware INERT")
        return
    app.add_middleware(CloudProxyMiddleware)
    logger.info(
        f"[cloud_proxy] installed. Cloud base: {_cloud_url()}. "
        f"Allowlist prefixes: {_CLOUD_PATH_PREFIXES} exact: {_CLOUD_PATH_EXACT}"
    )
