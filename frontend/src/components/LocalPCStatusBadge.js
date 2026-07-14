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
import { createPortal } from "react-dom";
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
  RefreshCw,
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
  const [refreshResult, setRefreshResult] = useState(null);
  const [resyncing, setResyncing] = useState(false);

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

  async function resyncToPC(e) {
    // Stop propagation so we don't open the pair modal too
    if (e?.stopPropagation) e.stopPropagation();
    if (resyncing) return;
    setResyncing(true);
    const t = toast.loading("Pushing config to your PC…");
    try {
      const token = localStorage.getItem("token");
      const r = await axios.post(
        `${BACKEND_URL}/api/bridge/resync-to-desktop`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.dismiss(t);
      if (r.data?.ok) {
        toast.success(r.data.message || "PC resync complete");
      } else if (r.data?.online === false) {
        toast.error(r.data.message || "PC is offline");
      } else {
        toast.warning(
          `Partial sync: ${r.data?.message || "see console"}`
        );
        // eslint-disable-next-line no-console
        console.warn("[resync-to-desktop] errors:", r.data?.errors);
      }
    } catch (err) {
      toast.dismiss(t);
      toast.error(
        err?.response?.data?.detail || err?.message || "Resync failed"
      );
    } finally {
      setResyncing(false);
    }
  }

  if (!loaded || !isCloud || loading) return null;

  const online = status?.online;
  const ram = status?.ram_gb;
  const cpu = status?.cpu_cores;
  const host = status?.hostname;

  return (
    <>
      {online ? (
        <span className="inline-flex items-center gap-1">
          <button
            data-testid="local-pc-badge-online"
            onClick={openPair}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-medium hover:bg-emerald-500/20 hover:border-emerald-500/50 transition cursor-pointer"
            title={`Bridge active — click to re-pair or view setup. PC: ${host || "your computer"}`}
            type="button"
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
          </button>
          <button
            data-testid="local-pc-resync-btn"
            onClick={resyncToPC}
            disabled={resyncing}
            className="inline-flex items-center gap-1 px-2 py-1.5 rounded-md bg-sky-500/10 border border-sky-500/30 text-sky-300 text-xs font-medium hover:bg-sky-500/20 hover:border-sky-500/50 transition disabled:opacity-50 disabled:cursor-not-allowed"
            title="Push links & Proxy credentials from cloud to your PC's local database"
            type="button"
          >
            {resyncing ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <RefreshCw size={13} />
            )}
            <span className="hidden lg:inline">Resync to PC</span>
          </button>
        </span>
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
            - Reconnect
          </span>
        </button>
      )}

      {showPair && createPortal(
        <div
          className="fixed inset-0 z-[2147483647] bg-black/85 backdrop-blur-md flex items-start sm:items-center justify-center p-4 overflow-y-auto"
          data-testid="pair-pc-modal"
          onClick={(e)=>{ if(e.target === e.currentTarget) setShowPair(false); }}
          style={{position:"fixed", top:0, left:0, right:0, bottom:0}}
        >
          <div className="bg-[#0f0a18] border border-[#3B82F6]/40 rounded-2xl w-full max-w-2xl max-h-[92vh] my-4 sm:my-8 overflow-hidden flex flex-col shadow-2xl">
            <div className="px-6 py-5 border-b border-white/10 flex items-start justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-widest font-bold mb-1.5 inline-block px-2 py-0.5 rounded bg-[#3B82F6]/20 text-[#3B82F6]">
                  Connect your PC
                </div>
                <h3 className="text-lg font-bold text-white inline-flex items-center gap-2">
                  <Link2 size={18} /> Krexion Desktop
                </h3>
                <p className="text-xs text-[#71717A] mt-1">
                  Install the native Windows app — heavy jobs from
                  krexion.com run on your local machine with full
                  Chromium + Playwright power.
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
                  {/* v1.0.21: "Already installed?" reconnect card.
                      Most repeat users hitting this modal already
                      have the desktop app installed — the badge
                      is just showing stale offline because of a
                      heartbeat timing glitch or because the
                      desktop's tray app got closed. Give them a
                      ONE-CLICK reconnect path instead of forcing
                      a reinstall. */}
                  <div className="mb-4 p-4 rounded-xl bg-amber-500/5 border border-amber-500/30">
                    <div className="text-[10px] uppercase tracking-widest font-bold mb-1.5 inline-block px-2 py-0.5 rounded bg-amber-500/25 text-amber-200">
                      Already installed?
                    </div>
                    <h4 className="text-white font-bold text-base mb-1.5">
                      Reconnect your PC
                    </h4>
                    <p className="text-[#D4D4D8] text-xs mb-3 leading-relaxed">
                      Krexion desktop app already chal rahi hai? 1) System tray
                      me Krexion icon check karein — agar nahi to Start menu
                      se launch karein. 2) Niche button click karke status
                      refresh karein. 3) Status 30 sec me green ho jayega.
                    </p>
                    <div className="flex items-center gap-2 flex-wrap">
                      <button
                        type="button"
                        data-testid="pair-reconnect-refresh"
                        onClick={async () => {
                          setLoading(true);
                          setRefreshResult(null);
                          try {
                            const r = await axios.get(
                              `${BACKEND_URL}/api/bridge/me/local-status`,
                              { headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` } }
                            );
                            setStatus(r.data);
                            if (r.data?.online) {
                              setRefreshResult({type:"ok", text:`PC reconnected! Hostname: ${r.data.hostname || "?"}`});
                              toast.success("PC reconnected!");
                              setTimeout(()=>setShowPair(false), 1200);
                            } else {
                              setRefreshResult({
                                type:"warn",
                                text:`Still offline — last heartbeat ${r.data?.last_seen_sec_ago ?? "never"} sec ago. Make sure Krexion is running in the system tray.`
                              });
                            }
                          } catch (e) {
                            setRefreshResult({type:"err", text:"Status refresh failed - try again."});
                          } finally {
                            setLoading(false);
                          }
                        }}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 text-black font-bold text-sm hover:bg-amber-400 transition"
                      >
                        <MonitorCheck size={15} /> Refresh PC status
                      </button>
                      <span className="text-[11px] text-amber-300/80">
                        Last seen:{" "}
                        {status?.last_seen_sec_ago != null
                          ? `${status.last_seen_sec_ago}s ago`
                          : "never"}
                        {status?.hostname ? ` · ${status.hostname}` : ""}
                      </span>
                    </div>
                    {refreshResult && (
                      <div
                        data-testid="pair-refresh-result"
                        className={`mt-3 p-3 rounded-lg text-sm font-medium border ${
                          refreshResult.type === "ok"
                            ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-200"
                            : refreshResult.type === "warn"
                            ? "bg-amber-500/15 border-amber-500/40 text-amber-200"
                            : "bg-rose-500/15 border-rose-500/40 text-rose-200"
                        }`}
                      >
                        {refreshResult.text}
                      </div>
                    )}
                  </div>

                  {/* v1.0.20: PRIMARY path — download the native
                      installer. The legacy PowerShell flow has been
                      retired because the KrexionBridge scheduled task
                      it created raced our Python sync_client and
                      caused 'feature not supported by PowerShell
                      bridge' errors. The installer self-cleans any
                      pre-existing KrexionBridge task and runs the
                      proper Python bridge. */}
                  <div className="mb-5 p-4 rounded-xl bg-gradient-to-br from-[#3B82F6]/15 to-emerald-500/10 border border-[#3B82F6]/40">
                    <div className="text-[10px] uppercase tracking-widest font-bold mb-1.5 inline-block px-2 py-0.5 rounded bg-emerald-500/30 text-emerald-200">
                      First-time install
                    </div>
                    <h4 className="text-white font-bold text-base mb-1.5">
                      Install Krexion Desktop (Windows)
                    </h4>
                    <p className="text-[#D4D4D8] text-xs mb-3 leading-relaxed">
                      One-click installer · auto-pairs to this account ·
                      bundled Chromium · auto-updates · system tray + dashboard.
                      Heavy jobs from krexion.com run on YOUR machine.
                    </p>
                    <a
                      href="/download"
                      target="_blank"
                      rel="noopener noreferrer"
                      data-testid="pair-download-installer"
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#3B82F6] text-black font-bold text-sm hover:bg-[#60A5FA] transition shadow-lg shadow-[#3B82F6]/30"
                    >
                      <Link2 size={15} />
                      Download Krexion-Setup.exe
                    </a>
                    <div className="mt-3 text-[11px] text-[#94a3b8] leading-snug">
                      <strong>Steps:</strong> 1) Download installer · 2) Run as
                      Admin · 3) Paste license key when prompted · 4) F5 this
                      page — badge will turn green.
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs">
                    <strong>Your License Key:</strong>{" "}
                    <code className="bg-black/40 px-1.5 py-0.5 rounded text-emerald-200 select-all">
                      {pair.license_key}
                    </code>
                    <br />
                    <span className="text-emerald-200/80">
                      {pair.created
                        ? "Yeh license abhi banayi gayi hai. Safe rakhein — installer me yahi paste karna hai, aur re-install ke time bhi kaam aayegi."
                        : "Aap ke account pe pehle se license thi — wahi use kar raha hun. Installer me yeh paste karein."}
                    </span>
                  </div>

                  {/* Legacy power-user fallback. Kept for advanced users
                      who can't run an installer (locked-down machines)
                      but hidden by default. */}
                  <details className="mt-4 group">
                    <summary className="text-[11px] text-[#71717A] cursor-pointer hover:text-[#93C5FD]">
                      Advanced: PowerShell-only setup (no installer) ▾
                    </summary>
                    <div className="mt-3">
                      <ol className="space-y-2 list-decimal list-inside mb-3 text-xs text-[#94a3b8]">
                        {(pair.instructions || []).map((line, i) => (
                          <li key={i}>{line}</li>
                        ))}
                      </ol>
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
                      <p className="mt-2 text-[10px] text-amber-300/80 leading-snug">
                        ⚠ PowerShell bridge sirf adspower/* features handle
                        karta hai. RUT / Form Filler / Visual Recorder ke
                        liye installer use karein.
                      </p>
                    </div>
                  </details>
                </>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
