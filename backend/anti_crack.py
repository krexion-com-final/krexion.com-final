"""
Krexion — Anti-Crack & Hardening Utilities
============================================

Pure-additive hardening layer for customer-shipped builds. Every helper
is wrapped in a top-level try/except so a single missing dependency or
unsupported platform NEVER blocks backend startup. The module is
imported lazily by `server.py` via `run_customer_launch_hardening()`
which itself is wrapped in a guard.

Capabilities provided
---------------------
1. **Hardware Fingerprint (HWID)**  — `compute_hwid()` returns a
   stable SHA-256 derived from machine-level identifiers (machine-id,
   CPU info, MAC of the primary network interface). Used by the
   license server to bind a license key to ONE specific PC so that a
   leaked / stolen license can't be activated on a second machine.

2. **Anti-Debug Scan** — `detect_debugger()` looks for common reverse-
   engineering / debugger processes (IDA, x64dbg, Ollydbg, Process
   Hacker, ProcMon, WinDbg, Cheat Engine, Wireshark, Fiddler, etc.).
   Returns the list of suspicious process names found. The license
   server reads this list via the heartbeat and can revoke the
   license if known cracking tools are detected on the customer's PC.

3. **Binary Integrity Check** — `check_self_integrity()` SHA-256s
   the running Python source / Nuitka binary and compares against a
   trusted manifest shipped at build time. If anyone has patched
   `license_module.py` to bypass checks, the hash mismatch is
   reported back to the license server via heartbeat.

4. **Time-Bomb** — `check_license_freshness(last_check_iso)` returns
   False if the local copy has not phoned-home in N days (default 7),
   so a fully-offline cracked install eventually gets disabled.

5. **Customer launch hardening** — `run_customer_launch_hardening()`
   bundles 1-4 into a single call invoked from server startup. All
   results are stored in a module-level dict that the license module
   can include in every heartbeat payload.

CRITICAL INVARIANTS
-------------------
* This module must NEVER raise — every public function is wrapped.
* In cloud / dev mode (env KREXION_MODE=cloud or HOSTNAME contains
  emergent / k8s indicators), all checks are NO-OPS and return safe
  defaults so the cloud-hosted preview keeps working unchanged.
* No external network calls are made from this module — only local
  system inspection.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Mode detection — cloud preview pods MUST always be no-op so the
# Emergent hosted demo never gets flagged by its own anti-crack layer.
# ──────────────────────────────────────────────────────────────────────
def _is_cloud_or_dev_mode() -> bool:
    """Return True if this process is running in a cloud preview pod
    or in dev mode. Used to short-circuit all enforcement so the demo
    instance is never accidentally locked out by its own checks."""
    try:
        mode = (os.environ.get("KREXION_MODE", "") or "").strip().lower()
        if mode in ("cloud", "dev", "preview", "test"):
            return True
        # Heuristic — Kubernetes / Emergent / Docker hostname patterns
        host = socket.gethostname().lower()
        for tok in ("emergent", "k8s", "kube", "container", "preview", "cluster"):
            if tok in host:
                return True
        # Skip enforcement when no compiled binary marker exists — a
        # Nuitka build sets KREXION_BUILD_TYPE=binary in its frozen
        # environment. Without that marker we assume dev source run.
        if os.environ.get("KREXION_BUILD_TYPE", "").lower() != "binary":
            # Default: enforcement OFF for source runs. Customer builds
            # ship with KREXION_BUILD_TYPE=binary baked in.
            return True
    except Exception:
        return True  # On any error → safe default = cloud (no-op)
    return False


# Cached state populated by `run_customer_launch_hardening()`.
_STATE: Dict[str, Any] = {
    "hwid": None,
    "platform": None,
    "debug_tools_detected": [],
    "integrity_ok": True,
    "integrity_hash": None,
    "checked_at": None,
    "is_cloud_mode": True,  # safe default
}


# ──────────────────────────────────────────────────────────────────────
# 1. Hardware Fingerprint (HWID)
# ──────────────────────────────────────────────────────────────────────
def _read_machine_id_linux() -> Optional[str]:
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(p, "r") as f:
                v = (f.read() or "").strip()
                if v:
                    return v
        except Exception:
            continue
    return None


def _read_machine_id_windows() -> Optional[str]:
    try:
        import subprocess
        # MachineGuid is the canonical Windows install identifier — survives
        # most user-level resets, changes only on full reinstall.
        out = subprocess.check_output(
            ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Cryptography", "/v", "MachineGuid"],
            stderr=subprocess.DEVNULL, timeout=5,
        ).decode("utf-8", errors="ignore")
        for line in out.splitlines():
            if "MachineGuid" in line:
                parts = line.split()
                if parts:
                    return parts[-1].strip()
    except Exception:
        pass
    return None


def _read_machine_id_macos() -> Optional[str]:
    try:
        import subprocess
        out = subprocess.check_output(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            stderr=subprocess.DEVNULL, timeout=5,
        ).decode("utf-8", errors="ignore")
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                return line.split("=")[-1].strip().strip('"')
    except Exception:
        pass
    return None


def _primary_mac() -> Optional[str]:
    """Return the MAC of the primary non-loopback network interface."""
    try:
        import uuid as _uuid
        m = _uuid.getnode()
        # uuid.getnode() returns a random 48-bit value when no real MAC is
        # available — discard that case.
        if (m >> 40) & 0x01:
            return None
        return ":".join(f"{(m >> i) & 0xff:02x}" for i in range(40, -1, -8))
    except Exception:
        return None


def compute_hwid() -> str:
    """Compute a stable hardware fingerprint for this machine.

    Returns a SHA-256 hex digest derived from the strongest available
    identifiers on the current OS. Always returns a string (never
    raises) — falls back to a hash of hostname + platform if all
    stronger sources fail.
    """
    if _STATE.get("hwid"):
        return _STATE["hwid"]
    parts: List[str] = []
    try:
        sys_name = platform.system().lower()
        if "windows" in sys_name:
            mid = _read_machine_id_windows()
            if mid:
                parts.append("win:" + mid)
        elif "darwin" in sys_name:
            mid = _read_machine_id_macos()
            if mid:
                parts.append("mac:" + mid)
        else:
            mid = _read_machine_id_linux()
            if mid:
                parts.append("lin:" + mid)
        mac = _primary_mac()
        if mac:
            parts.append("mac:" + mac)
        parts.append("cpu:" + platform.machine() + ":" + platform.processor())
        parts.append("host:" + socket.gethostname())
    except Exception:
        pass
    if not parts:
        parts = ["fallback:" + socket.gethostname() + ":" + platform.platform()]
    raw = "|".join(parts).encode("utf-8")
    hw = hashlib.sha256(raw).hexdigest()
    _STATE["hwid"] = hw
    return hw


# ──────────────────────────────────────────────────────────────────────
# 2. Anti-Debug — scan for known reverse-engineering tools
# ──────────────────────────────────────────────────────────────────────
_KNOWN_DEBUG_PROCESSES = {
    # Disassemblers / debuggers
    "ida.exe", "ida64.exe", "idaq.exe", "idaq64.exe", "ida-pro",
    "x32dbg.exe", "x64dbg.exe", "ollydbg.exe", "windbg.exe", "windbgx.exe",
    "ghidra.exe", "ghidra", "binaryninja.exe", "binaryninja", "radare2",
    "r2", "cutter.exe", "cutter", "hopper.exe", "hopper",
    # Process inspectors
    "procexp.exe", "procexp64.exe", "procmon.exe", "procmon64.exe",
    "processhacker.exe", "tcpview.exe", "regshot.exe", "regshot64.exe",
    # Network sniffers / API hooking
    "wireshark.exe", "tshark.exe", "fiddler.exe", "fiddler everywhere.exe",
    "charles.exe", "mitmproxy.exe", "mitmweb.exe", "burpsuite",
    "httpdebuggerpro.exe", "httpdebugger.exe",
    # Cheating / patching tools
    "cheatengine-x86_64.exe", "cheatengine-i386.exe", "cheatengine.exe",
    "scylla.exe", "scylla_x64.exe", "scylla_x86.exe",
    "petools.exe", "lordpe.exe", "die.exe", "exeinfope.exe",
    # Code injectors
    "extreme injector v3.exe", "xenos64.exe", "xenos.exe",
}


def detect_debugger() -> List[str]:
    """Scan running processes for known reverse-engineering tools.

    Returns the list of suspicious process names found (lower-cased).
    Empty list = clean. Returns empty list on any error so it never
    contributes a false positive.
    """
    try:
        import psutil  # noqa
    except Exception:
        return []
    found: List[str] = []
    try:
        for p in psutil.process_iter(attrs=["name"]):
            try:
                n = (p.info.get("name") or "").lower()
                if n and n in _KNOWN_DEBUG_PROCESSES:
                    found.append(n)
            except Exception:
                continue
    except Exception:
        return []
    return sorted(set(found))


# ──────────────────────────────────────────────────────────────────────
# 3. Binary Integrity — hash the running source / binary
# ──────────────────────────────────────────────────────────────────────
def _self_path_candidates() -> List[Path]:
    out: List[Path] = []
    try:
        # 1. Nuitka / PyInstaller frozen executable path
        if getattr(sys, "frozen", False):
            out.append(Path(sys.executable))
            return out
        # 2. Source-mode: hash the two most security-critical modules.
        for fn in ("server.py", "license_module.py", "anti_crack.py"):
            p = Path(__file__).parent / fn
            if p.exists():
                out.append(p)
    except Exception:
        pass
    return out


def check_self_integrity() -> Dict[str, Any]:
    """Compute a SHA-256 over the security-critical files (or the
    Nuitka binary in frozen builds) and return the result.

    Returns:
        {
          "hash": "<sha256-hex>",
          "files": ["server.py", "license_module.py", ...],
          "ok": True/False  # vs. trusted manifest if present
        }

    A trusted manifest is read from `<install-dir>/krexion-manifest.json`
    when present. If absent (e.g., source-mode dev runs), `ok=True`
    is returned so dev never gets locked out — the license server
    can still SEE the actual hash via heartbeat and react if it changes
    unexpectedly between two heartbeats from the same HWID.
    """
    result: Dict[str, Any] = {"hash": None, "files": [], "ok": True}
    try:
        paths = _self_path_candidates()
        if not paths:
            return result
        h = hashlib.sha256()
        names: List[str] = []
        for p in paths:
            try:
                names.append(p.name)
                with open(p, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        h.update(chunk)
            except Exception:
                continue
        result["hash"] = h.hexdigest()
        result["files"] = names
        # Manifest comparison — only if a trusted manifest is shipped.
        try:
            mf = Path(__file__).parent.parent / "krexion-manifest.json"
            if mf.exists():
                import json as _json
                with open(mf, "r") as f:
                    expected = _json.load(f).get("integrity_hash")
                if expected and expected != result["hash"]:
                    result["ok"] = False
        except Exception:
            pass
    except Exception:
        pass
    return result


# ──────────────────────────────────────────────────────────────────────
# 4. Time-bomb — disable if no heartbeat in N days
# ──────────────────────────────────────────────────────────────────────
def check_license_freshness(last_check_iso: Optional[str], max_age_days: int = 7) -> bool:
    """Return True if the last successful license server check was
    within `max_age_days`. Returns True if `last_check_iso` is None
    (= never checked, fresh install) so the very first run doesn't
    fail. The license server is expected to reset the timer on every
    successful heartbeat."""
    if not last_check_iso:
        return True
    try:
        # Accept both `Z` and `+00:00` forms.
        s = last_check_iso.replace("Z", "+00:00")
        ts = datetime.fromisoformat(s)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
        return delta <= max_age_days
    except Exception:
        return True


# ──────────────────────────────────────────────────────────────────────
# 5. Launch hardening — single entry-point called from server startup
# ──────────────────────────────────────────────────────────────────────
def run_customer_launch_hardening() -> Dict[str, Any]:
    """Run all hardening checks once at server startup and cache the
    result in `_STATE`. Returns the cached dict. Always succeeds —
    individual checks are independently safe-failed.

    In cloud/dev mode this is a no-op that fills the state with safe
    defaults so the heartbeat payload still has the keys the schema
    expects but the values never trigger enforcement.
    """
    cloud = _is_cloud_or_dev_mode()
    _STATE["is_cloud_mode"] = cloud
    _STATE["platform"] = platform.platform()
    _STATE["checked_at"] = datetime.now(timezone.utc).isoformat()
    if cloud:
        # In cloud / dev — record HWID but skip the active scans.
        try:
            _STATE["hwid"] = compute_hwid()
        except Exception:
            _STATE["hwid"] = "cloud-noop"
        _STATE["debug_tools_detected"] = []
        _STATE["integrity_ok"] = True
        _STATE["integrity_hash"] = None
        logger.info("anti_crack: cloud/dev mode — enforcement disabled, HWID-only")
        return dict(_STATE)
    # Customer-binary mode — full scans
    try:
        _STATE["hwid"] = compute_hwid()
    except Exception:
        _STATE["hwid"] = "compute-failed"
    try:
        _STATE["debug_tools_detected"] = detect_debugger()
    except Exception:
        _STATE["debug_tools_detected"] = []
    try:
        integ = check_self_integrity()
        _STATE["integrity_ok"] = bool(integ.get("ok", True))
        _STATE["integrity_hash"] = integ.get("hash")
    except Exception:
        _STATE["integrity_ok"] = True
        _STATE["integrity_hash"] = None
    if _STATE["debug_tools_detected"]:
        logger.warning(
            f"anti_crack: debugger tools detected: {_STATE['debug_tools_detected']}"
        )
    if not _STATE["integrity_ok"]:
        logger.warning("anti_crack: binary integrity mismatch vs shipped manifest")
    logger.info(
        f"anti_crack: HWID={_STATE['hwid'][:16]}… "
        f"integrity_ok={_STATE['integrity_ok']} "
        f"debug_tools={len(_STATE['debug_tools_detected'])}"
    )
    return dict(_STATE)


def get_hardening_state() -> Dict[str, Any]:
    """Return a shallow copy of the cached hardening state for the
    license module to embed in heartbeat payloads."""
    return dict(_STATE)


# Public re-exports for the license module:
__all__ = [
    "compute_hwid",
    "detect_debugger",
    "check_self_integrity",
    "check_license_freshness",
    "run_customer_launch_hardening",
    "get_hardening_state",
]
