"""
Krexion Desktop Dashboard — main entry point
==============================================
Launches as ``krexion-coreapp.exe -m desktop.krexion_dashboard``
(via krexion-tray.bat) on the customer's PC.

Behaviour:
  1. Starts a pystray icon in a background thread.
  2. Opens a PyWebView window pointing at the bundled
     ``static/index.html``. Closing the window's X minimises to tray
     (the dashboard never silently dies).
  3. The HTML polls the local backend (127.0.0.1:8001) for live stats
     and the cloud (krexion.com) for auto-update banners.

Cross-platform-friendly: the imports are wrapped so this file can be
linted on Linux build runners too (the Windows .exe build is the only
place it actually executes).
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

logger = logging.getLogger("krexion.dashboard")

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"
INDEX_FILE = STATIC_DIR / "index.html"

# %PROGRAMDATA%\Krexion is where the installer drops license-key.txt +
# system-specs.json. Used by the tray menu's "Show Specs" item.
PROGRAM_DATA = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Krexion"
LOG_DIR = Path(os.environ.get("KREXION_LOG_DIR", str(HERE.parent.parent.parent / "logs")))

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
    1×1 transparent pixel if the bundled icon is missing (so the tray
    icon still appears, even if it's invisible)."""
    from PIL import Image  # type: ignore
    candidates = [
        HERE / "icons" / "krexion.ico",
        HERE.parent / "krexion.ico",
        HERE.parent.parent / "installer" / "krexion.ico",
    ]
    for p in candidates:
        if p.exists():
            try:
                return Image.open(str(p))
            except Exception:  # noqa: BLE001
                continue
    return Image.new("RGBA", (16, 16), (0, 0, 0, 0))


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
        _tray = _build_tray()
        _tray.run()  # blocks the thread it's called from
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Tray icon failed: {exc}")


def _on_window_closing():
    # Hide instead of close. PyWebView's `closing` event with a return
    # value of `False` cancels the close; we then show the tray icon's
    # "Show Dashboard" as the way back.
    _on_hide_dashboard()
    return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not INDEX_FILE.exists():
        logger.error(f"Dashboard HTML missing at {INDEX_FILE} — aborting.")
        return 1

    # Start tray in background thread BEFORE webview blocks the main thread.
    threading.Thread(target=_start_tray, daemon=True, name="krexion-tray").start()

    # Lazy import so this module is at least parseable in Linux CI lints
    # (pywebview's import pulls in WebView2/edgechromium on Windows).
    import webview  # type: ignore

    global _window
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

    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
