import React, { useEffect, useState } from "react";
import axios from "axios";
import { RefreshCw, Activity, AlertCircle, Wifi, WifiOff, Server } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SyncHeartbeatsPage() {
  const [data, setData] = useState({ count: 0, heartbeats: [] });
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const token =
        localStorage.getItem("adminToken") ||
        localStorage.getItem("admin_token") ||
        localStorage.getItem("token");
      const r = await axios.get(`${API}/admin/sync/heartbeats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load heartbeats");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const isOnline = (iso) => {
    if (!iso) return false;
    return Date.now() - new Date(iso).getTime() < 2 * 60 * 1000; // <2 min
  };

  const timeAgo = (iso) => {
    if (!iso) return "—";
    const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="sync-heartbeats-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Server className="text-[#A78BFA]" size={22} />
            Customer Installs — Live Status
          </h1>
          <p className="text-sm text-[#A1A1AA] mt-1">
            Real-time heartbeats from desktop installs (auto-refresh every 30s)
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          data-testid="refresh-heartbeats"
          className="flex items-center gap-2 bg-white/5 border border-white/10 px-4 py-2 rounded-md hover:bg-white/10 transition text-sm disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white/[0.03] border border-white/10 rounded-xl p-5">
          <div className="text-xs uppercase tracking-wider text-[#71717A] mb-1">Active in last 24h</div>
          <div className="text-3xl font-bold">{data.count}</div>
        </div>
        <div className="bg-white/[0.03] border border-white/10 rounded-xl p-5">
          <div className="text-xs uppercase tracking-wider text-[#71717A] mb-1">Currently online (&lt;2 min)</div>
          <div className="text-3xl font-bold text-[#22C55E]">
            {data.heartbeats.filter((h) => isOnline(h.last_seen)).length}
          </div>
        </div>
        <div className="bg-white/[0.03] border border-white/10 rounded-xl p-5">
          <div className="text-xs uppercase tracking-wider text-[#71717A] mb-1">Unique IPs</div>
          <div className="text-3xl font-bold">
            {new Set(data.heartbeats.map((h) => h.ip).filter(Boolean)).size}
          </div>
        </div>
      </div>

      <div className="bg-white/[0.02] border border-white/10 rounded-xl overflow-hidden">
        {data.heartbeats.length === 0 ? (
          <div className="text-center py-12 text-[#71717A]">
            <AlertCircle className="mx-auto mb-3" size={28} />
            <p>No customer installs have reported in the last 24 hours.</p>
            <p className="text-xs mt-1">When customers run the desktop app, they'll appear here.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-white/[0.03] text-[#A1A1AA] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Customer</th>
                <th className="text-left px-4 py-3">License</th>
                <th className="text-left px-4 py-3">Hostname</th>
                <th className="text-left px-4 py-3">Version</th>
                <th className="text-left px-4 py-3">IP</th>
                <th className="text-right px-4 py-3">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {data.heartbeats.map((h) => {
                const online = isOnline(h.last_seen);
                return (
                  <tr key={h.license_key} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="px-4 py-3">
                      {online ? (
                        <span className="inline-flex items-center gap-1.5 text-[#22C55E] text-xs font-medium">
                          <Wifi size={12} /> online
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-[#71717A] text-xs font-medium">
                          <WifiOff size={12} /> offline
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">{h.email}</td>
                    <td className="px-4 py-3 font-mono text-xs text-[#A78BFA]">
                      {h.license_key?.slice(0, 16)}…
                    </td>
                    <td className="px-4 py-3">{h.hostname || "—"}</td>
                    <td className="px-4 py-3 text-xs text-[#A1A1AA]">{h.version || "—"}</td>
                    <td className="px-4 py-3 font-mono text-xs">{h.ip || "—"}</td>
                    <td className="px-4 py-3 text-right text-xs text-[#A1A1AA]">
                      {timeAgo(h.last_seen)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="mt-6 text-xs text-[#71717A] flex items-center gap-2">
        <Activity size={12} />
        Each customer's desktop install heartbeats every 30 seconds — push links + pull clicks happen in the same cycle.
      </div>
    </div>
  );
}
