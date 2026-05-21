import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";

/**
 * Reusable mobile menu (hamburger) for public/marketing pages.
 * Renders a hamburger icon that toggles a dropdown panel containing
 * the same nav links shown on desktop. Visible only on mobile (`md:hidden`).
 *
 * Props:
 *   links: [{ to, label, external? }]  — external links use <a>, internal use <Link>
 *   ctaTo: string  — primary CTA route (e.g. "/pricing")
 *   ctaLabel: string  — primary CTA text (defaults to "Get started")
 *   accent: "blue" | "purple"  — accent color for active CTA
 */
export default function PublicMobileMenu({
  links = [],
  ctaTo = "/pricing",
  ctaLabel = "Get started",
  accent = "blue",
}) {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  // Close menu on route change
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  // Lock body scroll when menu is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const ctaClass =
    accent === "purple"
      ? "bg-[#A78BFA] text-black hover:bg-[#C4B5FD]"
      : "bg-blue-500 text-white hover:bg-blue-400";

  return (
    <div className="md:hidden flex items-center gap-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        data-testid="public-mobile-menu-toggle"
        className="p-2 -mr-2 text-zinc-300 hover:text-white transition"
      >
        {open ? <X size={22} /> : <Menu size={22} />}
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 top-[57px] bg-black/70 backdrop-blur-sm z-40"
            onClick={() => setOpen(false)}
            data-testid="public-mobile-menu-backdrop"
          />
          {/* Panel */}
          <div
            className="fixed left-0 right-0 top-[57px] bg-black/95 border-b border-white/10 z-50 px-6 py-4 flex flex-col gap-1"
            data-testid="public-mobile-menu-panel"
          >
            {links.map((l) => {
              const isActive = location.pathname === l.to;
              const baseCls = `block py-3 text-base transition border-b border-white/5 last:border-b-0 ${
                isActive ? "text-white" : "text-zinc-300 hover:text-white"
              }`;
              if (l.external || (typeof l.to === "string" && l.to.startsWith("#"))) {
                return (
                  <a
                    key={l.to + l.label}
                    href={l.to}
                    className={baseCls}
                    onClick={() => setOpen(false)}
                    data-testid={`mobile-menu-link-${l.label.toLowerCase().replace(/\s+/g, "-")}`}
                  >
                    {l.label}
                  </a>
                );
              }
              return (
                <Link
                  key={l.to + l.label}
                  to={l.to}
                  className={baseCls}
                  data-testid={`mobile-menu-link-${l.label.toLowerCase().replace(/\s+/g, "-")}`}
                >
                  {l.label}
                </Link>
              );
            })}
            {ctaTo && (
              <Link
                to={ctaTo}
                className={`mt-3 inline-flex items-center justify-center px-4 py-2.5 rounded-md font-medium text-sm transition ${ctaClass}`}
                data-testid="mobile-menu-cta"
              >
                {ctaLabel}
              </Link>
            )}
          </div>
        </>
      )}
    </div>
  );
}
