import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, RefreshCw, Activity, CheckCircle2, XCircle, Clock, ChevronRight } from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const authH = () => ({
  Authorization: `Bearer ${localStorage.getItem("token")}`,
  "Content-Type": "application/json",
});

const statusIcon = (s) => {
  switch (s) {
    case "completed": return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
    case "failed":    return <XCircle className="w-4 h-4 text-red-500" />;
    case "cancelled": return <XCircle className="w-4 h-4 text-slate-500" />;
    case "running":   return <Activity className="w-4 h-4 text-blue-500 animate-pulse" />;
    default:          return <Clock className="w-4 h-4 text-amber-500" />;
  }
};

export default function RPARunsPage() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/rpa/runs?limit=100`, { headers: authH() });
      if (r.ok) setRuns(await r.json());
    } catch (e) {
      toast.error(e.message);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="p-6 space-y-4" data-testid="rpa-runs-page">
      <div className="flex items-center gap-3">
        <Link to="/rpa-studio" className="p-2 rounded hover:bg-slate-800">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Activity className="w-6 h-6 text-blue-500" />
          Run History
        </h1>
        <div className="flex-1" />
        <button onClick={load} className="p-2 rounded hover:bg-slate-800" data-testid="rpa-runs-refresh">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 space-y-2">
          {loading && <div className="text-slate-500 text-sm">Loading…</div>}
          {!loading && runs.length === 0 && <div className="text-slate-500 text-sm p-4 text-center">No runs yet</div>}
          {runs.map((r) => (
            <button
              key={r.id}
              onClick={() => setSelected(r)}
              className={`w-full text-left p-3 rounded border ${selected?.id === r.id ? "border-blue-500 bg-blue-500/10" : "border-slate-700 bg-slate-800/50 hover:bg-slate-800"}`}
              data-testid={`rpa-run-row-${r.id}`}
            >
              <div className="flex items-center gap-2 text-sm">
                {statusIcon(r.status)}
                <span className="font-semibold truncate flex-1">{r.workflow_name || r.workflow_id}</span>
                <ChevronRight className="w-3 h-3 opacity-50" />
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {new Date(r.started_at).toLocaleString()} · {r.status}
              </div>
            </button>
          ))}
        </div>

        <div className="lg:col-span-2 bg-slate-800/30 border border-slate-700 rounded-lg p-4 min-h-[400px]">
          {selected ? (
            <div>
              <div className="flex items-center gap-2 mb-3">
                {statusIcon(selected.status)}
                <h3 className="text-lg font-semibold flex-1">{selected.workflow_name}</h3>
                <span className="text-xs text-slate-500">{selected.id}</span>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-4 text-xs">
                <div>
                  <div className="text-slate-500">Status</div>
                  <div className="font-mono">{selected.status}</div>
                </div>
                <div>
                  <div className="text-slate-500">Progress</div>
                  <div className="font-mono">{selected.progress || 0}%</div>
                </div>
                <div>
                  <div className="text-slate-500">Started</div>
                  <div className="font-mono">{new Date(selected.started_at).toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-slate-500">Finished</div>
                  <div className="font-mono">{selected.finished_at ? new Date(selected.finished_at).toLocaleString() : "—"}</div>
                </div>
              </div>
              {selected.error_message && (
                <div className="mb-3 p-3 rounded bg-red-500/10 border border-red-500/30 text-red-300 text-xs">
                  <strong>Error:</strong> {selected.error_message}
                </div>
              )}
              <div className="text-xs text-slate-400 mb-1">Step events ({(selected.step_results || []).length})</div>
              <div className="max-h-96 overflow-y-auto bg-slate-950 rounded p-2 text-xs font-mono space-y-1">
                {(selected.step_results || []).map((ev, i) => (
                  <div
                    key={i}
                    className={`px-2 py-1 rounded ${
                      ev.status === "ok" ? "bg-emerald-900/20 text-emerald-300" :
                      ev.status === "error" ? "bg-red-900/20 text-red-300" :
                      "bg-slate-800/40 text-slate-300"
                    }`}
                    data-testid={`rpa-run-detail-event-${i}`}
                  >
                    <span className="opacity-60">[{ev.step || i + 1}]</span> {ev.type} — <span className="opacity-70">{ev.status}</span>
                    {ev.error && <span className="block text-red-400 mt-0.5">⚠ {ev.error}</span>}
                  </div>
                ))}
                {(!selected.step_results || selected.step_results.length === 0) && <div className="text-slate-500">No events</div>}
              </div>
            </div>
          ) : (
            <div className="text-slate-500 text-sm flex items-center justify-center h-full">
              ← Select a run to see details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
