import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Plus, Play, Trash2, Copy, Download, Upload, Zap, Activity, Workflow as WfIcon, ArrowRight, Search, Camera, X } from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const authH = () => ({
  Authorization: `Bearer ${localStorage.getItem("token")}`,
  "Content-Type": "application/json",
});

export default function RPAWorkflowsPage() {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showRecordingsModal, setShowRecordingsModal] = useState(false);
  const [recordings, setRecordings] = useState([]);
  const [loadingRecordings, setLoadingRecordings] = useState(false);
  const [importingId, setImportingId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/rpa/workflows`, { headers: authH() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setWorkflows(await r.json());
    } catch (e) {
      toast.error(`Load failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const createNew = () => navigate("/rpa-studio/new");

  const duplicate = async (id) => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/rpa/workflows/${id}/duplicate`, {
        method: "POST",
        headers: authH(),
      });
      if (r.ok) {
        toast.success("Duplicated ✓");
        load();
      }
    } catch (e) { toast.error(e.message); }
  };

  const del = async (id, name) => {
    if (!window.confirm(`Delete workflow "${name}"?`)) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/rpa/workflows/${id}`, {
        method: "DELETE",
        headers: authH(),
      });
      if (r.ok) {
        toast.success("Deleted ✓");
        load();
      }
    } catch (e) { toast.error(e.message); }
  };

  const importJson = async () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      try {
        const text = await f.text();
        const data = JSON.parse(text);
        const r = await fetch(`${BACKEND_URL}/api/rpa/workflows/import`, {
          method: "POST",
          headers: authH(),
          body: JSON.stringify(data),
        });
        if (r.ok) {
          toast.success("Imported ✓");
          load();
        } else {
          const d = await r.json();
          toast.error(d.detail || "Import failed");
        }
      } catch (err) {
        toast.error(`Bad JSON: ${err.message}`);
      }
    };
    input.click();
  };

  // ── Live Recording → RPA Studio conversion ────────────────────────
  // Opens a modal listing the user's saved Visual Recorder uploads.
  // Picking one converts it to a flowchart workflow in one click.
  const openRecordingsModal = async () => {
    setShowRecordingsModal(true);
    setLoadingRecordings(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/uploads?type=automation_json`, { headers: authH() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const list = await r.json();
      setRecordings(Array.isArray(list) ? list : []);
    } catch (e) {
      toast.error(`Could not load recordings: ${e.message}`);
      setRecordings([]);
    } finally {
      setLoadingRecordings(false);
    }
  };

  const importFromRecording = async (upload) => {
    setImportingId(upload.id);
    try {
      const r = await fetch(`${BACKEND_URL}/api/rpa/workflows/from-upload/${upload.id}`, {
        method: "POST",
        headers: authH(),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      toast.success(`Imported "${upload.name}" → ${(d.nodes || []).length} nodes`);
      setShowRecordingsModal(false);
      navigate(`/rpa-studio/${d.id}`);
    } catch (e) {
      toast.error(`Import failed: ${e.message}`);
    } finally {
      setImportingId(null);
    }
  };

  const filtered = workflows.filter((w) =>
    !search.trim() || (w.name || "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 space-y-4" data-testid="rpa-workflows-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Zap className="w-6 h-6 text-blue-500" />
            RPA Studio
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Build no-code automation workflows with 55+ visual nodes — same power as AdsPower RPA.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/rpa-runs"
            className="px-3 py-2 rounded bg-slate-800 hover:bg-slate-700 text-sm flex items-center gap-2"
            data-testid="rpa-runs-link"
          >
            <Activity className="w-4 h-4" /> Runs
          </Link>
          <button
            onClick={openRecordingsModal}
            className="px-3 py-2 rounded bg-purple-600/20 hover:bg-purple-600 border border-purple-500/40 text-purple-200 hover:text-white text-sm flex items-center gap-2 transition-colors"
            data-testid="rpa-import-recording-btn"
            title="Convert a Visual Recorder session into an RPA flowchart"
          >
            <Camera className="w-4 h-4" /> Import from Recording
          </button>
          <button
            onClick={importJson}
            className="px-3 py-2 rounded bg-slate-800 hover:bg-slate-700 text-sm flex items-center gap-2"
            data-testid="rpa-import-btn"
          >
            <Upload className="w-4 h-4" /> Import JSON
          </button>
          <button
            onClick={createNew}
            className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-sm flex items-center gap-2 font-medium"
            data-testid="rpa-create-btn"
          >
            <Plus className="w-4 h-4" /> New Workflow
          </button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search workflows…"
          className="w-full pl-9 pr-3 py-2 rounded bg-slate-800 border border-slate-700 text-sm outline-none focus:ring-2 focus:ring-blue-500"
          data-testid="rpa-search"
        />
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-500">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 border-2 border-dashed border-slate-700 rounded-lg">
          <WfIcon className="w-12 h-12 mx-auto mb-3 text-slate-600" />
          <div className="text-lg mb-1">No workflows yet</div>
          <div className="text-sm text-slate-500 mb-4">Click <strong>New Workflow</strong> to create your first one</div>
          <button onClick={createNew} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm inline-flex items-center gap-2">
            <Plus className="w-4 h-4" /> Create Workflow
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((wf) => (
            <div
              key={wf.id}
              className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 hover:border-blue-500 transition-colors group"
              data-testid={`rpa-card-${wf.id}`}
            >
              <Link to={`/rpa-studio/${wf.id}`} className="block">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-sm truncate flex-1">{wf.name}</h3>
                  <span className="text-xs text-slate-500 ml-2">v{wf.version || 1}</span>
                </div>
                {wf.description && (
                  <p className="text-xs text-slate-400 mb-3 line-clamp-2">{wf.description}</p>
                )}
                <div className="flex items-center gap-3 text-xs text-slate-500">
                  <span>{(wf.nodes || []).length} nodes</span>
                  <span>·</span>
                  <span>{(wf.edges || []).length} edges</span>
                </div>
              </Link>
              <div className="mt-3 pt-3 border-t border-slate-700/50 flex items-center gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
                <Link
                  to={`/rpa-studio/${wf.id}`}
                  className="px-2 py-1 text-xs rounded bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white flex items-center gap-1"
                  data-testid={`rpa-edit-${wf.id}`}
                >
                  Open <ArrowRight className="w-3 h-3" />
                </Link>
                <div className="flex-1" />
                <button onClick={() => duplicate(wf.id)} className="p-1.5 rounded hover:bg-slate-700" title="Duplicate" data-testid={`rpa-duplicate-${wf.id}`}>
                  <Copy className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => del(wf.id, wf.name)} className="p-1.5 rounded hover:bg-red-500/20 text-red-400" title="Delete" data-testid={`rpa-delete-${wf.id}`}>
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Recordings modal — Live Visual Recorder → RPA Studio ── */}
      {showRecordingsModal && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowRecordingsModal(false)}
          data-testid="rpa-recordings-modal"
        >
          <div
            className="bg-slate-900 border border-purple-500/40 rounded-lg w-full max-w-3xl max-h-[80vh] flex flex-col overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
              <h3 className="font-semibold flex items-center gap-2">
                <Camera className="w-5 h-5 text-purple-400" />
                Import from Visual Recorder
              </h3>
              <button
                onClick={() => setShowRecordingsModal(false)}
                className="p-1 rounded hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="px-4 py-3 text-xs text-slate-400 border-b border-slate-800">
              Pick a saved recording — it will be auto-converted into a Krexion RPA flowchart that you can extend with If/Else, Loops, sub-workflows, and 3rd-party nodes.
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {loadingRecordings && <div className="text-sm text-slate-500 text-center py-8">Loading recordings…</div>}
              {!loadingRecordings && recordings.length === 0 && (
                <div className="text-center py-10">
                  <Camera className="w-10 h-10 mx-auto mb-2 text-slate-600" />
                  <div className="text-sm text-slate-500 mb-1">No saved recordings yet</div>
                  <div className="text-xs text-slate-600 mb-4">Open the Visual Recorder, record a flow, click Save → it'll appear here.</div>
                  <Link
                    to="/visual-recorder"
                    className="inline-flex items-center gap-2 px-3 py-2 bg-purple-600 hover:bg-purple-500 rounded text-sm"
                    onClick={() => setShowRecordingsModal(false)}
                  >
                    <Camera className="w-4 h-4" /> Open Visual Recorder
                  </Link>
                </div>
              )}
              {recordings.map((u) => {
                let stepCount = 0;
                try { stepCount = JSON.parse(u.automation_json || "[]").length; } catch {}
                return (
                  <button
                    key={u.id}
                    onClick={() => importFromRecording(u)}
                    disabled={importingId === u.id}
                    className="w-full text-left p-3 rounded border border-slate-700 bg-slate-800/50 hover:bg-slate-800 hover:border-purple-500 transition-colors disabled:opacity-50 flex items-center gap-3"
                    data-testid={`rpa-import-recording-${u.id}`}
                  >
                    <div className="w-10 h-10 rounded bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                      <Camera className="w-5 h-5 text-purple-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-sm truncate">{u.name || "Untitled recording"}</div>
                      {u.description && <div className="text-xs text-slate-400 truncate">{u.description}</div>}
                      <div className="text-xs text-slate-500 mt-0.5">
                        {stepCount} step{stepCount === 1 ? "" : "s"}
                        {u.created_at && ` · ${new Date(u.created_at).toLocaleDateString()}`}
                      </div>
                    </div>
                    {importingId === u.id ? (
                      <span className="text-xs text-purple-300">Converting…</span>
                    ) : (
                      <ArrowRight className="w-4 h-4 text-slate-500" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
