"""
Krexion Desktop Dashboard — main entry point
==============================================
Launches as ``krexion-coreapp.exe -m desktop.krexion_dashboard``
(via krexion-tray.bat) on the customer's PC.

Behaviour:
  1. Sets up a file logger to ``{InstallDir}\\logs\\dashboard.log`` BEFORE
     any heavy imports so even a top-level ImportError leaves a paper
     trail (previous v1.0.4 used pythonw.exe which sends stderr to NUL).
  2. Starts a pystray icon in a background thread.
  3. Opens a PyWebView window pointing at the bundled
     ``static/index.html``. Closing the window's X minimises to tray
     (the dashboard never silently dies).
  4. If PyWebView / WebView2 fail to initialise (common on Win10 PCs
     without the WebView2 runtime installed), we fall back to a
     lightweight Tkinter window that at least surfaces the failure +
     a button to open krexion.com — so the customer ALWAYS sees a
     Krexion window after install, never a silent miss.

Cross-platform-friendly: the imports are wrapped so this file can be
linted on Linux build runners too (the Windows .exe build is the only
place it actually executes).
"""
from __future__ import annotations

# ── File logger setup FIRST — every other import below may raise ─────
import logging
import os
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"
INDEX_FILE = STATIC_DIR / "index.html"

# Locate the install dir's logs/ folder. In the bundled layout the
# desktop package sits at {app}\bin\app\desktop\ so {app}\logs\ is three
# parents up. Fall back to the desktop folder itself if that doesn't
# exist (dev-mode run from repo).
_LOG_DIR_CANDIDATES = [
    Path(os.environ.get("KREXION_LOG_DIR", "")) if os.environ.get("KREXION_LOG_DIR") else None,
    HERE.parent.parent.parent / "logs",   # {app}\logs (native install)
    HERE.parent / "logs",                  # repo dev fallback
    Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Krexion" / "logs",
]
LOG_DIR = next((p for p in _LOG_DIR_CANDIDATES if p), Path.cwd() / "logs")
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:  # noqa: BLE001
    LOG_DIR = Path.cwd()

LOG_FILE = LOG_DIR / "dashboard.log"

# Configure logging immediately — file + (when console attached) stream
_handlers: list[logging.Handler] = []
try:
    _handlers.append(logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"))
except Exception:  # noqa: BLE001
    pass
# If launched from cmd.exe we still want visible output
try:
    if sys.stderr and sys.stderr.fileno() >= 0:
        _handlers.append(logging.StreamHandler(sys.stderr))
except Exception:  # noqa: BLE001
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
    force=True,
)

logger = logging.getLogger("krexion.dashboard")
logger.info("=" * 60)
logger.info("Krexion Dashboard launching")
logger.info(f"  Python    : {sys.executable}")
logger.info(f"  Argv      : {sys.argv}")
logger.info(f"  CWD       : {os.getcwd()}")
logger.info(f"  HERE      : {HERE}")
logger.info(f"  INDEX     : {INDEX_FILE} (exists={INDEX_FILE.exists()})")
logger.info(f"  LOG_FILE  : {LOG_FILE}")


# Global, uncaught-exception hook — logs ANY crash anywhere in the app
def _excepthook(exc_type, exc_value, exc_tb):
    logger.error("UNCAUGHT EXCEPTION:\n" + "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))


sys.excepthook = _excepthook


# %PROGRAMDATA%\Krexion is where the installer drops license-key.txt +
# system-specs.json. Used by the tray menu's "Show Specs" item.
PROGRAM_DATA = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Krexion"

KREXION_CLOUD = os.environ.get("KREXION_CLOUD_URL", "https://krexion.com").rstrip("/")

_window = None
_tray = None


def _open_in_explorer(path: Path) -> None:
    import subprocess
    try:
        if path.exists():
            subprocess.Popen(["explorer", str(path)])
        else:
            logger.warning(f"Cannot open (missing): {path}")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"explorer launch failed: {exc}")


def _on_show_dashboard(_icon=None, _item=None) -> None:
    global _window
    if _window is not None:
        try:
            _window.show()
            _window.restore()
        except Exception:  # noqa: BLE001
            pass


def _on_hide_dashboard(_icon=None, _item=None) -> None:
    global _window
    if _window is not None:
        try:
            _window.hide()
        except Exception:  # noqa: BLE001
            pass


def _on_open_krexion(_icon=None, _item=None) -> None:
    webbrowser.open(f"{KREXION_CLOUD}/login")


def _on_open_logs(_icon=None, _item=None) -> None:
    _open_in_explorer(LOG_DIR)


def _on_open_specs(_icon=None, _item=None) -> None:
    _open_in_explorer(PROGRAM_DATA)


def _on_quit(icon, _item=None) -> None:
    global _window
    try:
        icon.stop()
    except Exception:  # noqa: BLE001
        pass
    try:
        if _window is not None:
            _window.destroy()
    except Exception:  # noqa: BLE001
        pass
    os._exit(0)  # pystray's run() blocks main thread; hard-exit guarantees release.


def _load_tray_icon():
    """Returns a PIL.Image suitable for pystray, falling back to a
    16x16 solid-colour square if the bundled icon is missing (so the
    tray icon still appears, even without the .ico file). Previously
    we returned a 1x1 fully-transparent pixel which Windows refused
    to render at all → tray icon invisible bug."""
    from PIL import Image  # type: ignore
    candidates = [
        HERE / "icons" / "krexion.ico",
        HERE.parent / "krexion.ico",
        HERE.parent.parent / "installer" / "krexion.ico",
        # Native install layout: krexion.ico lives at {app}\krexion.ico
        HERE.parent.parent.parent.parent / "krexion.ico",
    ]
    for p in candidates:
        try:
            if p.exists():
                img = Image.open(str(p))
                logger.info(f"Tray icon loaded from {p}")
                return img
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Tray icon at {p} failed to load: {exc}")
            continue
    # Visible fallback — solid teal square so the icon is at least clickable
    logger.warning("No .ico found, using solid-colour fallback (16x16 teal).")
    return Image.new("RGBA", (16, 16), (45, 212, 191, 255))


def _build_tray():
    import pystray  # type: ignore
    image = _load_tray_icon()
    menu = pystray.Menu(
        pystray.MenuItem("Show Dashboard", _on_show_dashboard, default=True),
        pystray.MenuItem("Hide Dashboard", _on_hide_dashboard),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open krexion.com", _on_open_krexion),
        pystray.MenuItem("View Logs", _on_open_logs),
        pystray.MenuItem("View System Specs", _on_open_specs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Krexion Dashboard", _on_quit),
    )
    return pystray.Icon("Krexion", image, "Krexion — running", menu)


def _start_tray() -> None:
    global _tray
    try:
        logger.info("Tray thread: building icon...")
        _tray = _build_tray()
        logger.info("Tray thread: icon built — entering run() (blocking)")
        _tray.run()  # blocks the thread it's called from
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Tray icon failed: {exc}", exc_info=True)


def _on_window_closing():
    # Hide instead of close. PyWebView's `closing` event with a return
    # value of `False` cancels the close; we then show the tray icon's
    # "Show Dashboard" as the way back.
    _on_hide_dashboard()
    return False


def _launch_pywebview_window() -> bool:
    """Try the normal PyWebView+WebView2 path. Returns True on success,
    False if any import / runtime error indicates the runtime is missing
    so the caller can fall back to Tkinter."""
    if not INDEX_FILE.exists():
        logger.error(f"Dashboard HTML missing at {INDEX_FILE} — cannot start PyWebView.")
        return False

    try:
        import webview  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.error(f"PyWebView import failed: {exc}", exc_info=True)
        return False

    global _window
    try:
        _window = webview.create_window(
            title="Krexion — Local PC Dashboard",
            url=INDEX_FILE.as_uri(),
            width=1180,
            height=760,
            min_size=(960, 640),
            background_color="#0a0e1a",
            easy_drag=False,
            confirm_close=False,
        )
        try:
            _window.events.closing += _on_window_closing
        except Exception:  # noqa: BLE001
            # Older PyWebView versions: gracefully degrade. Window will just
            # close normally and tray will still be alive — customer can
            # reopen from tray.
            pass
        logger.info("PyWebView window created — entering webview.start() loop.")
        webview.start(debug=False)
        logger.info("webview.start() returned cleanly (window closed normally).")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"PyWebView runtime failure (likely WebView2 missing): {exc}", exc_info=True)
        return False


def _launch_native_messagebox_fallback() -> None:
    """Last-resort dialog so the customer is NEVER left wondering whether
    Krexion installed correctly. Uses Win32 ``user32!MessageBoxW`` via
    ``ctypes`` — works in EVERY Python interpreter on Windows including
    the embedded distribution we ship with the installer (which does
    NOT include tcl/tk, so Tkinter is unavailable; we previously tried
    Tkinter as fallback and it crashed too with "Can't find a usable
    init.tcl in the following directories...").

    Shows:
      * Krexion brand + version + reason for compatibility mode
      * Two buttons: "Open krexion.com" + "Open Logs Folder"
      * A close button (does NOT kill the tray icon)

    Falls back to opening krexion.com in the default browser if even
    ctypes is unavailable (which would only happen on a broken
    Python install).
    """
    try:
        import ctypes
        import ctypes.wintypes
    except Exception as exc:  # noqa: BLE001
        logger.error(f"ctypes unavailable, opening krexion.com in browser: {exc}", exc_info=True)
        webbrowser.open(f"{KREXION_CLOUD}/login")
        return

    # MB_OKCANCEL | MB_ICONWARNING | MB_TOPMOST = 0x00040031
    MB_FLAGS = 0x00000001 | 0x00000030 | 0x00040000
    title = "Krexion - Compatibility Mode"
    body = (
        "Krexion is installed and running in the background, but the\n"
        "full dashboard window could not start on this PC.\n\n"
        "Most likely cause: Microsoft Edge WebView2 Runtime is missing.\n"
        "Install it once from:\n"
        "https://go.microsoft.com/fwlink/p/?LinkId=2124703\n\n"
        "Backend services are running on 127.0.0.1:8001. The tray icon\n"
        "should still be visible in the notification area - right-click\n"
        "it for Show Dashboard / Open krexion.com / View Logs.\n\n"
        "Press OK to open krexion.com in your browser,\n"
        "or Cancel to open the logs folder for troubleshooting."
    )

    try:
        rv = ctypes.windll.user32.MessageBoxW(None, body, title, MB_FLAGS)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"MessageBoxW failed: {exc}", exc_info=True)
        webbrowser.open(f"{KREXION_CLOUD}/login")
        return

    # IDOK = 1, IDCANCEL = 2
    if rv == 1:
        webbrowser.open(f"{KREXION_CLOUD}/login")
    elif rv == 2:
        _open_in_explorer(LOG_DIR)
    logger.info(f"Compatibility MessageBox closed (button={rv}).")


def main() -> int:
    # Start tray in background thread BEFORE the GUI blocks the main thread.
    threading.Thread(target=_start_tray, daemon=True, name="krexion-tray").start()

    if _launch_pywebview_window():
        return 0
    # PyWebView failed - fallback so customer ALWAYS sees a window
    logger.warning("Falling back to native Win32 MessageBox compatibility dialog.")
    _launch_native_messagebox_fallback()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("Fatal error in main()")
        # Last-ditch: open krexion.com so user has SOMETHING to click
        try:
            webbrowser.open(f"{KREXION_CLOUD}/login")
        except Exception:  # noqa: BLE001
            pass
        sys.exit(1)
