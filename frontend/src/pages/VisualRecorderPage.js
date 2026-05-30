import React, { useEffect, useRef, useState, useCallback } from "react";
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
  CheckCheck,
  XCircle,
  Lightbulb,
  Timer,
  Pencil,
  Brain,
  Trash,
  FastForward,
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
  // 2026-05: explicit "close browser" step. Inserts {"action":"close"}
  // at current position so the RUT runner frees the browser as soon
  // as it reaches this step (recommended right after the conversion-
  // confirmation Capture so post-submit pixel chains don't keep the
  // tile alive on slower VPSes).
  { id: "close_browser", icon: XCircle, label: "Close Browser", key: "9", help: "Insert a close-browser step — RUT runner will end this visit's browser immediately when reached (frees RAM for next worker)" },
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
  // Edit-step modal state (2026-01) — null when closed; otherwise
  // {index, draft} where `draft` is a mutable copy of the step the
  // user is editing. See `openEditStep` / `saveEditStep` below.
  const [editingStep, setEditingStep] = useState(null);
  // Smart Selector Suggester state (2026-01) — { loading, items[], failedSelector }
  const [selectorSuggest, setSelectorSuggest] = useState({ loading: false, items: null, error: "" });
  // Hover-preview state (2026-01) — bbox of the suggestion currently
  // being hovered, drawn as a blue pulse outline overlay on the
  // live screenshot. null = no preview.
  const [hoverPreview, setHoverPreview] = useState(null);   // { x, y, width, height, viewport }
  // Manual "Add Step" modal — null when closed; otherwise a draft step
  const [manualStepDraft, setManualStepDraft] = useState(null);
  // Selector Aliases panel (2026-01, self-healing memory) — null = closed
  const [aliasesPanel, setAliasesPanel] = useState(null);   // { loading, items, error }
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
  // ── 2026-01 (new) — Active sessions panel ─────────────────────────
  // Shows every recorder currently running under this user's account
  // so they can SEE the 5/5 cap, switch between sessions, or stop the
  // ones they don't need. Polled every 3s while on the setup screen.
  const [activeSessions, setActiveSessions] = useState([]);
  const [activeSessionStats, setActiveSessionStats] = useState({ user_session_count: 0, total_running: 0, max_concurrent: 5 });
  const [devicePreset, setDevicePreset] = useState("mobile");
  const [pjAvailable, setPjAvailable] = useState(false);
  const [pjCountry, setPjCountry] = useState("US");
  const [saving, setSaving] = useState(false);
  const [savedToLibraryId, setSavedToLibraryId] = useState(null);

  // ── 2026-05: Edit-an-existing-template mode ─────────────────────
  // When the user clicks the "Open in Visual Recorder" (camera) icon
  // on the Uploaded Things → Automation JSON tab, the page is loaded
  // with `?edit_upload_id=X` in the URL. We then:
  //   1. Fetch that upload via /api/uploads, extract the saved
  //      automation_json + name + description + first goto.url.
  //   2. Pre-fill the Offer URL field so the user just clicks Start.
  //   3. After the recording session is ready, POST the saved steps
  //      to /visual-recorder/{sid}/import-steps — so the recorder
  //      session is seeded with the existing recording.
  //   4. When the user clicks Save-to-Library, we PATCH the original
  //      upload_id instead of POSTing a new one (preserves every
  //      RUT campaign preset that already references this template).
  // editTemplate holds the loaded upload object once /uploads returns;
  // editUploadId is the live URL-param (truthy = edit mode is active).
  const [editUploadId, setEditUploadId] = useState(null);
  const [editTemplate, setEditTemplate] = useState(null);   // {id, name, description, automation_json}
  // JSON editor state (2026-01) — when truthy, the Preview JSON block
  // turns into an editable textarea on the Recording Complete screen.
  const [editingJson, setEditingJson] = useState(false);
  const [editingJsonText, setEditingJsonText] = useState("");
  const [editingJsonError, setEditingJsonError] = useState("");
  // Live Visual Test state — when running, the finalized page shows a
  // progress overlay and re-opens the recorder so the user can watch
  // the full automation step-by-step.
  const [replayLaunching, setReplayLaunching] = useState(false);
  // ── 2026-05: Live Test + Smart Diagnostics ──
  const [liveTestResult, setLiveTestResult] = useState(null); // {ok, total_ms, step_results, diagnostics, ...}
  const [liveTesting, setLiveTesting] = useState(false);
  // 2026-01: Real-time step-by-step progress feed during live test.
  // Populated by polling /live-progress endpoint every ~400ms while
  // a test is running. Cleared at the start of each run.
  const [liveProgress, setLiveProgress] = useState([]);
  // 2026-01: Latest live browser screenshot (data:image/jpeg;base64,...)
  // from the most recent step event. Updated as steps execute.
  const [liveFrame, setLiveFrame] = useState(null);
  const [liveFrameMeta, setLiveFrameMeta] = useState(null);
  const [showDiagnostics, setShowDiagnostics] = useState(true);
  // ── 2026-05: Auto-fix history + auto-retest toggle ──
  // Persisted across the session so the user can: 1) Auto-fix all,
  // 2) automatically re-run Live Test, 3) Finalize — in 3 clicks
  // total. Undo button reverts the most recent fix if it broke
  // something specific to the user's page.
  const [fixHistoryCount, setFixHistoryCount] = useState(0);
  const [lastUndoneFix, setLastUndoneFix] = useState(null);
  const [autoRetestEnabled, setAutoRetestEnabled] = useState(true);
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

  // ── 2026-05: Edit-existing-template mode bootstrap ─────────────
  // When the user lands on /visual-recorder?edit_upload_id=X (from
  // Uploaded Things → Edit-in-Recorder camera icon), fetch the saved
  // template so we can:
  //   • pre-fill the Offer URL field (extracted from the first goto
  //     step) so the user doesn't have to retype it,
  //   • show an "Editing template …" banner above the Start button,
  //   • remember the upload_id so Save-to-Library PATCHes the same
  //     row instead of creating a new one.
  // Listening on `window.location.search` (no react-router-dom dep
  // change) keeps this drop-in.
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const id = sp.get("edit_upload_id");
    if (!id) return;
    setEditUploadId(id);
    (async () => {
      try {
        const r = await fetch(`${API_URL}/api/uploads?type=automation_json`, {
          headers: authH(),
        });
        const list = await r.json();
        if (!r.ok) throw new Error(list?.detail || `HTTP ${r.status}`);
        const found = Array.isArray(list)
          ? list.find((u) => u.id === id)
          : null;
        if (!found) {
          toast.error("Template not found — it may have been deleted.");
          return;
        }
        setEditTemplate(found);
        // Pre-fill the Offer URL from the first step that mentions a
        // URL. Recorder JSONs USUALLY start with `goto`, but a lot of
        // older / hand-crafted templates start with `wait_for_load` and
        // rely on the RUT job to inject the URL at run-time. We search
        // multiple step shapes so we catch as many as possible:
        //   • {action:"goto", url:"…"}
        //   • {action:"navigate", url:"…"}        (alias used by some recorders)
        //   • {action:"wait_for_url", url:"…"}    (sometimes a substring)
        // If none match, we LEAVE the field blank — the user can
        // either type one in OR just click Start Editing (we now
        // accept blank URL in edit-mode and the recorder opens
        // about:blank so the step-list UI is still fully usable).
        try {
          const parsedSteps = JSON.parse(found.automation_json || "[]");
          if (Array.isArray(parsedSteps)) {
            const urlStep = parsedSteps.find((s) => {
              if (!s || typeof s !== "object") return false;
              if (typeof s.url !== "string") return false;
              return ["goto", "navigate", "wait_for_url"].includes(s.action);
            });
            if (urlStep && urlStep.url) {
              setUrl(urlStep.url);
            }
          }
        } catch (_pe) {
          // bad JSON — user will see error if they try to import. Don't
          // surface here to avoid spurious toasts on page load.
        }
        toast.info(
          `🔧 Editing template: ${found.name} — start recording to load existing steps`,
          { duration: 6000 },
        );
      } catch (e) {
        toast.error(`Could not load template: ${e.message || e}`);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 2026-01 (new) — Active sessions list (poll while on setup) ────
  const refreshActiveSessions = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/sessions`, {
        headers: authH(),
      });
      if (!r.ok) return;
      const d = await r.json();
      setActiveSessions(Array.isArray(d.sessions) ? d.sessions : []);
      setActiveSessionStats({
        user_session_count: d.user_session_count || 0,
        total_running: d.total_running || 0,
        max_concurrent: d.max_concurrent || 5,
      });
    } catch {}
  }, []);

  useEffect(() => {
    if (setupStage !== "setup") return;
    refreshActiveSessions();
    const t = setInterval(refreshActiveSessions, 3000);
    return () => clearInterval(t);
  }, [setupStage, refreshActiveSessions]);

  // Switch to an existing session (minimize/restore flow). Does NOT
  // stop the current session — just hops the UI over to render the
  // other one. The original session continues running in the
  // background; the user can come back any time via the same panel.
  const switchToSession = useCallback((sess) => {
    if (!sess || !sess.session_id) return;
    setSessionId(sess.session_id);
    setViewport(sess.viewport || { width: 412, height: 914 });
    setSessionState(sess.state || "starting");
    setSessionError(sess.error_message || "");
    setShotTick(0);
    setShotErrorCount(0);
    setSteps([]);  // refreshState will repopulate
    setSetupStage("recording");
    toast.success(`Switched to recorder · ${(() => { try { return new URL(sess.current_url || sess.url).hostname; } catch { return (sess.url || "").slice(0, 30); } })()}`);
  }, []);

  // Stop a specific session from the list (without leaving setup stage).
  const stopSessionById = useCallback(async (sid, hostnameLabel) => {
    if (!sid) return;
    if (!window.confirm(`Stop this recorder session?${hostnameLabel ? `\n\n${hostnameLabel}` : ""}\n\nAny unsaved steps in this session will be lost.`)) return;
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sid}`, {
        method: "DELETE",
        headers: authH(),
      });
      toast.success("Session stopped");
      refreshActiveSessions();
    } catch (e) {
      toast.error(`Failed to stop: ${e?.message || e}`);
    }
  }, [refreshActiveSessions]);

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
    // ── 2026-05: In edit-mode the URL field is OPTIONAL ──
    // The user is editing an existing step list. They can fully use
    // the step-management UI (reorder / delete / rename / edit-step
    // modal / append manual-step / save) without ever needing a live
    // browser page. If they DO want to add new recorded clicks, they
    // can navigate the recorder browser to any URL via the existing
    // Navigate textbox after the session is ready. We default to
    // about:blank so the recorder still has a target — Chromium opens
    // a blank tab instantly, no proxy slowdown.
    const effectiveUrl = url.trim() || (editUploadId ? "about:blank" : "");
    if (!effectiveUrl) {
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
          url: effectiveUrl,
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
      // ── 2026-05: Edit-mode — auto-import the saved steps so the user
      // can continue from where the original recording left off. The
      // session is "starting" at this point; the import-steps endpoint
      // does NOT need a ready page (it just appends to sess.steps).
      // After session reaches "ready" the user can immediately reorder,
      // re-record over, delete, or append new steps.
      if (editUploadId && editTemplate?.automation_json) {
        try {
          let parsedSteps = JSON.parse(editTemplate.automation_json);
          if (!Array.isArray(parsedSteps)) parsedSteps = [];
          const importRes = await fetch(
            `${API_URL}/api/visual-recorder/${d.session_id}/import-steps`,
            {
              method: "POST",
              headers: authH(),
              body: JSON.stringify({ steps: parsedSteps }),
            },
          );
          if (!importRes.ok) {
            const ie = await importRes.json().catch(() => ({}));
            throw new Error(ie.detail || `HTTP ${importRes.status}`);
          }
          toast.success(
            `✓ Loaded ${parsedSteps.length} step${parsedSteps.length === 1 ? "" : "s"} from "${editTemplate.name}" — edit freely, Save to update`,
            { duration: 6000 },
          );
        } catch (impErr) {
          toast.error(`Could not load existing steps: ${impErr.message || impErr}`);
        }
      }
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

    // 2026-05: "close_browser" tool — no click needed, just append a
    // {"action":"close"} step at the current position. Same pattern as
    // the capture tool above. We auto-flip back to "default" so the
    // operator can keep recording (or save/test) without manually
    // changing the tool.
    if (tool === "close_browser") {
      setBusy(true);
      try {
        const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/close-browser-step`, {
          method: "POST",
          headers: authH(),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        toast.success("🔌 Close-browser step inserted — RUT will end the visit's browser here");
        setTool("default");
        refreshState();
      } catch (err) {
        toast.error(`Insert close failed: ${err.message || err}`);
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

  // 2026-01: New step types — Wait for Text / Wait for URL / Extract / Dismiss Popups
  const addWaitForText = async () => {
    if (!sessionId) return;
    const text = window.prompt("Wait until this text appears on the page (e.g. 'Thank you', 'Order confirmed'):", "");
    if (!text || !text.trim()) return;
    const tout = window.prompt("Max wait time in ms (default 15000):", "15000");
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/add-wait-text`, {
        method: "POST", headers: authH(),
        body: JSON.stringify({
          text: text.trim(),
          timeout: Math.max(1000, Number(tout) || 15000),
          case_insensitive: true,
          optional: false,
        }),
      });
      const d = await r.json();
      if (!r.ok || !d.recorded) { toast.error(d.error || d.detail || "Failed"); return; }
      toast.success(`Wait for text "${text.slice(0, 30)}" added`);
      refreshState();
    } catch (e) { toast.error(e.message || "Failed"); }
  };

  const addWaitForUrl = async () => {
    if (!sessionId) return;
    const contains = window.prompt("Wait until URL contains (e.g. '/thank-you', '/success'):", "");
    if (!contains || !contains.trim()) return;
    const tout = window.prompt("Max wait time in ms (default 15000):", "15000");
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/add-wait-url`, {
        method: "POST", headers: authH(),
        body: JSON.stringify({
          contains: contains.trim(),
          timeout: Math.max(1000, Number(tout) || 15000),
          optional: false,
        }),
      });
      const d = await r.json();
      if (!r.ok || !d.recorded) { toast.error(d.error || d.detail || "Failed"); return; }
      toast.success(`Wait for URL ~ "${contains}" added`);
      refreshState();
    } catch (e) { toast.error(e.message || "Failed"); }
  };

  const addExtract = async () => {
    if (!sessionId) return;
    const sel = window.prompt("CSS selector to extract text from (e.g. '#order-id', '.confirmation .code'):", "");
    if (!sel || !sel.trim()) return;
    const key = window.prompt("Variable name to store the value (e.g. 'order_id'). Use later as {{order_id}}:", "");
    if (!key || !key.trim()) return;
    const attr = window.prompt("(Optional) attribute name to read instead of text (e.g. 'href', 'data-id'). Leave blank for text:", "");
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/add-extract`, {
        method: "POST", headers: authH(),
        body: JSON.stringify({
          selector: sel.trim(),
          store_key: key.trim(),
          attribute: (attr || "").trim() || null,
          timeout: 10000,
          optional: false,
        }),
      });
      const d = await r.json();
      if (!r.ok || !d.recorded) { toast.error(d.error || d.detail || "Failed"); return; }
      toast.success(`Extract → {{${key}}} added`);
      refreshState();
    } catch (e) { toast.error(e.message || "Failed"); }
  };

  const addDismissPopups = async () => {
    if (!sessionId) return;
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/add-dismiss-popups`, {
        method: "POST", headers: authH(),
      });
      const d = await r.json();
      if (!r.ok || !d.recorded) { toast.error(d.error || d.detail || "Failed"); return; }
      toast.success("Dismiss popups step added");
      refreshState();
    } catch (e) { toast.error(e.message || "Failed"); }
  };

  // Pre-flight lint
  const [lintResult, setLintResult] = useState(null);
  const [showLintPanel, setShowLintPanel] = useState(false);
  const runLint = async () => {
    if (!sessionId) return;
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/lint`, { headers: authH() });
      const d = await r.json();
      setLintResult(d);
      setShowLintPanel(true);
      const summary = d.summary || {};
      if (d.ok) toast.success(`Lint passed (${summary.warnings || 0} warnings, ${summary.infos || 0} info)`);
      else toast.error(`Lint found ${summary.errors || 0} error(s)`);
    } catch (e) { toast.error(e.message || "Lint failed"); }
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

  // 2026-01: Drag-and-drop reorder — move any step to any index
  const moveStepTo = async (fromIndex, toIndex) => {
    if (!sessionId) return;
    if (fromIndex === toIndex) return;
    try {
      await fetch(`${API_URL}/api/visual-recorder/${sessionId}/step/move-to`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ from_index: fromIndex, to_index: toIndex }),
      });
      refreshState();
    } catch (e) {
      toast.error(e.message || "Move failed");
    }
  };

  // 2026-01: Drag-and-drop state — `dragSrc` is the index currently being dragged
  const [dragSrc, setDragSrc] = useState(null);
  const [dragOver, setDragOver] = useState(null);

  // 2026-01: Insert a new step at a SPECIFIC index (between two existing steps).
  // Prompts the user to pick action type, then opens the existing modal.
  const insertStepAt = async (position) => {
    if (!sessionId) return;
    const action = window.prompt(
      "Step action to insert? Options: click, fill, type, select, check, uncheck, wait, wait_for_selector, wait_for_text, wait_for_url, press, scroll, screenshot, hover, dismiss_popups, extract",
      "wait"
    );
    if (!action || !action.trim()) return;
    const cleanAction = action.trim().toLowerCase();
    let stepDraft = { action: cleanAction };
    // Action-specific prompts
    if (["click", "fill", "type", "select", "check", "uncheck", "hover", "wait_for_selector"].includes(cleanAction)) {
      const sel = window.prompt("CSS selector (or XPath e.g. //input[@name='x']):", "");
      if (!sel || !sel.trim()) return;
      stepDraft.selector = sel.trim();
      if (["fill", "type", "select"].includes(cleanAction)) {
        const val = window.prompt("Value to fill/type/select (use {{var}} for row data):", "");
        if (val !== null) stepDraft.value = val;
      }
    } else if (cleanAction === "wait") {
      const ms = window.prompt("Wait time in milliseconds:", "1000");
      stepDraft.ms = Math.max(0, Number(ms) || 1000);
    } else if (cleanAction === "wait_for_text") {
      const text = window.prompt("Text to wait for (e.g. 'Thank you'):", "");
      if (!text || !text.trim()) return;
      stepDraft.text = text.trim();
      stepDraft.timeout = 15000;
    } else if (cleanAction === "wait_for_url") {
      const contains = window.prompt("URL must contain:", "");
      if (!contains || !contains.trim()) return;
      stepDraft.contains = contains.trim();
      stepDraft.timeout = 15000;
    } else if (cleanAction === "press") {
      const key = window.prompt("Key to press (e.g. Enter, Tab, Escape):", "Enter");
      stepDraft.key = key || "Enter";
    } else if (cleanAction === "scroll") {
      stepDraft.value = window.prompt("Scroll amount (px, e.g. 500 or 'bottom'):", "500") || "500";
    } else if (cleanAction === "screenshot") {
      stepDraft.name = window.prompt("Screenshot label (e.g. 'After Submit'):", "Capture") || "Capture";
    } else if (cleanAction === "extract") {
      const sel = window.prompt("CSS selector to extract from:", "");
      if (!sel) return;
      stepDraft.selector = sel.trim();
      const key = window.prompt("Variable name to store value as (use later via {{var}}):", "");
      if (!key) return;
      stepDraft.store_key = key.trim();
    }
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/manual-step`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({ step: stepDraft, position }),
      });
      const d = await r.json();
      if (!r.ok || !d.added) {
        toast.error(d.reason || d.detail || "Insert failed");
        return;
      }
      toast.success(`Step inserted at position #${(d.index ?? position) + 1}`);
      refreshState();
    } catch (e) {
      toast.error(e.message || "Insert failed");
    }
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

  // ── Edit step (2026-01) ──────────────────────────────────────────
  // Opens the Edit modal pre-filled with the current step's editable
  // fields (selector / value / timeout / etc.). Lets the user fix a
  // wrong selector or bump a timeout after a Live Test failure
  // (e.g. the #birth_month case from the screenshots), then PATCHes
  // the change to the backend and refreshes the recorded-steps list.
  const openEditStep = (idx) => {
    if (idx < 0 || idx >= steps.length) return;
    const s = steps[idx] || {};
    setSelectorSuggest({ loading: false, items: null, error: "" });
    setEditingStep({
      index: idx,
      draft: {
        action: s.action || "",       // read-only display
        selector: s.selector || "",
        value: s.value != null ? String(s.value) : "",
        timeout: s.timeout != null ? String(s.timeout) : "",
        key: s.key || "",
        ms: s.ms != null ? String(s.ms) : "",
        state: s.state || "",
        delay: s.delay != null ? String(s.delay) : "",
        match_by: s.match_by || "",
        humanize: s.humanize !== false,   // default true (existing behaviour)
        name: s.name || "",
      },
    });
  };

  const cancelEditStep = () => {
    setEditingStep(null);
    setSelectorSuggest({ loading: false, items: null, error: "" });
    setHoverPreview(null);
  };

  // Fetch live-page DOM candidates for a given (failed) selector and
  // surface them in the Edit modal as one-click suggestions.
  const fetchSelectorSuggestions = async () => {
    if (!editingStep || !sessionId) return;
    const failed = (editingStep.draft.selector || "").trim();
    if (!failed) {
      toast.error("Enter a selector first (or paste the failed one) before suggesting alternatives.");
      return;
    }
    setSelectorSuggest({ loading: true, items: null, error: "" });
    try {
      const r = await fetch(
        `${API_URL}/api/visual-recorder/${sessionId}/suggest-selectors?failed=${encodeURIComponent(failed)}&limit=10`,
        { headers: authH() },
      );
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setSelectorSuggest({ loading: false, items: [], error: d.detail || "Suggest failed" });
        return;
      }
      const items = d.suggestions || [];
      setSelectorSuggest({ loading: false, items, error: items.length === 0 ? "No similar elements found on the live page." : "" });
    } catch (e) {
      setSelectorSuggest({ loading: false, items: [], error: e.message || "Suggest failed" });
    }
  };

  // Apply a clicked suggestion → write into the Edit-modal selector field.
  const applySuggestion = (sel) => {
    if (!editingStep) return;
    setEditingStep({
      ...editingStep,
      draft: { ...editingStep.draft, selector: sel },
    });
    toast.success("Selector updated — review and Save");
  };

  // Hover-preview: fetch the bounding box of `selector` from the live
  // page and stash it so the screenshot overlay renders a blue pulse.
  // Debounced via a tiny ref so quick hovers across the list don't
  // hammer the backend.
  const previewFetchRef = useRef(0);
  const showSelectorPreview = async (selector) => {
    if (!sessionId || !selector) return;
    const myReq = ++previewFetchRef.current;
    try {
      const r = await fetch(
        `${API_URL}/api/visual-recorder/${sessionId}/selector-bbox?selector=${encodeURIComponent(selector)}`,
        { headers: authH() },
      );
      const d = await r.json().catch(() => ({}));
      // Discard if another hover already fired after this one
      if (myReq !== previewFetchRef.current) return;
      if (r.ok && d.found) {
        setHoverPreview({
          x: d.x, y: d.y, width: d.width, height: d.height,
          viewport: d.viewport || { width: viewport.width, height: viewport.height },
          selector,
        });
      } else {
        setHoverPreview(null);
      }
    } catch {
      setHoverPreview(null);
    }
  };

  const clearSelectorPreview = () => {
    previewFetchRef.current++;   // invalidate any in-flight request
    setHoverPreview(null);
  };

  // ── Smart Error → Fix Suggester (2026-01) ────────────────────────
  // Parses common Playwright / replay errors and returns a friendly
  // explanation + a recommended next action the user can take from the
  // Live Test results panel. Returns null when no rule matches (raw
  // error is then shown verbatim).
  const getSuggestedFix = (errorMsg, action, failedIdx) => {
    if (!errorMsg) return null;
    const e = String(errorMsg).toLowerCase();

    // 1. Execution context destroyed (navigation during evaluate / click)
    if (e.includes("execution context") || e.includes("context was destroyed")) {
      return {
        cause: "JavaScript ran a click that navigated the page mid-evaluate. The replay engine has been updated to swallow this safely — most likely just needs a re-run.",
        fix: "Click Re-run Live Test. If it persists, the JS may be navigating before doing all its work — split into two steps (one to click, one to wait_for_navigation).",
        action: "rerun",
      };
    }

    // 2. Selector exhausted (smart_wait gave up)
    if (e.includes("exhausted") && e.includes("selector variants")) {
      return {
        cause: "The recorded selector — and all auto-derived fallbacks — no longer match anything on the page. The site likely renamed this form field.",
        fix: typeof failedIdx === "number"
          ? `Open the Edit modal (✏️) on step #${failedIdx + 1}, click "Find similar" — Krexion will scan the live page and suggest the new selector. Saved as a permanent alias for future runs.`
          : "Edit the failing step and use Find similar to pick the correct selector. Save = permanent alias.",
        action: "edit",
        edit_idx: failedIdx,
      };
    }

    // 3. Generic timeout on wait_for_selector
    if (e.includes("timeout") && (e.includes("wait_for_selector") || e.includes("waiting for"))) {
      return {
        cause: "Element didn't appear within the step's timeout — page may be slow, or the selector is wrong, or the element is hidden behind a custom UI.",
        fix: "Edit the step: (a) increase timeout (e.g., 8000 → 20000), (b) change State to 'attached' if the element is hidden, OR (c) Find similar if the selector is stale.",
        action: "edit",
        edit_idx: failedIdx,
      };
    }

    // 4. Element not visible / not stable
    if (e.includes("not visible") || e.includes("element is not stable") || e.includes("element is outside of the viewport")) {
      return {
        cause: "Element exists in the DOM but is hidden (display:none) or being animated/transformed when we tried to act on it.",
        fix: "In Edit modal, change State to 'attached' (DOM-only). For check/select on hidden inputs, this usually fixes it instantly.",
        action: "edit",
        edit_idx: failedIdx,
      };
    }

    // 5. Net errors / navigation timeout
    if (e.includes("net::") || e.includes("err_") || e.includes("navigation timeout") || e.includes("page.goto")) {
      return {
        cause: "Page failed to load — proxy issue, DNS failure, target site down, or strict CAPTCHA before content.",
        fix: "Verify the URL works in a normal browser. If using a proxy, try without it first. Try a different proxy region. Increase the goto timeout if the page is just slow.",
        action: "rerun",
      };
    }

    // 6. Captcha
    if (e.includes("captcha")) {
      return {
        cause: "The page is showing a CAPTCHA challenge before our automation could proceed.",
        fix: "Some offers show CAPTCHA only on specific proxies/UAs. Switch proxy region or User-Agent. Add a 'wait' step to give the page time to settle. Consider AdsPower profiles for fingerprint-resistant runs.",
        action: "rerun",
      };
    }

    // 7. Target / browser closed
    if (e.includes("target closed") || e.includes("browser has been closed") || e.includes("connection closed")) {
      return {
        cause: "Browser session ended unexpectedly — usually a memory pressure event or the recorder session expired.",
        fix: "Discard this session and start a fresh recording. Steps already saved are NOT lost — they remain in your sample data.",
        action: "restart",
      };
    }

    // 8. Frame detached
    if (e.includes("frame was detached") || e.includes("frame got detached")) {
      return {
        cause: "An iframe holding the element was removed mid-action. Common on SPA-style pages that swap content.",
        fix: "Add a small 'wait' (1000ms) step BEFORE the failing step so the frame has time to mount stably.",
        action: "manual_add",
      };
    }

    // 9. Generic fill / type fail
    if (action === "fill" || action === "type") {
      return {
        cause: "Could not type into the input. Either the selector is wrong, the field is read-only/disabled, or a different element is intercepting focus.",
        fix: "Edit step → Find similar (may have renamed) OR try uncheck 'Human-like typing' (some pages reject character-by-character input).",
        action: "edit",
        edit_idx: failedIdx,
      };
    }

    return null;
  };

  // ── Manual Add Step (2026-01) ────────────────────────────────────
  // Opens a creation modal so the user can author a step by hand
  // (action + selector + value + timeout). Accepts both CSS and XPath.
  const openManualAddStep = () => {
    setManualStepDraft({
      action: "wait_for_selector",
      selector: "",
      value: "",
      timeout: "8000",
      key: "",
      ms: "1000",
      state: "visible",
      match_by: "label",
      humanize: true,
      name: "",
      position: "",   // empty = append to end
    });
  };

  const cancelManualAddStep = () => setManualStepDraft(null);

  // ── Selector Aliases panel (2026-01) ─────────────────────────────
  // Opens a read-only list of every selector rename the user has
  // accumulated across all their recordings. Each entry is one-click
  // deletable in case the user wants to revoke a past self-heal rule.
  const openAliasesPanel = async () => {
    setAliasesPanel({ loading: true, items: [], error: "" });
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/aliases`, {
        headers: authH(),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setAliasesPanel({ loading: false, items: [], error: d.detail || "Failed to load aliases" });
        return;
      }
      setAliasesPanel({ loading: false, items: d.aliases || [], error: "" });
    } catch (e) {
      setAliasesPanel({ loading: false, items: [], error: e.message || "Failed to load" });
    }
  };

  const closeAliasesPanel = () => setAliasesPanel(null);

  const deleteAlias = async (domain, original) => {
    try {
      const r = await fetch(
        `${API_URL}/api/visual-recorder/aliases?domain=${encodeURIComponent(domain)}&original=${encodeURIComponent(original)}`,
        { method: "DELETE", headers: authH() },
      );
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.deleted) {
        toast.error(d.detail || "Delete failed");
        return;
      }
      toast.success("Alias removed");
      // Refresh the panel
      openAliasesPanel();
    } catch (e) {
      toast.error(e.message || "Delete failed");
    }
  };

  const saveManualAddStep = async () => {
    if (!manualStepDraft || !sessionId) return;
    const d = manualStepDraft;
    const action = (d.action || "").toLowerCase();
    // Build clean step payload based on action
    const step = { action };
    if (d.name && d.name.trim()) step.name = d.name.trim();
    if (["wait_for_selector", "click", "fill", "type", "select", "hover", "check", "uncheck", "press"].includes(action)) {
      if (!d.selector || !d.selector.trim()) {
        toast.error("Selector is required for this action");
        return;
      }
      step.selector = d.selector.trim();
    }
    if (["fill", "type", "select"].includes(action)) {
      step.value = d.value || "";
      step.timeout = d.timeout === "" ? 8000 : Number(d.timeout);
      if (action !== "select") step.humanize = !!d.humanize;
      if (action === "select" && d.match_by) step.match_by = d.match_by;
    } else if (action === "wait_for_selector") {
      step.timeout = d.timeout === "" ? 8000 : Number(d.timeout);
      if (d.state) step.state = d.state;
    } else if (action === "wait") {
      step.ms = d.ms === "" ? 1000 : Number(d.ms);
    } else if (action === "press") {
      if (!d.key || !d.key.trim()) {
        toast.error("Key is required (e.g., Enter, Tab, Escape)");
        return;
      }
      step.key = d.key.trim();
      if (d.selector) step.selector = d.selector.trim();
    } else if (["click", "hover", "check", "uncheck"].includes(action)) {
      step.timeout = d.timeout === "" ? 8000 : Number(d.timeout);
    }

    const body = { step };
    if (d.position !== "" && d.position != null && !isNaN(Number(d.position))) {
      body.position = Math.max(0, Number(d.position) - 1); // user enters 1-based
    }

    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/manual-step`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify(body),
      });
      const dr = await r.json().catch(() => ({}));
      if (!r.ok || dr.added === false) {
        toast.error(dr.detail || dr.reason || "Add step failed");
        return;
      }
      toast.success(`Manual step added at #${(dr.index ?? 0) + 1}`);
      setManualStepDraft(null);
      refreshState();
    } catch (e) {
      toast.error(e.message || "Add step failed");
    }
  };

  const saveEditStep = async () => {
    if (!editingStep || !sessionId) return;
    const { index, draft } = editingStep;
    // Build patch payload — only include fields relevant to this action
    // so we don't write empty strings into steps that never had them.
    const patch = {};
    const action = (draft.action || "").toLowerCase();
    if (draft.selector !== undefined) patch.selector = draft.selector;
    if (draft.name !== undefined) patch.name = draft.name;
    if (action === "fill" || action === "type" || action === "select") {
      patch.value = draft.value;
      patch.timeout = draft.timeout === "" ? 0 : Number(draft.timeout);
      if (action !== "select") patch.humanize = !!draft.humanize;
      if (action === "type" && draft.delay !== "") patch.delay = Number(draft.delay);
      if (action === "select" && draft.match_by) patch.match_by = draft.match_by;
    } else if (action === "wait_for_selector") {
      patch.timeout = draft.timeout === "" ? 0 : Number(draft.timeout);
      if (draft.state) patch.state = draft.state;
    } else if (action === "wait") {
      if (draft.ms !== "") patch.ms = Number(draft.ms);
    } else if (action === "press") {
      patch.key = draft.key;
      if (draft.selector) patch.selector = draft.selector;
    } else if (action === "click" || action === "hover" || action === "check" || action === "uncheck") {
      patch.timeout = draft.timeout === "" ? 0 : Number(draft.timeout);
    } else {
      // Fallback — pass through whatever non-empty fields the user touched.
      if (draft.value) patch.value = draft.value;
      if (draft.timeout !== "") patch.timeout = Number(draft.timeout);
    }

    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/step/${index}`, {
        method: "PATCH",
        headers: authH(),
        body: JSON.stringify(patch),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || d.updated === false) {
        toast.error(d.detail || d.reason || "Edit failed");
        return;
      }
      toast.success(`Step #${index + 1} updated`);
      if (d.alias_saved) {
        // Self-healing memory — let the user know their fix is now
        // permanent for this domain (future replays will auto-recover).
        toast.success("🧠 Selector alias saved — future runs will auto-heal", {
          duration: 5000,
          description: `Krexion will remember this rename for future recordings on this site.`,
        });
      }
      setEditingStep(null);
      refreshState();
    } catch (e) {
      toast.error(e.message || "Edit failed");
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
  // ── 2026-05: Live Test + Diagnostics ─────────────────────────────
  // Runs the current recorded steps end-to-end (fresh page in same
  // browser context) and shows per-step timing + pass/fail + a Smart
  // Replay Diagnostics summary. User can iterate the recording until
  // every step passes before finalising the JSON.
  const runLiveTest = async (opts = {}) => {
    if (!sessionId) return;
    if (!steps || steps.length === 0) {
      toast.error("Record at least one step first.");
      return;
    }
    // 2026-01: "Replay from here" — `opts.startIndex` skips the first
    // N steps and forces fresh_page=false so the browser stays on its
    // current state (post-previous-failure page).
    const startIndex = Math.max(0, Number(opts.startIndex || 0));
    const freshPage = startIndex > 0 ? false : true;
    setLiveTesting(true);
    setLiveTestResult(null);
    // 2026-01: real-time progress feed — clear & start polling
    setLiveProgress([]);
    setLiveFrame(null);
    setLiveFrameMeta(null);
    let sinceIdx = 0;
    const pollProgress = async () => {
      try {
        const r = await fetch(
          `${API_URL}/api/visual-recorder/${sessionId}/live-progress?since=${sinceIdx}`,
          { headers: authH() }
        );
        if (!r.ok) return;
        const d = await r.json();
        if (Array.isArray(d.events) && d.events.length > 0) {
          sinceIdx = d.total_events;
          // 2026-01: pick most recent event that has a screenshot
          // (most actions emit one; some lightweight events skip it)
          for (let i = d.events.length - 1; i >= 0; i--) {
            const e = d.events[i];
            if (e && e.screenshot_b64) {
              setLiveFrame(e.screenshot_b64);
              setLiveFrameMeta({
                idx: e.idx,
                action: e.action,
                selector: e.selector,
                status: e.status,
                page_url: e.page_url,
                ms: e.ms,
              });
              break;
            }
          }
          // Strip screenshot_b64 from the array before keeping in
          // memory to avoid bloating React state.
          const lite = d.events.map((e) => {
            if (!e || !e.screenshot_b64) return e;
            // eslint-disable-next-line no-unused-vars
            const { screenshot_b64, ...rest } = e;
            return rest;
          });
          setLiveProgress((prev) => [...prev, ...lite].slice(-200));
        }
        return d.running;
      } catch {
        return null;
      }
    };
    // Start polling every 400ms
    const pollTimer = setInterval(async () => {
      const stillRunning = await pollProgress();
      // Auto-stop polling if backend says it's finished (but keep one
      // last poll to drain final events)
      if (stillRunning === false) {
        await pollProgress();
        clearInterval(pollTimer);
      }
    }, 400);

    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/live-test`, {
        method: "POST",
        headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ fresh_page: freshPage, start_index: startIndex }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      setLiveTestResult(d);
      if (d.ok) {
        const range = startIndex > 0
          ? ` (resumed from step #${startIndex + 1})`
          : "";
        toast.success(`Live test PASSED — ${d.executed_steps}/${d.total_steps} steps in ${(d.total_ms / 1000).toFixed(1)}s${range}`);
      } else {
        toast.error(
          d.error
            ? `Live test FAILED at step #${(d.failed_at_idx ?? 0) + 1}: ${d.error.slice(0, 120)}`
            : "Live test failed."
        );
      }
    } catch (e) {
      toast.error(`Live test crashed: ${e.message || e}`);
    } finally {
      // Drain final progress events, then stop polling
      try { await pollProgress(); } catch {}
      clearInterval(pollTimer);
      setLiveTesting(false);
    }
  };

  // ── 2026-05: Auto-fix one or all anti-pattern findings ───────────
  // Applies a structured fix (or all auto-fixable fixes in one shot)
  // to the recorder session. Re-fetches steps + diagnostics on
  // success so the UI re-renders with the post-fix state.
  //
  // 2026-05 update: also tracks `fix_history_count` from the response
  // (powers the Undo button) and, when `autoRetestEnabled` is on,
  // automatically triggers Run Live Test after the fix succeeds — so
  // the full loop becomes: Live Test → Auto-fix all → (auto Live Test) →
  // Finalize. Three clicks total.
  const applyAutoFix = async ({ kind, at_step, extra } = {}, applyAll = false) => {
    if (!sessionId) return;
    setLiveTesting(true);
    try {
      const body = applyAll ? { apply_all: true } : { kind, at_step, extra };
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/auto-fix`, {
        method: "POST",
        headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);

      if (Array.isArray(d.steps)) setSteps(d.steps);
      if (typeof d.fix_history_count === "number") setFixHistoryCount(d.fix_history_count);
      setLastUndoneFix(null); // any new fix invalidates the "last undone" hint

      if (liveTestResult) {
        setLiveTestResult({
          ...liveTestResult,
          diagnostics: d.diagnostics || liveTestResult.diagnostics,
        });
      }

      const nApplied = (d.applied || []).length;
      const nSkipped = (d.skipped || []).length;
      if (applyAll) {
        toast.success(
          nApplied > 0
            ? `Auto-fix applied ${nApplied} fix${nApplied === 1 ? "" : "es"}${nSkipped ? ` · ${nSkipped} skipped` : ""}.`
            : "Nothing to fix — all anti-patterns are non-auto-fixable.",
        );
      } else {
        toast.success(d.applied?.[0]?.summary || "Auto-fix applied.");
      }

      // Auto-retest: if enabled and we actually applied at least one
      // fix, immediately re-run Live Test so the user sees the result
      // of the fix without another click.
      if (autoRetestEnabled && nApplied > 0) {
        // Brief pause so the toast registers + steps state propagates
        // through React before the next fetch fires.
        setTimeout(() => { runLiveTest(); }, 400);
      }
    } catch (e) {
      toast.error(`Auto-fix failed: ${e.message || e}`);
    } finally {
      setLiveTesting(false);
    }
  };

  // ── 2026-05: Undo last auto-fix ──────────────────────────────────
  // Pops the most-recent fix from history and restores the pre-fix
  // snapshot of the steps array. Used when an auto-fix turned out to
  // break something specific to the user's page that the static
  // analyser couldn't predict.
  const undoLastAutoFix = async () => {
    if (!sessionId || fixHistoryCount === 0) return;
    setLiveTesting(true);
    try {
      const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/auto-fix/undo`, {
        method: "POST",
        headers: authH(),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);

      if (Array.isArray(d.steps)) setSteps(d.steps);
      if (typeof d.fix_history_count === "number") setFixHistoryCount(d.fix_history_count);
      setLastUndoneFix(d.undone || null);
      if (liveTestResult) {
        setLiveTestResult({
          ...liveTestResult,
          diagnostics: d.diagnostics || liveTestResult.diagnostics,
        });
      }
      const k = d.undone?.kind || "last fix";
      toast.success(`Undone: ${k}. Run Live Test to re-verify.`);
    } catch (e) {
      toast.error(`Undo failed: ${e.message || e}`);
    } finally {
      setLiveTesting(false);
    }
  };

  const saveToLibrary = async () => {
    if (!finalBundle) return;
    // ── 2026-05: Edit-mode → PATCH the original upload instead of
    // POSTing a new one. Preserves upload_id (every RUT campaign that
    // already references this template keeps working) and updates the
    // step_count badge automatically.
    if (editUploadId && editTemplate) {
      if (!window.confirm(
        `Update existing template "${editTemplate.name}" with the edited recording?\n\n` +
        `Step count will go from ${editTemplate.item_count || 0} → ${finalBundle.step_count}. ` +
        `Every saved RUT campaign that references this template will use the new version on its next run.`,
      )) return;
      setSaving(true);
      try {
        const fd = new FormData();
        fd.append("name", editTemplate.name);
        fd.append("automation_json", JSON.stringify(finalBundle.automation_json));
        if (editTemplate.description) {
          fd.append("description", editTemplate.description);
        }
        const r = await fetch(
          `${API_URL}/api/uploads/automation-json/${editUploadId}`,
          {
            method: "PATCH",
            headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
            body: fd,
          },
        );
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        setSavedToLibraryId(d.id || editUploadId);
        toast.success(`Updated "${editTemplate.name}" — every campaign using this template will pick up the new version automatically.`);
      } catch (e) {
        toast.error(`Update failed: ${e.message || e}`);
      } finally {
        setSaving(false);
      }
      return;
    }
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

  // ── JSON inline edit (2026-01) ──────────────────────────────────
  // On the Recording Complete page, lets the user toggle the JSON
  // preview into an editable textarea, fix anything by hand
  // (selectors, timeouts, add/remove steps), then save back into the
  // `finalBundle` so the Copy/Download/Save-to-Library + Live Visual
  // Test buttons all use the edited version. Validates the JSON is a
  // non-empty array of step objects.
  const openJsonEditor = () => {
    if (!finalBundle) return;
    setEditingJsonText(JSON.stringify(finalBundle.automation_json, null, 2));
    setEditingJsonError("");
    setEditingJson(true);
  };

  const cancelJsonEditor = () => {
    setEditingJson(false);
    setEditingJsonError("");
  };

  const saveJsonEditor = () => {
    let parsed;
    try {
      parsed = JSON.parse(editingJsonText);
    } catch (e) {
      setEditingJsonError(`Invalid JSON: ${e.message}`);
      return;
    }
    if (!Array.isArray(parsed)) {
      setEditingJsonError("JSON must be an array of step objects (e.g., [{...}, {...}])");
      return;
    }
    if (parsed.length === 0) {
      setEditingJsonError("Steps array cannot be empty");
      return;
    }
    // Per-step lightweight validation
    for (let i = 0; i < parsed.length; i++) {
      const s = parsed[i];
      if (!s || typeof s !== "object") {
        setEditingJsonError(`Step ${i + 1} is not an object`);
        return;
      }
      if (!s.action || typeof s.action !== "string") {
        setEditingJsonError(`Step ${i + 1} is missing 'action' (string)`);
        return;
      }
    }
    setFinalBundle({
      ...finalBundle,
      automation_json: parsed,
      step_count: parsed.length,
    });
    setEditingJson(false);
    setEditingJsonError("");
    toast.success(`JSON updated — ${parsed.length} steps`);
    if (savedToLibraryId) {
      toast.info("Tip: Re-click 'Save to Library' to update the saved template with these edits.", { duration: 6000 });
    }
  };

  // ── Live Visual Test on finalized bundle (2026-01) ───────────────
  // Re-opens a fresh recorder session with the saved URL / proxy / UA,
  // imports the finalized JSON, then drops the UI back into recording
  // mode so the existing "Run Live Test from Start" button + live
  // screenshot polling shows the full automation step-by-step. Any
  // failure surfaces the Smart Fix suggester so the user can edit
  // problematic steps and re-test — and on Finalize again, the
  // updated steps are exported.
  const launchVisualReplay = async () => {
    if (!finalBundle) return;
    if (!finalBundle.url) {
      toast.error("Cannot replay — original URL is missing from the bundle");
      return;
    }
    setReplayLaunching(true);
    try {
      // 1. Start a fresh recorder session with the same params
      const startRes = await fetch(`${API_URL}/api/visual-recorder/start`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({
          url: finalBundle.url,
          proxy: finalBundle.proxy || null,
          user_agent: finalBundle.user_agent || null,
          headers: finalBundle.headers || [],
          sample_row: Object.keys(sampleRow || {}).length ? sampleRow : null,
        }),
      });
      const startData = await startRes.json();
      if (!startRes.ok) {
        throw new Error(startData.detail || `Failed to start replay session: HTTP ${startRes.status}`);
      }
      const newSid = startData.session_id;

      // 2. Poll until ready (max ~30s)
      let ready = false;
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 500));
        const sr = await fetch(`${API_URL}/api/visual-recorder/${newSid}/state`, { headers: authH() });
        const sd = await sr.json().catch(() => ({}));
        if (sd.state === "ready") { ready = true; break; }
        if (sd.state === "error") {
          throw new Error(sd.error_msg || "Replay session failed to start");
        }
      }
      if (!ready) {
        throw new Error("Replay session timed out while loading the page");
      }

      // 3. Import the saved steps into the new session
      const impRes = await fetch(`${API_URL}/api/visual-recorder/${newSid}/import-steps`, {
        method: "POST",
        headers: authH(),
        body: JSON.stringify({
          steps: finalBundle.automation_json,
          sample_row: Object.keys(sampleRow || {}).length ? sampleRow : null,
          headers: finalBundle.headers || [],
        }),
      });
      const impData = await impRes.json();
      if (!impRes.ok || impData.imported === false) {
        throw new Error(impData.detail || impData.reason || "Failed to import steps");
      }

      // 4. Transition UI back into recording mode with the imported state
      setSessionId(newSid);
      setSessionState("ready");
      setSteps(finalBundle.automation_json);
      setUrl(finalBundle.url);
      setProxy(finalBundle.proxy || "");
      setUa(finalBundle.user_agent || "");
      setHeaders(finalBundle.headers || []);
      setFinalBundle(null);
      setEditingJson(false);
      setSetupStage("recording");
      toast.success(`Replay session ready — ${impData.total} steps loaded. Click "Run Live Test from Start" to watch the full flow.`, { duration: 6000 });
    } catch (e) {
      toast.error(`Visual replay failed: ${e.message || e}`);
    } finally {
      setReplayLaunching(false);
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
                {/* ── 2026-01: Minimize button ──────────────────────
                    Keeps the recorder ALIVE in the background and
                    returns the user to the setup screen, where they
                    can start a 2nd / 3rd recorder OR switch to any
                    other running session via the Active Sessions
                    panel. Standard "minimize to background" flow. */}
                {sessionId && (
                  <button
                    onClick={() => {
                      setSetupStage("setup");
                      toast.success("Recorder minimized — still running in background. Reopen from \"Active recorder sessions\" panel.", { duration: 4500 });
                    }}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 hover:text-emerald-300 transition-colors"
                    data-testid="vr-minimize-btn"
                    title="Minimize (keeps session alive in background, lets you start another)"
                  >
                    <ArrowLeft className="w-3 h-3" />
                    Minimize
                  </button>
                )}
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
            {/* ── 2026-01: Active Sessions panel ────────────────────
                Shows every recorder this user has running right now
                so the 5-concurrent cap is never a mystery. Each row
                lets the user OPEN (switch to / minimize current) or
                STOP a session. */}
            {activeSessions.length > 0 && (
              <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-700/30" data-testid="vr-active-sessions-panel">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-emerald-200">
                    <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
                    Active recorder sessions
                    <span
                      className={`ml-1 text-[11px] px-1.5 py-0.5 rounded ${
                        activeSessionStats.user_session_count >= activeSessionStats.max_concurrent
                          ? "bg-rose-700/40 border border-rose-500/40 text-rose-200"
                          : "bg-emerald-700/40 border border-emerald-500/40 text-emerald-200"
                      }`}
                      data-testid="vr-active-count"
                    >
                      {activeSessionStats.user_session_count}/{activeSessionStats.max_concurrent} in use
                    </span>
                  </div>
                  <button
                    onClick={refreshActiveSessions}
                    className="text-[11px] text-zinc-500 hover:text-emerald-300 inline-flex items-center gap-1"
                    data-testid="vr-active-refresh"
                    title="Refresh list"
                  >
                    <RefreshCw className="w-3 h-3" /> refresh
                  </button>
                </div>
                <div className="space-y-2">
                  {activeSessions.map((s) => {
                    const hostname = (() => {
                      try { return new URL(s.current_url || s.url).hostname; } catch { return (s.url || "").slice(0, 40); }
                    })();
                    const stateColor =
                      s.state === "ready"
                        ? "bg-emerald-700/40 border-emerald-500/40 text-emerald-200"
                        : s.state === "error"
                        ? "bg-rose-700/40 border-rose-500/40 text-rose-200"
                        : "bg-amber-700/40 border-amber-500/40 text-amber-200";
                    const stateLabel =
                      s.state === "ready" ? "REC" :
                      s.state === "error" ? "ERROR" :
                      s.state === "starting" ? "CONNECTING" :
                      String(s.state || "").toUpperCase();
                    const mins = Math.floor((s.elapsed_seconds || 0) / 60);
                    const secs = (s.elapsed_seconds || 0) % 60;
                    const elapsedStr = `${String(mins).padStart(2,"0")}:${String(secs).padStart(2,"0")}`;
                    return (
                      <div
                        key={s.session_id}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-zinc-900/70 border border-zinc-800 hover:border-emerald-600/40 transition-colors"
                        data-testid={`vr-active-session-${s.session_id}`}
                      >
                        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold border ${stateColor} shrink-0`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${s.state === "ready" ? "bg-emerald-400 animate-pulse" : s.state === "error" ? "bg-rose-400" : "bg-amber-400 animate-pulse"}`} />
                          {stateLabel}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-zinc-200 truncate font-medium" title={s.current_url || s.url}>
                            <Globe className="w-3 h-3 inline mr-1 text-emerald-400" />
                            {hostname}
                          </div>
                          <div className="text-[10px] text-zinc-500 flex items-center gap-2 mt-0.5">
                            <span title="Recording elapsed time"><Clock className="w-2.5 h-2.5 inline mr-0.5" />{elapsedStr}</span>
                            <span>·</span>
                            <span>{s.step_count} step{s.step_count === 1 ? "" : "s"}</span>
                            <span>·</span>
                            <span className="font-mono text-[9px] text-zinc-600" title="Session ID">{(s.session_id || "").slice(0, 8)}</span>
                          </div>
                          {s.state === "error" && s.error_message && (
                            <div className="text-[10px] text-rose-400/80 mt-0.5 truncate" title={s.error_message}>
                              {s.error_message.split("\n")[0].slice(0, 90)}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => switchToSession(s)}
                          className="px-2.5 py-1 rounded-md bg-emerald-700/40 hover:bg-emerald-600/60 border border-emerald-500/40 text-emerald-200 text-xs font-medium inline-flex items-center gap-1 transition-colors shrink-0"
                          data-testid={`vr-active-open-${s.session_id}`}
                          title="Switch to this session"
                        >
                          <Play className="w-3 h-3" /> Open
                        </button>
                        <button
                          onClick={() => stopSessionById(s.session_id, hostname)}
                          className="px-2.5 py-1 rounded-md bg-rose-700/40 hover:bg-rose-600/60 border border-rose-500/40 text-rose-200 text-xs font-medium inline-flex items-center gap-1 transition-colors shrink-0"
                          data-testid={`vr-active-stop-${s.session_id}`}
                          title="Stop this session (frees a slot)"
                        >
                          <Square className="w-3 h-3" /> Stop
                        </button>
                      </div>
                    );
                  })}
                </div>
                {activeSessionStats.user_session_count >= activeSessionStats.max_concurrent && (
                  <div className="mt-3 text-[11px] text-amber-300 bg-amber-950/30 border border-amber-700/40 rounded-md px-3 py-2">
                    ⚠️ You've hit the max ({activeSessionStats.max_concurrent}) concurrent recorders. Stop one above to start a new recording, or click <b>Open</b> to continue an existing one.
                  </div>
                )}
              </div>
            )}

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

            <div className="md:col-span-2 flex flex-col items-center gap-3">
              {/* 2026-05: Edit-mode banner — visible whenever the page
                  was opened via `?edit_upload_id=X`. Tells the user
                  EXACTLY what will happen when they click Start. */}
              {editUploadId && (
                <div
                  className="w-full max-w-2xl rounded-xl border border-indigo-500/40 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-200 flex items-start gap-3"
                  data-testid="vr-edit-mode-banner"
                >
                  <Pencil className="w-5 h-5 shrink-0 mt-0.5 text-indigo-300" />
                  <div className="flex-1">
                    <div className="font-semibold mb-0.5 text-indigo-100">
                      Editing template: {editTemplate?.name || "(loading…)"}
                    </div>
                    <div className="text-xs text-indigo-200/80 leading-relaxed">
                      Click <b>Start Recording</b> below — your existing{" "}
                      <b>{editTemplate?.item_count ?? "…"} steps</b> will load
                      automatically. You can re-record over them, reorder, fix
                      selectors live, delete, or append new steps. Saving will
                      update this SAME template (upload ID preserved → every
                      RUT campaign using it keeps working).
                    </div>
                  </div>
                </div>
              )}
              <button
                onClick={startRecording}
                disabled={busy || (editUploadId ? !editTemplate : !url.trim())}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-medium text-base transition-colors shadow-lg shadow-emerald-900/30"
                data-testid="vr-start-btn"
              >
                {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                {editUploadId ? "Start Editing (loads existing steps)" : "Start Recording"}
              </button>
              {editUploadId && !url.trim() && (
                <p className="text-[11px] text-zinc-500 max-w-md text-center mt-1">
                  No URL — recorder will open <code className="text-zinc-400">about:blank</code>.
                  You can still reorder / edit / delete / append steps. To add
                  new <em>recorded clicks</em>, type the offer URL above or
                  use the Navigate box after the session starts.
                </p>
              )}
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

                {/* ── Selector hover-preview overlay (2026-01) ────────
                    Drawn when the user hovers a suggestion in the
                    Edit-modal's "Find similar" panel. Position is
                    percent-based on viewport so it stays aligned even
                    if the screenshot is responsively scaled. */}
                {hoverPreview && hoverPreview.viewport?.width > 0 && (
                  <>
                    {/* Outer pulse ring */}
                    <div
                      className="absolute pointer-events-none animate-ping rounded-sm"
                      style={{
                        left: `${(hoverPreview.x / hoverPreview.viewport.width) * 100}%`,
                        top: `${(hoverPreview.y / hoverPreview.viewport.height) * 100}%`,
                        width: `${(hoverPreview.width / hoverPreview.viewport.width) * 100}%`,
                        height: `${(hoverPreview.height / hoverPreview.viewport.height) * 100}%`,
                        boxShadow: "0 0 0 3px rgba(59, 130, 246, 0.5)",
                        backgroundColor: "rgba(59, 130, 246, 0.10)",
                      }}
                    />
                    {/* Solid outline + label badge */}
                    <div
                      className="absolute pointer-events-none rounded-sm transition-all duration-150"
                      style={{
                        left: `${(hoverPreview.x / hoverPreview.viewport.width) * 100}%`,
                        top: `${(hoverPreview.y / hoverPreview.viewport.height) * 100}%`,
                        width: `${(hoverPreview.width / hoverPreview.viewport.width) * 100}%`,
                        height: `${(hoverPreview.height / hoverPreview.viewport.height) * 100}%`,
                        outline: "2px solid rgb(59, 130, 246)",
                        outlineOffset: "0px",
                        backgroundColor: "rgba(59, 130, 246, 0.12)",
                        boxShadow: "0 0 12px 2px rgba(59, 130, 246, 0.6)",
                      }}
                    >
                      <div
                        className="absolute -top-5 left-0 px-1.5 py-0.5 rounded-sm bg-blue-600 text-white text-[10px] font-mono whitespace-nowrap shadow-lg"
                        data-testid="vr-hover-preview-label"
                      >
                        {hoverPreview.selector}
                      </div>
                    </div>
                  </>
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
                        // 2026-05: `close_browser` is an instant-action
                        // tool — there's nothing to "click on the page"
                        // for it. Fire the insert immediately and snap
                        // back to the default tool so the operator can
                        // keep recording without an extra step.
                        if (t.id === "close_browser") {
                          (async () => {
                            setBusy(true);
                            try {
                              const r = await fetch(`${API_URL}/api/visual-recorder/${sessionId}/close-browser-step`, {
                                method: "POST",
                                headers: authH(),
                              });
                              const d = await r.json();
                              if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
                              toast.success("🔌 Close-browser step inserted");
                              refreshState();
                            } catch (err) {
                              toast.error(`Insert close failed: ${err.message || err}`);
                            } finally {
                              setBusy(false);
                            }
                          })();
                          return;
                        }
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
                  <button
                    onClick={addWaitForText}
                    disabled={sessionState !== "ready"}
                    title="Wait until specific text appears on the page (e.g. 'Thank you')"
                    className="px-2 py-1 rounded bg-zinc-800 hover:bg-emerald-700/40 border border-zinc-700 hover:border-emerald-500/40 text-zinc-300 text-[10px] disabled:opacity-40"
                    data-testid="vr-wait-text-btn"
                  >
                    💬 Wait for text
                  </button>
                  <button
                    onClick={addWaitForUrl}
                    disabled={sessionState !== "ready"}
                    title="Wait until URL contains a pattern (e.g. '/thank-you')"
                    className="px-2 py-1 rounded bg-zinc-800 hover:bg-cyan-700/40 border border-zinc-700 hover:border-cyan-500/40 text-zinc-300 text-[10px] disabled:opacity-40"
                    data-testid="vr-wait-url-btn"
                  >
                    🔗 Wait for URL
                  </button>
                  <button
                    onClick={addExtract}
                    disabled={sessionState !== "ready"}
                    title="Extract text/attribute into a variable usable later with {{var_name}}"
                    className="px-2 py-1 rounded bg-zinc-800 hover:bg-purple-700/40 border border-zinc-700 hover:border-purple-500/40 text-zinc-300 text-[10px] disabled:opacity-40"
                    data-testid="vr-extract-btn"
                  >
                    📋 Extract var
                  </button>
                  <button
                    onClick={addDismissPopups}
                    disabled={sessionState !== "ready"}
                    title="Auto-dismiss cookie/GDPR banners and popups"
                    className="px-2 py-1 rounded bg-zinc-800 hover:bg-amber-700/40 border border-zinc-700 hover:border-amber-500/40 text-zinc-300 text-[10px] disabled:opacity-40"
                    data-testid="vr-dismiss-popups-btn"
                  >
                    🍪 Dismiss popups
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
                <div className="flex items-center gap-1">
                  <button
                    onClick={runLint}
                    title="Pre-flight lint — checks for missing selectors, invalid actions, hard-waits >30s, etc."
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-zinc-800 hover:bg-emerald-700/40 border border-zinc-700 hover:border-emerald-500/40 text-zinc-300 hover:text-emerald-200 transition-colors"
                    data-testid="vr-lint-btn"
                  >
                    ✓ Lint
                  </button>
                  <button
                    onClick={openAliasesPanel}
                    title="View self-healing selector aliases (saved automatically when you fix wrong selectors)"
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-zinc-800 hover:bg-fuchsia-700/40 border border-zinc-700 hover:border-fuchsia-500/40 text-zinc-300 hover:text-fuchsia-200 transition-colors"
                    data-testid="vr-aliases-btn"
                  >
                    <Brain className="w-3 h-3" /> Aliases
                  </button>
                  <button
                    onClick={openManualAddStep}
                    title="Add a step manually (CSS / XPath selector + action)"
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-zinc-800 hover:bg-sky-700/40 border border-zinc-700 hover:border-sky-500/40 text-zinc-300 hover:text-sky-200 transition-colors"
                    data-testid="vr-add-manual-step-btn"
                  >
                    <ListPlus className="w-3 h-3" /> Add Step
                  </button>
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
              </div>

              {/* 2026-01: Lint Result Panel */}
              {showLintPanel && lintResult && (
                <div
                  className={`mb-2 p-2 rounded border text-[11px] ${
                    lintResult.ok
                      ? 'bg-emerald-950/30 border-emerald-500/30'
                      : 'bg-rose-950/30 border-rose-500/30'
                  }`}
                  data-testid="vr-lint-panel"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`font-medium ${lintResult.ok ? 'text-emerald-300' : 'text-rose-300'}`}>
                      {lintResult.ok ? '✓ Lint passed' : '⚠ Lint found issues'}
                      <span className="text-zinc-500 ml-2">
                        ({lintResult.summary?.errors || 0} errors,
                        {' '}{lintResult.summary?.warnings || 0} warnings,
                        {' '}{lintResult.summary?.infos || 0} info)
                      </span>
                    </span>
                    <button
                      onClick={() => setShowLintPanel(false)}
                      className="text-zinc-500 hover:text-zinc-300 px-1"
                      data-testid="vr-lint-close"
                    >×</button>
                  </div>
                  {(lintResult.issues || []).length > 0 && (
                    <ul className="space-y-0.5 max-h-32 overflow-y-auto">
                      {lintResult.issues.map((issue, idx) => (
                        <li
                          key={idx}
                          className={`flex items-start gap-1 ${
                            issue.level === 'error'
                              ? 'text-rose-300'
                              : issue.level === 'warn'
                              ? 'text-amber-300'
                              : 'text-zinc-400'
                          }`}
                          data-testid={`vr-lint-issue-${idx}`}
                        >
                          <span className="flex-shrink-0 font-mono">
                            {issue.level === 'error' ? '✗' : issue.level === 'warn' ? '⚠' : 'ℹ'}
                          </span>
                          <span>{issue.message}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
                {steps.length === 0 && (
                  <div className="text-zinc-600 text-xs text-center py-4">No steps yet — click on the preview to record</div>
                )}
                {steps.map((s, i) => {
                  // 2026-01: Step icon + color coding for quick visual scan
                  const stepIconMap = {
                    click: { icon: "👆", color: "text-emerald-400", bg: "bg-emerald-700/30 border-emerald-500/30" },
                    fill: { icon: "✏️", color: "text-sky-400", bg: "bg-sky-700/30 border-sky-500/30" },
                    type: { icon: "⌨️", color: "text-sky-400", bg: "bg-sky-700/30 border-sky-500/30" },
                    select: { icon: "▾", color: "text-purple-400", bg: "bg-purple-700/30 border-purple-500/30" },
                    check: { icon: "☑", color: "text-emerald-400", bg: "bg-emerald-700/30 border-emerald-500/30" },
                    uncheck: { icon: "☐", color: "text-zinc-400", bg: "bg-zinc-700/30 border-zinc-500/30" },
                    wait: { icon: "⏱", color: "text-zinc-400", bg: "bg-zinc-700/30 border-zinc-500/30" },
                    wait_for_selector: { icon: "⏳", color: "text-sky-400", bg: "bg-sky-700/30 border-sky-500/30" },
                    wait_for_load: { icon: "⏳", color: "text-sky-400", bg: "bg-sky-700/30 border-sky-500/30" },
                    wait_for_navigation: { icon: "⏳", color: "text-sky-400", bg: "bg-sky-700/30 border-sky-500/30" },
                    wait_for_networkidle: { icon: "⏳", color: "text-sky-400", bg: "bg-sky-700/30 border-sky-500/30" },
                    wait_for_text: { icon: "💬", color: "text-emerald-400", bg: "bg-emerald-700/30 border-emerald-500/30" },
                    wait_for_url: { icon: "🔗", color: "text-cyan-400", bg: "bg-cyan-700/30 border-cyan-500/30" },
                    extract: { icon: "📋", color: "text-purple-400", bg: "bg-purple-700/30 border-purple-500/30" },
                    dismiss_popups: { icon: "🍪", color: "text-amber-400", bg: "bg-amber-700/30 border-amber-500/30" },
                    screenshot: { icon: "📷", color: "text-amber-400", bg: "bg-amber-700/30 border-amber-500/30" },
                    scroll: { icon: "⇅", color: "text-zinc-400", bg: "bg-zinc-700/30 border-zinc-500/30" },
                    navigate: { icon: "🌐", color: "text-cyan-400", bg: "bg-cyan-700/30 border-cyan-500/30" },
                    goto: { icon: "🌐", color: "text-cyan-400", bg: "bg-cyan-700/30 border-cyan-500/30" },
                    press: { icon: "🔘", color: "text-zinc-400", bg: "bg-zinc-700/30 border-zinc-500/30" },
                    hover: { icon: "🖱", color: "text-zinc-400", bg: "bg-zinc-700/30 border-zinc-500/30" },
                    evaluate: { icon: "⚡", color: "text-yellow-400", bg: "bg-yellow-700/30 border-yellow-500/30" },
                    auto_continue: { icon: "🔄", color: "text-violet-400", bg: "bg-violet-700/30 border-violet-500/30" },
                    auto_continue_survey: { icon: "🔄", color: "text-violet-400", bg: "bg-violet-700/30 border-violet-500/30" },
                  };
                  const sm = stepIconMap[s.action] || { icon: "•", color: "text-zinc-400", bg: "bg-zinc-700/30 border-zinc-500/30" };
                  const isDragSrc = dragSrc === i;
                  const isDragOver = dragOver === i;
                  return (
                  <React.Fragment key={i}>
                    {/* 2026-01: Insert-here button (appears between steps on hover) */}
                    <div
                      className="relative h-1 group/insert"
                      data-testid={`vr-step-insert-zone-${i}`}
                    >
                      <button
                        onClick={() => insertStepAt(i)}
                        title={`Insert a new step BEFORE step #${i + 1}`}
                        className="absolute left-1/2 -translate-x-1/2 -top-1.5 px-1.5 py-0.5 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-[9px] font-bold opacity-0 group-hover/insert:opacity-100 transition-opacity z-10 leading-none"
                        data-testid={`vr-step-insert-before-${i}`}
                      >
                        + insert here
                      </button>
                    </div>
                  <div
                    className={`flex items-start gap-1 p-2 rounded bg-zinc-950 border text-xs hover:border-zinc-700 transition-all group ${
                      isDragSrc ? 'opacity-40 border-emerald-500' :
                      isDragOver ? 'border-emerald-500 bg-emerald-950/30' :
                      'border-zinc-800'
                    }`}
                    draggable
                    onDragStart={(e) => {
                      setDragSrc(i);
                      try { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(i)); } catch {}
                    }}
                    onDragEnd={() => { setDragSrc(null); setDragOver(null); }}
                    onDragOver={(e) => {
                      e.preventDefault();
                      try { e.dataTransfer.dropEffect = "move"; } catch {}
                      if (dragOver !== i) setDragOver(i);
                    }}
                    onDragLeave={(e) => {
                      // Only clear if leaving the entire element (not entering a child)
                      if (e.currentTarget.contains(e.relatedTarget)) return;
                      if (dragOver === i) setDragOver(null);
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      let src = dragSrc;
                      try {
                        const dt = parseInt(e.dataTransfer.getData("text/plain"), 10);
                        if (!Number.isNaN(dt)) src = dt;
                      } catch {}
                      setDragOver(null);
                      setDragSrc(null);
                      if (src !== null && src !== i) {
                        moveStepTo(src, i);
                      }
                    }}
                    data-testid={`vr-step-${i}`}
                  >
                    <span
                      className="text-zinc-600 hover:text-zinc-300 cursor-grab active:cursor-grabbing select-none pt-0.5 text-[10px]"
                      title="Drag to reorder"
                      data-testid={`vr-step-drag-${i}`}
                    >⋮⋮</span>
                    <span className="text-emerald-400 font-mono pt-0.5 text-[10px]">#{i + 1}</span>
                    <span
                      className={`px-1.5 py-0.5 rounded border ${sm.bg} ${sm.color} text-[10px] font-medium flex-shrink-0`}
                      title={s.action}
                    >
                      {sm.icon}
                    </span>
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
                        onClick={() => runLiveTest({ startIndex: i })}
                        title={`Test from this step onwards (skips previous ${i} steps, uses current page state)`}
                        disabled={i === 0 || liveTesting || busy}
                        className="p-0.5 text-zinc-600 hover:text-fuchsia-400 disabled:opacity-30 disabled:cursor-not-allowed text-[10px]"
                        data-testid={`vr-step-test-from-${i}`}
                      >⏵</button>
                      <button
                        onClick={() => duplicateStep(i)}
                        title="Duplicate"
                        className="p-0.5 text-zinc-600 hover:text-sky-400 text-[10px]"
                        data-testid={`vr-step-dup-${i}`}
                      >⎘</button>
                      <button
                        onClick={() => openEditStep(i)}
                        title="Edit step (selector, value, timeout, etc.)"
                        className="p-0.5 text-zinc-600 hover:text-amber-400"
                        data-testid={`vr-step-edit-${i}`}
                      >
                        <Pencil className="w-3 h-3" />
                      </button>
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
                  </React.Fragment>
                  );
                })}
                {/* 2026-01: Final "insert at end" button (always visible) */}
                {steps.length > 0 && (
                  <div className="relative h-1 group/insert" data-testid="vr-step-insert-zone-end">
                    <button
                      onClick={() => insertStepAt(steps.length)}
                      title="Insert a new step at the END"
                      className="absolute left-1/2 -translate-x-1/2 -top-1.5 px-1.5 py-0.5 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-[9px] font-bold opacity-0 group-hover/insert:opacity-100 transition-opacity z-10 leading-none"
                      data-testid="vr-step-insert-end"
                    >
                      + insert step
                    </button>
                  </div>
                )}
              </div>

              {/* Action buttons */}
              <div className="mt-3 pt-3 border-t border-zinc-800 space-y-2">
                <button
                  onClick={runLiveTest}
                  disabled={steps.length === 0 || liveTesting || busy}
                  data-testid="vr-live-test-btn"
                  className="w-full inline-flex items-center justify-center gap-1.5 py-2 rounded bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-sm font-medium transition-colors"
                  title="Opens a FRESH page and runs all recorded steps end-to-end from the start — exactly like a real RUT visit. See per-step pass/fail + suggested fixes for any failures before you Finalize."
                >
                  {liveTesting ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Running from start…</>
                  ) : (
                    <><Zap className="w-4 h-4" /> Run Live Test from Start ({steps.length} step{steps.length === 1 ? "" : "s"})</>
                  )}
                </button>
                <div className="text-[10px] text-zinc-500 text-center -mt-1">
                  Opens a fresh browser tab and replays your steps from step 0
                </div>
                <div className="grid grid-cols-2 gap-2">
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

              {/* 2026-01: Live Activity Panel — real-time step feed during live test */}
              {(liveTesting || (liveProgress && liveProgress.length > 0 && !liveTestResult)) && (
                <div
                  className="mb-2 p-2 rounded border bg-zinc-950/80 border-blue-500/30"
                  data-testid="vr-live-activity-panel"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-medium text-blue-300 flex items-center gap-1">
                      {liveTesting ? (
                        <><Loader2 className="w-3 h-3 animate-spin" /> Live Activity — backend pe kya chal raha hai</>
                      ) : (
                        <>📋 Live Activity (last run)</>
                      )}
                    </span>
                    {liveProgress.length > 0 && (() => {
                      const okCount = liveProgress.filter(e => e.status === "ok").length;
                      const failedCount = liveProgress.filter(e => e.status === "failed").length;
                      const runningCount = liveProgress.filter(e => e.status === "running").length;
                      const totalSteps = liveProgress[0]?.total_steps || steps.length;
                      return (
                        <span className="text-[10px] text-zinc-400 font-mono">
                          {okCount}✓ / {failedCount}✗ / {Math.max(0, runningCount - okCount - failedCount)}⏵ / {totalSteps}
                        </span>
                      );
                    })()}
                  </div>
                  {/* Progress bar */}
                  {liveProgress.length > 0 && (() => {
                    const okCount = liveProgress.filter(e => e.status === "ok").length;
                    const failedCount = liveProgress.filter(e => e.status === "failed").length;
                    const totalSteps = liveProgress[0]?.total_steps || steps.length || 1;
                    const pct = Math.min(100, ((okCount + failedCount) / totalSteps) * 100);
                    return (
                      <div className="mb-1.5 h-1 bg-zinc-800 rounded overflow-hidden">
                        <div
                          className={`h-full transition-all ${failedCount > 0 ? 'bg-rose-500' : 'bg-emerald-500'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    );
                  })()}

                  {/* 2026-01: LIVE BROWSER SCREENSHOT — see the page state at the latest completed step */}
                  {liveFrame && (
                    <div className="mb-1.5 relative rounded overflow-hidden border border-zinc-800" data-testid="vr-live-frame">
                      <img
                        src={liveFrame}
                        alt="Live browser view"
                        className="w-full h-auto block"
                        style={{ maxHeight: 320, objectFit: "contain", background: "#000" }}
                      />
                      {liveFrameMeta && (
                        <div className="absolute top-1 left-1 right-1 flex items-center justify-between gap-1 pointer-events-none">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                            liveFrameMeta.status === 'ok' ? 'bg-emerald-900/90 text-emerald-200' :
                            liveFrameMeta.status === 'failed' ? 'bg-rose-900/90 text-rose-200' :
                            'bg-blue-900/90 text-blue-200'
                          }`}>
                            #{(liveFrameMeta.idx ?? 0) + 1} {liveFrameMeta.action}
                            {liveFrameMeta.selector ? ` ${liveFrameMeta.selector.slice(0, 30)}` : ''}
                          </span>
                          {typeof liveFrameMeta.ms === 'number' && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-900/90 text-zinc-200">
                              {liveFrameMeta.ms}ms
                            </span>
                          )}
                        </div>
                      )}
                      {liveTesting && (
                        <div className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-rose-700/90 text-[10px] text-white font-medium animate-pulse">
                          ● LIVE
                        </div>
                      )}
                    </div>
                  )}
                  {!liveFrame && liveTesting && (
                    <div className="mb-1.5 p-3 rounded border border-zinc-800 bg-zinc-900/50 text-center text-[10px] text-zinc-500" data-testid="vr-live-frame-empty">
                      <Loader2 className="w-4 h-4 animate-spin inline-block mr-1" /> Waiting for first browser frame…
                    </div>
                  )}

                  {/* Event log — most recent first, max 12 visible */}
                  <div
                    className="max-h-48 overflow-y-auto space-y-0.5 text-[10px] font-mono"
                    data-testid="vr-live-activity-log"
                  >
                    {liveProgress.length === 0 ? (
                      <div className="text-zinc-500 italic">Waiting for first step…</div>
                    ) : (
                      [...liveProgress].reverse().slice(0, 30).map((ev, k) => {
                        const stepNum = (ev.idx ?? 0) + 1;
                        const icon =
                          ev.status === "ok" ? "✓" :
                          ev.status === "failed" ? "✗" :
                          "⏵";
                        const color =
                          ev.status === "ok" ? "text-emerald-400" :
                          ev.status === "failed" ? "text-rose-400" :
                          "text-blue-400 animate-pulse";
                        const time = ev.timestamp_ms ?
                          new Date(ev.timestamp_ms).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) :
                          "";
                        return (
                          <div
                            key={`${ev.timestamp_ms}-${ev.idx}-${ev.status}-${k}`}
                            className={`flex items-start gap-1.5 ${color}`}
                            data-testid={`vr-live-event-${k}`}
                          >
                            <span className="flex-shrink-0 w-3">{icon}</span>
                            <span className="flex-shrink-0 text-zinc-500">[{time}]</span>
                            <span className="flex-shrink-0">#{stepNum}</span>
                            <span className="flex-shrink-0 text-zinc-300">{ev.action}</span>
                            {ev.selector && (
                              <span className="flex-shrink-0 text-zinc-500 truncate max-w-[140px]" title={ev.selector}>
                                {ev.selector.slice(0, 24)}{ev.selector.length > 24 ? '…' : ''}
                              </span>
                            )}
                            {ev.status === "ok" && typeof ev.ms === "number" && (
                              <span className="flex-shrink-0 text-zinc-500">{ev.ms}ms</span>
                            )}
                            {ev.status === "failed" && ev.error && (
                              <span className="text-rose-300 truncate" title={ev.error}>{ev.error.slice(0, 80)}</span>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              )}

              {/* Live Test Results Panel */}
              {liveTestResult && (
                <div
                  data-testid="vr-live-test-results"
                  className={`mt-3 rounded-lg border ${
                    liveTestResult.ok
                      ? "bg-emerald-950/30 border-emerald-700/40"
                      : "bg-rose-950/30 border-rose-700/40"
                  }`}
                >
                  <div className="p-3 flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      {liveTestResult.ok ? (
                        <CheckCheck className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <XCircle className="w-4 h-4 text-rose-400" />
                      )}
                      <span className={`text-sm font-medium ${liveTestResult.ok ? "text-emerald-200" : "text-rose-200"}`}>
                        Live test {liveTestResult.ok ? "passed" : "FAILED"}
                      </span>
                      <span className="text-xs text-zinc-400" data-testid="vr-live-test-summary">
                        {liveTestResult.executed_steps}/{liveTestResult.total_steps} steps
                        {typeof liveTestResult.total_ms === "number" && (
                          <> · {(liveTestResult.total_ms / 1000).toFixed(2)}s total</>
                        )}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* Auto-retest toggle */}
                      <label
                        className="inline-flex items-center gap-1 text-[10px] text-zinc-400 cursor-pointer select-none"
                        title="When ON, Live Test is automatically re-run after every Auto-fix so you can see the result without an extra click. Off if you want manual control."
                        data-testid="vr-autoretest-toggle-label"
                      >
                        <input
                          type="checkbox"
                          checked={autoRetestEnabled}
                          onChange={(e) => setAutoRetestEnabled(e.target.checked)}
                          data-testid="vr-autoretest-toggle"
                          className="accent-blue-500 cursor-pointer"
                        />
                        Auto-retest after fix
                      </label>
                      {/* Undo button (only when there's fix history) */}
                      {fixHistoryCount > 0 && (
                        <button
                          onClick={undoLastAutoFix}
                          disabled={liveTesting}
                          data-testid="vr-undo-fix-btn"
                          className="inline-flex items-center gap-1 px-2 py-1 rounded bg-amber-600/20 hover:bg-amber-600/40 border border-amber-500/40 text-amber-200 text-[10px] font-medium transition-colors disabled:opacity-40"
                          title="Revert the most recent Auto-fix. Use this if the fix turned out to break something specific to your page."
                        >
                          <Undo2 className="w-3 h-3" />
                          Undo ({fixHistoryCount})
                        </button>
                      )}
                      <button
                        onClick={() => setLiveTestResult(null)}
                        className="text-xs text-zinc-500 hover:text-zinc-200"
                        data-testid="vr-live-test-close"
                      >
                        Close ✕
                      </button>
                    </div>
                  </div>

                  {/* Optional "last undone" hint */}
                  {lastUndoneFix && (
                    <div
                      className="mx-3 mb-2 p-2 rounded bg-amber-950/40 border border-amber-700/40 text-[11px] text-amber-100 flex items-start gap-1.5"
                      data-testid="vr-last-undone-hint"
                    >
                      <Undo2 className="w-3 h-3 mt-0.5 shrink-0" />
                      <span>
                        Reverted: <code className="text-amber-300">{lastUndoneFix.kind}</code> @ step #{(lastUndoneFix.at_step ?? 0) + 1}.
                        Re-run Live Test to confirm the previous state still works.
                      </span>
                    </div>
                  )}

                  {liveTestResult.error && (() => {
                    // 2026-01: Smart fix suggester — parses the error
                    // and surfaces a one-liner cause + recommended
                    // action with quick-jump buttons.
                    const failedIdx = liveTestResult.failed_at_idx;
                    const failedStep = (typeof failedIdx === "number" && steps[failedIdx]) || null;
                    const failedAction = failedStep?.action || null;
                    const fix = getSuggestedFix(liveTestResult.error, failedAction, failedIdx);
                    return (
                      <div className="mx-3 mb-2 space-y-1.5" data-testid="vr-live-test-error">
                        {/* Raw error */}
                        <div className="p-2 rounded bg-rose-900/40 border border-rose-700/40 text-xs text-rose-100">
                          <AlertCircle className="inline w-3.5 h-3.5 mr-1" />
                          {liveTestResult.error}
                        </div>
                        {/* 2026-01: Friendly hint (Roman-Urdu/English plain-language explanation) */}
                        {liveTestResult.friendly_hint && (
                          <div
                            className="p-2 rounded bg-amber-950/30 border border-amber-700/30 text-xs text-amber-100"
                            data-testid="vr-friendly-hint"
                          >
                            💡 <span className="font-medium">Hint:</span> {liveTestResult.friendly_hint}
                          </div>
                        )}
                        {/* Smart suggestion */}
                        {fix && (
                          <div
                            className="p-2.5 rounded bg-sky-950/30 border border-sky-700/30"
                            data-testid="vr-fix-suggestion"
                          >
                            <div className="flex items-start gap-2 mb-1.5">
                              <Lightbulb className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                              <div className="flex-1">
                                <div className="text-[11px] font-semibold text-amber-200 mb-0.5">
                                  WHY THIS HAPPENED
                                </div>
                                <div className="text-xs text-zinc-200 leading-relaxed">
                                  {fix.cause}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-start gap-2 mb-2">
                              <Sparkles className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                              <div className="flex-1">
                                <div className="text-[11px] font-semibold text-emerald-300 mb-0.5">
                                  SUGGESTED FIX
                                </div>
                                <div className="text-xs text-zinc-200 leading-relaxed">
                                  {fix.fix}
                                </div>
                              </div>
                            </div>
                            {/* Quick-jump action buttons */}
                            <div className="flex items-center gap-1.5 flex-wrap mt-2">
                              {fix.action === "edit" && typeof fix.edit_idx === "number" && (
                                <button
                                  onClick={() => openEditStep(fix.edit_idx)}
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded bg-amber-700 hover:bg-amber-600 text-white text-[11px] font-medium"
                                  data-testid="vr-fix-edit-btn"
                                >
                                  <Pencil className="w-3 h-3" /> Edit step #{fix.edit_idx + 1}
                                </button>
                              )}
                              {/* "Replay from here" — picks up replay
                                  on the CURRENT page state (no fresh
                                  page) starting at the failed step.
                                  Saves the user from re-running 1-2
                                  min of preceding steps. Available
                                  whenever a specific step index
                                  failed. */}
                              {typeof failedIdx === "number" && failedIdx > 0 && (
                                <button
                                  onClick={() => runLiveTest({ startIndex: failedIdx })}
                                  disabled={liveTesting}
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded bg-fuchsia-700 hover:bg-fuchsia-600 text-white text-[11px] font-medium disabled:opacity-40"
                                  data-testid="vr-fix-resume-btn"
                                  title={`Re-run from step #${failedIdx + 1} only — keeps the browser on its current state. ~5-10× faster than a full re-run.`}
                                >
                                  <FastForward className="w-3 h-3" /> Replay from step #{failedIdx + 1}
                                </button>
                              )}
                              {fix.action === "rerun" && (
                                <button
                                  onClick={() => runLiveTest()}
                                  disabled={liveTesting}
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded bg-blue-700 hover:bg-blue-600 text-white text-[11px] font-medium disabled:opacity-40"
                                  data-testid="vr-fix-rerun-btn"
                                >
                                  <Zap className="w-3 h-3" /> Re-run Live Test
                                </button>
                              )}
                              {fix.action === "manual_add" && (
                                <button
                                  onClick={openManualAddStep}
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded bg-sky-700 hover:bg-sky-600 text-white text-[11px] font-medium"
                                  data-testid="vr-fix-add-btn"
                                >
                                  <ListPlus className="w-3 h-3" /> Add a wait step
                                </button>
                              )}
                              {fix.action === "restart" && (
                                <button
                                  onClick={stopAndDiscard}
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded bg-rose-700 hover:bg-rose-600 text-white text-[11px] font-medium"
                                  data-testid="vr-fix-restart-btn"
                                >
                                  <RefreshCw className="w-3 h-3" /> Discard & restart
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}

                  {/* Per-step timing list */}
                  {Array.isArray(liveTestResult.step_results) && liveTestResult.step_results.length > 0 && (
                    <div className="mx-3 mb-2 max-h-56 overflow-y-auto rounded border border-zinc-800 bg-zinc-950/60 divide-y divide-zinc-800/60">
                      {liveTestResult.step_results.map((r) => (
                        <div
                          key={`vrst-${r.idx}`}
                          data-testid={`vr-live-step-${r.idx}`}
                          className={`px-2 py-1.5 text-xs flex items-center justify-between gap-2 ${
                            r.ok
                              ? "text-zinc-200"
                              : "text-rose-200 bg-rose-950/40"
                          }`}
                          title={r.error || ""}
                        >
                          <div className="flex items-center gap-1.5 min-w-0 flex-1">
                            {r.ok ? (
                              <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                            ) : (
                              <XCircle className="w-3 h-3 text-rose-400 shrink-0" />
                            )}
                            <span className="text-zinc-500 w-7 shrink-0">#{(r.idx ?? 0) + 1}</span>
                            <span className="font-mono text-[11px] uppercase shrink-0 text-zinc-400">{r.action}</span>
                            <span className="truncate text-zinc-500">{r.selector}</span>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {r.self_healed && (
                              <span className="text-[10px] px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">healed</span>
                            )}
                            {r.optional && !r.ok && (
                              <span className="text-[10px] px-1 py-0.5 rounded bg-zinc-700/40 text-zinc-400">skipped</span>
                            )}
                            <span className={`font-mono text-[11px] ${(r.ms || 0) > 5000 ? "text-amber-300" : "text-zinc-400"}`}>
                              <Timer className="inline w-3 h-3 mr-0.5" />{r.ms ?? 0}ms
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Smart Diagnostics */}
                  {liveTestResult.diagnostics && showDiagnostics && (
                    <div className="mx-3 mb-3 rounded border border-zinc-800 bg-zinc-950/60 p-2" data-testid="vr-diagnostics-panel">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-1 text-xs font-medium text-blue-300">
                          <Lightbulb className="w-3.5 h-3.5" /> Smart Replay Diagnostics
                        </div>
                        <button
                          onClick={() => setShowDiagnostics(false)}
                          className="text-[10px] text-zinc-500 hover:text-zinc-200"
                        >
                          Hide
                        </button>
                      </div>

                      {/* Top-3 slowest */}
                      {Array.isArray(liveTestResult.diagnostics.slowest) && liveTestResult.diagnostics.slowest.length > 0 && (
                        <div className="mb-2">
                          <div className="text-[10px] uppercase tracking-wide text-zinc-500 mb-1">Top slowest steps</div>
                          <div className="flex flex-wrap gap-1.5">
                            {liveTestResult.diagnostics.slowest.map((s) => (
                              <span
                                key={`slow-${s.idx}`}
                                data-testid={`vr-diag-slow-${s.idx}`}
                                className={`text-[10px] px-2 py-0.5 rounded-full border ${(s.ms || 0) > 5000 ? "bg-amber-500/15 border-amber-500/40 text-amber-200" : "bg-zinc-800 border-zinc-700 text-zinc-300"}`}
                              >
                                #{(s.idx ?? 0) + 1} {s.action} · {s.ms}ms
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Wrapper summary */}
                      {liveTestResult.diagnostics.wrapper_summary && Object.keys(liveTestResult.diagnostics.wrapper_summary).length > 0 && (
                        <div className="mb-2">
                          <div className="text-[10px] uppercase tracking-wide text-zinc-500 mb-1">Dropdown wrappers</div>
                          <div className="flex flex-wrap gap-1.5">
                            {Object.entries(liveTestResult.diagnostics.wrapper_summary).map(([k, v]) => (
                              <span
                                key={`wk-${k}`}
                                data-testid={`vr-diag-wrap-${k}`}
                                className={`text-[10px] px-2 py-0.5 rounded-full border ${k === "native" ? "bg-zinc-800 border-zinc-700 text-zinc-300" : "bg-blue-500/15 border-blue-500/40 text-blue-200"}`}
                              >
                                {k}: {v}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Anti-patterns / Findings — with Auto-fix buttons */}
                      {(Array.isArray(liveTestResult.diagnostics.findings) && liveTestResult.diagnostics.findings.length > 0) ? (
                        <div className="mb-2" data-testid="vr-diag-findings-section">
                          <div className="flex items-center justify-between mb-1.5 flex-wrap gap-1">
                            <div className="text-[10px] uppercase tracking-wide text-amber-400 flex items-center gap-1">
                              <AlertCircle className="w-3 h-3" /> Anti-patterns ({liveTestResult.diagnostics.findings.length})
                            </div>
                            {(liveTestResult.diagnostics.auto_fixable_count || 0) > 0 && (
                              <button
                                onClick={() => applyAutoFix({}, true)}
                                disabled={liveTesting}
                                data-testid="vr-autofix-all-btn"
                                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-[10px] font-medium transition-colors"
                                title="Apply every auto-fixable finding in one shot. Re-run Live Test after to confirm."
                              >
                                <Sparkles className="w-3 h-3" />
                                Auto-fix all ({liveTestResult.diagnostics.auto_fixable_count})
                              </button>
                            )}
                          </div>
                          <ul className="space-y-1.5 text-[11px]">
                            {liveTestResult.diagnostics.findings.map((f, i) => (
                              <li
                                key={`f-${i}-${f.kind}-${f.at_step}`}
                                data-testid={`vr-diag-finding-${i}`}
                                className="rounded border border-zinc-800 bg-zinc-950/40 p-1.5 flex items-start gap-2"
                              >
                                <div className="flex-1 min-w-0">
                                  <div className="text-zinc-200 leading-snug">{f.message}</div>
                                  {f.fix_summary && (
                                    <div className="text-emerald-300/80 mt-0.5 text-[10px] flex items-start gap-1">
                                      <Lightbulb className="w-2.5 h-2.5 mt-0.5 shrink-0" />
                                      <span>{f.fix_summary}</span>
                                    </div>
                                  )}
                                </div>
                                {f.auto_fixable ? (
                                  <button
                                    onClick={() => applyAutoFix({ kind: f.kind, at_step: f.at_step, extra: f.extra })}
                                    disabled={liveTesting}
                                    data-testid={`vr-autofix-btn-${i}`}
                                    className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded bg-emerald-600/30 hover:bg-emerald-600/60 border border-emerald-500/40 text-emerald-100 text-[10px] font-medium transition-colors disabled:opacity-40"
                                    title={f.fix_summary || "Apply this fix"}
                                  >
                                    <Sparkles className="w-2.5 h-2.5" /> Auto-fix
                                  </button>
                                ) : (
                                  <span className="shrink-0 text-[10px] text-zinc-500 px-1 py-0.5">manual</span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : (
                        // Fallback to legacy string-only render for builds without findings field
                        Array.isArray(liveTestResult.diagnostics.anti_patterns) && liveTestResult.diagnostics.anti_patterns.length > 0 && (
                          <div className="mb-2">
                            <div className="text-[10px] uppercase tracking-wide text-amber-400 mb-1 flex items-center gap-1">
                              <AlertCircle className="w-3 h-3" /> Anti-patterns ({liveTestResult.diagnostics.anti_patterns.length})
                            </div>
                            <ul className="space-y-1 text-[11px] text-zinc-300 list-disc list-inside">
                              {liveTestResult.diagnostics.anti_patterns.map((ap, i) => (
                                <li key={`ap-${i}`} data-testid={`vr-diag-ap-${i}`} className="leading-snug">{ap}</li>
                              ))}
                            </ul>
                          </div>
                        )
                      )}

                      {/* Recommendations — only show if NO structured findings
                          (otherwise the fix_summary inside each finding is
                          already showing the actionable advice) */}
                      {(!Array.isArray(liveTestResult.diagnostics.findings) || liveTestResult.diagnostics.findings.length === 0) && Array.isArray(liveTestResult.diagnostics.recommendations) && liveTestResult.diagnostics.recommendations.length > 0 && (
                        <div>
                          <div className="text-[10px] uppercase tracking-wide text-emerald-400 mb-1 flex items-center gap-1">
                            <Lightbulb className="w-3 h-3" /> Recommendations
                          </div>
                          <ul className="space-y-1 text-[11px] text-emerald-100/90 list-disc list-inside">
                            {liveTestResult.diagnostics.recommendations.map((rc, i) => (
                              <li key={`rc-${i}`} data-testid={`vr-diag-rec-${i}`} className="leading-snug">{rc}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
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
                onClick={launchVisualReplay}
                disabled={replayLaunching || !finalBundle.url}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-sm font-medium transition-colors"
                data-testid="vr-visual-replay-btn"
                title="Re-opens a fresh browser session and replays the full saved JSON step-by-step with live visual — perfect for verifying everything works end-to-end before deploying."
              >
                {replayLaunching ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Launching replay…</>
                ) : (
                  <><Zap className="w-4 h-4" /> Live Visual Test (Step-by-Step)</>
                )}
              </button>
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
                disabled={saving}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-700/40 hover:bg-indigo-700/60 border border-indigo-500/40 text-indigo-100 text-sm font-medium disabled:opacity-60 transition-colors"
                data-testid="vr-save-library-btn"
                title={editUploadId
                  ? `Update existing template "${editTemplate?.name || ''}" (upload ID preserved)`
                  : "Save as reusable template in Uploaded Things library"}
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : savedToLibraryId ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                {savedToLibraryId
                  ? (editUploadId ? "Updated ✓ (re-save to push more edits)" : "Saved (re-save to update)")
                  : (editUploadId
                      ? `Update "${editTemplate?.name || 'template'}"`
                      : "Save to Library")}
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
                <ChevronDown className="w-4 h-4" /> {editingJson ? "Edit JSON" : "Preview JSON"}
                {!editingJson && (
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); openJsonEditor(); }}
                    className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-700/40 hover:bg-amber-700/60 border border-amber-500/40 text-amber-200 text-[10px] font-medium"
                    data-testid="vr-edit-json-btn"
                    title="Edit the finalized JSON directly — fix selectors, tweak timeouts, add/remove steps"
                  >
                    <Pencil className="w-3 h-3" /> Edit JSON
                  </button>
                )}
                {editingJson && <span className="text-[10px] text-amber-400 ml-auto">unsaved changes</span>}
              </summary>
              {editingJson ? (
                <div className="mt-2 space-y-2">
                  <textarea
                    value={editingJsonText}
                    onChange={(e) => { setEditingJsonText(e.target.value); setEditingJsonError(""); }}
                    spellCheck={false}
                    className="w-full p-3 rounded bg-zinc-950 border border-amber-700/40 focus:border-amber-500 text-emerald-300 text-xs font-mono leading-relaxed outline-none resize-y"
                    style={{ minHeight: "24rem", maxHeight: "60vh" }}
                    data-testid="vr-edit-json-textarea"
                  />
                  {editingJsonError && (
                    <div className="p-2 rounded bg-rose-900/40 border border-rose-700/40 text-xs text-rose-200" data-testid="vr-edit-json-error">
                      <AlertCircle className="inline w-3.5 h-3.5 mr-1" />
                      {editingJsonError}
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={saveJsonEditor}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium"
                      data-testid="vr-save-json-btn"
                    >
                      <Save className="w-3.5 h-3.5" /> Save JSON Changes
                    </button>
                    <button
                      onClick={cancelJsonEditor}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs"
                      data-testid="vr-cancel-json-btn"
                    >
                      Cancel
                    </button>
                    <div className="text-[10px] text-zinc-500 ml-2">
                      Must be a JSON array of step objects with <code className="text-zinc-300">"action"</code>.
                    </div>
                  </div>
                </div>
              ) : (
                <pre
                  className="mt-2 p-3 rounded bg-zinc-950 border border-zinc-800 text-xs overflow-x-auto max-h-96 font-mono leading-relaxed"
                  dangerouslySetInnerHTML={{
                    __html: colorizeJson(finalBundle.automation_json),
                  }}
                />
              )}
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

      {/* ── Edit Step Modal (2026-01) ─────────────────────────────────
          Opened by the per-step pencil button. Lets the user fix a
          wrong selector / bump a timeout / change a value or key after
          a Live Test failure, without deleting + re-recording.
          `action` is shown read-only — changing it would break replay
          semantics (delete + re-record instead). ────────────────── */}
      {editingStep && (
        <div
          className="fixed inset-0 z-50 flex items-stretch justify-end pointer-events-none"
          data-testid="vr-edit-modal-backdrop"
        >
          {/* Transparent click-catcher (close on outside click) — does NOT
              blur the page so the live screenshot stays visible for
              hover-preview. */}
          <div
            className="absolute inset-0 pointer-events-auto bg-black/10"
            onClick={cancelEditStep}
          />
          <div
            className="relative w-full max-w-md bg-zinc-950/95 border-l border-zinc-800 shadow-2xl backdrop-blur-md pointer-events-auto flex flex-col"
            onClick={(e) => e.stopPropagation()}
            data-testid="vr-edit-modal"
          >
            <div className="flex items-center justify-between p-4 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <Pencil className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-semibold text-zinc-100">
                  Edit Step #{editingStep.index + 1}
                </h3>
                <span className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-400 text-[10px] font-mono uppercase">
                  {editingStep.draft.action || "step"}
                </span>
              </div>
              <button
                onClick={cancelEditStep}
                className="p-1 text-zinc-500 hover:text-zinc-200"
                data-testid="vr-edit-modal-close"
              >
                <XCircle className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 space-y-3 flex-1 overflow-y-auto">
              {/* Name (label) */}
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Step name (label only)
                </label>
                <input
                  type="text"
                  value={editingStep.draft.name}
                  onChange={(e) =>
                    setEditingStep({
                      ...editingStep,
                      draft: { ...editingStep.draft, name: e.target.value },
                    })
                  }
                  placeholder={editingStep.draft.action}
                  className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-amber-500 text-zinc-200 text-xs outline-none"
                  data-testid="vr-edit-name"
                />
              </div>

              {/* Selector — shown for all element-targeted actions */}
              {!["wait", "goto"].includes(
                (editingStep.draft.action || "").toLowerCase()
              ) && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-[11px] text-zinc-400">
                      Selector{" "}
                      <span className="text-zinc-600">
                        (CSS or XPath — e.g. <code>#birth_month</code>,{" "}
                        <code>{`//input[@name="month"]`}</code>)
                      </span>
                    </label>
                    <button
                      type="button"
                      onClick={fetchSelectorSuggestions}
                      disabled={selectorSuggest.loading}
                      className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-emerald-700/30 hover:bg-emerald-700/50 border border-emerald-600/40 text-emerald-200 disabled:opacity-50"
                      title="Scan the live page for elements that look like what you meant"
                      data-testid="vr-edit-suggest-btn"
                    >
                      {selectorSuggest.loading ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Sparkles className="w-3 h-3" />
                      )}
                      Find similar
                    </button>
                  </div>
                  <input
                    type="text"
                    value={editingStep.draft.selector}
                    onChange={(e) =>
                      setEditingStep({
                        ...editingStep,
                        draft: { ...editingStep.draft, selector: e.target.value },
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-amber-500 text-zinc-200 text-xs font-mono outline-none"
                    data-testid="vr-edit-selector"
                  />
                  {/* Suggestions panel */}
                  {selectorSuggest.items !== null && (
                    <div className="mt-2 rounded border border-emerald-700/30 bg-emerald-950/20 p-2">
                      <div className="text-[10px] text-emerald-300/80 font-medium mb-1.5 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        Smart Selector Suggestions
                        {selectorSuggest.items.length > 0 && (
                          <span className="text-zinc-500">({selectorSuggest.items.length} matches)</span>
                        )}
                      </div>
                      {selectorSuggest.error && (
                        <div className="text-[11px] text-amber-400 mb-1">{selectorSuggest.error}</div>
                      )}
                      <div className="space-y-1 max-h-48 overflow-y-auto">
                        {selectorSuggest.items.map((s, k) => (
                          <button
                            type="button"
                            key={k}
                            onClick={() => applySuggestion(s.selector)}
                            onMouseEnter={() => showSelectorPreview(s.selector)}
                            onMouseLeave={clearSelectorPreview}
                            onFocus={() => showSelectorPreview(s.selector)}
                            onBlur={clearSelectorPreview}
                            className="w-full text-left p-1.5 rounded bg-zinc-900/80 hover:bg-emerald-900/40 border border-zinc-800 hover:border-emerald-600/40 transition-colors group"
                            data-testid={`vr-edit-suggest-item-${k}`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <code className="text-[11px] text-emerald-300 font-mono truncate">
                                {s.selector}
                              </code>
                              <span className="text-[9px] px-1 rounded bg-zinc-800 border border-zinc-700 text-zinc-400 uppercase font-mono shrink-0">
                                {s.tag}
                                {s.input_type ? `[${s.input_type}]` : ""}
                              </span>
                            </div>
                            <div className="text-[10px] text-zinc-500 mt-0.5 truncate">
                              {s.label && <span className="text-zinc-300">{s.label}</span>}
                              {s.placeholder && !s.label && (
                                <span>placeholder: {s.placeholder}</span>
                              )}
                              {(s.matched_tokens || []).length > 0 && (
                                <span className="ml-2 text-emerald-400/70">
                                  ✓ {(s.matched_tokens || []).join(", ")}
                                </span>
                              )}
                              {!s.visible && (
                                <span className="ml-2 text-amber-500/70">hidden</span>
                              )}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Value — for fill / type / select / goto */}
              {["fill", "type", "select", "goto"].includes(
                (editingStep.draft.action || "").toLowerCase()
              ) && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Value{" "}
                    <span className="text-zinc-600">
                      (supports <code>{"{{header}}"}</code> placeholders)
                    </span>
                  </label>
                  <input
                    type="text"
                    value={editingStep.draft.value}
                    onChange={(e) =>
                      setEditingStep({
                        ...editingStep,
                        draft: { ...editingStep.draft, value: e.target.value },
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-amber-500 text-zinc-200 text-xs font-mono outline-none"
                    data-testid="vr-edit-value"
                  />
                </div>
              )}

              {/* Key — for press action */}
              {(editingStep.draft.action || "").toLowerCase() === "press" && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Key{" "}
                    <span className="text-zinc-600">
                      (Enter, Tab, Escape, ArrowDown, etc.)
                    </span>
                  </label>
                  <input
                    type="text"
                    value={editingStep.draft.key}
                    onChange={(e) =>
                      setEditingStep({
                        ...editingStep,
                        draft: { ...editingStep.draft, key: e.target.value },
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-amber-500 text-zinc-200 text-xs font-mono outline-none"
                    data-testid="vr-edit-key"
                  />
                </div>
              )}

              {/* Timeout — shown for everything except plain "wait" */}
              {(editingStep.draft.action || "").toLowerCase() !== "wait" && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Timeout{" "}
                    <span className="text-zinc-600">
                      (ms — e.g. 8000. Bump this if the element appears slowly.)
                    </span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="500"
                    value={editingStep.draft.timeout}
                    onChange={(e) =>
                      setEditingStep({
                        ...editingStep,
                        draft: { ...editingStep.draft, timeout: e.target.value },
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-amber-500 text-zinc-200 text-xs outline-none"
                    data-testid="vr-edit-timeout"
                  />
                </div>
              )}

              {/* ms — for "wait" action */}
              {(editingStep.draft.action || "").toLowerCase() === "wait" && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Wait duration (ms)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="100"
                    value={editingStep.draft.ms}
                    onChange={(e) =>
                      setEditingStep({
                        ...editingStep,
                        draft: { ...editingStep.draft, ms: e.target.value },
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-amber-500 text-zinc-200 text-xs outline-none"
                    data-testid="vr-edit-ms"
                  />
                </div>
              )}

              {/* State — for wait_for_selector */}
              {(editingStep.draft.action || "").toLowerCase() ===
                "wait_for_selector" && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    State
                  </label>
                  <select
                    value={editingStep.draft.state || "visible"}
                    onChange={(e) =>
                      setEditingStep({
                        ...editingStep,
                        draft: { ...editingStep.draft, state: e.target.value },
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-amber-500 text-zinc-200 text-xs outline-none"
                    data-testid="vr-edit-state"
                  >
                    <option value="visible">visible (default)</option>
                    <option value="attached">attached (DOM only, may be hidden)</option>
                    <option value="hidden">hidden</option>
                    <option value="detached">detached</option>
                  </select>
                </div>
              )}

              {/* match_by — for select action */}
              {(editingStep.draft.action || "").toLowerCase() === "select" && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Match by
                  </label>
                  <select
                    value={editingStep.draft.match_by || "label"}
                    onChange={(e) =>
                      setEditingStep({
                        ...editingStep,
                        draft: { ...editingStep.draft, match_by: e.target.value },
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-amber-500 text-zinc-200 text-xs outline-none"
                    data-testid="vr-edit-match-by"
                  >
                    <option value="label">label (visible text)</option>
                    <option value="value">value (HTML value attr)</option>
                    <option value="index">index (0-based)</option>
                  </select>
                </div>
              )}

              {/* Humanize toggle — for fill / type only */}
              {["fill", "type"].includes(
                (editingStep.draft.action || "").toLowerCase()
              ) && (
                <div className="p-2.5 rounded bg-zinc-900/60 border border-zinc-800">
                  <label className="flex items-start gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editingStep.draft.humanize}
                      onChange={(e) =>
                        setEditingStep({
                          ...editingStep,
                          draft: {
                            ...editingStep.draft,
                            humanize: e.target.checked,
                          },
                        })
                      }
                      className="mt-0.5 w-3.5 h-3.5 accent-emerald-500"
                      data-testid="vr-edit-humanize"
                    />
                    <div className="flex-1">
                      <div className="text-xs text-zinc-200 font-medium">
                        Human-like typing
                        <span className="ml-1 text-emerald-400 text-[10px]">
                          (anti-detect — default)
                        </span>
                      </div>
                      <div className="text-[11px] text-zinc-500 mt-0.5">
                        Types character-by-character with realistic
                        delays (~50-180ms each + thinking pauses).
                        Uncheck for fast <code>page.fill()</code> — useful
                        for debugging or internal forms where speed
                        matters more than stealth.
                      </div>
                    </div>
                  </label>
                </div>
              )}
            </div>
            <div className="flex items-center justify-end gap-2 p-4 border-t border-zinc-800">
              <button
                onClick={cancelEditStep}
                className="px-4 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs"
                data-testid="vr-edit-cancel"
              >
                Cancel
              </button>
              <button
                onClick={saveEditStep}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium"
                data-testid="vr-edit-save"
              >
                <Save className="w-3.5 h-3.5" /> Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Manual Add Step Modal (2026-01) ───────────────────────────
          Opened by the "+ Add Step" button. Lets the user inject a
          step the auto-recorder didn't capture — supports BOTH CSS
          and XPath selectors. ───────────────────────────────────── */}
      {manualStepDraft && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={cancelManualAddStep}
          data-testid="vr-manual-modal-backdrop"
        >
          <div
            className="w-full max-w-lg bg-zinc-950 border border-zinc-800 rounded-xl shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            data-testid="vr-manual-modal"
          >
            <div className="flex items-center justify-between p-4 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <ListPlus className="w-4 h-4 text-sky-400" />
                <h3 className="text-sm font-semibold text-zinc-100">
                  Add Manual Step
                </h3>
                <span className="px-1.5 py-0.5 rounded bg-sky-900/40 border border-sky-700/40 text-sky-300 text-[10px] font-mono uppercase">
                  CSS or XPath
                </span>
              </div>
              <button
                onClick={cancelManualAddStep}
                className="p-1 text-zinc-500 hover:text-zinc-200"
                data-testid="vr-manual-close"
              >
                <XCircle className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
              {/* Action type */}
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Action type
                </label>
                <select
                  value={manualStepDraft.action}
                  onChange={(e) =>
                    setManualStepDraft({
                      ...manualStepDraft,
                      action: e.target.value,
                    })
                  }
                  className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs outline-none"
                  data-testid="vr-manual-action"
                >
                  <option value="wait_for_selector">wait_for_selector — wait until element appears</option>
                  <option value="click">click — click an element</option>
                  <option value="fill">fill — type into input</option>
                  <option value="type">type — slow per-char typing</option>
                  <option value="select">select — choose a &lt;select&gt; option</option>
                  <option value="press">press — keyboard key (Enter / Tab / etc.)</option>
                  <option value="wait">wait — pause for N ms</option>
                  <option value="hover">hover — mouse over element</option>
                  <option value="check">check — tick a checkbox/radio</option>
                  <option value="uncheck">uncheck — untick a checkbox</option>
                  <option value="screenshot">screenshot — capture page state</option>
                </select>
              </div>

              {/* Step name (optional label) */}
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Step name <span className="text-zinc-600">(optional label)</span>
                </label>
                <input
                  type="text"
                  value={manualStepDraft.name}
                  onChange={(e) =>
                    setManualStepDraft({ ...manualStepDraft, name: e.target.value })
                  }
                  placeholder={manualStepDraft.action}
                  className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs outline-none"
                  data-testid="vr-manual-name"
                />
              </div>

              {/* Selector — for most actions */}
              {!["wait"].includes(manualStepDraft.action) && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Selector{" "}
                    <span className="text-zinc-600">
                      (CSS like <code>#email</code>, OR XPath like{" "}
                      <code>{`//input[@name="email"]`}</code>)
                    </span>
                  </label>
                  <input
                    type="text"
                    value={manualStepDraft.selector}
                    onChange={(e) =>
                      setManualStepDraft({
                        ...manualStepDraft,
                        selector: e.target.value,
                      })
                    }
                    placeholder="#email  OR  //input[@name='email']"
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs font-mono outline-none"
                    data-testid="vr-manual-selector"
                  />
                  <div className="text-[10px] text-zinc-500 mt-1">
                    Playwright auto-detects XPath (starts with <code>//</code> or <code>(</code>).
                    For complex cases, prefix with <code>xpath=</code>.
                  </div>
                </div>
              )}

              {/* Value — for fill / type / select */}
              {["fill", "type", "select"].includes(manualStepDraft.action) && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Value{" "}
                    <span className="text-zinc-600">
                      (supports <code>{"{{header}}"}</code> placeholders)
                    </span>
                  </label>
                  <input
                    type="text"
                    value={manualStepDraft.value}
                    onChange={(e) =>
                      setManualStepDraft({
                        ...manualStepDraft,
                        value: e.target.value,
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs font-mono outline-none"
                    data-testid="vr-manual-value"
                  />
                </div>
              )}

              {/* Key — for press */}
              {manualStepDraft.action === "press" && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Key
                  </label>
                  <input
                    type="text"
                    value={manualStepDraft.key}
                    onChange={(e) =>
                      setManualStepDraft({ ...manualStepDraft, key: e.target.value })
                    }
                    placeholder="Enter / Tab / Escape / ArrowDown"
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs font-mono outline-none"
                    data-testid="vr-manual-key"
                  />
                </div>
              )}

              {/* Timeout (most actions) */}
              {!["wait", "press"].includes(manualStepDraft.action) && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Timeout (ms)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="500"
                    value={manualStepDraft.timeout}
                    onChange={(e) =>
                      setManualStepDraft({
                        ...manualStepDraft,
                        timeout: e.target.value,
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs outline-none"
                    data-testid="vr-manual-timeout"
                  />
                </div>
              )}

              {/* ms — for wait */}
              {manualStepDraft.action === "wait" && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Wait duration (ms)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="100"
                    value={manualStepDraft.ms}
                    onChange={(e) =>
                      setManualStepDraft({ ...manualStepDraft, ms: e.target.value })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs outline-none"
                    data-testid="vr-manual-ms"
                  />
                </div>
              )}

              {/* State — for wait_for_selector */}
              {manualStepDraft.action === "wait_for_selector" && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    State
                  </label>
                  <select
                    value={manualStepDraft.state}
                    onChange={(e) =>
                      setManualStepDraft({
                        ...manualStepDraft,
                        state: e.target.value,
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs outline-none"
                    data-testid="vr-manual-state"
                  >
                    <option value="visible">visible (default)</option>
                    <option value="attached">attached (DOM only)</option>
                    <option value="hidden">hidden</option>
                    <option value="detached">detached</option>
                  </select>
                </div>
              )}

              {/* match_by — for select */}
              {manualStepDraft.action === "select" && (
                <div>
                  <label className="block text-[11px] text-zinc-400 mb-1">
                    Match by
                  </label>
                  <select
                    value={manualStepDraft.match_by}
                    onChange={(e) =>
                      setManualStepDraft({
                        ...manualStepDraft,
                        match_by: e.target.value,
                      })
                    }
                    className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs outline-none"
                    data-testid="vr-manual-match-by"
                  >
                    <option value="label">label (visible text)</option>
                    <option value="value">value</option>
                    <option value="index">index (0-based)</option>
                  </select>
                </div>
              )}

              {/* humanize for fill / type */}
              {["fill", "type"].includes(manualStepDraft.action) && (
                <label className="flex items-start gap-2 cursor-pointer p-2.5 rounded bg-zinc-900/60 border border-zinc-800">
                  <input
                    type="checkbox"
                    checked={manualStepDraft.humanize}
                    onChange={(e) =>
                      setManualStepDraft({
                        ...manualStepDraft,
                        humanize: e.target.checked,
                      })
                    }
                    className="mt-0.5 w-3.5 h-3.5 accent-emerald-500"
                    data-testid="vr-manual-humanize"
                  />
                  <div className="flex-1">
                    <div className="text-xs text-zinc-200 font-medium">
                      Human-like typing
                      <span className="ml-1 text-emerald-400 text-[10px]">
                        (anti-detect — default)
                      </span>
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">
                      Uncheck for fast <code>page.fill()</code>.
                    </div>
                  </div>
                </label>
              )}

              {/* Position — where in the steps list to insert */}
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Insert at position{" "}
                  <span className="text-zinc-600">
                    (leave empty = append to end; 1-based)
                  </span>
                </label>
                <input
                  type="number"
                  min="1"
                  max={steps.length + 1}
                  value={manualStepDraft.position}
                  onChange={(e) =>
                    setManualStepDraft({
                      ...manualStepDraft,
                      position: e.target.value,
                    })
                  }
                  placeholder={`${steps.length + 1} (end)`}
                  className="w-full px-2.5 py-1.5 rounded bg-zinc-900 border border-zinc-700 focus:border-sky-500 text-zinc-200 text-xs outline-none"
                  data-testid="vr-manual-position"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 p-4 border-t border-zinc-800">
              <button
                onClick={cancelManualAddStep}
                className="px-4 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs"
                data-testid="vr-manual-cancel"
              >
                Cancel
              </button>
              <button
                onClick={saveManualAddStep}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-white text-xs font-medium"
                data-testid="vr-manual-save"
              >
                <ListPlus className="w-3.5 h-3.5" /> Add Step
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Selector Aliases Panel (2026-01) ──────────────────────────
          Read-only listing of all self-healing rules the user has
          accumulated. Each row shows the original selector + the alias
          chain + per-row hit count + delete button. ─────────────── */}
      {aliasesPanel && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={closeAliasesPanel}
          data-testid="vr-aliases-modal-backdrop"
        >
          <div
            className="w-full max-w-2xl max-h-[80vh] bg-zinc-950 border border-zinc-800 rounded-xl shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
            data-testid="vr-aliases-modal"
          >
            <div className="flex items-center justify-between p-4 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-fuchsia-400" />
                <h3 className="text-sm font-semibold text-zinc-100">
                  Self-Healing Selector Aliases
                </h3>
                {aliasesPanel.items && (
                  <span className="px-1.5 py-0.5 rounded bg-fuchsia-900/40 border border-fuchsia-700/40 text-fuchsia-200 text-[10px] font-mono">
                    {aliasesPanel.items.length} rule{aliasesPanel.items.length === 1 ? "" : "s"}
                  </span>
                )}
              </div>
              <button
                onClick={closeAliasesPanel}
                className="p-1 text-zinc-500 hover:text-zinc-200"
                data-testid="vr-aliases-close"
              >
                <XCircle className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 flex-1 overflow-y-auto">
              <div className="text-[11px] text-zinc-500 mb-3 leading-relaxed">
                Every time you fix a wrong selector via the Edit modal,
                Krexion saves the mapping below. Future Live Tests and
                RUT jobs on the same website silently try these aliases
                when the original selector fails — so your recordings
                keep working even after the site renames its form fields.
              </div>
              {aliasesPanel.loading && (
                <div className="flex items-center justify-center py-6 text-zinc-500 text-xs gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading aliases…
                </div>
              )}
              {!aliasesPanel.loading && aliasesPanel.error && (
                <div className="p-3 rounded border border-rose-700/40 bg-rose-950/30 text-rose-300 text-xs">
                  {aliasesPanel.error}
                </div>
              )}
              {!aliasesPanel.loading &&
                !aliasesPanel.error &&
                aliasesPanel.items.length === 0 && (
                  <div className="text-center py-8 text-zinc-500 text-xs">
                    <Brain className="w-10 h-10 mx-auto mb-2 text-zinc-700" />
                    No aliases yet. They are saved automatically when you
                    edit a step's selector via the pencil icon.
                  </div>
                )}
              {!aliasesPanel.loading && aliasesPanel.items.length > 0 && (
                <div className="space-y-2">
                  {aliasesPanel.items.map((a) => (
                    <div
                      key={a._id}
                      className="p-2.5 rounded border border-zinc-800 bg-zinc-900/60 hover:border-fuchsia-700/30 transition-colors"
                      data-testid={`vr-alias-row-${a._id}`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <div className="flex items-center gap-2 min-w-0">
                          <Globe className="w-3 h-3 text-emerald-400 shrink-0" />
                          <span className="text-[11px] text-zinc-300 font-mono truncate">
                            {a.domain}
                          </span>
                          {(a.hit_count || 0) > 0 && (
                            <span className="px-1.5 py-0.5 rounded bg-emerald-900/40 border border-emerald-700/40 text-emerald-300 text-[9px] font-mono shrink-0">
                              ✓ {a.hit_count} rescue{a.hit_count === 1 ? "" : "s"}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => deleteAlias(a.domain, a.original)}
                          title="Delete this alias"
                          className="p-1 text-zinc-500 hover:text-rose-400 shrink-0"
                          data-testid={`vr-alias-delete-${a._id}`}
                        >
                          <Trash className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap text-[11px] font-mono">
                        <code className="px-1.5 py-0.5 rounded bg-rose-950/50 border border-rose-800/40 text-rose-200">
                          {a.original}
                        </code>
                        <ArrowRight className="w-3 h-3 text-zinc-600" />
                        <div className="flex items-center gap-1 flex-wrap">
                          {(a.aliases || []).map((alt, k) => (
                            <code
                              key={k}
                              className={`px-1.5 py-0.5 rounded ${
                                k === 0
                                  ? "bg-emerald-950/50 border border-emerald-700/40 text-emerald-200"
                                  : "bg-zinc-800/60 border border-zinc-700/40 text-zinc-400"
                              }`}
                              title={k === 0 ? "Most recent — tried first" : `Older alias (#${k + 1})`}
                            >
                              {alt}
                            </code>
                          ))}
                        </div>
                      </div>
                      {a.last_used_at && (
                        <div className="text-[10px] text-zinc-600 mt-1">
                          Last used: {new Date(a.last_used_at).toLocaleString()}
                          {a.last_alias_used && <span className="ml-1 font-mono">via {a.last_alias_used}</span>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center justify-end gap-2 p-4 border-t border-zinc-800">
              <button
                onClick={closeAliasesPanel}
                className="px-4 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs"
                data-testid="vr-aliases-cancel"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
