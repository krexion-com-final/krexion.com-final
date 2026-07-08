"""
Krexion Window Icon Override (Windows only)
============================================
Replaces the chrome.exe / chromium.exe taskbar icon at RUNTIME with the
Krexion K-badge — no custom binary build required.

How it works
------------
1. On first import (Windows only), we generate a 32×32 ICO file
   containing the Krexion K-badge (cyan #22d3ee background, dark
   navy K glyph) and cache it under `%TEMP%/krexion_taskbar.ico`.
2. `apply_krexion_icon_to_pid(pid)` uses ctypes + user32 to:
     • Enumerate every top-level window on the desktop.
     • Filter to windows whose owning process ID matches `pid`
       (i.e. the Chromium process we just launched).
     • LoadImage() the cached ICO into two HICON handles
       (16×16 small + 32×32 large).
     • SendMessage(WM_SETICON) on each window → the taskbar entry
       AND the top-left window title-bar chip both flip to Krexion.
     • Keeps a background thread polling every 800 ms so any NEW
       windows the user opens later (new tabs promoted to windows,
       DevTools, print previews, etc.) also get the Krexion icon.
3. Also calls `SetCurrentProcessExplicitAppUserModelID` on the
   spawning Python process so Windows GROUPS the Chromium windows
   under the Krexion taskbar entry instead of a generic "Chrome"
   entry.

Every step is best-effort: on non-Windows platforms all public
functions are no-ops.  On Windows, every failure is swallowed so
this helper can NEVER break profile launches — only makes them
prettier.
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
import time
from typing import Optional, Set

logger = logging.getLogger("krexion.window_icon")

# ── Platform gate ────────────────────────────────────────────────────
_IS_WINDOWS = sys.platform.startswith("win")

# Cache of PIDs whose windows we've already re-iconed at least once,
# so the polling thread doesn't spam SendMessage on unchanged windows.
_ICONED_HWNDS: Set[int] = set()
_LOCK = threading.Lock()


# ── ICO generation ───────────────────────────────────────────────────
def _krexion_ico_path() -> str:
    """Return the on-disk path to a 32×32 Krexion K-badge ICO, creating
    it on first call.  Cached in %TEMP% so it survives across launches
    without any repo-side asset bundling."""
    out = os.path.join(tempfile.gettempdir(), "krexion_taskbar.ico")
    if os.path.exists(out) and os.path.getsize(out) > 200:
        return out
    try:
        # Pillow ships with the Krexion backend stack (already used by
        # RUT screenshot processing).  A pure-stdlib fallback exists
        # below just in case a stripped install is missing PIL.
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Rounded cyan square (approximated by drawing over a rect with
        # 4 pieslices at the corners — PIL's `rounded_rectangle` is 9.2+).
        try:
            draw.rounded_rectangle(
                [(0, 0), (size - 1, size - 1)],
                radius=14,
                fill=(34, 211, 238, 255),  # #22d3ee
            )
        except Exception:
            draw.rectangle([(0, 0), (size - 1, size - 1)], fill=(34, 211, 238, 255))
        # Bold K glyph — use a large system font.  PIL's default is
        # tiny/bitmap so we try DejaVu / Segoe / Arial in that order.
        font = None
        for name in ("segoeuib.ttf", "SegoeUI-Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
            try:
                font = ImageFont.truetype(name, 42)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        text = "K"
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = (size - tw) // 2 - bbox[0]
            ty = (size - th) // 2 - bbox[1] - 2
        except Exception:
            tw, th = draw.textsize(text, font=font)  # legacy PIL
            tx = (size - tw) // 2
            ty = (size - th) // 2 - 2
        draw.text((tx, ty), text, fill=(11, 18, 32, 255), font=font)
        # Save as ICO with 16, 32, 48, 64 subimages so Windows picks
        # the right one for each surface (16 for taskbar list, 32/48
        # for title-bar / alt-tab, 64 for large icons view).
        img.save(out, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        return out
    except Exception as e:
        logger.debug(f"[krexion-icon] Pillow ICO gen failed, using stub: {e}")
        # Stub ICO (16×16, cyan square) — enough for Windows to accept
        # it as a valid icon even if the pretty K glyph is missing.
        stub = _minimal_16x16_cyan_ico()
        try:
            with open(out, "wb") as f:
                f.write(stub)
            return out
        except Exception:
            return ""


def _minimal_16x16_cyan_ico() -> bytes:
    """Hand-built 16×16 32-bit ICO of a solid cyan square.  Zero deps.
    Fallback for environments without Pillow."""
    import struct
    w = h = 16
    # ICONDIR (6 bytes)
    header = struct.pack("<HHH", 0, 1, 1)
    # BITMAPINFOHEADER (40) + pixel data (16×16×4) + AND mask (16×16/8 = 32)
    dib_size = 40 + (w * h * 4) + ((w * h) // 8)
    # ICONDIRENTRY (16 bytes)
    entry = struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, dib_size, 22)
    # BITMAPINFOHEADER
    bih = struct.pack(
        "<IIIHHIIIIII",
        40,          # header size
        w,           # width
        h * 2,       # doubled for ICO XOR+AND
        1, 32,       # planes, bpp
        0, w * h * 4, 0, 0, 0, 0,
    )
    # Pixel rows bottom-up, BGRA cyan
    pixel = struct.pack("<BBBB", 0xEE, 0xD3, 0x22, 0xFF) * (w * h)
    mask = b"\x00" * ((w * h) // 8)
    return header + entry + bih + pixel + mask


# ── Public API ───────────────────────────────────────────────────────
def apply_krexion_icon_to_pid(
    pid: int,
    profile_label: str = "Krexion",
    poll_seconds: float = 45.0,
    poll_interval: float = 0.8,
) -> Optional[threading.Thread]:
    """Spawn a background thread that keeps every top-level window
    owned by `pid` decorated with the Krexion icon for `poll_seconds`
    (long enough for Chromium's late-opening windows — new-tab-in-
    window promotions, DevTools, print previews).

    Returns the thread (already started) or None on non-Windows /
    silent failure.  Every failure is logged at DEBUG level ONLY;
    callers do not need to handle exceptions.
    """
    return apply_krexion_icon_to_pids(
        [pid],
        profile_label=profile_label,
        poll_seconds=poll_seconds,
        poll_interval=poll_interval,
    )


def apply_krexion_icon_to_pids(
    pids: list,
    profile_label: str = "Krexion",
    poll_seconds: float = 60.0,
    poll_interval: float = 0.8,
    parent_pid: Optional[int] = None,
) -> Optional[threading.Thread]:
    """v2.4.1 — Multi-PID variant. Playwright's Chromium spawns a tree
    of processes (browser, renderer, GPU, utility, crashpad_handler…)
    and only the "browser" main process owns the taskbar HWND we need
    to WM_SETICON.  We accept a LIST of PIDs (already discovered by
    the caller) AND — if `parent_pid` is provided — the polling thread
    walks that parent's descendants on every tick, so windows opened
    later (a new tab that gets torn out into its own window, a print
    preview, DevTools) are captured too.

    Non-Windows platforms: no-op returning None.  Any Windows-side
    failure is swallowed so browser launch is never broken.
    """
    if not _IS_WINDOWS:
        return None
    try:
        try:
            import ctypes
            appid = f"Krexion.BrowserProfile.{profile_label}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
        except Exception:
            pass

        ico_path = _krexion_ico_path()
        if not ico_path or not os.path.exists(ico_path):
            logger.debug("[krexion-icon] no ICO available — skipping")
            return None

        _clean = sorted({int(p) for p in (pids or []) if p})
        if not _clean and not parent_pid:
            return None
        t = threading.Thread(
            target=_icon_apply_loop_multi,
            args=(_clean, parent_pid, ico_path, poll_seconds, poll_interval),
            daemon=True,
            name=f"KrexionIcon-{parent_pid or _clean[0]}",
        )
        t.start()
        return t
    except Exception as e:
        logger.debug(f"[krexion-icon] apply failed: {e}")
        return None


def _walk_descendants(parent_pid: int) -> Set[int]:
    """Return the set of descendant PIDs of `parent_pid` using psutil.
    Returns an empty set on any failure so the caller keeps whatever
    PIDs it already had."""
    out: Set[int] = set()
    try:
        import psutil as _psu
        try:
            proc = _psu.Process(parent_pid)
        except Exception:
            return out
        for child in proc.children(recursive=True):
            try:
                out.add(int(child.pid))
            except Exception:
                pass
    except Exception:
        pass
    return out


def _icon_apply_loop_multi(
    seed_pids: list,
    parent_pid: Optional[int],
    ico_path: str,
    deadline_s: float,
    interval_s: float,
) -> None:
    """v2.4.1 — Runs in a daemon thread. Every `interval_s`:
      1. Refresh the PID set by walking `parent_pid`'s descendants
         (so newly-spawned Chromium helpers are picked up).
      2. EnumWindows across the whole desktop; keep any HWND whose
         owning PID is in the set and IsWindowVisible == True.
      3. SendMessage(WM_SETICON, small + big) + SetClassLongPtr for
         inheritance to child windows.
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010

        hicon_small = user32.LoadImageW(
            None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE
        )
        hicon_large = user32.LoadImageW(
            None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE
        )
        if not hicon_small and not hicon_large:
            logger.debug("[krexion-icon] LoadImageW returned 0 for both sizes")
            return

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        GetWindowThreadProcessId = user32.GetWindowThreadProcessId
        GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        GetWindowThreadProcessId.restype = wintypes.DWORD

        deadline = time.time() + deadline_s
        pid_set: Set[int] = {int(p) for p in seed_pids or []}
        # Include the parent itself in case it also owns a window.
        if parent_pid:
            pid_set.add(int(parent_pid))

        while time.time() < deadline:
            # Refresh descendants — Chromium spawns helpers over time.
            if parent_pid:
                pid_set |= _walk_descendants(int(parent_pid))

            found_hwnds = []

            def _cb(hwnd, _lparam):
                try:
                    win_pid = wintypes.DWORD(0)
                    GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
                    if win_pid.value in pid_set:
                        if user32.IsWindowVisible(hwnd):
                            found_hwnds.append(hwnd)
                except Exception:
                    pass
                return True

            user32.EnumWindows(EnumWindowsProc(_cb), 0)

            for hwnd in found_hwnds:
                with _LOCK:
                    already = hwnd in _ICONED_HWNDS
                if already:
                    continue
                try:
                    if hicon_small:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                    if hicon_large:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_large)
                    # Class-icon patch so subsequent child windows
                    # inherit the Krexion icon at creation time.
                    GCLP_HICON = -14
                    GCLP_HICONSM = -34
                    try:
                        SetClassLongPtrW = getattr(user32, "SetClassLongPtrW", user32.SetClassLongW)
                        if hicon_large:
                            SetClassLongPtrW(hwnd, GCLP_HICON, hicon_large)
                        if hicon_small:
                            SetClassLongPtrW(hwnd, GCLP_HICONSM, hicon_small)
                    except Exception:
                        pass
                    with _LOCK:
                        _ICONED_HWNDS.add(hwnd)
                    logger.debug(f"[krexion-icon] applied to hwnd={hwnd}")
                except Exception as se:
                    logger.debug(f"[krexion-icon] SendMessage failed on hwnd={hwnd}: {se}")

            # Fast-exit if the parent process exited (nothing left to icon).
            if parent_pid:
                try:
                    proc = kernel32.OpenProcess(0x1000, False, int(parent_pid))
                    if not proc:
                        return
                    kernel32.CloseHandle(proc)
                except Exception:
                    pass

            time.sleep(interval_s)
    except Exception as e:
        logger.debug(f"[krexion-icon] loop crashed: {e}")


# ── Legacy single-PID loop (kept for backwards compat with any pinned
#    call sites; not used by v2.4.1+ paths). ─────────────────────────
def _icon_apply_loop_LEGACY_do_not_call(pid: int, ico_path: str, deadline_s: float, interval_s: float) -> None:
    """Runs in a daemon thread.  Enumerates windows every `interval_s`
    for `deadline_s` seconds, applying the Krexion ICO to any window
    owned by `pid` that we haven't touched yet."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        # Constants
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010

        # Load two icon handles — small (16) + large (32)
        hicon_small = user32.LoadImageW(
            None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE
        )
        hicon_large = user32.LoadImageW(
            None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE
        )
        if not hicon_small and not hicon_large:
            logger.debug("[krexion-icon] LoadImageW returned 0 for both sizes")
            return

        # EnumWindows callback prototype
        EnumWindowsProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        GetWindowThreadProcessId = user32.GetWindowThreadProcessId
        GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        GetWindowThreadProcessId.restype = wintypes.DWORD

        deadline = time.time() + deadline_s

        while time.time() < deadline:
            found_hwnds = []

            def _cb(hwnd, _lparam):
                try:
                    win_pid = wintypes.DWORD(0)
                    GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
                    if win_pid.value == pid:
                        # Only top-level, visible windows
                        if user32.IsWindowVisible(hwnd):
                            found_hwnds.append(hwnd)
                except Exception:
                    pass
                return True

            user32.EnumWindows(EnumWindowsProc(_cb), 0)

            for hwnd in found_hwnds:
                with _LOCK:
                    already = hwnd in _ICONED_HWNDS
                if already:
                    continue
                try:
                    if hicon_small:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                    if hicon_large:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_large)
                    # Also patch the class icon so any NEW window
                    # spawned from this window inherits Krexion too.
                    GCLP_HICON = -14
                    GCLP_HICONSM = -34
                    try:
                        SetClassLongPtrW = getattr(user32, "SetClassLongPtrW", user32.SetClassLongW)
                        if hicon_large:
                            SetClassLongPtrW(hwnd, GCLP_HICON, hicon_large)
                        if hicon_small:
                            SetClassLongPtrW(hwnd, GCLP_HICONSM, hicon_small)
                    except Exception:
                        pass
                    with _LOCK:
                        _ICONED_HWNDS.add(hwnd)
                    logger.debug(f"[krexion-icon] applied to hwnd={hwnd} pid={pid}")
                except Exception as se:
                    logger.debug(f"[krexion-icon] SendMessage failed on hwnd={hwnd}: {se}")

            # Fast-exit if Chromium quit
            try:
                # OpenProcess with PROCESS_QUERY_LIMITED_INFORMATION
                proc = kernel32.OpenProcess(0x1000, False, pid)
                if not proc:
                    return
                kernel32.CloseHandle(proc)
            except Exception:
                pass

            time.sleep(interval_s)
    except Exception as e:
        logger.debug(f"[krexion-icon] loop crashed: {e}")
