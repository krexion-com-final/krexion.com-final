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


def _launch_tkinter_fallback() -> None:
    """Last-resort window so the customer is NEVER left wondering
    whether Krexion installed correctly. Uses Tkinter (ships with
    embeddable CPython, no extra deps).

    Shows:
      * Krexion brand text + version
      * Backend status (polled every 2 s)
      * "Open krexion.com" + "Open logs folder" buttons
      * A clear "WebView2 runtime not detected — install it from
        https://go.microsoft.com/fwlink/p/?LinkId=2124703" hint
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Tkinter unavailable, no GUI possible: {exc}", exc_info=True)
        return

    import urllib.request

    root = tk.Tk()
    root.title("Krexion — Local PC Dashboard (compatibility mode)")
    root.configure(bg="#0a0e1a")
    root.geometry("720x460")
    root.minsize(640, 400)

    # Brand header
    header = tk.Frame(root, bg="#0a0e1a")
    header.pack(fill="x", padx=24, pady=(22, 8))
    tk.Label(header, text="KREXION", fg="#2dd4bf", bg="#0a0e1a",
             font=("Segoe UI", 20, "bold")).pack(side="left")
    tk.Label(header, text="Local PC Dashboard", fg="#94a3b8", bg="#0a0e1a",
             font=("Segoe UI", 11)).pack(side="left", padx=12, pady=(8, 0))

    # Status box
    status_frame = tk.Frame(root, bg="#0f172a", highlightthickness=1,
                             highlightbackground="#1e293b")
    status_frame.pack(fill="x", padx=24, pady=12)
    backend_lbl = tk.Label(status_frame, text="Backend: checking...",
                            fg="#e2e8f0", bg="#0f172a",
                            font=("Segoe UI", 11), anchor="w", padx=18, pady=14)
    backend_lbl.pack(fill="x")

    # Compatibility notice
    notice_frame = tk.Frame(root, bg="#1e293b")
    notice_frame.pack(fill="x", padx=24, pady=8)
    tk.Label(notice_frame,
             text=("Compatibility-mode window. The full Krexion Dashboard\n"
                   "requires Microsoft WebView2 Runtime on Windows 10.\n"
                   "Install it from: go.microsoft.com/fwlink/p/?LinkId=2124703"),
             fg="#fbbf24", bg="#1e293b",
             font=("Segoe UI", 9), justify="left", padx=14, pady=12).pack(anchor="w")

    # Buttons
    btn_frame = tk.Frame(root, bg="#0a0e1a")
    btn_frame.pack(fill="x", padx=24, pady=(8, 20))

    def open_url(u):
        webbrowser.open(u)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Krexion.TButton", background="#2dd4bf", foreground="#0a0e1a",
                    font=("Segoe UI", 10, "bold"), padding=10, borderwidth=0)
    style.map("Krexion.TButton", background=[("active", "#14b8a6")])

    ttk.Button(btn_frame, text="Open krexion.com", style="Krexion.TButton",
               command=lambda: open_url(f"{KREXION_CLOUD}/login")).pack(side="left", padx=(0, 8))
    ttk.Button(btn_frame, text="Install WebView2", style="Krexion.TButton",
               command=lambda: open_url("https://go.microsoft.com/fwlink/p/?LinkId=2124703")).pack(side="left", padx=8)
    ttk.Button(btn_frame, text="View Logs", style="Krexion.TButton",
               command=lambda: _open_in_explorer(LOG_DIR)).pack(side="left", padx=8)
    ttk.Button(btn_frame, text="Quit", style="Krexion.TButton",
               command=root.destroy).pack(side="right")

    # Footer
    tk.Label(root,
             text="Krexion runs in the system tray. Closing this window keeps services running.",
             fg="#64748b", bg="#0a0e1a", font=("Segoe UI", 9)).pack(side="bottom", pady=8)

    # Poll backend status every 2 s
    def poll_backend():
        try:
            with urllib.request.urlopen("http://127.0.0.1:8001/api/desktop/stats", timeout=2) as r:
                if r.status == 200:
                    backend_lbl.config(text="Backend: ONLINE — local engine reachable on 127.0.0.1:8001",
                                       fg="#2dd4bf")
                else:
                    backend_lbl.config(text=f"Backend: HTTP {r.status}", fg="#fbbf24")
        except Exception as exc:  # noqa: BLE001
            backend_lbl.config(text=f"Backend: unreachable ({type(exc).__name__})", fg="#fb7185")
        root.after(2000, poll_backend)

    root.after(500, poll_backend)
    logger.info("Tkinter fallback window entering mainloop.")
    root.mainloop()


def main() -> int:
    # Start tray in background thread BEFORE the GUI blocks the main thread.
    threading.Thread(target=_start_tray, daemon=True, name="krexion-tray").start()

    if _launch_pywebview_window():
        return 0
    # PyWebView failed → fallback so customer ALWAYS sees a window
    logger.warning("Falling back to Tkinter compatibility window.")
    _launch_tkinter_fallback()
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
