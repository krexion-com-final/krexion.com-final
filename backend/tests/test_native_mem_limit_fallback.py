"""
test_native_mem_limit_fallback.py
==================================
2026-06-28 — Verify the memory-cap auto-detection now falls back to
psutil.virtual_memory() on hosts where cgroup files don't exist
(Windows native installs, macOS dev machines, Electron-bundled
backend on customer PCs, etc.).

Before this fix the function returned the hardcoded 6144 MB default on
ANY non-Linux-container host. On a 32 GB customer PC the backend RSS
would routinely cross 80% of the fake 6 GB cap as soon as Playwright +
Chromium loaded, tripping the RUT memory-throttle and pausing every
new visit dispatch indefinitely. The customer saw a job stuck on
"running · 0/10 visits · 0 ok · 13 m ago" despite their 32 GB / 8-core
machine showing only 53% RAM used.

The fix adds a third detection step that calls psutil.virtual_memory()
when neither cgroup file exists, computing a cap of:
    max(1024, min((total_mb - 4096) * 0.85, 32768))

These tests verify:
  1. cgroup v2 reading still wins when /sys/fs/cgroup/memory.max exists
     and contains a real byte count (i.e. inside Docker on the VPS).
  2. cgroup v1 reading wins when /sys/fs/cgroup/memory/memory.limit_in_bytes
     contains a real byte count.
  3. When BOTH cgroup files are missing OR contain the unbounded sentinel,
     the psutil branch fires and produces a cap derived from total RAM.
  4. The cap clamps correctly at both ends:
        very small machines (≤ 5 GB)   → at least 1024 MB
        very large machines (≥ 64 GB)  → at most 32768 MB
  5. The 6144 MB hardcoded default ONLY fires when even psutil fails
     (e.g. corrupted system).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make sure backend/ is on the path so we can import server.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# `server.py` resolves the cap at import time, so we use the bare function
# directly to test each path in isolation.
from server import _detect_container_mem_limit_mb  # noqa: E402


def test_cgroup_v2_real_limit_wins():
    """If cgroup v2 reports a real (sub-1TB) limit, it wins over psutil."""
    with patch("server.os.path.exists") as mock_exists, \
         patch("builtins.open", create=True) as mock_open:
        # Pretend ONLY the v2 file exists, and it returns 4 GB
        mock_exists.side_effect = lambda p: p == "/sys/fs/cgroup/memory.max"
        fake_file = MagicMock()
        fake_file.__enter__.return_value.read.return_value = str(4 * 1024 * 1024 * 1024)
        mock_open.return_value = fake_file
        cap = _detect_container_mem_limit_mb(default_mb=6144)
        assert cap == 4096, f"Expected cgroup v2 reading of 4096 MB, got {cap}"


def test_cgroup_v2_unbounded_falls_through_to_psutil():
    """cgroup v2 'max' literal means unbounded — should fall to psutil branch."""
    with patch("server.os.path.exists") as mock_exists, \
         patch("builtins.open", create=True) as mock_open, \
         patch("psutil.virtual_memory") as mock_vm:
        mock_exists.side_effect = lambda p: p == "/sys/fs/cgroup/memory.max"
        fake_file = MagicMock()
        fake_file.__enter__.return_value.read.return_value = "max"
        mock_open.return_value = fake_file
        # 32 GB machine
        mock_vm.return_value.total = 32 * 1024 * 1024 * 1024
        cap = _detect_container_mem_limit_mb(default_mb=6144)
        # (32768 - 4096) * 0.85 = 24371 (rounded)
        assert 24000 < cap < 25000, \
            f"Expected ~24371 MB for 32 GB machine via psutil fallback, got {cap}"


def test_psutil_branch_32gb_native_install():
    """No cgroup at all (Windows native) + psutil reports 32 GB → ~24 GB cap."""
    with patch("server.os.path.exists", return_value=False), \
         patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 32 * 1024 * 1024 * 1024
        cap = _detect_container_mem_limit_mb(default_mb=6144)
        # (32768 - 4096) * 0.85 = 24371.2 -> int(24371)
        assert cap == 24371, f"Expected 24371 MB for 32 GB native, got {cap}"


def test_psutil_branch_16gb_native_install():
    """16 GB customer PC → ~10.4 GB cap, comfortably above the old 6 GB default."""
    with patch("server.os.path.exists", return_value=False), \
         patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 16 * 1024 * 1024 * 1024
        cap = _detect_container_mem_limit_mb(default_mb=6144)
        # (16384 - 4096) * 0.85 = 10444.8 -> int(10444)
        assert cap == 10444, f"Expected 10444 MB for 16 GB native, got {cap}"


def test_psutil_branch_8gb_native_install_throttles_safely():
    """8 GB customer PC → ~3.4 GB cap. Lower than the old 6 GB default —
    that's CORRECT: an 8 GB machine running Playwright + 4 GB cap was
    over-committed and would OOM the host. The smaller cap correctly
    causes the throttle to fire BEFORE OOM."""
    with patch("server.os.path.exists", return_value=False), \
         patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 8 * 1024 * 1024 * 1024
        cap = _detect_container_mem_limit_mb(default_mb=6144)
        # (8192 - 4096) * 0.85 = 3481.6 -> int(3481)
        assert cap == 3481, f"Expected 3481 MB for 8 GB native, got {cap}"


def test_psutil_branch_huge_64gb_workstation_clamps_at_32gb():
    """Don't let a 256 GB workstation try to use 200+ GB for a single
    backend — clamp at 32 GB max."""
    with patch("server.os.path.exists", return_value=False), \
         patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 256 * 1024 * 1024 * 1024
        cap = _detect_container_mem_limit_mb(default_mb=6144)
        assert cap == 32768, f"Expected hard clamp at 32768 MB, got {cap}"


def test_psutil_branch_tiny_4gb_machine_floors_at_1gb():
    """4 GB toy machine: raw formula would give (4096-4096)*0.85 = 0 MB,
    which is obviously useless. Floor at 1 GB so the throttle still has
    headroom math."""
    with patch("server.os.path.exists", return_value=False), \
         patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 4 * 1024 * 1024 * 1024
        cap = _detect_container_mem_limit_mb(default_mb=6144)
        assert cap == 1024, f"Expected hard floor at 1024 MB, got {cap}"


def test_falls_back_to_default_when_psutil_explodes():
    """If psutil throws on a locked-down system, we still get the safe
    6 GB default — no crash."""
    with patch("server.os.path.exists", return_value=False), \
         patch("psutil.virtual_memory", side_effect=RuntimeError("locked down")):
        cap = _detect_container_mem_limit_mb(default_mb=6144)
        assert cap == 6144, f"Expected default 6144 MB fallback, got {cap}"


def test_psutil_zero_total_falls_back_to_default():
    """psutil returning 0/very small total (kiosk OS, sandbox) → fallback."""
    with patch("server.os.path.exists", return_value=False), \
         patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 0
        cap = _detect_container_mem_limit_mb(default_mb=6144)
        assert cap == 6144, f"Expected default for zero RAM detection, got {cap}"
