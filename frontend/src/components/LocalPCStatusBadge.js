/**
 * LocalPCStatusBadge v2 - Pair-aware
 * ----------------------------------
 * Compact header badge that:
 *   - Polls /api/bridge/me/local-status every 15s
 *   - GREEN if heartbeat <90s old
 *   - AMBER ("offline") + clickable to open a "Pair my PC" modal that
 *     fetches the license key + ready-to-paste PowerShell command
 *
 * Hidden when running on a local install (no need - everything is local).
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import {
  Cpu,
  MonitorOff,
  MonitorCheck,
  X,
  Copy,
  Check,
  Loader2,
  Link2,
} from "lucide-react";
import { toast } from "sonner";
import { useMode } from "../context/ModeContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function LocalPCStatusBadge() {
  const { isCloud, loaded } = useMode();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showPair, setShowPair] = useState(false);
  const [pair, setPair] = useState(null);
  const [pairLoading, setPairLoading] = useState(false);
  const [copied, setCopied] = useState(false);

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
        const r = await axios.get(
          `${BACKEND_URL}/api/bridge/me/local-status`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
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

  async function openPair() {
    setShowPair(true);
    if (pair) return; // cached
    setPairLoading(true);
    try {
      const token = localStorage.getItem("token");
      const r = await axios.post(
        `${BACKEND_URL}/api/bridge/pair`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setPair(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Pair fail");
    } finally {
      setPairLoading(false);
    }
  }

  function copyCommand() {
    if (!pair?.powershell_command) return;
    navigator.clipboard.writeText(pair.powershell_command);
    setCopied(true);
    toast.success("PowerShell command copied!");
    setTimeout(() => setCopied(false), 2500);
  }

  if (!loaded || !isCloud || loading) return null;

  const online = status?.online;
  const ram = status?.ram_gb;
  const cpu = status?.cpu_cores;
  const host = status?.hostname;

  return (
    <>
      {online ? (
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
      ) : (
        <button
          data-testid="local-pc-badge-offline"
          onClick={openPair}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium hover:bg-amber-500/20 hover:border-amber-500/50 transition cursor-pointer"
          title="Click to pair your PC with this account"
        >
          <MonitorOff size={14} />
          <span className="hidden sm:inline">PC offline</span>
          <span className="hidden md:inline text-amber-400/80 font-semibold underline">
            - Pair my PC
          </span>
        </button>
      )}

      {showPair && (
        <div
          className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          data-testid="pair-pc-modal"
        >
          <div className="bg-[#0f0a18] border border-[#3B82F6]/40 rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col shadow-2xl">
            <div className="px-6 py-5 border-b border-white/10 flex items-start justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-widest font-bold mb-1.5 inline-block px-2 py-0.5 rounded bg-[#3B82F6]/20 text-[#3B82F6]">
                  One-time pairing
                </div>
                <h3 className="text-lg font-bold text-white inline-flex items-center gap-2">
                  <Link2 size={18} /> Pair my PC
                </h3>
                <p className="text-xs text-[#71717A] mt-1">
                  Aap ke local install ko is account se connect kar raha hun - ek baar setup.
                </p>
              </div>
              <button
                onClick={() => setShowPair(false)}
                data-testid="pair-close"
                className="text-[#71717A] hover:text-white p-1"
              >
                <X size={18} />
              </button>
            </div>
            <div className="px-6 py-5 overflow-auto flex-1 text-sm text-[#D4D4D8]">
              {pairLoading && (
                <div className="flex items-center gap-2 text-[#71717A] py-8 justify-center">
                  <Loader2 size={16} className="animate-spin" />
                  License key generate kar raha hun...
                </div>
              )}
              {!pairLoading && pair && (
                <>
                  <ol className="space-y-2 list-decimal list-inside mb-4">
                    {(pair.instructions || []).map((line, i) => (
                      <li key={i} className="text-[#D4D4D8]">
                        {line}
                      </li>
                    ))}
                  </ol>
                  <div className="mt-4">
                    <div className="text-xs uppercase tracking-wider text-[#71717A] mb-2">
                      PowerShell command (copy + paste)
                    </div>
                    <div className="relative">
                      <pre
                        data-testid="pair-command"
                        className="bg-black/60 border border-white/10 rounded-lg p-3 text-xs text-emerald-200 font-mono overflow-x-auto whitespace-pre-wrap break-all"
                      >
                        {pair.powershell_command}
                      </pre>
                      <button
                        onClick={copyCommand}
                        data-testid="pair-copy"
                        className="absolute top-2 right-2 inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded bg-[#3B82F6] text-black font-semibold hover:bg-[#60A5FA] transition"
                      >
                        {copied ? (
                          <>
                            <Check size={13} /> Copied
                          </>
                        ) : (
                          <>
                            <Copy size={13} /> Copy
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                  <div className="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs">
                    <strong>License key:</strong>{" "}
                    <code className="bg-black/40 px-1 py-0.5 rounded text-emerald-200">
                      {pair.license_key}
                    </code>
                    <br />
                    {pair.created
                      ? "Yeh license abhi banayi gayi hai. Safe rakhein - re-install ke time kaam aayegi."
                      : "Aap ke account pe already ek license thi - wahi use kar raha hun."}
                  </div>
                  <div className="mt-3 p-3 rounded-lg bg-[#3B82F6]/10 border border-[#3B82F6]/30 text-[#93C5FD] text-xs">
                    <strong>Tip:</strong> Command paste karne ke baad 30 sec wait karein, phir{" "}
                    <strong>krexion.com pe F5 refresh</strong> karein - is badge ki jagah{" "}
                    <strong>green "PC connected"</strong> dikhna chahye.
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
