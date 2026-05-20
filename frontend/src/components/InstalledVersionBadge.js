import { useEffect, useState } from "react";
import axios from "axios";

/**
 * InstalledVersionBadge
 * --------------------
 * Shows the customer the EXACT version their local install is currently
 * running. Polls /api/system/public-latest (no-auth) every 60s — that
 * endpoint returns `current` from the VERSION file on disk, so it
 * always reflects what was actually pulled from git (not what was
 * published in the admin panel). If a newer version exists, the
 * badge turns blue with a small "•" indicator next to it.
 */
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function InstalledVersionBadge() {
  const [current, setCurrent] = useState("");
  const [hasUpdate, setHasUpdate] = useState(false);

  useEffect(() => {
    let mounted = true;
    const fetchVersion = async () => {
      try {
        const r = await axios.get(`${API}/system/public-latest`, { timeout: 5000 });
        if (!mounted) return;
        setCurrent(r.data?.current || "");
        setHasUpdate(Boolean(r.data?.update_available));
      } catch (_e) {
        // silent — badge just hides
      }
    };
    fetchVersion();
    const t = setInterval(fetchVersion, 60_000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, []);

  if (!current) return null;

  return (
    <span
      data-testid="installed-version-badge"
      title={hasUpdate ? `New version available — open Releases to update` : `You are on the latest version`}
      className="text-[10px] font-semibold px-2 py-0.5 rounded-full select-none"
      style={{
        background: hasUpdate
          ? "linear-gradient(90deg, rgba(79,127,255,0.35), rgba(79,127,255,0.15))"
          : "rgba(255,255,255,0.08)",
        color: hasUpdate ? "#A8C2FF" : "#9CA3AF",
        border: hasUpdate ? "1px solid rgba(79,127,255,0.5)" : "1px solid rgba(255,255,255,0.1)",
        letterSpacing: "0.02em",
      }}
    >
      v{current}{hasUpdate ? " •" : ""}
    </span>
  );
}
