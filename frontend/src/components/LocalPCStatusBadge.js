/**
 * LocalPCStatusBadge
 * -------------------
 * Shows a compact "Connected to your PC" / "PC offline" badge in the
 * dashboard header so the user knows whether heavy features will be
 * served by their own PC (transparent bridge) or are unavailable.
 *
 * Polls /api/bridge/me/local-status every 15 s when on the cloud edge.
 * Hidden when on a local install (no need — everything runs locally).
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { Cpu, MonitorOff, MonitorCheck } from "lucide-react";
import { useMode } from "../context/ModeContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function LocalPCStatusBadge() {
  const { isCloud, loaded } = useMode();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isCloud) return;
    let cancelled = false;

    async function fetchStatus() {
      try {
        const token = localStorage.getItem("token");
        if (!token) {
          if (!cancelled) setLoading(false);
          return;
        }
        const r = await axios.get(`${BACKEND_URL}/api/bridge/me/local-status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) {
          setStatus(r.data);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    }

    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isCloud]);

  if (!loaded || !isCloud || loading) return null;

  const online = status?.online;
  const ram = status?.ram_gb;
  const cpu = status?.cpu_cores;
  const host = status?.hostname;

  if (online) {
    return (
      <div
        data-testid="local-pc-badge-online"
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-medium"
        title={`Bridge active - heavy features will run on your PC: ${host || "your computer"}`}
      >
        <MonitorCheck size={14} />
        <span className="hidden sm:inline">PC connected</span>
        {ram && (
          <span className="hidden md:inline text-emerald-400/70 font-normal">
            <Cpu size={11} className="inline mr-0.5" />
            {ram} GB
            {cpu ? ` / ${cpu} cores` : ""}
          </span>
        )}
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
      </div>
    );
  }

  return (
    <div
      data-testid="local-pc-badge-offline"
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium"
      title="Heavy features (proxy check, RUT, form filler) need your PC turned on"
    >
      <MonitorOff size={14} />
      <span className="hidden sm:inline">PC offline</span>
      <span className="hidden md:inline text-amber-400/70 font-normal">
        - turn on for heavy features
      </span>
    </div>
  );
}
