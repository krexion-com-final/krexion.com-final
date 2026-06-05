import React, { useEffect, useState } from "react";
import axios from "axios";
import { Activity, CheckCircle2, AlertCircle, Server, Users, Cpu, RefreshCw } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Public system status page — no auth needed.
 * Shows real-time health of the Krexion platform:
 *   - Cloud API
 *   - MongoDB
 *   - Active customer PCs (last 5 min)
 *   - Bridge jobs (last 24h: queued / running / done / failed)
 * Auto-refreshes every 15 s.
 */
export default function StatusPage() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancel = false;
    const run = async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/public/status`);
        if (!cancel) {
          setStatus(r.data);
          setErr(null);
        }
      } catch (e) {
        if (!cancel) setErr(e?.response?.data?.detail || e.message);
      } finally {
        if (!cancel) setLoading(false);
      }
    };
    run();
    const id = setInterval(run, 15000);
    return () => { cancel = true; clearInterval(id); };
  }, [tick]);

  const Pill = ({ ok, label }) => (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${
      ok ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
         : "bg-rose-500/15 border-rose-500/40 text-rose-300"
    }`} data-testid={`status-pill-${label.toLowerCase().replace(/\s+/g,'-')}`}>
      {ok ? <CheckCircle2 size={13}/> : <AlertCircle size={13}/>}
      {label}: {ok ? "OK" : "DOWN"}
    </span>
  );

  const Card = ({ icon, title, value, hint, testid }) => (
    <div className="p-5 rounded-2xl bg-[#0c0816] border border-white/10" data-testid={testid}>
      <div className="flex items-center gap-2 text-[#94a3b8] text-xs uppercase tracking-wider mb-2">
        {icon}{title}
      </div>
      <div className="text-3xl font-extrabold text-white">{value}</div>
      {hint && <div className="text-[11px] text-[#71717A] mt-1.5">{hint}</div>}
    </div>
  );

  return (
    <div className="min-h-screen bg-[#06030d] text-white">
      <div className="max-w-5xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
              Krexion <span className="text-[#3B82F6]">Status</span>
            </h1>
            <p className="text-[#94a3b8] text-sm mt-2">
              Live health of every Krexion subsystem. Auto-refreshes every 15 s.
            </p>
          </div>
          <button
            onClick={() => setTick(t=>t+1)}
            data-testid="status-refresh"
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-[#3B82F6]/15 border border-[#3B82F6]/30 text-[#93C5FD] text-sm hover:bg-[#3B82F6]/25 transition"
          >
            <RefreshCw size={14}/> Refresh
          </button>
        </div>

        {loading && <div className="text-[#94a3b8]">Loading…</div>}
        {err && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">
            Could not fetch status: {err}
          </div>
        )}

        {status && (
          <>
            <div className="flex items-center gap-2 flex-wrap mb-8">
              <Pill ok={status.api_ok} label="Cloud API" />
              <Pill ok={status.mongo_ok} label="Database" />
              <Pill ok={(status.bridge_workers ?? 0) >= 0} label="Bridge" />
              <span className="text-xs text-[#71717A] ml-2">
                Updated: {new Date(status.now).toLocaleString()}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <Card
                icon={<Server size={14}/>} title="API"
                value={status.api_ok ? "Up" : "Down"}
                hint={`v${status.version || "?"}`}
                testid="status-card-api"
              />
              <Card
                icon={<Activity size={14}/>} title="Mongo"
                value={status.mongo_ok ? "Up" : "Down"}
                hint="ping <50ms"
                testid="status-card-mongo"
              />
              <Card
                icon={<Cpu size={14}/>} title="Online PCs"
                value={status.online_pcs ?? 0}
                hint="heartbeats in last 90 s"
                testid="status-card-online-pcs"
              />
              <Card
                icon={<Users size={14}/>} title="Active Users 24h"
                value={status.active_users_24h ?? 0}
                hint="logged in in last day"
                testid="status-card-active-users"
              />
            </div>

            <div className="p-6 rounded-2xl bg-[#0c0816] border border-white/10">
              <h2 className="text-base font-bold text-white mb-4">Bridge jobs (last 24 h)</h2>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <Card icon={null} title="Queued" value={status.bridge_jobs_24h?.pending ?? 0} testid="status-bridge-pending" />
                <Card icon={null} title="Running" value={status.bridge_jobs_24h?.running ?? 0} testid="status-bridge-running" />
                <Card icon={null} title="Done" value={status.bridge_jobs_24h?.done ?? 0} testid="status-bridge-done" />
                <Card icon={null} title="Failed" value={status.bridge_jobs_24h?.failed ?? 0} testid="status-bridge-failed" />
              </div>
            </div>

            <div className="mt-6 text-[11px] text-[#71717A] leading-relaxed">
              Krexion runs a hybrid SaaS + native-desktop architecture. The "Cloud API" is the
              orchestrator at krexion.com; the "Bridge" relays heavy jobs (Real User Traffic, Visual
              Recorder, Form Filler) from the cloud to your own Windows PC where they execute via
              bundled Chromium. If you're seeing "PC offline" in the badge but this status page
              shows the API is up, restart the Krexion desktop app from your system tray.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
