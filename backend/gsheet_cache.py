"""
gsheet_cache.py
────────────────
Async TTL cache + per-URL single-flight coordination for Google Sheet
reads.

WHY THIS EXISTS
    The whole project pivoted to "live Google Sheets" so users can edit a
    sheet and have every job pick up the latest rows without re-uploading.
    The downside: every endpoint that needs row data — list uploads,
    create job, pick a proxy, pick a UA — calls
    `load_rows_from_google_sheet()` which round-trips to Google's API.
    With one user this feels fine. With 10 users running bulk RUT/CPI
    jobs concurrently it murders latency (Google rate-limits + each call
    is 200-800ms).

WHAT THIS GIVES YOU
    • An async in-memory cache (~20 s TTL by default) keyed by the
      normalised sheet URL (id+gid). Repeat hits within the TTL window
      return INSTANTLY (microseconds) — no Google API call, no HTTP
      round-trip.
    • Per-URL `asyncio.Lock` single-flight: when N concurrent callers hit
      the same expired URL, ONE actually fetches and the rest await the
      same result. Stops the "10 users = 10 fetches" thundering herd.
    • An `invalidate(url)` hook so write paths (delete_row_by_email)
      can drop the stale entry and the next read sees fresh data.

TUNABLES
    Set GSHEET_CACHE_TTL (seconds, default 20) in backend/.env to adjust
    freshness vs. throughput tradeoff. 0 disables the cache entirely.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────── Configuration ──────────────────────────────
def _env_float(key: str, default: float) -> float:
    try:
        v = float((os.environ.get(key) or "").strip() or default)
        return max(0.0, v)
    except Exception:
        return default


_DEFAULT_TTL = _env_float("GSHEET_CACHE_TTL", 60.0)


# ─────────────────────────── URL normalisation ──────────────────────────
_ID_RE = re.compile(r"/d/([a-zA-Z0-9_-]+)")
_GID_RE = re.compile(r"[?&#]gid=(\d+)")


def _normalize_key(url: str) -> str:
    """Two URLs that point at the same sheet+tab should share a cache
    entry. We extract `(spreadsheet_id, gid)` and use that as the key.
    Falls back to the raw URL when ids cannot be parsed (still cached
    correctly per-string)."""
    if not url:
        return ""
    m = _ID_RE.search(url)
    sid = m.group(1) if m else None
    gm = _GID_RE.search(url)
    gid = gm.group(1) if gm else "0"
    if sid:
        return f"{sid}#{gid}"
    return url.strip()


# ─────────────────────────── State ──────────────────────────────────────
# entries:   key  -> { "value": Any, "expires_at": float }
# locks:     key  -> asyncio.Lock (created lazily; lives for process)
_entries: Dict[str, Dict[str, Any]] = {}
_locks: Dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()
# Stats — useful for ops dashboards
stats: Dict[str, int] = {"hits": 0, "misses": 0, "single_flight_waits": 0, "invalidations": 0}


async def _get_lock(key: str) -> asyncio.Lock:
    """Lazily create + reuse a per-URL lock."""
    lock = _locks.get(key)
    if lock is not None:
        return lock
    async with _locks_lock:
        lock = _locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _locks[key] = lock
        return lock


def _now() -> float:
    return time.monotonic()


# ─────────────────────────── Public API ─────────────────────────────────
async def get_or_fetch(
    url: str,
    fetcher: Callable[[], Awaitable[Any]],
    ttl: Optional[float] = None,
) -> Any:
    """Return a cached value for `url` if fresh, otherwise call
    `fetcher()` ONCE (single-flight) and cache the result.

    `fetcher` is a zero-arg async callable so callers can lazy-bind
    the actual fetch (e.g. a closure capturing the original URL).
    """
    use_ttl = _DEFAULT_TTL if ttl is None else max(0.0, float(ttl))
    if use_ttl <= 0:
        # Caching disabled — just fetch directly
        return await fetcher()

    key = _normalize_key(url)
    if not key:
        return await fetcher()

    # Fast path: fresh hit, no lock needed
    entry = _entries.get(key)
    now = _now()
    if entry and entry["expires_at"] > now:
        stats["hits"] += 1
        return entry["value"]

    # Slow path: take the per-URL lock and re-check inside (single-flight)
    lock = await _get_lock(key)
    waited = lock.locked()
    async with lock:
        if waited:
            stats["single_flight_waits"] += 1
        entry = _entries.get(key)
        now = _now()
        if entry and entry["expires_at"] > now:
            # Another caller filled the cache while we were waiting.
            stats["hits"] += 1
            return entry["value"]
        stats["misses"] += 1
        value = await fetcher()
        _entries[key] = {"value": value, "expires_at": now + use_ttl}
        # Light-weight bound: if the cache grows past 1024 distinct URLs,
        # drop the 256 oldest. Real production won't hit this — sheets
        # per user are O(1-50).
        if len(_entries) > 1024:
            _evict_lru(256)
        return value


def invalidate(url: str) -> bool:
    """Drop the cached value for `url` so the next read re-fetches.
    Returns True when an entry was actually removed."""
    key = _normalize_key(url)
    if not key:
        return False
    removed = _entries.pop(key, None)
    if removed is not None:
        stats["invalidations"] += 1
        return True
    return False


def invalidate_all() -> int:
    """Drop every cached entry. Returns count removed."""
    n = len(_entries)
    _entries.clear()
    if n:
        stats["invalidations"] += n
    return n


def _evict_lru(n: int) -> None:
    """Drop the `n` entries with the earliest expiry. Cheap O(N log N)
    on a small cache (≤1024)."""
    if n <= 0 or not _entries:
        return
    items = sorted(_entries.items(), key=lambda kv: kv[1]["expires_at"])
    for k, _ in items[:n]:
        _entries.pop(k, None)


def snapshot() -> Dict[str, Any]:
    """Return a debug snapshot of cache state — exposed via an admin
    endpoint so ops can verify hit-ratio in production."""
    now = _now()
    fresh = sum(1 for e in _entries.values() if e["expires_at"] > now)
    return {
        "ttl_seconds": _DEFAULT_TTL,
        "entries": len(_entries),
        "fresh_entries": fresh,
        "locks": len(_locks),
        "hits": stats["hits"],
        "misses": stats["misses"],
        "single_flight_waits": stats["single_flight_waits"],
        "invalidations": stats["invalidations"],
        "hit_ratio": (stats["hits"] / max(1, stats["hits"] + stats["misses"])),
    }
