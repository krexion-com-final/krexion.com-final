// Minimal preload — exposes a small, safe API for the renderer.
// No nodeIntegration, no remote, no fs. The React app already speaks to
// http://127.0.0.1:8088 directly via REACT_APP_BACKEND_URL.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('krexion', {
  isDesktop: true,
  platform: process.platform,
  version: process.env.npm_package_version || null,
  // 2026-06-11: One-click in-app update. When the React UpdateBanner
  // (shared with the web app) detects we're running inside Electron,
  // it calls this instead of POSTing /api/system/install-update — which
  // is the wrong path for the Electron build because there's no
  // host-updater service watching for a flag file on the desktop. The
  // main process forwards to electron-updater.checkForUpdates() and,
  // once the new build is downloaded, runs quitAndInstall() so the
  // customer never has to download / uninstall / reinstall manually.
  installUpdate: () => ipcRenderer.invoke('krexion:install-update'),
  checkForUpdates: () => ipcRenderer.invoke('krexion:check-for-updates'),
});
