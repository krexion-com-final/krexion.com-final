import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Activity, Wrench, RefreshCw, CheckCircle2, AlertTriangle, XCircle, Loader2, Database, Cpu, HardDrive, MemoryStick, Cog, Sheet } from "lucide-react";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { useToast } from "../hooks/use-toast";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Visual config per check key — title, icon, friendly description.
const CHECK_META = {
  mongodb:        { title: "MongoDB",         icon: Database,    blurb: "Database connection — clicks, jobs, uploads ka storage" },
  playwright:     { title: "Playwright",      icon: Cpu,         blurb: "Browser engine — Real User Traffic ke visits ke liye" },
  memory:         { title: "Memory",          icon: MemoryStick, blurb: "Backend RAM usage — agar 80% hua to throttle on" },
  disk:           { title: "Disk Space",      icon: HardDrive,   blurb: "Free space — old job ZIPs / pending leads" },
  gsheet_sa:      { title: "Google Sheets SA",icon: Sheet,       blurb: "Service Account — gsheet-backed uploads aur live row delete" },
  active_rut_jobs:{ title: "Active RUT Jobs", icon: Cog,         blurb: "Live Real User Traffic jobs running" },
};

// Status → color/icon mapping for tile borders + status pill.
const STATUS_STYLE = {
  ok:   { ring: "ring-emerald-500/40", pill: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", glow: "shadow-emerald-500/10", Icon: CheckCircle2,   iconClass: "text-emerald-400" },
  warn: { ring: "ring-amber-500/40",   pill: "bg-amber-500/15 text-amber-300 border-amber-500/30",       glow: "shadow-amber-500/10",   Icon: AlertTriangle,  iconClass: "text-amber-400" },
  fail: { ring: "ring-rose-500/40",    pill: "bg-rose-500/15 text-rose-300 border-rose-500/30",          glow: "shadow-rose-500/15",    Icon: XCircle,         iconClass: "text-rose-400" },
};

const OVERALL_STYLE = {
  ok:   { label: "Healthy",    color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/40" },
  warn: { label: "Attention",  color: "text-amber-400",   bg: "bg-amber-500/10 border-amber-500/40" },
  fail: { label: "Critical",   color: "text-rose-400",    bg: "bg-rose-500/10 border-rose-500/40" },
};

export default function SystemHealthPage() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [repairing, setRepairing] = useState(false);
  const [lastRepair, setLastRepair] = useState(null);
  const { toast } = useToast();

  const fetchHealth = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/diagnostics/health`, { timeout: 12000 });
      setHealth(data);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Failed to fetch health");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial + 8s auto-refresh
  useEffect(() => {
    fetchHealth();
    const id = setInterval(fetchHealth, 8000);
    return () => clearInterval(id);
  }, [fetchHealth]);

  const runRepair = async () => {
    setRepairing(true);
    try {
      const token = localStorage.getItem("token");
      const { data } = await axios.post(
        `${API}/diagnostics/repair`,
        {},
        { headers: { Authorization: `Bearer ${token}` }, timeout: 150000 }
      );
      setLastRepair(data);
      const { ok_count, fail_count } = data;
      if (fail_count === 0) {
        toast({ title: "Auto-Repair complete ✨", description: `${ok_count} action(s) succeeded.` });
      } else {
        toast({
          title: "Auto-Repair finished",
          description: `${ok_count} OK · ${fail_count} failed — see details below`,
          variant: "destructive",
        });
      }
      // Re-fetch health after repair
      setTimeout(fetchHealth, 500);
    } catch (e) {
      toast({
        title: "Repair failed",
        description: e.response?.data?.detail || e.message || "Unknown error",
        variant: "destructive",
      });
    } finally {
      setRepairing(false);
    }
  };

  if (loading && !health) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-3 text-muted-foreground">Loading system health…</span>
      </div>
    );
  }

  const overall = health?.overall || "warn";
  const overallStyle = OVERALL_STYLE[overall] || OVERALL_STYLE.warn;
  const checks = health?.checks || {};
  const hasIssues = Object.values(checks).some((c) => c.status !== "ok");

  return (
    <div className="space-y-6 p-1" data-testid="system-health-page">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3">
            <Activity className="h-7 w-7 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight" data-testid="system-health-title">
              System Health
            </h1>
            <div
              className={`flex items-center gap-2 px-3 py-1 rounded-full border text-sm font-semibold ${overallStyle.bg} ${overallStyle.color}`}
              data-testid="system-health-overall-badge"
            >
              <span className="h-2 w-2 rounded-full bg-current animate-pulse" />
              {overallStyle.label}
            </div>
          </div>
          <p className="text-sm text-muted-foreground mt-1.5">
            Job chalane se pehle yahaan check kar lein. Agar koi tile <span className="text-amber-400">yellow</span> ya <span className="text-rose-400">red</span> hai, neeche <strong>Auto Repair</strong> dabayein — sab apne aap fix ho jayega.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchHealth}
            disabled={loading}
            data-testid="system-health-refresh-btn"
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={runRepair}
            disabled={repairing}
            data-testid="system-health-repair-btn"
            className="gap-2 bg-emerald-600 hover:bg-emerald-500 text-white"
          >
            {repairing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wrench className="h-4 w-4" />}
            {repairing ? "Repairing…" : (hasIssues ? "Auto Repair All" : "Run Auto Repair")}
          </Button>
        </div>
      </div>

      {error && (
        <Card className="p-4 border-rose-500/40 bg-rose-500/5">
          <div className="flex items-start gap-3 text-sm">
            <XCircle className="h-5 w-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-rose-300">Health endpoint error</div>
              <div className="text-rose-200/70 mt-1">{error}</div>
            </div>
          </div>
        </Card>
      )}

      {/* Tile Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="system-health-grid">
        {Object.entries(CHECK_META).map(([key, meta]) => {
          const check = checks[key];
          if (!check) return null;
          const style = STATUS_STYLE[check.status] || STATUS_STYLE.warn;
          const Icon = meta.icon;
          const StatusIcon = style.Icon;
          return (
            <Card
              key={key}
              className={`relative p-5 transition-all hover:scale-[1.02] hover:shadow-lg ring-1 ${style.ring} ${style.glow} shadow-lg`}
              data-testid={`system-health-tile-${key}`}
            >
              {/* Status pill */}
              <div
                className={`absolute top-4 right-4 flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold uppercase tracking-wide ${style.pill}`}
                data-testid={`system-health-tile-${key}-status`}
              >
                <StatusIcon className={`h-3.5 w-3.5 ${style.iconClass}`} />
                {check.status}
              </div>

              {/* Icon + Title */}
              <div className="flex items-start gap-3 mb-3 pr-20">
                <div className={`p-2.5 rounded-lg bg-muted ${style.iconClass}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-bold text-base leading-tight">{meta.title}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">{meta.blurb}</p>
                </div>
              </div>

              {/* Value */}
              <div className="mt-4">
                <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Reading</div>
                <div className="text-sm font-mono font-medium break-words" data-testid={`system-health-tile-${key}-value`}>
                  {check.value || "(no data)"}
                </div>
              </div>

              {/* Hint (only when not OK) */}
              {check.hint && check.status !== "ok" && (
                <div className="mt-3 pt-3 border-t border-border">
                  <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Suggested Action</div>
                  <div className="text-xs text-foreground/80 leading-relaxed">{check.hint}</div>
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {/* Last repair report */}
      {lastRepair && (
        <Card className="p-5" data-testid="system-health-last-repair">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-base flex items-center gap-2">
              <Wrench className="h-4 w-4 text-emerald-400" />
              Last Auto-Repair Run
            </h3>
            <div className="text-xs text-muted-foreground">
              {new Date(lastRepair.repaired_at).toLocaleString()}
            </div>
          </div>
          <div className="text-sm mb-3">
            <span className="text-emerald-400 font-semibold">{lastRepair.ok_count} succeeded</span>
            {lastRepair.fail_count > 0 && (
              <>
                {" · "}
                <span className="text-rose-400 font-semibold">{lastRepair.fail_count} failed</span>
              </>
            )}
          </div>
          <div className="space-y-2">
            {lastRepair.actions.map((a, i) => {
              const isOk = a.status === "ok";
              const RowIcon = isOk ? CheckCircle2 : XCircle;
              const rowColor = isOk ? "text-emerald-400" : "text-rose-400";
              return (
                <div key={i} className="flex items-start gap-3 text-sm py-1.5">
                  <RowIcon className={`h-4 w-4 flex-shrink-0 mt-0.5 ${rowColor}`} />
                  <div className="flex-1 min-w-0">
                    <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground mr-2">
                      {a.name}
                    </span>
                    <span className="text-foreground/80">{a.detail}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Footer info */}
      <div className="text-xs text-muted-foreground text-center pt-4">
        Auto-refresh every 8 s · Last checked: {health?.checked_at ? new Date(health.checked_at).toLocaleTimeString() : "—"}
      </div>
    </div>
  );
}
