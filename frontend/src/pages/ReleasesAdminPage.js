import React, { useEffect, useState } from "react";
import axios from "axios";
import { Plus, Sparkles, Trash2, Edit3, RefreshCw, X, Wand2 } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SEVERITY_COLORS = {
  info: "bg-[#A78BFA]/15 text-[#A78BFA] border-[#A78BFA]/30",
  recommended: "bg-[#3B82F6]/15 text-[#3B82F6] border-[#3B82F6]/30",
  critical: "bg-[#EF4444]/15 text-[#EF4444] border-[#EF4444]/30",
};

function authHeaders() {
  const token =
    localStorage.getItem("adminToken") ||
    localStorage.getItem("admin_token") ||
    localStorage.getItem("token");
  return { Authorization: `Bearer ${token}` };
}

export default function ReleasesAdminPage() {
  const [releases, setReleases] = useState([]);
  const [currentVersion, setCurrentVersion] = useState("");
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [detection, setDetection] = useState(null); // last auto-detect result for the modal preview
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({
    version: "",
    title: "",
    notes: "",
    severity: "recommended",
    download_url: "",
    published: true,
  });

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/releases`, { headers: authHeaders() });
      setReleases(r.data.releases || []);
      setCurrentVersion(r.data.current_version || "");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load releases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const reset = () => {
    setForm({ version: "", title: "", notes: "", severity: "recommended", download_url: "", published: true });
    setEditingId(null);
    setDetection(null);
    setShowForm(false);
  };

  const autoDetect = async () => {
    setDetecting(true);
    try {
      const r = await axios.get(`${API}/admin/releases/auto-detect`, { headers: authHeaders() });
      const d = r.data || {};
      if (!d.needs_release) {
        toast.info(
          d.last_release_version
            ? `No new changes since v${d.last_release_version}. Nothing to release.`
            : "No new changes detected. Nothing to release."
        );
        setDetection(d);
        return;
      }
      // Pre-fill the form with detected suggestions and open the modal
      setForm({
        version: d.suggested_version || "",
        title: d.suggested_title || "",
        notes: d.suggested_notes || "",
        severity: d.suggested_severity || "recommended",
        download_url: "",
        published: true,
      });
      setEditingId(null);
      setDetection(d);
      setShowForm(true);
      const n = d.meaningful_commit_count || d.files_changed_count || d.commit_count || 0;
      const unit = d.notes_source === "files" ? "file" : "change";
      toast.success(`Detected ${n} ${unit}${n === 1 ? "" : "s"} since last release — review and publish.`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Auto-detect failed");
    } finally {
      setDetecting(false);
    }
  };

  const save = async () => {
    try {
      if (editingId) {
        const patch = { ...form };
        delete patch.version; // immutable
        await axios.patch(`${API}/admin/releases/${editingId}`, patch, { headers: authHeaders() });
        toast.success("Release updated");
      } else {
        await axios.post(`${API}/admin/releases`, form, { headers: authHeaders() });
        toast.success(`Release ${form.version} published — all customers will be notified within 10 minutes.`);
      }
      reset();
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  const edit = (rel) => {
    setForm({
      version: rel.version,
      title: rel.title || "",
      notes: rel.notes || "",
      severity: rel.severity || "recommended",
      download_url: rel.download_url || "",
      published: !!rel.published,
    });
    setEditingId(rel.id);
    setShowForm(true);
  };

  const remove = async (rel) => {
    if (!window.confirm(`Delete release v${rel.version}? Customers will stop seeing this update notification.`)) return;
    try {
      await axios.delete(`${API}/admin/releases/${rel.id}`, { headers: authHeaders() });
      toast.success("Release deleted");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="releases-admin-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Sparkles className="text-[#A78BFA]" size={22} />
            App Releases
          </h1>
          <p className="text-sm text-[#A1A1AA] mt-1">
            Publish a new version → every customer gets a notification banner within 10 minutes. They click "Install update" → containers auto-rebuild on their PC.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="flex items-center gap-1.5 bg-white/5 border border-white/10 px-3 py-2 rounded-md hover:bg-white/10 transition text-xs"
            data-testid="refresh-releases"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
          <button
            onClick={autoDetect}
            disabled={detecting}
            data-testid="auto-detect-release-button"
            className="flex items-center gap-1.5 bg-[#3B82F6]/15 border border-[#3B82F6]/40 text-[#93C5FD] px-3 py-2 rounded-md hover:bg-[#3B82F6]/25 transition text-xs disabled:opacity-60 disabled:cursor-not-allowed"
            title="Detect changes since last release and pre-fill a new release"
          >
            <Wand2 size={13} className={detecting ? "animate-spin" : ""} />
            {detecting ? "Detecting…" : "Auto-detect update"}
          </button>
          <button
            onClick={() => { reset(); setShowForm(true); }}
            data-testid="new-release-button"
            className="flex items-center gap-1.5 bg-[#A78BFA] text-black px-4 py-2 rounded-md font-medium hover:bg-[#C4B5FD] transition text-sm"
          >
            <Plus size={15} /> Publish release
          </button>
        </div>
      </div>

      <div className="text-xs text-[#71717A] mb-4">
        This server is running version{" "}
        <span className="font-mono text-[#A78BFA]">{currentVersion || "—"}</span>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0f0a18] border border-white/10 rounded-2xl w-full max-w-lg p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-bold">{editingId ? "Edit release" : "Publish a new release"}</h3>
              <button onClick={reset} className="text-[#71717A] hover:text-white" data-testid="close-form"><X size={18} /></button>
            </div>
            {detection && !editingId && detection.needs_release && (
              <div
                data-testid="auto-detect-banner"
                className="mb-4 flex items-start gap-2 bg-[#3B82F6]/10 border border-[#3B82F6]/30 text-[#BFDBFE] rounded-md px-3 py-2 text-xs"
              >
                <Wand2 size={14} className="mt-0.5 shrink-0" />
                <div>
                  Auto-filled from{" "}
                  {detection.notes_source === "files" ? (
                    <>
                      <span className="font-mono">{detection.files_changed_count}</span>{" "}
                      file{detection.files_changed_count === 1 ? "" : "s"} changed
                    </>
                  ) : (
                    <>
                      <span className="font-mono">{detection.meaningful_commit_count || detection.commit_count}</span>{" "}
                      commit{(detection.meaningful_commit_count || detection.commit_count) === 1 ? "" : "s"}
                    </>
                  )}
                  {" "}since{" "}
                  {detection.last_release_version
                    ? <>last release <span className="font-mono">v{detection.last_release_version}</span></>
                    : "the start of the repo"}.
                  {" "}You can edit anything below before publishing.
                </div>
              </div>
            )}
            <div className="space-y-3">
              <div>
                <label className="block text-xs uppercase tracking-wider text-[#71717A] mb-1">Version (semver)</label>
                <input
                  type="text"
                  placeholder="1.0.2"
                  value={form.version}
                  onChange={(e) => setForm({ ...form, version: e.target.value })}
                  disabled={!!editingId}
                  data-testid="release-version"
                  className="w-full bg-white/[0.04] border border-white/10 rounded-md px-3 py-2 text-sm font-mono disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-wider text-[#71717A] mb-1">Title</label>
                <input
                  type="text"
                  placeholder="v1.0.2 — Improved proxy speeds"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  data-testid="release-title"
                  className="w-full bg-white/[0.04] border border-white/10 rounded-md px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-wider text-[#71717A] mb-1">Release notes</label>
                <textarea
                  rows={6}
                  placeholder="- Added X&#10;- Fixed Y&#10;- Improved Z"
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  data-testid="release-notes"
                  className="w-full bg-white/[0.04] border border-white/10 rounded-md px-3 py-2 text-sm font-sans"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs uppercase tracking-wider text-[#71717A] mb-1">Severity</label>
                  <select
                    value={form.severity}
                    onChange={(e) => setForm({ ...form, severity: e.target.value })}
                    data-testid="release-severity"
                    className="w-full bg-white/[0.04] border border-white/10 rounded-md px-3 py-2 text-sm"
                  >
                    <option value="info">Info (purple, dismissable)</option>
                    <option value="recommended">Recommended (blue, dismissable)</option>
                    <option value="critical">Critical (red, NOT dismissable)</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={form.published}
                      onChange={(e) => setForm({ ...form, published: e.target.checked })}
                      data-testid="release-published"
                      className="w-4 h-4"
                    />
                    Publish immediately
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-xs uppercase tracking-wider text-[#71717A] mb-1">Download URL (optional)</label>
                <input
                  type="text"
                  placeholder="https://krexion.com/releases/1.0.2.zip"
                  value={form.download_url}
                  onChange={(e) => setForm({ ...form, download_url: e.target.value })}
                  data-testid="release-download-url"
                  className="w-full bg-white/[0.04] border border-white/10 rounded-md px-3 py-2 text-sm font-mono"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <button onClick={reset} className="px-4 py-2 text-sm hover:bg-white/5 rounded-md">Cancel</button>
              <button
                onClick={save}
                data-testid="save-release"
                className="bg-[#A78BFA] text-black font-semibold px-5 py-2 rounded-md hover:bg-[#C4B5FD] text-sm"
              >
                {editingId ? "Save changes" : "Publish release"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {releases.length === 0 && !loading && (
          <div className="bg-white/[0.02] border border-white/10 rounded-xl p-10 text-center text-[#71717A]">
            <Sparkles size={28} className="mx-auto mb-3 opacity-50" />
            <p className="font-semibold mb-1 text-white">No releases yet</p>
            <p className="text-sm">Publish your first release — customers will see a notification banner the next time their app polls (within 10 minutes).</p>
          </div>
        )}
        {releases.map((r) => (
          <div
            key={r.id}
            data-testid={`release-item-${r.version}`}
            className="bg-white/[0.03] border border-white/10 rounded-xl p-5 flex items-start gap-4"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-bold text-lg font-mono text-white">v{r.version}</span>
                <span className={`text-[10px] uppercase tracking-widest px-2 py-0.5 rounded border ${SEVERITY_COLORS[r.severity] || SEVERITY_COLORS.recommended}`}>
                  {r.severity}
                </span>
                {!r.published && (
                  <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded border bg-white/5 border-white/10 text-[#71717A]">
                    draft
                  </span>
                )}
              </div>
              <h3 className="font-semibold text-sm mb-1">{r.title}</h3>
              {r.notes && (
                <p className="text-xs text-[#A1A1AA] whitespace-pre-wrap line-clamp-3 mt-2 mb-1">{r.notes}</p>
              )}
              <p className="text-[10px] text-[#71717A] mt-2">
                Published {new Date(r.created_at).toLocaleString()} by {r.created_by}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => edit(r)}
                className="p-2 text-[#A1A1AA] hover:text-white hover:bg-white/5 rounded-md transition"
                data-testid={`edit-release-${r.version}`}
                title="Edit"
              >
                <Edit3 size={15} />
              </button>
              <button
                onClick={() => remove(r)}
                className="p-2 text-[#A1A1AA] hover:text-[#EF4444] hover:bg-[#EF4444]/10 rounded-md transition"
                data-testid={`delete-release-${r.version}`}
                title="Delete"
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
