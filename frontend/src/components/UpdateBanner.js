import React, { useEffect, useState } from "react";
import axios from "axios";
import { Sparkles, AlertCircle, Download, X, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const POLL_INTERVAL_MS = 10 * 60 * 1000; // 10 min

/**
 * UpdateBanner
 * -------------
 * Polls /api/system/public-latest. When a newer release exists, shows a
 * banner with title + severity color. Click → modal with full release
 * notes + "Install update" button. Admins on local installs can trigger
 * the update via POST /api/system/install-update (writes a flag file the
 * host updater service picks up).
 *
 * Dismissable per-version (sessionStorage key includes version).
 */
export default function UpdateBanner() {
  const [info, setInfo] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const fetchLatest = async () => {
    try {
      const r = await axios.get(`${API}/system/public-latest`);
      if (r.data?.update_available) {
        const v = r.data.latest.version;
        const key = `update_banner_dismissed_${v}`;
        setDismissed(sessionStorage.getItem(key) === "1");
        setInfo(r.data);
      } else {
        setInfo(null);
      }
    } catch (_e) {
      // silent — banner just hides
    }
  };

  useEffect(() => {
    fetchLatest();
    const t = setInterval(fetchLatest, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, []);

  if (!info || dismissed) return null;

  const { latest, current } = info;
  const severity = latest.severity || "recommended";
  const colors = {
    info: { bg: "from-[#1e1530] to-[#0f0a18]", accent: "#A78BFA", label: "Info" },
    recommended: { bg: "from-[#0d2740] to-[#0a0f1f]", accent: "#3B82F6", label: "Recommended" },
    critical: { bg: "from-[#3b0a0a] to-[#1f0a0a]", accent: "#EF4444", label: "Critical" },
  };
  const c = colors[severity] || colors.recommended;

  const handleInstall = async () => {
    setInstalling(true);
    try {
      const token =
        localStorage.getItem("token") ||
        localStorage.getItem("adminToken") ||
        localStorage.getItem("admin_token");
      const r = await axios.post(
        `${API}/system/install-update`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(r.data?.message || "Update started — Krexion will restart shortly.");
      setShowModal(false);
      // After ~90s the new version should be live → reload
      setTimeout(() => window.location.reload(), 90000);
    } catch (e) {
      const detail = e.response?.data?.detail || "Update failed";
      toast.error(detail);
    } finally {
      setInstalling(false);
    }
  };

  const dismiss = () => {
    sessionStorage.setItem(`update_banner_dismissed_${latest.version}`, "1");
    setDismissed(true);
  };

  return (
    <>
      <div
        data-testid="update-banner"
        className={`bg-gradient-to-r ${c.bg} border-b text-white`}
        style={{ borderBottomColor: `${c.accent}66` }}
      >
        <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center gap-3 text-sm">
          <div
            className="shrink-0 w-7 h-7 rounded-md flex items-center justify-center border"
            style={{ backgroundColor: `${c.accent}33`, borderColor: `${c.accent}66` }}
          >
            <Sparkles size={14} style={{ color: c.accent }} />
          </div>
          <div className="flex-1 min-w-0">
            <span
              className="text-[10px] uppercase tracking-widest font-bold mr-2 px-2 py-0.5 rounded"
              style={{ backgroundColor: `${c.accent}22`, color: c.accent }}
              data-testid="update-banner-severity"
            >
              {c.label} update
            </span>
            <span className="font-semibold">
              {latest.title || `Krexion v${latest.version}`}
            </span>
            <span className="text-[#A1A1AA] ml-2 hidden sm:inline">
              — you're on v{current}, latest is v{latest.version}
            </span>
          </div>
          <button
            onClick={() => setShowModal(true)}
            data-testid="update-banner-view"
            className="shrink-0 text-xs font-semibold px-3 py-1.5 rounded-md transition"
            style={{ backgroundColor: c.accent, color: "#0a0a0f" }}
          >
            View & install
          </button>
          {severity !== "critical" && (
            <button
              onClick={dismiss}
              className="shrink-0 text-[#A1A1AA] hover:text-white p-1"
              aria-label="Dismiss"
              data-testid="update-banner-dismiss"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {showModal && (
        <div
          className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          data-testid="update-modal"
        >
          <div className="bg-[#0f0a18] border border-white/10 rounded-2xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col shadow-2xl">
            <div className="px-6 py-5 border-b border-white/10 flex items-start justify-between gap-3">
              <div>
                <div
                  className="text-[10px] uppercase tracking-widest font-bold mb-1.5 inline-block px-2 py-0.5 rounded"
                  style={{ backgroundColor: `${c.accent}22`, color: c.accent }}
                >
                  {c.label} update
                </div>
                <h3 className="text-lg font-bold">{latest.title || `Krexion v${latest.version}`}</h3>
                <p className="text-xs text-[#71717A] mt-1">
                  Released {new Date(latest.created_at).toLocaleDateString()} • upgrading from v{current} → v{latest.version}
                </p>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-[#71717A] hover:text-white p-1"
                data-testid="update-modal-close"
              >
                <X size={18} />
              </button>
            </div>
            <div className="px-6 py-5 overflow-auto flex-1">
              <div className="text-xs uppercase tracking-wider text-[#71717A] mb-2">What's new</div>
              <pre
                className="text-sm text-[#D4D4D8] whitespace-pre-wrap font-sans leading-relaxed"
                data-testid="update-modal-notes"
              >
                {latest.notes || "No release notes provided."}
              </pre>
            </div>
            <div className="px-6 py-4 border-t border-white/10 flex items-center justify-between bg-white/[0.02]">
              <div className="flex items-start gap-2 text-xs text-[#71717A]">
                <AlertCircle size={13} className="shrink-0 mt-0.5" />
                <span>
                  Krexion will restart automatically.<br/>
                  Active proxy/RUT jobs will resume after restart.
                </span>
              </div>
              <button
                onClick={handleInstall}
                disabled={installing}
                data-testid="update-modal-install"
                className="inline-flex items-center gap-2 font-bold px-5 py-2.5 rounded-lg transition disabled:opacity-60"
                style={{ backgroundColor: c.accent, color: "#0a0a0f" }}
              >
                {installing ? (
                  <>
                    <Loader2 size={15} className="animate-spin" /> Installing…
                  </>
                ) : (
                  <>
                    <Download size={15} /> Install update
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
