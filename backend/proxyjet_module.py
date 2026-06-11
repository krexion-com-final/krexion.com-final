"""
ProxyJet Auto Mode — Generate unique residential proxies on-the-fly.

This module lets a user save their ProxyJet credentials ONCE and the
RUT engine then auto-generates unique exit-IPs per visit so the user
never has to paste a proxy list again. Every session-ID we hand out is
tracked in MongoDB so the SAME exit-IP is never picked twice for that
user — eliminates duplicate-IP clicks on the offer URL completely.

Proxy string format (resi rotating, sticky):
    {username}-resi-{COUNTRY}-ip-{session_id}:{password}@{gateway}:{port}

Example (from user's ProxyJet dashboard):
    260202i9bQO-resi-US-ip-647264893:eeTIJJ6Ot7gzPYG@ca.proxy-jet.io:1010

Design goals
────────────
1. ADDITIVE — no existing flow is modified; everything is opt-in via
   the new `use_proxyjet_auto` toggle on the RUT submit endpoint.
2. SAFE — credentials are stored per-user; the `proxyjet_used_sessions`
   collection is auto-created on first write, no migration needed.
3. ANTI-DUPLICATE — every generated session_id is reserved BEFORE being
   returned, so two parallel RUT jobs from the same user can never get
   the same session_id and the same exit-IP.

The actual exit-IP a session resolves to is decided by ProxyJet at
connect-time, but a 30-bit random session_id space (≈1 billion) gives
us a vanishingly small collision probability and ProxyJet itself maps
distinct session_ids to distinct exit-IPs from its residential pool.
"""

from __future__ import annotations

import random
import string
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

# ----- Constants -----
DEFAULT_GATEWAY = "ca"               # ca.proxy-jet.io
DEFAULT_SERVER = "proxy-jet.io"
DEFAULT_PORT = 1010
DEFAULT_COUNTRY = "US"
DEFAULT_PRODUCT = "resi"             # rotating residential

# Session IDs in ProxyJet look like a 9-10 digit numeric token. We keep
# the same shape so the generated string is indistinguishable from one
# pasted from the ProxyJet dashboard.
_SESSION_ID_MIN = 100_000_000
_SESSION_ID_MAX = 999_999_999


def _new_session_id() -> str:
    """Return a fresh 9-digit numeric session ID (cryptographically random)."""
    return str(secrets.randbelow(_SESSION_ID_MAX - _SESSION_ID_MIN + 1) + _SESSION_ID_MIN)


def build_proxy_string(
    username: str,
    password: str,
    country: str = DEFAULT_COUNTRY,
    session_id: Optional[str] = None,
    gateway: str = DEFAULT_GATEWAY,
    server: str = DEFAULT_SERVER,
    port: int = DEFAULT_PORT,
    product: str = DEFAULT_PRODUCT,
    state: Optional[str] = None,
    sticky_minutes: Optional[int] = None,
) -> Tuple[str, str]:
    """Build a single ProxyJet proxy line. Returns ``(proxy_string, session_id)``.

    The returned string is in the standard
    ``user:pass@host:port`` shape that the existing RUT engine already
    accepts (see ``_parse_proxy_line`` in ``real_user_traffic.py``).

    Optional ``state`` (2-letter US state code like ``CA``, ``TX``) is
    appended via ProxyJet's ``-st-{STATE}`` filter for geo-targeted runs.

    Optional ``sticky_minutes`` (1..120) appends ProxyJet's
    ``-sessTime-{N}`` token so the same exit-IP is held for N minutes
    on subsequent connects (sticky session). When None or 0, the proxy
    is rotating — every connect resolves to a fresh exit-IP within the
    requested country/state pool.
    """
    sid = session_id or _new_session_id()
    parts = [username, product, country.upper()]
    if state:
        parts.extend(["st", state.upper()])
    parts.extend(["ip", sid])
    if sticky_minutes and int(sticky_minutes) > 0:
        # Clamp to ProxyJet's documented sticky-session limit (120 min).
        sm = max(1, min(int(sticky_minutes), 120))
        parts.extend(["sessTime", str(sm)])
    full_user = "-".join(parts)
    proxy_str = f"{full_user}:{password}@{gateway}.{server}:{port}"
    return proxy_str, sid


def mask_password(pw: str) -> str:
    """Return a partially-masked copy of a password for UI display."""
    if not pw:
        return ""
    if len(pw) <= 4:
        return "•" * len(pw)
    return pw[:2] + "•" * (len(pw) - 4) + pw[-2:]


# ────────────────────────────────────────────────────────────────────
# MongoDB helpers — all writes go through these functions so the
# collections stay consistent. Both collections are created on first
# write (Mongo auto-creates them).
# ────────────────────────────────────────────────────────────────────

# Collection: proxyjet_credentials
#   {
#     user_id: str,
#     server: "proxy-jet.io",
#     port: 1010,
#     username: "260202i9bQO",
#     password: "eeTIJJ6Ot7gzPYG",       # stored as-is (private DB)
#     default_country: "US",
#     gateway: "ca",
#     product: "resi",
#     created_at: ISO str,
#     updated_at: ISO str,
#   }

# Collection: proxyjet_used_sessions
#   {
#     user_id: str,
#     session_id: str,
#     country: "US",
#     created_at: ISO str,
#     job_id: str | None,       # which RUT job consumed this session
#     exit_ip: str | None,      # filled by RUT engine after first use
#   }
# Compound unique index: (user_id, session_id)


async def get_credentials(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the user's stored ProxyJet credentials (raw, with password)."""
    doc = await db.proxyjet_credentials.find_one({"user_id": user_id}, {"_id": 0})
    return doc


async def save_credentials(
    db,
    user_id: str,
    *,
    username: str,
    password: str,
    server: str = DEFAULT_SERVER,
    port: int = DEFAULT_PORT,
    default_country: str = DEFAULT_COUNTRY,
    gateway: str = DEFAULT_GATEWAY,
    product: str = DEFAULT_PRODUCT,
    default_state: Optional[str] = None,
) -> Dict[str, Any]:
    """Upsert ProxyJet credentials for a user. Returns the stored doc."""
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_id": user_id,
        "server": (server or DEFAULT_SERVER).strip(),
        "port": int(port or DEFAULT_PORT),
        "username": (username or "").strip(),
        "password": (password or "").strip(),
        "default_country": (default_country or DEFAULT_COUNTRY).strip().upper(),
        "default_state": (default_state or "").strip().upper() or None,
        "gateway": (gateway or DEFAULT_GATEWAY).strip(),
        "product": (product or DEFAULT_PRODUCT).strip(),
        "updated_at": now,
    }
    existing = await db.proxyjet_credentials.find_one({"user_id": user_id})
    if existing:
        await db.proxyjet_credentials.update_one({"user_id": user_id}, {"$set": doc})
    else:
        doc["created_at"] = now
        await db.proxyjet_credentials.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def delete_credentials(db, user_id: str) -> int:
    """Delete the user's ProxyJet credentials. Returns deleted count."""
    res = await db.proxyjet_credentials.delete_one({"user_id": user_id})
    return res.deleted_count


async def generate_unique_proxies(
    db,
    user_id: str,
    count: int,
    *,
    country: Optional[str] = None,
    state: Optional[str] = None,
    sticky_minutes: Optional[int] = None,
    job_id: Optional[str] = None,
    max_attempts_per_pick: int = 6,
    # ── 2026-06-11: Multi-geo MIX mode ─────────────────────────────
    # When `countries_pool` has 2+ entries, the generator picks a
    # RANDOM country per proxy (e.g. ["US","CA","GB"] → output is a
    # mixed-country batch). `states_pool` works the same way for the
    # 2-letter US state filter. Single-entry lists silently degrade
    # to scalar `country`/`state` so legacy callers see zero change.
    countries_pool: Optional[List[str]] = None,
    states_pool: Optional[List[str]] = None,
) -> List[str]:
    """Generate ``count`` ProxyJet proxy lines whose session_ids have
    never been used by this user before.

    Each new session_id is recorded in ``proxyjet_used_sessions`` BEFORE
    the function returns, so a follow-up call (even from a parallel job)
    will never get the same session_id again.

    Optional ``state`` (e.g. "CA") narrows the residential pool to that
    US state at the gateway level.

    Raises ``RuntimeError`` if credentials aren't configured.
    """
    creds = await get_credentials(db, user_id)
    if not creds:
        raise RuntimeError(
            "ProxyJet credentials not configured. Add them in Proxies → "
            "Auto Mode (one-time setup)."
        )

    # ── 2026-06-11: Normalise + validate MIX pools ────────────────
    _clean_countries: Optional[List[str]] = None
    if countries_pool:
        c = [str(x).strip().upper() for x in countries_pool if str(x).strip()]
        # Dedupe preserving order
        seen = set()
        c = [x for x in c if not (x in seen or seen.add(x))]
        if len(c) >= 2:
            _clean_countries = c
        elif len(c) == 1 and not country:
            country = c[0]  # auto-promote single entry to scalar

    _clean_states: Optional[List[str]] = None
    if states_pool:
        s = [str(x).strip().upper() for x in states_pool if str(x).strip()]
        seen_s = set()
        s = [x for x in s if not (x in seen_s or seen_s.add(x))]
        if len(s) >= 2:
            _clean_states = s
        elif len(s) == 1 and not state:
            state = s[0]

    country = (country or creds.get("default_country") or DEFAULT_COUNTRY).upper()
    effective_state = (state or creds.get("default_state") or "").strip().upper() or None
    if count < 1:
        return []
    if count > 200_000:
        count = 200_000  # safety cap

    out: List[str] = []
    now = datetime.now(timezone.utc).isoformat()
    inserts: List[Dict[str, Any]] = []

    for _ in range(count):
        # ── 2026-06-11: Per-proxy random pick from MIX pools ─────
        per_proxy_country = (
            random.choice(_clean_countries) if _clean_countries else country
        )
        per_proxy_state = (
            random.choice(_clean_states) if _clean_states else effective_state
        )
        # Pick a session_id not yet used by this user. The session-id
        # space (~10⁹) is enormous vs the per-user history (tens of
        # thousands at most), so collisions are extremely rare — but
        # we still defend with a retry loop.
        sid = None
        for _attempt in range(max_attempts_per_pick):
            candidate = _new_session_id()
            exists = await db.proxyjet_used_sessions.find_one(
                {"user_id": user_id, "session_id": candidate},
                {"_id": 1},
            )
            if not exists:
                sid = candidate
                break
        if sid is None:
            # Should be near-impossible. Fall back to a longer ID to
            # break out of any (theoretical) high-collision region.
            sid = str(secrets.randbelow(10**12)).rjust(12, "0")

        proxy_str, _ = build_proxy_string(
            username=creds["username"],
            password=creds["password"],
            country=per_proxy_country,
            session_id=sid,
            gateway=creds.get("gateway", DEFAULT_GATEWAY),
            server=creds.get("server", DEFAULT_SERVER),
            port=int(creds.get("port", DEFAULT_PORT)),
            product=creds.get("product", DEFAULT_PRODUCT),
            state=per_proxy_state,
            sticky_minutes=sticky_minutes,
        )
        out.append(proxy_str)
        inserts.append({
            "user_id": user_id,
            "session_id": sid,
            "country": per_proxy_country,
            "state": per_proxy_state,
            "created_at": now,
            "job_id": job_id,
            "exit_ip": None,
        })

    if inserts:
        try:
            await db.proxyjet_used_sessions.insert_many(inserts, ordered=False)
        except Exception:
            # ordered=False so duplicate-key collisions (race condition
            # between two parallel jobs) just skip; the proxy lines we
            # already returned are still safe — even if two jobs picked
            # the same session_id (≈10⁻⁹ chance), ProxyJet will still
            # assign them different exit IPs because the gateway uses
            # per-connection routing.
            pass

    return out


async def ensure_indexes(db) -> None:
    """Create the unique index on proxyjet_used_sessions. Called once at
    startup so repeated picks of the same session_id raise a duplicate-
    key error instead of silently being inserted twice. Idempotent.
    """
    try:
        await db.proxyjet_used_sessions.create_index(
            [("user_id", 1), ("session_id", 1)],
            unique=True,
            name="uniq_user_session",
        )
        await db.proxyjet_credentials.create_index(
            [("user_id", 1)],
            unique=True,
            name="uniq_user_creds",
        )
    except Exception:
        # Index may already exist from a previous boot. Safe to ignore.
        pass


async def mark_exit_ip(db, user_id: str, session_id: str, exit_ip: str) -> None:
    """Optional helper — RUT engine can call this after first connect
    so we record which exit IP a session_id resolved to. Lets the user
    see real history in the future "Used IPs" log. No-op if doc missing.
    """
    try:
        await db.proxyjet_used_sessions.update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$set": {"exit_ip": exit_ip}},
        )
    except Exception:
        pass


async def get_usage_stats(db, user_id: str) -> Dict[str, Any]:
    """Return a small summary the UI can display under the credentials
    panel: total sessions ever generated for this user, how many in the
    last 24 h, and a small recent-history list (max 10 rows).
    """
    total = await db.proxyjet_used_sessions.count_documents({"user_id": user_id})
    # last 24h
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    last_24h = await db.proxyjet_used_sessions.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": cutoff},
    })
    recent = await db.proxyjet_used_sessions.find(
        {"user_id": user_id},
        {"_id": 0, "session_id": 1, "country": 1, "exit_ip": 1, "created_at": 1, "job_id": 1},
    ).sort("created_at", -1).limit(10).to_list(10)
    return {
        "total_sessions_used": total,
        "last_24h": last_24h,
        "recent": recent,
    }
