"""
Krexion — Desktop Companion Endpoints
=====================================
Serves the locally-running PyWebView dashboard (desktop/krexion_dashboard.py)
with the live stats it needs to render its widgets.

These endpoints intentionally only do anything meaningful on the
CUSTOMER's local backend (KREXION_MODE=native). On the cloud edge
(krexion.com) they're still mounted — but they return a clear "not
applicable here" payload so any accidental hit from the wrong place
doesn't leak host stats.

Endpoints:

  GET  /api/desktop/stats        Live snapshot for the dashboard
  POST /api/desktop/run-update   Triggers desktop.updater.apply_update()
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("krexion.desktop_module")

# In the NATIVE Windows bundle the `desktop/` package sits at
# {app}/bin/app/desktop and `app/` is on sys.path via python311._pth.
# In the dev container the repo root holds it at /app/desktop. We add
# the repo root once so `from desktop.system_info import ...` succeeds
# in both layouts without an env-var dance.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

desktop_router = APIRouter(prefix="/api/desktop", tags=["desktop"])

# Bound by server.py on startup
_db: Any = None
_get_bridge_stats: Any = None


def _bind(*, main_db, get_bridge_stats=None) -> None:
    global _db, _get_bridge_stats
    _db = main_db
    _get_bridge_stats = get_bridge_stats


# ── Helpers ─────────────────────────────────────────────────────────

def _is_local_mode() -> bool:
    return (os.environ.get("KREXION_MODE") or "local").lower().strip() in {"local", "native"}


def _read_license_summary() -> dict:
    """Best-effort license info read.

    v1.0.13 fix: previously this only read from `_LICENSE_KEY_CACHE`
    which is populated by `license_module.validate_license_key()` —
    a function that ONLY fires when the customer-side proxy validation
    request reaches it. On a fresh native install, before the first
    heartbeat round-trip, the cache is empty and the dashboard shows
    "Inactive" even when a perfectly valid license-key.txt is on disk.
    Now we ALSO fall back to reading the install-time license file at
    `%PROGRAMDATA%\\Krexion\\license-key.txt` so the dashboard says
    "Active" the moment the customer finishes the wizard.
    """
    info = {"active": False, "email": None, "expires_at": None, "key_tail": None}
    # Path 1: runtime in-memory cache (populated after first cloud validation)
    try:
        from license_module import _LICENSE_KEY_CACHE  # type: ignore
        cached = _LICENSE_KEY_CACHE or {}
        if cached:
            info["active"] = bool(cached.get("active", True))
            info["email"] = cached.get("email")
            info["expires_at"] = cached.get("expires_at")
            info["key_tail"] = (cached.get("license_key") or "")[-6:] or None
            if info["active"]:
                return info
    except Exception:  # noqa: BLE001
        pass
    # Path 2: on-disk license file written by the installer's [Code] section
    try:
        candidates = [
            Path(os.environ.get("KREXION_LICENSE_FILE", "")) if os.environ.get("KREXION_LICENSE_FILE") else None,
            Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Krexion" / "license-key.txt",
            Path("/etc/krexion/license-key.txt"),
        ]
        for p in candidates:
            if not p:
                continue
            try:
                if p.exists():
                    raw = p.read_text(encoding="utf-8", errors="ignore").strip()
                    if raw:
                        info["active"] = True
                        info["key_tail"] = raw[-6:]
                        info["email"] = "—"  # email fetched on next cloud heartbeat
                        return info
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return info


def _read_version() -> str:
    """v1.0.13 fix: original implementation only looked at
    `Path(__file__).parent / 'VERSION'`. In a native install the layout
    is:
        H:\\Krexion\\bin\\app\\backend\\desktop_module.py
        H:\\Krexion\\bin\\app\\backend\\VERSION
    which works IF the VERSION file got copied. But our build-backend.py
    copies the source tree without dotfile filtering, so VERSION should
    be there. The customer is still seeing 0.0.0 in the dashboard which
    means EITHER the file is missing OR something is making the relative
    resolution fail at runtime.
    Now we check multiple known locations and the embedded fallback in
    desktop/__init__.__version__ so the badge is NEVER 0.0.0 on a real
    install."""
    candidates = [
        Path(__file__).parent / "VERSION",                # bin/app/backend/VERSION
        Path(__file__).parent.parent / "backend" / "VERSION",  # bin/app/backend/VERSION (alt path)
        Path(__file__).parent.parent / "VERSION",          # bin/app/VERSION (defensive)
    ]
    for p in candidates:
        try:
            if p.exists():
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v
        except Exception:  # noqa: BLE001
            continue
    # Last-ditch: the desktop package itself carries __version__
    try:
        from desktop import __version__  # type: ignore
        return str(__version__)
    except Exception:  # noqa: BLE001
        return "0.0.0"


async def _db_health() -> dict:
    """Returns {connected, collections, last_error}. Wraps in a 2 s
    timeout so a dead Mongo never hangs the dashboard."""
    if _db is None:
        return {"connected": False, "collections": 0, "last_error": "db not bound"}
    try:
        names = await asyncio.wait_for(_db.list_collection_names(), timeout=2.0)
        return {"connected": True, "collections": len(names), "last_error": None}
    except Exception as exc:  # noqa: BLE001
        return {"connected": False, "collections": 0, "last_error": str(exc)[:200]}


async def _cloud_link_status() -> dict:
    """Reads the last heartbeat ack time from the sync_client side. On
    local installs `sync_client.py` updates a tiny status file each
    successful heartbeat — we read that here instead of doing an HTTP
    round-trip every 2 s."""
    status_file = Path(os.environ.get("KREXION_SYNC_STATUS_FILE", "/tmp/krexion-sync-status.json"))
    try:
        if status_file.exists():
            d = json.loads(status_file.read_text(encoding="utf-8-sig"))
            last = d.get("last_heartbeat_at")
            if last:
                age_sec = int(time.time() - float(last))
                return {"connected": age_sec < 120, "last_sync_age": age_sec}
    except Exception:  # noqa: BLE001
        pass
    return {"connected": False, "last_sync_age": None}


def _feature_to_label(feature: str) -> str:
    """Turn a bridge job's `feature` (e.g. 'visual-recorder/start',
    'real-user-traffic/jobs', 'form-filler/jobs', 'adspower/create')
    into a friendly label suitable for the Native dashboard's
    'Active Heavy Jobs' / 'Recent Activity' rows. We don't want raw
    REST-style identifiers on a customer-facing UI."""
    if not feature:
        return "job"
    f = str(feature).strip().lower()
    # Strip leading /api/ in case the cloud auto-route stored the full path
    if f.startswith("/api/"):
        f = f[5:]
    f = f.strip("/")
    # Pretty-print known prefixes — fallback to the prefix itself
    mapping = {
        "visual-recorder": "Visual Recorder",
        "real-user-traffic": "Real User Traffic",
        "rut": "Real User Traffic",
        "form-filler": "Form Filler",
        "proxies": "Proxy Check",
        "adspower": "AdsPower",
        "browser-profile": "Browser Profile",
        "cpi": "CPI",
        "system": "System",
        "sync": "Sync",
        "proxyjet": "ProxyJet",
    }
    head = f.split("/", 1)[0]
    base = mapping.get(head, head.replace("-", " ").title() or "Job")
    # Append sub-action when present (e.g. "Visual Recorder · start")
    tail = f.split("/", 1)[1] if "/" in f else ""
    if tail:
        # Drop any UUID-looking trailing path segments
        parts = [p for p in tail.split("/") if p and not _looks_like_id(p)]
        if parts:
            return f"{base} · {parts[0].replace('-', ' ')}"
    return base


def _looks_like_id(s: str) -> bool:
    """Lightweight UUID/hex/int detector so we don't pollute job labels
    with random ids like '7f3a...'. """
    if not s:
        return False
    if "-" in s and len(s) >= 16:
        return True
    if len(s) >= 8 and all(c in "0123456789abcdefABCDEF" for c in s):
        return True
    if s.isdigit():
        return True
    return False


def _bridge_detail(doc: dict) -> str:
    """Extract a one-line human-readable detail from a bridge_jobs doc.
    Order of preference:
      1. payload.body.url           (RUT / VR / FF target page)
      2. payload.path               (heavy-feature replay path)
      3. error                       (when status=failed)
      4. result.body.session_id     (VR session id, useful on Recent)
    """
    try:
        payload = doc.get("payload") or {}
        body = payload.get("body") if isinstance(payload, dict) else None
        if isinstance(body, dict):
            url = body.get("url") or body.get("offer_url") or body.get("target_url")
            if url:
                return str(url)[:80]
            name = body.get("name") or body.get("label")
            if name:
                return str(name)[:80]
        err = doc.get("error")
        if err:
            return f"⚠ {str(err)[:78]}"
        path = (payload.get("path") if isinstance(payload, dict) else "") or ""
        if path:
            return str(path)[:80]
        result = doc.get("result") or {}
        if isinstance(result, dict):
            rb = result.get("body") or {}
            if isinstance(rb, dict):
                sid = rb.get("session_id") or rb.get("job_id")
                if sid:
                    return f"id={str(sid)[:12]}"
    except Exception:  # noqa: BLE001
        pass
    return ""


async def _active_and_recent_jobs() -> dict:
    """Pulls active + recent heavy jobs from the bridge_jobs collection
    (which is what sync_client.py pulls from).

    v2.1.59 fix: previously the queries used WRONG field names that
    do not exist on bridge_jobs documents at all:
        - projected `kind`     → actual field is `feature`
        - projected `detail`   → no such field; derive from payload
        - filtered `finished_at` and sorted on it → actual is `completed_at`
        - filtered status `completed`/`error` → actual is `done`/`failed`
    Net effect: Recent Activity panel ALWAYS showed "No recent activity"
    even when many jobs were running/completing, and Active Heavy Jobs
    only ever showed bare "job" rows with no description. This restored
    the live activity feed the customer reported missing."""
    out = {"active": [], "recent": [], "throughput": {"jobs_per_hour": 0, "success_rate_pct": 0}}
    if _db is None:
        return out
    try:
        # 1. Active jobs (running or queued on this PC)
        cursor = _db.bridge_jobs.find(
            {"status": {"$in": ["pending", "running"]}},
            projection={
                "_id": 0,
                "feature": 1,
                "status": 1,
                "started_at": 1,
                "created_at": 1,
                "payload": 1,
                "error": 1,
                "result": 1,
            },
            sort=[("created_at", -1)],
            limit=10,
        )
        now = datetime.now(timezone.utc)
        async for doc in cursor:
            start_iso = doc.get("started_at") or doc.get("created_at")
            ago = _humanise_age(start_iso, now)
            out["active"].append({
                "kind": _feature_to_label(doc.get("feature") or ""),
                "status": doc.get("status") or "running",
                "detail": _bridge_detail(doc)[:80],
                "started_ago": ago,
            })

        # 2. Recent completed/failed (last 8)
        cursor = _db.bridge_jobs.find(
            {"status": {"$in": ["done", "failed"]}},
            projection={
                "_id": 0,
                "feature": 1,
                "status": 1,
                "completed_at": 1,
                "payload": 1,
                "error": 1,
                "result": 1,
            },
            sort=[("completed_at", -1)],
            limit=8,
        )
        async for doc in cursor:
            finished = doc.get("completed_at")
            # Map internal "done" → user-facing "completed" so the green
            # badge css class (.job-status-completed) lights up.
            disp_status = "completed" if doc.get("status") == "done" else (doc.get("status") or "completed")
            out["recent"].append({
                "kind": _feature_to_label(doc.get("feature") or ""),
                "status": disp_status,
                "detail": _bridge_detail(doc)[:80],
                "started_ago": _humanise_age(finished, now),
            })

        # 3. Throughput — last hour
        try:
            from datetime import timedelta
            since = now - timedelta(hours=1)
            since_iso = since.isoformat()
            total = await _db.bridge_jobs.count_documents({"completed_at": {"$gte": since_iso}})
            ok = await _db.bridge_jobs.count_documents({
                "completed_at": {"$gte": since_iso}, "status": "done",
            })
            out["throughput"] = {
                "jobs_per_hour": total,
                "success_rate_pct": (100.0 * ok / total) if total else 0.0,
            }
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"job stats query failed: {exc}")
    return out


def _humanise_age(iso_value, now) -> str:
    if not iso_value:
        return ""
    try:
        if isinstance(iso_value, str):
            ts = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        else:
            ts = iso_value
        delta = (now - ts).total_seconds()
        if delta < 60:
            return f"{int(delta)}s ago"
        if delta < 3600:
            return f"{int(delta // 60)}m ago"
        if delta < 86400:
            return f"{int(delta // 3600)}h ago"
        return f"{int(delta // 86400)}d ago"
    except Exception:  # noqa: BLE001
        return ""


async def _dependency_health() -> dict:
    """v2.1.59 — Single-shot check of every external dependency a Krexion
    feature needs so the dashboard can show GREEN/YELLOW/RED for each
    one and the customer knows which feature is usable.

    Currently covers:
        chromium      Playwright browser engine (RUT, Visual Recorder,
                      Browser Profiles, Form Filler all need this)
        playwright    The Python package itself
        adb           Android Debug Bridge (CPI module — Android only)

    Each entry: {status: "ok"|"installing"|"missing"|"error", message: str}
    `status="ok"` means the feature that needs it WILL work right now.
    Anything else is a clear, actionable hint the UI can show.
    """
    out: dict = {}

    # ── Playwright package import ───────────────────────────────────
    try:
        import importlib
        importlib.import_module("playwright.async_api")
        out["playwright"] = {"status": "ok", "message": "package importable"}
    except Exception as exc:  # noqa: BLE001
        out["playwright"] = {
            "status": "missing",
            "message": f"playwright package not importable: {exc}",
        }

    # ── Playwright Chromium binary (the file Playwright actually runs) ─
    try:
        from real_user_traffic import get_engine_status  # type: ignore
        engine = get_engine_status()
        s = (engine or {}).get("status") or "error"
        # Map the existing 4 states 1:1 — the names align with the
        # rest of this dict for easy UI consumption.
        out["chromium"] = {
            "status": s,
            "message": (engine or {}).get("message") or "",
            "expected_revision": (engine or {}).get("expected_revision"),
        }
    except Exception as exc:  # noqa: BLE001
        out["chromium"] = {
            "status": "error",
            "message": f"engine status helper failed: {str(exc)[:120]}",
        }

    # ── adb (Android Debug Bridge) — needed for the CPI Android flow ─
    # Lazy: don't crash this whole endpoint if shutil is funky on the
    # native install (we've seen weird PATH situations on Windows).
    try:
        import shutil as _sh
        adb_path = _sh.which("adb")
        if adb_path:
            out["adb"] = {
                "status": "ok",
                "message": f"adb on PATH: {adb_path}",
            }
        else:
            out["adb"] = {
                "status": "missing",
                "message": (
                    "adb.exe not on PATH. Required for CPI Android flow. "
                    "Install Android Platform-Tools or use the Krexion "
                    "CPI worker which bundles it."
                ),
            }
    except Exception as exc:  # noqa: BLE001
        out["adb"] = {"status": "error", "message": str(exc)[:120]}

    return out


# ── Routes ──────────────────────────────────────────────────────────

@desktop_router.get("/stats")
async def desktop_stats():
    """One-shot snapshot the PyWebView dashboard polls every 2s. We
    keep it heterogeneous (system + license + jobs + cloud-link +
    dependency-health) so the dashboard makes ONE request, not five.
    """
    # Lazy import — keeps the cloud edge clean (system_info is shipped
    # with the desktop bundle, not necessarily present in production
    # Docker containers).
    try:
        from desktop.system_info import get_specs  # type: ignore
        system = get_specs()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"system_info unavailable on this host: {exc}")
        system = {
            "ram_gb": 0, "cpu_cores": 0, "ram_used_gb": 0, "ram_used_pct": 0,
            "cpu_pct": 0, "tier": "unknown", "max_concurrent_heavy_jobs": 2,
            "detected_by": "fallback",
        }

    db_health = await _db_health()
    cloud_link = await _cloud_link_status()
    jobs = await _active_and_recent_jobs() if _is_local_mode() else {
        "active": [], "recent": [],
        "throughput": {"jobs_per_hour": 0, "success_rate_pct": 0},
    }
    # v2.1.59 — dependency health so dashboard can show which features
    # are usable right now vs still installing.
    try:
        deps = await _dependency_health() if _is_local_mode() else {}
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"dependency health check failed: {exc}")
        deps = {}

    return {
        "ok": True,
        "mode": (os.environ.get("KREXION_MODE") or "local").lower(),
        "backend_version": _read_version(),
        "system": system,
        "database": db_health,
        "cloud": cloud_link,
        "license": _read_license_summary(),
        "jobs": jobs,
        "dependencies": deps,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@desktop_router.post("/run-update")
async def desktop_run_update(request: Request):
    """Triggered when the customer clicks the "Update Now" banner in
    the dashboard. Calls `desktop.updater.apply_update()` which:
      1. Downloads the latest Krexion-Setup.exe to %TEMP%
      2. Launches it with /VERYSILENT /SUPPRESSMSGBOXES
      3. Installer stops services, swaps files, restarts services
    """
    if not _is_local_mode():
        # Refuse on cloud edge — VPS doesn't run an installer
        raise HTTPException(400, "Updates only run on the customer's local install.")

    body = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        pass
    target_version = (body or {}).get("target_version")

    try:
        from desktop.updater import apply_update  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Updater module unavailable: {exc}")

    # apply_update is sync (subprocess + requests) — run in thread pool
    # so we don't block the asyncio loop while downloading 400 MB.
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, apply_update, target_version)
    return result


@desktop_router.get("/specs")
async def desktop_specs():
    """Tiny read-only endpoint a future Settings tab could call. Same
    payload as the `system` block in /stats — exposed separately so the
    settings page can display the install-time specs without polling
    the full live snapshot.

    On the cloud edge (where the `desktop` package isn't mounted into
    the backend Docker container), we degrade gracefully and return a
    fallback payload rather than 500 — the cloud frontend never calls
    this endpoint anyway, but better to be quiet than noisy.
    """
    try:
        from desktop.system_info import get_specs  # type: ignore
        return get_specs()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"system_info unavailable on this host: {exc}")
        return {
            "ram_gb": 0,
            "cpu_cores": 0,
            "ram_used_gb": 0,
            "ram_used_pct": 0,
            "cpu_pct": 0,
            "tier": "unknown",
            "max_concurrent_heavy_jobs": 2,
            "detected_by": "fallback",
            "note": "desktop package not available on this host (cloud edge)",
        }
