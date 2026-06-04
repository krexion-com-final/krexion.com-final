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

const $ = (id) => document.getElementById(id);

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
    const r = await fetch(`${LOCAL}/api/desktop/stats`, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();

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

    setText("version-pill", "v" + (d.backend_version || "—"));
  } catch (e) {
    setPill("connection-pill", "Backend starting…", "warn");
    setDot("backend-dot", "warn");
    setText("backend-detail", "service is starting up (~10s on first boot)");
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

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
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

  pollLocal();
  pollUpdate();
  setInterval(pollLocal, POLL_LOCAL_MS);
  setInterval(pollUpdate, POLL_CLOUD_MS);
}

document.addEventListener("DOMContentLoaded", init);
