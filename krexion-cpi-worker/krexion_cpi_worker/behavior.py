"""Behavior simulator — random taps/swipes to mimic real user app sessions.

Keeps the TARGET package foreground throughout. If the user (or any system
event) drifts to another app, we re-launch the target so all behavior
happens INSIDE the target app — required for SDK conversion fire and
to avoid 5-min "browse" actually being on Chrome instead of TikTok.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .adb import ADB

logger = logging.getLogger("cpi.behavior")


async def simulate_session(
    adb: "ADB",
    serial: str,
    duration_seconds: int,
    target_package: Optional[str] = None,
) -> int:
    """Run a random touch session for ~duration_seconds inside `target_package`.

    Every ~10s we verify the focused app is still `target_package`. If not,
    force-stop browsers + re-launch the target. Returns # of actions performed.
    """
    width, height = await adb.screen_size(serial)
    actions = 0
    end_at = asyncio.get_event_loop().time() + duration_seconds
    last_fg_check = 0.0

    while asyncio.get_event_loop().time() < end_at:
        now = asyncio.get_event_loop().time()
        # Foreground enforcement every 10s
        if target_package and (now - last_fg_check) >= 10.0:
            last_fg_check = now
            try:
                fg = await adb.get_foreground_app(serial)
                if fg and fg != target_package:
                    logger.info(f"foreground drifted to {fg}, re-launching {target_package}")
                    await adb.kill_browsers(serial)
                    await adb.start_app(serial, target_package)
                    await asyncio.sleep(2.5)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"foreground check err: {e}")

        choice = random.random()
        if choice < 0.55:
            # Tap somewhere in the central content area (avoid system bars)
            x = random.randint(int(width * 0.15), int(width * 0.85))
            y = random.randint(int(height * 0.20), int(height * 0.85))
            await adb.tap(serial, x, y)
        elif choice < 0.85:
            # Swipe up/down (scroll)
            cx = random.randint(int(width * 0.3), int(width * 0.7))
            y1 = random.randint(int(height * 0.6), int(height * 0.8))
            y2 = random.randint(int(height * 0.2), int(height * 0.4))
            if random.random() < 0.5:
                y1, y2 = y2, y1  # reverse direction
            await adb.swipe(serial, cx, y1, cx, y2, dur_ms=random.randint(200, 600))
        else:
            # Horizontal swipe (carousel / next screen)
            cy = random.randint(int(height * 0.4), int(height * 0.7))
            x1 = random.randint(int(width * 0.7), int(width * 0.9))
            x2 = random.randint(int(width * 0.1), int(width * 0.3))
            await adb.swipe(serial, x1, cy, x2, cy, dur_ms=random.randint(250, 500))
        actions += 1
        # Random pause between actions — real users don't tap continuously
        await asyncio.sleep(random.uniform(1.2, 4.5))
    return actions


async def random_pre_install_delay(min_s: int, max_s: int) -> None:
    delay = random.randint(min_s, max_s)
    logger.debug(f"Pre-install delay: {delay}s")
    await asyncio.sleep(delay)
