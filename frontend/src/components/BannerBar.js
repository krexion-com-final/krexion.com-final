import React, { useEffect, useState } from "react";
import { Megaphone, X, ExternalLink } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const LS_DISMISSED = "krexion_dismissed_banners_v1";

const themeClass = (t) => {
  switch (t) {
    case "promo":   return "bg-gradient-to-r from-fuchsia-600 to-pink-600";
    case "success": return "bg-gradient-to-r from-emerald-600 to-teal-600";
    case "warning": return "bg-gradient-to-r from-amber-500 to-orange-600";
    case "danger":  return "bg-gradient-to-r from-red-600 to-rose-600";
    default:        return "bg-gradient-to-r from-blue-600 to-indigo-600";
  }
};

export default function BannerBar() {
  const [banners, setBanners] = useState([]);
  const [dismissed, setDismissed] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem(LS_DISMISSED) || "[]")); }
    catch { return new Set(); }
  });

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/banners/active`);
        if (!r.ok) return;
        const data = await r.json();
        if (mounted) setBanners(Array.isArray(data) ? data : []);
      } catch {}
    };
    load();
    // Refresh every 2 mins (banners are admin-curated, low velocity)
    const t = setInterval(load, 120000);
    return () => { mounted = false; clearInterval(t); };
  }, []);

  const dismiss = (id) => {
    const next = new Set(dismissed);
    next.add(id);
    setDismissed(next);
    try { localStorage.setItem(LS_DISMISSED, JSON.stringify([...next])); } catch {}
  };

  const visible = banners.filter((b) => !dismissed.has(b.id));
  if (visible.length === 0) return null;

  return (
    <div className="space-y-1" data-testid="banner-bar">
      {visible.map((b) => (
        <div
          key={b.id}
          className={`${themeClass(b.theme)} text-white px-4 py-2.5 flex items-center gap-3 shadow`}
          data-testid={`banner-${b.id}`}
        >
          <Megaphone className="w-4 h-4 flex-shrink-0 opacity-90" />
          <span className="flex-1 text-sm">{b.message}</span>
          {b.cta_label && b.cta_url && (
            <a
              href={b.cta_url}
              target={b.cta_url.startsWith("http") ? "_blank" : undefined}
              rel="noopener noreferrer"
              className="px-3 py-1 rounded bg-white/20 hover:bg-white/30 text-xs font-semibold flex items-center gap-1 transition-colors"
              data-testid={`banner-cta-${b.id}`}
            >
              {b.cta_label}
              {b.cta_url.startsWith("http") && <ExternalLink className="w-3 h-3" />}
            </a>
          )}
          {b.dismissible !== false && (
            <button
              onClick={() => dismiss(b.id)}
              className="p-1 rounded hover:bg-white/20"
              title="Dismiss"
              data-testid={`banner-dismiss-${b.id}`}
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
