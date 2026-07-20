"""Krexion Desktop Dashboard — runs only on the customer's PC.

This package is bundled inside the native Windows build at
``{install_dir}\\bin\\app\\desktop\\`` and launched via
``{install_dir}\\krexion-tray.bat`` which invokes the renamed
``krexion-coreapp.exe`` (== pythonw.exe) interpreter.

The dashboard window:
  * Loads ``static/index.html`` via PyWebView (no external browser dep)
  * Polls the local backend at ``http://127.0.0.1:8001/api/desktop/stats``
    every 2 s for CPU / RAM / job stats
  * Polls ``https://krexion.com/api/system/public-latest`` every 15 min
    for new-version banners (auto-update workflow)
  * Sits in the system tray (pystray) — closing the X minimises to tray;
    a real "Quit" lives in the tray menu so the customer never
    accidentally kills it
"""
__version__ = "2.6.15"
