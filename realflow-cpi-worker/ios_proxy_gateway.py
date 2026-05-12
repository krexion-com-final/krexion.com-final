"""
RealFlow CPI — Local iOS Proxy Gateway

Why this exists:
  iOS does NOT allow programmatic per-install HTTP-proxy switching from
  Windows over USB without a paid MDM enrollment. Even libimobiledevice's
  profile-installation requires UI taps for new signatures.

Workaround used here (zero touch after one-time setup):
  • One-time on the iPhone: Settings → WiFi → Configure Proxy → Manual →
    set the home-PC's LAN IP and port 8866 (this script).
  • This mitmproxy add-on then forwards each iPhone request through a
    rotating Proxy Jet upstream IP picked from a pool. The pool is
    populated live by the RealFlow CPI Worker (orchestrator) per-install.

Run:
  pip install mitmproxy
  mitmdump -s ios_proxy_gateway.py --listen-port 8866

The worker writes to:
  /tmp/realflow-cpi-ios-proxy-pool.json     (Linux/macOS)
  C:\\realflow\\realflow-cpi-worker\\ios-proxy-pool.json  (Windows)

JSON format:
  {
    "<udid>": "host:port:user:pass"
  }
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

POOL_PATHS = [
    Path("C:/realflow/realflow-cpi-worker/ios-proxy-pool.json"),
    Path("/tmp/realflow-cpi-ios-proxy-pool.json"),
    Path(os.path.expanduser("~/.realflow-cpi-ios-proxy-pool.json")),
]

_lock = threading.Lock()
_pool: dict[str, str] = {}
_last_loaded: float = 0.0


def _load_pool():
    global _pool, _last_loaded
    for p in POOL_PATHS:
        if p.exists() and p.stat().st_mtime > _last_loaded:
            try:
                _pool = json.loads(p.read_text(encoding="utf-8"))
                _last_loaded = p.stat().st_mtime
                return
            except Exception:  # noqa: BLE001
                pass


def _pick_upstream(client_ip: str) -> str | None:
    """Pick an upstream proxy. Default: round-robin across all pool entries.
    Future: tag pool keys with WiFi MAC / IP for per-device pinning."""
    _load_pool()
    with _lock:
        if not _pool:
            return None
        # If only one entry, use it. Otherwise round-robin via a counter
        # stored in the module.
        if len(_pool) == 1:
            return next(iter(_pool.values()))
        keys = sorted(_pool.keys())
        idx = (_pick_upstream.counter := getattr(_pick_upstream, "counter", -1) + 1) % len(keys)
        return _pool[keys[idx]]


# ── mitmproxy hooks ──────────────────────────────────────
def request(flow):
    """Set upstream proxy per-flow."""
    upstream = _pick_upstream(flow.client_conn.peername[0])
    if not upstream:
        return  # no upstream configured; let mitmproxy default-pass
    # Format upstream "host:port:user:pass" → mitmproxy URL form
    parts = upstream.split(":")
    if len(parts) == 4:
        host, port, user, pwd = parts
        flow.metadata["upstream_proxy"] = f"http://{user}:{pwd}@{host}:{port}"
    elif len(parts) == 2:
        host, port = parts
        flow.metadata["upstream_proxy"] = f"http://{host}:{port}"
