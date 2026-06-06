/* ════════════════════════════════════════════════════════════════════════
   LicensePage.js — Customer-facing license dashboard
   ════════════════════════════════════════════════════════════════════════

   Shown at /license. Lets the logged-in customer:
     • See their license key, plan status, days remaining
     • See which PC their license is currently bound to
     • Release the current PC binding (so they can re-activate on
       another machine without contacting support)

   Backend endpoints used:
     GET  /api/license/me            — read-only view of own license
     POST /api/license/deactivate-me — release current machine binding

   NEVER touches business data (clicks, conversions, RUT jobs, etc.).
   Purely a license-management surface.
   ════════════════════════════════════════════════════════════════════════ */

import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  KeyRound, Monitor, CalendarClock, ShieldCheck, ShieldAlert,
  ShieldX, RefreshCw, LogOut, ExternalLink, Copy, Crown, Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle, AlertDialogTrigger,
} from "../components/ui/alert-dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Status → badge style + icon. Mirrors the wording the customer sees
// in their purchase email so the experience is consistent.
const STATUS_META = {
  active:                { label: "Active",            cls: "bg-emerald-600 text-white",  Icon: ShieldCheck },
  trial:                 { label: "Trial",             cls: "bg-blue-600 text-white",     Icon: ShieldCheck },
  expired:               { label: "Expired",           cls: "bg-amber-600 text-white",    Icon: ShieldAlert },
  revoked:               { label: "Revoked",           cls: "bg-red-700 text-white",      Icon: ShieldX },
  deactivated_by_takeover: { label: "Moved to another PC", cls: "bg-zinc-700 text-white", Icon: ShieldAlert },
};

function StatusBadge({ status }) {
  const m = STATUS_META[status] || { label: status || "Unknown", cls: "bg-zinc-700 text-white", Icon: ShieldAlert };
  const { Icon } = m;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium ${m.cls}`}
      data-testid="license-status-badge"
    >
      <Icon size={12} />
      {m.label}
    </span>
  );
}

function MaskedKey({ value }) {
  if (!value) return <span className="text-zinc-500">—</span>;
  // Show first 4 + last 4 chars: KRX1...AB9F
  const head = value.slice(0, 4);
  const tail = value.slice(-4);
  return (
    <span className="font-mono text-sm">
      {head}<span className="text-zinc-500 mx-1">••••••••••</span>{tail}
    </span>
  );
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function LicensePage() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [deactivating, setDeactivating] = useState(false);
  const [showKey, setShowKey] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  // Fetch license info. Reused after deactivation to refresh the view.
  async function fetchLicense() {
    try {
      const r = await axios.get(`${API}/license/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(r.data);
    } catch (e) {
      console.error("[license/me] failed:", e);
      toast.error(e?.response?.data?.detail || "Could not load license info.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/license/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setData(r.data);
      } catch (e) {
        if (!cancelled) {
          console.error("[license/me] failed:", e);
          toast.error(e?.response?.data?.detail || "Could not load license info.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const load = fetchLicense;

  const copyKey = async () => {
    const k = data?.license?.license_key;
    if (!k) return;
    try {
      await navigator.clipboard.writeText(k);
      toast.success("License key copied to clipboard.");
    } catch {
      toast.error("Copy failed — please select the key manually.");
    }
  };

  const releasePc = async () => {
    setDeactivating(true);
    try {
      await axios.post(`${API}/license/deactivate-me`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success("This PC has been released from your license.");
      await load();
    } catch (e) {
      console.error("[deactivate-me] failed:", e);
      toast.error(e?.response?.data?.detail || "Could not release this PC.");
    } finally {
      setDeactivating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]" data-testid="license-loading">
        <Loader2 className="animate-spin text-zinc-400" size={28} />
      </div>
    );
  }

  // Licensing globally disabled — show a friendly note instead of an empty page.
  if (data && data.licensing_enabled === false) {
    return (
      <div className="p-6">
        <Card className="bg-zinc-950/60 border border-zinc-800" data-testid="license-disabled-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <Crown size={18} /> License
            </CardTitle>
            <CardDescription>
              Licensing is currently disabled on this Krexion instance. You
              have full access to every feature.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const lic = data?.license;

  // No license tied to this account yet — common right after first signup
  // before the customer purchases. Surface a clean call-to-action.
  if (!lic) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <Card className="bg-zinc-950/60 border border-zinc-800" data-testid="license-empty-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <KeyRound size={18} /> No license on this account yet
            </CardTitle>
            <CardDescription className="text-zinc-400">
              Your Krexion account exists, but no license key is currently
              tied to <span className="text-white">{(JSON.parse(localStorage.getItem("user") || "{}")).email || "your email"}</span>.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => window.open("https://krexion.com/pricing", "_blank", "noopener")}
              data-testid="license-buy-btn"
              className="bg-blue-600 hover:bg-blue-500"
            >
              <ExternalLink size={14} className="mr-2" /> View plans
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const days = lic.days_remaining;
  const lowDays = typeof days === "number" && days <= 7;
  const noDays = typeof days === "number" && days <= 0;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4" data-testid="license-page">
      {/* ── Header card ────────────────────────────────────────────── */}
      <Card className="bg-zinc-950/60 border border-zinc-800">
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <Crown size={18} /> Your Krexion License
            </CardTitle>
            <CardDescription className="text-zinc-400 mt-1">
              Subscription status, machine binding and renewal.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={lic.status} />
            <Button
              size="sm"
              variant="ghost"
              onClick={load}
              data-testid="license-refresh-btn"
              className="text-zinc-400 hover:text-white"
            >
              <RefreshCw size={14} />
            </Button>
          </div>
        </CardHeader>
      </Card>

      {/* ── License key ───────────────────────────────────────────── */}
      <Card className="bg-zinc-950/60 border border-zinc-800">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-md bg-blue-600/10 border border-blue-600/30 flex items-center justify-center">
                <KeyRound size={18} className="text-blue-400" />
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-zinc-500">License key</div>
                <div className="text-white mt-0.5" data-testid="license-key-display">
                  {showKey ? (
                    <span className="font-mono text-sm">{lic.license_key}</span>
                  ) : (
                    <MaskedKey value={lic.license_key} />
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => setShowKey(s => !s)}
                data-testid="license-toggle-show">
                {showKey ? "Hide" : "Show"}
              </Button>
              <Button size="sm" variant="outline" onClick={copyKey}
                data-testid="license-copy-key">
                <Copy size={14} className="mr-1" /> Copy
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Days remaining + plan ─────────────────────────────────── */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card className="bg-zinc-950/60 border border-zinc-800">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-md bg-emerald-600/10 border border-emerald-600/30 flex items-center justify-center">
                <CalendarClock size={18} className="text-emerald-400" />
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-zinc-500">Days remaining</div>
                <div className={`text-2xl font-semibold mt-0.5 ${noDays ? "text-red-400" : lowDays ? "text-amber-400" : "text-white"}`}
                  data-testid="license-days-remaining">
                  {typeof days === "number" ? `${days}d` : "—"}
                </div>
                <div className="text-xs text-zinc-500 mt-0.5">
                  Renews / expires: {fmtDate(lic.subscription_ends_at || lic.trial_ends_at)}
                </div>
              </div>
            </div>
            {lowDays && (
              <div className="mt-3 text-xs text-amber-400" data-testid="license-low-warning">
                {noDays ? "Your subscription has ended — renew to continue using Krexion." : "Your subscription ends soon. Renew now to avoid interruption."}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-zinc-950/60 border border-zinc-800">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-md bg-purple-600/10 border border-purple-600/30 flex items-center justify-center">
                <Crown size={18} className="text-purple-400" />
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-zinc-500">Plan</div>
                <div className="text-white font-medium mt-0.5" data-testid="license-plan-name">
                  {lic.status === "trial" ? "Free Trial" : lic.status === "active" ? "Pro" : (lic.status || "—")}
                </div>
                <div className="text-xs text-zinc-500 mt-0.5">
                  Activated: {fmtDate(lic.activated_at)}
                </div>
              </div>
            </div>
            <Button
              size="sm"
              className="mt-4 bg-blue-600 hover:bg-blue-500"
              onClick={() => window.open("https://krexion.com/pricing", "_blank", "noopener")}
              data-testid="license-renew-btn"
            >
              <ExternalLink size={14} className="mr-2" /> Renew / upgrade
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* ── Bound PC ───────────────────────────────────────────────── */}
      <Card className="bg-zinc-950/60 border border-zinc-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white text-sm">
            <Monitor size={16} /> Bound PC
          </CardTitle>
          <CardDescription className="text-zinc-400">
            One license = {data.max_pcs} active PC{data.max_pcs > 1 ? "s" : ""} at a time.
            Activating on a new PC silently moves the seat — but you can also
            release this PC manually below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between flex-wrap gap-3 rounded-md bg-zinc-900/60 border border-zinc-800 p-3">
            <div>
              <div className="text-white font-medium" data-testid="license-machine-label">
                {lic.machine_label || "(unnamed PC)"}
              </div>
              <div className="text-xs text-zinc-500 mt-0.5">
                ID: <span className="font-mono">{lic.machine_id_short || "—"}</span> ·
                Last seen: {fmtDate(lic.last_validated_at)}
              </div>
            </div>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={!lic.machine_id_short || deactivating}
                  data-testid="license-release-pc-btn"
                >
                  {deactivating ? <Loader2 size={14} className="animate-spin mr-1" /> : <LogOut size={14} className="mr-1" />}
                  Release this PC
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent data-testid="license-release-confirm">
                <AlertDialogHeader>
                  <AlertDialogTitle>Release this PC from your license?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Your license seat will be free immediately. Krexion on this PC
                    will stop working until you re-activate (you can re-activate
                    on this PC or any other PC at any time).
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel data-testid="license-release-cancel">Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={releasePc}
                    className="bg-red-600 hover:bg-red-500"
                    data-testid="license-release-confirm-btn"
                  >
                    Release PC
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          {data.max_pcs > 1 && (
            <div className="mt-3 text-xs text-zinc-500" data-testid="license-machines-used">
              Active PCs on this license: <span className="text-zinc-300">{lic.machines_used} / {data.max_pcs}</span>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
