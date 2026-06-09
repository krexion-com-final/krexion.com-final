import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Plus, Play, Trash2, Copy, Download, Upload, Zap, Activity, Workflow as WfIcon, ArrowRight, Search } from "lucide-react";
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
    </div>
  );
}
