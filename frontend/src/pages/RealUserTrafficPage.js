import { useState, useEffect, useRef, useMemo } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { toast } from "sonner";
import {
  Fingerprint,
  Play,
  RefreshCw,
  Download,
  Trash2,
  StopCircle,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileSpreadsheet,
  Globe,
  Sheet as SheetIcon,
  ClipboardCheck,
  Radio,
  Apple,
  Monitor,
  Activity,
  X,
  Zap,
} from "lucide-react";

const API_URL = process.env.REACT_APP_BACKEND_URL;

const COUNTRY_CHIPS = [
  "Pakistan", "India", "United States", "United Kingdom", "Canada", "Australia",
  "Germany", "France", "Italy", "Spain", "Netherlands", "Brazil", "Mexico",
  "United Arab Emirates", "Saudi Arabia", "Turkey", "Indonesia", "Philippines",
  "Thailand", "Vietnam", "Japan", "South Korea", "Nigeria", "South Africa", "Egypt",
];

const OS_CHIPS = [
  { key: "android", label: "Android" },
  { key: "ios", label: "iOS" },
  { key: "windows", label: "Windows" },
  { key: "macos", label: "macOS" },
  { key: "linux", label: "Linux" },
];

const PACING_PRESETS = [
  { label: "1m", value: 1 },
  { label: "5m", value: 5 },
  { label: "10m", value: 10 },
  { label: "20m", value: 20 },
  { label: "30m", value: 30 },
  { label: "60m", value: 60 },
  { label: "Instant", value: 0 },
];

function StatusBadge({ status }) {
  const map = {
    completed: "bg-emerald-900/50 text-emerald-200 border-emerald-800",
    running: "bg-blue-900/50 text-blue-200 border-blue-800",
    queued: "bg-blue-900/50 text-blue-200 border-blue-800",
    preparing: "bg-cyan-900/50 text-cyan-200 border-cyan-800",
    failed: "bg-red-900/50 text-red-200 border-red-800",
    stopped: "bg-orange-900/50 text-orange-200 border-orange-800",
    ok: "bg-emerald-900/50 text-emerald-200 border-emerald-800",
    skipped_captcha: "bg-amber-900/50 text-amber-200 border-amber-800",
    skipped_country: "bg-amber-900/50 text-amber-200 border-amber-800",
    skipped_os: "bg-amber-900/50 text-amber-200 border-amber-800",
    skipped_duplicate_ip: "bg-amber-900/50 text-amber-200 border-amber-800",
    skipped_vpn: "bg-amber-900/50 text-amber-200 border-amber-800",
    no_fields_matched: "bg-zinc-800 text-zinc-300 border-zinc-700",
    submitted_but_no_redirect: "bg-indigo-900/50 text-indigo-200 border-indigo-800",
  };
  return (
    <Badge className={`border ${map[status] || "bg-zinc-800 text-zinc-300 border-zinc-700"}`}>
      {status}
    </Badge>
  );
}

function EngineStatusBadge({ status, onPrewarm, prewarming }) {
  // status = { status: "ready"|"installing"|"missing"|"error", message, expected_revision }
  const s = status?.status || "ready";
  const config = {
    ready: {
      dotClass: "bg-emerald-400 shadow-emerald-400/50",
      pulse: false,
      borderClass: "border-emerald-800/60 bg-emerald-950/30",
      textClass: "text-emerald-200",
      labelClass: "text-emerald-300",
      label: "Engine Ready",
    },
    installing: {
      dotClass: "bg-amber-400 shadow-amber-400/50",
      pulse: true,
      borderClass: "border-amber-800/60 bg-amber-950/30",
      textClass: "text-amber-200",
      labelClass: "text-amber-300",
      label: "Installing…",
    },
    missing: {
      dotClass: "bg-red-400 shadow-red-400/50",
      pulse: false,
      borderClass: "border-red-800/60 bg-red-950/30",
      textClass: "text-red-200",
      labelClass: "text-red-300",
      label: "Engine Missing",
    },
    error: {
      dotClass: "bg-red-400 shadow-red-400/50",
      pulse: false,
      borderClass: "border-red-800/60 bg-red-950/30",
      textClass: "text-red-200",
      labelClass: "text-red-300",
      label: "Engine Error",
    },
  }[s] || {
    dotClass: "bg-zinc-400",
    pulse: false,
    borderClass: "border-zinc-700 bg-zinc-900",
    textClass: "text-zinc-300",
    labelClass: "text-zinc-300",
    label: "Engine",
  };

  // Show prewarm button only when engine is NOT ready and NOT actively
  // installing (so users don't double-click while a download is in progress).
  const canPrewarm = s === "missing" || s === "error";

  return (
    <div
      data-testid="rut-engine-status-badge"
      data-engine-status={s}
      title={status?.message || config.label}
      className={`flex-shrink-0 flex items-center gap-3 px-3 py-2 rounded-lg border ${config.borderClass} text-xs`}
    >
      <span className="relative flex w-2.5 h-2.5">
        {config.pulse && (
          <span className={`absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping ${config.dotClass}`}></span>
        )}
        <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${config.dotClass} shadow`}></span>
      </span>
      <div className="flex flex-col leading-tight">
        <span className={`font-semibold ${config.labelClass}`}>{config.label}</span>
        <span className={`${config.textClass} text-[11px] opacity-80`}>
          {status?.expected_revision ? `Chromium rev ${status.expected_revision}` : (status?.message || "")}
        </span>
      </div>
      {canPrewarm && onPrewarm && (
        <button
          type="button"
          data-testid="rut-engine-prewarm-btn"
          onClick={onPrewarm}
          disabled={prewarming}
          className="ml-1 px-2.5 py-1.5 rounded-md text-[11px] font-semibold border border-amber-700/60 bg-amber-900/40 text-amber-100 hover:bg-amber-900/70 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
        >
          <Zap size={12} />
          {prewarming ? "Starting…" : "Pre-warm"}
        </button>
      )}
    </div>
  );
}

// Device-mix widget palette. Keys are `os_tag` values used by uploaded
// UA batches. Unknown keys fall through to `other`.
const DEVICE_MIX_COLORS = {
  android:  "rgb(110, 231, 183)",   // emerald-300
  ios:      "rgb(165, 180, 252)",   // indigo-300
  windows:  "rgb(251, 191, 36)",    // amber-400
  macos:    "rgb(203, 213, 225)",   // slate-300
  linux:    "rgb(252, 165, 165)",   // red-300
  other:    "rgb(148, 163, 184)",   // slate-400
};
const DEVICE_MIX_LABELS = {
  android:  "Android",
  ios:      "iOS (iPhone/iPad)",
  windows:  "Windows",
  macos:    "macOS",
  linux:    "Linux",
  other:    "Other",
};


export default function RealUserTrafficPage() {
  // Target
  const [links, setLinks] = useState([]);
  const [linkId, setLinkId] = useState("");
  const [targetUrlOverride, setTargetUrlOverride] = useState("");
  // AI Learning panel state — historical answer→conversion stats per offer host
  const [aiLearning, setAiLearning] = useState(null);
  const [aiLearningLoading, setAiLearningLoading] = useState(false);

  // Target Screenshot Verification — user uploads a reference image of the
  // expected final/thank-you page so the bot can pHash-verify each visit
  // actually reached that destination (not just heuristic host-change).
  const [targetScreenshotFile, setTargetScreenshotFile] = useState(null);
  const [targetScreenshotPreview, setTargetScreenshotPreview] = useState("");
  const [targetScreenshotThreshold, setTargetScreenshotThreshold] = useState(12);

  // Compute the offer URL that AI Learning will key against (override > selected link)
  const effectiveOfferUrl = useMemo(() => {
    if (targetUrlOverride && targetUrlOverride.trim()) return targetUrlOverride.trim();
    const link = (links || []).find((l) => l.id === linkId);
    return link?.offer_url || "";
  }, [targetUrlOverride, linkId, links]);

  const fetchAiLearning = async () => {
    if (!effectiveOfferUrl) {
      setAiLearning(null);
      return;
    }
    setAiLearningLoading(true);
    try {
      const r = await fetch(
        `${API}/real-user-traffic/ai-learning?offer_url=${encodeURIComponent(effectiveOfferUrl)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (r.ok) {
        const data = await r.json();
        setAiLearning(data);
      } else {
        setAiLearning(null);
      }
    } catch (e) {
      setAiLearning(null);
    } finally {
      setAiLearningLoading(false);
    }
  };

  // Auto-fetch when offer URL changes (debounced 500ms)
  useEffect(() => {
    if (!effectiveOfferUrl) {
      setAiLearning(null);
      return;
    }
    const t = setTimeout(() => fetchAiLearning(), 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveOfferUrl]);

  // Proxies & UAs
  const [proxies, setProxies] = useState("");
  const [userAgents, setUserAgents] = useState("");
  const [useStoredProxies, setUseStoredProxies] = useState(false);
  // ── ProxyJet Auto Mode ────────────────────────────────────────
  // When ON, the user does NOT have to paste / upload any proxies —
  // the backend auto-generates a fresh batch of unique residential
  // proxies per job (using ProxyJet credentials saved on the Proxies
  // page). Every exit-IP is guaranteed unused for this user.
  const [useProxyJetAuto, setUseProxyJetAuto] = useState(false);
  const [proxyJetCountry, setProxyJetCountry] = useState("US");
  const [proxyJetState, setProxyJetState] = useState("");
  const [pjConfigured, setPjConfigured] = useState(null); // null=unknown, true/false
  // ── Inline UA Generator (so user doesn't have to leave RUT page) ──
  const [uaGenOpen, setUaGenOpen] = useState(false);
  const [uaGenApp, setUaGenApp] = useState("chrome");
  const [uaGenPlatform, setUaGenPlatform] = useState("android");
  const [uaGenCount, setUaGenCount] = useState(50);
  const [uaGenBusy, setUaGenBusy] = useState(false);

  // Uploaded Things — saved batch IDs (alternative to paste)
  const [uploadedLibrary, setUploadedLibrary] = useState([]);
  const [selectedUploadProxyId, setSelectedUploadProxyId] = useState("");
  const [selectedUploadUaId, setSelectedUploadUaId] = useState("");         // legacy single-select (kept for backward compat)
  const [selectedUploadUaIds, setSelectedUploadUaIds] = useState([]);       // NEW: multi-select device UA batches
  const [selectedUploadDataId, setSelectedUploadDataId] = useState("");

  // Compute device-mix distribution from the selected UA batches. Runs
  // purely on the client so the user sees an *estimated* OS split the
  // moment they check/uncheck a batch — no backend call. Groups by the
  // batch's `os_tag` (user-provided label) and weights by `available_count`
  // (falls back to `item_count` for legacy docs). Skips depleted batches.
  const deviceMix = (() => {
    const totals = {};
    let grand = 0;
    uploadedLibrary.forEach((u) => {
      if (u.type !== "user_agents") return;
      if (!selectedUploadUaIds.includes(u.id)) return;
      const avail = Number(u.available_count ?? u.item_count ?? 0);
      if (avail <= 0) return;
      const key = ((u.os_tag || "other") + "").toLowerCase();
      totals[key] = (totals[key] || 0) + avail;
      grand += avail;
    });
    const entries = Object.entries(totals).sort((a, b) => b[1] - a[1]);
    return { entries, grand };
  })();

  // Run settings
  const [totalClicks, setTotalClicks] = useState(10);
  const [concurrency, setConcurrency] = useState(15);
  const [durationMinutes, setDurationMinutes] = useState(0);
  // Target-mode: "clicks" = N fixed visits, "conversions" = keep trying
  // until X thank-you pages reached (capped by max_attempts for safety)
  const [targetMode, setTargetMode] = useState("clicks");
  const [targetConversions, setTargetConversions] = useState(10);
  const [maxAttempts, setMaxAttempts] = useState(100);

  // Filters
  const [allowedCountries, setAllowedCountries] = useState([]);
  const [allowedOs, setAllowedOs] = useState([]);
  const [skipDuplicateIp, setSkipDuplicateIp] = useState(true);
  const [skipVpn, setSkipVpn] = useState(true);
  const [followRedirect, setFollowRedirect] = useState(false);
  const [noRepeatedProxy, setNoRepeatedProxy] = useState(false);
  // When ON, every RUT visit is forced to route through the tracker URL
  // (/api/t/<short_code>) — server-side click counter, duplicate IP check
  // and link-stats all increment naturally. OFF (default) keeps the
  // preview-pod auto-bypass so residential proxies don't hit Cloudflare 403.
  const [forceTrackerUrl, setForceTrackerUrl] = useState(false);

  // Form-fill toggle
  const [formFillEnabled, setFormFillEnabled] = useState(false);
  const [dataSource, setDataSource] = useState("excel");
  const [file, setFile] = useState(null);
  const [gsheetUrl, setGsheetUrl] = useState("");
  const [pendingCandidates, setPendingCandidates] = useState([]);
  const [importPendingJobId, setImportPendingJobId] = useState("");
  const [stateMatchEnabled, setStateMatchEnabled] = useState(false);
  const [invalidDetectionEnabled, setInvalidDetectionEnabled] = useState(false);
  const [skipCaptcha, setSkipCaptcha] = useState(true);
  const [postSubmitWait, setPostSubmitWait] = useState(6);
  const [automationJson, setAutomationJson] = useState("");
  const [useCustomJson, setUseCustomJson] = useState(false);
  const [selectedUploadAjId, setSelectedUploadAjId] = useState("");
  const [selfHeal, setSelfHeal] = useState(true);
  // Default OFF — per user's explicit request: "job ek sequence mein
  // chale, resume na ho". When OFF, a backend restart marks the job
  // failed and the user clicks Retry manually. Predictable lifecycle.
  const [autoResumeEnabled, setAutoResumeEnabled] = useState(false);

  // AI Automation Generator state
  const [aiGenOpen, setAiGenOpen] = useState(false);
  const [aiGenFiles, setAiGenFiles] = useState([]);
  const [aiGenTargetUrl, setAiGenTargetUrl] = useState("");
  const [aiGenDesc, setAiGenDesc] = useState("");
  const [aiGenCols, setAiGenCols] = useState("");
  const [aiGenLoading, setAiGenLoading] = useState(false);

  // Job state
  const [submitting, setSubmitting] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [activeJob, setActiveJob] = useState(null);
  const [selectedJobIds, setSelectedJobIds] = useState(new Set());
  const pollRef = useRef(null);

  // Live activity modal — default OFF so backend stays light
  const [liveModalOpen, setLiveModalOpen] = useState(false);
  const [liveSteps, setLiveSteps] = useState([]);
  const [previewShot, setPreviewShot] = useState(null);
  const liveCursorRef = useRef(0);
  const liveTimerRef = useRef(null);

  // Diagnostics modal — shows macro-leak + stuck-visit events recorded
  // during the run. Powers the "Why didn't this offer convert?" workflow.
  const [diagModalOpen, setDiagModalOpen] = useState(false);
  const [diagData, setDiagData] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);

  const openDiagnostics = async () => {
    if (!activeJob?.job_id) return;
    setDiagModalOpen(true);
    setDiagLoading(true);
    setDiagData(null);
    try {
      const r = await fetch(
        `${API_URL}/api/real-user-traffic/jobs/${activeJob.job_id}/diagnostics`,
        { headers: authH() },
      );
      if (r.ok) {
        setDiagData(await r.json());
      }
    } catch (e) {
      // silent — UI shows "no data" state
    } finally {
      setDiagLoading(false);
    }
  };

  // Engine readiness — polled every 5s. Coloured badge at top of page.
  const [engineStatus, setEngineStatus] = useState({
    status: "ready",
    message: "Chromium ready",
    expected_revision: null,
  });
  const engineTimerRef = useRef(null);
  const [enginePrewarming, setEnginePrewarming] = useState(false);

  const token = () => localStorage.getItem("token");
  const authH = () => ({ Authorization: `Bearer ${token()}` });

  // ─── Data fetching ─────────────────────────────────────────────
  const fetchLinks = async () => {
    try {
      const r = await fetch(`${API_URL}/api/links`, { headers: authH() });
      if (r.ok) {
        const data = await r.json();
        setLinks(Array.isArray(data) ? data : (data.links || []));
      }
    } catch (e) { /* ignore */ }
  };

  const fetchJobs = async () => {
    try {
      const r = await fetch(`${API_URL}/api/real-user-traffic/jobs`, { headers: authH() });
      if (r.ok) {
        const data = await r.json();
        setJobs(data.jobs || []);
      }
    } catch (e) { /* ignore */ }
  };

  const fetchPendingCandidates = async () => {
    try {
      const r = await fetch(`${API_URL}/api/real-user-traffic/jobs/pending-candidates`, { headers: authH() });
      if (r.ok) {
        const data = await r.json();
        setPendingCandidates(data.items || []);
      }
    } catch (e) { /* ignore */ }
  };

  // Detect whether ProxyJet credentials are already saved — used to
  // gate the Auto-Mode toggle on/off and show a friendly hint when off.
  const fetchProxyJetStatus = async () => {
    try {
      const r = await fetch(`${API_URL}/api/proxyjet/credentials`, { headers: authH() });
      if (r.ok) {
        const data = await r.json();
        setPjConfigured(!!data.configured);
        if (data.configured && data.default_country) {
          setProxyJetCountry((prev) => prev || data.default_country);
        }
        if (data.configured && data.default_state) {
          setProxyJetState((prev) => prev || data.default_state);
        }
      } else {
        setPjConfigured(false);
      }
    } catch (e) { setPjConfigured(false); }
  };

  // ── Inline UA Generator ────────────────────────────────────────────
  // Fetch UAs from /api/user-agents/generate and append into the UA
  // textarea — avoids leaving the page just to populate user agents.
  const generateUAsInline = async () => {
    const n = Math.max(1, Math.min(Number(uaGenCount) || 10, 5000));
    setUaGenBusy(true);
    try {
      const r = await fetch(`${API_URL}/api/user-agents/generate`, {
        method: "POST",
        headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({
          app: uaGenApp,
          platform: uaGenPlatform,
          count: n,
          format: "json",
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      const list = (d.user_agents || []).map((x) => x.user_agent).filter(Boolean);
      if (!list.length) {
        toast.error("Generator returned 0 UAs — try a different app/platform");
        return;
      }
      // Append to existing list (preserve what user already pasted)
      setUserAgents((prev) => {
        const sep = prev.trim() ? "\n" : "";
        return prev + sep + list.join("\n");
      });
      toast.success(`✓ Generated ${list.length} ${uaGenPlatform} ${uaGenApp} UAs`);
      setUaGenOpen(false);
    } catch (e) {
      toast.error(`UA generation failed: ${e.message || e}`);
    } finally {
      setUaGenBusy(false);
    }
  };

  const fetchJobDetail = async (jobId) => {
    try {
      const r = await fetch(`${API_URL}/api/real-user-traffic/jobs/${jobId}`, { headers: authH() });
      if (r.ok) {
        const data = await r.json();
        setActiveJob(data);
        if (["completed", "failed", "stopped"].includes(data.status) && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          fetchJobs();
          fetchPendingCandidates();
        }
      }
    } catch (e) { /* ignore */ }
  };

  const startPolling = (jobId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    fetchJobDetail(jobId);
    pollRef.current = setInterval(() => fetchJobDetail(jobId), 2500);
  };

  // ─── Live activity log polling (only runs when modal is open) ──
  const fetchLiveSteps = async (jobId) => {
    try {
      const r = await fetch(
        `${API_URL}/api/real-user-traffic/jobs/${jobId}/live-log?since=${liveCursorRef.current}`,
        { headers: authH() }
      );
      if (!r.ok) return;
      const data = await r.json();
      if (data.steps && data.steps.length > 0) {
        liveCursorRef.current = data.cursor;
        setLiveSteps((prev) => {
          const next = [...prev, ...data.steps];
          return next.length > 400 ? next.slice(-400) : next;
        });
      }
      if (!data.running) {
        // job ended — stop auto-poll
        if (liveTimerRef.current) {
          clearInterval(liveTimerRef.current);
          liveTimerRef.current = null;
        }
      }
    } catch (_) { /* ignore */ }
  };

  const openLiveModal = () => {
    if (!activeJob?.job_id) return;
    setLiveSteps([]);
    liveCursorRef.current = 0;
    setLiveModalOpen(true);
    fetchLiveSteps(activeJob.job_id);
    liveTimerRef.current = setInterval(() => fetchLiveSteps(activeJob.job_id), 1500);
  };

  const closeLiveModal = () => {
    setLiveModalOpen(false);
    if (liveTimerRef.current) {
      clearInterval(liveTimerRef.current);
      liveTimerRef.current = null;
    }
  };

  useEffect(() => {
    fetchLinks();
    fetchJobs();
    fetchPendingCandidates();
    fetchUploadedLibrary();
    fetchEngineStatus();
    fetchProxyJetStatus();
    // Poll engine status every 5s — cheap (single fs check on the backend)
    // and gives the user immediate feedback when chromium finishes
    // installing on a fresh pod boot.
    engineTimerRef.current = setInterval(fetchEngineStatus, 5000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (liveTimerRef.current) clearInterval(liveTimerRef.current);
      if (engineTimerRef.current) clearInterval(engineTimerRef.current);
    };
  }, []);

  const fetchEngineStatus = async () => {
    try {
      const r = await fetch(`${API_URL}/api/real-user-traffic/engine-status`, {
        headers: authH(),
      });
      if (r.ok) {
        const data = await r.json();
        setEngineStatus({
          status: data.status || "ready",
          message: data.message || "",
          expected_revision: data.expected_revision || null,
        });
      }
    } catch (e) { /* ignore — keep last known status */ }
  };

  const handleEnginePrewarm = async () => {
    if (enginePrewarming) return;
    setEnginePrewarming(true);
    // Optimistic flip to "installing" so the badge gives instant feedback
    // even before the next poll cycle lands.
    setEngineStatus((prev) => ({
      ...prev,
      status: "installing",
      message: "Prewarm requested — downloading Chromium…",
    }));
    try {
      const r = await fetch(`${API_URL}/api/real-user-traffic/engine-prewarm`, {
        method: "POST",
        headers: authH(),
      });
      const data = await r.json().catch(() => ({}));
      if (r.ok) {
        if (data.already_ready) {
          toast.success("Engine already ready");
        } else if (data.already_installing) {
          toast.info("Install already in progress");
        } else {
          toast.success("Pre-warm started — engine will be ready in ~60s");
        }
        // Force an immediate re-fetch so the badge picks up the real status
        fetchEngineStatus();
      } else {
        toast.error(data.detail || "Pre-warm failed");
      }
    } catch (e) {
      toast.error("Pre-warm error: " + (e.message || e));
    } finally {
      setEnginePrewarming(false);
    }
  };

  const fetchUploadedLibrary = async () => {
    try {
      const r = await fetch(`${API_URL}/api/uploads`, { headers: authH() });
      if (r.ok) {
        const data = await r.json();
        setUploadedLibrary(data || []);
      }
    } catch (e) {
      // silent — feature may not be enabled for this user
    }
  };

  // ─── Helpers ──────────────────────────────────────────────────
  const toggleCountry = (c) => {
    setAllowedCountries((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
    );
  };
  const toggleOs = (k) => {
    setAllowedOs((prev) => (prev.includes(k) ? prev.filter((x) => x !== k) : [...prev, k]));
  };

  const proxyCount = proxies.split("\n").filter((l) => l.trim()).length;
  const uaCount = userAgents.split("\n").filter((l) => l.trim()).length;

  // ─── AI Automation Generator ──────────────────────────────────
  const onAiGenerate = async () => {
    if (!aiGenFiles || aiGenFiles.length === 0) {
      return toast.error("Upload at least one screenshot or a short video");
    }
    const hasVideo = Array.from(aiGenFiles).some((f) => (f.type || "").startsWith("video/"));
    const imageCount = Array.from(aiGenFiles).filter((f) => (f.type || "").startsWith("image/")).length;
    if (imageCount > 15) {
      return toast.error("Maximum 15 screenshots per request");
    }
    if (Array.from(aiGenFiles).filter((f) => (f.type || "").startsWith("video/")).length > 1) {
      return toast.error("Only one video per request");
    }

    setAiGenLoading(true);
    try {
      const fd = new FormData();
      if (aiGenTargetUrl.trim()) fd.append("target_url", aiGenTargetUrl.trim());
      if (aiGenDesc.trim()) fd.append("description", aiGenDesc.trim());
      if (aiGenCols.trim()) fd.append("excel_columns", aiGenCols.trim());
      for (const f of aiGenFiles) fd.append("files", f);

      const r = await fetch(`${API_URL}/api/real-user-traffic/ai-generate-automation`, {
        method: "POST",
        headers: authH(),
        body: fd,
      });
      const data = await r.json();
      if (!r.ok || data.status === "failed") {
        return toast.error(data.error || data.detail || "AI generation failed");
      }
      if (!data.steps || data.steps.length === 0) {
        return toast.error("AI did not return any steps — try adding a description or clearer screenshots");
      }

      const pretty = JSON.stringify({ steps: data.steps }, null, 2);
      setAutomationJson(pretty);
      setUseCustomJson(true);
      toast.success(`Generated ${data.steps.length} automation steps — review & Start`);
      setAiGenOpen(false);
      if (hasVideo) setAiGenFiles([]);
    } catch (e) {
      toast.error("AI generation error: " + (e.message || e));
    } finally {
      setAiGenLoading(false);
    }
  };

  const onStart = async () => {
    if (!linkId) return toast.error("Select a tracker link");
    // Validation: either paste OR uploaded batch OR ProxyJet Auto must be present
    if (!useProxyJetAuto && !useStoredProxies && !selectedUploadProxyId && !proxies.trim()) {
      return toast.error("Paste proxies, select an uploaded proxy batch, enable 'Use my stored proxies', or turn on ProxyJet Auto Mode");
    }
    if (useProxyJetAuto && !pjConfigured) {
      return toast.error("ProxyJet credentials not saved yet. Go to Proxies → ProxyJet Auto and save them first.");
    }
    if (!selectedUploadUaId && selectedUploadUaIds.length === 0 && !userAgents.trim()) {
      return toast.error("Paste at least one User Agent or select one-or-more uploaded UA batch(es)");
    }
    if (formFillEnabled) {
      if (dataSource === "excel" && !file && !selectedUploadDataId) {
        return toast.error("Upload the leads Excel/CSV file or select an uploaded data file");
      }
      if (dataSource === "gsheet" && !gsheetUrl.trim()) return toast.error("Paste the Google Sheet URL");
      if (dataSource === "pending_from_job" && !importPendingJobId) return toast.error("Select a previous job to import pending leads from");
      if (useCustomJson) {
        // Either a saved template is selected OR user pasted JSON
        if (!selectedUploadAjId && !automationJson.trim()) {
          return toast.error("Paste the custom automation JSON, pick a saved template, or disable the toggle");
        }
        if (!selectedUploadAjId) {
          try { JSON.parse(automationJson); }
          catch (e) { return toast.error("Automation JSON is not valid: " + e.message); }
        }
      }
    }

    setSubmitting(true);
    // Declared outside try so catch can read it for network-abort recovery.
    let jobsBefore = null;
    try {
      // ─────── Pre-upload ALL big payloads via library endpoints to avoid
      // Cloudflare tunnel ~100s timeout + ingress body-size limits on the
      // main job-create POST. Even small pastes are pre-uploaded so the
      // final job-create request body stays < 10 KB (IDs + numbers only).
      // Any pre-upload failure is HARD-FAILED (no silent fallback to raw
      // payload) so the user sees a clear error instead of a mysterious
      // "Network request aborted" message 30-90s later. ────────────────

      const preUpload = async (label, url, builder) => {
        try {
          const fd = new FormData();
          builder(fd);
          const r = await fetch(url, {
            method: "POST", headers: authH(), body: fd,
          });
          if (!r.ok) {
            const txt = await r.text().catch(() => "");
            throw new Error(`${label} pre-upload failed (HTTP ${r.status}): ${txt.slice(0, 200)}`);
          }
          const j = await r.json();
          return j.id || "";
        } catch (e) {
          throw new Error(`${label} pre-upload failed: ${e.message || e}`);
        }
      };

      // Excel data-file (if user picked a fresh file, not from library)
      // ────────────────────────────────────────────────────────────────
      // PARALLEL PRE-UPLOADS — earlier these ran sequentially which made
      // a typical job take 3-7 s before the actual /jobs POST fired.
      // Now all independent uploads (Excel, proxies paste, UAs paste,
      // automation JSON, target screenshot) fire at once via Promise.all
      // so total wait collapses to max-of-N (~1-2 s on a typical link).
      // ────────────────────────────────────────────────────────────────
      const wantExcel = formFillEnabled && dataSource === "excel" && file && !selectedUploadDataId;
      const wantProxies = !useProxyJetAuto && !useStoredProxies && !selectedUploadProxyId && proxies && proxies.trim();
      const wantUas = !selectedUploadUaId && selectedUploadUaIds.length === 0 && userAgents && userAgents.trim();
      const wantAj = formFillEnabled && useCustomJson && !selectedUploadAjId && automationJson.trim();
      const wantTarget = !!targetScreenshotFile;

      const [
        autoDataIdR, autoProxyIdR, autoUaIdR, autoAjIdR, autoTargetScreenshotIdR
      ] = await Promise.all([
        wantExcel ? preUpload("Excel data file",
          `${API_URL}/api/uploads/data-file`,
          (fd) => {
            fd.append("name", `auto-${Date.now()}-${file.name}`.slice(0, 80));
            fd.append("file", file);
          }) : Promise.resolve(""),
        wantProxies ? preUpload("Proxies",
          `${API_URL}/api/uploads/proxies`,
          (fd) => {
            fd.append("name", `auto-proxies-${Date.now()}`);
            fd.append("proxies", proxies);
          }) : Promise.resolve(""),
        wantUas ? preUpload("User-Agents",
          `${API_URL}/api/uploads/user-agents`,
          (fd) => {
            fd.append("name", `auto-uas-${Date.now()}`);
            fd.append("user_agents", userAgents);
          }) : Promise.resolve(""),
        wantAj ? preUpload("Automation JSON",
          `${API_URL}/api/uploads/automation-json`,
          (fd) => {
            fd.append("name", `auto-aj-${Date.now()}`);
            fd.append("automation_json", automationJson);
          }) : Promise.resolve(""),
        wantTarget ? preUpload("Target screenshot",
          `${API_URL}/api/uploads/target-screenshot`,
          (fd) => {
            fd.append("name", `auto-target-${Date.now()}`);
            fd.append("file", targetScreenshotFile);
          }) : Promise.resolve(""),
      ]);
      const autoDataId = autoDataIdR;
      const autoProxyId = autoProxyIdR;
      const autoUaId = autoUaIdR;
      const autoAjId = autoAjIdR;
      const autoTargetScreenshotId = autoTargetScreenshotIdR;

      const fd = new FormData();
      fd.append("link_id", linkId);
      if (targetUrlOverride.trim()) fd.append("target_url", targetUrlOverride.trim());

      // Target Screenshot Verification — prefer pre-uploaded ID (tiny payload).
      // Only fall back to inline multipart if pre-upload was somehow skipped
      // (shouldn't happen now that we always pre-upload above).
      if (autoTargetScreenshotId) {
        fd.append("target_screenshot_upload_id", autoTargetScreenshotId);
        fd.append(
          "target_screenshot_threshold",
          String(targetScreenshotThreshold)
        );
      } else if (targetScreenshotFile) {
        fd.append("target_screenshot", targetScreenshotFile);
        fd.append(
          "target_screenshot_threshold",
          String(targetScreenshotThreshold)
        );
      }

      // Use pre-uploaded IDs when available (smaller payload = no timeout)
      fd.append("proxies", autoProxyId ? "" : proxies);
      fd.append("user_agents", (autoUaId || selectedUploadUaIds.length > 0) ? "" : userAgents);
      fd.append("use_stored_proxies", String(useStoredProxies));
      // Uploaded batches — backend prefers these over pasted content
      const finalProxyId = selectedUploadProxyId || autoProxyId;
      const finalDataId = selectedUploadDataId || autoDataId;
      if (finalProxyId) fd.append("upload_proxy_id", finalProxyId);
      // UA: multi-batch mode wins if the user checked any; otherwise
      // fall back to legacy single-batch (backward-compat with deep
      // links / stored drafts / auto-created batches).
      if (selectedUploadUaIds.length > 0) {
        fd.append("upload_ua_ids", selectedUploadUaIds.join(","));
      } else {
        const finalUaId = selectedUploadUaId || autoUaId;
        if (finalUaId) fd.append("upload_ua_id", finalUaId);
      }
      if (formFillEnabled && dataSource === "excel" && finalDataId) {
        fd.append("upload_data_file_id", finalDataId);
      }

      fd.append("total_clicks", String(totalClicks));
      fd.append("concurrency", String(concurrency));
      fd.append("duration_minutes", String(durationMinutes));
      fd.append("target_mode", targetMode);
      if (targetMode === "conversions") {
        fd.append("target_conversions", String(targetConversions));
        fd.append("max_attempts", String(maxAttempts));
      }

      fd.append("allowed_countries", allowedCountries.join(","));
      fd.append("allowed_os", allowedOs.join(","));
      fd.append("skip_duplicate_ip", String(skipDuplicateIp));
      fd.append("skip_vpn", String(skipVpn));
      fd.append("follow_redirect", String(followRedirect));
      fd.append("no_repeated_proxy", String(noRepeatedProxy));
      fd.append("force_tracker_url", String(forceTrackerUrl));
      // ProxyJet Auto Mode — when ON the backend ignores proxies/use_stored_proxies/upload_proxy_id
      // and instead asks proxyjet_module to generate a fresh batch of
      // unique residential proxies (one-per-visit, no exit-IP ever reused).
      fd.append("use_proxyjet_auto", String(useProxyJetAuto));
      fd.append("proxyjet_country", (proxyJetCountry || "US").toUpperCase());
      fd.append("proxyjet_state", (proxyJetState || "").toUpperCase());

      fd.append("form_fill_enabled", String(formFillEnabled));
      if (formFillEnabled) {
        fd.append("data_source", dataSource);
        // Skip raw file upload if we already pre-uploaded above (avoids
        // duplicate transfer + Cloudflare timeout).
        if (dataSource === "excel" && file && !autoDataId) fd.append("file", file);
        if (dataSource === "gsheet") fd.append("gsheet_url", gsheetUrl.trim());
        if (dataSource === "pending_from_job") {
          fd.append("import_pending_from_job_id", importPendingJobId);
        }
        fd.append("state_match_enabled", String(stateMatchEnabled));
        fd.append("invalid_detection_enabled", String(invalidDetectionEnabled));
        fd.append("skip_captcha", String(skipCaptcha));
        fd.append("post_submit_wait", String(postSubmitWait));
        if (useCustomJson) {
          const finalAjId = selectedUploadAjId || autoAjId;
          if (finalAjId) {
            fd.append("upload_automation_json_id", finalAjId);
          } else if (automationJson.trim()) {
            fd.append("automation_json", automationJson);
          }
        }
        fd.append("self_heal", String(selfHeal));
        fd.append("auto_resume_enabled", String(autoResumeEnabled));
      }

      // Snapshot of the latest job-id BEFORE posting, used by the
      // fallback-detection branch below to tell whether a fetch-abort
      // actually meant the job DID start on the backend.
      jobsBefore = new Set((await (async () => {
        try {
          const rr = await fetch(`${API_URL}/api/real-user-traffic/jobs`, { headers: authH() });
          if (!rr.ok) return [];
          const jj = await rr.json();
          return Array.isArray(jj) ? jj : (jj.jobs || []);
        } catch { return []; }
      })()).map((j) => j.job_id));

      // Resilient submit: very generous timeout + TWO silent retries on
      // transient network abort. Cloudflare-tunnel idle-timeouts are
      // usually ~100s, but the backend's job-create endpoint now returns
      // within ~100ms because all heavy prep (gsheet fetches, Excel
      // parse, dup-IP scan) is deferred to a background task. We use
      // a 600s ceiling so even on a heavily loaded box / many parallel
      // submissions / extra-slow tunnel the submit will NEVER time out
      // before the response arrives.
      const submitOnce = async () => {
        const ac = new AbortController();
        const timer = setTimeout(() => ac.abort(), 600_000);
        try {
          return await fetch(`${API_URL}/api/real-user-traffic/jobs`, {
            method: "POST",
            headers: authH(),
            body: fd,
            signal: ac.signal,
          });
        } finally {
          clearTimeout(timer);
        }
      };
      let r;
      try {
        r = await submitOnce();
      } catch (firstErr) {
        const fmsg = (firstErr && firstErr.message) ? firstErr.message : String(firstErr);
        const transient = /failed to fetch|networkerror|load failed|aborted|timeout/i.test(fmsg);
        if (!transient) throw firstErr;
        // First retry after 2s — backend has just finished any cold-
        // start gsheet fetches and cached `last_synced_at` so the
        // second call returns fast.
        await new Promise((res) => setTimeout(res, 2000));
        try {
          r = await submitOnce();
        } catch (secondErr) {
          const smsg = (secondErr && secondErr.message) ? secondErr.message : String(secondErr);
          const stillTransient = /failed to fetch|networkerror|load failed|aborted|timeout/i.test(smsg);
          if (!stillTransient) throw secondErr;
          // Final retry after 4s — if even this fails we fall through
          // to the recovery-poll branch below which will pick the job
          // up from the /jobs list (backend inserts the DB row before
          // any heavy work, so the job IS there).
          await new Promise((res) => setTimeout(res, 4000));
          r = await submitOnce();
        }
      }
      let data = null;
      try { data = await r.json(); } catch (_) { data = null; }
      if (!r.ok) {
        const msg = (data && (data.detail || data.error)) || `HTTP ${r.status}`;
        throw new Error(msg);
      }
      toast.success(`Job started: ${data.total} visit(s) queued`);
      // Clear selected uploaded batches — they'll be deleted server-side
      // when the job finishes. Also refresh the library so the UI reflects
      // what's still available for future campaigns.
      setSelectedUploadProxyId("");
      setSelectedUploadUaId("");
      setSelectedUploadUaIds([]);
      setSelectedUploadDataId("");
      await fetchJobs();
      fetchUploadedLibrary();
      startPolling(data.job_id);
    } catch (e) {
      // Better diagnostics: "Failed to fetch" is usually a network/ingress abort
      console.error("RUT job start failed:", e);
      const raw = (e && e.message) ? e.message : String(e);
      const isNetworkAbort = /failed to fetch|networkerror|load failed|aborted|timeout/i.test(raw);

      // If the main POST was aborted by the network (tunnel/ingress)
      // even after multiple silent retries, the backend may STILL have
      // already accepted the job (the tunnel can drop the response
      // while the server keeps processing). Poll the past-jobs list
      // for up to 600s (10 min) — backend inserts the DB row BEFORE
      // any heavy work so the job is guaranteed to be there.
      if (isNetworkAbort && jobsBefore) {
        const deadline = Date.now() + 600_000;
        let recovered = null;
        while (Date.now() < deadline) {
          await new Promise((res) => setTimeout(res, 2500));
          try {
            const rr = await fetch(`${API_URL}/api/real-user-traffic/jobs`, { headers: authH() });
            if (rr.ok) {
              const jj = await rr.json();
              const list = Array.isArray(jj) ? jj : (jj.jobs || []);
              const fresh = list.find((j) => !jobsBefore.has(j.job_id));
              if (fresh) { recovered = fresh; break; }
            }
          } catch { /* keep polling */ }
        }
        if (recovered) {
          toast.success("Job started (auto-recovered after network timeout)");
          setSelectedUploadProxyId("");
          setSelectedUploadUaId("");
          setSelectedUploadUaIds([]);
          setSelectedUploadDataId("");
          await fetchJobs();
          fetchUploadedLibrary();
          startPolling(recovered.job_id);
          return;
        }
      }

      let friendly = raw;
      if (isNetworkAbort) {
        friendly = "Network aborted 3x + 600s recovery poll failed — job DID NOT start. " +
                   "Most likely cause: Cloudflare tunnel down OR backend container restarting. " +
                   "Steps: (1) Check tunnel status (cloudflared logs / Cloudflare dashboard). " +
                   "(2) `docker compose ps` — is `krexion-backend` healthy? " +
                   "(3) Refresh Past Jobs list once more — the job may still appear there.";
      }
      toast.error(friendly);
    } finally {
      setSubmitting(false);
    }
  };

  const onDownload = async (jobId) => {
    try {
      const r = await fetch(`${API_URL}/api/real-user-traffic/jobs/${jobId}/download`, { headers: authH() });
      if (!r.ok) return toast.error("Results not ready yet");
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `real-user-traffic-${jobId.slice(0, 8)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast.error("Download failed"); }
  };

  const onDownloadPendingLeads = async (jobId) => {
    try {
      const r = await fetch(`${API_URL}/api/real-user-traffic/jobs/${jobId}/pending-leads`, { headers: authH() });
      if (!r.ok) {
        const txt = await r.text().catch(() => "");
        return toast.error(txt.includes("not found") ? "No pending leads file (this run had no data file)" : "Pending leads not ready");
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pending_leads_${jobId.slice(0, 8)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Pending leads downloaded — upload this as next run's data");
    } catch (e) { toast.error("Download failed"); }
  };

  const onDelete = async (jobId) => {
    if (!window.confirm("Delete this job and its results?")) return;
    try {
      await fetch(`${API_URL}/api/real-user-traffic/jobs/${jobId}`, {
        method: "DELETE",
        headers: authH(),
      });
      toast.success("Deleted");
      if (activeJob?.job_id === jobId) setActiveJob(null);
      setSelectedJobIds((prev) => {
        const n = new Set(prev); n.delete(jobId); return n;
      });
      fetchJobs();
    } catch (e) { /* ignore */ }
  };

  const onStop = async (jobId) => {
    if (!window.confirm("Stop this job now? Partial screenshots + Excel will be packaged for download.")) return;
    try {
      const r = await fetch(`${API_URL}/api/real-user-traffic/jobs/${jobId}/stop`, {
        method: "POST",
        headers: authH(),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) return toast.error(data.detail || "Stop failed");
      if (data.stopped) toast.success("Stop signal sent — finalising partial results…");
      else toast.info(data.message || "Job already finished");
      // Keep polling so UI flips to `stopped` + enables Download
      fetchJobs();
      if (activeJob?.job_id === jobId) startPolling(jobId);
    } catch (e) { toast.error("Stop request failed"); }
  };

  const onBulkDelete = async () => {
    const ids = Array.from(selectedJobIds);
    if (ids.length === 0) return;
    if (!window.confirm(`Delete ${ids.length} selected job(s)?`)) return;
    try {
      const r = await fetch(`${API_URL}/api/real-user-traffic/jobs/bulk-delete`, {
        method: "POST",
        headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: ids }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Failed");
      toast.success(`Deleted ${d.deleted} job(s)`);
      if (activeJob && ids.includes(activeJob.job_id)) setActiveJob(null);
      setSelectedJobIds(new Set());
      fetchJobs();
    } catch (e) {
      toast.error(e.message || "Bulk delete failed");
    }
  };

  const toggleJobSelected = (jobId) => {
    setSelectedJobIds((prev) => {
      const n = new Set(prev);
      if (n.has(jobId)) n.delete(jobId); else n.add(jobId);
      return n;
    });
  };

  const toggleSelectAll = () => {
    if (selectedJobIds.size === jobs.length && jobs.length > 0) {
      setSelectedJobIds(new Set());
    } else {
      setSelectedJobIds(new Set(jobs.map((j) => j.job_id)));
    }
  };

  return (
    <div className="space-y-5" data-testid="real-user-traffic-page">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Fingerprint className="text-fuchsia-400" size={28} />
            Real User Traffic
          </h1>
          <p className="text-zinc-400 text-sm mt-1">
            Add clicks with custom IPs, user agents, countries & OS — optionally auto-fill the
            landing-page form with Excel/CSV or Google Sheet data.
          </p>
        </div>
        {/* Engine Status badge — auto-polled every 5s. Lets users know
            instantly whether the Chromium engine is ready, still
            installing on a fresh pod, missing, or errored. Pre-warm
            button appears when status is missing/error so users can
            kick off the install BEFORE running a campaign. */}
        <EngineStatusBadge
          status={engineStatus}
          onPrewarm={handleEnginePrewarm}
          prewarming={enginePrewarming}
        />
      </div>

      {/* ═══ Select Link ═══ */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="pb-3">
          <CardTitle className="text-white flex items-center gap-2 text-base">
            <Globe size={18} className="text-blue-400" /> Select Link
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <select
            data-testid="rut-link-select"
            value={linkId}
            onChange={(e) => setLinkId(e.target.value)}
            className="w-full h-11 px-3 rounded-md bg-zinc-800 border border-zinc-700 text-zinc-100 text-sm"
          >
            <option value="">Select a link…</option>
            {links.map((l) => (
              <option key={l.id} value={l.id}>
                /{l.short_code} → {l.offer_url?.slice(0, 70)}
                {l.offer_url && l.offer_url.length > 70 ? "…" : ""}
              </option>
            ))}
          </select>
        </CardContent>
      </Card>

      {/* ═══ Real Traffic Config ═══ */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2 text-base">
            <Radio size={18} className="text-red-400" /> Real Traffic via Residential Proxies
          </CardTitle>
          <CardDescription className="text-zinc-400 text-xs">
            Fires <strong>real</strong> browser sessions against your selected short link through each
            proxy you paste. Each exit IP is checked for duplicates · VPN · allowed country · allowed
            OS <strong>BEFORE</strong> the click is sent — so only clean traffic reaches your tracker.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* ── ProxyJet Auto Mode toggle (one-time creds → unique IP per visit) ── */}
          <div
            className={`rounded-md border p-3 transition-colors ${
              useProxyJetAuto
                ? "bg-gradient-to-r from-indigo-950/40 via-indigo-950/20 to-transparent border-indigo-500/40"
                : "bg-zinc-900/40 border-zinc-700/60"
            }`}
            data-testid="rut-proxyjet-auto-block"
          >
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={useProxyJetAuto}
                onChange={(e) => setUseProxyJetAuto(e.target.checked)}
                className="mt-1 w-4 h-4 accent-indigo-500"
                data-testid="rut-use-proxyjet-auto"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-indigo-200 font-medium text-sm">
                    🚀 ProxyJet Auto Mode
                  </span>
                  {pjConfigured === false && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                      credentials not saved — go to Proxies page
                    </span>
                  )}
                  {pjConfigured === true && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                      ✓ ready
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-zinc-400 mt-1 leading-snug">
                  Skip pasting proxies entirely. Backend auto-generates one fresh residential
                  proxy per visit. Every exit-IP is guaranteed <b className="text-emerald-300">unused</b> for your
                  account — no duplicate clicks on your offer URL, ever.
                </p>
                {useProxyJetAuto && (
                  <div className="mt-3 flex items-center gap-2 flex-wrap">
                    <Label className="text-xs text-zinc-300">Country:</Label>
                    <select
                      value={proxyJetCountry}
                      onChange={(e) => {
                        setProxyJetCountry(e.target.value);
                        if (e.target.value !== "US") setProxyJetState("");
                      }}
                      className="h-8 px-2 rounded bg-zinc-800 border border-zinc-700 text-zinc-100 text-xs"
                      data-testid="rut-proxyjet-country"
                    >
                      {["US","CA","GB","DE","FR","AU","BR","IN","JP","IT","ES","NL","MX"].map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                    {proxyJetCountry === "US" && (
                      <>
                        <Label className="text-xs text-zinc-300 ml-2">State:</Label>
                        <select
                          value={proxyJetState}
                          onChange={(e) => setProxyJetState(e.target.value)}
                          className="h-8 px-2 rounded bg-zinc-800 border border-zinc-700 text-zinc-100 text-xs"
                          data-testid="rut-proxyjet-state"
                        >
                          <option value="">Any</option>
                          {["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"].map((s) => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </select>
                      </>
                    )}
                    <span className="text-[10px] text-indigo-300 w-full">
                      Anti-detect safeties (no-repeated-proxy + skip-duplicate-IP) auto-enabled.
                    </span>
                  </div>
                )}
              </div>
            </label>
          </div>

          {/* Proxies + UAs side-by-side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className={useProxyJetAuto ? "opacity-50 pointer-events-none" : ""}>
              <div className="flex items-center justify-between mb-1">
                <Label className="text-zinc-300">
                  Proxies (one per line)
                  {useProxyJetAuto && <span className="ml-2 text-[10px] text-indigo-300">— disabled (Auto Mode ON)</span>}
                </Label>
                <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useStoredProxies}
                    onChange={(e) => setUseStoredProxies(e.target.checked)}
                    className="w-3.5 h-3.5 accent-fuchsia-500"
                    data-testid="rut-use-stored-proxies"
                    disabled={useProxyJetAuto}
                  />
                  Use my stored proxies
                </label>
              </div>
              {/* Uploaded proxy batch picker */}
              {uploadedLibrary.filter(u => u.type === "proxies").length > 0 && (
                <div className="mb-2 p-2 bg-indigo-950/30 border border-indigo-900/50 rounded">
                  <Label className="text-indigo-300 text-xs mb-1 block">
                    Or pick a saved batch from <span className="font-semibold">Uploaded Things</span> (auto-deletes after use)
                  </Label>
                  <select
                    value={selectedUploadProxyId}
                    onChange={(e) => setSelectedUploadProxyId(e.target.value)}
                    className="w-full h-8 px-2 rounded bg-zinc-800 border border-zinc-700 text-zinc-100 text-xs"
                    data-testid="rut-upload-proxy-id"
                  >
                    <option value="">— paste manually below —</option>
                    {uploadedLibrary.filter(u => u.type === "proxies").map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name} · {u.country_tag || "?"}{u.state_tag ? `/${u.state_tag}` : ""} · {u.item_count} proxies
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <Textarea
                data-testid="rut-proxies"
                rows={selectedUploadProxyId ? 5 : 9}
                placeholder={"user:pass@host:port\nuser:pass@host:port"}
                value={proxies}
                onChange={(e) => setProxies(e.target.value)}
                disabled={useStoredProxies || !!selectedUploadProxyId}
                className="bg-zinc-800 border-zinc-700 text-zinc-100 font-mono text-xs disabled:opacity-50"
              />
              <p className="text-xs text-zinc-500 mt-1">
                {selectedUploadProxyId
                  ? "Using uploaded batch (will auto-delete after job)"
                  : useStoredProxies
                    ? "Using your saved proxies from the Proxies page."
                    : `${proxyCount} proxies`}
              </p>
            </div>
            <div>
              <Label className="text-zinc-300 mb-1 block">User Agents (one per line)</Label>
              {/* Uploaded UA batch picker — multi-select so a single job
                  can span iPhone + Android + iPad pools at once.
                  Engine round-robins across the merged pool and $pulls
                  each consumed UA from its ORIGINAL batch (via ua→batch
                  map on the server). */}
              {uploadedLibrary.filter(u => u.type === "user_agents").length > 0 && (
                <div className="mb-2 p-2 bg-indigo-950/30 border border-indigo-900/50 rounded">
                  <Label className="text-indigo-300 text-xs mb-1 block">
                    Or pick saved batches from <span className="font-semibold">Uploaded Things</span> —{" "}
                    <span className="text-amber-300/80">check multiple</span> to mix devices in one job (e.g., iPhone + Android)
                  </Label>
                  <div
                    className="max-h-36 overflow-y-auto bg-zinc-900/60 border border-zinc-700 rounded divide-y divide-zinc-800"
                    data-testid="rut-upload-ua-multiselect"
                  >
                    {uploadedLibrary.filter(u => u.type === "user_agents").map((u) => {
                      const checked = selectedUploadUaIds.includes(u.id);
                      const available = Number(u.available_count ?? u.item_count ?? 0);
                      const isDepleted = !!u.depleted || available === 0;
                      return (
                        <label
                          key={u.id}
                          className={`flex items-center gap-2 px-2 py-1.5 text-xs cursor-pointer hover:bg-indigo-950/40 ${isDepleted ? "opacity-50" : ""}`}
                          data-testid={`rut-ua-option-${u.id}`}
                        >
                          <input
                            type="checkbox"
                            className="accent-indigo-500"
                            checked={checked}
                            disabled={isDepleted}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedUploadUaIds([...selectedUploadUaIds, u.id]);
                              } else {
                                setSelectedUploadUaIds(selectedUploadUaIds.filter(x => x !== u.id));
                              }
                            }}
                          />
                          <span className="flex-1 text-zinc-100 truncate">
                            <span className="font-medium">{u.name}</span>
                            <span className="text-zinc-400"> · {u.os_tag || "?"}{u.network_tag ? `/${u.network_tag}` : ""} · </span>
                            <span className={available > 0 ? "text-emerald-300" : "text-red-400"}>
                              {available}
                            </span>
                            <span className="text-zinc-500"> UAs</span>
                            {isDepleted && <span className="ml-1 text-[10px] text-red-300 font-bold">● DEPLETED</span>}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                  {selectedUploadUaIds.length > 0 && (
                    <div className="flex items-center justify-between mt-1.5 text-[11px]">
                      <span className="text-emerald-300">
                        {selectedUploadUaIds.length} batch{selectedUploadUaIds.length !== 1 ? "es" : ""} selected · mixed-device mode ON
                      </span>
                      <button
                        type="button"
                        onClick={() => setSelectedUploadUaIds([])}
                        className="text-indigo-300 hover:text-indigo-200 underline-offset-2 hover:underline"
                        data-testid="rut-ua-clear-all"
                      >
                        clear all
                      </button>
                    </div>
                  )}
                  {selectedUploadUaIds.length >= 2 && deviceMix.grand > 0 && (
                    <div
                      className="mt-2 p-2 bg-zinc-900/40 border border-zinc-700 rounded"
                      data-testid="rut-device-mix"
                    >
                      <div className="text-[11px] text-zinc-400 mb-1.5 font-medium">
                        📊 Estimated device mix — based on merged pool of{" "}
                        <span className="text-zinc-200">{deviceMix.grand.toLocaleString()}</span> UAs
                      </div>
                      <div
                        className="flex h-3 rounded overflow-hidden bg-zinc-800"
                        role="img"
                        aria-label="Device mix bar"
                      >
                        {deviceMix.entries.map(([os, count]) => {
                          const pct = (count / deviceMix.grand) * 100;
                          const color = DEVICE_MIX_COLORS[os] || DEVICE_MIX_COLORS.other;
                          const label = DEVICE_MIX_LABELS[os] || os;
                          return (
                            <div
                              key={os}
                              style={{ width: `${pct}%`, backgroundColor: color }}
                              title={`${label}: ${count.toLocaleString()} UAs (${pct.toFixed(1)}%)`}
                              data-testid={`rut-device-mix-bar-${os}`}
                            />
                          );
                        })}
                      </div>
                      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5 text-[10px]">
                        {deviceMix.entries.map(([os, count]) => {
                          const pct = (count / deviceMix.grand) * 100;
                          const color = DEVICE_MIX_COLORS[os] || DEVICE_MIX_COLORS.other;
                          const label = DEVICE_MIX_LABELS[os] || os;
                          return (
                            <span
                              key={os}
                              className="inline-flex items-center gap-1"
                              data-testid={`rut-device-mix-legend-${os}`}
                            >
                              <span
                                className="inline-block w-2 h-2 rounded-full"
                                style={{ backgroundColor: color }}
                              />
                              <span className="text-zinc-200">{label}</span>
                              <span className="text-zinc-500">
                                · {pct.toFixed(0)}% ({count.toLocaleString()})
                              </span>
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
              <div className="flex items-center justify-between mb-1">
                <Label className="text-zinc-300 text-sm" htmlFor="rut-user-agents">User Agents (one per line)</Label>
                <button
                  type="button"
                  onClick={() => setUaGenOpen((v) => !v)}
                  disabled={selectedUploadUaIds.length > 0}
                  className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-emerald-600/20 hover:bg-emerald-600/40 border border-emerald-500/40 text-emerald-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  data-testid="rut-ua-gen-toggle"
                  title="Generate realistic UAs inline — no need to visit UA Generator page"
                >
                  <span className="text-xs">✨</span> Generate UAs
                </button>
              </div>

              {/* Inline UA Generator panel (collapsed by default) */}
              {uaGenOpen && (
                <div
                  className="mb-2 p-3 rounded-md bg-emerald-950/30 border border-emerald-500/30 space-y-2"
                  data-testid="rut-ua-gen-panel"
                >
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    <div>
                      <Label className="text-[10px] text-zinc-400 uppercase tracking-wide">App</Label>
                      <select
                        value={uaGenApp}
                        onChange={(e) => setUaGenApp(e.target.value)}
                        className="w-full h-8 px-2 rounded bg-zinc-800 border border-zinc-700 text-zinc-100 text-xs"
                        data-testid="rut-ua-gen-app"
                      >
                        <option value="chrome">Chrome (web)</option>
                        <option value="instagram">Instagram</option>
                        <option value="facebook">Facebook</option>
                        <option value="tiktok">TikTok</option>
                        <option value="snapchat">Snapchat</option>
                        <option value="pinterest">Pinterest</option>
                      </select>
                    </div>
                    <div>
                      <Label className="text-[10px] text-zinc-400 uppercase tracking-wide">Platform</Label>
                      <select
                        value={uaGenPlatform}
                        onChange={(e) => setUaGenPlatform(e.target.value)}
                        className="w-full h-8 px-2 rounded bg-zinc-800 border border-zinc-700 text-zinc-100 text-xs"
                        data-testid="rut-ua-gen-platform"
                      >
                        <option value="any">Any (mix)</option>
                        <option value="android">Android</option>
                        <option value="ios">iOS</option>
                        <option value="desktop">Desktop</option>
                      </select>
                    </div>
                    <div>
                      <Label className="text-[10px] text-zinc-400 uppercase tracking-wide">Count</Label>
                      <Input
                        type="number"
                        min={1}
                        max={5000}
                        value={uaGenCount}
                        onChange={(e) => setUaGenCount(Number(e.target.value) || 50)}
                        className="h-8 bg-zinc-800 border-zinc-700 text-zinc-100 text-xs"
                        data-testid="rut-ua-gen-count"
                      />
                    </div>
                    <div className="flex items-end">
                      <Button
                        onClick={generateUAsInline}
                        disabled={uaGenBusy}
                        className="w-full h-8 bg-emerald-600 hover:bg-emerald-500 text-white text-xs"
                        data-testid="rut-ua-gen-run"
                      >
                        {uaGenBusy ? "Generating…" : "Generate & Append"}
                      </Button>
                    </div>
                  </div>
                  <p className="text-[10px] text-emerald-300/80">
                    Generated UAs are <b>appended</b> below — existing ones are preserved. Want full advanced
                    options (brand, regions, resolutions)? Open the <a href="/user-agent-generator" className="underline text-emerald-300">UA Generator page</a>.
                  </p>
                </div>
              )}

              <Textarea
                data-testid="rut-user-agents"
                rows={selectedUploadUaIds.length > 0 ? 5 : 9}
                placeholder={"Mozilla/5.0 (Linux; Android 15; SM-S928U) AppleWebKit/...\nMozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) ..."}
                value={userAgents}
                onChange={(e) => setUserAgents(e.target.value)}
                disabled={selectedUploadUaIds.length > 0}
                className="bg-zinc-800 border-zinc-700 text-zinc-100 font-mono text-xs disabled:opacity-50"
              />
              <p className="text-xs text-zinc-500 mt-1">
                {selectedUploadUaIds.length > 0
                  ? `Using ${selectedUploadUaIds.length} uploaded batch${selectedUploadUaIds.length !== 1 ? "es" : ""} — only used UAs will be removed per-row from each`
                  : `${uaCount} UAs · system auto-detects OS + device from each UA and matches viewport, platform, touch & canvas/WebGL spoof`}
              </p>
            </div>
          </div>

          {/* Target URL override */}
          <div>
            <Label className="text-zinc-300 text-sm">
              Target URL{" "}
              <span className="text-zinc-500 text-xs font-normal">
                (optional — paste your PUBLIC short-link URL if tracker isn't reachable from the
                internet, e.g. localhost / Docker / behind NAT)
              </span>
            </Label>
            <Input
              data-testid="rut-target-url"
              placeholder="https://yourdomain.com/t/insta  — leave empty to auto-detect"
              value={targetUrlOverride}
              onChange={(e) => setTargetUrlOverride(e.target.value)}
              className="mt-1 bg-zinc-800 border-zinc-700 text-zinc-100 text-sm font-mono"
            />
          </div>

          {/* AI Learning Panel — historical answer→conversion stats */}
          {effectiveOfferUrl && (
            <div className="p-4 bg-gradient-to-br from-purple-950/40 to-zinc-950/60 border border-purple-900/40 rounded-lg">
              <Label className="text-zinc-300 flex items-center gap-2 text-sm">
                <span className="inline-block w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                AI Answer Learning
                <span className="text-xs text-zinc-500 font-normal">
                  — bot biases survey answers toward historically high-converting picks
                </span>
              </Label>
              {aiLearningLoading ? (
                <p className="text-xs text-zinc-500 mt-2" data-testid="ai-learning-loading">
                  Loading learning data…
                </p>
              ) : !aiLearning || aiLearning.questions_learned === 0 ? (
                <p className="text-xs text-zinc-500 mt-2" data-testid="ai-learning-empty">
                  No learning data yet for{" "}
                  <span className="font-mono text-purple-300">
                    {(() => {
                      try {
                        return new URL(effectiveOfferUrl).hostname;
                      } catch {
                        return effectiveOfferUrl.slice(0, 50);
                      }
                    })()}
                  </span>{" "}
                  — first run will be pure random. After ~10 conversions the bot will
                  auto-bias toward winning answers.
                </p>
              ) : (
                <div className="mt-3 space-y-3" data-testid="ai-learning-panel">
                  <div className="text-xs text-zinc-400">
                    <span className="text-purple-300 font-semibold">
                      {aiLearning.questions_learned}
                    </span>{" "}
                    questions learned ·{" "}
                    <span className="text-purple-300 font-semibold">
                      {aiLearning.total_clicks}
                    </span>{" "}
                    historical answer clicks recorded
                  </div>
                  {aiLearning.questions.map((q, i) => (
                    <div
                      key={i}
                      className="bg-zinc-950/60 border border-zinc-800 rounded p-3"
                      data-testid={`ai-learning-question-${i}`}
                    >
                      <div className="text-xs text-zinc-400 mb-2 truncate">
                        Q: {q.question || "(no signature)"}
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {(q.answers || []).slice(0, 6).map((a, j) => {
                          const isBest =
                            a.answer === q.best_answer && q.best_rate > 0;
                          return (
                            <div
                              key={j}
                              className={`flex items-center justify-between text-xs px-2 py-1 rounded ${
                                isBest
                                  ? "bg-purple-900/30 border border-purple-700/40"
                                  : "bg-zinc-900/40"
                              }`}
                            >
                              <span
                                className={
                                  isBest
                                    ? "text-purple-200 font-medium"
                                    : "text-zinc-400"
                                }
                              >
                                {isBest && "★ "}
                                {a.answer}
                              </span>
                              <span className="text-zinc-500 font-mono">
                                {a.conv}/{a.clicks} (
                                {Math.round((a.rate || 0) * 100)}%)
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Target Screenshot Verification — upload reference final page image */}
          <div className="p-4 bg-gradient-to-br from-emerald-950/40 to-zinc-950/60 border border-emerald-900/40 rounded-lg">
            <Label className="text-zinc-300 flex items-center gap-2 text-sm">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-400" />
              Target Page Screenshot Verification{" "}
              <span className="text-xs text-zinc-500 font-normal">
                — upload a screenshot of the FINAL page each visit must reach;
                bot will pHash-compare and mark only matching visits as TRUE conversions
              </span>
            </Label>
            <div className="mt-3 flex flex-col md:flex-row gap-4">
              <div className="flex-1">
                <input
                  data-testid="rut-target-screenshot"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    setTargetScreenshotFile(f || null);
                    if (f) {
                      const url = URL.createObjectURL(f);
                      setTargetScreenshotPreview(url);
                    } else {
                      setTargetScreenshotPreview("");
                    }
                  }}
                  className="text-xs text-zinc-300 file:bg-emerald-700 file:hover:bg-emerald-600 file:text-white file:border-0 file:rounded file:px-3 file:py-1 file:mr-3 file:cursor-pointer"
                />
                <p className="text-xs text-zinc-500 mt-2">
                  Tip: open the offer in incognito with a US proxy, complete it
                  manually once, screenshot the final reward / "Congratulations"
                  / partner-deal page → upload here. Bot will count only visits
                  that visually match this page as conversions.
                </p>
                <div className="mt-3 flex items-center gap-2">
                  <Label className="text-zinc-400 text-xs whitespace-nowrap">
                    Match strictness
                  </Label>
                  <Input
                    data-testid="rut-target-screenshot-threshold"
                    type="number"
                    min="0"
                    max="30"
                    value={targetScreenshotThreshold}
                    onChange={(e) =>
                      setTargetScreenshotThreshold(
                        Math.max(0, Math.min(30, Number(e.target.value || 12)))
                      )
                    }
                    className="w-20 bg-zinc-800 border-zinc-700 text-zinc-100 text-xs h-7"
                  />
                  <span className="text-xs text-zinc-500">
                    (lower = stricter · 12 default · 0 = pixel-perfect · 22 = same template)
                  </span>
                </div>
              </div>
              {targetScreenshotPreview && (
                <div
                  className="flex-shrink-0 relative"
                  data-testid="rut-target-screenshot-preview"
                >
                  <img
                    src={targetScreenshotPreview}
                    alt="target preview"
                    className="max-h-40 rounded border border-emerald-800/40 bg-zinc-950"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setTargetScreenshotFile(null);
                      setTargetScreenshotPreview("");
                    }}
                    className="absolute -top-2 -right-2 bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-700 rounded-full w-6 h-6 text-xs flex items-center justify-center"
                    data-testid="rut-target-screenshot-remove"
                  >
                    ×
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Pacing */}
          <div className="p-4 bg-zinc-950/60 border border-zinc-800 rounded-lg">
            <Label className="text-zinc-300 flex items-center gap-2 text-sm">
              <RefreshCw size={14} className="text-blue-400" /> Pacing — deliver clicks over time (optional)
            </Label>
            <p className="text-xs text-zinc-500 mt-1 mb-3">
              Set duration in minutes to spread the run. e.g. Target=1000 + Duration=20 → about one
              click every ~1.2s. Leave 0 to fire as fast as possible.
            </p>
            <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
              <div className="flex-1 md:max-w-xs">
                <Label className="text-zinc-400 text-xs">Duration (minutes)</Label>
                <Input
                  data-testid="rut-duration"
                  type="number"
                  min={0}
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(Math.max(0, Number(e.target.value) || 0))}
                  className="mt-1 bg-zinc-800 border-zinc-700 text-zinc-100"
                />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {PACING_PRESETS.map((p) => (
                  <button
                    key={p.label}
                    type="button"
                    data-testid={`rut-pacing-${p.label}`}
                    onClick={() => setDurationMinutes(p.value)}
                    className={`px-3 py-1.5 rounded-md border text-xs font-medium transition ${
                      durationMinutes === p.value
                        ? p.label === "Instant"
                          ? "bg-red-600 border-red-500 text-white"
                          : "bg-fuchsia-600 border-fuchsia-500 text-white"
                        : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <span className="text-xs text-zinc-500 whitespace-nowrap ml-auto">
                {durationMinutes === 0 ? "As fast as proxies allow" : `~${(durationMinutes * 60 / Math.max(1, totalClicks)).toFixed(1)}s between clicks`}
              </span>
            </div>
          </div>

          {/* Total + Concurrency */}
          {/* Target-mode selector + conditional inputs */}
          <div>
            <Label className="text-zinc-300 text-sm mb-2 block">Run target</Label>
            <div className="grid grid-cols-2 gap-2 mb-3">
              <button
                type="button"
                onClick={() => setTargetMode("clicks")}
                data-testid="rut-target-clicks-mode"
                className={`p-2.5 rounded-lg border text-sm font-medium transition flex items-center justify-center gap-2 ${
                  targetMode === "clicks"
                    ? "bg-cyan-600 border-cyan-500 text-white"
                    : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                }`}
              >
                📈 Total clicks (fixed count)
              </button>
              <button
                type="button"
                onClick={() => setTargetMode("conversions")}
                data-testid="rut-target-conversions-mode"
                className={`p-2.5 rounded-lg border text-sm font-medium transition flex items-center justify-center gap-2 ${
                  targetMode === "conversions"
                    ? "bg-emerald-600 border-emerald-500 text-white"
                    : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                }`}
              >
                🎯 Target conversions (keep trying)
              </button>
            </div>
            {targetMode === "conversions" && !formFillEnabled && (
              <p className="text-xs text-amber-400 bg-amber-950/30 border border-amber-900/50 rounded-md px-3 py-2 mb-3" data-testid="rut-conv-mode-warning">
                ⚠️ Conversions are only detected when Form Auto-Fill is ON (a conversion = thank-you page reached after submitting a lead). Enable <b>Form Auto-Fill</b> below or switch back to <b>Total clicks</b> mode.
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {targetMode === "clicks" ? (
              <div>
                <Label className="text-zinc-300 text-sm">Total Clicks Target</Label>
                <Input
                  data-testid="rut-total-clicks"
                  type="number"
                  min={1}
                  max={100000}
                  value={totalClicks}
                  onChange={(e) => setTotalClicks(Math.max(1, Math.min(100000, Number(e.target.value) || 1)))}
                  className="mt-1 bg-zinc-800 border-zinc-700 text-zinc-100"
                />
                <p className="text-xs text-zinc-500 mt-1">Runs exactly this many visits.</p>
              </div>
            ) : (
              <>
                <div>
                  <Label className="text-zinc-300 text-sm">Target Conversions (thank-you pages)</Label>
                  <Input
                    data-testid="rut-target-conversions"
                    type="number"
                    min={1}
                    max={10000}
                    value={targetConversions}
                    onChange={(e) => setTargetConversions(Math.max(1, Math.min(10000, Number(e.target.value) || 1)))}
                    className="mt-1 bg-zinc-800 border-zinc-700 text-zinc-100"
                  />
                  <p className="text-xs text-emerald-300 mt-1">Stops AS SOON AS this many conversions reach the thank-you page.</p>
                </div>
                <div>
                  <Label className="text-zinc-300 text-sm">Max Attempts (safety cap)</Label>
                  <Input
                    data-testid="rut-max-attempts"
                    type="number"
                    min={1}
                    max={100000}
                    value={maxAttempts}
                    onChange={(e) => setMaxAttempts(Math.max(1, Math.min(100000, Number(e.target.value) || 1)))}
                    className="mt-1 bg-zinc-800 border-zinc-700 text-zinc-100"
                  />
                  <p className="text-xs text-zinc-500 mt-1">Hard cap — run stops when this many visits have been launched even if the target wasn't hit.</p>
                </div>
              </>
            )}
            <div>
              <Label className="text-zinc-300 text-sm">Concurrency (1–50) ⚡</Label>
              <Input
                data-testid="rut-concurrency"
                type="number"
                min={1}
                max={50}
                value={concurrency}
                onChange={(e) => setConcurrency(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
                className="mt-1 bg-zinc-800 border-zinc-700 text-zinc-100"
              />
              <p className="text-xs text-gray-500 mt-1">
                Recommended: 20-30 (safe) | 40-50 (ultra speed)
              </p>
            </div>
          </div>

          {/* Allowed OS */}
          <div>
            <Label className="text-zinc-300 mb-2 block text-sm">
              Allowed Operating Systems{" "}
              <span className="text-zinc-500 text-xs font-normal">
                (click to toggle — leave empty to allow ALL OS)
              </span>
            </Label>
            <div className="flex flex-wrap gap-2">
              {OS_CHIPS.map((os) => {
                const active = allowedOs.includes(os.key);
                const Icon =
                  os.key === "ios" || os.key === "macos" ? Apple :
                  os.key === "android" ? Radio :
                  Monitor;
                return (
                  <button
                    key={os.key}
                    type="button"
                    data-testid={`rut-os-${os.key}`}
                    onClick={() => toggleOs(os.key)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition flex items-center gap-2 ${
                      active
                        ? "bg-fuchsia-600 border-fuchsia-500 text-white"
                        : "bg-zinc-900 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                    }`}
                  >
                    <Icon size={14} />
                    {os.label}
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-zinc-500 mt-2">
              {allowedOs.length === 0
                ? "Any OS will be accepted"
                : `Only ${allowedOs.map(k => OS_CHIPS.find(o => o.key === k)?.label).join(" · ")} UAs will be used — all others skipped`}
            </p>
          </div>

          {/* Allowed Countries */}
          <div>
            <Label className="text-zinc-300 mb-2 block text-sm">
              Allowed Countries{" "}
              <span className="text-zinc-500 text-xs font-normal">
                (click to toggle — leave empty to allow ALL countries)
              </span>
            </Label>
            <div className="flex flex-wrap gap-1.5">
              {COUNTRY_CHIPS.map((c) => {
                const active = allowedCountries.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    data-testid={`rut-country-${c.replace(/\s+/g, "-").toLowerCase()}`}
                    onClick={() => toggleCountry(c)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                      active
                        ? "bg-fuchsia-600 border-fuchsia-500 text-white"
                        : "bg-zinc-900 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                    }`}
                  >
                    {c}
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-zinc-500 mt-2">
              {allowedCountries.length === 0
                ? "Any country will be accepted"
                : `${allowedCountries.length} countries selected`}
            </p>
          </div>

          {/* Toggle filters - inline row */}
          <div className="flex flex-wrap gap-x-6 gap-y-3 pt-2 border-t border-zinc-800">
            <CheckRow testId="rut-skip-duplicate-ip" checked={skipDuplicateIp} onChange={setSkipDuplicateIp}>
              <span className="text-zinc-300">🚫 Skip duplicate exit IP</span>
            </CheckRow>
            <CheckRow testId="rut-skip-vpn" checked={skipVpn} onChange={setSkipVpn}>
              <span className="text-zinc-300">🛡️ Skip VPN / datacenter</span>
            </CheckRow>
            <CheckRow testId="rut-follow-redirect" checked={followRedirect} onChange={setFollowRedirect}>
              <span className="text-zinc-300">🔄 Follow redirect to offer URL</span>
            </CheckRow>
            <CheckRow testId="rut-no-repeated-proxy" checked={noRepeatedProxy} onChange={setNoRepeatedProxy}>
              <span className="text-zinc-300">♻️ No repeated proxy (one use per line)</span>
            </CheckRow>
            <CheckRow testId="rut-force-tracker-url" checked={forceTrackerUrl} onChange={setForceTrackerUrl}>
              <span className="text-zinc-300">
                🎯 Strict tracker URL
                <span className="text-zinc-500 text-xs ml-2">
                  (force every visit through /api/t/&lt;short_code&gt; — best for strict duplicate-IP &amp; click counting; may 403 from some residential proxies on preview pods)
                </span>
              </span>
            </CheckRow>
          </div>
        </CardContent>
      </Card>

      {/* ═══ Form Filler TOGGLE ═══ */}
      <Card className={`border transition ${
        formFillEnabled ? "bg-emerald-950/20 border-emerald-800" : "bg-zinc-900 border-zinc-800"
      }`}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <ClipboardCheck className={formFillEnabled ? "text-emerald-400" : "text-zinc-500"} size={22} />
              <div>
                <CardTitle className="text-white text-base flex items-center gap-2">
                  Form Filler / Survey Bot
                  {formFillEnabled && (
                    <Badge className="bg-emerald-900/50 text-emerald-200 border-emerald-800">ENABLED</Badge>
                  )}
                </CardTitle>
                <CardDescription className="text-zinc-400 text-xs mt-1">
                  Turn ON to auto-fill the landing-page form + survey with your leads data, using
                  the same proxies + UAs + OS filter from above.
                </CardDescription>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setFormFillEnabled(!formFillEnabled)}
              data-testid="rut-form-fill-toggle"
              role="switch"
              aria-checked={formFillEnabled}
              className={`relative inline-flex h-7 w-14 shrink-0 cursor-pointer items-center rounded-full border transition ${
                formFillEnabled ? "bg-emerald-600 border-emerald-500" : "bg-zinc-700 border-zinc-600"
              }`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
                  formFillEnabled ? "translate-x-8" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </CardHeader>

        {formFillEnabled && (
          <CardContent className="space-y-4 border-t border-emerald-900/30 pt-4">
            {/* Data source toggle */}
            <div>
              <Label className="text-zinc-300 text-sm mb-2 block">Data source</Label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setDataSource("excel")}
                  data-testid="rut-data-excel"
                  className={`p-3 rounded-lg border text-sm font-medium transition flex items-center justify-center gap-2 ${
                    dataSource === "excel"
                      ? "bg-emerald-600 border-emerald-500 text-white"
                      : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                  }`}
                >
                  <FileSpreadsheet size={16} /> Excel / CSV upload
                </button>
                <button
                  type="button"
                  onClick={() => setDataSource("gsheet")}
                  data-testid="rut-data-gsheet"
                  className={`p-3 rounded-lg border text-sm font-medium transition flex items-center justify-center gap-2 ${
                    dataSource === "gsheet"
                      ? "bg-emerald-600 border-emerald-500 text-white"
                      : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                  }`}
                >
                  <SheetIcon size={16} /> Google Sheet
                </button>
                <button
                  type="button"
                  onClick={() => { setDataSource("pending_from_job"); fetchPendingCandidates(); }}
                  data-testid="rut-data-pending"
                  disabled={pendingCandidates.length === 0}
                  title={pendingCandidates.length === 0 ? "No past runs with unused leads — finish a run first" : "Import the unused leads from a previous run"}
                  className={`p-3 rounded-lg border text-sm font-medium transition flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed ${
                    dataSource === "pending_from_job"
                      ? "bg-amber-600 border-amber-500 text-white"
                      : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-600"
                  }`}
                >
                  <Download size={16} /> Pending from previous run
                  {pendingCandidates.length > 0 && (
                    <span className="ml-1 text-[10px] bg-amber-900/60 px-1.5 py-0.5 rounded">{pendingCandidates.length}</span>
                  )}
                </button>
              </div>
              {dataSource === "excel" ? (
                <div className="mt-2 space-y-2">
                  {/* Uploaded data file picker */}
                  {uploadedLibrary.filter(u => u.type === "data_file").length > 0 && (
                    <div className="p-2 bg-indigo-950/30 border border-indigo-900/50 rounded">
                      <Label className="text-indigo-300 text-xs mb-1 block">
                        Or pick a saved file from <span className="font-semibold">Uploaded Things</span> (auto-deletes after use)
                      </Label>
                      <select
                        value={selectedUploadDataId}
                        onChange={(e) => setSelectedUploadDataId(e.target.value)}
                        className="w-full h-8 px-2 rounded bg-zinc-800 border border-zinc-700 text-zinc-100 text-xs"
                        data-testid="rut-upload-data-id"
                      >
                        <option value="">— upload manually below —</option>
                        {uploadedLibrary.filter(u => u.type === "data_file").map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.name} · {u.item_count} rows · {u.file_name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  <Input
                    data-testid="rut-file"
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    disabled={!!selectedUploadDataId}
                    className="bg-zinc-800 border-zinc-700 text-zinc-100 file:text-zinc-100 file:bg-zinc-700 file:border-0 file:rounded disabled:opacity-50"
                  />
                  {selectedUploadDataId && (
                    <p className="text-xs text-zinc-500">Using uploaded batch (will auto-delete after job)</p>
                  )}
                </div>
              ) : dataSource === "gsheet" ? (
                <Input
                  data-testid="rut-gsheet-url"
                  placeholder="https://docs.google.com/spreadsheets/d/…/edit — must be published as CSV"
                  value={gsheetUrl}
                  onChange={(e) => setGsheetUrl(e.target.value)}
                  className="mt-2 bg-zinc-800 border-zinc-700 text-zinc-100"
                />
              ) : (
                <div className="mt-2 space-y-1">
                  <select
                    data-testid="rut-pending-select"
                    value={importPendingJobId}
                    onChange={(e) => setImportPendingJobId(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 text-zinc-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-amber-500"
                  >
                    <option value="">— Select a previous run —</option>
                    {pendingCandidates.map((c) => (
                      <option key={c.job_id} value={c.job_id}>
                        {c.job_id.slice(0, 8)} · {c.pending_leads_count} leads left · {c.link_short_code || "—"} · {c.created_at ? new Date(c.created_at).toLocaleString() : ""}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-amber-300/80">
                    Imports the `pending_leads.xlsx` from the selected run automatically — no file upload needed.
                  </p>
                </div>
              )}
              <p className="text-xs text-zinc-500 mt-1">
                Columns auto-match to form fields by name / id / placeholder / aria-label — e.g.{" "}
                <code className="text-zinc-400">first_name, last_name, email, phone, address, zip, dob</code>
              </p>
            </div>

            {/* State-match toggle */}
            <div className="rounded-lg border border-amber-900/40 bg-amber-950/10 p-3">
              <CheckRow testId="rut-state-match" checked={stateMatchEnabled} onChange={setStateMatchEnabled}>
                <span className="text-amber-200 font-medium">🌎 Match lead state to proxy IP state</span>
              </CheckRow>
              <p className="text-xs text-zinc-400 mt-1 pl-7">
                When ON: a row is only submitted through a proxy whose exit-IP is in the SAME US state
                as the lead (e.g. California lead → California proxy). Needs a <code className="text-amber-300">state</code> column in your data
                (full name or 2-letter code). Visits with no matching lead are counted as <code className="text-amber-300">skipped_state_mismatch</code>.
              </p>
            </div>

            {/* Invalid-data detection toggle — DEFAULT OFF */}
            <div className="rounded-lg border border-red-900/40 bg-red-950/10 p-3">
              <CheckRow testId="rut-invalid-detect" checked={invalidDetectionEnabled} onChange={setInvalidDetectionEnabled}>
                <span className="text-red-200 font-medium">🔍 Detect &amp; remove invalid leads <span className="text-[10px] text-zinc-500 font-normal">(advanced — leave OFF if unsure)</span></span>
              </CheckRow>
              <p className="text-xs text-zinc-400 mt-1 pl-7">
                When ON: after every submit, the page is scanned for inline validation errors (Bootstrap <code className="text-red-300">.invalid-feedback</code>, Angular / MUI error messages, or body text like "invalid email / invalid zip / duplicate submission"). Matching rows are auto-removed from pending leads and the form retries with the next lead.
                <br />
                <span className="text-amber-300">
                  ⚠️ Keep OFF for offer pages that show consent / marketing banners — those can be misread as errors and cause every visit to loop-retry without any conversion.
                </span>
              </p>
            </div>

            <CheckRow testId="rut-skip-captcha" checked={skipCaptcha} onChange={setSkipCaptcha}>
              <span className="text-zinc-300">
                ⚠️ Skip if captcha detected{" "}
                <span className="text-zinc-500 text-xs">(reCAPTCHA · hCaptcha · Turnstile)</span>
              </span>
            </CheckRow>

            {/* Post-submit wait */}
            <div className="pt-3 border-t border-emerald-900/30">
              <Label className="text-zinc-300 text-sm">
                Post-submit wait (seconds) — how long to stay on the "thank-you" page before final screenshot
              </Label>
              <div className="flex items-center gap-3 mt-1">
                <Input
                  type="number"
                  min={3}
                  max={15}
                  value={postSubmitWait}
                  onChange={(e) => setPostSubmitWait(Math.max(3, Math.min(15, Number(e.target.value) || 6)))}
                  className="bg-zinc-800 border-zinc-700 text-zinc-100 max-w-[120px]"
                  data-testid="rut-post-submit-wait"
                />
                <span className="text-xs text-zinc-500">Range: 3-15s. Default: 6s.</span>
              </div>
            </div>

            {/* AI Automation Generator */}
            <div className="pt-3 border-t border-emerald-900/30">
              <button
                type="button"
                onClick={() => setAiGenOpen((v) => !v)}
                className="w-full text-left flex items-center justify-between px-3 py-2 rounded-md bg-gradient-to-r from-fuchsia-900/40 to-indigo-900/40 border border-fuchsia-700/40 hover:from-fuchsia-900/60 hover:to-indigo-900/60 transition"
                data-testid="rut-ai-generator-toggle"
              >
                <span className="text-sm font-semibold text-fuchsia-200">
                  🎬 AI Automation Generator — screenshots/video se JSON banao
                </span>
                <span className="text-xs text-fuchsia-300">{aiGenOpen ? "▲ Hide" : "▼ Open"}</span>
              </button>

              {aiGenOpen && (
                <div className="mt-3 p-3 rounded-md border border-fuchsia-800/40 bg-zinc-950/60 space-y-3">
                  <p className="text-xs text-zinc-400">
                    Upload karo: <b>1-15 screenshots</b> (jpg/png/webp) <b>ya 1 short video</b> (mp4/mov/webm, max 40 MB)
                    jismein aap ka form-fill process dikh raha ho. Gemini 2.5 Pro dekh ke
                    automation JSON khud bana de ga.
                  </p>

                  <div className="grid md:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-zinc-300 text-xs">Target URL (optional, best accuracy)</Label>
                      <Input
                        data-testid="rut-aigen-target-url"
                        value={aiGenTargetUrl}
                        onChange={(e) => setAiGenTargetUrl(e.target.value)}
                        placeholder="https://example-offer.com"
                        className="bg-zinc-900 border-zinc-700 text-zinc-100 text-xs"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-zinc-300 text-xs">Excel columns (comma-separated)</Label>
                      <Input
                        data-testid="rut-aigen-cols"
                        value={aiGenCols}
                        onChange={(e) => setAiGenCols(e.target.value)}
                        placeholder="first, last, email, phone, zip, month, day, year"
                        className="bg-zinc-900 border-zinc-700 text-zinc-100 text-xs"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <Label className="text-zinc-300 text-xs">Description (Roman Urdu/English OK)</Label>
                    <Textarea
                      data-testid="rut-aigen-desc"
                      rows={3}
                      value={aiGenDesc}
                      onChange={(e) => setAiGenDesc(e.target.value)}
                      placeholder="Pehle UNLOCK NOW par click karo, phir form fill karo (first, last, email, phone), TCPA checkbox tick karo, Submit par click karo, 6 second wait karo."
                      className="bg-zinc-900 border-zinc-700 text-zinc-100 text-xs"
                    />
                  </div>

                  <div className="space-y-1">
                    <Label className="text-zinc-300 text-xs">Screenshots or Video</Label>
                    <input
                      type="file"
                      multiple
                      accept="image/png,image/jpeg,image/webp,video/mp4,video/quicktime,video/webm,video/mpeg"
                      onChange={(e) => setAiGenFiles(Array.from(e.target.files || []))}
                      data-testid="rut-aigen-files"
                      className="block w-full text-xs text-zinc-300 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-fuchsia-700 file:text-white hover:file:bg-fuchsia-600"
                    />
                    {aiGenFiles.length > 0 && (
                      <p className="text-xs text-zinc-500">
                        Selected: {aiGenFiles.length} file(s) —{" "}
                        {Array.from(aiGenFiles).map((f) => f.name).join(", ").slice(0, 140)}
                      </p>
                    )}
                  </div>

                  <Button
                    type="button"
                    onClick={onAiGenerate}
                    disabled={aiGenLoading}
                    data-testid="rut-aigen-submit"
                    className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                  >
                    {aiGenLoading ? (
                      <><RefreshCw className="animate-spin mr-2" size={16} /> Gemini 2.5 Pro analysing…</>
                    ) : (
                      <>✨ Generate Automation JSON</>
                    )}
                  </Button>

                  <p className="text-xs text-amber-300/70">
                    💡 Tip: Video mein aap screen record karein — landing page → UNLOCK click → form fill → submit tak.
                    Aur Excel columns ke naam upar likh dein taa ke placeholders match hon ({"{{first}}"}, {"{{email}}"} etc.).
                  </p>
                </div>
              )}
            </div>

            {/* Custom Automation JSON */}
            <div className="pt-3 border-t border-emerald-900/30">
              <label className="flex items-center gap-2 cursor-pointer mb-2">
                <input
                  type="checkbox"
                  checked={useCustomJson}
                  onChange={(e) => setUseCustomJson(e.target.checked)}
                  className="w-4 h-4 accent-emerald-500"
                  data-testid="rut-use-custom-json"
                />
                <span className="text-zinc-200 text-sm font-medium">
                  🧩 Use Custom Automation JSON (for specific offer sites)
                </span>
              </label>
              <p className="text-xs text-zinc-500 mb-2 ml-6">
                Bypass the auto form-filler and run your own step-by-step script.
                Supports: <code className="text-zinc-400">click · fill · type · select · check · press · wait · wait_for_selector · scroll · evaluate · screenshot</code>.
                Placeholders: <code className="text-zinc-400">{"{{first}} {{email}} {{phone}} {{random.10}}"}</code>.
              </p>
              {useCustomJson && (
                <>
                  {/* Uploaded automation-json template picker (reusable, never auto-deletes) */}
                  {uploadedLibrary.filter(u => u.type === "automation_json").length > 0 && (
                    <div className="mb-2 p-2 bg-emerald-950/30 border border-emerald-900/50 rounded">
                      <Label className="text-emerald-300 text-xs mb-1 block">
                        Or pick a <span className="font-semibold">saved template</span> from Uploaded Things (reusable — never deleted)
                      </Label>
                      <select
                        value={selectedUploadAjId}
                        onChange={(e) => setSelectedUploadAjId(e.target.value)}
                        className="w-full h-8 px-2 rounded bg-zinc-800 border border-zinc-700 text-zinc-100 text-xs"
                        data-testid="rut-upload-aj-id"
                      >
                        <option value="">— paste manually below —</option>
                        {uploadedLibrary.filter(u => u.type === "automation_json").map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.name} · {u.item_count} steps
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  <Textarea
                    data-testid="rut-automation-json"
                    rows={10}
                    placeholder={`{
  "steps": [
    {"action": "click", "selector": "a:has-text('UNLOCK NOW')", "wait_nav": true, "optional": true},
    {"action": "fill",  "selector": "input[name='first']",   "value": "{{first}}"},
    {"action": "fill",  "selector": "input[name='last']",    "value": "{{last}}"},
    {"action": "fill",  "selector": "input[name='email']",   "value": "{{email}}"},
    {"action": "fill",  "selector": "input[name='phone']",   "value": "{{cellphone}}"},
    {"action": "fill",  "selector": "input[name='zip']",     "value": "{{zip}}"},
    {"action": "select","selector": "select[name='dobmonth']","value": "{{month}}"},
    {"action": "select","selector": "select[name='dobday']", "value": "{{day}}"},
    {"action": "select","selector": "select[name='dobyear']","value": "{{year}}"},
    {"action": "click", "selector": "#submit-btn", "wait_nav": true}
  ]
}`}
                    value={automationJson}
                    onChange={(e) => setAutomationJson(e.target.value)}
                    disabled={!!selectedUploadAjId}
                    className="bg-zinc-950 border-zinc-700 text-zinc-100 font-mono text-xs disabled:opacity-50"
                  />
                  {selectedUploadAjId && (
                    <p className="text-xs text-emerald-400/70 mt-1">
                      Using saved template (template is NOT consumed — you can reuse it for future campaigns)
                    </p>
                  )}
                </>
              )}
              <p className="text-xs text-amber-400/70 mt-2 ml-6">
                💡 Aap koi bhi naya offer site bhejen (URL + brief kya karna hai) — main aapke liye exact JSON bana dunga, bas yahan paste karen.
              </p>

              {/* Self-heal toggle */}
              <label className="flex items-start gap-2 cursor-pointer mt-3 ml-6">
                <input
                  type="checkbox"
                  checked={selfHeal}
                  onChange={(e) => setSelfHeal(e.target.checked)}
                  className="w-4 h-4 accent-emerald-500 mt-0.5"
                  data-testid="rut-self-heal"
                />
                <span className="text-xs text-zinc-300">
                  🤖 <b>Smart self-heal</b> — agar runtime par koi unexpected popup / modal / cookie banner aa jaye,
                  Gemini 2.5 Pro screenshot dekh ke khud close/skip kar dega aur automation continue karega (up to 3 recoveries per lead).
                </span>
              </label>

              {/* Auto-resume toggle (default OFF) — added 2026-01 per user request */}
              <label className="flex items-start gap-2 cursor-pointer mt-3 ml-6">
                <input
                  type="checkbox"
                  checked={autoResumeEnabled}
                  onChange={(e) => setAutoResumeEnabled(e.target.checked)}
                  className="w-4 h-4 accent-orange-500 mt-0.5"
                  data-testid="rut-auto-resume"
                />
                <span className="text-xs text-zinc-300">
                  ⟳ <b>Auto-resume on backend restart</b> (default <span className="text-orange-400">OFF</span>) — agar backend kabhi restart ho mid-job, ON honay par job apne aap continue hogi (visits + counters preserve). OFF rakhain to job <span className="text-rose-400">failed</span> mark hogi aur aap manually "Retry" karein — predictable lifecycle, no surprise resumes.
                </span>
              </label>
            </div>
          </CardContent>
        )}
      </Card>

      {/* ═══ Big red START button ═══ */}
      <Button
        data-testid="rut-start-btn"
        onClick={onStart}
        disabled={submitting}
        className="w-full h-14 text-lg font-semibold bg-red-600 hover:bg-red-700 text-white border border-red-500"
      >
        {submitting ? (
          <>
            <RefreshCw className="animate-spin mr-2" size={20} /> Starting…
          </>
        ) : (
          <>
            <Play className="mr-2" size={20} />
            {targetMode === "conversions"
              ? `Run until ${targetConversions} Conversions (max ${maxAttempts} attempts)`
              : `Send ${totalClicks} Real ${formFillEnabled ? "Visits with Auto-Fill" : "Clicks"}`}
          </>
        )}
      </Button>

      {/* ═══ Live Run panel ═══ */}
      {activeJob && (
        <Card className="bg-zinc-900 border-fuchsia-900/50">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              Live Run <StatusBadge status={activeJob.status} />
            </CardTitle>
            <CardDescription className="text-zinc-400 font-mono text-xs break-all">
              target: {activeJob.target_url}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Prep-step indicator — shows what the BG task is currently
                doing while the job is in queued/preparing state. Without
                this, users stare at "queued" with zero feedback during
                the 5-30s prep phase. */}
            {(activeJob.status === "queued" || activeJob.status === "preparing") && activeJob.prep_step && (
              <div data-testid="rut-job-prep-step" className="mb-4 rounded-lg border border-blue-900/60 bg-blue-950/30 px-4 py-3 flex items-center gap-3">
                <RefreshCw className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />
                <div className="text-sm text-blue-200">
                  <span className="font-semibold">Preparing:</span> {activeJob.prep_step}
                </div>
              </div>
            )}
            {/* Show error/diagnosis banner — covers BOTH "failed" jobs
                (with error_message) AND "stopped" jobs that produced
                zero visits (where the new engine self-diagnosis fills
                in `diagnosis` to explain WHY it ended early). Without
                this, users only see a "failed/stopped" badge with no
                detail. */}
            {(activeJob.status === "failed" || activeJob.status === "stopped" || activeJob.status === "running" || activeJob.status === "queued") && (activeJob.error || activeJob.error_message || activeJob.diagnosis || activeJob.stop_reason) && (
              <div
                data-testid="rut-job-error-banner"
                className={`mb-4 rounded-lg border px-4 py-3 flex items-start gap-3 ${
                  activeJob.status === "failed"
                    ? "border-red-900/60 bg-red-950/40"
                    : "border-amber-900/60 bg-amber-950/30"
                }`}
              >
                <AlertTriangle className={`w-5 h-5 mt-0.5 flex-shrink-0 ${
                  activeJob.status === "failed" ? "text-red-400" : "text-amber-400"
                }`} />
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-semibold mb-1 ${
                    activeJob.status === "failed" ? "text-red-300" : "text-amber-300"
                  }`}>
                    {activeJob.status === "failed"
                      ? "Job failed"
                      : activeJob.status === "stopped"
                      ? "Job stopped — diagnosis"
                      : "Job status note"}
                  </div>
                  <div className={`text-sm break-words whitespace-pre-wrap ${
                    activeJob.status === "failed" ? "text-red-200" : "text-amber-200"
                  }`}>
                    {activeJob.error || activeJob.error_message || activeJob.diagnosis || activeJob.stop_reason}
                  </div>
                  {activeJob.status === "stopped" && (activeJob.diagnosis || activeJob.stop_reason) && (
                    <div className="mt-2 text-xs text-amber-300/80">
                      Tip: hit <code className="bg-amber-900/40 px-1 rounded">/api/diagnostics/health</code> on your backend to see if Mongo, Playwright, GSheet SA and memory are all green.
                    </div>
                  )}
                  {/* Resume / Retry button — appears on failed/stopped jobs
                      that have persisted submit_params (the source of
                      truth for resumability), OR on queued/preparing
                      jobs that appear stuck (let the user force-resume
                      instead of waiting for the auto-resume to give up).
                      The endpoint preserves processed/succeeded/skipped
                      counters — engine continues from `prev_processed`. */}
                  {(activeJob.status === "failed" || activeJob.status === "stopped" || activeJob.status === "queued" || activeJob.status === "preparing") && activeJob.job_id && (
                    <button
                      data-testid="rut-job-retry-btn"
                      onClick={async () => {
                        try {
                          const r = await fetch(`${API_URL}/api/real-user-traffic/jobs/${activeJob.job_id}/retry`, {
                            method: "POST",
                            headers: authH(),
                          });
                          const d = await r.json();
                          if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
                          const _doneAlready = Number(activeJob.processed || 0);
                          toast.success(_doneAlready > 0
                            ? `Resuming from visit #${_doneAlready + 1} (${_doneAlready} already done)`
                            : "Job re-queued — preparing now");
                          await loadJobs();
                          setActiveJob(null);
                        } catch (e) {
                          toast.error(`Resume failed: ${e.message || e}`);
                        }
                      }}
                      className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-700/40 hover:bg-emerald-700/60 border border-emerald-500/40 text-emerald-200 text-sm font-medium transition-colors"
                    >
                      <RefreshCw className="w-4 h-4" />
                      {(activeJob.status === "queued" || activeJob.status === "preparing")
                        ? "Force restart job"
                        : (Number(activeJob.processed || 0) > 0
                            ? `▶ Resume from visit #${Number(activeJob.processed || 0) + 1}`
                            : "Retry this job")}
                    </button>
                  )}
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 md:grid-cols-8 gap-3 mb-4">
              <Stat label="Total" value={activeJob.total ?? 0} />
              <Stat label="Processed" value={activeJob.processed ?? 0} />
              <Stat label="Succeeded" value={activeJob.succeeded ?? 0} color="emerald" />
              <Stat
                label={activeJob.target_mode === "conversions" ? `Conversions (${activeJob.conversions ?? 0}/${activeJob.target_conversions ?? "?"})` : "Conversions"}
                value={activeJob.conversions ?? 0}
                color="fuchsia"
                data-testid="rut-conversions-stat"
              />
              <Stat
                label="Skipped"
                value={(activeJob.skipped_captcha ?? 0) + (activeJob.skipped_country ?? 0) + (activeJob.skipped_os ?? 0) + (activeJob.skipped_duplicate_ip ?? 0) + (activeJob.skipped_vpn ?? 0) + (activeJob.skipped_state_mismatch ?? 0)}
                color="amber"
                data-testid="rut-skipped-total"
              />
              <Stat label="Invalid Data" value={activeJob.invalid_data ?? 0} color="red" data-testid="rut-invalid-stat" />
              <Stat label="Failed" value={activeJob.failed ?? 0} color="red" />
              <Stat label="Leads Left" value={activeJob.leftover_leads_count ?? "—"} color="emerald" data-testid="rut-leads-left-stat" />
            </div>
            <div className="border border-zinc-800 rounded-lg overflow-hidden">
              <div className="bg-zinc-950 text-zinc-400 text-xs font-semibold px-3 py-2 uppercase tracking-wide">
                Recent Visits
              </div>
              <div className="max-h-80 overflow-y-auto divide-y divide-zinc-800">
                {(activeJob.events || []).slice().reverse().map((ev, i) => (
                  <div key={i} className="px-3 py-2 text-sm flex items-center gap-3">
                    <span className="text-zinc-500 w-10 text-right">#{ev.row}</span>
                    <StatusBadge status={ev.status} />
                    <span className="text-zinc-400 font-mono text-xs">{ev.exit_ip || "?"}</span>
                    <span className="text-zinc-500 text-xs">{ev.city}, {ev.country}</span>
                    <span className="text-zinc-300 text-xs hidden md:inline">{ev.device}</span>
                    {ev.error && <span className="text-red-400 text-xs truncate ml-auto">{ev.error}</span>}
                  </div>
                ))}
                {(!activeJob.events || activeJob.events.length === 0) && (
                  <div className="px-3 py-6 text-center text-zinc-500 text-sm">Waiting for first visit…</div>
                )}
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              {activeJob.is_draining && (
                <div
                  className="flex items-center gap-2 px-3 py-1.5 rounded border text-sm"
                  style={{
                    backgroundColor: "rgba(245, 158, 11, 0.10)",
                    borderColor: "rgba(245, 158, 11, 0.40)",
                    color: "rgb(252, 211, 77)",
                  }}
                  title="Target reached. The dispatcher has stopped spawning new visits. In-flight visits will run to completion so the proxies/UAs/leads they already picked up aren't wasted."
                  data-testid="rut-draining-badge"
                >
                  <span className="text-base leading-none">🎯</span>
                  <span className="font-medium">Target reached — draining in-flight visits…</span>
                </div>
              )}
              {(activeJob.status === "running" || activeJob.status === "queued" || activeJob.status === "preparing") && (
                <>
                  <Button
                    data-testid="rut-stop-active"
                    onClick={() => onStop(activeJob.job_id)}
                    className="bg-orange-600 hover:bg-orange-700 text-white"
                  >
                    <StopCircle size={16} className="mr-2" /> Stop Now & Package Partial Results
                  </Button>
                  <Button
                    data-testid="rut-live-activity-btn"
                    onClick={openLiveModal}
                    variant="outline"
                    className="bg-zinc-800 border-fuchsia-700 text-fuchsia-200 hover:bg-fuchsia-950"
                  >
                    <Activity size={16} className="mr-2" /> Show Live Activity
                  </Button>
                  <Button
                    data-testid="rut-show-diagnostics-btn"
                    onClick={openDiagnostics}
                    variant="outline"
                    className="bg-zinc-800 border-amber-700 text-amber-200 hover:bg-amber-950"
                    title="Show macro-leak blocks + stuck-visit events for this job"
                  >
                    <AlertTriangle size={16} className="mr-2" /> Diagnostics
                  </Button>
                </>
              )}
              {(activeJob.status === "completed" || activeJob.status === "stopped") && (
                <>
                  <Button
                    data-testid="rut-download-active"
                    onClick={() => onDownload(activeJob.job_id)}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    <Download size={16} className="mr-2" /> Download Results ZIP
                    {activeJob.status === "stopped" ? " (Partial)" : ""}
                  </Button>
                  {activeJob.form_fill_enabled && (
                    <Button
                      data-testid="rut-download-pending-leads-active"
                      onClick={() => onDownloadPendingLeads(activeJob.job_id)}
                      className="bg-amber-600 hover:bg-amber-700 text-white"
                      title="Excel with only the leads that haven't been used yet (used + invalid removed). Re-upload as next run's data."
                    >
                      <Download size={16} className="mr-2" /> Pending Leads
                      {typeof activeJob.leftover_leads_count === "number" ? ` (${activeJob.leftover_leads_count})` : ""}
                    </Button>
                  )}
                  <Button
                    data-testid="rut-show-diagnostics-completed-btn"
                    onClick={openDiagnostics}
                    variant="outline"
                    className="bg-zinc-800 border-amber-700 text-amber-200 hover:bg-amber-950"
                    title="Show macro-leak blocks + stuck-visit events for this job"
                  >
                    <AlertTriangle size={16} className="mr-2" /> Diagnostics
                  </Button>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ═══ Past jobs ═══ */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-white">Past Jobs</CardTitle>
            <CardDescription className="text-zinc-400">
              Latest runs — auto-refreshes while running
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {selectedJobIds.size > 0 && (
              <Button
                size="sm"
                onClick={onBulkDelete}
                data-testid="rut-bulk-delete-btn"
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                <Trash2 size={14} className="mr-1" /> Delete Selected ({selectedJobIds.size})
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={fetchJobs} className="bg-zinc-800 border-zinc-700 text-zinc-200">
              <RefreshCw size={14} className="mr-1" /> Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <p className="text-zinc-500 text-sm text-center py-6">
              No jobs yet — start one above 👆
            </p>
          ) : (
            <div className="border border-zinc-800 rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-zinc-950 text-zinc-400">
                  <tr>
                    <th className="px-3 py-2 text-left">
                      <input
                        type="checkbox"
                        checked={selectedJobIds.size === jobs.length && jobs.length > 0}
                        onChange={toggleSelectAll}
                        className="w-4 h-4 accent-fuchsia-500 cursor-pointer"
                        data-testid="rut-select-all"
                      />
                    </th>
                    <th className="px-3 py-2 text-left font-semibold">Job</th>
                    <th className="px-3 py-2 text-left font-semibold">Status</th>
                    <th className="px-3 py-2 text-left font-semibold">Progress</th>
                    <th className="px-3 py-2 text-left font-semibold">Created</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800">
                  {jobs.map((j) => {
                    const checked = selectedJobIds.has(j.job_id);
                    return (
                    <tr key={j.job_id} className={`hover:bg-zinc-800/50 ${checked ? "bg-fuchsia-950/20" : ""}`}>
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleJobSelected(j.job_id)}
                          className="w-4 h-4 accent-fuchsia-500 cursor-pointer"
                          data-testid={`rut-select-${j.job_id}`}
                        />
                      </td>
                      <td className="px-3 py-2 text-zinc-300 font-mono text-xs">{j.job_id.slice(0, 8)}</td>
                      <td className="px-3 py-2"><StatusBadge status={j.status} /></td>
                      <td className="px-3 py-2 text-zinc-400 text-xs">
                        {j.processed || 0} / {j.total || 0}
                        {j.succeeded ? <span className="text-emerald-400 ml-2"><CheckCircle2 size={12} className="inline" /> {j.succeeded}</span> : null}
                        {j.conversions ? <span className="text-fuchsia-400 ml-2">🎯 {j.conversions}</span> : null}
                        {j.failed ? <span className="text-red-400 ml-2"><XCircle size={12} className="inline" /> {j.failed}</span> : null}
                      </td>
                      <td className="px-3 py-2 text-zinc-500 text-xs">{j.created_at ? new Date(j.created_at).toLocaleString() : ""}</td>
                      <td className="px-3 py-2 text-right space-x-1 whitespace-nowrap">
                        <Button size="sm" variant="outline" onClick={() => startPolling(j.job_id)} className="bg-zinc-800 border-zinc-700 text-zinc-200">View</Button>
                        {(j.status === "running" || j.status === "queued" || j.status === "preparing") && (
                          <Button
                            size="sm"
                            onClick={() => onStop(j.job_id)}
                            title="Stop"
                            className="bg-orange-600 hover:bg-orange-700 text-white"
                            data-testid={`rut-stop-${j.job_id}`}
                          >
                            <StopCircle size={12} />
                          </Button>
                        )}
                        {(j.status === "completed" || j.status === "stopped") && (
                          <>
                            <Button size="sm" onClick={() => onDownload(j.job_id)} className="bg-emerald-600 hover:bg-emerald-700 text-white" title="Download full results ZIP"><Download size={12} /></Button>
                            {j.form_fill_enabled && (
                              <Button
                                size="sm"
                                onClick={() => onDownloadPendingLeads(j.job_id)}
                                className="bg-amber-600 hover:bg-amber-700 text-white"
                                title="Download pending leads (unused rows only, re-uploadable)"
                                data-testid={`rut-download-pending-${j.job_id}`}
                              >
                                <Download size={12} />
                                <span className="ml-1 text-[10px] font-bold">LEADS</span>
                              </Button>
                            )}
                          </>
                        )}
                        <Button size="sm" variant="outline" onClick={() => onDelete(j.job_id)} className="bg-red-900/40 border-red-800 text-red-200 hover:bg-red-900/60"><Trash2 size={12} /></Button>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ═══ Live Activity Modal ═══ */}
      {liveModalOpen && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          data-testid="rut-live-modal"
        >
          <div className="bg-zinc-950 border border-fuchsia-900/50 rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <Activity size={18} className="text-fuchsia-400 animate-pulse" />
                <h3 className="text-white font-semibold">Live Activity — what backend is doing right now</h3>
              </div>
              <button
                onClick={closeLiveModal}
                className="text-zinc-400 hover:text-white p-1 rounded"
                data-testid="rut-live-modal-close"
                aria-label="Close live activity"
              >
                <X size={20} />
              </button>
            </div>
            <div className="px-5 py-3 border-b border-zinc-800 text-xs text-zinc-400 flex items-center justify-between">
              <span>
                Polling every 1.5s · auto-stops when job finishes · steps: <span className="text-zinc-200 font-mono">{liveSteps.length}</span>
              </span>
              <span className="text-zinc-500">Thumbnails are real browser screenshots — click to enlarge.</span>
            </div>
            <div
              className="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-1"
              data-testid="rut-live-modal-body"
            >
              {liveSteps.length === 0 ? (
                <div className="text-center text-zinc-500 py-10">
                  Waiting for the next backend step…
                </div>
              ) : (
                liveSteps.map((s) => {
                  const colorMap = {
                    ok: "text-emerald-300",
                    info: "text-zinc-200",
                    skipped: "text-amber-300",
                    failed: "text-rose-300",
                  };
                  const stageTagColor = {
                    setup: "bg-zinc-800 text-zinc-200",
                    geo: "bg-blue-900/50 text-blue-200",
                    filter: "bg-amber-900/50 text-amber-200",
                    browser: "bg-indigo-900/50 text-indigo-200",
                    landing: "bg-cyan-900/50 text-cyan-200",
                    form: "bg-fuchsia-900/50 text-fuchsia-200",
                    form_filled: "bg-pink-900/50 text-pink-200",
                    submit: "bg-violet-900/50 text-violet-200",
                    post_submit: "bg-purple-900/50 text-purple-200",
                    final: "bg-emerald-900/50 text-emerald-200",
                    done: "bg-emerald-900/50 text-emerald-200",
                  };
                  // If this step has a screenshot, build a secured URL with the auth token.
                  const shotSrc = s.screenshot
                    ? `${API_URL}/api/real-user-traffic/jobs/${activeJob?.job_id}/screenshot/${encodeURIComponent(s.screenshot)}?t=${encodeURIComponent(token())}`
                    : null;
                  return (
                    <div key={s.idx} className="flex gap-2 items-start">
                      <span className="text-zinc-600 w-16 text-right shrink-0 pt-0.5">
                        #{String(s.visit).padStart(3, "0")}
                      </span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold shrink-0 mt-0.5 ${stageTagColor[s.stage] || "bg-zinc-800 text-zinc-200"}`}>
                        {s.stage}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className={`${colorMap[s.status] || "text-zinc-200"} leading-snug break-words`}>
                          {s.detail}
                        </div>
                        {shotSrc && (
                          <button
                            type="button"
                            onClick={() => setPreviewShot(shotSrc)}
                            className="mt-1 block rounded-md overflow-hidden border border-zinc-800 hover:border-fuchsia-500 transition-colors"
                            data-testid={`rut-live-thumb-${s.idx}`}
                            title="Click to enlarge"
                          >
                            <img
                              src={shotSrc}
                              alt={`visit ${s.visit} ${s.stage}`}
                              loading="lazy"
                              className="max-h-28 w-auto block"
                            />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ Diagnostics Modal ═══ */}
      {diagModalOpen && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          data-testid="rut-diag-modal"
        >
          <div className="bg-zinc-950 border border-amber-900/50 rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <AlertTriangle size={18} className="text-amber-400" />
                <h3 className="text-white font-semibold">
                  Diagnostics — macro leaks & stuck visits
                </h3>
              </div>
              <button
                onClick={() => setDiagModalOpen(false)}
                className="text-zinc-400 hover:text-white p-1 rounded"
                data-testid="rut-diag-modal-close"
                aria-label="Close diagnostics"
              >
                <X size={20} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 text-xs space-y-4">
              {diagLoading && (
                <div className="text-center text-zinc-500 py-10">Loading diagnostics…</div>
              )}
              {!diagLoading && diagData && (
                <>
                  {/* ── Macro leaks ── */}
                  <section>
                    <h4 className="text-amber-300 font-semibold mb-2 flex items-center gap-2">
                      <AlertTriangle size={14} /> Macro-leak blocks
                      <span className="text-zinc-500 font-mono text-[11px]">
                        ({diagData.macro_leak_count || 0})
                      </span>
                    </h4>
                    <p className="text-zinc-500 mb-2">
                      Each row = a navigation that was blocked because the URL
                      still contained an unfilled tracker macro
                      (<code className="text-amber-300">{`{{ccpa}}`}</code>,
                      <code className="text-amber-300">{`{{sub}}`}</code>, etc.).
                      Frequent leaks on the same host mean that offer's tracker
                      URL is missing a required parameter — fix it on the
                      affiliate-network side.
                    </p>
                    {(diagData.top_macro_leak_hosts || []).length > 0 && (
                      <div className="mb-2 flex flex-wrap gap-1">
                        {diagData.top_macro_leak_hosts.map((h, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded bg-amber-900/40 border border-amber-800 text-amber-200 font-mono"
                            data-testid={`rut-diag-top-host-${i}`}
                          >
                            {h.host} × {h.count}
                          </span>
                        ))}
                      </div>
                    )}
                    {(diagData.macro_leaks || []).length === 0 ? (
                      <p className="text-zinc-600 italic">No macro leaks recorded for this job.</p>
                    ) : (
                      <div className="max-h-48 overflow-y-auto border border-zinc-800 rounded">
                        <table className="w-full font-mono">
                          <thead className="bg-zinc-900 text-zinc-400 sticky top-0">
                            <tr>
                              <th className="text-left px-2 py-1">Visit</th>
                              <th className="text-left px-2 py-1">Type</th>
                              <th className="text-left px-2 py-1">Blocked URL</th>
                            </tr>
                          </thead>
                          <tbody>
                            {diagData.macro_leaks.map((ev, i) => (
                              <tr
                                key={i}
                                className="border-t border-zinc-900 text-zinc-300"
                                data-testid={`rut-diag-macro-row-${i}`}
                              >
                                <td className="px-2 py-1">#{ev.visit_index}</td>
                                <td className="px-2 py-1 text-zinc-500">{ev.resource_type || "?"}</td>
                                <td className="px-2 py-1 break-all">{ev.blocked_url}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>

                  {/* ── Stuck events ── */}
                  <section>
                    <h4 className="text-rose-300 font-semibold mb-2 flex items-center gap-2">
                      <AlertTriangle size={14} /> Stuck visits
                      <span className="text-zinc-500 font-mono text-[11px]">
                        ({diagData.stuck_event_count || 0})
                      </span>
                    </h4>
                    <p className="text-zinc-500 mb-2">
                      Each row = a visit whose page URL didn't change for
                      &gt;25 seconds while automation steps were running.
                      Clusters around the same URL mean the bot is dying on
                      that specific offer page — usually because the JSON
                      script's selectors don't match.
                    </p>
                    {(diagData.top_stuck_hosts || []).length > 0 && (
                      <div className="mb-2 flex flex-wrap gap-1">
                        {diagData.top_stuck_hosts.map((h, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded bg-rose-900/40 border border-rose-800 text-rose-200 font-mono"
                            data-testid={`rut-diag-stuck-host-${i}`}
                          >
                            {h.host} × {h.count}
                          </span>
                        ))}
                      </div>
                    )}
                    {(diagData.stuck_events || []).length === 0 ? (
                      <p className="text-zinc-600 italic">No stuck visits recorded for this job.</p>
                    ) : (
                      <div className="max-h-48 overflow-y-auto border border-zinc-800 rounded">
                        <table className="w-full font-mono">
                          <thead className="bg-zinc-900 text-zinc-400 sticky top-0">
                            <tr>
                              <th className="text-left px-2 py-1">Visit</th>
                              <th className="text-left px-2 py-1">Stuck (s)</th>
                              <th className="text-left px-2 py-1">URL</th>
                            </tr>
                          </thead>
                          <tbody>
                            {diagData.stuck_events.map((ev, i) => (
                              <tr
                                key={i}
                                className="border-t border-zinc-900 text-zinc-300"
                                data-testid={`rut-diag-stuck-row-${i}`}
                              >
                                <td className="px-2 py-1">#{ev.visit_index}</td>
                                <td className="px-2 py-1 text-rose-300">
                                  {ev.seconds_stuck}
                                </td>
                                <td className="px-2 py-1 break-all">{ev.stuck_url}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>
                </>
              )}
              {!diagLoading && !diagData && (
                <div className="text-center text-zinc-500 py-10">
                  No diagnostics data available for this job.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ Thumbnail lightbox ═══ */}
      {previewShot && (
        <div
          className="fixed inset-0 bg-black/85 backdrop-blur-md z-[60] flex items-center justify-center p-4"
          onClick={() => setPreviewShot(null)}
          data-testid="rut-live-lightbox"
        >
          <button
            type="button"
            onClick={() => setPreviewShot(null)}
            className="absolute top-4 right-4 text-zinc-300 hover:text-white p-2 rounded-full bg-zinc-900/70 border border-zinc-700"
            aria-label="Close preview"
            data-testid="rut-live-lightbox-close"
          >
            <X size={22} />
          </button>
          <img
            src={previewShot}
            alt="Visit screenshot full size"
            className="max-w-[95vw] max-h-[90vh] object-contain rounded-md shadow-2xl border border-zinc-800"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }) {
  const colorMap = { emerald: "text-emerald-300", amber: "text-amber-300", red: "text-red-300", fuchsia: "text-fuchsia-300" };
  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${colorMap[color] || "text-zinc-100"}`}>{value}</div>
    </div>
  );
}

function CheckRow({ testId, checked, onChange, children }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 accent-fuchsia-500"
        data-testid={testId}
      />
      {children}
    </label>
  );
}
