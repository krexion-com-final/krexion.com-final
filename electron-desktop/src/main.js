// ─────────────────────────────────────────────────────────────────────────────
// Krexion Desktop — Electron main process
// ─────────────────────────────────────────────────────────────────────────────
// Boots a fully-local Krexion stack on the customer's PC:
//
//   1. Starts a bundled portable MongoDB on 127.0.0.1:27117 with dbpath in
//      %APPDATA%\Krexion-Desktop\db
//   2. Starts the embedded-Python FastAPI backend on 127.0.0.1:8088 with
//      MONGO_URL pointing at the local MongoDB.
//   3. Loads the production React frontend (baked with REACT_APP_BACKEND_URL=
//      http://127.0.0.1:8088) inside a Chromium BrowserWindow.
//
// Heavy workload data stays 100% on the customer's machine. Only license
// validation and release checks reach krexion.com (handled inside the
// backend's existing license_module / releases_module).
//
// This file is intentionally additive — it does NOT modify the existing
// Inno-Setup installer or web app. Both ship side-by-side.
// ─────────────────────────────────────────────────────────────────────────────

const { app, BrowserWindow, Menu, Tray, dialog, shell, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');
const log = require('electron-log/main');

log.initialize();
log.transports.file.level = 'info';
log.transports.console.level = 'info';

// ── Paths ────────────────────────────────────────────────────────────────────
// In packaged builds, electron-builder unpacks `resources/krexion/**` to:
//   <app-root>/resources/krexion/...
// In dev, we look in ../resources/krexion (populated by prepare-resources.js).
const resourcesRoot = app.isPackaged
  ? path.join(process.resourcesPath, 'krexion')
  : path.join(__dirname, '..', 'resources', 'krexion');

const pythonExe = path.join(resourcesRoot, 'python', 'python.exe');
const backendDir = path.join(resourcesRoot, 'backend');
const backendEntry = path.join(backendDir, 'server.py');
const mongoExe = path.join(resourcesRoot, 'mongodb', 'bin', 'mongod.exe');
const frontendDir = path.join(resourcesRoot, 'frontend');
const iconPath = path.join(resourcesRoot, 'icon.ico');

const userDataDir = app.getPath('userData');
const dbDir = path.join(userDataDir, 'db');
const logsDir = path.join(userDataDir, 'logs');
fs.mkdirSync(dbDir, { recursive: true });
fs.mkdirSync(logsDir, { recursive: true });

const MONGO_PORT = 27117;
const BACKEND_PORT = 8088;
const MONGO_URL = `mongodb://127.0.0.1:${MONGO_PORT}`;
const DB_NAME = 'krexion_local';
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

let mongoProc = null;
let backendProc = null;
let mainWindow = null;
let splashWindow = null;
let tray = null;
let isQuitting = false;

// ── Single-instance lock so customers cannot launch 2 Krexion Desktops ──────
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  return;
}
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

// ── Helpers ──────────────────────────────────────────────────────────────────
function logFileStream(name) {
  return fs.createWriteStream(path.join(logsDir, name), { flags: 'a' });
}

function waitForHttp(url, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const tick = () => {
      const req = http.get(url, { timeout: 2000 }, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode < 500) return resolve();
        if (Date.now() - start > timeoutMs) return reject(new Error(`Timeout waiting for ${url}`));
        setTimeout(tick, 1000);
      });
      req.on('error', () => {
        if (Date.now() - start > timeoutMs) return reject(new Error(`Timeout waiting for ${url}`));
        setTimeout(tick, 1000);
      });
      req.on('timeout', () => {
        req.destroy();
        if (Date.now() - start > timeoutMs) return reject(new Error(`Timeout waiting for ${url}`));
        setTimeout(tick, 1000);
      });
    };
    tick();
  });
}

function waitForTcp(host, port, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const net = require('net');
    const start = Date.now();
    const tick = () => {
      const socket = new net.Socket();
      socket.setTimeout(2000);
      socket.once('connect', () => { socket.destroy(); resolve(); });
      socket.once('timeout', () => { socket.destroy(); retry(); });
      socket.once('error', () => { socket.destroy(); retry(); });
      socket.connect(port, host);
      function retry() {
        if (Date.now() - start > timeoutMs) return reject(new Error(`Timeout waiting for ${host}:${port}`));
        setTimeout(tick, 1000);
      }
    };
    tick();
  });
}

// ── MongoDB ──────────────────────────────────────────────────────────────────
function startMongo() {
  log.info(`[mongo] starting on 127.0.0.1:${MONGO_PORT}, dbpath=${dbDir}`);
  mongoProc = spawn(
    mongoExe,
    [
      '--dbpath', dbDir,
      '--port', String(MONGO_PORT),
      '--bind_ip', '127.0.0.1',
      '--noauth',
      '--quiet'
    ],
    {
      cwd: path.dirname(mongoExe),
      windowsHide: true,
    }
  );
  const out = logFileStream('mongo.log');
  mongoProc.stdout.pipe(out);
  mongoProc.stderr.pipe(out);
  mongoProc.on('exit', (code) => {
    log.warn(`[mongo] exited code=${code}`);
    if (!isQuitting) {
      dialog.showErrorBox('Krexion Desktop', 'Local database stopped unexpectedly. Please restart Krexion Desktop.');
      app.quit();
    }
  });
  return waitForTcp('127.0.0.1', MONGO_PORT, 45000);
}

// ── Python backend ───────────────────────────────────────────────────────────
function startBackend() {
  log.info(`[backend] starting on 127.0.0.1:${BACKEND_PORT}`);
  const env = {
    ...process.env,
    MONGO_URL,
    DB_NAME,
    KREXION_MODE: 'local',
    KREXION_DESKTOP: '1',
    PORT: String(BACKEND_PORT),
    HOST: '127.0.0.1',
    // Help embedded Python find site-packages under <python>\Lib\site-packages
    PYTHONHOME: path.join(resourcesRoot, 'python'),
    PYTHONPATH: [
      backendDir,
      path.join(resourcesRoot, 'python', 'Lib', 'site-packages'),
    ].join(path.delimiter),
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
    PYTHONDONTWRITEBYTECODE: '1',
  };

  // Prefer uvicorn directly; server.py exposes `app` as a FastAPI instance.
  backendProc = spawn(
    pythonExe,
    [
      '-m', 'uvicorn',
      'server:app',
      '--host', '127.0.0.1',
      '--port', String(BACKEND_PORT),
      '--no-access-log',
    ],
    {
      cwd: backendDir,
      env,
      windowsHide: true,
    }
  );
  const out = logFileStream('backend.log');
  backendProc.stdout.pipe(out);
  backendProc.stderr.pipe(out);
  backendProc.on('exit', (code) => {
    log.warn(`[backend] exited code=${code}`);
    if (!isQuitting) {
      dialog.showErrorBox('Krexion Desktop', 'Local backend stopped unexpectedly. Please restart Krexion Desktop.');
      app.quit();
    }
  });
  return waitForHttp(`${BACKEND_URL}/api/`, 90000).catch(() =>
    waitForHttp(`${BACKEND_URL}/docs`, 30000)
  );
}

// ── Windows ──────────────────────────────────────────────────────────────────
function createSplash() {
  splashWindow = new BrowserWindow({
    width: 520,
    height: 320,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    transparent: false,
    show: true,
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  splashWindow.loadFile(path.join(__dirname, 'splash.html'));
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    backgroundColor: '#0b0b0d',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    title: 'Krexion Desktop',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // Load the local backend URL so the React app (built with
  // REACT_APP_BACKEND_URL=http://127.0.0.1:8088) talks to localhost only.
  // The bundled frontend is served by the backend itself via a static mount,
  // OR we load the file://-based index.html and let the SPA call the backend.
  const indexHtml = path.join(frontendDir, 'index.html');
  if (fs.existsSync(indexHtml)) {
    mainWindow.loadFile(indexHtml);
  } else {
    // Fallback: load backend root (assumes backend serves /).
    mainWindow.loadURL(`${BACKEND_URL}/`);
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (splashWindow) {
      splashWindow.destroy();
      splashWindow = null;
    }
  });

  // External links → default browser, not inside the Electron shell.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://127.0.0.1') || url.startsWith(BACKEND_URL)) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

function createTray() {
  const image = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath)
    : nativeImage.createEmpty();
  tray = new Tray(image);
  tray.setToolTip('Krexion Desktop');
  const menu = Menu.buildFromTemplate([
    { label: 'Open Krexion', click: () => mainWindow && mainWindow.show() },
    { label: 'Open Logs Folder', click: () => shell.openPath(logsDir) },
    { type: 'separator' },
    { label: 'Quit Krexion', click: () => { isQuitting = true; app.quit(); } },
  ]);
  tray.setContextMenu(menu);
  tray.on('click', () => mainWindow && mainWindow.show());
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
async function boot() {
  try {
    createSplash();
    await startMongo();
    log.info('[boot] mongo ready');
    await startBackend();
    log.info('[boot] backend ready');
    createMainWindow();
    createTray();
  } catch (err) {
    log.error('[boot] failed', err);
    dialog.showErrorBox(
      'Krexion Desktop — startup failed',
      `${err.message || err}\n\nLogs: ${logsDir}`
    );
    isQuitting = true;
    app.quit();
  }
}

app.on('ready', boot);

app.on('window-all-closed', (e) => {
  // Keep running in tray on Windows.
  if (process.platform !== 'darwin') e.preventDefault?.();
});

app.on('before-quit', () => {
  isQuitting = true;
  for (const p of [backendProc, mongoProc]) {
    if (p && !p.killed) {
      try { p.kill(); } catch (_) {}
    }
  }
});

process.on('uncaughtException', (err) => log.error('uncaughtException', err));
process.on('unhandledRejection', (err) => log.error('unhandledRejection', err));
