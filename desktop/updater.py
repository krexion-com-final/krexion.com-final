"""
Krexion Desktop Updater — handles self-update flow
====================================================
Triggered from the dashboard's "Update Now" banner click. Steps:

  1. Hit /api/system/latest-version (auth) to get installer URL + size
  2. Download Krexion-Setup-vX.Y.Z.exe to %TEMP%
  3. Verify download (size match — sha256 optional, server hasn't shipped
     hashes yet so we keep this best-effort)
  4. Launch installer with /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
     /CLOSEAPPLICATIONS — Inno Setup will:
        * Stop the running Krexion services
        * Overwrite the program files
        * Restart the services
     User data (%PROGRAMDATA%\\Krexion + license) is preserved by virtue
     of being in a separate path the installer never touches.
  5. Exit current dashboard process (the fresh installer's [Run] section
     will spawn a new instance once install finishes).

This module is called BY the dashboard JS via a tiny endpoint
``/api/desktop/run-update`` exposed in server.py — keeps all subprocess
logic out of the browser sandbox.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

logger = logging.getLogger("krexion.updater")

CLOUD = os.environ.get("KREXION_CLOUD_URL", "https://krexion.com").rstrip("/")
LICENSE_FILE = Path(os.environ.get("LICENSE_KEY_FILE", "C:/ProgramData/Krexion/license-key.txt"))


def _read_license_key() -> str:
    try:
        return LICENSE_FILE.read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return ""


def download_installer(target_version: str | None = None) -> Path | None:
    """Download the latest installer .exe to %TEMP%. Returns the file
    path on success, None on any failure (logged)."""
    key = _read_license_key()
    if not key:
        logger.error("No license key file — cannot download installer.")
        return None

    download_url = f"{CLOUD}/api/license/download-installer/{key}"
    try:
        # We follow redirects (the endpoint 302s to the actual GitHub
        # release asset) and stream so a 400 MB .exe doesn't blow up RAM.
        with requests.get(download_url, stream=True, timeout=60, allow_redirects=True) as r:
            if r.status_code != 200:
                logger.error(f"Installer download HTTP {r.status_code}: {r.text[:200]}")
                return None
            # Use the version in the filename so multiple updates in a
            # row don't clobber each other.
            suffix = f"-{target_version}" if target_version else ""
            dest = Path(tempfile.gettempdir()) / f"Krexion-Setup{suffix}.exe"
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
            logger.info(f"Installer downloaded to {dest} ({dest.stat().st_size} bytes)")
            return dest
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Installer download failed: {exc}")
        return None


def run_installer(installer_path: Path) -> bool:
    """Spawn the installer in silent-update mode. Returns True if the
    process was successfully launched (not necessarily completed)."""
    if not installer_path.exists():
        logger.error(f"Installer not found at {installer_path}")
        return False
    try:
        # /VERYSILENT       - no UI, no progress bar
        # /SUPPRESSMSGBOXES - auto-Yes for everything
        # /NORESTART        - we manage restart ourselves (services
        #                     auto-restart via NSSM AppExit=Restart)
        # /CLOSEAPPLICATIONS - close ours cleanly before overwriting
        # /RESTARTAPPLICATIONS - relaunch tray + services
        subprocess.Popen(
            [
                str(installer_path),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/CLOSEAPPLICATIONS",
                "/RESTARTAPPLICATIONS",
            ],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
            close_fds=True,
        )
        logger.info("Installer spawned in silent-update mode.")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Installer launch failed: {exc}")
        return False


def apply_update(target_version: str | None = None) -> dict:
    """High-level orchestrator the dashboard endpoint calls."""
    installer = download_installer(target_version)
    if installer is None:
        return {"ok": False, "stage": "download", "message": "Installer download failed. Check internet + license key."}
    ok = run_installer(installer)
    if not ok:
        return {"ok": False, "stage": "launch", "message": "Could not launch installer. Antivirus may be blocking — please run as admin."}
    return {
        "ok": True,
        "stage": "running",
        "message": "Installer started silently. Krexion will restart in a moment.",
        "installer": str(installer),
    }


if __name__ == "__main__":
    # Manual test entry point: `krexion-coreapp.exe -m desktop.updater`
    logging.basicConfig(level=logging.INFO)
    result = apply_update(target_version=sys.argv[1] if len(sys.argv) > 1 else None)
    print(result)
