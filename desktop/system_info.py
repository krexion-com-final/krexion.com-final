"""
Krexion System Info Detector
============================
One-stop helper used by:
  * The desktop dashboard       (for the live CPU/RAM gauges)
  * The local backend           (to size the heavy-job semaphore)
  * The sync_client heartbeat   (to inform the cloud about capacity)

It reads ``%PROGRAMDATA%\\Krexion\\system-specs.json`` (written by the
installer's [Code] section) as the authoritative answer — but ALSO
recomputes live from psutil so RAM-used / CPU-load values stay fresh.

Tiers (matches what the installer .iss emits):

  low      → max 1 concurrent heavy job   (4 GB RAM or <= 2 cores)
  medium   → max 2 concurrent heavy jobs  (8 GB RAM or <= 4 cores)
  high     → max 4 concurrent heavy jobs  (16 GB RAM or <= 8 cores)
  extreme  → max 8 concurrent heavy jobs  (16+ GB AND 8+ cores)
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("krexion.system_info")

SPECS_FILE = Path(os.environ.get(
    "KREXION_SYSTEM_SPECS_FILE",
    "C:/ProgramData/Krexion/system-specs.json",
))


def _derive_tier(ram_gb: float, cores: int) -> tuple[str, int]:
    """v1.0.13 rebalance — the v1.0.x ladder was way too conservative:
    it returned only 4 jobs for a 32 GB / 8-core machine because cores
    capped the tier at "high". Real-world headless Chromium is mostly
    network-I/O-bound (waiting on the offer page to load), so CPU
    cores aren't the bottleneck for typical RUT / form-fill traffic
    workloads. RAM is.

    New ladder (memory-driven, with a soft cores-based cap to avoid
    over-committing on tiny CPUs):

      headless_shell ~= 350 MB RAM steady-state. Reserve 4 GB for OS +
      Krexion services. Cap at cores * 8 to keep per-core context
      switching reasonable.

      ram_gb -> usable -> by_ram -> tier (after cores cap)
        4     ->   1  ->    2   -> low      (1)
        8     ->   4  ->   11   -> medium   (8 - cores cap if 1c)
        16    ->  12  ->   34   -> high     (up to 24)
        32    ->  28  ->   80   -> extreme  (up to 56 on 8 cores)
        64    ->  60  ->  171   -> monster  (up to 120 on 16 cores)

    For the customer's 32 GB / 8-core PC the new value is ~56, matching
    the "40-50 concurrent" expectation they had from the original
    settings doc.
    """
    if ram_gb <= 0 or cores <= 0:
        # Specs file wasn't ready yet; play safe.
        return "low", 1

    usable_ram_gb = max(0.5, ram_gb - 4.0)        # reserve 4 GB for OS / Krexion / Mongo
    by_ram = max(1, int(usable_ram_gb / 0.6))      # 600 MB / headless_shell incl. peak headroom
    cores_cap = max(1, cores * 6)                  # 6 jobs per logical core ceiling
    max_jobs = min(by_ram, cores_cap)

    if max_jobs >= 50:
        tier = "monster"
    elif max_jobs >= 25:
        tier = "extreme"
    elif max_jobs >= 10:
        tier = "high"
    elif max_jobs >= 4:
        tier = "medium"
    else:
        tier = "low"
    return tier, max_jobs


def _live_specs() -> dict[str, Any]:
    """Compute current specs from psutil. Best-effort — returns sane
    fallbacks if psutil is missing (which shouldn't happen since it's
    a hard runtime dep, but linters appreciate the guard)."""
    info: dict[str, Any] = {
        "ram_gb": 8.0,
        "cpu_cores": 4,
        "ram_used_gb": 0.0,
        "ram_used_pct": 0.0,
        "cpu_pct": 0.0,
    }
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        info["ram_gb"] = round(vm.total / (1024 ** 3), 1)
        info["ram_used_gb"] = round(vm.used / (1024 ** 3), 1)
        info["ram_used_pct"] = round(vm.percent, 1)
        info["cpu_cores"] = psutil.cpu_count(logical=True) or 4
        # interval=0 returns instantaneous; the caller polls every few
        # seconds so we don't need an averaging window here.
        info["cpu_pct"] = round(psutil.cpu_percent(interval=0), 1)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"psutil unavailable: {exc}")
    tier, max_jobs = _derive_tier(info["ram_gb"], info["cpu_cores"])
    info["tier"] = tier
    info["max_concurrent_heavy_jobs"] = max_jobs
    return info


def _installer_specs() -> Optional[dict[str, Any]]:
    """Read the JSON the installer wrote at first install. None if
    not present (e.g., user is on a dev / non-Inno-installed setup)."""
    try:
        if SPECS_FILE.exists():
            return json.loads(SPECS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Could not read {SPECS_FILE}: {exc}")
    return None


def get_specs() -> dict[str, Any]:
    """Public API — installer values for fixed fields (cores, RAM total,
    tier), live psutil for dynamic fields (CPU %, RAM used)."""
    live = _live_specs()
    installer = _installer_specs()
    if installer:
        # Prefer installer-detected static fields. They survived a
        # reboot, so they're the authoritative answer for what we
        # initialised the system with.
        merged = {**live, **{
            "ram_gb": installer.get("ram_gb", live["ram_gb"]),
            "cpu_cores": installer.get("cpu_cores", live["cpu_cores"]),
            "tier": installer.get("tier", live["tier"]),
            "max_concurrent_heavy_jobs": installer.get(
                "max_concurrent_heavy_jobs", live["max_concurrent_heavy_jobs"],
            ),
            "detected_by": installer.get("detected_by", "live"),
        }}
        return merged
    return {**live, "detected_by": "live"}


def get_max_concurrent_heavy_jobs() -> int:
    """Tiny convenience used by server.py to size its semaphore."""
    try:
        return int(get_specs().get("max_concurrent_heavy_jobs", 2))
    except Exception:  # noqa: BLE001
        return 2


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    json.dump(get_specs(), sys.stdout, indent=2)
    sys.stdout.write("\n")
