import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { ArrowLeft, RefreshCw, ChevronDown, ChevronRight, CheckCircle2, XCircle, Loader2, Circle } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const stColor = (s) => ({
  queued: "secondary",
  running: "default",
  installed: "default",
  conversion_likely: "default",
  failed: "destructive",
}[s] || "secondary");

const stIcon = (s) => ({
  queued: "○",
  running: "↻",
  installed: "▶",
  conversion_likely: "✓",
  failed: "✗",
}[s] || "○");

// Friendly step labels (Roman Urdu friendly)
const stepLabels = {
  reset_state: "Phone reset (clear app data)",
  fingerprint: "Fingerprint apply (locale/GAID/timezone)",
  proxy_set: "Proxy configure on device",
  click_tracker_serverside: "Server-side click (proxy se)",
  click_tracker: "Phone Chrome se click",
  apk_resolved: "APK URL resolve",
  install: "APK install on device",
  install_referrer_broadcast: "INSTALL_REFERRER broadcast",
  app_opened: "App launch",
  behavior_sim: "Behavior simulate (scroll/tap)",
  settle: "Settle wait (SDK fire conversion)",
  cleanup: "Cleanup (uninstall + proxy off)",
  exception: "Exception (error)",
};

function StepIcon({ ok, isLast, isRunning }) {
  if (isRunning) return <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin" />;
  if (ok === false) return <XCircle className="h-3.5 w-3.5 text-red-500" />;
  if (ok === true) return <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />;
  return <Circle className="h-3.5 w-3.5 text-muted-foreground" />;
}

function StepRow({ step, isLast, isRunning }) {
  const label = stepLabels[step.name] || step.name;
  const extras = Object.entries(step)
    .filter(([k]) => !["name", "ok", "ts"].includes(k))
    .map(([k, v]) => `${k}=${typeof v === "string" ? v.slice(0, 80) : v}`)
    .join(" · ");
  return (
    <div className="flex items-start gap-2 py-1 text-xs">
      <StepIcon ok={step.ok} isLast={isLast} isRunning={isRunning} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={step.ok === false ? "text-red-500 font-medium" : "font-medium"}>{label}</span>
          <span className="text-muted-foreground text-[10px]">{step.ts ? `+${step.ts.toFixed(1)}s` : ""}</span>
        </div>
        {extras && <div className="text-muted-foreground text-[10px] truncate mt-0.5">{extras}</div>}
      </div>
    </div>
  );
}

function AttemptDetail({ a, isExpanded, onToggle }) {
  const isLive = a.status === "running" || a.status === "queued";
  const steps = a.steps || [];

  return (
    <>
      <tr className="border-t hover:bg-muted/20 cursor-pointer" data-testid={`cpi-attempt-row-${a.id}`} onClick={onToggle}>
        <td className="p-2 text-muted-foreground">
          <div className="flex items-center gap-1">
            {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            #{a.idx}
          </div>
        </td>
        <td className="p-2">
          <span className="inline-flex items-center gap-1">
            {isLive && <Loader2 className="h-3 w-3 animate-spin text-blue-500" />}
            <span>{stIcon(a.status)}</span>
            <Badge variant={stColor(a.status)} className="text-[10px]">{a.status}</Badge>
          </span>
        </td>
        <td className="p-2 text-muted-foreground">{a.started_at ? new Date(a.started_at).toLocaleTimeString() : "—"}</td>
        <td className="p-2 text-muted-foreground">{a.duration_seconds == null ? (isLive ? "running…" : "—") : `${Math.round(a.duration_seconds)}s`}</td>
        <td className="p-2 text-muted-foreground">{a.device_label || "—"}</td>
        <td className="p-2 text-muted-foreground font-mono text-[10px] truncate max-w-[200px]">
          {a.proxy_used ? a.proxy_used.split(":").slice(0, 2).join(":") : "—"}
        </td>
        <td className="p-2 text-muted-foreground">
          {a.failure_reason ? <span className="text-red-500 font-medium">{a.failure_reason}</span> : (
            <span>
              {steps.length} steps
              {isLive && steps.length > 0 && (
                <span className="text-blue-500 ml-2">
                  → {stepLabels[steps[steps.length - 1]?.name] || steps[steps.length - 1]?.name}
                </span>
              )}
            </span>
          )}
        </td>
      </tr>
      {isExpanded && (
        <tr className="border-t bg-muted/10">
          <td colSpan={7} className="p-3">
            <div className="text-xs font-medium text-muted-foreground mb-2">Step-by-step:</div>
            {steps.length === 0 ? (
              <div className="text-xs text-muted-foreground italic">
                {isLive ? "Worker just started — abhi steps log nahi aayi" : "Koi step record nahi"}
              </div>
            ) : (
              <div className="border-l-2 border-muted pl-3 space-y-0.5">
                {steps.map((s, i) => (
                  <StepRow key={i} step={s} isLast={i === steps.length - 1} isRunning={isLive && i === steps.length - 1} />
                ))}
                {isLive && (
                  <div className="flex items-center gap-2 py-1 text-xs text-blue-500">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span className="font-medium">Live · agla step chal raha hai...</span>
                  </div>
                )}
              </div>
            )}
            {a.failure_reason && (
              <div className="mt-3 p-2 rounded border border-red-500/20 bg-red-500/5 text-xs">
                <span className="font-medium text-red-500">Failure: </span>
                <span className="text-red-400 font-mono">{a.failure_reason}</span>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function CPIJobDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [attempts, setAttempts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({});

  const token = localStorage.getItem("token");
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const load = async () => {
    try {
      const [j, a] = await Promise.all([
        axios.get(`${API}/cpi/jobs/${id}`, auth),
        axios.get(`${API}/cpi/jobs/${id}/attempts`, auth),
      ]);
      setJob(j.data);
      const list = (a.data || []).map((x, i) => ({ ...x, idx: i + 1 }));
      setAttempts(list);
      // Auto-expand the latest live attempt
      const live = list.find((x) => x.status === "running" || x.status === "queued");
      if (live && expanded[live.id] === undefined) {
        setExpanded((e) => ({ ...e, [live.id]: true }));
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load job");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // Faster polling for live jobs (2s); slow when finished (10s)
    const isFinished = job?.status === "completed" || job?.status === "failed";
    const interval = isFinished ? 10000 : 2000;
    const t = setInterval(load, interval);
    return () => clearInterval(t);
  }, [id, job?.status]); // eslint-disable-line

  const toggle = (aid) => setExpanded((e) => ({ ...e, [aid]: !e[aid] }));

  if (loading) return <div className="text-sm text-muted-foreground">Loading…</div>;
  if (!job) return <div className="text-sm text-muted-foreground">Job not found</div>;

  const total = job.target_count || 1;
  const done = (job.completed || 0) + (job.failed || 0);
  const pct = Math.round((done / total) * 100);
  const fmtTime = (s) => s ? new Date(s).toLocaleTimeString() : "—";
  const isLiveJob = job.status !== "completed" && job.status !== "failed";

  return (
    <div className="space-y-6" data-testid="cpi-job-detail-page">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate("/cpi/jobs")} data-testid="cpi-job-back-btn">
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{job.offer_name}</h1>
          <p className="text-sm text-muted-foreground">
            Job · {job.target_os} · created {fmtTime(job.created_at)}
            {isLiveJob && (
              <span className="ml-3 inline-flex items-center gap-1 text-blue-500">
                <Loader2 className="h-3 w-3 animate-spin" /> live
              </span>
            )}
          </p>
        </div>
        <Badge variant={stColor(job.status)} data-testid="cpi-job-status">{job.status}</Badge>
        <Button variant="ghost" size="sm" onClick={load} data-testid="cpi-job-refresh-btn"><RefreshCw className="h-4 w-4" /></Button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="border rounded-lg p-4">
          <div className="text-xs text-muted-foreground">Completed</div>
          <div className="text-2xl font-bold text-green-500">{job.completed || 0}</div>
        </div>
        <div className="border rounded-lg p-4">
          <div className="text-xs text-muted-foreground">Failed</div>
          <div className="text-2xl font-bold text-red-500">{job.failed || 0}</div>
        </div>
        <div className="border rounded-lg p-4">
          <div className="text-xs text-muted-foreground">Running</div>
          <div className="text-2xl font-bold text-yellow-500">{job.in_progress || 0}</div>
        </div>
        <div className="border rounded-lg p-4">
          <div className="text-xs text-muted-foreground">Target</div>
          <div className="text-2xl font-bold">{total}</div>
        </div>
      </div>

      <div className="border rounded-lg p-4 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm font-medium">Progress</div>
          <div className="text-xs text-muted-foreground">{done} / {total} ({pct}%)</div>
        </div>
        <Progress value={pct} className="h-3" />
      </div>

      <div className="border rounded-lg overflow-hidden">
        <div className="bg-muted/50 p-3 text-sm font-medium flex items-center justify-between">
          <span>Live Install Log</span>
          <span className="text-xs text-muted-foreground font-normal">
            Tip: Status row par click karein to step-by-step detail dikhega
          </span>
        </div>
        <div className="max-h-[600px] overflow-auto">
          <table className="w-full text-xs">
            <thead className="bg-muted/30 sticky top-0">
              <tr>
                <th className="text-left p-2 w-16">#</th>
                <th className="text-left p-2">Status</th>
                <th className="text-left p-2">Started</th>
                <th className="text-left p-2">Duration</th>
                <th className="text-left p-2">Device</th>
                <th className="text-left p-2">Proxy</th>
                <th className="text-left p-2">Current Step / Failure</th>
              </tr>
            </thead>
            <tbody>
              {attempts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-muted-foreground text-xs">
                    Abhi koi attempt nahi — worker job pickup karne ka wait kar raha hai.
                  </td>
                </tr>
              ) : (
                attempts.map((a) => (
                  <AttemptDetail
                    key={a.id}
                    a={a}
                    isExpanded={!!expanded[a.id]}
                    onToggle={() => toggle(a.id)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
