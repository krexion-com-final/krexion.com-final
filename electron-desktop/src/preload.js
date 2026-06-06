// Minimal preload — exposes a small, safe API for the renderer.
// No nodeIntegration, no remote, no fs. The React app already speaks to
// http://127.0.0.1:8088 directly via REACT_APP_BACKEND_URL.
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('krexion', {
  isDesktop: true,
  platform: process.platform,
  version: process.env.npm_package_version || null,
});
