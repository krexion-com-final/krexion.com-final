import { useEffect, useRef, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Camera,
  Play,
  Square,
  Trash2,
  Download,
  Copy,
  Hand,
  Type,
  Shuffle,
  Flag,
  Clock,
  ScrollText,
  ArrowLeft,
  Loader2,
  CheckCircle2,
  Sparkles,
  Globe,
  ListPlus,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import * as XLSX from "xlsx";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_URL = `${BACKEND_URL}`;

const authH = () => ({
  Authorization: `Bearer ${localStorage.getItem("token")}`,
  "Content-Type": "application/json",
});

const TOOLS = [
  { id: "default", icon: Hand, label: "Click", help: "Normal click — captures button/link text" },
  { id: "form_fill", icon: Type, label: "Form Fill", help: "Click an input, then bind to Excel column" },
  { id: "random", icon: Shuffle, label: "Random Pick", help: "Click 2+ buttons → random one each run" },
  { id: "final", icon: Flag, label: "Mark Final", help: "Capture this page as conversion target" },
];

export default function VisualRecorderPage() {
  const [setupStage, setSetupStage] = useState("setup"); // setup | recording | done
  const [url, setUrl] = useState("");
  const [proxy, setProxy] = useState("");
  const [ua, setUa] = useState("");
  const [headers, setHeaders] = useState([]);
  const [headersInput, setHeadersInput] = useState("");
  const [excelFile, setExcelFile] = useState(null);

  const [sessionId, setSessionId] = useState(null);
  const [sessionState, setSessionState] = useState("starting"); // starting | ready | error | stopped
  const [sessionError, setSessionError] = useState("");
  const [connectElapsed, setConnectElapsed] = useState(0);
  const [shotTick, setShotTick] = useState(0);   // bumps every poll → forces <img> reload via ?ts=
  const [shotErrorCount, setShotErrorCount] = useState(0);
  const [viewport, setViewport] = useState({ width: 412, height: 914 });
  const [steps, setSteps] = useState([]);
  const [pageMeta, setPageMeta] = useState({ url: "", title: "" });
  const [tool, setTool] = useState("default");
  const [pendingFormFill, setPendingFormFill] = useState(null); // {selector, header_name?}
  const [pendingRandom, setPendingRandom] = useState([]); // texts collected so far
  const [navUrl, setNavUrl] = useState("");
  const [waitMs, setWaitMs] = useState(2000);
  const [busy, setBusy] = useState(false);
  const [finalBundle, setFinalBundle] = useState(null);
  const [showHelp, setShowHelp] = useState(false);
  const imgRef = useRef(null);

  // ── Excel header parsing ──────────────────────────────────────────
  const onExcelUpload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setExcelFile(f);
    try {
      const buf = await f.arrayBuffer();
      const wb = XLSX.read(buf, { type: "array" });
      const ws = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: "" });
      const hdr = (rows[0] || []).filter((h) => String(h).trim()).map((h) => String(h).trim());
      setHeaders(hdr);
      setHeadersInput(hdr.join(", "));
      toast.success(`Detected ${hdr.length} columns: ${hdr.slice(0, 5).join(", ")}${hdr.length > 5 ? "…" : ""}`);
    } catch (err) {
      toast.error(`Excel parse failed: ${err.message}`);
    }
  };

  const applyManualHeaders = () => {
    const arr = headersInput
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    setHeaders(arr);
    if (arr.length) toast.success(`${arr.length} headers ready`);
  };

  // ── Recording session ─────────────────────────────────────────────
  const startRecording = async () => {
    if (!url.trim()) {
      toast.error("URL required");
      return;
    }
    setBusy(true);
    setSessionError("");
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/start`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({
          url: url.trim(),
          proxy: proxy.trim() || null,
          user_agent: ua.trim() || null,
          headers: headers,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      setSessionId(d.session_id);
      setViewport(d.viewport);
      setSessionState(d.state || "starting");
      setConnectElapsed(0);
      setSetupStage("recording");
      toast.success("Recording session created — connecting…");
    } catch (e) {
      toast.error(`Start failed: ${e.message || e}`);
    } finally {
      setBusy(false);
    }
  };

  const refreshState = useCallback(async () => {
    if (!sessionId) return;
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/state`, {
        headers: authH(),
      });
      if (!r.ok) return;
      const d = await r.json();
      setSteps(d.steps || []);
      setPageMeta(d.page || { url: "", title: "" });
      if (d.state) setSessionState(d.state);
      if (d.state === "error") setSessionError(d.error_message || "Unknown error");
      if (typeof d.elapsed_seconds === "number") setConnectElapsed(d.elapsed_seconds);
    } catch {}
  }, [sessionId]);

  const refreshScreenshot = useCallback(() => {
    if (!sessionId) return;
    // Just bump the tick → <img> re-fetches via cache-busting URL.
    setShotTick((t) => t + 1);
  }, [sessionId]);

  // Poll state always (covers connecting + recording).
  useEffect(() => {
    if (setupStage !== "recording" || !sessionId) return;
    refreshState();
    const t1 = setInterval(refreshState, 1000);
    return () => clearInterval(t1);
  }, [setupStage, sessionId, refreshState]);

  // Tick screenshot URL once per second when ready
  useEffect(() => {
    if (setupStage !== "recording" || !sessionId || sessionState !== "ready") return;
    setShotTick((x) => x + 1);
    const t = setInterval(() => setShotTick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [setupStage, sessionId, sessionState]);

  // Build the direct img src with ?t=<token>&ts=<tick> so the browser handles
  // load + retries natively (no blob URL plumbing — removes a class of races).
  const screenshotSrc = (sessionId && sessionState === "ready")
    ? `${API_URL}/api/visual-recorder/${sessionId}/screenshot?t=${encodeURIComponent(localStorage.getItem("token") || "")}&ts=${shotTick}`
    : "";

  // ── Click forwarding ──────────────────────────────────────────────
  const handleImgClick = async (e) => {
    if (busy || !imgRef.current || !sessionId) return;
    if (sessionState !== "ready") {
      toast.error("Session is still connecting");
      return;
    }

    const rect = imgRef.current.getBoundingClientRect();
    const scaleX = viewport.width / rect.width;
    const scaleY = viewport.height / rect.height;
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    if (tool === "final") {
      setBusy(true);
      try {
        const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/mark-final`, {
          method: "POST",
          headers: authH(),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        toast.success("Final page captured! Conversion target set.");
        setTool("default");
      } catch (err) {
        toast.error(`Mark final failed: ${err.message || err}`);
      } finally {
        setBusy(false);
      }
      return;
    }

    setBusy(true);
    try {
      const body = { x, y, mode: tool };
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/click`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);

      if (tool === "form_fill" && d.element) {
        setPendingFormFill({ selector: d.selector || "input", element: d.element });
      } else if (tool === "random" && d.element) {
        const txt = (d.element.text || "").trim();
        if (txt) {
          setPendingRandom((prev) => [...prev, txt]);
          toast.success(`Random pool: ${pendingRandom.length + 1} items — click "Build Random Step" when ready`);
        }
      } else if (tool === "default") {
        const txt = (d.element?.text || "").slice(0, 30);
        toast.success(txt ? `Click recorded: "${txt}"` : "Click recorded");
      }
      refreshState();
      refreshScreenshot();
    } catch (err) {
      toast.error(`Click failed: ${err.message || err}`);
    } finally {
      setBusy(false);
    }
  };

  // ── Form fill: complete the type after clicking an input ─────────
  const submitFormFill = async (headerName, plainValue) => {
    if (!pendingFormFill || !sessionId) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/type`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({
          selector: pendingFormFill.selector,
          value: plainValue || `{{${headerName}}}`,
          header_name: headerName || null,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      toast.success(headerName ? `Bound to {{${headerName}}}` : "Plain value set");
      setPendingFormFill(null);
      refreshState();
      refreshScreenshot();
    } catch (err) {
      toast.error(err.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  const buildRandomStep = async () => {
    if (pendingRandom.length < 2 || !sessionId) {
      toast.error("Need at least 2 elements in pool");
      return;
    }
    setBusy(true);
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/group-random`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ count: pendingRandom.length }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      toast.success(`Random step built: pick from ${d.items?.length || 0}`);
      setPendingRandom([]);
      refreshState();
    } catch (err) {
      toast.error(err.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  // ── Manual step shortcuts ─────────────────────────────────────────
  const addWait = async () => {
    if (!sessionId) return;
    setBusy(true);
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}/wait`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ ms: Number(waitMs) || 2000 }),
      });
      toast.success(`Wait ${waitMs}ms added`);
      refreshState();
    } finally {
      setBusy(false);
    }
  };

  const addWaitLoad = async () => {
    if (!sessionId) return;
    setBusy(true);
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}/wait-load`, {
        method: "POST",
        headers: authH(),
      });
      toast.success("Wait-for-load added");
      refreshState();
    } finally {
      setBusy(false);
    }
  };

  const addScroll = async (direction) => {
    if (!sessionId) return;
    setBusy(true);
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}/scroll`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ y: direction === "down" ? 600 : -600 }),
      });
      toast.success(`Scrolled ${direction}`);
      refreshState();
      refreshScreenshot();
    } finally {
      setBusy(false);
    }
  };

  const navigateTo = async () => {
    if (!sessionId || !navUrl.trim()) return;
    setBusy(true);
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}/navigate`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ url: navUrl.trim() }),
      });
      toast.success("Navigated");
      setNavUrl("");
      refreshState();
      refreshScreenshot();
    } finally {
      setBusy(false);
    }
  };

  const deleteStep = async (idx) => {
    if (!sessionId) return;
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}/step/${idx}`, {
        method: "DELETE",
        headers: authH(),
      });
      refreshState();
    } catch {}
  };

  // ── Finalize ──────────────────────────────────────────────────────
  const finalize = async () => {
    if (!sessionId) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/finalize`, {
        method: "POST",
        headers: authH(),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      setFinalBundle(d);
      setSetupStage("done");
      toast.success(`Recording complete — ${d.step_count} steps`);
    } catch (err) {
      toast.error(err.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  const stopAndDiscard = async () => {
    if (!sessionId) return;
    if (!window.confirm("Discard recording and stop session?")) return;
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}`, {
        method: "DELETE",
        headers: authH(),
      });
    } catch {}
    setSessionId(null);
    setSteps([]);
    setSetupStage("setup");
    setSessionState("starting");
    setSessionError("");
    setShotTick(0);
    toast.success("Session stopped");
  };

  const copyJson = () => {
    if (!finalBundle) return;
    const txt = JSON.stringify(finalBundle.automation_json, null, 2);
    navigator.clipboard.writeText(txt).then(() => toast.success("JSON copied to clipboard"));
  };

  const downloadJson = () => {
    if (!finalBundle) return;
    const txt = JSON.stringify(finalBundle.automation_json, null, 2);
    const blob = new Blob([txt], { type: "application/json" });
    const u = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = u;
    a.download = `automation_${finalBundle.session_id?.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(u);
  };

  const downloadTargetScreenshot = () => {
    if (!finalBundle?.target_screenshot_path) {
      toast.error("No final page was marked");
      return;
    }
    const a = document.createElement("a");
    a.href = `${API_URL}/api/visual-recorder/${finalBundle.session_id}/target-screenshot`;
    a.download = `target_${finalBundle.session_id?.slice(0, 8)}.png`;
    // Need auth for the GET — open with token via fetch+blob instead
    fetch(a.href, { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } })
      .then((r) => r.blob())
      .then((b) => {
        const u = URL.createObjectURL(b);
        a.href = u;
        a.click();
        URL.revokeObjectURL(u);
      });
  };

  // ── UI ────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" data-testid="visual-recorder-page">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <Link
              to="/real-user-traffic"
              className="p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200"
              data-testid="vr-back-btn"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-2xl font-semibold flex items-center gap-2">
                <Camera className="w-6 h-6 text-emerald-400" />
                Visual Recorder
              </h1>
              <p className="text-sm text-zinc-400">
                Click your way through any offer page → automatic JSON for RUT
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowHelp(!showHelp)}
            className="text-xs text-zinc-400 hover:text-emerald-400"
            data-testid="vr-help-toggle"
          >
            {showHelp ? "Hide help" : "Show help"}
          </button>
        </div>

        {showHelp && (
          <div className="mb-5 p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 text-sm text-zinc-300 space-y-2">
            <div className="flex items-center gap-2 font-medium text-emerald-400"><Sparkles className="w-4 h-4" /> Quick guide</div>
            <ol className="list-decimal list-inside space-y-1 text-zinc-400">
              <li>Enter the offer URL (and optionally proxy + UA + Excel headers)</li>
              <li>Click <b>Start Recording</b> — a real Chromium opens server-side and shows you live</li>
              <li>Use the toolbar: <b>Click</b> for normal buttons, <b>Form Fill</b> for inputs, <b>Random Pick</b> for surveys</li>
              <li>Need to scroll? Use scroll buttons. Need to wait? Use Wait shortcut.</li>
              <li>When you reach the conversion page, switch to <b>Mark Final</b> tool and click anywhere</li>
              <li>Hit <b>Finalize & Generate</b> — copy/download the JSON</li>
            </ol>
          </div>
        )}

        {/* SETUP stage */}
        {setupStage === "setup" && (
          <div className="grid md:grid-cols-2 gap-5">
            <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800">
              <h2 className="text-lg font-medium mb-3 flex items-center gap-2"><Globe className="w-5 h-5 text-emerald-400" />Target</h2>
              <label className="block text-sm font-medium text-zinc-300 mb-1">Offer URL <span className="text-rose-400">*</span></label>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://your-offer.com/landing"
                className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-100 placeholder-zinc-600 focus:border-emerald-500 focus:outline-none"
                data-testid="vr-url-input"
              />

              <label className="block text-sm font-medium text-zinc-300 mb-1 mt-3">Proxy <span className="text-zinc-500 font-normal">(optional)</span></label>
              <input
                type="text"
                value={proxy}
                onChange={(e) => setProxy(e.target.value)}
                placeholder="http://user:pass@host:port  or  host:port"
                className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-100 placeholder-zinc-600 focus:border-emerald-500 focus:outline-none"
                data-testid="vr-proxy-input"
              />

              <label className="block text-sm font-medium text-zinc-300 mb-1 mt-3">User Agent <span className="text-zinc-500 font-normal">(optional)</span></label>
              <input
                type="text"
                value={ua}
                onChange={(e) => setUa(e.target.value)}
                placeholder="Defaults to Pixel 7 mobile UA"
                className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-100 placeholder-zinc-600 focus:border-emerald-500 focus:outline-none text-xs"
                data-testid="vr-ua-input"
              />
            </div>

            <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800">
              <h2 className="text-lg font-medium mb-3 flex items-center gap-2"><ListPlus className="w-5 h-5 text-emerald-400" />Excel Headers <span className="text-xs text-zinc-500 font-normal">(for form fill)</span></h2>

              <p className="text-xs text-zinc-400 mb-3">Upload the same Excel you'll use in RUT — we'll detect column names so you can bind form inputs. <b>Or</b> type them manually below.</p>

              <label className="block text-sm font-medium text-zinc-300 mb-1">Upload Excel</label>
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                onChange={onExcelUpload}
                className="w-full text-sm text-zinc-300 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:bg-emerald-700/40 file:text-emerald-200 hover:file:bg-emerald-700/60"
                data-testid="vr-excel-input"
              />
              {excelFile && (
                <div className="mt-1 text-xs text-zinc-500">📄 {excelFile.name}</div>
              )}

              <label className="block text-sm font-medium text-zinc-300 mb-1 mt-3">Or type headers (comma-separated)</label>
              <input
                type="text"
                value={headersInput}
                onChange={(e) => setHeadersInput(e.target.value)}
                onBlur={applyManualHeaders}
                placeholder="first, last, email, phone, day, month, year"
                className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-100 placeholder-zinc-600 focus:border-emerald-500 focus:outline-none text-sm"
                data-testid="vr-headers-input"
              />
              {headers.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {headers.map((h) => (
                    <span key={h} className="px-2 py-0.5 rounded bg-emerald-700/30 border border-emerald-500/30 text-emerald-200 text-xs">
                      {h}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="md:col-span-2 flex justify-center">
              <button
                onClick={startRecording}
                disabled={busy || !url.trim()}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-medium text-base transition-colors"
                data-testid="vr-start-btn"
              >
                {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                Start Recording
              </button>
            </div>
          </div>
        )}

        {/* RECORDING stage */}
        {setupStage === "recording" && (
          <div className="grid lg:grid-cols-3 gap-4">
            {/* Live preview */}
            <div className="lg:col-span-2 p-3 rounded-xl bg-zinc-900/60 border border-zinc-800">
              <div className="flex items-center justify-between mb-2 px-1">
                <div className="flex items-center gap-2 text-xs text-zinc-400 truncate">
                  <Globe className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="truncate" title={pageMeta.url}>{pageMeta.url || "loading…"}</span>
                </div>
                <button onClick={refreshScreenshot} title="Refresh" className="p-1 text-zinc-400 hover:text-emerald-400">
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Live image */}
              <div className="relative bg-zinc-950 rounded-lg overflow-hidden flex justify-center">
                {sessionState === "error" ? (
                  <div className="aspect-[412/914] w-full flex flex-col items-center justify-center text-rose-300 text-sm gap-3 px-6 text-center" data-testid="vr-error-state">
                    <div className="text-2xl">⚠️</div>
                    <div className="font-medium text-rose-200">Connection failed</div>
                    <div className="text-xs text-zinc-400 max-w-xs leading-relaxed">{sessionError}</div>
                    <button
                      onClick={async () => {
                        // discard + go back to setup
                        try { await fetch(`${API_URL}/api/visual-recorder/${sessionId}`, { method: "DELETE", headers: authH() }); } catch {}
                        setSessionId(null);
                        setSessionState("starting");
                        setSessionError("");
                        setSetupStage("setup");
                      }}
                      className="mt-1 px-4 py-2 rounded-lg bg-rose-700 hover:bg-rose-600 text-white text-xs font-medium"
                      data-testid="vr-retry-btn"
                    >
                      Try Again
                    </button>
                  </div>
                ) : sessionState !== "ready" ? (
                  <div className="aspect-[412/914] w-full flex flex-col items-center justify-center text-zinc-400 text-sm gap-2" data-testid="vr-connecting-state">
                    <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
                    <div className="font-medium text-zinc-200">Connecting via {proxy ? "proxy" : "direct"}…</div>
                    <div className="text-xs text-zinc-500">{connectElapsed}s elapsed · timeout 45s</div>
                  </div>
                ) : screenshotSrc ? (
                  <img
                    ref={imgRef}
                    src={screenshotSrc}
                    alt="Live preview"
                    onClick={handleImgClick}
                    onLoad={() => setShotErrorCount(0)}
                    onError={() => setShotErrorCount((c) => c + 1)}
                    className={`max-w-full h-auto cursor-${tool === "form_fill" ? "text" : tool === "final" ? "crosshair" : "pointer"} select-none`}
                    style={{ aspectRatio: `${viewport.width}/${viewport.height}` }}
                    data-testid="vr-preview-img"
                  />
                ) : (
                  <div className="aspect-[412/914] w-full flex items-center justify-center text-zinc-500 text-sm">
                    <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading first frame…
                  </div>
                )}
                {busy && (
                  <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
                  </div>
                )}
              </div>

              {/* Toolbar */}
              <div className="mt-3 grid grid-cols-4 gap-2">
                {TOOLS.map((t) => {
                  const Ic = t.icon;
                  const active = tool === t.id;
                  return (
                    <button
                      key={t.id}
                      onClick={() => {
                        setTool(t.id);
                        if (t.id !== "random") setPendingRandom([]);
                      }}
                      title={t.help}
                      className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                        active
                          ? "bg-emerald-600 text-white"
                          : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                      }`}
                      data-testid={`vr-tool-${t.id}`}
                    >
                      <Ic className="w-4 h-4" />
                      {t.label}
                    </button>
                  );
                })}
              </div>

              {/* Sub-controls per mode */}
              {tool === "random" && pendingRandom.length > 0 && (
                <div className="mt-3 p-3 rounded-lg bg-amber-950/40 border border-amber-700/40">
                  <div className="text-xs text-amber-300 mb-2 font-medium">
                    Random pool ({pendingRandom.length}): click more to add, then "Build Random Step"
                  </div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {pendingRandom.map((t, i) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-zinc-900 text-amber-200 text-xs">{t.slice(0, 30)}</span>
                    ))}
                  </div>
                  <button
                    onClick={buildRandomStep}
                    disabled={pendingRandom.length < 2}
                    className="px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-xs font-medium"
                    data-testid="vr-build-random-btn"
                  >
                    Build Random Step ({pendingRandom.length})
                  </button>
                </div>
              )}

              {pendingFormFill && (
                <div className="mt-3 p-3 rounded-lg bg-blue-950/40 border border-blue-700/40">
                  <div className="text-xs text-blue-300 mb-2 font-medium">
                    Bind input <code className="text-zinc-300">{pendingFormFill.selector}</code> to:
                  </div>
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {headers.length === 0 && <span className="text-xs text-zinc-500">No Excel headers — use Plain value below</span>}
                    {headers.map((h) => (
                      <button
                        key={h}
                        onClick={() => submitFormFill(h, null)}
                        className="px-2 py-1 rounded bg-blue-600/40 hover:bg-blue-600 border border-blue-500/40 text-blue-100 text-xs"
                        data-testid={`vr-bind-${h}`}
                      >
                        {`{{${h}}}`}
                      </button>
                    ))}
                  </div>
                  <div className="flex gap-2 mt-2">
                    <input
                      type="text"
                      placeholder="Or plain value"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") submitFormFill(null, e.target.value);
                      }}
                      className="flex-1 px-2 py-1 rounded bg-zinc-950 border border-zinc-800 text-zinc-100 placeholder-zinc-600 text-xs"
                      data-testid="vr-plain-value-input"
                    />
                    <button
                      onClick={() => setPendingFormFill(null)}
                      className="px-2 py-1 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Auxiliary controls */}
              <div className="mt-3 flex flex-wrap gap-2">
                <button onClick={() => addScroll("down")} title="Scroll down" className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs">
                  <ScrollText className="w-3.5 h-3.5" /> Scroll ↓
                </button>
                <button onClick={() => addScroll("up")} title="Scroll up" className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs">
                  <ScrollText className="w-3.5 h-3.5 rotate-180" /> Scroll ↑
                </button>
                <button onClick={addWaitLoad} className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs">
                  <Clock className="w-3.5 h-3.5" /> Wait for Load
                </button>
                <div className="inline-flex items-center gap-1">
                  <input
                    type="number"
                    value={waitMs}
                    onChange={(e) => setWaitMs(e.target.value)}
                    className="w-16 px-1.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-100 text-xs"
                    data-testid="vr-wait-ms"
                  />
                  <button onClick={addWait} className="inline-flex items-center gap-1 px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs" data-testid="vr-add-wait">
                    + Wait ms
                  </button>
                </div>
                <div className="inline-flex items-center gap-1 flex-1 min-w-[200px]">
                  <input
                    type="text"
                    value={navUrl}
                    onChange={(e) => setNavUrl(e.target.value)}
                    placeholder="Navigate to URL"
                    className="flex-1 px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-100 placeholder-zinc-600 text-xs"
                    data-testid="vr-nav-input"
                  />
                  <button onClick={navigateTo} className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs" data-testid="vr-nav-go">
                    Go
                  </button>
                </div>
              </div>
            </div>

            {/* Steps panel */}
            <div className="lg:col-span-1 p-3 rounded-xl bg-zinc-900/60 border border-zinc-800 flex flex-col" style={{ maxHeight: "85vh" }}>
              <div className="flex items-center justify-between mb-2 px-1">
                <h3 className="text-sm font-medium flex items-center gap-1.5"><ScrollText className="w-4 h-4 text-emerald-400" />Recorded Steps ({steps.length})</h3>
              </div>

              <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
                {steps.length === 0 && (
                  <div className="text-zinc-600 text-xs text-center py-4">No steps yet — click on the preview to record</div>
                )}
                {steps.map((s, i) => (
                  <div key={i} className="flex items-start gap-2 p-2 rounded bg-zinc-950 border border-zinc-800 text-xs">
                    <span className="text-emerald-400 font-mono">#{i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-zinc-300 font-medium">{s.action}</div>
                      <div className="text-zinc-500 truncate">
                        {s.selector && <span>sel: <code className="text-zinc-400">{s.selector.slice(0, 28)}</code></span>}
                        {s.value && <span> → {String(s.value).slice(0, 30)}</span>}
                        {s.ms && <span>{s.ms}ms</span>}
                        {s.timeout && !s.ms && <span>tout: {s.timeout}</span>}
                        {s.script && <span title={s.script}>{s.script.slice(0, 50)}…</span>}
                      </div>
                    </div>
                    <button
                      onClick={() => deleteStep(i)}
                      title="Delete"
                      className="p-0.5 text-zinc-600 hover:text-rose-400"
                      data-testid={`vr-step-del-${i}`}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>

              {/* Action buttons */}
              <div className="mt-3 pt-3 border-t border-zinc-800 grid grid-cols-2 gap-2">
                <button
                  onClick={stopAndDiscard}
                  className="inline-flex items-center justify-center gap-1.5 py-2 rounded bg-zinc-800 hover:bg-rose-700 text-zinc-300 hover:text-white text-sm transition-colors"
                  data-testid="vr-discard-btn"
                >
                  <Square className="w-4 h-4" /> Discard
                </button>
                <button
                  onClick={finalize}
                  disabled={steps.length < 2 || busy}
                  className="inline-flex items-center justify-center gap-1.5 py-2 rounded bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-sm font-medium transition-colors"
                  data-testid="vr-finalize-btn"
                >
                  <CheckCircle2 className="w-4 h-4" /> Finalize
                </button>
              </div>
            </div>
          </div>
        )}

        {/* DONE stage */}
        {setupStage === "done" && finalBundle && (
          <div className="max-w-3xl mx-auto p-6 rounded-xl bg-zinc-900/60 border border-emerald-700/40">
            <div className="flex items-center gap-2 mb-4">
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
              <h2 className="text-xl font-semibold">Recording Complete!</h2>
            </div>
            <div className="grid sm:grid-cols-3 gap-3 mb-5">
              <div className="p-3 rounded bg-zinc-950 border border-zinc-800">
                <div className="text-xs text-zinc-500">Steps</div>
                <div className="text-2xl font-semibold text-emerald-400">{finalBundle.step_count}</div>
              </div>
              <div className="p-3 rounded bg-zinc-950 border border-zinc-800">
                <div className="text-xs text-zinc-500">Headers</div>
                <div className="text-2xl font-semibold text-emerald-400">{finalBundle.headers?.length || 0}</div>
              </div>
              <div className="p-3 rounded bg-zinc-950 border border-zinc-800">
                <div className="text-xs text-zinc-500">Final Page</div>
                <div className="text-2xl font-semibold text-emerald-400">{finalBundle.target_screenshot_path ? "✓" : "—"}</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              <button
                onClick={copyJson}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-700/40 hover:bg-emerald-700/60 border border-emerald-500/40 text-emerald-100 text-sm font-medium"
                data-testid="vr-copy-json-btn"
              >
                <Copy className="w-4 h-4" /> Copy JSON
              </button>
              <button
                onClick={downloadJson}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-700/40 hover:bg-emerald-700/60 border border-emerald-500/40 text-emerald-100 text-sm font-medium"
                data-testid="vr-download-json-btn"
              >
                <Download className="w-4 h-4" /> Download JSON
              </button>
              {finalBundle.target_screenshot_path && (
                <button
                  onClick={downloadTargetScreenshot}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-700/40 hover:bg-blue-700/60 border border-blue-500/40 text-blue-100 text-sm font-medium"
                  data-testid="vr-download-target-btn"
                >
                  <Download className="w-4 h-4" /> Download Final Screenshot
                </button>
              )}
            </div>

            <details className="mt-4">
              <summary className="cursor-pointer text-sm text-zinc-400 hover:text-zinc-200">Preview JSON</summary>
              <pre className="mt-2 p-3 rounded bg-zinc-950 border border-zinc-800 text-xs text-zinc-300 overflow-x-auto max-h-96">
                {JSON.stringify(finalBundle.automation_json, null, 2)}
              </pre>
            </details>

            <div className="mt-5 flex gap-3">
              <button
                onClick={() => {
                  setFinalBundle(null);
                  setSessionId(null);
                  setSteps([]);
                  setSetupStage("setup");
                  setUrl("");
                  setProxy("");
                  setUa("");
                }}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm"
                data-testid="vr-new-recording-btn"
              >
                <Play className="w-4 h-4" /> New Recording
              </button>
              <Link
                to="/real-user-traffic"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm"
              >
                <ArrowLeft className="w-4 h-4" /> Back to RUT
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
