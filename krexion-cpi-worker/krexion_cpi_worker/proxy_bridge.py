"""Local HTTP proxy bridge.

The phone cannot use authenticated upstream proxies because Android's global
http_proxy setting drops credentials. To work around this we run a tiny local
HTTP proxy on the PC (no auth) that forwards every request to the real
authenticated upstream proxy.

The phone connects to PC_LAN_IP:LISTEN_PORT (no auth) -> bridge -> upstream
authenticated Proxy Jet -> internet. Result: every app on the phone routes
through the chosen geo, including Chrome, TikTok, AppsFlyer SDK, etc.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("cpi.proxy_bridge")


def _get_lan_ip() -> str:
    """Best-effort detect this machine's LAN IP (used as the device-side
    proxy host). Falls back to 127.0.0.1 (only useful for emulators)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class ProxyBridge:
    """Async HTTP/HTTPS proxy that forwards to an authenticated upstream."""

    def __init__(self, listen_port: int = 8788):
        self.listen_port = listen_port
        self.lan_ip = _get_lan_ip()
        self._upstream: Optional[str] = None  # e.g. "user:pass@host:port"
        self._server: Optional[asyncio.base_events.Server] = None

    async def start(self):
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._client_handler, "0.0.0.0", self.listen_port
        )
        logger.info(
            f"ProxyBridge listening on 0.0.0.0:{self.listen_port} "
            f"(phone should use {self.lan_ip}:{self.listen_port})"
        )

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def set_upstream(self, upstream: Optional[str]):
        """upstream format: user:pass@host:port  OR  host:port (no auth)"""
        self._upstream = upstream
        logger.info(f"ProxyBridge upstream -> {self._mask(upstream) if upstream else 'DIRECT'}")

    @staticmethod
    def _mask(p: str) -> str:
        if "@" in p:
            return p.split("@", 1)[0].split(":")[0] + ":***@" + p.split("@", 1)[1]
        return p

    @staticmethod
    def _parse_upstream(s: str) -> Tuple[str, int, Optional[str]]:
        if "@" in s:
            creds, hp = s.split("@", 1)
        else:
            creds, hp = "", s
        host, _, port = hp.partition(":")
        return host, int(port or 80), creds or None

    async def _client_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            await self._handle_one(reader, writer)
        except Exception as e:
            logger.debug(f"client error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_one(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        # Peek the first line to decide CONNECT vs plain HTTP
        try:
            first_line = await asyncio.wait_for(reader.readline(), timeout=20.0)
        except asyncio.TimeoutError:
            return
        if not first_line:
            return

        # Read headers
        headers_raw = b""
        while True:
            line = await reader.readline()
            if not line or line in (b"\r\n", b"\n"):
                headers_raw += line
                break
            headers_raw += line

        if not self._upstream:
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\nNo upstream set\n")
            await writer.drain()
            return

        host, port, creds = self._parse_upstream(self._upstream)

        # Connect to upstream Proxy Jet
        try:
            up_reader, up_writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=15.0
            )
        except Exception as e:
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            logger.warning(f"upstream connect failed: {e}")
            return

        # Build the request to send to upstream:
        # 1. Original first line (CONNECT host:port HTTP/1.1, GET http://... HTTP/1.1, etc.)
        # 2. Inject Proxy-Authorization
        # 3. Pass through original headers (minus existing Proxy-Authorization)
        injected_headers = headers_raw
        if creds:
            auth_b64 = base64.b64encode(creds.encode()).decode()
            # Remove existing Proxy-Authorization if any (case-insensitive)
            new_lines = []
            for line in injected_headers.split(b"\r\n"):
                if line.lower().startswith(b"proxy-authorization:"):
                    continue
                new_lines.append(line)
            injected_headers = b"\r\n".join(new_lines)
            # Inject ours just before the final blank line
            if injected_headers.endswith(b"\r\n\r\n"):
                injected_headers = injected_headers[:-2] + f"Proxy-Authorization: Basic {auth_b64}\r\n\r\n".encode()

        up_writer.write(first_line + injected_headers)
        await up_writer.drain()

        # Now forward bidirectionally
        async def pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter):
            try:
                while True:
                    chunk = await src.read(64 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
                    await dst.drain()
            except Exception:
                pass
            try:
                dst.close()
            except Exception:
                pass

        await asyncio.gather(
            pipe(reader, up_writer),
            pipe(up_reader, writer),
        )


# Module-level singleton (one bridge serves all devices)
_BRIDGE: Optional[ProxyBridge] = None


async def get_bridge(listen_port: int = 8788) -> ProxyBridge:
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = ProxyBridge(listen_port=listen_port)
        await _BRIDGE.start()
    return _BRIDGE
