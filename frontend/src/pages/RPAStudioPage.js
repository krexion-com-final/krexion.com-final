import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  Play,
  Save,
  Plus,
  Trash2,
  Download,
  Upload,
  ChevronLeft,
  Layers,
  X,
  Settings as SettingsIcon,
  Activity,
  Zap,
  Search,
  Copy,
  ArrowLeft,
  AlertCircle,
  Code,
} from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const authH = () => ({
  Authorization: `Bearer ${localStorage.getItem("token")}`,
  "Content-Type": "application/json",
});

// Inline node component — small, color-coded, shows type + first param value
const FlowNode = ({ data }) => (
  <div
    style={{
      background: data.color || "#1e293b",
      color: "#fff",
      borderRadius: 10,
      padding: "10px 14px",
      minWidth: 160,
      border: data.selected ? "2px solid #60a5fa" : "1px solid rgba(255,255,255,.15)",
      boxShadow: "0 6px 16px rgba(0,0,0,.4)",
      fontFamily: "ui-sans-serif, system-ui",
    }}
    data-testid={`rpa-node-${data.type}`}
  >
    <div style={{ fontWeight: 600, fontSize: 13, opacity: 0.95 }}>{data.label || data.type}</div>
    <div style={{ fontSize: 11, opacity: 0.75, marginTop: 4, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
      {data.summary || data.type}
    </div>
  </div>
);

const nodeTypes = { rpa: FlowNode };

export default function RPAStudioPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [workflow, setWorkflow] = useState(null);
  const [catalog, setCatalog] = useState({ categories: [] });
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [search, setSearch] = useState("");
  const [running, setRunning] = useState(false);
  const [runId, setRunId] = useState(null);
  const [runEvents, setRunEvents] = useState([]);
  const [runStatus, setRunStatus] = useState(null);
  const [showJsonEditor, setShowJsonEditor] = useState(false);
  const [jsonText, setJsonText] = useState("");
  const [saving, setSaving] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showRunPanel, setShowRunPanel] = useState(false);
  const reactFlowWrapper = useRef(null);
  const [rfInstance, setRfInstance] = useState(null);
  const [livePreview, setLivePreview] = useState(null);
  const liveImgRef = useRef(null);

  // Load catalog + workflow
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/rpa/node-catalog`, { headers: authH() });
        if (r.ok) {
          setCatalog(await r.json());
        }
      } catch {}
    })();
  }, []);

  useEffect(() => {
    if (!id || id === "new") {
      setWorkflow({ name: "Untitled Workflow", nodes: [], edges: [], settings: {}, variables: {} });
      setNodes([]);
      setEdges([]);
      return;
    }
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/rpa/workflows/${id}`, { headers: authH() });
        if (!r.ok) {
          toast.error("Workflow not found");
          navigate("/rpa-studio");
          return;
        }
        const wf = await r.json();
        setWorkflow(wf);
        setNodes(deserializeNodes(wf.nodes || [], catalog));
        setEdges(deserializeEdges(wf.edges || []));
      } catch (e) {
        toast.error(`Load failed: ${e.message}`);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Build a lookup of {type: {label, color, category}} from catalog
  const typeLookup = useMemo(() => {
    const out = {};
    (catalog.categories || []).forEach((cat) => {
      (cat.nodes || []).forEach((n) => {
        out[n.type] = { label: n.label, color: cat.color, category: cat.key, params: n.params };
      });
    });
    return out;
  }, [catalog]);

  const onNodesChange = useCallback((changes) => setNodes((nds) => applyNodeChanges(changes, nds)), []);
  const onEdgesChange = useCallback((changes) => setEdges((eds) => applyEdgeChanges(changes, eds)), []);
  const onConnect = useCallback(
    (connection) => setEdges((eds) => addEdge({ ...connection, animated: true, style: { stroke: "#60a5fa", strokeWidth: 2 } }, eds)),
    []
  );

  const addNode = useCallback(
    (nodeType) => {
      const typeInfo = typeLookup[nodeType] || {};
      const newId = `n_${Math.random().toString(36).slice(2, 9)}`;
      const newNode = {
        id: newId,
        type: "rpa",
        position: { x: 200 + Math.random() * 250, y: 100 + Math.random() * 250 },
        data: {
          type: nodeType,
          label: typeInfo.label || nodeType,
          color: typeInfo.color || "#1e293b",
          params: {},
          on_error: "skip",
          summary: nodeType,
        },
      };
      setNodes((nds) => [...nds, newNode]);
      setSelectedNodeId(newId);
      toast.success(`Added: ${typeInfo.label || nodeType}`);
    },
    [typeLookup]
  );

  const deleteNode = (nodeId) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    if (selectedNodeId === nodeId) setSelectedNodeId(null);
  };

  const updateNodeParam = (nodeId, key, value) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id !== nodeId) return n;
        const newParams = { ...(n.data.params || {}), [key]: value };
        // Build a friendly 1-line summary
        const firstVal = Object.values(newParams)[0];
        return {
          ...n,
          data: {
            ...n.data,
            params: newParams,
            summary: firstVal ? String(firstVal).slice(0, 30) : n.data.type,
          },
        };
      })
    );
  };

  const updateNodeOnError = (nodeId, val) => {
    setNodes((nds) => nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, on_error: val } } : n)));
  };

  const saveWorkflow = async () => {
    if (!workflow) return;
    setSaving(true);
    try {
      const serialized = {
        name: workflow.name || "Untitled",
        description: workflow.description || "",
        nodes: nodes.map(serializeNode),
        edges: edges.map((e) => ({ from: e.source, to: e.target, label: e.label })),
        settings: workflow.settings || {},
        variables: workflow.variables || {},
      };
      let r;
      if (workflow.id) {
        r = await fetch(`${BACKEND_URL}/api/rpa/workflows/${workflow.id}`, {
          method: "PATCH",
          headers: authH(),
          body: JSON.stringify(serialized),
        });
      } else {
        r = await fetch(`${BACKEND_URL}/api/rpa/workflows`, {
          method: "POST",
          headers: authH(),
          body: JSON.stringify(serialized),
        });
      }
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      setWorkflow(d);
      toast.success("Saved ✓");
      if (!workflow.id) navigate(`/rpa-studio/${d.id}`, { replace: true });
    } catch (e) {
      toast.error(`Save failed: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const runWorkflow = async () => {
    if (!workflow?.id) {
      toast.error("Save the workflow first");
      return;
    }
    setRunning(true);
    setRunEvents([]);
    setRunStatus("starting");
    setShowRunPanel(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/rpa/workflows/${workflow.id}/run`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({}),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      setRunId(d.run_id);
      toast.success(`Run started: ${d.run_id}`);
    } catch (e) {
      toast.error(`Run failed: ${e.message}`);
      setRunning(false);
    }
  };

  // Poll run status
  useEffect(() => {
    if (!runId) return;
    const poll = async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/rpa/runs/${runId}/live`, { headers: authH() });
        if (!r.ok) return;
        const d = await r.json();
        setRunEvents(d.events || []);
        setRunStatus(d.status);
        if (d.has_screenshot) {
          setLivePreview(`${BACKEND_URL}/api/rpa/runs/${runId}/screenshot?t=${encodeURIComponent(localStorage.getItem("token"))}&ts=${Date.now()}`);
        }
        if (["completed", "failed", "cancelled"].includes(d.status)) {
          setRunning(false);
          if (d.status === "completed") toast.success("Run completed ✓");
          else if (d.status === "failed") toast.error(`Run failed: ${d.error_message || "unknown"}`);
        }
      } catch {}
    };
    poll();
    const t = setInterval(poll, 1500);
    return () => clearInterval(t);
  }, [runId]);

  const stopRun = async () => {
    if (!runId) return;
    await fetch(`${BACKEND_URL}/api/rpa/runs/${runId}/stop`, { method: "POST", headers: authH() });
    setRunning(false);
    toast.info("Run stopped");
  };

  const exportJson = () => {
    if (!workflow?.id) {
      toast.error("Save first");
      return;
    }
    fetch(`${BACKEND_URL}/api/rpa/workflows/${workflow.id}/export`, { headers: authH() })
      .then((r) => r.json())
      .then((d) => {
        const blob = new Blob([JSON.stringify(d, null, 2)], { type: "application/json" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${(workflow.name || "workflow").replace(/[^a-z0-9]/gi, "_")}.json`;
        a.click();
        URL.revokeObjectURL(a.href);
      });
  };

  // Filter palette nodes by search
  const filteredCategories = useMemo(() => {
    if (!search.trim()) return catalog.categories || [];
    const q = search.toLowerCase();
    return (catalog.categories || [])
      .map((cat) => ({
        ...cat,
        nodes: (cat.nodes || []).filter((n) => n.label.toLowerCase().includes(q) || n.type.toLowerCase().includes(q)),
      }))
      .filter((cat) => cat.nodes.length > 0);
  }, [search, catalog]);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const paramSpec = selectedNode ? typeLookup[selectedNode.data.type]?.params || [] : [];

  return (
    <ReactFlowProvider>
      <div className="flex flex-col h-screen bg-slate-950 text-white" data-testid="rpa-studio-page">
        {/* Top toolbar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800 bg-slate-900">
          <button
            onClick={() => navigate("/rpa-studio")}
            className="p-2 rounded hover:bg-slate-800"
            data-testid="rpa-back-btn"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <input
            value={workflow?.name || ""}
            onChange={(e) => setWorkflow({ ...workflow, name: e.target.value })}
            placeholder="Workflow name"
            className="bg-slate-800 px-3 py-1.5 rounded text-sm w-72 outline-none focus:ring-2 focus:ring-blue-500"
            data-testid="rpa-name-input"
          />
          <span className="text-xs text-slate-400">
            {nodes.length} nodes · {edges.length} edges {workflow?.id && `· v${workflow.version}`}
          </span>
          <div className="flex-1" />
          <button onClick={() => setShowSettings(!showSettings)} className="p-2 rounded hover:bg-slate-800" title="Settings" data-testid="rpa-settings-btn">
            <SettingsIcon className="w-4 h-4" />
          </button>
          <button onClick={exportJson} className="p-2 rounded hover:bg-slate-800" title="Export JSON" data-testid="rpa-export-btn">
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={saveWorkflow}
            disabled={saving}
            className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-sm flex items-center gap-1.5 disabled:opacity-50"
            data-testid="rpa-save-btn"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? "Saving..." : "Save"}
          </button>
          <button
            onClick={running ? stopRun : runWorkflow}
            disabled={!workflow?.id}
            className={`px-3 py-1.5 rounded text-sm flex items-center gap-1.5 ${running ? "bg-red-600 hover:bg-red-500" : "bg-emerald-600 hover:bg-emerald-500"} disabled:opacity-50`}
            data-testid="rpa-run-btn"
          >
            {running ? <X className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {running ? "Stop" : "Run"}
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Left: Node Palette */}
          <div className="w-64 border-r border-slate-800 bg-slate-900 overflow-y-auto" data-testid="rpa-palette">
            <div className="p-3 sticky top-0 bg-slate-900 z-10 border-b border-slate-800">
              <div className="flex items-center gap-2 mb-2">
                <Layers className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-semibold">Node Palette</h3>
              </div>
              <div className="relative">
                <Search className="absolute left-2 top-2 w-3.5 h-3.5 text-slate-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search nodes…"
                  className="w-full bg-slate-800 pl-7 pr-2 py-1.5 rounded text-xs outline-none focus:ring-2 focus:ring-blue-500"
                  data-testid="rpa-palette-search"
                />
              </div>
            </div>
            <div className="p-2 space-y-3">
              {filteredCategories.map((cat) => (
                <div key={cat.key}>
                  <div className="text-xs font-semibold mb-1 px-2 flex items-center gap-1.5" style={{ color: cat.color }}>
                    <span className="w-2 h-2 rounded-full" style={{ background: cat.color }} />
                    {cat.label} ({cat.nodes.length})
                  </div>
                  <div className="space-y-1">
                    {cat.nodes.map((n) => (
                      <button
                        key={n.type}
                        onClick={() => addNode(n.type)}
                        className="w-full text-left px-3 py-1.5 text-xs rounded bg-slate-800 hover:bg-slate-700 flex items-center justify-between transition-colors"
                        data-testid={`rpa-palette-add-${n.type}`}
                      >
                        <span>{n.label}</span>
                        <Plus className="w-3 h-3 opacity-50" />
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              {filteredCategories.length === 0 && (
                <div className="text-xs text-slate-500 p-3">No matching nodes</div>
              )}
            </div>
          </div>

          {/* Center: Canvas */}
          <div className="flex-1 relative" ref={reactFlowWrapper}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={(_, node) => setSelectedNodeId(node.id)}
              onPaneClick={() => setSelectedNodeId(null)}
              nodeTypes={nodeTypes}
              fitView
              onInit={setRfInstance}
              defaultEdgeOptions={{ animated: true, style: { stroke: "#60a5fa", strokeWidth: 2 } }}
              data-testid="rpa-canvas"
            >
              <Background color="#1e293b" gap={20} />
              <Controls />
              <MiniMap nodeColor={(n) => n.data?.color || "#475569"} maskColor="rgba(0,0,0,.5)" />
            </ReactFlow>
            {nodes.length === 0 && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-slate-500">
                <Zap className="w-12 h-12 mb-3 opacity-40" />
                <div className="text-lg mb-1">Empty workflow</div>
                <div className="text-sm">← Click a node from the palette to start</div>
              </div>
            )}
          </div>

          {/* Right: Inspector */}
          <div className="w-80 border-l border-slate-800 bg-slate-900 overflow-y-auto" data-testid="rpa-inspector">
            {selectedNode ? (
              <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full" style={{ background: selectedNode.data.color }} />
                    {selectedNode.data.label}
                  </h3>
                  <button
                    onClick={() => deleteNode(selectedNode.id)}
                    className="p-1.5 rounded hover:bg-red-500/20 text-red-400"
                    title="Delete node"
                    data-testid="rpa-delete-node-btn"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="text-xs text-slate-500 mb-3 font-mono">{selectedNode.data.type}</div>

                {/* Param fields */}
                <div className="space-y-3">
                  {paramSpec.map((paramName) => (
                    <div key={paramName}>
                      <label className="block text-xs text-slate-400 mb-1 capitalize">{paramName.replace(/_/g, " ")}</label>
                      {paramName === "script" || paramName === "body" || paramName === "template" ? (
                        <textarea
                          value={selectedNode.data.params?.[paramName] || ""}
                          onChange={(e) => updateNodeParam(selectedNode.id, paramName, e.target.value)}
                          rows={4}
                          className="w-full bg-slate-800 px-2 py-1.5 rounded text-xs font-mono outline-none focus:ring-2 focus:ring-blue-500"
                          data-testid={`rpa-param-${paramName}`}
                        />
                      ) : (
                        <input
                          value={selectedNode.data.params?.[paramName] || ""}
                          onChange={(e) => updateNodeParam(selectedNode.id, paramName, e.target.value)}
                          placeholder={paramHint(paramName)}
                          className="w-full bg-slate-800 px-2 py-1.5 rounded text-xs outline-none focus:ring-2 focus:ring-blue-500"
                          data-testid={`rpa-param-${paramName}`}
                        />
                      )}
                    </div>
                  ))}
                  {paramSpec.length === 0 && (
                    <div className="text-xs text-slate-500">This node has no parameters</div>
                  )}
                </div>

                {/* On error */}
                <div className="mt-4 pt-3 border-t border-slate-800">
                  <label className="block text-xs text-slate-400 mb-1">On Error</label>
                  <select
                    value={selectedNode.data.on_error || "skip"}
                    onChange={(e) => updateNodeOnError(selectedNode.id, e.target.value)}
                    className="w-full bg-slate-800 px-2 py-1.5 rounded text-xs outline-none focus:ring-2 focus:ring-blue-500"
                    data-testid="rpa-on-error-select"
                  >
                    <option value="skip">Skip — continue to next step</option>
                    <option value="stop">Stop — abort workflow</option>
                    <option value="retry">Retry (3 attempts)</option>
                  </select>
                </div>
              </div>
            ) : (
              <div className="p-6 text-center text-slate-500">
                <Layers className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <div className="text-sm">Select a node to configure</div>
              </div>
            )}

            {/* Settings drawer */}
            {showSettings && (
              <div className="border-t border-slate-800 p-4 bg-slate-950/50">
                <h4 className="text-xs font-semibold text-blue-400 mb-2">Workflow Settings</h4>
                <label className="block text-xs text-slate-400 mb-1">Headless</label>
                <select
                  value={workflow?.settings?.headless ?? true}
                  onChange={(e) => setWorkflow({ ...workflow, settings: { ...(workflow.settings || {}), headless: e.target.value === "true" } })}
                  className="w-full bg-slate-800 px-2 py-1.5 rounded text-xs mb-2"
                  data-testid="rpa-settings-headless"
                >
                  <option value="true">Headless (no visible window)</option>
                  <option value="false">Headed (visible browser)</option>
                </select>
                <label className="block text-xs text-slate-400 mb-1">Max runtime (sec)</label>
                <input
                  type="number"
                  value={workflow?.settings?.max_runtime_seconds ?? 3600}
                  onChange={(e) => setWorkflow({ ...workflow, settings: { ...(workflow.settings || {}), max_runtime_seconds: Number(e.target.value) } })}
                  className="w-full bg-slate-800 px-2 py-1.5 rounded text-xs"
                />
              </div>
            )}
          </div>
        </div>

        {/* Run panel (bottom overlay when running) */}
        {showRunPanel && (
          <div className="absolute bottom-0 left-64 right-80 max-h-96 border-t border-slate-700 bg-slate-950/95 backdrop-blur" data-testid="rpa-run-panel">
            <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
              <div className="flex items-center gap-3 text-sm">
                <Activity className={`w-4 h-4 ${running ? "text-emerald-400 animate-pulse" : "text-slate-400"}`} />
                <span className="font-semibold">Run: {runId?.slice(0, 16)}…</span>
                <span className={`px-2 py-0.5 rounded text-xs ${
                  runStatus === "completed" ? "bg-emerald-500/20 text-emerald-300" :
                  runStatus === "failed" ? "bg-red-500/20 text-red-300" :
                  runStatus === "running" ? "bg-blue-500/20 text-blue-300" :
                  "bg-slate-700 text-slate-400"
                }`}>{runStatus}</span>
              </div>
              <button onClick={() => setShowRunPanel(false)} className="p-1 hover:bg-slate-800 rounded">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex h-72">
              {/* Live preview */}
              <div className="w-1/2 border-r border-slate-800 p-2 overflow-hidden">
                <div className="text-xs text-slate-400 mb-1">Live Browser View</div>
                {livePreview ? (
                  <img
                    ref={liveImgRef}
                    src={livePreview}
                    alt="live"
                    className="w-full h-full object-contain rounded border border-slate-700"
                    data-testid="rpa-run-live-image"
                    onError={() => {}}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-600 text-sm">
                    No preview yet
                  </div>
                )}
              </div>
              {/* Event log */}
              <div className="w-1/2 overflow-y-auto p-2 text-xs font-mono">
                {runEvents.length === 0 && <div className="text-slate-500">No events yet</div>}
                {runEvents.map((ev, i) => (
                  <div
                    key={i}
                    className={`px-2 py-1 mb-0.5 rounded text-xs ${
                      ev.status === "ok" ? "bg-emerald-900/20 text-emerald-300" :
                      ev.status === "error" ? "bg-red-900/20 text-red-300" :
                      ev.status === "running" ? "bg-blue-900/20 text-blue-300" :
                      "bg-slate-800/50 text-slate-400"
                    }`}
                    data-testid={`rpa-run-event-${i}`}
                  >
                    <span className="opacity-60">[{ev.step || i + 1}]</span> {ev.type}
                    {ev.status === "error" && <span className="block text-red-400 mt-0.5">⚠ {ev.error}</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </ReactFlowProvider>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────
function paramHint(name) {
  const hints = {
    url: "https://example.com",
    selector: "#id  .class  input[name='x']",
    value: "{{var}} or literal",
    text: "Thank you",
    contains: "/success",
    times: "5",
    ms: "1000",
    timeout: "15000",
    pattern: ".*?(\\d+)",
    key: "save_to_var_name",
    save_to: "var_name",
    prompt: "Summarize this page",
    provider: "openai | anthropic | gemini",
    model: "gpt-4o-mini",
  };
  return hints[name] || "";
}

function deserializeNodes(nodesArr, catalog) {
  const typeMap = {};
  (catalog?.categories || []).forEach((cat) => {
    (cat.nodes || []).forEach((n) => {
      typeMap[n.type] = { label: n.label, color: cat.color };
    });
  });
  return nodesArr.map((n) => ({
    id: n.id,
    type: "rpa",
    position: n.position || { x: 100, y: 100 },
    data: {
      type: n.type,
      label: typeMap[n.type]?.label || n.type,
      color: typeMap[n.type]?.color || "#1e293b",
      params: n.params || {},
      on_error: n.on_error || "skip",
      body: n.body || [],
      branches: n.branches || {},
      summary: Object.values(n.params || {})[0] ? String(Object.values(n.params || {})[0]).slice(0, 30) : n.type,
    },
  }));
}

function deserializeEdges(edgesArr) {
  return edgesArr.map((e, i) => ({
    id: e.id || `e_${i}_${e.from}_${e.to}`,
    source: e.from || e.source,
    target: e.to || e.target,
    label: e.label,
    animated: true,
    style: { stroke: "#60a5fa", strokeWidth: 2 },
  }));
}

function serializeNode(node) {
  return {
    id: node.id,
    type: node.data.type,
    position: node.position,
    params: node.data.params || {},
    on_error: node.data.on_error || "skip",
    body: node.data.body || [],
    branches: node.data.branches || {},
  };
}
