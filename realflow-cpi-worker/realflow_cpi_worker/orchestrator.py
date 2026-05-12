"""Orchestrator — top-level loop that:
  • Discovers connected Android + iOS devices on startup and on each cycle
  • Registers them with the RealFlow backend
  • Sends heartbeats
  • Polls for queued install attempts and dispatches to the right engine
  • Reports results back

Designed to be safe to restart anytime — fully stateless.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .adb import ADB
from .android_engine import AndroidEngine
from .api_client import APIClient
from .config import Config
from .ios_engine import IOSEngine
from .ios_tools import IOSTools

logger = logging.getLogger("cpi.orchestrator")


class DeviceSlot:
    """Tracks one physical device and its currently-running install task."""
    def __init__(self, info: Dict[str, str], engine_kind: str):
        self.info = info
        self.engine_kind = engine_kind          # "android" | "ios"
        self.busy = False
        self.last_install_at: Optional[float] = None
        self.task: Optional[asyncio.Task] = None
        # Backend's device row id (from /devices/register response)
        self.backend_id: Optional[str] = None

    @property
    def serial(self) -> str:
        return self.info["serial"]

    @property
    def device_type(self) -> str:
        return self.info["device_type"]


class Orchestrator:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.api = APIClient(cfg.api.base_url, cfg.api.token)
        self.adb = ADB(cfg.android.adb_path)
        self.ios_tools = IOSTools(cfg.ios.libimobiledevice_path, cfg.ios.tidevice_path)
        self.android_engine = AndroidEngine(self.adb, cfg.android, cfg.workflow)
        self.ios_engine = IOSEngine(self.ios_tools, cfg.ios, cfg.workflow)
        self.slots: Dict[str, DeviceSlot] = {}
        self._stop = asyncio.Event()

    async def run(self):
        logger.info(f"RealFlow CPI Worker starting → backend={self.cfg.api.base_url}")
        try:
            me = await self.api.auth_check()
            logger.info(f"Auth OK as user: {me.get('email')} (status={me.get('status')})")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Auth failed: {e}. Check api.token in config.yaml")
            return

        await self._discover_and_register()
        if not self.slots:
            logger.warning("No devices found. Connect phones via USB and restart.")

        # Main loops
        await asyncio.gather(
            self._heartbeat_loop(),
            self._discovery_loop(),
            self._dispatch_loop(),
        )

    # ── Discovery & registration ───────────────────────────
    async def _discover_and_register(self):
        if self.cfg.android.enabled:
            try:
                for d in await self.android_engine.discover():
                    await self._register_slot(d, "android")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Android discovery failed (continuing): {e}")
        if self.cfg.ios.enabled:
            try:
                for d in await self.ios_engine.discover():
                    await self._register_slot(d, "ios")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"iOS discovery failed (continuing without iOS): {e}")

    async def _register_slot(self, info: Dict[str, str], engine_kind: str):
        if info["serial"] in self.slots:
            return
        try:
            row = await self.api.register_device(
                device_id=info["device_id"],
                device_type=info["device_type"],
                label=info.get("model"),
                model=info.get("model"),
                os_version=info.get("os_version"),
            )
            slot = DeviceSlot(info, engine_kind)
            slot.backend_id = row.get("id")
            self.slots[info["serial"]] = slot
            logger.info(f"Registered {engine_kind} device {info['serial']} ({info.get('model')})")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"register_device failed for {info['serial']}: {e}")

    async def _discovery_loop(self):
        while not self._stop.is_set():
            try:
                await self._discover_and_register()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"discovery loop: {e}")
            await asyncio.sleep(60)

    # ── Heartbeats ─────────────────────────────────────────
    async def _heartbeat_loop(self):
        while not self._stop.is_set():
            for slot in list(self.slots.values()):
                status = "busy" if slot.busy else "online"
                if slot.backend_id:
                    await self.api.heartbeat(slot.backend_id, status=status)
            await asyncio.sleep(self.cfg.api.heartbeat_interval_seconds)

    # ── Job dispatch ───────────────────────────────────────
    async def _dispatch_loop(self):
        while not self._stop.is_set():
            try:
                # Find an idle device
                idle = [s for s in self.slots.values() if not s.busy]
                if not idle:
                    await asyncio.sleep(self.cfg.api.poll_interval_seconds)
                    continue

                slot = idle[0]
                payload = await self.api.poll(
                    device_types=[slot.device_type],
                    device_id=slot.backend_id,
                )
                if not payload.get("has_work"):
                    await asyncio.sleep(self.cfg.api.poll_interval_seconds)
                    continue

                attempt = payload["attempt"]
                job = payload["job"]
                offer = payload["offer"]
                slot.busy = True
                slot.task = asyncio.create_task(
                    self._execute_one(slot, attempt, job, offer),
                    name=f"install-{attempt['id']}",
                )

            except Exception as e:  # noqa: BLE001
                logger.warning(f"dispatch loop: {e}")
                await asyncio.sleep(self.cfg.api.poll_interval_seconds)

    async def _execute_one(self, slot: DeviceSlot, attempt: Dict[str, Any],
                           job: Dict[str, Any], offer: Dict[str, Any]):
        attempt_id = attempt["id"]
        timeout = self.cfg.workflow.install_timeout_seconds
        try:
            if slot.engine_kind == "android":
                coro = self.android_engine.execute_install(slot.serial, attempt, job, offer)
            else:
                coro = self.ios_engine.execute_install(slot.serial, attempt, job, offer)
            success, reason, steps, dur = await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            success, reason, steps, dur = False, "timeout", [{"name": "timeout"}], float(timeout)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"execute_one error: {e}")
            success, reason, steps, dur = False, f"unhandled: {str(e)[:120]}", [], 0.0

        # Report result
        try:
            await self.api.report_result(
                attempt_id=attempt_id,
                success=success,
                failure_reason=reason,
                duration_seconds=dur,
                steps=steps,
                click_id=attempt.get("_click_id"),
                device_id=slot.serial,
                device_label=slot.info.get("model") or slot.serial[:12],
            )
            logger.info(
                f"Attempt {attempt_id[:10]} on {slot.serial}: "
                f"{'OK' if success else 'FAIL'} ({reason or 'completed'}) in {dur:.1f}s"
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"report_result failed: {e}")
        finally:
            slot.busy = False
            slot.last_install_at = time.time()


# ────────────────────────────────────────────────────────────
# Doctor — health check
# ────────────────────────────────────────────────────────────
async def run_doctor(cfg: Config) -> int:
    print("RealFlow CPI Worker — Doctor\n" + "─" * 40)
    api = APIClient(cfg.api.base_url, cfg.api.token)
    try:
        me = await api.auth_check()
        print(f"  ✓ Backend reachable, auth OK ({me.get('email')})")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Backend / auth: {e}")
        await api.close()
        return 1

    if cfg.android.enabled:
        adb = ADB(cfg.android.adb_path)
        devs = await adb.devices()
        print(f"  • Android devices via adb: {len(devs)}")
        for d in devs:
            print(f"      {d['serial']} ({d.get('model')}) state={d['state']}")
    else:
        print("  • Android engine disabled in config")

    if cfg.ios.enabled:
        ios = IOSTools(cfg.ios.libimobiledevice_path, cfg.ios.tidevice_path)
        try:
            udids = await ios.list_udids()
        except Exception as e:  # noqa: BLE001
            udids = []
            print(f"  ! iOS tools error: {e}")
        print(f"  • iOS devices: {len(udids)}")
        for u in udids:
            print(f"      {u}")
    else:
        print("  • iOS engine disabled in config")

    await api.close()
    print("\nDoctor finished. If devices are missing, see CPI-FAQ-URDU.md.")
    return 0
