"""iOS tools — wraps libimobiledevice / tidevice3 / pymobiledevice3 commands.

Windows-compatible: NO macOS / Xcode required. Works with non-jailbroken iPhones
for basic install (via App Store deeplink) and with jailbroken iPhones for
full automation (sideload IPA, deeper anti-detect).
"""
from __future__ import annotations

import asyncio
import logging
import shlex
import subprocess
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("cpi.ios_tools")


class IOSTools:
    def __init__(self, libimobile_path: str = "", tidevice_path: str = "tidevice3"):
        self.libimobile_path = libimobile_path
        self.tidevice = tidevice_path

    async def _run(self, cmd: List[str], timeout: int = 60) -> Tuple[int, str, str]:
        logger.debug(f"ios run: {' '.join(shlex.quote(c) for c in cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            logger.warning(f"iOS tool not on PATH: {cmd[0]!r} ({e}). iOS engine disabled.")
            return 127, "", f"not found: {cmd[0]}"
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return 124, "", "timeout"
        return proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    # ── Discovery ──────────────────────────────────────────
    async def list_udids(self) -> List[str]:
        # Prefer tidevice3 (cross-platform Python). Falls back to libimobile.
        # If neither tool is on PATH (e.g. Android-only user), return [] gracefully.
        rc, out, err = await self._run([self.tidevice, "list"])
        if rc == 127:
            return []
        if rc == 0:
            udids = []
            for line in out.splitlines():
                line = line.strip()
                if not line or line.startswith("List") or line.startswith("UDID"):
                    continue
                parts = line.split()
                if parts and len(parts[0]) >= 25:
                    udids.append(parts[0])
            if udids:
                return udids
        # libimobile fallback
        bin_id = self._lib_bin("idevice_id")
        rc, out, _ = await self._run([bin_id, "-l"])
        if rc == 127:
            return []
        return [u.strip() for u in out.splitlines() if u.strip()]

    async def info(self, udid: str) -> Dict[str, str]:
        rc, out, _ = await self._run([self.tidevice, "-u", udid, "info"])
        info = {}
        for line in out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()
        return info

    # ── App management ─────────────────────────────────────
    async def list_apps(self, udid: str) -> List[str]:
        rc, out, _ = await self._run([self.tidevice, "-u", udid, "applist"])
        apps = []
        for line in out.splitlines():
            line = line.strip()
            if line:
                # Format: "com.example.app App Name 1.0"
                parts = line.split(maxsplit=1)
                if parts:
                    apps.append(parts[0])
        return apps

    async def install_ipa(self, udid: str, ipa_path_or_url: str) -> Tuple[bool, str]:
        rc, out, err = await self._run(
            [self.tidevice, "-u", udid, "install", ipa_path_or_url],
            timeout=600,
        )
        return rc == 0, (out + err)[-400:]

    async def uninstall(self, udid: str, bundle_id: str) -> bool:
        rc, _, _ = await self._run([self.tidevice, "-u", udid, "uninstall", bundle_id])
        return rc == 0

    async def launch(self, udid: str, bundle_id: str) -> bool:
        rc, _, _ = await self._run([self.tidevice, "-u", udid, "launch", bundle_id])
        return rc == 0

    async def kill(self, udid: str, bundle_id: str) -> None:
        await self._run([self.tidevice, "-u", udid, "kill", bundle_id])

    async def open_url(self, udid: str, url: str) -> bool:
        # Use Safari / open URL via xcrun simctl-like or pymobiledevice springboard
        # tidevice3 supports `safari` action via its automation extension.
        rc, _, _ = await self._run([self.tidevice, "-u", udid, "safari", url])
        return rc == 0

    # ── App Store install (non-jailbroken; requires manual confirm) ──
    async def open_app_store(self, udid: str, app_id: str) -> bool:
        """Open App Store deep link; user/automation must confirm install."""
        url = f"itms-apps://itunes.apple.com/app/id{app_id}"
        return await self.open_url(udid, url)

    # ── Helpers ────────────────────────────────────────────
    def _lib_bin(self, name: str) -> str:
        if self.libimobile_path:
            from os.path import join
            return join(self.libimobile_path, f"{name}.exe" if not name.endswith(".exe") else name)
        return name
