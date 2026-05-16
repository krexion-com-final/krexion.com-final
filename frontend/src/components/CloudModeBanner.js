import React, { useState } from "react";
import { Download, X, Zap } from "lucide-react";
import { useMode } from "../context/ModeContext";

/**
 * CloudModeBanner
 * ----------------
 * Shows ONLY on the cloud edge (krexion.com). Informs the user that heavy
 * features (proxy checks, real-user-traffic, form filler, etc.) run on the
 * Krexion desktop app — keeps the cloud snappy for everyone.
 * Dismissable per-session (stored in sessionStorage).
 */
export default function CloudModeBanner() {
  const { isCloud, downloadUrl, loaded } = useMode();
  const [dismissed, setDismissed] = useState(
    () => typeof window !== "undefined" && sessionStorage.getItem("cloud_banner_dismissed") === "1"
  );

  if (!loaded || !isCloud || dismissed) return null;

  return (
    <div
      data-testid="cloud-mode-banner"
      className="relative bg-gradient-to-r from-[#1e1530] via-[#2a1845] to-[#1e1530] border-b border-[#A78BFA]/30 text-white"
    >
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center gap-3 text-sm">
        <div className="shrink-0 w-7 h-7 rounded-md bg-[#A78BFA]/20 border border-[#A78BFA]/40 flex items-center justify-center">
          <Zap size={14} className="text-[#A78BFA]" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="font-semibold text-white">Cloud (light) mode</span>{" "}
          <span className="text-[#D4D4D8]">
            — heavy features (proxy check, real-user-traffic, form filler) run on the desktop app for unlimited speed.
          </span>
        </div>
        <a
          href={downloadUrl || "https://krexion.com/download"}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="cloud-banner-download"
          className="shrink-0 inline-flex items-center gap-1.5 bg-[#A78BFA] text-black font-semibold text-xs px-3 py-1.5 rounded-md hover:bg-[#C4B5FD] transition"
        >
          <Download size={12} /> Get desktop app
        </a>
        <button
          onClick={() => {
            sessionStorage.setItem("cloud_banner_dismissed", "1");
            setDismissed(true);
          }}
          className="shrink-0 text-[#A1A1AA] hover:text-white p-1"
          aria-label="Dismiss"
          data-testid="cloud-banner-dismiss"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
