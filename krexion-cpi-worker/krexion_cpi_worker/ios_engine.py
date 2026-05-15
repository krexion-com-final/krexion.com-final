"""iOS install engine — single install workflow on one iPhone.

Capabilities depend heavily on whether the device is jailbroken:
  • Non-jailbroken: limited — can install via Apple ID + App Store deep link
    (requires interactive user confirmation OR pre-warmed Apple ID session).
  • Jailbroken (palera1n / checkra1n): full sideload via tidevice3 install IPA,
    deeper anti-detect (carrier spoof, GAID equivalent, device tweaks).

Phase 3 ships the core flow; advanced jailbreak tweaks can be plugged in via
the `tweaks/` directory (user-supplied .deb modules).
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from .config import IOSConfig, WorkflowConfig
from .ios_tools import IOSTools

logger = logging.getLogger("cpi.ios")


class IOSEngine:
    def __init__(self, ios: IOSTools, cfg: IOSConfig, wf: WorkflowConfig):
        self.ios = ios
        self.cfg = cfg
        self.wf = wf

    async def discover(self) -> List[Dict[str, str]]:
        udids = await self.ios.list_udids()
        result = []
        for udid in udids:
            if self.cfg.serial_allowlist and udid not in self.cfg.serial_allowlist:
                continue
            info = await self.ios.info(udid)
            result.append({
                "device_id": udid,
                "serial": udid,
                "device_type": "ios_real",
                "model": info.get("ProductType") or info.get("DeviceName") or "iPhone",
                "os_version": f"iOS {info.get('ProductVersion', '?')}",
            })
        return result

    async def execute_install(
        self,
        udid: str,
        attempt: Dict[str, Any],
        job: Dict[str, Any],
        offer: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]], float]:
        steps: List[Dict[str, Any]] = []
        t0 = time.time()
        click_id = f"rf_{int(t0)}_{random.randint(1000,9999)}"
        attempt["_click_id"] = click_id

        def step(name: str, ok: bool = True, **kw):
            steps.append({"name": name, "ok": ok, "ts": time.time() - t0, **kw})

        ipa_url = offer.get("ipa_url") or ""
        ios_app_id = offer.get("ios_app_id") or ""
        bundle_id = offer.get("package_name") or ""  # we reuse this column for iOS bundle
        tracker_url = offer.get("tracker_url") or ""
        proxy = attempt.get("proxy_used")

        try:
            # 0) Update the local iOS proxy gateway pool so this device's
            #    next outbound request goes via the proxy assigned by the
            #    backend. The iPhone must already point its WiFi proxy at
            #    the home-PC's mitmproxy gateway (one-time setup).
            self._write_proxy_pool(udid, proxy)
            step("proxy_gateway_set", proxy=(proxy.split("@")[0] if proxy else "(none)"))

            # 1) Reset state — uninstall existing app instance if present
            if bundle_id:
                await self.ios.uninstall(udid, bundle_id)
            step("reset_state")

            # NOTE on iOS proxy:
            # iOS does not accept HTTP proxy via libimobiledevice. The user
            # must configure the iPhone's WiFi proxy ONE TIME during setup
            # (Settings → WiFi → Configure Proxy → Manual). The home-PC
            # router can be configured to route iPhone traffic through a
            # local proxy that itself rotates Proxy Jet upstream IPs per
            # connection (mitmproxy with a transparent rotation rule).
            # For a single-iPhone POC, set ONE Proxy Jet IP in WiFi proxy
            # and let RUT-style rotation happen at the upstream level.

            # 2) Click tracker URL — open in Safari
            click_url = self._inject_click_id(tracker_url, click_id)
            await self.ios.open_url(udid, click_url)
            step("click_tracker")

            # 3) Realistic pre-install wait
            delay = random.randint(self.wf.pre_install_min_seconds,
                                    self.wf.pre_install_max_seconds)
            await asyncio.sleep(delay)

            # 4) Install
            #    Path A: direct IPA sideload (works ALWAYS via tidevice3,
            #            ipa must be re-signed for the device's Apple ID)
            #    Path B: App Store deep link (requires Apple ID logged in
            #            and the user/script to tap "Get → Install")
            if ipa_url:
                ok, msg = await self.ios.install_ipa(udid, ipa_url)
                if not ok:
                    step("install_ipa", ok=False, msg=msg[-200:])
                    return False, f"ipa_install_failed: {msg[-120:]}", steps, time.time() - t0
                step("install_ipa")
            elif ios_app_id:
                opened = await self.ios.open_app_store(udid, ios_app_id)
                if not opened:
                    step("app_store_open", ok=False)
                    return False, "app_store_open_failed", steps, time.time() - t0
                step("app_store_open")
                # The actual install confirmation is interactive on non-jailbroken
                # devices. We wait a longer settle to give a pre-paired Apple ID
                # auto-confirm path (e.g., AltStore) time to complete.
                await asyncio.sleep(random.uniform(45, 90))
                step("app_store_settle")
            else:
                return False, "no_ipa_or_appid", steps, time.time() - t0

            # 5) Launch app
            if bundle_id:
                ok = await self.ios.launch(udid, bundle_id)
                if ok:
                    step("app_launched")
                else:
                    step("app_launched", ok=False)
                # Let the SDK fire its install event
                await asyncio.sleep(random.uniform(8, 18))

            # 6) Behavior simulation —  via tidevice3 perfd / WDA touches.
            # For non-jailbroken non-WDA setups we just keep the app
            # foregrounded for a realistic session length.
            beh = random.randint(self.wf.behavior_min_seconds, self.wf.behavior_max_seconds)
            await asyncio.sleep(beh)
            step("behavior_passive", duration=beh)

            # 7) Settle wait
            settle = job.get("settle_seconds", self.wf.default_settle_seconds)
            await asyncio.sleep(settle)
            step("settle", seconds=settle)

            # 8) Cleanup
            if bundle_id:
                await self.ios.kill(udid, bundle_id)
                await self.ios.uninstall(udid, bundle_id)
            step("cleanup")

            return True, None, steps, time.time() - t0

        except Exception as e:  # noqa: BLE001
            logger.exception(f"iOS install error on {udid}: {e}")
            step("exception", ok=False, error=str(e)[:200])
            return False, f"exception: {str(e)[:120]}", steps, time.time() - t0

    @staticmethod
    def _inject_click_id(url: str, click_id: str) -> str:
        if not url:
            return ""
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}click_id={click_id}&aff_sub5={click_id}"

    @staticmethod
    def _write_proxy_pool(udid: str, proxy: Optional[str]) -> None:
        """Write/update this device's current upstream proxy assignment to
        the JSON file consumed by ios_proxy_gateway.py."""
        import json
        from pathlib import Path
        candidates = [
            Path("C:/krexion/krexion-cpi-worker/ios-proxy-pool.json"),
            Path("/tmp/krexion-cpi-ios-proxy-pool.json"),
        ]
        for p in candidates:
            try:
                if p.parent.exists():
                    pool = {}
                    if p.exists():
                        try:
                            pool = json.loads(p.read_text(encoding="utf-8"))
                        except Exception:  # noqa: BLE001
                            pool = {}
                    if proxy:
                        pool[udid] = proxy
                    elif udid in pool:
                        del pool[udid]
                    p.write_text(json.dumps(pool, indent=2), encoding="utf-8")
                    return
            except Exception:  # noqa: BLE001
                continue
