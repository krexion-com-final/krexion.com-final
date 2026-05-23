import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, RefreshCw, Trash2, AlertTriangle, CheckCircle2, HardDrive, Cpu, Activity, Clock } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function authHeaders() {
  const token =
    localStorage.getItem("adminToken") ||
    localStorage.getItem("admin_token") ||
    localStorage.getItem("token");
  return { Authorization: `Bearer ${token}` };
}

function StatBox({ icon: Icon, label, value, sub, tone = "default", testId }) {
  const toneClass = {
    default: "border-[var(--brand-border)]",
    warn: "border-yellow-500/40 bg-yellow-500/5",
    danger: "border-red-500/40 bg-red-500/5",
    good: "border-emerald-500/40 bg-emerald-500/5",
  }[tone];
  return (
    <div className={`rounded-xl border ${toneClass} p-4`} data-testid={testId}>
      <div className="flex items-center gap-2 text-[#A1A1AA] text-xs uppercase tracking-wide">
        <Icon size={14} />
        <span>{label}</span>
      </div>
      <div className="text-2xl font-bold text-white mt-1">{value}</div>
      {sub && <div className="text-xs text-[#A1A1AA] mt-1">{sub}</div>}
    </div>
  );
}

export default function SystemMaintenancePage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [source, setSource] = useState("");
  const [deployment, setDeployment] = useState(null);
  const [status, setStatus] = useState({ pending: false, last_result: null, host_watcher_configured: false });
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([
        axios.get(`${API}/admin/system/host-stats`, { headers: authHeaders() }),
        axios.get(`${API}/admin/system/cleanup-status`, { headers: authHeaders() }),
      ]);
      setStats(s.data?.stats || null);
      setSource(s.data?.source || "");
      setDeployment(s.data?.deployment || null);
      setStatus(st.data || {});
    } catch (e) {
      const msg = e.response?.data?.detail || e.message;
      toast.error(`Could not load stats: ${msg}`);
      if (e.response?.status === 401 || e.response?.status === 403) {
        navigate("/admin");
      }
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 30000); // refresh every 30s
    return () => clearInterval(t);
  }, [fetchAll]);

  const requestCleanup = async () => {
    setCleaning(true);
    try {
      const r = await axios.post(`${API}/admin/system/cleanup`, {}, { headers: authHeaders() });
      toast.success(r.data?.message || "Cleanup queued");
      setShowConfirm(false);
      // Poll faster for ~3 minutes so the user sees the result land
      const start = Date.now();
      const fastPoll = setInterval(async () => {
        await fetchAll();
        if (Date.now() - start > 180000) clearInterval(fastPoll);
      }, 5000);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to request cleanup");
    } finally {
      setCleaning(false);
    }
  };

  const diskPct = stats?.disk_used_pct ?? 0;
  const memPct = stats?.memory_used_pct ?? 0;
  const swapPct = stats?.swap_used_pct ?? 0;
  const load = stats?.load_avg_1m ?? 0;

  const diskTone = diskPct >= 85 ? "danger" : diskPct >= 70 ? "warn" : "good";
  const memTone = memPct >= 90 ? "danger" : memPct >= 75 ? "warn" : "good";
  const loadTone = load >= 8 ? "danger" : load >= 4 ? "warn" : "good";

  return (
    <div className="min-h-screen bg-[var(--brand-bg)] text-white" data-testid="system-maintenance-page">
      <div className="max-w-5xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => navigate("/admin/dashboard")}
            className="flex items-center gap-2 text-[#A1A1AA] hover:text-white text-sm"
            data-testid="back-to-admin-btn"
          >
            <ArrowLeft size={16} /> Back to Admin
          </button>
          <button
            onClick={fetchAll}
            className="flex items-center gap-2 px-3 py-1.5 border border-[var(--brand-border)] rounded-lg text-sm hover:bg-white/5"
            data-testid="refresh-stats-btn"
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        <h1 className="text-2xl font-bold mb-1">VPS Maintenance</h1>
        <p className="text-sm text-[#A1A1AA] mb-6">
          Free disk space and clear server caches with one click. Click data, uploads, and RUT results are never touched.
        </p>

        {/* Heavy-Block Mode Banner */}
        {deployment?.is_cloud && (
          <div
            className={`mb-5 rounded-xl border p-4 ${
              deployment.strict_heavy_block
                ? "border-emerald-500/40 bg-emerald-500/5"
                : "border-yellow-500/40 bg-yellow-500/5"
            }`}
            data-testid="strict-mode-banner"
          >
            <div className="flex items-start gap-3">
              {deployment.strict_heavy_block ? (
                <CheckCircle2 size={20} className="text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle size={20} className="text-yellow-400 shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                <div className="font-semibold mb-1">
                  Heavy Ops on VPS:{" "}
                  {deployment.strict_heavy_block ? (
                    <span className="text-emerald-300">BLOCKED (recommended)</span>
                  ) : (
                    <span className="text-yellow-300">ALLOWED (legacy)</span>
                  )}
                </div>
                {deployment.strict_heavy_block ? (
                  <p className="text-xs text-[#A1A1AA]">
                    Real User Traffic, Form Filler, Visual Recorder and bulk proxy tests are forced to run on the customer's own PC via the bridge. The VPS will never spin up Playwright Chromium itself — keeping load low even with many customers.
                  </p>
                ) : (
                  <div className="text-xs text-[#A1A1AA] space-y-2">
                    <p>
                      Heavy features fall back to running on this VPS if the customer's PC is offline. This is why you may see 40+ Chromium browsers eating RAM. To force all heavy work onto customer PCs and protect the VPS, enable strict mode:
                    </p>
                    <div className="bg-black/40 border border-[var(--brand-border)] rounded-md p-2 font-mono text-[11px]">
                      <div># Add to /opt/krexion/backend/.env on the VPS:</div>
                      <div className="text-emerald-300">STRICT_CLOUD_HEAVY_BLOCK=true</div>
                      <div className="text-[#A1A1AA] mt-1"># Then: docker compose restart backend</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Stats Grid */}
        {loading ? (
          <div className="text-center py-12 text-[#A1A1AA]">Loading server stats…</div>
        ) : !stats ? (
          <div className="text-center py-12 text-red-400">Could not load stats.</div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              <StatBox
                icon={HardDrive}
                label="Disk Used"
                value={`${diskPct}%`}
                sub={stats.disk_free_gb != null ? `${stats.disk_free_gb} GB free` : ""}
                tone={diskTone}
                testId="stat-disk"
              />
              <StatBox
                icon={Cpu}
                label="Memory Used"
                value={`${memPct}%`}
                sub={swapPct > 0 ? `Swap ${swapPct}%` : "Swap 0%"}
                tone={memTone}
                testId="stat-memory"
              />
              <StatBox
                icon={Activity}
                label="Load (1m)"
                value={typeof load === "number" ? load.toFixed(2) : load}
                sub="Higher = busier"
                tone={loadTone}
                testId="stat-load"
              />
              <StatBox
                icon={Clock}
                label="Stats Updated"
                value={stats.updated_at ? new Date(stats.updated_at).toLocaleTimeString() : "—"}
                sub={source === "host-watcher" ? "live host data" : "container fallback"}
                tone="default"
                testId="stat-updated"
              />
            </div>

            {source !== "host-watcher" && (
              <div className="mb-4 p-3 rounded-lg border border-yellow-500/40 bg-yellow-500/5 text-yellow-200 text-xs flex items-start gap-2" data-testid="watcher-warning">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                <div>
                  Host watcher is not configured yet. The cleanup button will still work once the watcher script is installed on the VPS — see <code>scripts/vps-cleanup-watcher.sh</code> in the repo.
                </div>
              </div>
            )}
          </>
        )}

        {/* Cleanup Action */}
        <div className="rounded-xl border border-[var(--brand-border)] p-5 mb-6">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-[260px]">
              <h2 className="text-lg font-semibold">Clean VPS Cache</h2>
              <p className="text-sm text-[#A1A1AA] mt-1">
                Frees disk by clearing Docker build cache, old journal logs, APT cache, rotated Caddy access logs, and stale Playwright temp folders. Safe — never touches MongoDB data, uploads, or RUT results.
              </p>
              {status.pending && (
                <div className="mt-3 text-yellow-300 text-xs flex items-center gap-2" data-testid="cleanup-pending">
                  <RefreshCw size={12} className="animate-spin" />
                  Cleanup queued — host watcher will run within ~60 seconds.
                </div>
              )}
            </div>
            <button
              onClick={() => setShowConfirm(true)}
              disabled={cleaning || status.pending}
              className="bg-red-500 hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-2.5 rounded-lg font-medium flex items-center gap-2 transition"
              data-testid="cleanup-trigger-btn"
            >
              <Trash2 size={16} />
              {cleaning ? "Queuing…" : status.pending ? "Pending…" : "Clean VPS Now"}
            </button>
          </div>
        </div>

        {/* Last Result */}
        {status.last_result && (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5" data-testid="last-cleanup-result">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 size={18} className="text-emerald-400" />
              <h3 className="font-semibold">Last Cleanup</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 text-sm">
              <div>
                <div className="text-[#A1A1AA] text-xs">Completed</div>
                <div>{status.last_result.completed_at ? new Date(status.last_result.completed_at).toLocaleString() : "—"}</div>
              </div>
              <div>
                <div className="text-[#A1A1AA] text-xs">Disk Freed</div>
                <div className="text-emerald-300 font-semibold">{status.last_result.freed_mb ?? 0} MB</div>
              </div>
              <div>
                <div className="text-[#A1A1AA] text-xs">Disk Used Before → After</div>
                <div>
                  {status.last_result.before_used_kb
                    ? `${Math.round(status.last_result.before_used_kb / 1024 / 1024)} GB`
                    : "—"}{" "}
                  →{" "}
                  {status.last_result.after_used_kb
                    ? `${Math.round(status.last_result.after_used_kb / 1024 / 1024)} GB`
                    : "—"}
                </div>
              </div>
            </div>
            {status.last_result.actions && (
              <details className="text-xs text-[#A1A1AA]">
                <summary className="cursor-pointer hover:text-white">Action details</summary>
                <div className="mt-2 space-y-1 font-mono">
                  {Object.entries(status.last_result.actions).map(([k, v]) => (
                    <div key={k}>
                      <span className="text-[#A78BFA]">{k}:</span> {String(v)}
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" data-testid="cleanup-confirm-modal">
          <div className="bg-[var(--brand-bg)] border border-[var(--brand-border)] rounded-xl p-6 max-w-md w-full">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle size={20} className="text-yellow-400" />
              <h3 className="text-lg font-semibold">Confirm VPS Cleanup</h3>
            </div>
            <p className="text-sm text-[#A1A1AA] mb-2">This will safely clean up:</p>
            <ul className="text-xs text-[#A1A1AA] list-disc pl-5 mb-3 space-y-0.5">
              <li>Docker build cache (frees the most space)</li>
              <li>Stopped containers & dangling images</li>
              <li>System journal logs older than 7 days</li>
              <li>APT package cache</li>
              <li>Large Caddy access logs (rotated, not deleted)</li>
              <li>Stale /tmp Playwright profiles (&gt; 24h)</li>
            </ul>
            <p className="text-xs text-emerald-300 mb-4">
              ✓ Click data, uploads, RUT results, and active jobs are NEVER touched.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 text-sm border border-[var(--brand-border)] rounded-lg hover:bg-white/5"
                data-testid="cleanup-cancel-btn"
              >
                Cancel
              </button>
              <button
                onClick={requestCleanup}
                disabled={cleaning}
                className="px-4 py-2 text-sm bg-red-500 hover:bg-red-600 disabled:opacity-50 rounded-lg font-medium"
                data-testid="cleanup-confirm-btn"
              >
                {cleaning ? "Queuing…" : "Yes, Clean Now"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
