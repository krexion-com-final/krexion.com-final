/**
 * LocalPCOfflineDialog (2026-05)
 * --------------------------------
 * A globally-mounted modal that pops up the moment a heavy-feature
 * request is blocked because the customer's PC is offline / desktop
 * app isn't running. Replaces the easy-to-miss toast with a clear
 * "you cannot run this on the VPS — turn on your PC" dialog so the
 * customer immediately understands what's happening.
 *
 * Why a custom event (instead of putting state in a context):
 *   The trigger lives inside the axios response interceptor
 *   (utils/cloudGateInterceptor.js) which has no access to React
 *   state. Using `window.dispatchEvent(new CustomEvent('krexion:local-pc-offline'))`
 *   is the simplest non-invasive bridge — no provider tree changes,
 *   no extra deps. The dialog mounts once in App.js and listens.
 *
 * Lifecycle:
 *   • Interceptor catches a 503 with detail.code === "local_pc_offline"
 *     → dispatches a CustomEvent with the detail object as payload.
 *   • This component receives the event, stores the detail in state,
 *     and opens the modal.
 *   • Same toast also fires (for users who already dismissed the modal
 *     and just want a brief reminder on subsequent attempts).
 */
import React, { useEffect, useState } from "react";
import { PowerOff, Power, ExternalLink, AlertTriangle, X } from "lucide-react";

export default function LocalPCOfflineDialog() {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    const handler = (e) => {
      setDetail(e.detail || null);
      setOpen(true);
    };
    window.addEventListener("krexion:local-pc-offline", handler);
    return () => window.removeEventListener("krexion:local-pc-offline", handler);
  }, []);

  if (!open) return null;

  const localOnline = !!(detail?.local_status && detail.local_status.online);
  const hint =
    detail?.actionable_hint ||
    (localOnline ? "open_desktop_app" : "install_desktop_app");
  const downloadUrl = detail?.download_url || "https://krexion.com/download";

  // Tailor headline + body + CTA to the actual reason. Three states:
  //   • PC online (just not actively running heavy feature) → open desktop
  //   • PC offline / stale heartbeat → turn on PC
  //   • No bridge ever registered → install desktop app
  let icon, headline, body, ctaLabel, ctaHref;
  if (hint === "open_desktop_app" || hint === "use_desktop_app" || localOnline) {
    icon = <Power size={42} className="text-emerald-400" />;
    headline = "Open the Krexion desktop app";
    body =
      "Aap ka PC online hai ✓ — magar yeh heavy feature (Real User Traffic / Form Filler / Visual Recorder) aap ke desktop app se chalti hai, cloud server pe nahi. Apne PC pe Krexion app kholein aur waheen se yehi job submit karein. Data automatically sync ho jayega.";
    ctaLabel = "How to open desktop app";
    ctaHref = "/guide";
  } else if (hint === "turn_on_pc") {
    icon = <PowerOff size={42} className="text-yellow-400" />;
    headline = "Your PC is OFFLINE — turn it on first";
    body =
      "Heavy job VPS pe nahi chala sakte (server ko overload se bachane ke liye). Apna computer ON karein, Krexion desktop app start hone ka intezaar karein (10-20 seconds mein cloud reconnect ho jayega), phir yeh job DOBARA submit karein. Tab tak yeh request VPS pe queue NAHI hogi — aap ka data 100% safe hai.";
    ctaLabel = "Setup guide";
    ctaHref = "/guide";
  } else {
    icon = <AlertTriangle size={42} className="text-orange-400" />;
    headline = "Krexion desktop app required";
    body =
      detail?.message ||
      "Yeh heavy feature sirf aap ke PC ke desktop app pe chalti hai. License ke saath free download karein, install karein, login karein — phir yeh job chala sakein ge.";
    ctaLabel = "Download desktop app";
    ctaHref = downloadUrl;
  }

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      data-testid="local-pc-offline-dialog"
      onClick={(e) => {
        if (e.target === e.currentTarget) setOpen(false);
      }}
    >
      <div className="relative w-full max-w-lg rounded-2xl border border-yellow-500/30 bg-zinc-900 shadow-2xl shadow-yellow-500/10">
        <button
          onClick={() => setOpen(false)}
          className="absolute top-3 right-3 text-zinc-500 hover:text-zinc-200 p-1 rounded-md hover:bg-zinc-800"
          aria-label="Close"
          data-testid="local-pc-offline-close"
        >
          <X size={18} />
        </button>
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className="shrink-0">{icon}</div>
            <div className="flex-1">
              <h2 className="text-lg font-bold text-zinc-100 mb-2">
                {headline}
              </h2>
              <p className="text-sm text-zinc-300 leading-relaxed">{body}</p>
            </div>
          </div>
          <div className="mt-6 flex flex-col sm:flex-row gap-2 justify-end">
            <button
              onClick={() => setOpen(false)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-zinc-300 hover:bg-zinc-800 transition"
              data-testid="local-pc-offline-dismiss"
            >
              Got it
            </button>
            <a
              href={ctaHref}
              target={ctaHref.startsWith("http") ? "_blank" : "_self"}
              rel="noreferrer"
              onClick={() => setOpen(false)}
              className="px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white inline-flex items-center gap-1.5 transition"
              data-testid="local-pc-offline-cta"
            >
              {ctaLabel}
              <ExternalLink size={14} />
            </a>
          </div>
          <div className="mt-4 pt-3 border-t border-zinc-800 text-[11px] text-zinc-500">
            <span className="font-semibold text-zinc-400">Why?</span> Heavy
            jobs (RUT / Form Filler / Visual Recorder / bulk proxy tests)
            require lots of RAM &amp; CPU. Running them on the shared VPS
            slows everyone down, so they only execute on your own PC.
          </div>
        </div>
      </div>
    </div>
  );
}
