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
  ArrowRight,
  Loader2,
  CheckCircle2,
  Sparkles,
  Globe,
  ListPlus,
  RefreshCw,
  Image as ImageIcon,
  ChevronDown,
  CheckSquare,
  Undo2,
  Keyboard,
  History,
  Smartphone,
  Tablet,
  Monitor,
  Save,
  Zap,
  AlertCircle,
  Activity,
} from "lucide-react";
import { toast } from "sonner";
import * as XLSX from "xlsx";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_URL = `${BACKEND_URL}`;

const authH = () => ({
  Authorization: `Bearer ${localStorage.getItem("token")}`,
  "Content-Type": "application/json",
});

// Keyboard-shortcut hint shown inside the tool buttons. Each tool gets
// a number key 1-8 matching its position in TOOLS.
const TOOLS = [
  { id: "default",   icon: Hand,        label: "Click",       key: "1", help: "Normal click — captures button/link text" },
  { id: "form_fill", icon: Type,        label: "Form Fill",   key: "2", help: "Click an input, then bind to Excel column" },
  { id: "dropdown",  icon: ChevronDown, label: "Dropdown",    key: "3", help: "Click a <select> dropdown to bind option / Excel column" },
  { id: "check",     icon: CheckSquare, label: "Check Box",   key: "4", help: "Click a checkbox (consent / agree / opt-in) — works on hidden CSS-styled boxes too" },
  { id: "random",    icon: Shuffle,     label: "Random Pick", key: "5", help: "Auto-detect buttons on page → tick the ones to randomise each run" },
  { id: "capture",   icon: ImageIcon,   label: "Capture",     key: "6", help: "Insert a screenshot marker — shown in Live Activity" },
  { id: "final",     icon: Flag,        label: "Mark Final",  key: "7", help: "Capture this page as conversion target" },
  { id: "nav_only",  icon: ArrowRight,  label: "Move",        key: "8", help: "Click without recording — use to navigate past a Random Pick step" },
];

// Device-viewport presets — applied at session start so the recording
// resembles the target audience's typical screen. The actual viewport
// is set server-side via the proxy/UA combo; this is a hint for the UI
// scaling + UA defaults.
const DEVICE_PRESETS = [
  { id: "mobile",  label: "Mobile",  icon: Smartphone, width: 412, height: 914,  hint: "Pixel-8 / iPhone-14 size" },
  { id: "tablet",  label: "Tablet",  icon: Tablet,     width: 820, height: 1180, hint: "iPad / Galaxy Tab"        },
  { id: "desktop", label: "Desktop", icon: Monitor,    width: 1280, height: 800, hint: "1280×800 laptop"          },
];

// localStorage keys for recent recordings + draft state
const LS_RECENT_KEY = "vr_recent_v1";
const LS_DRAFT_KEY = "vr_draft_v1";

// Tiny JSON colorizer — safe (escapes HTML, only adds <span class>)
function colorizeJson(obj) {
  const json = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  // Escape HTML
  const esc = json.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = "text-amber-300"; // numbers
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? "text-sky-300" : "text-emerald-300";
      } else if (/true|false/.test(match)) {
        cls = "text-fuchsia-300";
      } else if (/null/.test(match)) {
        cls = "text-zinc-500";
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}

export default function VisualRecorderPage() {
  const [setupStage, setSetupStage] = useState("setup"); // setup | recording | done
  const [url, setUrl] = useState("");
  const [proxy, setProxy] = useState("");
  const [ua, setUa] = useState("");
  const [headers, setHeaders] = useState([]);
  const [headersInput, setHeadersInput] = useState("");
  const [excelFile, setExcelFile] = useState(null);
  // 2026-05: first data row → auto-fill form inputs during recording
  // so the user can submit forms and continue recording on the
  // post-submit page. Empty {} means no sample data yet.
  const [sampleRow, setSampleRow] = useState({});

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
  const [pendingDropdown, setPendingDropdown] = useState(null); // {selector, options:[{value,label,...}], element}
  const [pendingRandom, setPendingRandom] = useState([]); // texts collected so far (legacy click-to-pool flow)
  // 2026-01: NEW Random Pick checklist flow
  //   detectedClickables: full list returned by /detect-clickables (one per page)
  //   selectedRandomKeys: Set of indices the user has ticked from that list
  //   detectingClickables: spinner flag while the call is in flight
  const [detectedClickables, setDetectedClickables] = useState([]);
  const [selectedRandomKeys, setSelectedRandomKeys] = useState(() => new Set());
  const [detectingClickables, setDetectingClickables] = useState(false);
  const [navUrl, setNavUrl] = useState("");
  const [waitMs, setWaitMs] = useState(2000);
  const [busy, setBusy] = useState(false);
  const [finalBundle, setFinalBundle] = useState(null);
  const [showHelp, setShowHelp] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [recentRecordings, setRecentRecordings] = useState([]);
  const [devicePreset, setDevicePreset] = useState("mobile");
  const [pjAvailable, setPjAvailable] = useState(false);
  const [pjCountry, setPjCountry] = useState("US");
  const [saving, setSaving] = useState(false);
  const [savedToLibraryId, setSavedToLibraryId] = useState(null);
  const imgRef = useRef(null);
  const sessionStartedAt = useRef(null);
  const [recordingElapsed, setRecordingElapsed] = useState(0);

  // ── Recent recordings (localStorage) ───────────────────────────────
  useEffect(() => {
    try {
      const raw = localStorage.getItem(LS_RECENT_KEY);
      if (raw) setRecentRecordings(JSON.parse(raw));
    } catch {}
  }, []);

  const pushRecent = (item) => {
    try {
      const next = [item, ...recentRecordings.filter((r) => r.url !== item.url)].slice(0, 5);
      setRecentRecordings(next);
      localStorage.setItem(LS_RECENT_KEY, JSON.stringify(next));
    } catch {}
  };

  // ── ProxyJet availability check ────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_URL}/api/proxyjet/credentials`, { headers: authH() });
        if (r.ok) {
          const d = await r.json();
          setPjAvailable(!!d.configured);
          if (d.default_country) setPjCountry(d.default_country);
        }
      } catch {}
    })();
  }, []);

  // ── Live recording-elapsed counter ─────────────────────────────────
  useEffect(() => {
    if (setupStage !== "recording" || sessionState !== "ready") {
      sessionStartedAt.current = null;
      setRecordingElapsed(0);
      return;
    }
    if (!sessionStartedAt.current) sessionStartedAt.current = Date.now();
    const t = setInterval(() => {
      if (sessionStartedAt.current) {
        setRecordingElapsed(Math.floor((Date.now() - sessionStartedAt.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(t);
  }, [setupStage, sessionState]);

  // Fetch ONE fresh ProxyJet proxy via the existing generate-batch API.
  // Lets the user populate the proxy field with a single click on setup.
  const useProxyJetProxy = async () => {
    if (!pjAvailable) {
      toast.error("Save ProxyJet credentials first (Proxies page → ProxyJet Auto)");
      return;
    }
    setBusy(true);
    try {
      const r = await fetch(`${API_URL}/api/proxyjet/generate-batch`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ count: 1, country: pjCountry }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      if (d.proxies?.[0]) {
        setProxy(d.proxies[0]);
        toast.success(`Fresh ${pjCountry} residential proxy loaded`);
      } else {
        toast.error("No proxy returned");
      }
    } catch (e) {
      toast.error(e.message || "ProxyJet fetch failed");
    } finally {
      setBusy(false);
    }
  };

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
      // 2026-05: Build sample_row from the FIRST data row (row 2 of the
      // spreadsheet). This row is used to auto-fill form inputs during
      // recording so the user can submit forms and continue recording
      // on the next page.
      const first = rows[1] || [];
      const sample = {};
      hdr.forEach((h, i) => {
        const v = first[i];
        if (v !== undefined && v !== null && String(v).trim() !== "") {
          sample[h] = v;
        }
      });
      setSampleRow(sample);
      const sampleCount = Object.keys(sample).length;
      toast.success(
        `Detected ${hdr.length} columns: ${hdr.slice(0, 5).join(", ")}${hdr.length > 5 ? "…" : ""}` +
        (sampleCount > 0 ? ` · using ${sampleCount} sample values for live form-fill` : "")
      );
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
          // 2026-05: pass first data row so form inputs auto-fill
          // during recording (lets the user submit forms and continue
          // recording on the post-submit page)
          sample_row: Object.keys(sampleRow || {}).length ? sampleRow : null,
        }),
      });
      const d = await r.json();
      if (!r.ok) {
        // FastAPI can return detail as string, object, or array of validation errors.
        // Normalise so the toast never shows "[object Object]".
        let detailMsg = "";
        if (typeof d.detail === "string") {
          detailMsg = d.detail;
        } else if (Array.isArray(d.detail)) {
          detailMsg = d.detail
            .map((it) => (it && (it.msg || it.message)) ? `${it.msg || it.message}${it.loc ? ` (${it.loc.join('.')})` : ''}` : JSON.stringify(it))
            .join("; ");
        } else if (d.detail && typeof d.detail === "object") {
          detailMsg = d.detail.msg || d.detail.message || JSON.stringify(d.detail);
        }
        throw new Error(detailMsg || `HTTP ${r.status}`);
      }
      setSessionId(d.session_id);
      setViewport(d.viewport);
      setSessionState(d.state || "starting");
      setConnectElapsed(0);
      setSetupStage("recording");
      toast.success("Recording session created — connecting…");
      // Save to recent recordings (localStorage) for one-click re-use
      pushRecent({
        url: url.trim(),
        proxy: proxy.trim() || null,
        ua: ua.trim() || null,
        headers,
        device: devicePreset,
        ts: Date.now(),
      });
    } catch (e) {
      let msg = e && e.message ? e.message : "";
      if (!msg || msg === "[object Object]") {
        try { msg = typeof e === "string" ? e : JSON.stringify(e); } catch { msg = String(e); }
      }
      toast.error(`Start failed: ${msg}`);
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

  // ── Keyboard shortcuts ─────────────────────────────────────────────
  // 1-8  → switch tool
  // Esc  → cancel any pending binding (form-fill / dropdown / random)
  // Ctrl/Cmd+Z → undo last step
  // Ctrl/Cmd+Enter → finalize (if ≥ 2 steps)
  // Ignored when focus is in an <input>/<textarea>/contenteditable so
  // typing inside the URL / Excel / wait-ms fields is never hijacked.
  useEffect(() => {
    if (setupStage !== "recording") return;
    const onKey = (e) => {
      const target = e.target;
      const tag = (target?.tagName || "").toUpperCase();
      const editable =
        tag === "INPUT" || tag === "TEXTAREA" || target?.isContentEditable;
      const ctrl = e.ctrlKey || e.metaKey;

      // Ctrl+Z anywhere (except editable fields) — undo last step
      if (!editable && ctrl && e.key.toLowerCase() === "z") {
        e.preventDefault();
        undoLastStep();
        return;
      }
      // Ctrl+Enter — finalize
      if (!editable && ctrl && e.key === "Enter") {
        e.preventDefault();
        if (steps.length >= 2 && !busy) finalize();
        return;
      }
      // Esc — cancel pending bindings
      if (e.key === "Escape") {
        if (pendingFormFill) { setPendingFormFill(null); e.preventDefault(); return; }
        if (pendingDropdown) { setPendingDropdown(null); e.preventDefault(); return; }
        if (pendingRandom.length) { setPendingRandom([]); e.preventDefault(); return; }
        if (detectedClickables.length || selectedRandomKeys.size) {
          setDetectedClickables([]);
          setSelectedRandomKeys(new Set());
          e.preventDefault();
          return;
        }
      }
      // 1-8 — switch tool (only when nothing has focus)
      if (!editable && !ctrl && /^[1-8]$/.test(e.key)) {
        const t = TOOLS[Number(e.key) - 1];
        if (t) {
          setTool(t.id);
          if (t.id !== "random") {
            setPendingRandom([]);
            setDetectedClickables([]);
            setSelectedRandomKeys(new Set());
          } else {
            // Re-trigger auto-detect when switching via keyboard
            detectClickables();
          }
          e.preventDefault();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setupStage, steps.length, busy, pendingFormFill, pendingDropdown, pendingRandom]);

  // Format the live recording timer as mm:ss
  const fmtTimer = (sec) => {
    const m = Math.floor(sec / 60).toString().padStart(2, "0");
    const s = (sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

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

    // 2026-01: "nav_only" tool — click happens on the live page but
    // NO step is recorded. Used to advance the browser past a Random
    // Pick step (the random step already contains its own click JS;
    // we just need the live preview to move to the next page so the
    // user can record subsequent steps).
    if (tool === "nav_only") {
      setBusy(true);
      try {
        const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/nav-click`, {
          method: "POST",
          headers: authH(),
          body: JSON.stringify({ x, y }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        toast.success("Navigated — no step recorded ✓");
        refreshScreenshot();
      } catch (err) {
        toast.error(`Nav click failed: ${err.message || err}`);
      } finally {
        setBusy(false);
      }
      return;
    }

    // "capture" tool: insert a screenshot marker — no need to click
    // anywhere on the page, but if the user does, we still treat it
    // as a request to insert at current position.
    if (tool === "capture") {
      setBusy(true);
      try {
        const name = window.prompt(
          "Name this capture (shown in Live Activity):",
          `Step ${steps.length + 1}`,
        );
        if (name === null) { setBusy(false); return; }   // user cancelled
        const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/screenshot-marker`, {
          method: "POST",
          headers: authH(),
          body: JSON.stringify({ name: name || `Step ${steps.length + 1}` }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        toast.success(`📷 Capture point inserted: "${d.step?.name || "Step"}"`);
        refreshState();
      } catch (err) {
        toast.error(`Insert capture failed: ${err.message || err}`);
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
      } else if (tool === "dropdown") {
        // The backend returned the <select> element's options. Open
        // the binding panel so the user picks one option literal OR
        // an Excel column to substitute at run-time.
        if (d.warning) {
          toast.error(d.warning);
        } else if (!Array.isArray(d.options) || d.options.length === 0) {
          toast.error("No <select> options found at that point — click the dropdown control itself.");
        } else {
          setPendingDropdown({
            selector: d.selector || "select",
            options: d.options,
            element: d.element,
            wrapper_kind: d.wrapper_kind || "",
            is_hidden_select: !!d.is_hidden_select,
          });
          if (d.wrapper_kind) {
            toast.success(
              d.is_hidden_select
                ? `Hidden <select> behind ${d.wrapper_kind} detected — replay will be faster.`
                : `Custom dropdown UI detected: ${d.wrapper_kind}`
            );
          }
        }
      } else if (tool === "random" && d.element) {
        const txt = (d.element.text || "").trim();
        if (txt) {
          setPendingRandom((prev) => [...prev, txt]);
          toast.success(`Random pool: ${pendingRandom.length + 1} items — click "Build Random Step" when ready`);
        }
      } else if (tool === "check" && d.element) {
        // 2026-05: dedicated checkbox tool. Backend records a
        // {"action":"check"} step that the RUT engine routes through
        // _smart_check_with_fallback (handles CSS-styled hidden boxes).
        const tag = (d.element.tag || "").toLowerCase();
        const txt = (d.element.text || "").slice(0, 40);
        if (d.warning) {
          toast.error(d.warning);
        } else if (tag !== "input" || (d.element.type || "").toLowerCase() !== "checkbox") {
          toast.error("That isn't a checkbox — click directly on the box (or its label/border).");
        } else {
          toast.success(txt ? `☑ Checkbox recorded: "${txt}"` : "☑ Checkbox step recorded");
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

  // ── Dropdown bind: complete the select after picking the dropdown ─
  const submitDropdownBind = async (opts) => {
    // opts: { value?: string, header_name?: string, match_by?: 'label'|'value' }
    if (!pendingDropdown || !sessionId) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/dropdown-bind`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({
          selector: pendingDropdown.selector,
          value: opts.value || null,
          header_name: opts.header_name || null,
          match_by: opts.match_by || "label",
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      toast.success(
        opts.header_name
          ? `Dropdown bound to {{${opts.header_name}}}`
          : `Dropdown will select "${opts.value}"`,
      );
      setPendingDropdown(null);
      refreshState();
    } catch (err) {
      toast.error(err.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  // ── Form fill: complete the type after clicking an input ─────────
  const submitFormFill = async (headerName, plainValue) => {
    if (!pendingFormFill || !sessionId) return;
    setBusy(true);
    try {
      // ── 2026-05 fix ──
      // When binding to a header (no plain value), send `value=""` and
      // let the backend resolve the sample value via `sample_row[header]`.
      // Previously we sent `{{first}}` literally which got typed into the
      // live form input (visible as `{{first}}` text in the field) — the
      // form then failed validation and the user couldn't proceed.
      const sendValue = plainValue || "";
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/type`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({
          selector: pendingFormFill.selector,
          value: sendValue,
          header_name: headerName || null,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      const filled = d.filled_sample;
      toast.success(
        headerName
          ? `Bound to {{${headerName}}}${filled ? ` · live page filled with "${filled}"` : ""}`
          : "Plain value set"
      );
      if (d.sample_hint) toast(d.sample_hint, { icon: "ℹ️" });
      setPendingFormFill(null);
      refreshState();
      refreshScreenshot();
    } catch (err) {
      toast.error(err.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  // ── 2026-01 NEW: Detect all clickable elements on the current page ─
  // Called automatically when user selects the "Random Pick" tool.
  // The user then ticks which ones go in the random pool (no need to
  // click each one on the live page → no premature navigation).
  const detectClickables = async () => {
    if (!sessionId) return;
    setDetectingClickables(true);
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/detect-clickables`, {
        method: "GET",
        headers: authH(),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      const items = Array.isArray(d.items) ? d.items : [];
      setDetectedClickables(items);
      setSelectedRandomKeys(new Set());
      if (items.length === 0) {
        toast.error("No clickable elements detected on this page.");
      } else {
        toast.success(`Detected ${items.length} clickable element${items.length === 1 ? "" : "s"} — tick the ones for the random pool.`);
      }
    } catch (err) {
      toast.error(`Detect failed: ${err.message || err}`);
    } finally {
      setDetectingClickables(false);
    }
  };

  const buildRandomStep = async () => {
    // Two paths: NEW checklist flow (selectedRandomKeys) or legacy
    // click-to-pool flow (pendingRandom). Prefer checklist if any
    // boxes are ticked.
    const checklistTexts = Array.from(selectedRandomKeys)
      .map((idx) => detectedClickables[idx])
      .filter(Boolean)
      .map((el) => (el.text || "").trim())
      .filter(Boolean);

    const useChecklist = checklistTexts.length >= 2;
    const useLegacy = !useChecklist && pendingRandom.length >= 2;

    if (!useChecklist && !useLegacy) {
      toast.error("Need at least 2 items in the random pool");
      return;
    }
    if (!sessionId) return;
    setBusy(true);
    try {
      const body = useChecklist
        ? { count: checklistTexts.length, texts: checklistTexts }
        : { count: pendingRandom.length };
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/group-random`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      toast.success(`Random step built: pick from ${d.items?.length || 0}`);
      setPendingRandom([]);
      setSelectedRandomKeys(new Set());
      setDetectedClickables([]);
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

  // Send keyboard key to live session + auto-record as a step
  const pressKey = async (key) => {
    if (!sessionId || sessionState !== "ready") return;
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/press-key`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ key }),
      });
      const d = await r.json();
      if (!r.ok || !d.recorded) {
        toast.error(d.error || d.detail || "Press key failed");
        return;
      }
      toast.success(`Pressed ${key}`);
      refreshState();
    } catch (e) {
      toast.error(e.message || "Press key failed");
    }
  };

  // Wait for a CSS selector (recorded as step too)
  const waitForSelectorAction = async () => {
    const sel = window.prompt("CSS selector to wait for (e.g. 'button.cta' or '#thank-you-msg'):", "");
    if (!sel) return;
    const t = window.prompt("Max wait time in ms (default 15000):", "15000");
    if (!sessionId) return;
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/wait-for-selector`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ selector: sel.trim(), timeout_ms: Math.max(500, Number(t) || 15000) }),
      });
      const d = await r.json();
      if (!r.ok || !d.recorded) {
        toast.error(d.error || d.detail || "Wait failed");
        return;
      }
      toast.success("Selector appeared — recorded");
      refreshState();
    } catch (e) {
      toast.error(e.message || "Wait failed");
    }
  };

  // Move step up or down
  const moveStep = async (idx, direction) => {
    if (!sessionId) return;
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}/step/${idx}/move`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ direction }),
      });
      refreshState();
    } catch {}
  };

  // Duplicate step
  const duplicateStep = async (idx) => {
    if (!sessionId) return;
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}/step/${idx}/duplicate`, {
        method: "POST",
        headers: authH(),
      });
      refreshState();
      toast.success("Step duplicated");
    } catch {}
  };

  // Rename step (inline edit)
  const renameStep = async (idx, name) => {
    if (!sessionId) return;
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}/step/${idx}/rename`, {
        method: "PATCH",
        headers: authH(),
        body: JSON.stringify({ name }),
      });
      refreshState();
    } catch {}
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

  // Undo = delete the most recently added step. Visible only when there
  // is at least one step. Maps to Ctrl/Cmd+Z keyboard shortcut.
  const undoLastStep = async () => {
    if (!sessionId || steps.length === 0) return;
    await deleteStep(steps.length - 1);
    toast.success("Undid last step");
  };

  // Load a recent recording from localStorage into the setup form.
  const loadRecent = (r) => {
    setUrl(r.url || "");
    setProxy(r.proxy || "");
    setUa(r.ua || "");
    setHeaders(r.headers || []);
    setHeadersInput((r.headers || []).join(", "));
    if (r.device) setDevicePreset(r.device);
    toast.success("Recent recording loaded — review and Start");
  };

  const clearRecent = () => {
    if (!window.confirm("Clear all recent recordings?")) return;
    setRecentRecordings([]);
    try { localStorage.removeItem(LS_RECENT_KEY); } catch {}
  };

  // Save the finalized automation JSON into the user's Uploaded Things
  // library so they can pick it from a dropdown in the RUT page on every
  // future job without copy-pasting.
  const saveToLibrary = async () => {
    if (!finalBundle) return;
    const defaultName = `Recording-${new Date().toISOString().slice(0, 16).replace("T", " ")}`;
    const name = window.prompt("Save as template — name?", defaultName);
    if (!name) return;
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("name", name);
      fd.append("automation_json", JSON.stringify(finalBundle.automation_json));
      fd.append("description", `Recorded on ${new Date().toLocaleString()} · ${finalBundle.step_count} steps`);
      const r = await fetch(`${API_URL}/api/uploads/automation-json`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
        body: fd,
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      setSavedToLibraryId(d.id);
      toast.success(`Saved to library as "${name}"`);
    } catch (e) {
      toast.error(`Save failed: ${e.message || e}`);
    } finally {
      setSaving(false);
    }
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
    <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-950 to-black text-zinc-100" data-testid="visual-recorder-page">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {/* ─── Header (pro-grade, with live session badge) ─── */}
        <div className="flex flex-wrap items-center justify-between mb-5 gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <Link
              to="/real-user-traffic"
              className="p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
              data-testid="vr-back-btn"
              title="Back to Real-User-Traffic"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold flex items-center gap-2">
                <span className="relative inline-flex">
                  <Camera className="w-6 h-6 text-emerald-400" />
                  {setupStage === "recording" && sessionState === "ready" && (
                    <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                  )}
                </span>
                Visual Recorder
                <span className="text-[10px] font-normal text-zinc-500 ml-1 hidden sm:inline">PRO</span>
              </h1>
              <p className="text-sm text-zinc-400 truncate">
                Click your way through any offer page → automatic JSON for RUT
              </p>
            </div>
          </div>

          {/* Right-side cluster — live stats during recording */}
          <div className="flex items-center gap-2 flex-wrap">
            {setupStage === "recording" && (
              <>
                <div
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${
                    sessionState === "ready"
                      ? "bg-emerald-950/50 border-emerald-700/40 text-emerald-300"
                      : sessionState === "error"
                      ? "bg-rose-950/50 border-rose-700/40 text-rose-300"
                      : "bg-amber-950/50 border-amber-700/40 text-amber-300"
                  }`}
                  data-testid="vr-session-badge"
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      sessionState === "ready"
                        ? "bg-emerald-400 animate-pulse"
                        : sessionState === "error"
                        ? "bg-rose-400"
                        : "bg-amber-400 animate-pulse"
                    }`}
                  />
                  {sessionState === "ready" ? "REC" : sessionState === "error" ? "ERROR" : "CONNECTING"}
                </div>
                {sessionState === "ready" && (
                  <div
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono bg-zinc-900 border border-zinc-800 text-zinc-300"
                    data-testid="vr-elapsed-timer"
                    title="Recording elapsed time"
                  >
                    <Clock className="w-3 h-3 text-emerald-400" />
                    {fmtTimer(recordingElapsed)}
                  </div>
                )}
                <div
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-950/40 border border-indigo-700/40 text-indigo-300"
                  data-testid="vr-step-counter"
                  title="Steps recorded so far"
                >
                  <Activity className="w-3 h-3" />
                  {steps.length} step{steps.length === 1 ? "" : "s"}
                </div>
              </>
            )}
            <button
              onClick={() => setShowShortcuts((v) => !v)}
              className="p-1.5 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-emerald-400"
              data-testid="vr-shortcuts-toggle"
              title="Keyboard shortcuts"
            >
              <Keyboard className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowHelp(!showHelp)}
              className="text-xs px-2 py-1 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-emerald-400"
              data-testid="vr-help-toggle"
            >
              {showHelp ? "Hide help" : "Help"}
            </button>
          </div>
        </div>

        {/* Keyboard-shortcut cheat sheet (toggle) */}
        {showShortcuts && (
          <div
            className="mb-5 p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 text-sm"
            data-testid="vr-shortcuts-panel"
          >
            <div className="flex items-center gap-2 font-medium text-emerald-400 mb-3">
              <Keyboard className="w-4 h-4" /> Keyboard Shortcuts
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs text-zinc-300">
              {TOOLS.map((t) => (
                <div key={t.id} className="flex items-center gap-2">
                  <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-200 font-mono">{t.key}</kbd>
                  <span className="text-zinc-400">→ {t.label}</span>
                </div>
              ))}
              <div className="flex items-center gap-2">
                <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-200 font-mono">Esc</kbd>
                <span className="text-zinc-400">→ Cancel pending</span>
              </div>
              <div className="flex items-center gap-2">
                <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-200 font-mono">Ctrl+Z</kbd>
                <span className="text-zinc-400">→ Undo last step</span>
              </div>
              <div className="flex items-center gap-2">
                <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-200 font-mono">Ctrl+Enter</kbd>
                <span className="text-zinc-400">→ Finalize</span>
              </div>
            </div>
          </div>
        )}

        {showHelp && (
          <div className="mb-5 p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 text-sm text-zinc-300 space-y-2">
            <div className="flex items-center gap-2 font-medium text-emerald-400"><Sparkles className="w-4 h-4" /> Quick guide</div>
            <ol className="list-decimal list-inside space-y-1 text-zinc-400">
              <li>Enter the offer URL (and optionally proxy + UA + Excel headers)</li>
              <li>Click <b>Start Recording</b> — a real Chromium opens server-side and shows you live</li>
              <li>Use the toolbar: <b>Click</b> for buttons, <b>Form Fill</b> for inputs, <b>Dropdown</b> for &lt;select&gt;, <b>Check Box</b> for consent/agree, <b>Random Pick</b> for surveys</li>
              <li>Need to scroll? Use scroll buttons. Need to wait? Use Wait shortcut.</li>
              <li>When you reach the conversion page, switch to <b>Mark Final</b> tool and click anywhere</li>
              <li>Hit <b>Finalize & Generate</b> — copy/download the JSON</li>
            </ol>
          </div>
        )}

        {/* SETUP stage */}
        {setupStage === "setup" && (
          <div className="space-y-5">
            {/* Recent recordings — quick re-use (last 5) */}
            {recentRecordings.length > 0 && (
              <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800" data-testid="vr-recent-panel">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
                    <History className="w-4 h-4 text-emerald-400" /> Recent recordings
                  </div>
                  <button
                    onClick={clearRecent}
                    className="text-[11px] text-zinc-500 hover:text-rose-400"
                    data-testid="vr-clear-recent"
                  >
                    clear
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {recentRecordings.map((r, i) => (
                    <button
                      key={i}
                      onClick={() => loadRecent(r)}
                      className="text-xs px-2.5 py-1 rounded-md bg-zinc-800/80 hover:bg-emerald-700/40 border border-zinc-700 hover:border-emerald-500/40 text-zinc-300 hover:text-emerald-200 max-w-[280px] truncate transition-colors"
                      title={r.url}
                      data-testid={`vr-recent-${i}`}
                    >
                      <Globe className="w-3 h-3 inline mr-1" />
                      {(() => {
                        try { return new URL(r.url).hostname; } catch { return r.url.slice(0, 40); }
                      })()}
                      <span className="text-[10px] text-zinc-500 ml-1">· {r.device || "mobile"}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="grid md:grid-cols-2 gap-5">
              <div className="p-5 rounded-xl bg-zinc-900/60 border border-zinc-800">
                <h2 className="text-lg font-medium mb-3 flex items-center gap-2"><Globe className="w-5 h-5 text-emerald-400" />Target</h2>
                <label className="block text-sm font-medium text-zinc-300 mb-1">Offer URL <span className="text-rose-400">*</span></label>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://your-offer.com/landing"
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-100 placeholder-zinc-600 focus:border-emerald-500 focus:outline-none transition-colors"
                  data-testid="vr-url-input"
                />

                {/* Device preset selector */}
                <label className="block text-sm font-medium text-zinc-300 mb-1 mt-3">Device preset</label>
                <div className="grid grid-cols-3 gap-2" data-testid="vr-device-presets">
                  {DEVICE_PRESETS.map((d) => {
                    const Ic = d.icon;
                    const active = devicePreset === d.id;
                    return (
                      <button
                        key={d.id}
                        onClick={() => setDevicePreset(d.id)}
                        className={`flex flex-col items-center justify-center gap-1 py-2.5 rounded-lg border text-xs font-medium transition-colors ${
                          active
                            ? "bg-emerald-600 text-white border-emerald-500"
                            : "bg-zinc-950 hover:bg-zinc-800 border-zinc-800 text-zinc-300"
                        }`}
                        title={d.hint}
                        data-testid={`vr-device-${d.id}`}
                      >
                        <Ic className="w-4 h-4" />
                        {d.label}
                        <span className="text-[9px] opacity-70">{d.width}×{d.height}</span>
                      </button>
                    );
                  })}
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <label className="block text-sm font-medium text-zinc-300 mb-1">
                    Proxy <span className="text-zinc-500 font-normal">(optional)</span>
                  </label>
                  {pjAvailable && (
                    <button
                      onClick={useProxyJetProxy}
                      disabled={busy}
                      className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-indigo-600/30 hover:bg-indigo-600/60 border border-indigo-500/40 text-indigo-200 disabled:opacity-50"
                      data-testid="vr-use-pj-proxy"
                      title="Fetch a fresh unique ProxyJet residential proxy"
                    >
                      <Zap className="w-3 h-3" /> ProxyJet
                    </button>
                  )}
                </div>
                <input
                  type="text"
                  value={proxy}
                  onChange={(e) => setProxy(e.target.value)}
                  placeholder="http://user:pass@host:port  or  host:port"
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-100 placeholder-zinc-600 focus:border-emerald-500 focus:outline-none font-mono text-xs transition-colors"
                  data-testid="vr-proxy-input"
                />
                {!pjAvailable && (
                  <p className="text-[10px] text-zinc-500 mt-1">
                    Tip: save ProxyJet credentials on the Proxies page for one-click fresh proxies here.
                  </p>
                )}

                <label className="block text-sm font-medium text-zinc-300 mb-1 mt-3">User Agent <span className="text-zinc-500 font-normal">(optional)</span></label>
                <input
                  type="text"
                  value={ua}
                  onChange={(e) => setUa(e.target.value)}
                  placeholder={devicePreset === "desktop" ? "Defaults to Chrome desktop UA" : devicePreset === "tablet" ? "Defaults to iPad UA" : "Defaults to Pixel 7 mobile UA"}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-100 placeholder-zinc-600 focus:border-emerald-500 focus:outline-none text-xs transition-colors"
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
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-medium text-base transition-colors shadow-lg shadow-emerald-900/30"
                data-testid="vr-start-btn"
              >
                {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                Start Recording
              </button>
            </div>
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
                    <AlertCircle className="w-12 h-12 text-rose-400" />
                    <div className="font-medium text-rose-200">Connection failed</div>
                    <div className="text-xs text-zinc-400 max-w-xs leading-relaxed">{sessionError}</div>
                    <div className="text-[11px] text-zinc-500 max-w-xs leading-relaxed bg-zinc-900/60 rounded-md p-2 border border-zinc-800">
                      <span className="text-amber-300 font-medium">Common fixes:</span>{" "}
                      {sessionError.toLowerCase().includes("proxy") || sessionError.toLowerCase().includes("auth")
                        ? "Verify proxy credentials, ensure your IP is whitelisted at the proxy provider, or try a different gateway."
                        : sessionError.toLowerCase().includes("timeout") || sessionError.toLowerCase().includes("nav")
                        ? "Page may be slow — try without proxy first, or pick a closer proxy region."
                        : "Check the URL is correct & publicly reachable; confirm proxy is alive."}
                    </div>
                    <button
                      onClick={async () => {
                        try { await fetch(`${API_URL}/api/visual-recorder/${sessionId}`, { method: "DELETE", headers: authH() }); } catch {}
                        setSessionId(null);
                        setSessionState("starting");
                        setSessionError("");
                        setSetupStage("setup");
                      }}
                      className="mt-1 px-4 py-2 rounded-lg bg-rose-700 hover:bg-rose-600 text-white text-xs font-medium transition-colors"
                      data-testid="vr-retry-btn"
                    >
                      <ArrowLeft className="w-3 h-3 inline mr-1" /> Back to Setup
                    </button>
                  </div>
                ) : sessionState !== "ready" ? (
                  <div className="aspect-[412/914] w-full flex flex-col items-center justify-center text-zinc-400 text-sm gap-3 px-6" data-testid="vr-connecting-state">
                    <div className="relative">
                      <Loader2 className="w-10 h-10 animate-spin text-emerald-400" />
                      <div className="absolute inset-0 flex items-center justify-center text-[10px] text-emerald-300 font-mono">
                        {connectElapsed}s
                      </div>
                    </div>
                    <div className="font-medium text-zinc-200">
                      Spinning up Chromium {proxy ? "via proxy" : "directly"}…
                    </div>
                    <div className="text-[11px] text-zinc-500 text-center max-w-xs leading-relaxed">
                      Launching anti-detect browser → resolving DNS → opening page.<br />
                      <span className="text-amber-300">Slow proxies can take up to 45 seconds.</span>
                    </div>
                    {/* Progress shimmer */}
                    <div className="w-32 h-1 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 transition-all"
                        style={{ width: `${Math.min(100, (connectElapsed / 45) * 100)}%` }}
                      />
                    </div>
                  </div>
                ) : screenshotSrc ? (
                  <img
                    ref={imgRef}
                    src={screenshotSrc}
                    alt="Live preview"
                    onClick={handleImgClick}
                    onLoad={() => setShotErrorCount(0)}
                    onError={() => setShotErrorCount((c) => c + 1)}
                    className={`max-w-full h-auto cursor-${tool === "form_fill" ? "text" : tool === "final" ? "crosshair" : tool === "nav_only" ? "grab" : "pointer"} select-none`}
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

              {/* Toolbar — 7-col grid with kbd hints */}
              <div className="mt-3 grid grid-cols-4 sm:grid-cols-7 gap-2">
                {TOOLS.map((t) => {
                  const Ic = t.icon;
                  const active = tool === t.id;
                  return (
                    <button
                      key={t.id}
                      onClick={() => {
                        setTool(t.id);
                        if (t.id !== "random") {
                          setPendingRandom([]);
                          setDetectedClickables([]);
                          setSelectedRandomKeys(new Set());
                        } else {
                          // 2026-01: auto-detect all clickables on the
                          // current page the moment the user picks
                          // the Random Pick tool. No need to click each
                          // button manually anymore.
                          detectClickables();
                        }
                      }}
                      title={`${t.help} (key: ${t.key})`}
                      className={`relative flex flex-col items-center justify-center gap-1 py-2 px-1.5 rounded-lg text-xs font-medium transition-all ${
                        active
                          ? "bg-emerald-600 text-white shadow-md shadow-emerald-900/30"
                          : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                      }`}
                      data-testid={`vr-tool-${t.id}`}
                    >
                      <Ic className="w-4 h-4" />
                      <span className="truncate w-full text-center">{t.label}</span>
                      <kbd
                        className={`absolute top-0.5 right-1 text-[9px] px-1 rounded font-mono ${
                          active ? "bg-emerald-800 text-emerald-200" : "bg-zinc-900 text-zinc-500"
                        }`}
                      >
                        {t.key}
                      </kbd>
                    </button>
                  );
                })}
              </div>

              {/* Sub-controls per mode */}
              {/* 2026-01 NEW: Random Pick checklist panel — auto-populated
                  by /detect-clickables when the user selects the "Random
                  Pick" tool. User ticks the candidates they want in the
                  random pool, then clicks "Build Random Step". */}
              {tool === "random" && (detectingClickables || detectedClickables.length > 0) && (
                <div
                  className="mt-3 p-3 rounded-lg bg-amber-950/40 border border-amber-700/40"
                  data-testid="vr-random-checklist-panel"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs text-amber-300 font-medium">
                      {detectingClickables ? (
                        <span className="flex items-center gap-1.5">
                          <Loader2 className="w-3 h-3 animate-spin" /> Detecting clickable elements on the page…
                        </span>
                      ) : (
                        <>Random Pick — tick the buttons for the random pool ({selectedRandomKeys.size}/{detectedClickables.length} selected)</>
                      )}
                    </div>
                    <button
                      onClick={detectClickables}
                      disabled={detectingClickables}
                      title="Re-scan the current page"
                      className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-amber-200 border border-amber-800/40"
                      data-testid="vr-rescan-clickables-btn"
                    >
                      <RefreshCw className="w-3 h-3 inline-block mr-1" />
                      Re-scan
                    </button>
                  </div>
                  {!detectingClickables && detectedClickables.length > 0 && (
                    <>
                      <div className="max-h-56 overflow-y-auto pr-1 mb-2 space-y-1 rounded border border-amber-900/40 bg-zinc-950/40 p-1.5">
                        {detectedClickables.map((el, i) => {
                          const checked = selectedRandomKeys.has(i);
                          return (
                            <label
                              key={i}
                              className={`flex items-start gap-2 px-2 py-1 rounded cursor-pointer text-xs transition-colors ${
                                checked
                                  ? "bg-amber-900/40 text-amber-100"
                                  : "hover:bg-zinc-900 text-zinc-300"
                              }`}
                              data-testid={`vr-clickable-row-${i}`}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => {
                                  setSelectedRandomKeys((prev) => {
                                    const next = new Set(prev);
                                    if (next.has(i)) next.delete(i);
                                    else next.add(i);
                                    return next;
                                  });
                                }}
                                className="mt-0.5 accent-amber-500"
                                data-testid={`vr-clickable-check-${i}`}
                              />
                              <span className="flex-1 leading-snug">
                                <span className="font-medium">{el.text}</span>
                                <span className="ml-1.5 text-[9px] uppercase tracking-wide text-zinc-500">
                                  {el.tag}{el.role ? ` · role=${el.role}` : ""}
                                </span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => {
                            // Toggle all
                            if (selectedRandomKeys.size === detectedClickables.length) {
                              setSelectedRandomKeys(new Set());
                            } else {
                              setSelectedRandomKeys(new Set(detectedClickables.map((_, i) => i)));
                            }
                          }}
                          className="text-[10px] px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                          data-testid="vr-toggle-all-btn"
                        >
                          {selectedRandomKeys.size === detectedClickables.length ? "Clear all" : "Select all"}
                        </button>
                        <button
                          onClick={buildRandomStep}
                          disabled={selectedRandomKeys.size < 2 || busy}
                          className="px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-xs font-medium"
                          data-testid="vr-build-random-checklist-btn"
                        >
                          Build Random Step ({selectedRandomKeys.size})
                        </button>
                        <span className="text-[10px] text-amber-200/70">
                          Tip: After building, switch to <b>Click</b> and pick any answer to move to the next page.
                        </span>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Legacy click-to-pool flow — still works for users who
                  prefer clicking each candidate on the live page. Only
                  shown when the new checklist isn't being used. */}
              {tool === "random" && detectedClickables.length === 0 && !detectingClickables && pendingRandom.length > 0 && (
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

              {pendingDropdown && (
                <div
                  className="mt-3 p-3 rounded-lg bg-amber-950/30 border border-amber-700/40"
                  data-testid="vr-dropdown-bind-panel"
                >
                  <div className="text-xs text-amber-200 mb-1 font-medium flex items-center gap-1 flex-wrap">
                    <ChevronDown className="w-3.5 h-3.5" />
                    Bind dropdown <code className="text-zinc-300">{pendingDropdown.selector}</code>
                    {pendingDropdown.wrapper_kind && (
                      <span
                        data-testid="vr-dd-wrapper-badge"
                        className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/20 border border-blue-400/40 text-blue-200"
                        title={
                          pendingDropdown.is_hidden_select
                            ? "Native <select> is CSS-hidden behind this custom UI. Recorder will mark this step state=\"attached\" + prefer JS-set at replay so the visit doesn't 25s-timeout on visibility."
                            : "Custom dropdown UI detected — replay will use JS-first select."
                        }
                      >
                        {pendingDropdown.wrapper_kind === "generic-custom"
                          ? "Custom UI"
                          : pendingDropdown.wrapper_kind}
                        {pendingDropdown.is_hidden_select ? " · hidden <select>" : ""}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-zinc-400 mb-2">
                    {pendingDropdown.options.length} option{pendingDropdown.options.length === 1 ? "" : "s"} found —
                    pick a fixed one OR bind to an Excel column.
                  </div>

                  {/* Excel column bindings (preferred for per-row values) */}
                  {headers.length > 0 && (
                    <>
                      <div className="text-[11px] text-zinc-500 mb-1 uppercase tracking-wide">
                        Bind to Excel column (match by visible label)
                      </div>
                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {headers.map((h) => (
                          <button
                            key={`dd-h-${h}`}
                            onClick={() => submitDropdownBind({ header_name: h, match_by: "label" })}
                            className="px-2 py-1 rounded bg-amber-600/30 hover:bg-amber-600/60 border border-amber-500/40 text-amber-50 text-xs"
                            data-testid={`vr-dd-bind-${h}`}
                          >
                            {`{{${h}}}`}
                          </button>
                        ))}
                      </div>
                    </>
                  )}

                  <div className="text-[11px] text-zinc-500 mb-1 uppercase tracking-wide">
                    Or pick a fixed option (always selected)
                  </div>
                  <div className="max-h-44 overflow-y-auto rounded border border-zinc-800 bg-zinc-950/50 divide-y divide-zinc-800/60">
                    {pendingDropdown.options.map((o, idx) => {
                      const lbl = (o.label || o.value || "").trim() || `(option #${idx + 1})`;
                      const sub = o.value && o.value !== lbl ? ` · value="${o.value}"` : "";
                      return (
                        <button
                          key={`dd-opt-${idx}`}
                          onClick={() => submitDropdownBind({ value: o.label || o.value || "", match_by: "label" })}
                          className="w-full text-left px-2 py-1.5 text-xs text-zinc-200 hover:bg-amber-600/20 hover:text-amber-100 transition flex items-center justify-between"
                          data-testid={`vr-dd-opt-${idx}`}
                        >
                          <span className="truncate">{lbl}</span>
                          <span className="text-[10px] text-zinc-500 ml-2 truncate">{sub}</span>
                        </button>
                      );
                    })}
                  </div>

                  <div className="flex justify-end mt-2">
                    <button
                      onClick={() => setPendingDropdown(null)}
                      className="px-2 py-1 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs"
                      data-testid="vr-dd-cancel"
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

                {/* Keyboard quick-keys + wait-for-selector — power-user actions */}
                <div className="inline-flex items-center gap-1 ml-auto" data-testid="vr-key-row">
                  <span className="text-[10px] text-zinc-500 mr-1">Press:</span>
                  {["Enter","Tab","Escape","Backspace","ArrowDown"].map((k) => (
                    <button
                      key={k}
                      onClick={() => pressKey(k)}
                      disabled={sessionState !== "ready"}
                      title={`Press ${k} key`}
                      className="px-2 py-1 rounded bg-zinc-800 hover:bg-emerald-700/40 border border-zinc-700 hover:border-emerald-500/40 text-zinc-300 text-[10px] font-mono disabled:opacity-40"
                      data-testid={`vr-press-${k}`}
                    >
                      {k === "Backspace" ? "⌫" : k === "ArrowDown" ? "↓" : k}
                    </button>
                  ))}
                  <button
                    onClick={waitForSelectorAction}
                    disabled={sessionState !== "ready"}
                    title="Wait until a CSS selector becomes visible"
                    className="px-2 py-1 rounded bg-zinc-800 hover:bg-sky-700/40 border border-zinc-700 hover:border-sky-500/40 text-zinc-300 text-[10px] disabled:opacity-40 ml-1"
                    data-testid="vr-wait-selector-btn"
                  >
                    ⏳ Wait for selector
                  </button>
                </div>
              </div>
            </div>

            {/* Steps panel */}
            <div className="lg:col-span-1 p-3 rounded-xl bg-zinc-900/60 border border-zinc-800 flex flex-col" style={{ maxHeight: "85vh" }}>
              <div className="flex items-center justify-between mb-2 px-1">
                <h3 className="text-sm font-medium flex items-center gap-1.5">
                  <ScrollText className="w-4 h-4 text-emerald-400" />
                  Recorded Steps
                  <span className="px-1.5 py-0.5 rounded bg-emerald-700/30 border border-emerald-500/30 text-emerald-200 text-[10px] font-mono">
                    {steps.length}
                  </span>
                </h3>
                {steps.length > 0 && (
                  <button
                    onClick={undoLastStep}
                    title="Undo last step (Ctrl+Z)"
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-zinc-800 hover:bg-amber-700/40 border border-zinc-700 hover:border-amber-500/40 text-zinc-300 hover:text-amber-200 transition-colors"
                    data-testid="vr-undo-btn"
                  >
                    <Undo2 className="w-3 h-3" /> Undo
                  </button>
                )}
              </div>

              <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
                {steps.length === 0 && (
                  <div className="text-zinc-600 text-xs text-center py-4">No steps yet — click on the preview to record</div>
                )}
                {steps.map((s, i) => (
                  <div key={i} className="flex items-start gap-1 p-2 rounded bg-zinc-950 border border-zinc-800 text-xs hover:border-zinc-700 transition-colors group">
                    <span className="text-emerald-400 font-mono pt-0.5">#{i + 1}</span>
                    <div className="flex-1 min-w-0">
                      {/* Inline-editable name (click to edit) */}
                      <input
                        type="text"
                        defaultValue={s.name || s.action}
                        onBlur={(e) => {
                          const newName = (e.target.value || "").trim();
                          if (newName && newName !== (s.name || s.action)) renameStep(i, newName);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") e.target.blur();
                          if (e.key === "Escape") { e.target.value = s.name || s.action; e.target.blur(); }
                        }}
                        className="w-full bg-transparent border-0 border-b border-transparent hover:border-zinc-700 focus:border-emerald-500 focus:outline-none text-zinc-300 font-medium px-0 py-0 text-xs"
                        title={`Rename step (was: ${s.action})`}
                        data-testid={`vr-step-name-${i}`}
                      />
                      <div className="text-zinc-500 truncate">
                        {s.selector && <span>sel: <code className="text-zinc-400">{s.selector.slice(0, 28)}</code></span>}
                        {s.value && <span> → {String(s.value).slice(0, 30)}</span>}
                        {s.ms && <span>{s.ms}ms</span>}
                        {s.timeout && !s.ms && <span>tout: {s.timeout}</span>}
                        {s.key && <span>key: <code className="text-zinc-400">{s.key}</code></span>}
                        {s.script && !s.name && <span title={s.script}>{s.script.slice(0, 50)}…</span>}
                      </div>
                    </div>
                    {/* Step actions — visible on hover */}
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => moveStep(i, "up")}
                        disabled={i === 0}
                        title="Move up"
                        className="p-0.5 text-zinc-600 hover:text-emerald-400 disabled:opacity-30 disabled:cursor-not-allowed"
                        data-testid={`vr-step-up-${i}`}
                      >▲</button>
                      <button
                        onClick={() => moveStep(i, "down")}
                        disabled={i === steps.length - 1}
                        title="Move down"
                        className="p-0.5 text-zinc-600 hover:text-emerald-400 disabled:opacity-30 disabled:cursor-not-allowed"
                        data-testid={`vr-step-down-${i}`}
                      >▼</button>
                      <button
                        onClick={() => duplicateStep(i)}
                        title="Duplicate"
                        className="p-0.5 text-zinc-600 hover:text-sky-400 text-[10px]"
                        data-testid={`vr-step-dup-${i}`}
                      >⎘</button>
                      <button
                        onClick={() => deleteStep(i)}
                        title="Delete"
                        className="p-0.5 text-zinc-600 hover:text-rose-400"
                        data-testid={`vr-step-del-${i}`}
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
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
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-700/40 hover:bg-emerald-700/60 border border-emerald-500/40 text-emerald-100 text-sm font-medium transition-colors"
                data-testid="vr-copy-json-btn"
              >
                <Copy className="w-4 h-4" /> Copy JSON
              </button>
              <button
                onClick={downloadJson}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-700/40 hover:bg-emerald-700/60 border border-emerald-500/40 text-emerald-100 text-sm font-medium transition-colors"
                data-testid="vr-download-json-btn"
              >
                <Download className="w-4 h-4" /> Download JSON
              </button>
              <button
                onClick={saveToLibrary}
                disabled={saving || savedToLibraryId}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-700/40 hover:bg-indigo-700/60 border border-indigo-500/40 text-indigo-100 text-sm font-medium disabled:opacity-60 transition-colors"
                data-testid="vr-save-library-btn"
                title="Save as reusable template in Uploaded Things library"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : savedToLibraryId ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                {savedToLibraryId ? "Saved to Library" : "Save to Library"}
              </button>
              {finalBundle.target_screenshot_path && (
                <button
                  onClick={downloadTargetScreenshot}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-700/40 hover:bg-blue-700/60 border border-blue-500/40 text-blue-100 text-sm font-medium transition-colors"
                  data-testid="vr-download-target-btn"
                >
                  <Download className="w-4 h-4" /> Download Final Screenshot
                </button>
              )}
            </div>

            <details className="mt-4" open>
              <summary className="cursor-pointer text-sm text-zinc-400 hover:text-zinc-200 select-none flex items-center gap-1">
                <ChevronDown className="w-4 h-4" /> Preview JSON
                <span className="text-[10px] text-zinc-600 ml-auto">syntax-highlighted</span>
              </summary>
              <pre
                className="mt-2 p-3 rounded bg-zinc-950 border border-zinc-800 text-xs overflow-x-auto max-h-96 font-mono leading-relaxed"
                dangerouslySetInnerHTML={{
                  __html: colorizeJson(finalBundle.automation_json),
                }}
              />
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
