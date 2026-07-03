/* Krexion Desktop Dashboard — front-end logic
 * ────────────────────────────────────────────
 * Lightweight, dependency-free JS. Polls two backends:
 *   * Local backend (http://127.0.0.1:8001) every 2s for live stats
 *   * Cloud (https://krexion.com) every 15 min for auto-update banner
 *
 * If the local backend is unreachable, the UI shows a soft "starting up"
 * state instead of erroring — services may still be booting on first
 * install (NSSM gives them ~10s).
 */

const LOCAL = "http://127.0.0.1:8001";
const CLOUD = "https://krexion.com";

const POLL_LOCAL_MS = 2000;
const POLL_CLOUD_MS = 15 * 60 * 1000;

// v2.1.79 — Diagnostic thresholds when the local backend never
// answers. Prevents the dashboard from silently sitting on
// "checking…" forever (customer report: "2 hours ho gy ye checking
// pr he hai kuch b chal ni raha"). After the escalation thresholds
// below we surface actionable info + a Diagnose panel with retry +
// logs-folder hints.
const BACKEND_WARN_MS = 8000;     // 8 s → "not responding yet"
const BACKEND_ESCALATE_MS = 20000; // 20 s → open Diagnose panel
const BACKEND_FATAL_MS = 60000;   // 60 s → red status + urgent copy

const $ = (id) => document.getElementById(id);

// Track how long the backend has been unreachable + last error so
// we can surface it in the Diagnose panel.
const _diag = {
  firstFailAt: 0,          // unix ms of first consecutive failure
  lastFailAt: 0,           // unix ms of most recent failure
  consecutiveFailures: 0,  // # of polls in a row that failed
  lastError: "",           // one-line error summary
  everSucceeded: false,    // has ANY poll ever succeeded this run?
  lastSuccessAt: 0,        // unix ms of most recent success (for uptime label)
};

function fmtBytes(gb) {
  if (gb >= 100) return Math.round(gb) + " GB";
  if (gb >= 10) return gb.toFixed(0) + " GB";
  return gb.toFixed(1) + " GB";
}
function setText(id, value) { const e = $(id); if (e) e.textContent = value; }
function setBar(id, pct) {
  const e = $(id); if (!e) return;
  e.style.width = Math.max(0, Math.min(100, pct)).toFixed(1) + "%";
}
function setDot(id, state) {
  const e = $(id); if (!e) return;
  e.className = "dot dot-" + state;
}
function setPill(id, label, variant) {
  const e = $(id); if (!e) return;
  e.textContent = label;
  e.className = "pill" + (variant ? " pill-" + variant : "");
}

/* ── Poll local backend ─────────────────────────────────────────── */
async function pollLocal() {
  try {
    // Explicit 4 s per-poll timeout using AbortController so we can
    // distinguish "connection refused" (backend service dead) from
    // "backend hung on this request" — both show up in _diag.lastError
    // instead of the browser's opaque generic TypeError.
    const ac = new AbortController();
    const to = setTimeout(() => ac.abort(), 4000);
    let r;
    try {
      r = await fetch(`${LOCAL}/api/desktop/stats`, { cache: "no-store", signal: ac.signal });
    } finally {
      clearTimeout(to);
    }
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();

    // v2.1.79 — reset diagnostic state on ANY success; dismiss panel.
    _diag.firstFailAt = 0;
    _diag.lastFailAt = 0;
    _diag.consecutiveFailures = 0;
    _diag.lastError = "";
    _diag.everSucceeded = true;
    _diag.lastSuccessAt = Date.now();
    hideDiagnosePanel();

    setPill("connection-pill", "Backend Online", "ok");

    // ── Services ─────────────────────────
    setDot("backend-dot", "ok");
    setText("backend-detail", d.backend_version ? `running · ${d.backend_version}` : "running");
    setDot("db-dot", d.database?.connected ? "ok" : "danger");
    setText("db-detail", d.database?.connected
      ? `connected · ${d.database.collections || 0} collections`
      : "not reachable");
    setDot("cloud-dot", d.cloud?.connected ? "ok" : "warn");
    setText("cloud-detail", d.cloud?.connected
      ? `linked · ${d.cloud.last_sync_age || 0}s ago`
      : "no recent heartbeat");
    setText("services-last-checked", "updated " + new Date().toLocaleTimeString());

    // ── License ─────────────────────────
    const lic = d.license || {};
    setText("license-status", lic.active ? "Active ✓" : "Inactive");
    setText("license-email", lic.email || "—");
    $("license-status").style.color = lic.active ? "var(--ok)" : "var(--warn)";

    // ── CPU/RAM ─────────────────────────
    const s = d.system || {};
    setText("cpu-cores", `${s.cpu_cores || "—"} cores`);
    setBar("cpu-bar", s.cpu_pct || 0);
    setText("cpu-pct", (s.cpu_pct || 0).toFixed(0) + "%");

    setText("ram-total", `${fmtBytes(s.ram_gb || 0)} total`);
    setBar("ram-bar", s.ram_used_pct || 0);
    setText("ram-used", fmtBytes(s.ram_used_gb || 0));
    setText("ram-pct", (s.ram_used_pct || 0).toFixed(0) + "%");

    setText("capacity-tier", (s.tier || "—").toUpperCase());
    setText("capacity-max", s.max_concurrent_heavy_jobs || "—");
    setText("tier-detector", `Detected by ${s.detected_by || "live"} · ${s.cpu_cores || "—"}c / ${fmtBytes(s.ram_gb || 0)}`);

    // ── Active jobs ─────────────────────
    renderJobs($("jobs-list"), d.jobs?.active || [], "No active jobs. Submit one from krexion.com — it will run here.");
    const t = d.jobs?.throughput || {};
    setText("jobs-throughput",
      `${t.jobs_per_hour || 0} jobs/hour · ${(t.success_rate_pct || 0).toFixed(0)}% success`);

    // ── Recent ──────────────────────────
    renderJobs($("recent-list"), d.jobs?.recent || [], "No recent activity yet.");

    // ── Dependencies (v2.1.59) ──────────
    renderDeps(d.dependencies || {});

    setText("version-pill", "v" + (d.backend_version || "—"));
  } catch (e) {
    // v2.1.79 — Track failure duration + surface diagnostic UI.
    const now = Date.now();
    if (_diag.firstFailAt === 0) _diag.firstFailAt = now;
    _diag.lastFailAt = now;
    _diag.consecutiveFailures += 1;
    _diag.lastError = summariseError(e);
    const downMs = now - _diag.firstFailAt;

    // Progressive status copy so the customer sees the app IS aware
    // of the problem instead of a mysterious perpetual "checking…".
    if (downMs >= BACKEND_FATAL_MS) {
      setPill("connection-pill", "Backend offline", "danger");
      setDot("backend-dot", "danger");
      setText("backend-detail",
        `not responding for ${humanElapsed(downMs)} — service may have crashed`);
    } else if (downMs >= BACKEND_WARN_MS) {
      setPill("connection-pill", "Backend not responding", "warn");
      setDot("backend-dot", "warn");
      setText("backend-detail",
        `no reply for ${humanElapsed(downMs)} · ${_diag.lastError}`);
    } else {
      setPill("connection-pill", "Backend starting…", "warn");
      setDot("backend-dot", "warn");
      setText("backend-detail", "service is starting up (~10s on first boot)");
    }

    // Downstream cards can't be fresh either — mark them unknown so
    // the UI stops lying with a stale "checking…" for hours.
    setDot("db-dot", "unknown");
    setText("db-detail", _diag.everSucceeded ? "last check failed" : "waiting for backend");
    setDot("cloud-dot", "unknown");
    setText("cloud-detail", _diag.everSucceeded ? "last check failed" : "waiting for backend");

    // Escalate to Diagnose panel once we're clearly past normal boot.
    if (downMs >= BACKEND_ESCALATE_MS) {
      showDiagnosePanel(downMs);
    }
  }
}

function renderJobs(container, jobs, emptyMsg) {
  if (!container) return;
  if (!jobs || jobs.length === 0) {
    container.innerHTML = `<div class="jobs-empty">${emptyMsg}</div>`;
    return;
  }
  container.innerHTML = jobs.map((j) => `
    <div class="job-item">
      <div>
        <div>${escapeHtml(j.kind || "job")} · <span class="job-status-${escapeHtml(j.status || "running")}">${escapeHtml(j.status || "running")}</span></div>
        <div class="job-item-meta">${escapeHtml(j.detail || "")}</div>
      </div>
      <div class="job-item-meta">${escapeHtml(j.started_ago || "")}</div>
    </div>
  `).join("");
}

/* ── Dependencies grid (v2.1.59) ──────────────────────────────────
 * Surfaces the install state of every external binary a Krexion
 * feature needs (Playwright Chromium for RUT/VR/Browser-Profiles,
 * adb for CPI, the Playwright package itself, …) so the customer
 * sees at a glance which features are usable RIGHT NOW vs still
 * installing. Previously this only got surfaced once they CLICKED
 * Launch and the launch failed, leading to "kuch kaam ni krta" reports.
 */
const DEP_LABELS = {
  playwright: "Playwright (engine)",
  chromium:   "Chromium browser",
  adb:        "ADB (Android CPI)",
};
function renderDeps(deps) {
  const container = document.getElementById("deps-list");
  const summary = document.getElementById("deps-summary");
  if (!container) return;
  const keys = Object.keys(deps || {});
  if (keys.length === 0) {
    container.innerHTML = `<div class="jobs-empty">No dependency info available.</div>`;
    if (summary) summary.textContent = "—";
    return;
  }
  // Summary count
  let okCount = 0;
  let warnCount = 0;
  let failCount = 0;
  keys.forEach((k) => {
    const s = (deps[k]?.status || "error").toLowerCase();
    if (s === "ok") okCount++;
    else if (s === "installing") warnCount++;
    else failCount++;
  });
  if (summary) {
    summary.textContent = `${okCount}/${keys.length} ready` +
      (warnCount ? ` · ${warnCount} installing` : "") +
      (failCount ? ` · ${failCount} missing` : "");
  }
  container.innerHTML = keys.map((k) => {
    const d = deps[k] || {};
    const s = (d.status || "error").toLowerCase();
    const label = DEP_LABELS[k] || k;
    const dotClass = (s === "ok") ? "dot-ok"
                   : (s === "installing") ? "dot-warn"
                   : (s === "missing") ? "dot-danger"
                   : "dot-unknown";
    const stateText = (s === "ok") ? "ready"
                    : (s === "installing") ? "installing…"
                    : (s === "missing") ? "missing"
                    : "error";
    const msg = escapeHtml(d.message || "");
    return `
      <div class="dep-item">
        <span class="dot ${dotClass}"></span>
        <div class="dep-body">
          <div class="dep-label">${escapeHtml(label)} · <span class="job-status-${(s === 'ok') ? 'completed' : (s === 'missing' || s === 'error') ? 'failed' : 'running'}">${stateText}</span></div>
          ${msg ? `<div class="job-item-meta">${msg}</div>` : ""}
        </div>
      </div>
    `;
  }).join("");
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* ── Diagnose panel (v2.1.79) ────────────────────────────────────
 * Surfaces WHY the local backend isn't responding once we've been
 * failing for >20 s. Prevents the "2 hours stuck on checking…"
 * silent-failure mode. Shows retry count, downtime, last error,
 * and actionable steps (open logs folder path, restart guidance).
 */
function summariseError(e) {
  if (!e) return "unknown error";
  const name = e.name || "";
  const msg = e.message || String(e);
  if (name === "AbortError") return "request timed out (>4s)";
  if (/Failed to fetch|NetworkError|network/i.test(msg)) return "cannot reach 127.0.0.1:8001 (service not running?)";
  if (/^HTTP 5\d\d/.test(msg)) return "backend returned " + msg + " (internal error)";
  if (/^HTTP 4\d\d/.test(msg)) return "backend returned " + msg;
  return msg.length > 80 ? msg.slice(0, 80) + "…" : msg;
}

function humanElapsed(ms) {
  if (ms < 1000) return "<1s";
  const s = Math.floor(ms / 1000);
  if (s < 60) return s + "s";
  const m = Math.floor(s / 60);
  const remS = s % 60;
  if (m < 60) return `${m}m ${remS}s`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h}h ${remM}m`;
}

function showDiagnosePanel(downMs) {
  const panel = $("diagnose-panel");
  if (!panel) return;
  panel.classList.remove("hidden");
  // Severity-based header colour: warn under 60s, danger past that.
  panel.classList.toggle("diagnose-danger", downMs >= BACKEND_FATAL_MS);
  setText("diag-downtime", humanElapsed(downMs));
  setText("diag-retries", String(_diag.consecutiveFailures));
  setText("diag-error", _diag.lastError || "—");
  // Show a friendly line about whether backend ever answered this session.
  setText("diag-history",
    _diag.everSucceeded
      ? "Backend was responding earlier and then stopped — the KrexionBackend Windows service may have crashed."
      : "Backend has never responded since Krexion started — the KrexionBackend Windows service may not have started at all."
  );
}
function hideDiagnosePanel() {
  const panel = $("diagnose-panel");
  if (!panel) return;
  panel.classList.add("hidden");
  panel.classList.remove("diagnose-danger");
}

/* Kick the poll loop immediately when the customer clicks Retry —
 * don't make them wait up to POLL_LOCAL_MS for the next scheduled
 * cycle. Also flashes the button so they see something happened
 * even when the poll fails again. */
async function diagnoseRetryNow() {
  const btn = $("diag-retry-btn");
  if (btn) {
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "Checking…";
    try { await pollLocal(); } catch (_) {}
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = original;
    }, 800);
  } else {
    await pollLocal();
  }
}

/* ── Auto-update banner ─────────────────────────────────────────── */
async function pollUpdate() {
  try {
    const r = await fetch(`${CLOUD}/api/system/public-latest`, { cache: "no-store" });
    if (!r.ok) return;
    const d = await r.json();
    if (d.update_available && d.latest) {
      const v = d.latest.version || "newer";
      const dismissed = sessionStorage.getItem("krexion_update_dismissed_" + v) === "1";
      if (dismissed) return;
      $("update-banner").classList.remove("hidden");
      setText("update-version", `Krexion ${v} is available  (you have ${d.current || "—"})`);
      setText("update-notes", d.latest.title || "Click Update to install — Krexion will restart automatically.");
      $("update-banner").dataset.targetVersion = v;
    } else {
      $("update-banner").classList.add("hidden");
    }
  } catch (e) {
    // silent — banner just stays hidden if cloud is unreachable
  }
}

async function applyUpdate() {
  const btn = $("update-now-btn");
  const banner = $("update-banner");
  const target = banner?.dataset?.targetVersion || "";
  btn.disabled = true;
  btn.textContent = "Downloading…";
  try {
    const r = await fetch(`${LOCAL}/api/desktop/run-update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_version: target }),
    });
    const d = await r.json();
    if (d.ok) {
      btn.textContent = "Installing — Krexion will restart…";
      // Banner will disappear once the new version reports back
    } else {
      btn.disabled = false;
      btn.textContent = "Update Now";
      alert("Update failed: " + (d.message || "unknown error"));
    }
  } catch (e) {
    btn.disabled = false;
    btn.textContent = "Update Now";
    alert("Could not reach the local Krexion service.");
  }
}

/* ── Wire it up ─────────────────────────────────────────────────── */
function init() {
  $("open-cloud-btn").addEventListener("click", () => {
    // v1.0.14: always open krexion.com (per product design - the cloud
    // UI is authoritative for ALL feature submissions; heavy jobs are
    // automatically routed to this PC via the bridge worker so they
    // execute locally without the user ever leaving krexion.com).
    try { window.open(CLOUD + "/login", "_blank"); }
    catch (e) { window.location.href = CLOUD + "/login"; }
  });
  $("update-now-btn").addEventListener("click", applyUpdate);
  $("update-dismiss-btn").addEventListener("click", () => {
    const v = $("update-banner")?.dataset?.targetVersion;
    if (v) sessionStorage.setItem("krexion_update_dismissed_" + v, "1");
    $("update-banner").classList.add("hidden");
  });

  // v2.1.79 — Diagnose panel wiring (retry + copy-logs-path helpers).
  const retryBtn = $("diag-retry-btn");
  if (retryBtn) retryBtn.addEventListener("click", diagnoseRetryNow);
  const copyBtn = $("diag-copy-path-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const path = "C:\\Program Files\\Krexion\\logs\\backend.stderr.log";
      try {
        await navigator.clipboard.writeText(path);
        copyBtn.textContent = "Copied ✓";
        setTimeout(() => { copyBtn.textContent = "Copy Logs Path"; }, 1500);
      } catch {
        copyBtn.textContent = "Copy failed";
        setTimeout(() => { copyBtn.textContent = "Copy Logs Path"; }, 1500);
      }
    });
  }

  pollLocal();
  pollUpdate();
  setInterval(pollLocal, POLL_LOCAL_MS);
  setInterval(pollUpdate, POLL_CLOUD_MS);
}

document.addEventListener("DOMContentLoaded", init);
