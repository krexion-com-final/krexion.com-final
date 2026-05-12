import { useEffect, useState } from "react";
import axios from "axios";
import { TrendingUp, Smartphone, CheckCircle2, XCircle, Activity, DollarSign, Cpu } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import useVisibleInterval from "../hooks/useVisibleInterval";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CPIDashboardPage() {
  const [stats, setStats] = useState(null);
  const [period, setPeriod] = useState("today");
  const [loading, setLoading] = useState(true);

  const token = localStorage.getItem("token");
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const load = async (p) => {
    try {
      const r = await axios.get(`${API}/cpi/dashboard/stats?period=${p}`, auth);
      setStats(r.data);
    } catch (e) {
      // fail silently
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(period);
  }, [period]); // eslint-disable-line
  // Polls only while tab is visible — saves CPU/bandwidth on backgrounded tabs.
  useVisibleInterval(() => load(period), 8000);

  const Card = ({ icon: Icon, label, value, sub, color = "" }) => (
    <div className="border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <Icon className={`h-4 w-4 ${color || "text-muted-foreground"}`} />
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );

  return (
    <div className="space-y-6" data-testid="cpi-dashboard-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">CPI Dashboard</h1>
          <p className="text-sm text-muted-foreground">Live overview of your install operations</p>
        </div>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="w-[140px]" data-testid="cpi-dashboard-period">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="today">Today</SelectItem>
            <SelectItem value="week">Last 7 days</SelectItem>
            <SelectItem value="month">Last 30 days</SelectItem>
            <SelectItem value="all">All time</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading || !stats ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card icon={DollarSign} label="Earnings (est.)" value={`$${stats.earnings.toFixed(2)}`} sub={`Period: ${stats.period}`} color="text-green-500" />
            <Card icon={CheckCircle2} label="Conversions" value={stats.completed_installs} sub={`${stats.success_rate}% success rate`} color="text-green-500" />
            <Card icon={XCircle} label="Failures" value={stats.failed_installs} color="text-red-500" />
            <Card icon={Activity} label="Running" value={stats.running_installs} color="text-yellow-500" />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <Card icon={Cpu} label="Active Jobs" value={stats.active_jobs} />
            <Card icon={Smartphone} label="Devices Online" value={stats.devices_online} />
            <Card icon={TrendingUp} label="Total Attempts" value={stats.total_attempts} sub="incl. running" />
          </div>

          <div className="border rounded-lg p-6 space-y-3">
            <h2 className="text-lg font-semibold">Verification Note</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Earnings shown here are <strong>estimates</strong> based on completed install workflows × your offer's payout.
              The actual conversion is confirmed only on your CPI network's panel. After each install, the worker waits the
              configured "settle" delay (default 45s) for the app's tracking SDK to fire, then marks the attempt as
              <span className="inline-block px-1.5 py-0.5 mx-1 bg-green-500/20 text-green-500 rounded text-xs">conversion_likely</span>.
              Always cross-check totals on the network dashboard before counting earnings.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
