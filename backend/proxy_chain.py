"""
Krexion — Multi-Hop Proxy Chain (Step 3 / 2026-02 v2.1.31)
============================================================

Defeats single-IP correlation by routing every Playwright visit through
a multi-hop chain: 
    Chromium ─► local HTTP CONNECT proxy ─► hop_1 ─► hop_2 ─► ... ─► target

Typical chain for high-risk affiliate/CPI offers:

    Chromium ─► localhost:RAND ─► Tor SOCKS5 (127.0.0.1:9050)
              ─► residential exit proxy (ProxyJet, Bright Data, etc.)
              ─► target offer URL

Why this matters
----------------
Even with perfect TLS/JA3, perfect fingerprint, perfect behavior, the
single IP your visits exit from is logged in MMP/anti-fraud graphs.
Multiple visits from the same IP cluster against the same offer create
a correlation tell. By interposing Tor (or any second proxy) BEFORE the
exit residential, the exit IP rotates per Tor circuit (~10 min) while
the residential gives the "looks like a real user" final IP. Combined
with our existing PacingEngine + IdentityStore, this breaks the cross-
network correlation graph that AppsFlyer / IPQS / Anura build.

Design constraints
------------------
• Cloud preview env has NO Tor. The module MUST gracefully degrade:
  when Tor (or any first hop) is unreachable, we fall back to single-hop
  (exit proxy only). Callers always get a working proxy URL or None.
• No long-running threads — every chain dies when its owner closes it.
• Tiny, dependency-light: uses python_socks (already installed) for the
  chain build and asyncio TCP for the local CONNECT relay. No pproxy
  subprocess.
• Safe-by-default: caller opts in via `proxy_chain_enabled=True`. Off
  preserves the previous single-proxy behaviour exactly.
"""
from __future__ import annotations

import asyncio
import logging
import re
import socket
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("proxy_chain")

# python_socks is the chain builder. We import lazily so the module can
# import cleanly even if python_socks isn't installed in some envs.
_PS_AVAILABLE = False
try:
    from python_socks import ProxyType  # noqa: F401
    from python_socks.async_.asyncio import Proxy as _PsAsyncProxy
    # Newer python_socks (≥ 2.x) doesn't re-export ProxyChain from the
    # asyncio submodule — the class lives in the parent `_proxy_chain`
    # module. Import it from there so we work on every release.
    from python_socks.async_._proxy_chain import ProxyChain as _PsAsyncProxyChain
    _PS_AVAILABLE = True
except Exception:  # noqa: BLE001
    _PsAsyncProxy = None  # type: ignore
    _PsAsyncProxyChain = None  # type: ignore


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

_HOP_SCHEMES = {"http", "https", "socks5", "socks5h", "socks4"}


def _parse_hop(raw: str) -> Optional[str]:
    """Normalise a hop URI. Accepts:
      • `socks5://host:port`
      • `http://user:pass@host:port`
      • bare `host:port` (assumed http)
      • bare `host:port:user:pass` (the Krexion proxy text format)
    Returns a normalised URI like `http://user:pass@host:port` or None
    if the input is unparseable.
    """
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw:
        return None
    # Krexion's `host:port:user:pass` shorthand
    if "://" not in raw:
        parts = raw.split(":")
        if len(parts) == 4:
            host, port, user, pwd = parts
            return f"http://{user}:{pwd}@{host}:{port}"
        if len(parts) == 2:
            host, port = parts
            return f"http://{host}:{port}"
        return None
    # Full URI
    try:
        u = urlparse(raw)
        if u.scheme not in _HOP_SCHEMES or not u.hostname or not u.port:
            return None
        return raw
    except Exception:
        return None


async def is_host_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    """Cheap TCP connect probe. Returns True if the port accepts a
    connection within `timeout` seconds."""
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        try:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        except Exception:
            pass
        return True
    except Exception:
        return False


async def is_tor_available(socks_host: str = "127.0.0.1", socks_port: int = 9050) -> bool:
    """Returns True when a local Tor SOCKS5 listener is reachable."""
    return await is_host_reachable(socks_host, socks_port, timeout=1.5)


# ──────────────────────────────────────────────────────────────────────
# Local HTTP CONNECT proxy that chains internally via python_socks
# ──────────────────────────────────────────────────────────────────────

_CONNECT_RE = re.compile(rb"^CONNECT\s+([^\s:]+):(\d+)\s+HTTP/", re.IGNORECASE)


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """One-way TCP pump until either side closes."""
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


class _ChainServer:
    """Asyncio-backed local HTTP CONNECT proxy that chains every CONNECT
    through the configured upstream hops via python_socks ProxyChain.

    Lifetime: created by `start_chain(...)`. The owning RUT/Form Filler
    job stops it when the visit completes by calling `.stop()`. Each
    chain serves only one job to keep the threat model isolated.
    """

    def __init__(self, hops: List[str], listen_host: str = "127.0.0.1"):
        self.hops = hops
        self.listen_host = listen_host
        self.listen_port: int = 0
        self._server: Optional[asyncio.AbstractServer] = None
        self._active: int = 0

    async def _handle(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
        self._active += 1
        try:
            # Read the CONNECT request (single line + headers)
            try:
                head = await asyncio.wait_for(
                    client_reader.readuntil(b"\r\n\r\n"), timeout=15.0
                )
            except Exception:
                client_writer.close()
                return
            m = _CONNECT_RE.match(head)
            if not m:
                # Reject anything non-CONNECT — Chromium only sends CONNECT
                # for HTTPS upstreams; HTTP plain GET would need a relay we
                # don't ship. 405 keeps the connection clean.
                client_writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                await client_writer.drain()
                client_writer.close()
                return
            dest_host = m.group(1).decode("ascii", "ignore")
            dest_port = int(m.group(2))

            # Build chained connection through ALL hops
            try:
                if len(self.hops) >= 2 and _PsAsyncProxyChain is not None:
                    chain = _PsAsyncProxyChain([_PsAsyncProxy.from_url(h) for h in self.hops])
                    sock = await chain.connect(
                        dest_host=dest_host,
                        dest_port=dest_port,
                        timeout=30.0,
                    )
                elif len(self.hops) == 1 and _PsAsyncProxy is not None:
                    proxy = _PsAsyncProxy.from_url(self.hops[0])
                    sock = await proxy.connect(
                        dest_host=dest_host,
                        dest_port=dest_port,
                        timeout=30.0,
                    )
                else:
                    # Direct connect — no chain configured
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    await asyncio.get_event_loop().sock_connect(sock, (dest_host, dest_port))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"proxy_chain CONNECT to {dest_host}:{dest_port} failed via chain {self.hops}: {e}")
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                try:
                    await client_writer.drain()
                except Exception:
                    pass
                client_writer.close()
                return

            # Tell the client the tunnel is open
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()

            # Bridge two stream pairs
            try:
                upstream_reader, upstream_writer = await asyncio.open_connection(sock=sock)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"upstream stream wrap failed: {e}")
                try:
                    sock.close()
                except Exception:
                    pass
                client_writer.close()
                return

            await asyncio.gather(
                _pipe(client_reader, upstream_writer),
                _pipe(upstream_reader, client_writer),
                return_exceptions=True,
            )
        finally:
            self._active -= 1
            try:
                client_writer.close()
            except Exception:
                pass

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, self.listen_host, 0)
        # Resolve the actually-bound port
        sock = self._server.sockets[0] if self._server and self._server.sockets else None
        if sock is None:
            raise RuntimeError("proxy_chain: failed to bind local listener")
        self.listen_port = sock.getsockname()[1]
        logger.info(
            "proxy_chain listening on %s:%d → hops=%d (%s)",
            self.listen_host, self.listen_port, len(self.hops),
            " → ".join(_redact(h) for h in self.hops),
        )

    async def stop(self) -> None:
        if self._server is not None:
            try:
                self._server.close()
                try:
                    await self._server.wait_closed()
                except Exception:
                    pass
            except Exception:
                pass
            self._server = None

    @property
    def url(self) -> str:
        return f"http://{self.listen_host}:{self.listen_port}"


def _redact(uri: str) -> str:
    """Redact basic-auth credentials from a hop URI for log lines."""
    try:
        u = urlparse(uri)
        if u.username or u.password:
            netloc = f"{u.username or '?'}:****@{u.hostname}:{u.port}"
            return f"{u.scheme}://{netloc}"
        return uri
    except Exception:
        return uri


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

async def build_chain_hops(
    exit_proxy: Optional[Dict[str, Any]] = None,
    *,
    use_tor: bool = True,
    tor_socks_host: str = "127.0.0.1",
    tor_socks_port: int = 9050,
    extra_hops: Optional[List[str]] = None,
) -> Tuple[List[str], List[str]]:
    """Resolve the desired hop list given runtime config + reachability.
    Returns (hops_resolved, hops_skipped_with_reason). hops_resolved is
    ordered first-to-last (closest to client first)."""
    hops: List[str] = []
    skipped: List[str] = []

    if use_tor:
        if await is_tor_available(tor_socks_host, tor_socks_port):
            hops.append(f"socks5://{tor_socks_host}:{tor_socks_port}")
        else:
            skipped.append(f"tor:{tor_socks_host}:{tor_socks_port}:unreachable")

    if extra_hops:
        for h in extra_hops:
            p = _parse_hop(h)
            if p:
                hops.append(p)
            else:
                skipped.append(f"extra:{h}:invalid")

    if exit_proxy:
        server = (exit_proxy.get("server") or "").strip()
        user = (exit_proxy.get("username") or "").strip()
        pwd = (exit_proxy.get("password") or "").strip()
        if server:
            # Normalise to URI form
            if "://" not in server:
                server = f"http://{server}"
            try:
                u = urlparse(server)
                netloc = u.hostname or ""
                port = u.port or 8080
                if user and pwd:
                    uri = f"{u.scheme or 'http'}://{user}:{pwd}@{netloc}:{port}"
                else:
                    uri = f"{u.scheme or 'http'}://{netloc}:{port}"
                hops.append(uri)
            except Exception:
                skipped.append(f"exit:{server}:parse_error")

    return hops, skipped


async def start_chain(
    exit_proxy: Optional[Dict[str, Any]] = None,
    *,
    use_tor: bool = True,
    extra_hops: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Spin up a local HTTP CONNECT proxy that chains every CONNECT
    through (Tor → extra_hops → exit_proxy). Returns a Playwright-
    compatible payload:

        {
            "proxy":      {"server": "http://127.0.0.1:PORT"},   # for new_context(proxy=...)
            "handle":     ChainServer,                            # owner calls .stop() when done
            "hops":       [hop_1, hop_2, ...],                    # for logging
            "skipped":    [...],                                  # reasons for hops that fell out
            "is_multihop": bool,                                  # convenience flag
        }

    Returns None when no usable hop is available (caller falls back to
    direct or to the single exit_proxy passed straight to Playwright).
    """
    if not _PS_AVAILABLE:
        logger.debug("proxy_chain: python_socks not available — chain disabled")
        return None

    hops, skipped = await build_chain_hops(
        exit_proxy=exit_proxy,
        use_tor=use_tor,
        extra_hops=extra_hops,
    )
    if len(hops) < 1:
        return None

    srv = _ChainServer(hops=hops)
    try:
        await srv.start()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"proxy_chain start failed: {e}")
        return None

    return {
        "proxy": {"server": srv.url},
        "handle": srv,
        "hops": hops,
        "skipped": skipped,
        "is_multihop": len(hops) >= 2,
    }


__all__ = [
    "start_chain",
    "build_chain_hops",
    "is_tor_available",
    "is_host_reachable",
]
