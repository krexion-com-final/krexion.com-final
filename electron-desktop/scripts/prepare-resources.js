/* eslint-disable no-console */
// ─────────────────────────────────────────────────────────────────────────────
// prepare-resources.js
// ─────────────────────────────────────────────────────────────────────────────
// Populates electron-desktop/resources/krexion/** with everything the
// packaged app needs to run 100% locally on the customer's PC:
//
//   resources/krexion/
//     python/         — Embedded Python 3.11 (Windows x64) with deps installed
//     mongodb/        — Portable MongoDB Community Server (Windows x64)
//     backend/        — A copy of /app/backend (the FastAPI server)
//     frontend/       — The production React build (CRA `build/` output)
//     icon.ico        — Krexion icon (copied from installer/krexion.ico)
//
// Designed to run on the windows-latest GitHub Actions runner. Idempotent —
// existing downloads are reused. Never modifies the source repo.
// ─────────────────────────────────────────────────────────────────────────────

const fs = require('fs');
const path = require('path');
const https = require('https');
const { spawnSync, execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const REPO = path.resolve(ROOT, '..');
const RES = path.join(ROOT, 'resources', 'krexion');
const CACHE = path.join(ROOT, '.cache');

fs.mkdirSync(RES, { recursive: true });
fs.mkdirSync(CACHE, { recursive: true });

const PYTHON_VERSION = '3.11.9';
const PYTHON_URL =
  `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`;
const PIP_BOOTSTRAP_URL = 'https://bootstrap.pypa.io/get-pip.py';

const MONGO_VERSION = '7.0.14';
const MONGO_URL =
  `https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-${MONGO_VERSION}.zip`;

// ── tiny helpers ─────────────────────────────────────────────────────────────
function log(msg) { console.log(`[prepare] ${msg}`); }
function run(cmd, args, opts = {}) {
  log(`$ ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, { stdio: 'inherit', shell: false, ...opts });
  if (r.status !== 0) throw new Error(`${cmd} failed with exit code ${r.status}`);
}

function download(url, dest) {
  if (fs.existsSync(dest) && fs.statSync(dest).size > 0) {
    log(`cached: ${path.basename(dest)}`);
    return Promise.resolve();
  }
  log(`download: ${url}`);
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest + '.part');
    const get = (u) => {
      https.get(u, { headers: { 'user-agent': 'krexion-desktop-build' } }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          res.resume();
          return get(res.headers.location);
        }
        if (res.statusCode !== 200) {
          return reject(new Error(`HTTP ${res.statusCode} for ${u}`));
        }
        res.pipe(file);
        file.on('finish', () => file.close(() => {
          fs.renameSync(dest + '.part', dest);
          resolve();
        }));
      }).on('error', reject);
    };
    get(url);
  });
}

function unzip(zipPath, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  if (process.platform === 'win32') {
    run('powershell', [
      '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
      `Expand-Archive -Force -LiteralPath '${zipPath}' -DestinationPath '${destDir}'`
    ]);
  } else {
    run('unzip', ['-o', '-q', zipPath, '-d', destDir]);
  }
}

function rimraf(p) {
  if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
}

function copyDir(src, dest, filter = () => true) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (!filter(s, entry)) continue;
    if (entry.isDirectory()) copyDir(s, d, filter);
    else if (entry.isFile()) fs.copyFileSync(s, d);
  }
}

// ── 1. Embedded Python ───────────────────────────────────────────────────────
async function preparePython() {
  const pyDir = path.join(RES, 'python');
  if (fs.existsSync(path.join(pyDir, 'python.exe'))) {
    log('python: already prepared');
    return;
  }
  rimraf(pyDir);
  const zip = path.join(CACHE, `python-${PYTHON_VERSION}-embed.zip`);
  await download(PYTHON_URL, zip);
  unzip(zip, pyDir);

  // Enable site-packages in the embedded distribution.
  const pth = fs.readdirSync(pyDir).find((f) => /^python\d+\._pth$/i.test(f));
  if (pth) {
    const full = path.join(pyDir, pth);
    let text = fs.readFileSync(full, 'utf8');
    if (text.includes('#import site')) text = text.replace('#import site', 'import site');
    if (!/\bLib\\site-packages\b/.test(text)) text += '\nLib\\site-packages\n';
    fs.writeFileSync(full, text);
  }

  // Install pip into the embedded python.
  const getPip = path.join(CACHE, 'get-pip.py');
  await download(PIP_BOOTSTRAP_URL, getPip);
  if (process.platform === 'win32') {
    run(path.join(pyDir, 'python.exe'), [getPip, '--no-warn-script-location']);
    // Install backend requirements.
    //   The backend pins `emergentintegrations==0.1.0`, which lives on
    //   Emergent's private index (not on PyPI). We add that index as an
    //   `--extra-index-url` so pip can resolve it while still pulling the
    //   rest from PyPI.
    const req = path.join(REPO, 'backend', 'requirements.txt');
    run(path.join(pyDir, 'python.exe'), [
      '-m', 'pip', 'install',
      '--no-warn-script-location',
      '--extra-index-url', 'https://d33sy5i8bnduwe.cloudfront.net/simple/',
      '-r', req,
    ]);
  } else {
    log('python: non-Windows host — skipping pip install (resources will be incomplete).');
  }
}

// ── 2. Portable MongoDB ──────────────────────────────────────────────────────
async function prepareMongo() {
  const mongoDir = path.join(RES, 'mongodb');
  if (fs.existsSync(path.join(mongoDir, 'bin', 'mongod.exe'))) {
    log('mongodb: already prepared');
    return;
  }
  rimraf(mongoDir);
  const zip = path.join(CACHE, `mongodb-${MONGO_VERSION}.zip`);
  await download(MONGO_URL, zip);
  const tmp = path.join(CACHE, `mongo-extract-${MONGO_VERSION}`);
  rimraf(tmp);
  unzip(zip, tmp);
  // The archive extracts to a single mongodb-windows-* folder. Flatten it.
  const inner = fs.readdirSync(tmp).find((n) => n.toLowerCase().startsWith('mongodb-'));
  if (!inner) throw new Error('mongo: unexpected archive layout');
  fs.renameSync(path.join(tmp, inner), mongoDir);
  rimraf(tmp);

  // Keep only what we actually need (mongod + minimal deps) to shrink the
  // installer. We keep `bin/` fully — `mongod.exe` plus its sibling DLLs.
  // No further trimming for safety.
}

// ── 3. Backend snapshot ──────────────────────────────────────────────────────
function prepareBackend() {
  const dest = path.join(RES, 'backend');
  rimraf(dest);
  const src = path.join(REPO, 'backend');
  copyDir(src, dest, (full, entry) => {
    const rel = path.relative(src, full);
    if (entry.isDirectory()) {
      if (['__pycache__', 'tests', 'form_filler_results',
           'real_user_traffic_results', 'visual_recorder_sessions',
           'uploaded_resources'].includes(entry.name)) return false;
    }
    if (entry.isFile()) {
      if (entry.name.endsWith('.pyc')) return false;
      if (entry.name === '.env') return false; // never bundle dev .env
    }
    return true;
  });
  // Write a minimal .env so the backend has sane defaults even before the
  // installer drops a real one in %PROGRAMDATA%\Krexion-Desktop.
  const envFile = path.join(dest, '.env');
  fs.writeFileSync(envFile,
    'MONGO_URL=mongodb://127.0.0.1:27117\n' +
    'DB_NAME=krexion_local\n' +
    'KREXION_MODE=local\n' +
    'KREXION_DESKTOP=1\n'
  );
  log('backend: copied');
}

// ── 4. Frontend build ────────────────────────────────────────────────────────
function prepareFrontend() {
  const dest = path.join(RES, 'frontend');
  rimraf(dest);
  const frontDir = path.join(REPO, 'frontend');

  // Build with REACT_APP_BACKEND_URL pinned to the local backend so the
  // packaged app never talks to the cloud for app data.
  const env = {
    ...process.env,
    REACT_APP_BACKEND_URL: 'http://127.0.0.1:8088',
    CI: 'false',
    GENERATE_SOURCEMAP: 'false',
    INLINE_RUNTIME_CHUNK: 'false',
    PUBLIC_URL: '.', // produce relative asset URLs so file:// loading works
  };
  log('frontend: yarn install');
  run('yarn', ['install', '--network-timeout', '600000'], { cwd: frontDir, env, shell: true });
  log('frontend: yarn build');
  run('yarn', ['build'], { cwd: frontDir, env, shell: true });

  const built = path.join(frontDir, 'build');
  if (!fs.existsSync(built)) throw new Error('frontend: build/ not produced');
  copyDir(built, dest);
  log('frontend: copied build/ → resources/krexion/frontend');
}

// ── 5. Icon ──────────────────────────────────────────────────────────────────
function prepareIcon() {
  const src = path.join(REPO, 'installer', 'krexion.ico');
  const dest = path.join(RES, 'icon.ico');
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, dest);
    fs.copyFileSync(src, path.join(ROOT, 'build', 'icon.ico'));
    log('icon: copied');
  } else {
    log('icon: krexion.ico not found, electron-builder will use default');
  }
}

// ── main ─────────────────────────────────────────────────────────────────────
(async () => {
  fs.mkdirSync(path.join(ROOT, 'build'), { recursive: true });
  await preparePython();
  await prepareMongo();
  prepareBackend();
  prepareFrontend();
  prepareIcon();
  log('✅ resources ready at ' + RES);
})().catch((err) => {
  console.error('[prepare] FAILED:', err);
  process.exit(1);
});
